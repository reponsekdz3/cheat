# Architecture and workflows

## System boundary

The initial system is a modular application, not microservices.

- **Web console:** Next.js/React/TypeScript UI for signed-in officials. The console calls the API directly and keeps access tokens in memory only.
- **API:** FastAPI with explicit role dependencies, Pydantic request validation and SQLAlchemy async persistence.
- **Relational store:** PostgreSQL stores users, examination sessions, candidate references, staff records, custody events, structured answer responses, findings, cases, appeals and audit events.
- **Migration system:** Alembic applies the baseline schema before the API serves traffic.
- **Analysis module:** deterministic and versioned response normalization, exact-match agreement and cohort-frequency weighting.
- **Operational deployment:** Docker Compose is a local single-host configuration; it is not a high-availability or government production deployment.

## Domain objects

- Examination: one session/subject/level/date record.
- Candidate: registration number and examination-specific centre/room/seat assignment.
- Staff member: official staff reference, employing school and reviewed eligibility.
- Staff assignment: one staff/examination assignment with destination centre and room.
- Paper batch: a counted batch with a tamper-evident seal ID and a finite state machine.
- Custody event: actor, location, event type, prior hash and event hash.
- Answer submission: one response map for a registered candidate/examination.
- Integrity finding: candidate pair, score, model version, comparison evidence and review status.
- Case and appeal: separate investigation, decision and appeal record.
- Audit event/head: serialized event recording and sequential linkage.

## Paper custody lifecycle

`PREPARED → SEALED → DISPATCHED → RECEIVED → OPENED → RETURNED → RECONCILED`

Transitions out of sequence are rejected by the API. Event hashes link each event to its predecessor; verification follows predecessor hashes rather than relying on timestamp order, recomputes each event payload hash, and checks the stored batch head. Hashes only provide stronger assurance when checkpoints are held independently; a database administrator who can rewrite both history and head can otherwise rewrite the chain. A production deployment must anchor periodic audit hashes in independently controlled immutable storage and schedule custody-event verification. Audit entries migrated from the older hash format are marked legacy and are only link-checked.

## Answer-pattern analysis

The current `answer-pattern-v1.0.0` engine normalizes whitespace and case, compares questions answered by both candidates, measures exact agreement, and weights a match based on how often that same answer occurs for the same question in the submitted cohort. It records matched question identifiers, numbers of comparable/matching answers, score components and limitations.

It does not infer intent; it does not use facial cues; and it does not compare candidates against an answer key or model the educational difficulty of each question. Incomplete cohorts and short-answer questions can distort the score. Thresholds are configurable and must be calibrated using authorized historical cases and independent examiners before use in real decisions. A finding is never an outcome, sanction or result cancellation.

## Case workflow invariants

- A case can only target a candidate present in its source finding.
- The investigator who opened a case cannot decide it.
- A written evidence summary is mandatory for a decision.
- Appeals are accepted only after a decision.
- The original case decision-maker cannot resolve the appeal.
- Each transition adds an audit event.

## Integration architecture for the government

The authoritative source of candidate registration and school staff data must remain the government's approved systems. Build explicit adapters for the actual government interfaces once endpoint contracts, service identities, data agreements and test credentials are approved. Each adapter should validate schema/version, reconcile record counts, quarantine conflicts, preserve source identifiers and emit an audit event. Never scrape, synthesize or silently overwrite official records.

Potential integration boundaries include NESA/SDMS registration, official staff/school data, government SSO/MFA, authorized evidence storage, approved SMS/email notifications, and official reporting/export. None of those government services is connected in this repository today.
