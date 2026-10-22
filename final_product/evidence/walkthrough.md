# Recorded walkthrough

Recording: TODO(team): the Chipcast/Panopto link

Recorded TODO(team): date, and who narrates. Length TODO(team) (5-10 minutes), against the deployed system at
`http://18.222.255.231:8000`, commit `f5cea42`.

## Index

TODO(team): replace each time with the real one once the recording is done. The order is a suggestion, and every
row is something the recording has to cover.

| Time | What is on screen |
|---|---|
| 0:00 | What Campus Seekr does: lost and found posts, photos, suggested matches |
| TODO | The architecture: the four services and where each runs (`ARCHITECTURE.md` diagram) |
| TODO | Logging in on screen as a normal user, then `GET /users` refused with 403. Logging in as the admin, and the same call returning 200 |
| TODO | Posting a lost item, then the matching worker's suggestions (`GET /items/{id}/potential-matches`) |
| TODO | The request that crosses all four services: an upload link, the PUT straight to R2, `/complete` (202), the photo becoming `ready`, and the counter going up on `/metrics/` |
| TODO | The pipeline: the green CI run for `f5cea42`, and `adapter_deploy` printing the URL on its last line |
| TODO | The Grafana dashboard with traffic from this run and the time range visible |
| TODO | Two or three design decisions we would defend (`ARCHITECTURE.md`, "Design decisions") |
| TODO | What we would do differently (`EVALUATION.md` (f)) |

## Before recording

- Log in on screen; never paste a token. Don't open `.env.local`, `adapters/aws.env` or a terminal history that
  shows them. Type the Grafana password; don't show it.
- Generate traffic first, so the Grafana panels aren't flat.
- Record before the teardown: the walkthrough has to show the deployed system.
