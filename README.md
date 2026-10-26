# Rwanda Examination Integrity Platform

A secure, auditable platform for examination operations, candidate and staff verification, examination-paper chain of custody, answer-pattern review, case management, and appeals.

## Status

This repository is being initialized as an engineering foundation. It is not yet an official NESA or Government of Rwanda deployment and contains no government candidate data or credentials. All anomaly findings are investigative leads, never automated findings of guilt.

## Product principles

- Secure by default; least-privilege access and attributable actions.
- Offline-tolerant examination-centre workflows.
- Traceable chain of custody for examination materials.
- Explainable similarity signals with human review and appeal.
- Data minimization, privacy-by-design, and no continuous student surveillance.
- Reproducible builds, migrations, automated tests, and operational documentation.

## Planned components

- `apps/api`: FastAPI service for identity, examination operations, audit, integrity analysis and case workflows.
- `apps/web`: web operations console for authorized officials.
- `packages/integrity`: explainable answer-pattern similarity analysis.
- `infra`: PostgreSQL, app containers, health checks and environment examples.
- `.github/workflows`: continuous integration and security checks.

See the project documentation as components are added. Do not use this initial repository with real personal data before a formal security, privacy, legal and operational readiness review.