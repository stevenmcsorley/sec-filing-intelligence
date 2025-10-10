# Trello ↔ GitHub Sync Guide

The engineering workflow uses Trello as the source of truth for planning. Keep status synchronized with GitHub to maintain auditability.

## Card Lifecycle

1. **Pick Up:** Move the card from **Ready** to **In Progress**. Create a branch named `<TRELLO-ID>/<slug>`.
2. **Worklog:** Post intermediate updates as comments on the Trello card (e.g., links to draft PRs, demo videos, screenshots).
3. **Review:** When opening a PR, include the Trello card URL in the description and mark the card as **In Review**.
4. **Merge:** After the PR merges, move the card to **Done** and append a summary to the Build Log checklist on the card.
5. **Retrospective:** Capture follow-up tasks as new Trello cards or issues; avoid leaving TODOs in code without tracking work.

## Pull Request Template Usage

- Fill out the checklist items.
- Link to acceptance criteria from the Trello description.
- Note any additional qa steps or data migrations.

## Build Log Template

Add a comment to the Trello card after merge:

```
Build Log — YYYY-MM-DD
- PR: https://github.com/stevenmcsorley/sec-filing-intelligence/pull/NN
- Deployer: @username
- Tests: CI ✅ / Manual ✅ (notes)
- Follow-ups: TRELLO-00X
```

## Automation Roadmap

- Explore GitHub Actions to push status updates back to Trello via the REST API using the card ID embedded in branch/PR names.
- Consider adding a `docs/build-log.md` changelog that references Trello IDs once automation is in place.
