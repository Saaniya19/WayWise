# WayWise API Contract (Template)

> **Status:** Proposed structure only. Sample fields are not finalized.

## Conventions to decide

- Coordinate format: [latitude/longitude object]
- Distances: [meters]
- Durations: [seconds or minutes, choose one]
- Timestamps and timezones: [ISO 8601 with timezone offset]
- Optional or unknown values: [nullable fields vs absent fields]
- Errors: [status codes and machine-readable error format]

## GET /health

Purpose: Confirm that the FastAPI app is running.

Example successful response (already implemented during scaffolding):

```json
{"status": "ok"}
```

## POST /plan (not yet implemented)

Purpose: Accept a planning request and return one or more multimodal journeys.

### Request schema

[Define PlanningRequest, origin, destination, departure time, constraints, required and optional properties.]

### Response schema

[Define PlanningResponse, journeys, segment mode, endpoints, times, distance, geometry, source and errors.]

### Illustrative JSON example (NOT FINAL)

```json
{
  "origin": {"latitude": 43.4643, "longitude": -80.5204},
  "destination": {"latitude": 43.6452, "longitude": -79.3806},
  "departure_time": "2026-10-20T08:00:00-04:00",
  "constraints": {"max_walking_minutes": 15}
}
```

### Error handling

| Scenario | HTTP status | Response shape |
|---|---|---|
| Invalid input | [e.g. 422] | [TBD] |
| No feasible journey | [TBD] | [TBD] |
| External provider failure | [TBD] | [TBD] |

## Integration checklist

- [ ] Backend and frontend agree on field names and types.
- [ ] Candidate/routing services agree on internal interfaces.
- [ ] Units and timezone representations are consistent.
- [ ] Error and empty-result formats are specified.
- [ ] Sample request and response validated end-to-end.

## Change history

| Date | Change | Approved by |
|---|---|---|
| [Date] | Initial template | [Team] |
