# Authentic Marathi Preparation Pipeline for Tipitaka XML

This folder adds a **truth-first, review-first Marathi preparation workflow** for the `tipitaka-xml` corpus.

## Why this workflow exists

The upstream repository contains the canonical source text and script conversions for the Tipitaka.org corpus. The repository README states that the primary source text is maintained in `deva_master` and then transliterated into the other supported scripts by conversion tools. It also states that the files are updated over time as errors are corrected and asks downstream users to keep projects synced with the latest versions.

Because there is **no complete official Marathi translation layer in this repository**, this workflow does **not** invent one. Instead, it prepares the entire corpus for an **auditable, human-reviewed Marathi layer** that stays aligned to the Pali source and Vipassana-style terminology discipline.

## What this workflow does

- scans the whole repository for XML / TXT / MD source material
- extracts segment-level source text with stable IDs
- creates a manifest for the whole corpus
- applies a locked doctrinal glossary
- generates reviewer CSV batches for Marathi preparation
- validates Marathi rows for forbidden drift and terminology inconsistency
- merges reviewed batches into a single parallel corpus
- exports JSONL and CSV for apps, websites, and search

## What this workflow does not do

- it does **not** claim to create an official Marathi translation of the full Tipitaka
- it does **not** auto-publish unreviewed machine output as canonical truth
- it does **not** replace scholarly, linguistic, or doctrinal review

## Folder layout

- `glossary_locked.csv` — core locked terms
- `config.example.yaml` — example configuration
- `schema/translation_record.schema.json` — output schema
- `templates/review_batch.csv` — review CSV header example
- `tools/pipeline.py` — end-to-end CLI

## Quick start

```bash
python marathi/tools/pipeline.py scan \
  --repo-root . \
  --output marathi/work/source_segments.jsonl

python marathi/tools/pipeline.py manifest \
  --segments marathi/work/source_segments.jsonl \
  --output marathi/work/corpus_manifest.json

python marathi/tools/pipeline.py batch \
  --segments marathi/work/source_segments.jsonl \
  --glossary marathi/glossary_locked.csv \
  --batch-size 500 \
  --output-dir marathi/work/review_batches

# reviewers fill reviewed_marathi and reviewer_notes columns in each CSV

python marathi/tools/pipeline.py validate \
  --input-dir marathi/work/review_batches \
  --glossary marathi/glossary_locked.csv \
  --report marathi/work/validation_report.json

python marathi/tools/pipeline.py merge \
  --input-dir marathi/work/review_batches \
  --output marathi/work/marathi_parallel_corpus.jsonl

python marathi/tools/pipeline.py export \
  --input marathi/work/marathi_parallel_corpus.jsonl \
  --csv-output marathi/work/marathi_parallel_corpus.csv
```

## Authenticity rules

1. **Source first** — every Marathi line must remain traceable to a source segment.
2. **No hidden interpretation** — reviewer notes can explain choices, but the translation field stays direct.
3. **Locked terminology** — doctrinal terms are controlled through `glossary_locked.csv`.
4. **Review required** — unreviewed rows must never be published as final truth.
5. **Sync upstream** — rerun extraction after upstream corrections.

## Recommended review statuses

- `draft` — initial prepared row
- `reviewed` — linguistically checked
- `vipassana_checked` — checked for terminology and doctrinal discipline
- `approved` — publication-ready

## Minimal publication gate

Only publish rows where:

- `status == approved`
- `reviewer_name` is present
- `vipassana_notes` is non-empty when doctrinal terms appear

## Notes

- Marathi uses the Devanagari script, but **Devanagari source text is not the same thing as Marathi translation**. This pipeline keeps that distinction explicit.
- The workflow is intentionally conservative: it is designed to prevent overclaiming and doctrinal drift.
