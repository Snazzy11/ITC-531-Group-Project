# Walkthrough: from a lost item to a confirmed match

This takes about 15 minutes. You start a fresh stack with the demo data, then play two people:

- **Alex**, a student who lost an umbrella. Alex logs in, posts it, looks at what the app suggests, and confirms the match.
- **The admin**, who finds an item with no suggestions and runs a match search for it.

The whole time, two other windows show the matching worker and the event log reacting. Each step says what to
run, what you should see, and why. Some steps ask you to predict the result before you run the command.

## The idea in one picture

```mermaid
sequenceDiagram
    participant You as You (curl)
    participant API
    participant MQ as RabbitMQ
    participant W as matching_worker
    participant L as logger
    You->>API: POST /items
    API->>MQ: event item.created
    API->>MQ: job {"item_id": 11}
    API-->>You: 201, the new item
    MQ->>W: job
    W->>W: score item 11 against open found items, keep the best 5
    W->>MQ: event match.potential_found (one per new pair)
    MQ->>L: every event
    L->>L: append a line to /app/logs/events.jsonl
    You->>API: GET /items/11/potential-matches
```

Three things to keep in mind:

1. **Posting an item doesn't do the matching.** The API saves the item, puts a job on RabbitMQ and answers right
   away. The matching worker does the scoring a moment later.
2. **A suggestion is a lost/found pair with a score.** For each distinct word in the item's description that also
   appears in the other description, the pair gets 0.25. Repeats of a word add 0.1. Common words like "the", "with",
   "lost" and "found" don't count. Only `open` items of the other type are considered, and each item keeps its best 5.
3. **Every step publishes an event**, and the `logger` service writes each event as one line of
   `/app/logs/events.jsonl`. That file is the record of what happened.

## Before you start

- Docker with compose, `curl` and `jq`.
- **bash.** The commands use bash syntax. If your terminal runs fish, type `bash` first.
- In `.env.local`:
  - `ADMIN_DISPLAY_NAME` and `ADMIN_PASSWORD` set. That's the admin you use in step 7.
  - `DEMO_USER_PASSWORD` set to something 6 to 72 characters long. Every demo user signs in with it.
  - Storage settings that work (see `.env.local.example`).
- Run everything from the repo root.

## 1. Start from a clean slate

> **Warning:** `--volumes` deletes the database, the queue, the event log and stored photos. The walkthrough needs
> it because demo data is only created in a brand-new database.

```bash
docker compose --env-file .env.local down --volumes
docker compose --env-file .env.local up -d --build --wait
curl -s http://localhost:8000/api/v1/health | jq -c
```

You should see:

```
{"status":"ok","checks":{"database":"ok"}}
```

`--wait` returns once the API reports healthy. While it started, the API did all of this:

- created the admin, 3 demo users, 3 locations and 10 items
- matched the two water bottles
- queued one matching job, for the lost black backpack

## 2. Open two windows to watch

**Terminal 2: the event log**, showing every event as one compact line:

```bash
docker compose --env-file .env.local exec -T logger tail -n +1 -f /app/logs/events.jsonl \
  | jq -c '{type: .routing_key, source: .event.source, payload: .event.payload}'
```

The three suggestions the worker made for the backpack at startup should already be there:

```
{"type":"match.potential_found","source":"matching-worker","payload":{"lost_item_id":1,"found_item_id":2,"score":1.5}}
{"type":"match.potential_found","source":"matching-worker","payload":{"lost_item_id":1,"found_item_id":6,"score":0.25}}
{"type":"match.potential_found","source":"matching-worker","payload":{"lost_item_id":1,"found_item_id":8,"score":0.25}}
```

**Terminal 3: the matching worker and the notifier:**

```bash
docker compose --env-file .env.local logs -f matching_worker notifier
```

Look for these lines:

- `INFO Item 1: 3 suggestions, 3 new` from the matching worker.
- A `Would notify for match.potential_found` line from the notifier for each suggestion. The notifier doesn't send
  anything yet; it only logs what it would send.

Keep both windows open. Run everything else in terminal 1.

## 3. Set up terminal 1

