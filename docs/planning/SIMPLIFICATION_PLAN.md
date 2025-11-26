# Exegesis-AI Simplification Plan

**Version:** 1.0
**Date:** November 25, 2024
**Status:** Draft

## Executive Summary

This document outlines opportunities to reduce codebase complexity and technical debt in Exegesis-AI. The goal is to improve maintainability, reduce test flakiness, and establish a stable foundation for Phase 1+ features.

## Current State Assessment

### Codebase Metrics

- **Total Python files:** 433
- **TODO/FIXME comments:** 18 (very clean)
- **Deprecated imports:** 0 (migration from `theo` to `exegesis` complete)
- **Test files:** ~200+
- **Test isolation issues:** ~18 flaky tests when running full suite with random ordering (down from 19)

### Already Completed Cleanup

1. **Neo4j graph projection** - Retired (adapter, hooks, dependencies removed)
2. **Standalone MCP FastAPI server** - Retired (consolidated into REST/CLI)
3. **Package rename** - Migrated from `theo` to `exegesis` namespace

## Priority 1: Test Infrastructure Stabilization

### Issue: Test Isolation Failures

**Impact:** 19 tests fail when run with `--randomly-seed=1337` but pass individually

**Root Causes:**

1. Session-scoped fixtures in `tests/api/conftest.py` patch modules globally
2. Global state in `database_module._engine`, `telemetry_module._provider`
3. Settings cache not cleared between tests

**Completed Fixes:**

- Added `_reset_global_state` fixture in `tests/conftest.py`
- Fixed `test_telemetry_facade.py` to reload module fresh
- Added `skip_database` parameter when `api_engine` fixture is in use
- Fixed `test_api_boots_contradiction_seeding_without_migrations` to restore real `seed_reference_data` when session-scoped patches are active

**Remaining Work:**

- [ ] Audit remaining session-scoped fixtures in `tests/api/conftest.py` for isolation issues
- [ ] Consider converting session-scoped autouse fixtures to use markers instead
- [ ] Add explicit fixture ordering documentation

## Priority 2: Dependency Cleanup

### Unused or Redundant Dependencies

Review `pyproject.toml` for:

- [ ] Dependencies only used in deprecated features
- [ ] Duplicate functionality (e.g., multiple HTTP clients)
- [ ] Development dependencies that should be optional

### Heavy Dependencies

Consider lazy loading or making optional:

- `torch` - Only needed for ML features
- `sentence-transformers` - Only needed for embeddings
- `testcontainers` - Only needed for pgvector tests

## Priority 3: Code Consolidation

### Facade Layer Review

The `exegesis/application/facades/` layer should be audited for:

- [ ] Facades that are thin wrappers with no added value
- [ ] Duplicate functionality across facades
- [ ] Facades that could be merged

### Infrastructure Layer Review

The `exegesis/infrastructure/api/app/` structure has deep nesting:

- [ ] Consider flattening where appropriate
- [ ] Remove empty `__init__.py` files that add no exports
- [ ] Consolidate small related modules

## Priority 4: Documentation Cleanup

### Archive Candidates

Files in `docs/` that may be outdated:

- [ ] Review `docs/process/` for stale debugging logs
- [ ] Consolidate planning documents into roadmap
- [ ] Update `docs/INDEX.md` with current structure

### Missing Documentation

- [ ] Create `docs/testing/TEST_MAP.md` (per roadmap)
- [ ] Document fixture dependencies and ordering
- [ ] Add architecture diagrams for new developers

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Test isolation failures | 18 | 0 |
| TODO/FIXME comments | 18 | <10 |
| Cyclomatic complexity (avg) | Unknown | Measure baseline |
| Import time | Unknown | <2s |
| Test suite runtime | ~5 min | <3 min |

## Implementation Timeline

### Week 1-2: Test Stabilization

- Complete test isolation fixes
- Document fixture dependencies
- Achieve 0 flaky tests

### Week 3: Dependency Audit

- Review and prune dependencies
- Add lazy loading for heavy deps
- Update constraints files

### Week 4: Code Consolidation

- Flatten deep nesting where appropriate
- Remove dead code paths
- Update documentation

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking changes during cleanup | Medium | High | Comprehensive test coverage first |
| Removing code still in use | Low | High | Grep for all usages before removal |
| Introducing new bugs | Medium | Medium | Incremental changes with CI validation |

## Next Steps

1. Run full test suite with different random seeds to identify all flaky tests
2. Create test isolation tracking issue
3. Begin dependency audit with `pip-audit` and `pipdeptree`
4. Measure current cyclomatic complexity baseline
