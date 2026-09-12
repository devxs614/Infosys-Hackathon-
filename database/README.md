# Optional telemetry database

The backend stores telemetry in memory by default. To use Tiger Data or another PostgreSQL/TimescaleDB instance, create a database, apply `schema.sql`, and set `TIGER_DB_URL` in the backend `.env`.

No database credential belongs in this repository. A failed database connection is logged once and the simulation remains operational with the in-memory fallback.

