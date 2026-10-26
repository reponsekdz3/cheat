# Operations runbook

## Local start

1. Copy `.env.example` to `.env` and generate unique secret/password values.
2. Set the database URL to the same username/password/database as the PostgreSQL service.
3. Set a bootstrap administrator email and password of at least 16 characters before first startup.
4. Run `docker compose up --build -d`.
5. Verify `docker compose ps`, `http://localhost:8000/health/ready`, `http://localhost:8000/docs` and the web console on port 3000.
6. After the first administrator is created, remove bootstrap secrets from the runtime configuration and restart. Do not keep bootstrap credentials in a production secret store longer than needed.

## Migrations

The container applies Alembic migrations before starting the API. For a production rollout, use a separate migration identity and deployment job, capture a verified backup first, test forward and backward compatibility in staging, and do not use application credentials for schema administration. The baseline migration reflects the SQLAlchemy models at initial commit; future schema evolution must be delivered as reviewed, explicit migrations.

## Backups and restore

- Use encrypted, access-controlled database backups with retention and restore objectives approved by the data owner.
- Back up the evidence/object store separately and reconcile object metadata against database references.
- Keep encryption keys separate from backups.
- Run scheduled restore drills into isolated environments; verify row counts, audit linkage and selected custody chains before reopening service.
- Never restore an unverified backup directly into a live examination system.

## Authentication attempt retention

The login throttling table stores only keyed pseudonyms for the normalized email and client IP, plus success state and timestamp. Apply a reviewed retention policy and periodically delete expired attempt rows after the required audit/incident window; do not retain raw IP addresses or passwords for throttling. Behind a reverse proxy, configure only trusted proxy addresses so client IP throttling cannot be spoofed or collapsed onto the proxy address.

## Secret rotation

Rotate database credentials and JWT signing secrets using an approved change window. JWT secret rotation invalidates existing access tokens. A production implementation should support key identifiers and overlapping verification keys to avoid uncontrolled outage. Do not commit secret values to GitHub issues, code, test fixtures or build logs.

## Examination-day response

1. Record incident time, examination/centre/room, reporting person and immediate safety concerns.
2. Preserve package seals, original scripts, staff assignments, attendance and relevant custody records.
3. Restrict case evidence to designated investigators; never publicly label candidates as cheaters from a dashboard alert.
4. Record the evidence collection and every handover.
5. Have a reviewer independent of the investigator assess the case under applicable rules.
6. Notify candidates/guardians and support appeals according to official policy.
7. Publish only authorized aggregate outcomes.

## Monitoring

Alert on failed logins, repeated authorization failures, migration errors, database saturation, missing audit head, invalid custody transitions, unusual data exports, broken hash chains, high rates of analyst findings and prolonged open cases. The initial repository includes health endpoints and an audit status endpoint; centralized alerting and security telemetry require deployment configuration.
