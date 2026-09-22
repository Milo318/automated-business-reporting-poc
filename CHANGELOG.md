# Changelog

## 1.1.0

Validation and failure-handling update for verified business kpi reporting.

- Validate row identities, statuses, financial signs, finite amounts and ticket chronology.
- Use decimal financial arithmetic and reconcile revenue against the ledger.
- Require won leads to belong to the qualified cohort used in the conversion denominator.
- Block publication when reconciliation fails.
- Publish only a canonical statement derived from verified metric fields.
- Replace incorrect or unavailable model output with the same deterministic statement.
- Escape report text and generate both HTML and machine-readable JSON.

The documented runtime contracts now take precedence over historical benchmark cards.
Old live-model results remain preserved as historical evidence. See README for supported
input formats, output semantics and the checks to reproduce locally.
