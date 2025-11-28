# Documentation Index

This index calls out the only permitted directories under `docs/` (see `00_DOCUMENTATION_STRATEGY.md`) and points to the new cleanup archive buckets introduced in Phase 0.1.

## Active structure
- `docs/adr/` – finalized architecture decisions. Immutable once approved.
- `docs/guides/` – developer and user guidance (setup, onboarding, troubleshooting).
- `docs/planning/` – living roadmaps, enhancement plans, and enhancement retrospectives.
- `docs/reference/` – API references, schema contracts, and curated metadata descriptions.
- `docs/specs/` – functional specifications and RFC-style proposals.
- `docs/archive/` – historical or superseded content (see the Cleanup section below).
- `docs/inbox/` – temporary landing zone for unsorted notes or agent drafts (clean up or move to a canonical directory within 24 hours).
- `00_DOCUMENTATION_STRATEGY.md` – the policy that spells out this layout.

## Cleanup archive (`docs/archive/2025-11-Cleanup/`)
The following directories formerly lived at the `docs/` root and now sit under this archive bucket:

- `architecture/`
- `coverage/`
- `dashboards/`
- `dev/`
- `features/`
- `keys/`
- `migrations/`
- `process/`
- `releases/`
- `research/`
- `reviews/`
- `runbooks/`
- `security/`
- `status/`
- `tasks/`
- `testing/`

Every directory above is preserved verbatim for historical reference; new work should not modify them in place. The cleanup bucket also hosts:

- `DEPRECATED_FEATURE_MANIFEST.md` – Phase 0.1 inventory of deprecated features that are still referenced in archived docs along with the live code paths that need to be reconciled.

## Legacy archives
- `docs/archive/2025-10/`, `docs/archive/2025-10-26_core/`, `docs/archive/cleanup_2025_11/`, and older folders continue to hold snapshots from previous planning cycles. Refer to them for context when thunking about past decisions, but do not edit files there without explicit direction.

When you place new documentation assets in `docs/`, follow the `00_DOCUMENTATION_STRATEGY.md` guidance to keep the surface area ordered and predictable.
