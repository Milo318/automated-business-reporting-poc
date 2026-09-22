# Verified Business KPI Reporting

Build repeatable KPI reports from validated operational CSV exports.

[![Quality](https://github.com/Milo318/automated-business-reporting-poc/actions/workflows/ci.yml/badge.svg)](https://github.com/Milo318/automated-business-reporting-poc/actions/workflows/ci.yml)

## What the current implementation guarantees

- Validate row identities, statuses, financial signs, finite amounts and ticket chronology.
- Use decimal financial arithmetic and reconcile revenue against the ledger.
- Require won leads to belong to the qualified cohort used in the conversion denominator.
- Block publication when reconciliation fails.
- Publish only a canonical statement derived from verified metric fields.
- Replace incorrect or unavailable model output with the same deterministic statement.
- Escape report text and generate both HTML and machine-readable JSON.

## Run

Requires Python 3.11 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m business_reporting.cli
python -m business_reporting.cli --data /path/to/csv --output output/report.html
python -m business_reporting.benchmark --runs 50 --output /tmp/report-benchmark.json
```

## Scope and integration contract

The CSV contract is demonstrated in `data/mock`: payments, customers, leads and tickets.
Refund amounts must be negative; payment amounts nonnegative. The caller supplies a single
reporting period's records. SLA compliance uses resolved tickets as its denominator.
Production ingestion, period selection and accounting/CRM connectors remain separate work.

`--ai` uses `LLM_API_KEY` and optional `LLM_MODEL`/`LLM_API_URL`, plus `--previous` for the
prior snapshot. The primary change is selected in code. Every published sentence follows
the verified template: arbitrary model prose, unsupported causal explanations and extra
fields are never published. The model is optional and is not needed to calculate or explain
these four metrics. Provider failures fall back to the verified statement.

See [SCHEDULING.md](SCHEDULING.md) for scheduled execution.

## Verification

```bash
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
```

CI runs these checks and a fresh deterministic benchmark on Python 3.11 and 3.13.
Tests include malformed inputs, known regression cases and mocked provider failures.
No credentials or live model calls are needed for the test suite. Provider responses have
size limits, JSON-object validation and bounded retries for transient failures.

## Benchmark evidence

All bundled datasets are synthetic. `proof/benchmark.json` records a deterministic demo
run; it does not establish performance on arbitrary customer data. The older
`proof/autonomous-benchmark.json`, case JSONL and portfolio image are **historical v1.0.0
artifacts**, not quality or accuracy guarantees for v1.1.0. Their archive-consistency test
does not execute the current controller or a live model.

Use the current regression suite to verify the current behavior. A fresh live-model
benchmark is optional and requires a configured Ollama instance; none is implied by a green
CI result. [Changes and compatibility](CHANGELOG.md).

Built by **Milo Geller** · [MIT licensed](LICENSE).
