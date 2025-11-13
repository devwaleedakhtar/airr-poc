# Repository Guidelines

> **POC Status**: Testing not required at this stage.

---

## Core Principles

- **SOLID**: Strict Single Responsibility Principle
- **KISS & DRY**: Keep it simple, don't repeat yourself
- **Modularity**: Code must be modular, reusable, concise
- **No Over-Engineering**: Understand context before implementing
- **Consistency**: New code must match existing patterns
- **Research First**: Look up latest docs before installing packages or adding functionality

---

## Project Structure

### Frontend (`frontend/`)

**Stack**: Next.js 16, TypeScript, Tailwind 4, ShadCN UI, App Router

```
frontend/
├── app/                    # Pages (server components, minimal)
├── components/
│   ├── ui/                # ShadCN components
│   ├── <route>/           # Route-specific (dashboard/, profile/)
│   │   ├── types.ts       # Route-specific types
│   │   ├── index.tsx      # Route-specific main component
│   │   ├── utils.ts       # Route-specific utilities
│   │   └── constants.ts   # Route-specific constants
│   └── shared/            # Shared components
├── hooks/                 # Custom React hooks
├── lib/                   # Core utilities
├── types/                 # Global types
├── utils/                 # Global utilities
├── constants/             # Global constants
└── public/                # Static assets
```

**Rules**:

- Components: < 200 LOC, kebab-case files (`user-profile.tsx`)
- Pages: Server components in `app/`, minimal logic, fetch & pass to children
- Locality: Route-specific types/utils/constants stay in route folder
- Hooks: Extract complex state logic, side effects, derived calculations
- ShadCN: Use for all UI primitives (headings, paragraphs, images, etc.)
- index.tsx: Each route-specific folder will have a main component called index.tsx, the page.tsx will import this.
- Suspense/Boundary/Transitions: Use ErrorBoundary for graceful handling of error, and Suspense and useTransition for handling async data if required.

### Backend (`backend/`)

**Stack**: FastAPI, SQLAlchemy, Python 3.11+, Pydantic

```
backend/
├── app/
│   ├── main.py           # FastAPI entry
│   ├── routes/           # API routers (one per domain)
│   ├── schemas/          # Pydantic models
│   ├── crud/             # Database operations
│   ├── models/           # SQLAlchemy models
│   ├── core/             # Config, security, dependencies
│   └── services/         # Business logic
├── alembic/              # Migrations
├── requirements.txt
└── .env.local           # DO NOT COMMIT
```

**Rules**:

- Mirror frontend structure (one router per domain)
- Thin endpoints: validate → call service → return
- Dependency injection for DB session, auth, config
- Always return Pydantic models, never raw dicts
- Business logic in `services/`, not routes

---

## Coding Standards

### TypeScript

- No `any`, no `@ts-ignore`
- Prefer `satisfies` over casting
- Keep types close to usage (route-specific → `components/<route>/types.ts`)
- Components: PascalCase, Files: kebab-case
- 2-space indent

### Python

- Functions/vars: snake_case, Classes: PascalCase
- Always use type hints
- 4-space indent

---

## Pre-Commit Checklist

- [ ] Duplicates existing util/type/hook?
- [ ] Can split into smaller components/functions?
- [ ] Props drilled > 2 levels? (Lift state or use context)
- [ ] Constant used only here? (Keep local)
- [ ] Followed SRP principle?
- [ ] No `any` or `@ts-ignore`?
- [ ] Looked up latest docs for new packages/functionality?

---

## Security

- Store secrets in `.env.local` (NEVER commit)
- Next.js: Only expose client vars with `NEXT_PUBLIC_` prefix
- Never hardcode credentials
- Validate and sanitize all inputs

---

## Quick Reference

**File Placement**:

- Global types/utils/constants → `types/`, `utils/`, `constants/`
- Route-specific → `components/<route>/types.ts`, `utils.ts`, `constants.ts`
- Shared components → `components/shared/`

**When Unsure**:

- Where to place? → Check structure above
- Split component? → If in doubt, split it
- Research first → Always check latest docs before adding packages
