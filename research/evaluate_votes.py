"""Join labels AFTER inference and report conditional error rates and coverage."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def load_labels(path):
    labels = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row["label"].strip().lower()
            if value not in ("malicious", "benign"):
                raise ValueError("label must be malicious or benign")
            label = value == "malicious"
            url = row["url"]
            if url in labels and labels[url] != label:
                raise ValueError("Conflicting ground-truth labels for the same URL")
            labels[url] = label
    return labels


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def metrics(rows):
    tp = sum(r["original_verdict"] and r["ground_truth"] for r in rows)
    fp = sum(r["original_verdict"] and not r["ground_truth"] for r in rows)
    fn = sum(not r["original_verdict"] and r["ground_truth"] for r in rows)
    tn = sum(not r["original_verdict"] and not r["ground_truth"] for r in rows)
    return {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "error_rate": rate(fp + fn, len(rows)),
            "precision": rate(tp, tp + fp), "recall": rate(tp, tp + fn),
            "f1": rate(2 * tp, 2 * tp + fp + fn),
            "false_positive_rate": rate(fp, fp + tn),
            "mean_elapsed_seconds": rate(sum(r.get("elapsed_seconds", 0) for r in rows), len(rows))}


def evaluate(rows, labels):
    joined, failed, missing = [], [], []
    seen = set()
    for row in rows:
        if row["url"] in seen:
            raise ValueError("Duplicate evaluation URLs: deduplicate the test list first")
        seen.add(row["url"])
        if row.get("status") != "ok":
            failed.append(row["url"])
            continue
        if row["url"] not in labels:
            missing.append(row["url"])
            continue
        if not isinstance(row.get("original_verdict"), bool):
            raise ValueError("Verdict must be boolean")
        joined.append({**row, "ground_truth": labels[row["url"]]})
    groups = defaultdict(list)
    for row in joined:
        if row.get("decision_route") == "fast_malicious":
            groups[row["vote_group"]].append(row)
    fast_count = sum(len(group) for group in groups.values())
    return {
        "scope": "Original predictions; observational associations, not calibrated probabilities or causal effects.",
        "total_rows": len(rows), "evaluated_rows": len(joined),
        "processing_failures": failed, "missing_ground_truth": missing,
        "evaluation_coverage": rate(len(joined), len(rows)),
        "fast_fraction_of_evaluated": rate(fast_count, len(joined)),
        "overall": metrics(joined),
        "fast_vote_groups": {group: metrics(items) for group, items in sorted(groups.items())},
        "group_note": "For fast-malicious groups, error_rate is FP/(TP+FP), not the population false-positive rate.",
    }, joined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--labels", required=True, help="CSV with url,label; used only after inference")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.audit).read_text(encoding="utf-8").splitlines() if line.strip()]
    report, joined = evaluate(rows, load_labels(args.labels))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    target.with_suffix(".joined.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in joined), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
