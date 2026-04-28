# Code Explainability

Living document. Updated after each batch is approved. One entry per file: what it does, external services called, what calls it.

## Modules

| Module | File | Contents |
|--------|------|----------|
| [Infrastructure](infrastructure.md) | infrastructure.md | Migrations, .env, Dockerfiles, Railway configs, nginx |
| [Backend — Setup](backend-setup.md) | backend-setup.md | Python version, deps, config.py, main.py |
| [Backend — Schemas](backend-schemas.md) | backend-schemas.md | All Pydantic schema files |
| [Backend — Database](backend-db.md) | backend-db.md | Supabase client helpers, SQLite FTS index |
| [Backend — Pipeline](backend-pipeline.md) | backend-pipeline.md | VIN decoder + all search pipeline modules |
| [Backend — API](backend-api.md) | backend-api.md | All FastAPI route handlers |
| [Backend — Agents](backend-agents.md) | backend-agents.md | All LLM agent modules |
| [Backend — Workers](backend-workers.md) | backend-workers.md | Background async job processor |
| [Backend — Ingestion](backend-ingestion.md) | backend-ingestion.md | Full data ingestion pipeline |
| [Frontend — Setup](frontend-setup.md) | frontend-setup.md | npm, TypeScript, Vite, Tailwind, PostCSS config |
| [Frontend — Types & API](frontend-types-api.md) | frontend-types-api.md | TypeScript types + all API client modules |
| [Frontend — Pages](frontend-pages.md) | frontend-pages.md | React page components |
| [Frontend — Components](frontend-components.md) | frontend-components.md | React UI components + design system |
