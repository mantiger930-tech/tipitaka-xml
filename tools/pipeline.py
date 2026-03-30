from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

TEXT_EXTENSIONS = {".xml", ".txt", ".md"}
DEFAULT_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__"}
FORBIDDEN_WORDS = {"कदाचित", "बहुधा", "म्हणजे", "अर्थात", "तत्त्वज्ञान"}
STATUS_VALUES = {"draft", "reviewed", "vipassana_checked", "approved"}


def load_glossary(glossary_path: str | None) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not glossary_path:
        return mapping
    with open(glossary_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pali = (row.get("pali") or "").strip()
            marathi = (row.get("marathi") or "").strip()
            if pali and marathi:
                mapping[pali.lower()] = marathi
    return mapping


def should_skip(path: Path, repo_root: Path, exclude_dirs: set[str]) -> bool:
    rel_parts = path.relative_to(repo_root).parts
    return any(part in exclude_dirs for part in rel_parts[:-1])


def iter_source_lines(repo_root: Path, include_exts: set[str], exclude_dirs: set[str]) -> Iterable[dict]:
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in include_exts:
            continue
        if should_skip(path, repo_root, exclude_dirs):
            continue
        try:
            with path.open(encoding="utf-8") as f:
                for idx, raw in enumerate(f, start=1):
                    line = raw.strip()
                    if not line:
                        continue
                    rid = hashlib.sha1(f"{path.as_posix()}:{idx}:{line}".encode("utf-8")).hexdigest()
                    yield {
                        "id": rid,
                        "source_path": path.as_posix(),
                        "line_no": idx,
                        "pali": line,
                    }
        except UnicodeDecodeError:
            continue


def cmd_scan(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    exclude_dirs = set(args.exclude_dir)
    include_exts = set(args.ext)
    total = 0
    with output.open("w", encoding="utf-8") as out:
        for rec in iter_source_lines(repo_root, include_exts, exclude_dirs):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += 1
    print(json.dumps({"written": total, "output": str(output)}, ensure_ascii=False))


def cmd_manifest(args: argparse.Namespace) -> None:
    source_counter = Counter()
    total = 0
    with open(args.segments, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            total += 1
            source_counter[rec["source_path"]] += 1
    manifest = {
        "total_segments": total,
        "source_files": len(source_counter),
        "top_files": source_counter.most_common(25),
    }
    with open(args.output, "w", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False))


def draft_from_glossary(pali: str, glossary: Dict[str, str]) -> str:
    result = pali
    for term, marathi in glossary.items():
        result = re.sub(rf"\b{re.escape(term)}\b", marathi, result, flags=re.IGNORECASE)
    return result if result != pali else ""


def cmd_batch(args: argparse.Namespace) -> None:
    glossary = load_glossary(args.glossary)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: List[dict] = []
    with open(args.segments, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            rows.append(rec)
    batch_size = args.batch_size
    file_count = 0
    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        batch_path = output_dir / f"review_batch_{file_count:05d}.csv"
        with batch_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "id",
                    "source_path",
                    "line_no",
                    "pali",
                    "marathi_draft",
                    "marathi_reviewed",
                    "status",
                    "reviewer_name",
                    "reviewer_notes",
                    "vipassana_notes",
                ],
            )
            writer.writeheader()
            for rec in chunk:
                writer.writerow(
                    {
                        **rec,
                        "marathi_draft": draft_from_glossary(rec["pali"], glossary),
                        "marathi_reviewed": "",
                        "status": "draft",
                        "reviewer_name": "",
                        "reviewer_notes": "",
                        "vipassana_notes": "",
                    }
                )
        file_count += 1
    print(json.dumps({"batches": file_count, "rows": len(rows), "output_dir": str(output_dir)}, ensure_ascii=False))


def row_has_locked_term(text: str, glossary: Dict[str, str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in glossary.keys())


def cmd_validate(args: argparse.Namespace) -> None:
    glossary = load_glossary(args.glossary)
    issues: List[dict] = []
    summary = Counter()
    for path in sorted(Path(args.input_dir).glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = row.get("id", "")
                status = (row.get("status") or "").strip()
                pali = row.get("pali") or ""
                reviewed = row.get("marathi_reviewed") or ""
                reviewer_name = row.get("reviewer_name") or ""
                vipassana_notes = row.get("vipassana_notes") or ""
                if status and status not in STATUS_VALUES:
                    issues.append({"id": rid, "error": "invalid_status", "value": status})
                if status == "approved" and not reviewed.strip():
                    issues.append({"id": rid, "error": "approved_without_text"})
                if status in {"reviewed", "vipassana_checked", "approved"} and not reviewer_name.strip():
                    issues.append({"id": rid, "error": "missing_reviewer_name"})
                if any(word in reviewed for word in FORBIDDEN_WORDS):
                    issues.append({"id": rid, "error": "forbidden_word_in_translation"})
                if row_has_locked_term(pali, glossary) and status == "approved" and not vipassana_notes.strip():
                    issues.append({"id": rid, "error": "approved_locked_term_without_vipassana_notes"})
                summary[status or "(blank)"] += 1
    report = {"issues": issues, "summary_by_status": dict(summary), "issue_count": len(issues)}
    with open(args.report, "w", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False))


def cmd_merge(args: argparse.Namespace) -> None:
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as out:
        for path in sorted(Path(args.input_dir).glob("*.csv")):
            with path.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    count += 1
    print(json.dumps({"merged_rows": count, "output": str(out_path)}, ensure_ascii=False))


def cmd_export(args: argparse.Namespace) -> None:
    rows = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    out_path = Path(args.csv_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with out_path.open("w", encoding="utf-8") as f:
            f.write("")
        print(json.dumps({"rows": 0, "csv_output": str(out_path)}, ensure_ascii=False))
        return
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "csv_output": str(out_path)}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Authentic Marathi preparation pipeline for Tipitaka XML")
    sub = p.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan")
    scan.add_argument("--repo-root", required=True)
    scan.add_argument("--output", required=True)
    scan.add_argument("--ext", nargs="*", default=sorted(TEXT_EXTENSIONS))
    scan.add_argument("--exclude-dir", nargs="*", default=sorted(DEFAULT_EXCLUDE_DIRS))
    scan.set_defaults(func=cmd_scan)

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--segments", required=True)
    manifest.add_argument("--output", required=True)
    manifest.set_defaults(func=cmd_manifest)

    batch = sub.add_parser("batch")
    batch.add_argument("--segments", required=True)
    batch.add_argument("--glossary", required=False)
    batch.add_argument("--batch-size", type=int, default=500)
    batch.add_argument("--output-dir", required=True)
    batch.set_defaults(func=cmd_batch)

    validate = sub.add_parser("validate")
    validate.add_argument("--input-dir", required=True)
    validate.add_argument("--glossary", required=False)
    validate.add_argument("--report", required=True)
    validate.set_defaults(func=cmd_validate)

    merge = sub.add_parser("merge")
    merge.add_argument("--input-dir", required=True)
    merge.add_argument("--output", required=True)
    merge.set_defaults(func=cmd_merge)

    export = sub.add_parser("export")
    export.add_argument("--input", required=True)
    export.add_argument("--csv-output", required=True)
    export.set_defaults(func=cmd_export)

    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
