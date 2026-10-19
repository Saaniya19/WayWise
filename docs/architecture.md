# WayWise Architecture (Template)

> **Status:** Draft template. The implementation is not complete; replace placeholders with decisions the team has reviewed.

## 1. Project objective

[One-paragraph description of WayWise and the MVP journey-planning goal.]

## 2. System context

- **iOS app:** [User-facing responsibilities; map and journey presentation.]
- **FastAPI backend:** [Request handling and journey planning orchestration.]
- **External services:** [Google Routes API and any other selected providers.]
- **Transfer catalogue:** [Where candidates are stored, how verified and updated.]

## 3. Component diagram

[Insert diagram of iOS -> FastAPI -> catalogue and external routing services.]

## 4. Planning flow

1. [User submits origin, destination and constraints.]
2. [Backend selects candidate transfer locations.]
3. [Backend retrieves driving/walking/transit route data.]
4. [Backend checks timing and constraints; composes a journey.]
5. [Backend returns structured JSON; app displays results.]

## 5. Important design decisions

| Decision | Choice | Rationale | Owner / date |
|---|---|---|---|
| Language and framework | [Python / FastAPI] | [Why] | [Name / date] |
| Transit route provider | [To validate] | [Coverage, timing, cost] | [Name / date] |
| Candidate catalogue | [Initial approach] | [Tradeoffs] | [Name / date] |

## 6. Open questions and risks

- [Google transit coverage and timing details for the chosen GO corridor]
- [Candidate catalogue verification / refresh strategy]
- [API cost, quotas and permitted data storage]
- [Handling uncertain parking availability and connection buffers]

## 7. Related documents

- `docs/api-contract.md`
- `docs/development.md`
- [Relevant Jira tickets and UML/data model links]
