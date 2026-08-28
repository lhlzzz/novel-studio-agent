# Postiz Distribution Infrastructure

Postiz is operated as an external distribution service. Keep its PostgreSQL,
Redis, and Temporal data separate from the Meiti PostgreSQL database.

Set `POSTIZ_API_URL` and `POSTIZ_API_KEY` in the operator environment. Meiti
does not copy Postiz source or business data into this repository.

The official stack exposes Postiz at `http://127.0.0.1:4007` and uses its own
Postiz PostgreSQL, Redis, and Temporal services. The local `.env` is ignored by
Git and must contain a strong `JWT_SECRET`.
