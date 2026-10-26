# Security, privacy and AI governance

## Data sensitivity

Candidate identity, registration, examination responses, incident reports and disciplinary decisions are highly sensitive education records. Do not use real data until the data controller and legal counsel approve the purpose, lawful basis, notices, permitted users, retention schedule, data residency and sharing arrangements under Rwanda's applicable data-protection and education rules.

## Current controls

- Argon2-based password hashing.
- Database-backed failed-login throttling: keyed email/IP pseudonyms, at most 8 failures per email or 30 per client IP in a 15-minute window; raw email and IP are not stored in the attempt table.
- The staff-record creator cannot approve that same staff member's eligibility.
- Invigilator assignments start as pending; a different authorized official must approve or reject them, and the API rechecks eligibility and centre conflict before approval.
- JWT access tokens expire after a configurable short duration (default 15 minutes).
- Explicit role checks on protected APIs.
- Basic validation of identifiers, field sizes and answer-response values.
- Unique constraints for email, examination code, per-exam candidate registration, per-exam candidate submission and staff assignment.
- Eligibility defaults to false; staff assignment requires reviewed eligibility.
- Different case opener and decision-maker; different original decision-maker and appeal resolver.
- Ordered paper-batch state transitions, SHA-256-linked custody events and a sequential application audit hash chain.
- The web console keeps its access token in JavaScript memory, not local/session storage.

## Critical controls still required before live use

1. **Identity and access:** government IdP federation, MFA, token revocation/refresh rotation, account lockout and distributed rate limiting; formal user provisioning/deprovisioning; scoped roles by centre, examination, case and region; privileged access management.
2. **Transport and keys:** HTTPS/TLS everywhere, managed secret storage, key rotation, encryption for databases/backups/answer scripts/evidence and a key custody/rotation procedure.
3. **Audit:** store independently administered immutable checkpoints, verify event payloads as well as links, alert on breaks, and prevent ordinary application roles from deleting records.
4. **Application security:** CSRF/Origin policy where cookie auth is used, restrictive CSP/security headers, dependency monitoring, malware scanning of uploaded evidence, safe exports, request size limits, API rate limits and abuse monitoring.
5. **Operational separation:** separate environments, no real data in test/CI, segregated database and audit administrators, dual control for critical changes, backups and restore drills.
6. **Privacy:** purpose limitation, data minimization, retention/deletion schedules, access/export logs, candidate/guardian notices and procedures for data-subject requests.
7. **Government integration:** approved source contracts, mTLS/service credentials where required, signed or authenticated imports, schema validation, reconciliation and incident handling.
8. **Independent assurance:** penetration testing, threat modelling, formal privacy impact assessment, model evaluation and signed operational acceptance.

## AI use policy

An anomaly score is not proof. Candidate results, eligibility, sanctions or room-wide decisions must never be changed solely by a model. An authorized reviewer must inspect source scripts and context, record reasons, consider alternative explanations, and allow the affected candidate to respond and appeal. The model must be evaluated for false positives by subject, level, language, response type, school/centre context and other legally appropriate fairness dimensions. Publish aggregate validation performance and provide model/version traceability.

Do not use generalized facial-recognition surveillance, emotion inference, personal-message scanning or private-device tracking as default controls. Prefer auditable examination-process records that are directly relevant to integrity.

## Threats and mitigations

| Threat | Required control |
|---|---|
| Insider alters a staff roster | Versioned changes, dual approval, original value preservation, independent source reconciliation |
| Unauthorized staff assigned | Eligibility defaults false, authoritative eligibility check and assignment guard |
| Paper batch is diverted | Seal identifier, tracked handovers, sequence validation, discrepancy workflow and independent inspection |
| Credentials are stolen | MFA, rate limits, revocation, access review and alerts (remaining work) |
| Audit/database history is rewritten | External immutable checkpoint and independent verification (remaining work) |
| Similar answers lead to an innocent accusation | Explainable evidence, human review, corroboration, recorded reasoning and appeal |
| Bulk export leaks candidate data | Least privilege, restricted exports, redaction, access logs and retention controls |
| Device is offline at a centre | Signed local event journal and reconciled sync protocol (remaining work) |

## Incident response

Preserve source evidence and access logs, suspend compromised credentials, isolate affected workloads, capture database and audit checkpoints, notify the designated security/privacy leads under the approved response procedure, document all actions and do not silently edit original examination records.
