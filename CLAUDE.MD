# CLAUDE.MD - AI Agent Context for Exegesis AI

## Project Overview

**Exegesis AI** is a theological research platform that unifies research libraries into a verse-aware knowledge graph. The system combines semantic search, deterministic retrieval, and AI-powered summarization while maintaining strict citation traceability to canonical biblical texts.

**Tech Stack:**
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, pgvector
- **Frontend:** Next.js 20+, React, Radix UI
- **Database:** PostgreSQL 16 with pgvector extension
- **ML/AI:** Transformers, sentence embeddings, RAG (Retrieval-Augmented Generation)
- **Background Processing:** Celery, APScheduler
- **Testing:** pytest, Playwright, Vitest

## Architecture

### Domain-Driven Design Structure

```
exegesis/
├── domain/          # Core business logic and entities
│   ├── discoveries/ # Document and evidence models
│   ├── mappers/     # Domain object transformations
│   ├── repositories/# Repository interfaces
│   ├── research/    # Research collection models
│   └── services/    # Domain services
├── application/     # Application layer (use cases, facades)
│   ├── core/        # Core application logic
│   ├── dtos/        # Data transfer objects
│   ├── facades/     # Simplified interfaces to complex subsystems
│   ├── ports/       # Port interfaces
│   ├── repositories/# Repository implementations
│   ├── research/    # Research-specific application logic
│   ├── retrieval/   # Retrieval and search logic
│   ├── services/    # Application services
│   └── use_cases/   # Business use cases
├── adapters/        # External interfaces and persistence
│   ├── events/      # Event handling
│   ├── graph/       # Graph database adapters
│   ├── persistence/ # Database persistence
│   ├── research/    # Research data adapters
│   └── secrets/     # Secret management
├── infrastructure/  # Framework-specific implementations
│   ├── api/         # FastAPI application
│   └── ...
└── services/        # Service layer
    ├── api/         # API services
    └── ...
```

### Key Architectural Patterns

1. **Verse-Aware Retrieval**: All search results are anchored to normalized OSIS (Open Scripture Information Standard) references
2. **Hybrid Search**: Combines semantic (vector) and lexical (keyword) search for optimal retrieval
3. **Citation Preservation**: Every AI-generated insight traces back to source documents and verses
4. **Repository Pattern**: Clean separation between domain logic and data persistence
5. **Facade Pattern**: Simplified interfaces for complex subsystems (see `application/facades/`)

## Development Workflow

### Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install ".[api]" -c constraints/prod.txt
pip install ".[ml]" -c constraints/prod.txt
pip install ".[dev]" -c constraints/dev.txt

# Frontend setup
cd exegesis/services/web
npm install
```

### Running the Application

**Option 1: Development Scripts**
- PowerShell: `./scripts/dev.ps1`
- Bash: `./scripts/run.sh`

**Option 2: Manual Launch**
```bash
# 1. Start PostgreSQL
docker run --rm --name exegesis-db \
  -e POSTGRES_PASSWORD=exegesis \
  -e POSTGRES_USER=exegesis \
  -e POSTGRES_DB=exegesis \
  -p 5432:5432 postgres:16

# 2. Start API
export DATABASE_URL="postgresql://exegesis:exegesis@127.0.0.1:5432/exegesis"
uvicorn exegesis.infrastructure.api.app.main:app --reload --host 127.0.0.1 --port 8000

# 3. Start Web UI
cd exegesis/services/web
export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

**Option 3: Docker Compose**
```bash
cd infra
docker compose up --build -d
```

### Testing

```bash
# Fast tests (no slow, gpu, or contract tests)
pytest -m "not (slow or gpu or contract)"

# Full test suite with database
pytest --schema --pgvector --contract

# Web tests
cd exegesis/services/web
npm test
npm run test:e2e:smoke
```

## Code Modification Guidelines

### When Adding Features

1. **Start with the Domain Layer**: Define entities and business logic in `exegesis/domain/`
2. **Create Repository Interfaces**: Define contracts in `exegesis/domain/repositories/`
3. **Implement Adapters**: Add persistence in `exegesis/adapters/persistence/`
4. **Build Use Cases**: Create application logic in `exegesis/application/use_cases/`
5. **Expose via API**: Add endpoints in `exegesis/infrastructure/api/`
6. **Update UI**: Modify Next.js components in `exegesis/services/web/`

### File Naming Conventions

- **Python modules**: `snake_case.py`
- **Test files**: `test_*.py` or `*_test.py`
- **TypeScript/React**: `PascalCase.tsx` for components, `camelCase.ts` for utilities

### Testing Strategy

- **Unit tests**: Test domain logic in isolation
- **Integration tests**: Test adapter integrations (mark with `@pytest.mark.integration`)
- **Contract tests**: Verify API contracts (mark with `@pytest.mark.contract`)
- **Slow tests**: Long-running tests (mark with `@pytest.mark.slow`)
- **Database tests**: Tests requiring DB (mark with `@pytest.mark.db` or `@pytest.mark.pgvector`)

### Security Considerations

- **Authentication**: JWT-based auth for production, auto-generated keys for development
- **Input Validation**: Use Pydantic models for all API inputs
- **SQL Injection**: Use SQLAlchemy ORM parameterized queries
- **XSS Prevention**: React auto-escapes by default, but sanitize user HTML
- **OWASP Top 10**: Red team tests in `tests/` (mark with `@pytest.mark.redteam`)

### Performance Guidelines

- **Database Queries**: Use eager loading to avoid N+1 queries
- **Vector Search**: Leverage pgvector indexes for efficient similarity search
- **Caching**: Use cachetools for expensive computations
- **Background Jobs**: Offload heavy processing to Celery workers

