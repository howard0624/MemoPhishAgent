"""Read-only vote diagnostics; no LLM calls and no ground-truth inputs."""

from collections import Counter
from typing import Any


def build_vote_audit(hits: list[Any], k: int, threshold: float) -> dict[str, Any]:
    candidates = []
    for rank, hit in enumerate(hits, 1):
        candidates.append({
            "rank": rank,
            "memory_id": hit.key,
            "url": hit.value["url"],
            "similarity": hit.score,
            "accepted": hit.score >= threshold,
            "malicious": bool(hit.value["verdict"].get("malicious", False)),
            "stored_confidence": hit.value["verdict"].get("confidence"),
        })
    accepted = [hit for hit in candidates if hit["accepted"]]
    counts = Counter(hit["malicious"] for hit in accepted)
    total = len(accepted)
    fast = total >= k and counts[True] > counts[False]
    return {
        "k": k,
        "similarity_threshold": threshold,
        "retrieved_count": len(candidates),
        "accepted_count": total,
        "candidates": candidates,
        "accepted_memory_ids": [hit["memory_id"] for hit in accepted],
        "vote_distribution": {"malicious": counts[True], "benign": counts[False]},
        "vote_group": f"{counts[True]}:{counts[False]}",
        "malicious_vote_fraction": counts[True] / total if total else None,
        "agreement_fraction": max(counts[True], counts[False]) / total if total else None,
        "original_fast_malicious": fast,
        "decision_route": (
            "fast_malicious" if fast else "memory_guided_llm" if total else "no_match_llm"
        ),
    }
