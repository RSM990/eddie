# eddie Documentation

Navigation for eddie's docs. Mirrors the structure used across the other projects (TheWAC, Tortuga) so eddie can be grown the same way.

## Quick start (new Claude Code session)

```
Read CLAUDE.md, then docs/planning/CURRENT_SPRINT.md, then docs/current/CURRENT_STATUS.md.
For DB work, read docs/technical/V2_SCHEMA_CONTRACT.md.
```

## Tree

```
CLAUDE.md                              ← agent onboarding + hard rules
docs/
  DOC_NAVIGATION.md                    ← this file
  RUNBOOK.md                           ← setup + exact run commands + troubleshooting
  MAINTENANCE.md                       ← how/when docs get updated
  foundation/VISION.md                 ← what eddie is and why
  decisions/DECISIONS.md               ← architecture decision records
  technical/ARCHITECTURE.md            ← ETL stage design, boundaries
  technical/TECH_STACK.md              ← libraries + why
  technical/V2_SCHEMA_CONTRACT.md      ← shared tables eddie writes (build-critical)
  planning/ROADMAP.md                  ← phases of ingestion work
  planning/CURRENT_SPRINT.md           ← active sprint (execution doc)
  current/CURRENT_STATUS.md            ← where things stand
  testing/TESTING.md                   ← test strategy
  archive/                             ← retired docs
```

## Doc roles

- **CLAUDE.md** — read first. Architecture summary + the non-negotiable rules (shared-tables-only, ID strategy, fetch strategy, secrets).
- **VISION** — eddie as a generalized sports-data ETL serving multiple consumers.
- **DECISIONS** — why eddie is structured the way it is; mirrors TheWAC's DEC-012/013 from the consumer side.
- **ARCHITECTURE / TECH_STACK** — how the ETL is built and with what.
- **V2_SCHEMA_CONTRACT** — the authoritative spec for the TheWAC tables eddie writes.
- **ROADMAP / CURRENT_SPRINT / CURRENT_STATUS** — planning + execution + status.
- **TESTING** — pytest against a local v2 DB.

## Status

Populated: CLAUDE.md, VISION, DECISIONS, V2_SCHEMA_CONTRACT, CURRENT_SPRINT, CURRENT_STATUS.
Starter (expand as needed): ARCHITECTURE, TECH_STACK, ROADMAP, TESTING, MAINTENANCE.
