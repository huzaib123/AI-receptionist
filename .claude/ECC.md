# Everything Claude Code (ECC) — vendored subset

Source: https://github.com/affaan-m/everything-claude-code @ 25278e7 (MIT, see `ECC-LICENSE`).

Only the parts that fit this stack (FastAPI / Python, React / Vite, Postgres, LLM agent,
WhatsApp + billing + lead-gen) are vendored, so every session doesn't load 300+ skill descriptions.

| Folder | Contents |
|---|---|
| `skills/` | 37 ECC skills (python, fastapi, react, vite, postgres, migrations, docker, deployment, api-design, tdd, e2e, security, LLM cost / prompt caching, billing, lead-intelligence, market-research, scraping, seo, i18n, dashboards). `frontend-design` is the repo's own. |
| `agents/` | 17 subagents: architect, planner, code / security / python / fastapi / react / database reviewers, tdd-guide, build resolvers, e2e-runner, performance, silent-failure-hunter, refactor-cleaner, doc-updater, seo-specialist |
| `commands/` | `/plan`, `/feature-dev`, `/build-fix`, `/python-review`, `/fastapi-review`, `/react-review`, `/react-test`, `/react-build`, `/test-coverage`, `/refactor-clean` |
| `rules/` | common + path-scoped python / react / web rules |

Local changes from upstream:
- `security-review` skill renamed `secure-coding` (clashes with the built-in `/security-review`).
- Left out: ECC hooks and hook rules, `delivery-gate`, `security-scan` (runs a third-party npm package),
  the `code-review` command (built-in `/code-review` covers it), `rules/common/agents.md`,
  and the commit-attribution note in `rules/common/git-workflow.md`.

To add more: copy `skills/<name>` / `agents/<name>.md` from upstream into the matching folder here.
