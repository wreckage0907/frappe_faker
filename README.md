# Frappe Faker

Generate realistic, correctly-linked test data for any Frappe/ERPNext DocType
using an LLM — then delete it again in one click when you're done.

Point it at a DocType. It reads the schema, works out every DocType that one
links to, generates believable records with an AI provider of your choice, and
inserts them in dependency order so all the foreign keys line up. Every run is
tracked as a batch you can roll back.

<!-- TODO: add a screenshot or GIF of the generate -> results -> rollback flow at docs/images/generate.png -->

## Why

Empty dev sites are hard to work with. Hand-entering linked records (a Sales
Order needs a Customer, which needs a Customer Group...) is tedious, and plain
faker libraries ignore those links. Frappe Faker resolves the dependency graph
and generates data that actually validates and inserts.

## Install

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/wreckage0907/frappe_faker --branch main
bench install-app frappe_faker
```

## Configure

Open **Faker Settings** in Desk and pick an AI provider:

| Provider  | Notes |
|-----------|-------|
| OpenAI    | Needs an API key. |
| Anthropic | Needs an API key. |
| Gemini    | Google AI Studio key. Defaults to `gemini-2.5-flash` if Model Name is blank. |
| Ollama    | Local, no key. Defaults to `http://localhost:11434`. |
| Custom    | Any OpenAI-compatible endpoint. |

## Use it

### From the UI

Go to `/faker`, choose a DocType, set a count, optionally add free-text
instructions, and generate. You get a live progress view, a per-DocType
breakdown of what was created, and a one-click rollback.

### From the CLI

```bash
# See what will be generated (nothing is created)
bench --site mysite faker plan --doctype "Sales Order"

# Generate 5 Sales Orders and everything they depend on
bench --site mysite faker generate --doctype "Sales Order" --count 5 \
  --instructions "Enterprise customers, orders above 50k, last quarter"

# The output ends with a batch id:
#   Batch: 4l8mav5jir | Created: 18 | Failed: 0

# Undo the whole run
bench --site mysite faker cleanup --batch 4l8mav5jir
```

## How it works

1. **Meta analysis** — reads the DocType's fields, child tables, links, and
   naming rules into a schema for the prompt.
2. **Dependency resolution** — builds a graph of Link-field dependencies and
   topologically sorts it. Existing records are reused; system DocTypes (User,
   Company, Currency, ...) are never fabricated.
3. **Generation** — calls your configured LLM; calls for independent DocTypes
   run in parallel. Retries on malformed JSON.
4. **Insertion** — inserts in dependency order. A fast path uses `db_insert`
   for speed; `--no-fast-insert` runs full validation and Python hooks.
5. **Batch tracking** — every inserted record is logged so the run can be
   rolled back from the UI, the API, or the CLI.

## Notes and limitations

- Generation calls a live LLM, so it costs money/time and isn't deterministic —
  it's for seeding dev, demo, and test environments, not for fixed CI fixtures.
- The default fast insert path skips Python hooks, so generated documents won't
  have hook side-effects (ledger entries, computed defaults). Use
  `--no-fast-insert` when you need those.
- Access is restricted to System Manager. Intended for non-production sites.

## Development

```bash
cd apps/frappe_faker
pre-commit install   # ruff, eslint, prettier, pyupgrade
```

Run the tests:

```bash
bench --site mysite run-tests --app frappe_faker
```

Internal design notes live in [`docs/`](docs/).

## License

MIT
