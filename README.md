# Rwanda National Examination Integrity Platform

A secure, auditable software platform for examination operations, candidate registration and attendance, examination staff eligibility, paper chain-of-custody, explainable answer-pattern analysis, incident investigation, independent decisions and appeals.

**Project status:** the repository now contains a functioning initial software foundation. It is not an official NESA or Government of Rwanda deployment, is not connected to SDMS or any government identity system, and has not been approved for production use. Do not enter real candidate data until the security, privacy, legal, operational and integration readiness gates in the documentation are completed.

## What is implemented

- FastAPI service with OpenAPI documentation, short-lived signed access tokens, Argon2 password hashing and explicit role checks.
- Examination-session and candidate registration APIs, attendance updates, staff eligibility review and assignment guards.
- Paper-batch state transitions with SHA-256-linked custody events; out-of-order transitions are rejected.
- Cohort answer-pattern similarity analysis with a versioned, explainable model and persisted review leads.
- Case creation, independent case-decision checks, appeal submission and separate appeal-decision checks.
- Application audit events linked by a sequential hash chain.
- Next.js official-operations console that reads and writes real API records, plus database migrations, containerized local stack and CI tests.
- Unit tests for answer normalization, pair detection, blank answers and minimum evidence thresholds.

## Core flow

1. An authorized operations user creates an examination and registers candidates and staff.
2. A staff-eligibility reviewer records an evidence-backed eligibility decision. Assignment is rejected until the staff record is eligible and the destination is not the staff member's employing school.
3. Authorized operations staff register a paper batch, then record each permitted handover transition.
4. Authorized markers ingest answer responses for registered candidates.
5. An investigator runs cohort analysis. Output is an explainable **review lead**, never an automated guilt decision.
6. An investigator opens a case against a specific affected candidate. A different authorized reviewer records a reasoned decision.
7. An appeal can be filed after decision; the original decision-maker cannot resolve that appeal.
8. Authorized auditors check audit-chain linkage.

## Run locally with Docker

Requirements: Docker Desktop / Docker Engine with Compose, a current web browser and a network connection for downloading images and packages.

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` with a long random password. Set `DATABASE_URL` to use the same password and database username. Use URL-safe random characters for the password, or percent-encode reserved URL characters.
3. Set `JWT_SECRET` to a unique random secret of at least 32 bytes. A convenient generation command is `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` for the first startup only. Use a unique password of at least 16 characters. After the first administrator is created, remove those variables from the runtime environment and manage subsequent accounts through authorized administration.
5. Start the system with `docker compose up --build -d`.
6. Open the operations console at `http://localhost:3000`, API docs at `http://localhost:8000/docs`, and readiness status at `http://localhost:8000/health/ready`.

The first boot applies the Alembic schema migration and initializes the audit chain. The web console's API address is baked at build time; set `NEXT_PUBLIC_API_BASE_URL` before building if the browser should call a different address. Local HTTP is for development only. Government deployment requires HTTPS, managed secrets, network separation and the security gates below.

## Roles

`SUPER_ADMIN`, `ADMIN`, `EXAM_OPERATIONS`, `INVESTIGATOR`, `REVIEWER`, `APPEALS_OFFICER`, `CENTRE_SUPERVISOR`, `MARKER`, and `AUDITOR` are explicit application roles. Administrative-role grants are restricted to the super administrator. A role check is not a substitute for centre- and case-level scopes; the first build intentionally denies some supervisor actions until their verified scope registry is implemented.

## Key API routes

| Domain | Routes |
|---|---|
| Identity | `POST /auth/token`, `GET /auth/me`, `POST /admin/users` |
| Examination and candidates | `POST/GET /examinations`, `POST/GET /candidates`, `PATCH /candidates/{id}/attendance` |
| Staff | `POST/GET /staff`, `PATCH /staff/{id}/eligibility`, `POST /staff-assignments` |
| Paper custody | `POST /paper-batches`, `POST /paper-batches/{id}/events`, `GET /paper-batches/{id}/events`, `GET /paper-batches/{id}/verify` |
| Answer analysis | `POST /answer-submissions`, `POST /integrity/analyze/{examination_id}`, `GET /integrity/findings` |
| Casework | `POST /cases/from-finding/{finding_id}`, `GET /cases`, `POST /cases/{id}/decision`, `POST /cases/{id}/appeals`, `POST /appeals/{id}/resolution` |
| Audit | `GET /audit/status` |

OAuth2 password flow is used for this initial API. Tokens expire quickly and are held in browser memory by the console; refresh tokens, MFA and government identity-provider federation are not yet implemented. See the security and readiness docs before internet exposure.

## Development and tests

API unit tests:

```bash
python -m pip install -r apps/api/requirements.txt
PYTHONPATH=apps/api pytest
python -m compileall -q apps/api/app
ruff check --select F apps/api/app apps/api/tests
```

Web app:

```bash
cd apps/web
npm install
npm run lint
npm run build
```

Continuous integration executes the Python tests and TypeScript/Next.js checks for pushes and pull requests.

## Production-readiness gates

The code is an engineering foundation, not a claim that every national integration has been completed. Before any live examination:
- Complete an independent security review and a privacy impact assessment under Rwanda's applicable data-protection law.
- Integrate authoritative NESA/SDMS candidate records, approved staff and school registers, verified centre assignments and the government's approved identity provider. No connector or government credentials are included in this repository.
- Add MFA, refresh-token rotation/revocation, account lockout/rate limiting, centre/case-scoped object-level access control and formal privileged-access review.
- Move answer-script storage to encrypted object storage or application-level encryption backed by managed keys; enable TLS and encrypted managed PostgreSQL storage, encrypted backups and tested restore procedures.
- Anchor audit-chain checkpoints in a separately administered immutable/WORM store and run independent integrity verification.
- Add signed offline event synchronization, conflict resolution, bulk-import reconciliation, malware scanning and evidence retention/deletion rules.
- Calibrate and independently validate answer-pattern detection against representative, authorized, reviewed data. Publish false-positive and subgroup performance metrics. Maintain independent human review and appeals.
- Complete load, outage, failover, penetration, accessibility and disaster-recovery tests; obtain formal government and legal approval.

See [Architecture](docs/architecture.md), [Security and privacy](docs/security-and-privacy.md), and [Operations runbook](docs/runbook.md).