```bash
API=http://localhost:8000/api/v1
JSON='Content-Type: application/json'
login() {
  curl -s -X POST "$API/auth/login" --data-urlencode "username=$1" --data-urlencode "password=$2" | jq -r .access_token
}
env_value() { grep "^$1=" .env.local | cut -d= -f2-; }
ADMIN_DISPLAY_NAME=$(env_value ADMIN_DISPLAY_NAME)
ADMIN_PASSWORD=$(env_value ADMIN_PASSWORD)
DEMO_USER_PASSWORD=$(env_value DEMO_USER_PASSWORD)
```

`login NAME PASSWORD` prints a token. The last three lines copy your settings out of `.env.local`. If you put quotes
around those values, set the three variables by hand instead.

## 4. Look around (no login needed)

Browsing is public:

```bash
curl -s "$API/items?limit=50" | jq -c '.[] | {id, name, type, status}'
```

```
{"id":10,"name":"Umbrella","type":1,"status":"open"}
{"id":9,"name":"Grey hoodie","type":0,"status":"open"}
{"id":8,"name":"Car keys","type":1,"status":"open"}
{"id":7,"name":"Wireless earbuds","type":0,"status":"open"}
{"id":6,"name":"Blue lanyard","type":1,"status":"open"}
{"id":5,"name":"Student ID card","type":0,"status":"open"}
{"id":4,"name":"Water bottle","type":1,"status":"matched"}
{"id":3,"name":"Silver water bottle","type":0,"status":"matched"}
{"id":2,"name":"Black backpack","type":1,"status":"open"}
{"id":1,"name":"Black backpack","type":0,"status":"open"}
```

Newest first. `type` 0 is lost and 1 is found. The two water bottles (3 and 4) are already matched to each other.

Now the suggestions for item 1, the lost black backpack:

```bash
curl -s "$API/items/1/potential-matches" | jq -c '.[] | {found_item_id, score}'
```

```
{"found_item_id":2,"score":1.5}
{"found_item_id":6,"score":0.25}
{"found_item_id":8,"score":0.25}
```

> **Think it through:** Without the common words, the backpack's description is *black, backpack, laptop, sleeve,
> red, keychain, zipper, left, study, table, second, floor*.
>
> - The found backpack (2) shares six of them (black, backpack, red, keychain, zipper, table): 6 × 0.25 = 1.5.
> - The lanyard (6) only shares "floor", and the car keys (8) only share "black".
> - The umbrella (10) shares nothing, so it isn't listed. A pair that scores 0 is never kept.

## 5. Log in as Alex and post a lost item

```bash
ALEX=$(login alex-rivera "$DEMO_USER_PASSWORD")
echo "${ALEX:0:20}..."
curl -s $API/auth/me -H "Authorization: Bearer $ALEX" | jq -c '{id, display_name, roles: [.roles[].name]}'
```

The token starts with `eyJ`, and `/auth/me` shows who it belongs to:

```
{"id":2,"display_name":"alex-rivera","roles":["user"]}
```

If `$ALEX` is `null`, the password was wrong. See the last section.

Alex lost a navy umbrella near the library entrance.

> **Predict:** Item 10 is a found "Umbrella" described as *"Navy blue compact umbrella with a wooden handle, found in
> the umbrella stand by the main entrance."* Which items will be suggested for Alex's post, and which will come first?

```bash
LOST=$(curl -s -X POST $API/items -H "$JSON" -H "Authorization: Bearer $ALEX" \
  -d '{"name":"Navy umbrella","description":"Navy blue compact umbrella with a wooden handle, left near the main entrance of the library","type":0,"location_id":1}' \
  | jq .id)
echo "new lost item: $LOST"
```

```
new lost item: 11
```

Now look at the other windows:

- **Terminal 3:** `INFO Item 11: 2 suggestions, 2 new`.
- **Terminal 2:** the post, then the two suggestions the worker made a moment later:

```
{"type":"item.created","source":"campus-seekr-api","payload":{"item_id":11}}
{"type":"match.potential_found","source":"matching-worker","payload":{"lost_item_id":11,"found_item_id":10,"score":2.0}}
{"type":"match.potential_found","source":"matching-worker","payload":{"lost_item_id":11,"found_item_id":6,"score":0.25}}
```

