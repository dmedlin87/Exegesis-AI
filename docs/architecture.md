# Architecture Dependency Boundaries

The Exegesis AI codebase (formerly the Theo project) follows a layered
architecture that keeps the domain model isolated from infrastructure concerns.
The enforced dependency direction is:

```
exegesis.domain -> exegesis.application -> exegesis.infrastructure
```

* **Domain (`exegesis.domain`)** contains core business concepts. It must not
  depend on the application or infrastructure layers.
* **Application (`exegesis.application`)** coordinates domain workflows and
  exposes facades for infrastructure adapters. It may import the domain layer,
  but it must not reach into service runtimes, FastAPI, or infrastructure-level
  telemetry/resilience helpers.
* **Infrastructure (`exegesis.infrastructure`)** provides delivery mechanisms
  (API, CLI, UI) and may depend on both the application and domain layers.

## Enforced rules

The dependency graph is verified in two complementary ways:

1. **Architecture tests** (`tests/architecture/test_module_boundaries.py`)
   assert that application modules never import infrastructure runtime modules,
   telemetry/resilience/security adapters, FastAPI, or platform helpers.
   Symmetric tests also prevent domain modules from depending on infrastructure
   and ensure that workers/CLI entries resolve adapters through the shared
   bootstrap helpers.
2. **Import Linter** (`importlinter.ini`) encodes the layered contract so that no
   package can import “up” the stack. Any attempt to import from infrastructure
   to application (or from application to domain) fails during the lint step.

## Legacy platform retirement

The legacy `exegesis.platform` package (formerly `theo.platform` and its event
bus facade) has been fully removed in favour of direct orchestration through
`exegesis.application.services.bootstrap`. The bootstrap module now wires
adapters and services synchronously without the indirection of the former
platform events layer.【F:exegesis/application/services/bootstrap.py†L215-L303】
The architecture tests enforce that the package stays deleted and that no
module imports the retired namespace.【F:tests/architecture/test_module_boundaries.py†L182-L218】

Developers should resolve adapters or repositories by calling
`exegesis.application.services.bootstrap.resolve_application()` or the relevant
facade. Event publishers live under `exegesis.adapters.events` and are resolved
via `exegesis.application.facades.events`, matching the simplified interaction
model.【F:exegesis/application/facades/events.py†L1-L64】

## Running the checks locally

Use the Taskfile helpers to execute the architecture guardrails:

```sh
# run only the architecture-focused pytest suite
task architecture:test

# run the import-linter contracts
task architecture:imports

# run both together
task architecture:check
```

These commands run automatically in CI to block merges that break the enforced
module boundaries.

## Visualising the dependency graph

Generate snapshot artefacts with the Taskfile helper:

```sh
task architecture:graph
```

The command writes `dependency-graph.json` and `dependency-graph.svg` into
`dashboard/dependency-graph/`. Commit these files whenever the architecture
changes so reviewers can inspect the rendered diagram. To check for drift
between branches, compare the JSON metadata (`git diff -- dashboard/dependency-graph/dependency-graph.json`)
or open the SVGs in a viewer and toggle between versions.
