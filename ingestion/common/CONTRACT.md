# ingestion/common

Shared ingestion primitives live here.

This folder is not a source channel. It provides reusable contracts and helpers for all source adapters.

## Owns

- Loading source configuration from `~/park-io/_source management- james/sources.md`.
- Building standard ingestion artifacts.
- Writing channel artifacts to deterministic paths.
- URL normalization and identity helpers.
- Structured health and error payloads.
- Test helpers for channel contract validation.

## Does Not Own

- Fetching a specific source.
- Scoring or summarization.
- Reader-facing digest composition.
- Media transcript generation.

## Output Contract

All channel folders should converge on `contracts/ingestion-artifact.schema.json`.