Ask the API for them. The `sleep` gives the worker a moment, in case you pasted straight through:

```bash
sleep 2
curl -s "$API/items/$LOST/potential-matches" | jq -c '.[] | {found_item_id, score}'
```

```
{"found_item_id":10,"score":2.0}
{"found_item_id":6,"score":0.25}
```

> **Check:** The umbrella shares eight words (navy, blue, compact, umbrella, wooden, handle, main, entrance):
> 8 × 0.25 = 2.0. The lanyard only shares "blue". "With", "the" and "near" don't count.

If the list is empty, the worker hasn't finished yet. Run the command again. If it stays empty, look at terminal 3.

## 6. Confirm the match

Alex recognises item 10 as their umbrella:

```bash
FOUND=$(curl -s "$API/items/$LOST/potential-matches" | jq '.[0].found_item_id')
echo "top suggestion: $FOUND"
MATCH=$(curl -s -X POST $API/matches -H "$JSON" -H "Authorization: Bearer $ALEX" \
  -d "{\"lost_item_id\":$LOST,\"found_item_id\":$FOUND}" | jq .id)
echo "match: $MATCH"
curl -s "$API/items/$LOST" | jq -c '{id, name, status}'
curl -s "$API/items/$FOUND" | jq -c '{id, name, status}'
```

```
top suggestion: 10
match: 2
{"id":11,"name":"Navy umbrella","status":"matched"}
{"id":10,"name":"Umbrella","status":"matched"}
```

This is match 2 because match 1 is the water bottles. In the other windows:

- **Terminal 2:** `{"type":"match.confirmed",...,"payload":{"match_id":2,"lost_item_id":11,"found_item_id":10}}`
- **Terminal 3:** a `Would notify for match.confirmed` line from the notifier.

Now look at the suggestions again:

```bash
curl -s "$API/items/$LOST/potential-matches" | jq -c
```

```
[]
```

> **Why empty?** The suggestions are still stored. A pair is only shown while both of its items are `open`, because
> `POST /matches` would refuse it otherwise. Try matching the same pair again:

```bash
curl -s -X POST $API/matches -H "$JSON" -H "Authorization: Bearer $ALEX" \
  -d "{\"lost_item_id\":$LOST,\"found_item_id\":$FOUND}" | jq -c '.error | {code, detail}'
```

```
{"code":"ITEM_NOT_OPEN","detail":"item 11 is matched and cannot be matched"}
```

## 7. Log in as the admin and run a match search

```bash
ADMIN=$(login "$ADMIN_DISPLAY_NAME" "$ADMIN_PASSWORD")
curl -s $API/auth/me -H "Authorization: Bearer $ADMIN" | jq -c '{display_name, roles: [.roles[].name]}'
```

```
{"display_name":"<your ADMIN_DISPLAY_NAME>","roles":["admin"]}
```

Item 5 is a lost student ID card. Startup only ran matching for the backpack, so the ID card has no suggestions yet:

```bash
ID_CARD=$(curl -s "$API/items?q=student&type=0" | jq '.[0].id')
curl -s "$API/items/$ID_CARD/potential-matches" | jq -c
```

```
[]
```

Only an admin can start a search by hand. First check that nobody else can, with no token and then as Alex:

```bash
curl -s -X POST "$API/items/$ID_CARD/match-search" | jq -c '.error.code'
curl -s -X POST "$API/items/$ID_CARD/match-search" -H "Authorization: Bearer $ALEX" | jq -c '.error | {code, detail}'
```

```
"UNAUTHENTICATED"
{"code":"FORBIDDEN","detail":"requires one of: admin"}
```

That's a 401 with no token (the API doesn't know who you are) and a 403 for Alex (it knows, and the answer is no).

> **Predict:** The ID card was *"in a clear plastic holder on a blue lanyard, probably dropped near the printers on
> the first floor."* Which found item will come out on top? Will the umbrella (item 10) be suggested?

Now run it as the admin:

```bash
curl -s -X POST "$API/items/$ID_CARD/match-search" -H "Authorization: Bearer $ADMIN" | jq -c
```

```
{"item_id":5,"status":"queued"}
```

