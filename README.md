# nullbot
matrix chat bot

## Running

1. Export environment variables `MATRIX_HOMESERVER`, `MATRIX_USERNAME`, `MATRIX_PASSWORD`
2. Export environment variables for the psql connection: https://www.postgresql.org/docs/10/libpq-envars.html
3. *Twitch plugin only:* set environment variables `TWITCH_CLIENT_ID` and `STREAM_ROOM_ID`.
3. `poetry run nullbot`
