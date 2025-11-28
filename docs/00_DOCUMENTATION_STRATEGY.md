# Documentation Strategy

This file codifies the only allowed structure for the `docs/` directory and prevents agent confusion by making it clear where content belongs:

- `docs/adr/`: Architecture Decision Records; once finalized they are immutable.
- `docs/specs/`: Functional specifications and RFCs.
- `docs/guides/`: Developer and user guides such as setup and troubleshooting.
- `docs/planning/`: Active roadmaps and task lists.
- `docs/reference/`: API documentation, schema definitions, and data dictionaries.
- `docs/archive/`: Deprecated or superseded content.
- `docs/inbox/`: The only permitted location for unsorted or temporary AI dumps.

NO files are allowed in the `docs/` root except this file and `README.md`.

## Routing Logic

- IF content is a decision -> `docs/adr/`
- IF content is a plan -> `docs/planning/`
- IF unsure -> `docs/inbox/`
