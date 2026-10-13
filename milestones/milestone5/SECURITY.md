## 1. Authentication

Registration saves the user's display name, real name, and bcrypt password hash. We don't store the plain password or return the hash. New accounts get the user role. A duplicate display name returns 409.

Passwords must be 6-72 characters and at most 72 UTF-8 bytes. The schema counts characters and the hashing function checks bytes because some characters take more than one byte. Cutting off a password could make two different passwords match, so we reject it instead.

Login checks the password and returns a JWT lasting 30 minutes. The client sends Authorization: Bearer <token> with protected requests. The server checks the signature, expiration, user ID, and whether the account is still active. After the token expires, the user logs in again.

We use PyJWT with HS256. JWT_SECRET comes from the environment

## 2. Authorization

We have user and admin roles in a many-to-many relationship. Normal users can post items, upload files, and manage their own content. Admins can also manage locations, list users, hard-delete items, and manage other people's items and files.

The owner is set from the signed-in user's ID, not a user_id supplied by the client. The ownership check compares that ID with the owner saved on the item or file. A user doesn't need an admin role to change their own content.

Endpoint access:

- GET /health, gateway GET /healthz: Public
- POST /users, POST /auth/login: Public
- GET /items, /items/{id}, /items/{id}/matches, /matches, /matches/{id}: Public
- GET /locations, /locations/{id}, /locations/{id}/items: Public
- GET /items/{id}/images/{upload_id}: Public
- GET /docs, /openapi.json: Public
- GET /auth/me, POST /items, POST /files, POST /files/batch: Signed-in user
- GET /files: Signed-in user; normal users see their own files, while admins can see all or filter by user
- POST /matches, DELETE /matches/{id}: Signed-in user; ownership restrictions still need to be added
- PATCH /items/{id}, PATCH /items/{id}/status, DELETE /items/{id}: Item owner or admin
- POST /items/{id}/images, POST /items/{id}/images/{upload_id}/complete: Item owner or admin
- GET /files/{id}, GET /files/{id}/content, DELETE /files/{id}: File owner or admin
- POST /locations, PATCH /locations/{id}, DELETE /locations/{id}, POST /locations/{id}/restore, DELETE /locations/{id}/hard: Admin
- GET /users, DELETE /items/{id}/hard: Admin

A missing or invalid token returns 401. A signed-in user without permission gets a 403, such as when editing someone else's item.

## 3. Using the API

```bash
API=http://localhost:8000/api/v1
NAME="seekr-demo-$(date +%s)"
PASSWORD="$(openssl rand -hex 12)"

# Register
curl -sS -X POST "$API/users" \
  -H 'Content-Type: application/json' \
  -d "{\"display_name\":\"$NAME\",\"real_name\":\"Test Student\",\"password\":\"$PASSWORD\"}"

# Log in
LOGIN=$(curl -sS -X POST "$API/auth/login" \
  --data-urlencode "username=$NAME" \
  --data-urlencode "password=$PASSWORD")
jq '.access_token = "[redacted]"' <<< "$LOGIN"
TOKEN=$(jq -er '.access_token' <<< "$LOGIN")

# Make a protected request
curl -sS "$API/auth/me" -H "Authorization: Bearer $TOKEN"
```

```json
{"access_token":"[redacted]","token_type":"bearer","expires_in":1800}
```

Registration and /auth/me return a user like this. The name, ID, timestamp, and role ID will depend on the database:

```json
{
  "display_name": "seekr-demo-1791859000",
  "real_name": "Test Student",
  "id": 1,
  "is_active": true,
  "created_at": "2026-10-13T02:20:27",
  "roles": [{"id": 1, "name": "user"}]
}
```

## 4. Security decisions

We call bcrypt directly. Cost 10 was chosen in 2026 for local testing

Unknown users and wrong passwords get the same 401 message. A dummy bcrypt check for unknown users reduces the timing difference, but doesn't make request times exactly equal.

The server only allows HS256 and requires an expiration and user ID in the token. Roles are checked against the database.

Queries use SQLAlchemy; the health check's fixed SELECT 1 has no user input. Request schemas check things like lengths and positive IDs. Real environment files are gitignored.

## 5. Local shortcuts and remaining gaps

File locations:

- app/password_util.py:7 - bcrypt cost 10 keeps local tests faster. Review the cost on the deployment machine.
- compose.yml:12,50,109,125 - Database and storage credentials are written into Compose. Move them to required environment settings.
- compose.yml:84 - The gateway serves local HTTP. Use HTTPS before exposing login outside the laptop.
- compose.yml:106,128 - Database and storage ports are published on the host. Keep internal services private and limit who can reach them.
- app/api.py:58 - Tables are created automatically, and schema changes currently involve recreating the database. Use migrations and backups before keeping real data.
- app/crud.py:383,392 - Startup can give the configured admin role to an existing account with that name. Use controlled admin setup and avoid accidentally promoting an existing account.
- app/routers/auth.py:19 - Login has no rate limit or account lockout. Add a limit on repeated login attempts before public access.

## 6. Before deployment

- Remove committed credentials and keep real secrets in the environment.
- Check that missing JWT_SECRET still prevents startup.
- Run the security tests on a fresh database, including ownership, expired tokens, rejected algorithms, and long passwords.
- Check how database changes and backups will work.