## Important Files and Locations

### Configuration
- `pyproject.toml` - Python package configuration and dependencies
- `.env.example` - Environment variable template
- `Taskfile.yml` - Task runner configuration
- `constraints/` - Pinned dependency versions

### Documentation
- `docs/INDEX.md` - Master documentation index
- `docs/architecture.md` - Detailed architecture documentation
- `docs/API.md` - API documentation
- `docs/testing.md` - Testing guidelines
- `CONTRIBUTING.md` - Contribution guidelines
- `SECURITY.md` - Security policies
- `THREATMODEL.md` - Threat modeling

### Key Application Code
- `exegesis/domain/` - Core business entities and logic
- `exegesis/application/facades/` - Simplified subsystem interfaces
- `exegesis/infrastructure/api/app/main.py` - FastAPI application entry point
- `exegesis/services/web/` - Next.js frontend application

### Scripts
- `scripts/reset_reseed_smoke.py` - Database seeding for development
- `scripts/update_constraints.py` - Dependency lock file management
- `scripts/dev.ps1` / `scripts/run.sh` - Development launchers

### Tests
- `tests/` - All test suites
- `conftest.py` - Pytest configuration and fixtures

## Common Tasks

### Adding a New Endpoint

1. Define DTOs in `exegesis/application/dtos/`
2. Create use case in `exegesis/application/use_cases/`
3. Add route in `exegesis/infrastructure/api/app/routes/`
4. Write tests in `tests/infrastructure/api/`

### Adding a New Repository

1. Define interface in `exegesis/domain/repositories/`
2. Implement in `exegesis/adapters/persistence/`
3. Register in dependency injection container

### Updating Dependencies

```bash
# Edit pyproject.toml with new version ranges
# Then regenerate constraints
python scripts/update_constraints.py

# Verify constraints are up to date (for CI)
python scripts/update_constraints.py --check
```

### Database Migrations

```bash
# The system uses SQLAlchemy for ORM
# Schema changes are managed through model updates
# Tests marked with @pytest.mark.schema will verify migrations
```

### Seeding Test Data

```bash
# Unix/macOS
./scripts/reset_reseed_smoke.py --log-level DEBUG

# PowerShell
./scripts/reset-reseed-smoke.ps1 -LogLevel DEBUG
```

## Git Workflow

This is a git worktree environment:
- **Worktree path**: `C:\Users\dmedl\.claude-worktrees\Exegesis AI\competent-cohen`
- **Main repository**: `C:\Users\dmedl\Projects\Exegesis AI`
- **Current branch**: `competent-cohen`

### Commit Guidelines

- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- Reference issues when applicable
- Keep commits atomic and focused
- Write descriptive commit messages explaining "why" not "what"

### Before Committing

1. Run tests: `pytest -m "not (slow or gpu)"`
2. Check linting: `ruff check .`
3. Format code: `ruff format .`
4. Verify types: `mypy exegesis/infrastructure/api/app`

## Key Concepts

### OSIS References
- **Open Scripture Information Standard** - Canonical format for Bible references
- Example: `Gen.1.1`, `Matt.5.3-Matt.5.12`
- All search results are normalized to OSIS format

### Hybrid Search
- **Semantic search**: Uses vector embeddings for meaning-based retrieval
- **Lexical search**: Traditional keyword matching
- Combined for optimal recall and precision

### Research Collections
- Feature for organizing documents into themed collections
- Supports SQLAlchemy-based repository implementation
- See recent commit: `cccde7e8` for implementation details

### Evidence Panel
- UI component that displays sources and citations
- Ensures all AI-generated content is traceable
- Export formats: Markdown, NDJSON, CSV

## Troubleshooting

### Common Issues

1. **PostgreSQL connection errors**
   - Verify port 5432 is available
   - Check DATABASE_URL environment variable

2. **Node.js version conflicts**
   - Verify `node --version` returns 20.x+
   - Use `nvm use` if .nvmrc is present

3. **ML model download failures**
   - Confirm internet access and disk space
   - Rerun `pip install .[ml] -c constraints/prod.txt`

4. **Import errors**
   - Ensure virtual environment is activated
   - Verify package is installed in editable mode

## Recent Changes

Based on recent commits:
- **Rebranding**: Project renamed from "Theoria" to "Exegesis AI"
- **Research Collections**: New feature for organizing research (commit `cccde7e8`)
- **Package Updates**: Dependencies migrated from `theoria` to `exegesis-ai`
- **Documentation Updates**: Docstring references updated to reflect new name

## Resources

- **API Docs**: http://localhost:8000/docs (when running locally)
- **Web UI**: http://localhost:3000 (when running locally)
- **Command Palette**: Press ⌘K/CTRL+K in the web UI
- **Issue Tracker**: Check project repository for issues and pull requests

## Notes for AI Assistants

1. **Prefer editing over creating**: Always edit existing files rather than creating new ones unless absolutely necessary
2. **Follow DDD patterns**: Respect the domain-driven design architecture
3. **Test coverage**: Write tests for all new features
4. **Citation integrity**: Maintain verse-reference traceability in all retrieval operations
5. **Security first**: Validate all inputs, avoid OWASP Top 10 vulnerabilities
6. **Documentation**: Update relevant docs when making architectural changes
7. **Backwards compatibility**: Avoid compatibility hacks; delete unused code completely

## Authentication Notes

- **Development**: Auto-generated API key (printed to console on startup)
- **Production**: Configure `EXEGESIS_API_KEY` or `EXEGESIS_JWT_SECRET`
- **API exits on startup** if auth is not configured in production/staging environments