That's a 202: the job is queued, not finished. Terminal 3 then shows `INFO Item 5: 1 suggestions, 1 new`. Check the
result:

```bash
sleep 2
curl -s "$API/items/$ID_CARD/potential-matches" | jq -c '.[] | {found_item_id, score}'
```

```
{"found_item_id":6,"score":2.0}
```

> **Check:** The blue lanyard (6) shares eight words: card, clear, holder, blue, lanyard, printers, first, floor. The
> umbrella shares "blue" too, but it's matched now, so the worker skipped it.

A search for an item that can't be matched is refused:

```bash
curl -s -X POST "$API/items/$LOST/match-search" -H "Authorization: Bearer $ADMIN" | jq -c '.error | {code, detail}'
```

```
{"code":"ITEM_NOT_OPEN","detail":"item 11 is matched and cannot be matched"}
```

## 8. Optional: undo the match

Unmatching puts both items back to `open`, which automatically queues matching for both:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "$API/matches/$MATCH" -H "Authorization: Bearer $ALEX"
curl -s "$API/items/$LOST" | jq -c '{id, name, status}'
sleep 2
curl -s "$API/items/$LOST/potential-matches" | jq -c '.[] | {found_item_id, score}'
```

```
204
{"id":11,"name":"Navy umbrella","status":"open"}
{"found_item_id":10,"score":2.1}
{"found_item_id":6,"score":0.25}
```

What to notice:

- **Terminal 3** shows `Item 11: 2 suggestions, 0 new` and `Item 10: 2 suggestions, 1 new`.
- **Terminal 2** gets only one new `match.potential_found`, for the ID card and the umbrella (5 → 10). Pairs that
  were already suggested aren't announced again, so nobody is notified twice. The umbrella couldn't be suggested for
  the ID card while it was matched, so that pair really is new.
- **Why 2.1 now?** The found umbrella's re-run scored the pair from its own description, where "umbrella" appears
  twice. The repeat adds 0.1. A pair's score comes from whichever item's run scored it last.

## What you just checked

| Step | What it shows |
|---|---|
| 1, 4 | The stack starts, browsing is public, and the demo data and startup matching ran |
| 5 | Posting an item queues matching on RabbitMQ. The worker scores only `open` items of the other type, and common words don't count |
| 6 | Confirming a match sets both items to `matched`, hides their suggestions, and blocks matching them again (409) |
| 7 | `match-search` is admin-only (401 with no token, 403 for a user, 202 for the admin) and refuses closed items (409) |
| 8 | Reopening items re-runs matching without repeating notifications |
| 2 | Every one of these left a line in `/app/logs/events.jsonl`, written by the logger service |

## Cleaning up

Stop terminals 2 and 3 with Ctrl-C. Then either keep the data or delete everything:

```bash
docker compose --env-file .env.local down            # keeps the data
docker compose --env-file .env.local down --volumes  # deletes it all
```

## If something doesn't match

- **`up --wait` fails with `container campus-seekr-notifier-1 has no healthcheck configured`:** older Docker Compose
  versions refuse `--wait` for the workers, whose health check is turned off. Start the stack in two steps instead:
  `docker compose --env-file .env.local up -d --build --wait gateway app`, then
  `docker compose --env-file .env.local up -d --build`.
- **curl returns `{"error":{"code":"SERVICE_UNAVAILABLE",...}}`:** the gateway couldn't reach the API. Run
  `docker compose --env-file .env.local ps`. If `app` is `healthy`, recreate the gateway:
  `docker compose --env-file .env.local up -d --force-recreate gateway`.
- **`login` prints `null`:** wrong name or password. The demo users get the `DEMO_USER_PASSWORD` that was set when
  the database was created. If it was empty then, there are no demo users; start again from step 1.
- **The item list is empty, or the ids are different:** the database wasn't new. Go back to step 1, including
  `--volumes`, with `DEMO_USER_PASSWORD` set.
- **Suggestions never show up:** `docker compose --env-file .env.local ps matching_worker` should show it running.
  Terminal 3 shows any error.
- **Terminal 2 stays empty, or the logger exited with `Cannot write /app/logs/events.jsonl`:** the event log volume
  is from an older image. Step 1's `down --volumes` recreates it.
