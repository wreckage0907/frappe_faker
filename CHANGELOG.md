# Changelog

All notable changes to Frappe Faker are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-05-31

First public release.

### Added
- Schema-aware data generation for any DocType, including child tables.
- Automatic dependency resolution: Link fields are resolved into a graph,
  topologically sorted, and generated in foreign-key-safe order. Existing
  records are reused; system DocTypes are never fabricated.
- Multiple AI providers: OpenAI, Anthropic, Gemini, Ollama, and any
  OpenAI-compatible custom endpoint.
- Two insertion paths: a fast `db_insert` path and a standard `doc.insert`
  path that runs Python hooks and validation.
- Batch tracking with one-click rollback from the UI, the API, and the CLI.
- Vue 3 single-page UI at `/faker` with a dependency-tree preview, live job
  progress, a per-DocType results breakdown, and generation history.
- `bench faker` CLI commands: `plan`, `generate`, and `cleanup`.
- Background generation via Frappe's RQ queue, with synchronous generation
  available for the CLI and small runs.
- Claude Code skill for agent-driven test-data generation.
