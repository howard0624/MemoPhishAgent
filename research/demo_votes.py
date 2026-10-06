"""Synthetic audit examples ONLY. Does not visit websites or call APIs."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent/src"))
from memory_audit import build_vote_audit


def main():
    examples = [
        ("3:2", [True, True, True, False, False], [0.9] * 5),
        ("4:1", [True, True, True, True, False], [0.9] * 5),
        ("5:0", [True] * 5, [0.9] * 5),
        ("2:3", [True, True, False, False, False], [0.9] * 5),
        ("partial", [True] * 5, [0.9, 0.9, 0.9, 0.9, 0.59]),
        ("no_match", [True] * 5, [0.59] * 5),
    ]
    rows = []
    for name, labels, scores in examples:
        hits = [SimpleNamespace(key=f"fixture-{i}", score=score, value={
            "url": f"https://case-{i}.example.invalid", "verdict": {"malicious": label}})
            for i, (label, score) in enumerate(zip(labels, scores))]
        audit = build_vote_audit(hits, 5, 0.6)
        rows.append({"example": name, "synthetic": True, "audit": audit})
        print(f"{name}: accepted={audit['accepted_count']}, votes={audit['vote_group']}, route={audit['decision_route']}")
    output = ROOT / "research/synthetic_vote_examples.json"
    output.write_text(json.dumps({
        "warning": "Synthetic software verification ONLY; no real detection performance was measured.",
        "examples": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
