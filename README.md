# Authentic Marathi Preparation System for Tipitaka XML

This package is designed to be dropped into the root of the `tipitaka-xml` repository.

It does **not** claim to generate an official Marathi Tipitaka automatically. Instead, it builds a full-corpus, auditable workflow for preparing Marathi in a truth-first way:

- source scan across the whole repository
- segment extraction with stable IDs
- corpus manifest generation
- locked doctrinal glossary
- reviewer batch generation
- validation checks
- merge/export pipeline
- simple reviewer web app

## Quick start

```bash
python marathi/tools/pipeline.py scan --repo-root . --output marathi/work/source_segments.jsonl
python marathi/tools/pipeline.py manifest --segments marathi/work/source_segments.jsonl --output marathi/work/corpus_manifest.json
python marathi/tools/pipeline.py batch --segments marathi/work/source_segments.jsonl --glossary marathi/glossary_locked.csv --batch-size 500 --output-dir marathi/work/review_batches
python marathi/tools/pipeline.py validate --input-dir marathi/work/review_batches --glossary marathi/glossary_locked.csv --report marathi/work/validation_report.json
python marathi/tools/pipeline.py merge --input-dir marathi/work/review_batches --output marathi/work/marathi_parallel_corpus.jsonl
python marathi/tools/pipeline.py export --input marathi/work/marathi_parallel_corpus.jsonl --csv-output marathi/work/marathi_parallel_corpus.csv
```

## Reviewer app

```bash
streamlit run marathi/app/reviewer_app.py
```

## Publication rule

Only rows with `status=approved` should be treated as publication-ready.
