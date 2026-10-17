# WayWise Development Guide

This guide explains how to work in the WayWise monorepo. Update commands and conventions as the team makes decisions.

## Project layout

- `backend/` - FastAPI application, future routing logic, external API integrations, and catalogue data.
- `ios/WayWiseSwift/` - existing Xcode project and Swift iOS app.
- `docs/` - architecture notes, API contract, and setup instructions.
- `.github/` - GitHub pull request and workflow configuration.

## Prerequisites

- Git and access to the WayWise GitHub repository.
- Python 3.12 and `uv` for the backend.
- Xcode on macOS for building or running the iOS app.
- VS Code is optional for repository-wide editing.

## Start the Python backend

From the repository root:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Check `http://127.0.0.1:8000/health` for `{"status":"ok"}`. Stop the server with Ctrl+C.

Copy `backend/.env.example` to `backend/.env` only when a local configuration value is needed. Never commit real keys, tokens, or `.env` files. The `backend/.env` file is intended for local use only.

## Open the iOS app

Open the existing `.xcodeproj` inside `ios/WayWiseSwift/` in Xcode, select a simulator, then build/run. The current iOS app is a prototype and may evolve as frontend tickets are implemented. Do not create a second Xcode project.

## Branches and pull requests

1. Update local `main`: `git switch main && git pull origin main`.
2. Create a short-lived ticket branch, e.g. `git switch -c feature/SCRUM-60-repo-scaffolding`.
3. Keep changes within that ticket's scope and commit with the Jira ID in the message.
4. Open a pull request targeting `main`, using the template in `.github/pull_request_template.md`.
5. Request at least one teammate review. Address comments before squash-merging.
6. Delete the feature branch after merging; mark the Jira ticket Done only once its acceptance criteria are met and changes are merged.

Avoid direct commits to `main`. When multiple people need the same files, communicate early; agree on shared data models and interfaces before implementing coupled components.

## Code organization

- `backend/app/api/`: HTTP endpoints and request/response handling.
- `backend/app/models/`: shared data structures.
- `backend/app/services/`: WayWise domain logic (for example, selecting transfer candidates or constructing journeys).
- `backend/app/clients/`: integrations with external APIs such as Google Routes.
- `backend/app/core/`: application-wide settings and configuration.
- `backend/data/`: catalogue inputs and other small local data used for prototyping.

The frontend owner can reorganize Swift code into Views, Models, ViewModels and Services as part of their implementation tickets. Avoid creating placeholder feature files solely to fill directories.

## Shared interface decisions

Before connecting components, document agreed request/response field names, units (seconds vs minutes, meters vs kilometers), timezones, errors, and any missing/unknown values in `docs/api-contract.md`.

## Keeping this guide current

Update this file when setup steps, paths, or conventions change. Record major architectural decisions in `docs/architecture.md`.
