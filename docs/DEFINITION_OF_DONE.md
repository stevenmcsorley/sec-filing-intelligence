# Definition of Done Checklist

- [ ] Trello card moved to **In Review** only after lint, type-check, and tests pass locally.
- [ ] CI pipeline (lint + test jobs) green on GitHub.
- [ ] Branch rebased on latest `main`; no merge commits.
- [ ] Acceptance criteria from the card description satisfied and referenced in PR description.
- [ ] Trello card ID present in branch name, commit messages, and PR title.
- [ ] Documentation updated as needed (README, runbooks, API docs).
- [ ] No secrets or mock data committed; real integration points documented with environment configuration guidance.
- [ ] For backend changes: OPA policies touched? ensure unit tests updated (`opa test`) and audit logging validated.
- [ ] For frontend changes: accessibility checklist reviewed, storybook stories added/updated, fixtures sourced from real sanitized data.
- [ ] Post-merge action recorded in Trello Build Log (see `docs/TRELLO_SYNC.md`).
