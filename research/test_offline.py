"""Offline tests execute actual source classes via AST with fake external services.

These tests cover logic and data plumbing, not LangGraph/LLM integration.
"""

import ast
import asyncio
import itertools
import hashlib
import json
import logging
import sys
import time
import unittest
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, Optional, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent" / "src"))
from memory_audit import build_vote_audit
from evaluate_votes import evaluate


@contextmanager
def test_directory():
    # Avoid Windows TemporaryDirectory ACL changes; keep fixtures under ignored runs/.
    folder = ROOT / "research" / "runs" / ("offline-" + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    yield str(folder)


class Message:
    def __init__(self, content="", tool_calls=None, name=None, **kwargs):
        self.content, self.tool_calls, self.name = content, tool_calls or [], name

    def pretty_print(self):
        pass


class ToolMessage(Message):
    pass


class FakeStore:
    def __init__(self, index=None, hits=None):
        self.hits = hits or []
        self.records = {}

    def search(self, namespace, query=None, limit=10, offset=0):
        items = self.hits if query is not None else [
            SimpleNamespace(key=key, value=value) for key, value in self.records.items()]
        return items[offset:offset + limit]

    def put(self, namespace, key, value):
        self.records[key] = value


def hits(labels, scores=None):
    scores = scores or [0.9] * len(labels)
    return [SimpleNamespace(key=f"case-{i}", score=score, value={
        "url": f"https://case-{i}.example.invalid", "keywords": ["login"],
        "verdict": {"malicious": label, "confidence": 5, "reason": "fixture"}, "trace": []})
        for i, (label, score) in enumerate(zip(labels, scores))]


def load_classes(source, names):
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names]
    scope = {"Any": Any, "Optional": Optional, "Literal": Literal, "cast": cast,
             "Counter": Counter, "Path": Path, "json": json, "logging": logging, "hashlib": hashlib,
             "logger": logging.getLogger("offline"), "uuid": uuid, "time": time,
             "asyncio": asyncio, "InMemoryStore": FakeStore, "AgentTools": Any,
             "ReactURLState": Any, "URLState": Any, "BaseTool": Any,
             "RunnableConfig": Any, "CompiledStateGraph": Any,
             "AIMessage": Message, "HumanMessage": Message, "ToolMessage": ToolMessage,
             "build_vote_audit": build_vote_audit,
             "get_memory_embeddings": lambda provider: (None, 1),
             "get_provider_from_llm": lambda llm: "fake",
             "extract_and_fix": lambda text: [json.loads(text)],
             "is_rate_limit_error": lambda exc: False,
             "SYSTEM_REACT": "", "SYSTEM_REACT_MEM": ""}
    exec(compile(tree, "<actual-source-with-fake-services>", "exec"), scope)
    return scope


MEMORY = load_classes((ROOT / "agent/src/memory.py").read_text(encoding="utf-8"),
                      {"AgenticMemorySystem", "MemoryNodes"})
HELPERS = load_classes((ROOT / "agent/src/agent_helpers.py").read_text(encoding="utf-8"), {"ReactNodes"})


class OfflineTests(unittest.TestCase):
    def make_memory(self, labels, scores=None, k=5):
        memory = MEMORY["AgenticMemorySystem"](None, k=k)
        memory.memory_store = FakeStore(hits=hits(labels, scores))
        return memory

    def test_original_vote_behavior_unchanged(self):
        # Compare against the imported upstream implementation, not a rewritten formula.
        upstream = (ROOT / "research/upstream_memory.py.txt").read_text(encoding="utf-8")
        original = load_classes(upstream, {"AgenticMemorySystem"})["AgenticMemorySystem"]
        for k in (1, 4, 5):
            for labels in itertools.product((False, True), repeat=k):
                for scores in ([0.9] * k, [0.59] + [0.6] * (k - 1)):
                    current = self.make_memory(labels, scores, k)
                    old = original(None, k=k)
                    old.memory_store = current.memory_store
                    expected = asyncio.run(old.search_by_keywords_w_majority(["login"]))
                    self.assertEqual(asyncio.run(current.search_by_keywords_w_majority(["login"])), expected)
                    snippet, majority, audit = asyncio.run(current.search_by_keywords_w_majority(["login"], True))
                    self.assertEqual((snippet, majority), expected)
                    self.assertEqual(audit["original_fast_malicious"], majority is True)

    def test_routes_and_similarity_boundary(self):
        for malicious_count in (3, 4, 5):
            memory = self.make_memory([True] * malicious_count + [False] * (5 - malicious_count))
            _, majority, audit = asyncio.run(memory.search_by_keywords_w_majority(["login"], True))
            self.assertTrue(majority)
            self.assertEqual(audit["vote_group"], f"{malicious_count}:{5 - malicious_count}")
        partial = build_vote_audit(hits([True] * 5, [0.6, 0.9, 0.9, 0.9, 0.59]), 5, 0.6)
        self.assertEqual(partial["accepted_count"], 4)
        self.assertEqual(partial["decision_route"], "memory_guided_llm")
        self.assertEqual(len(partial["candidates"]), 5)
        for labels in ([False] * 5, [True, True, False, False]):
            self.assertEqual(build_vote_audit(hits(labels), len(labels), 0.6)["decision_route"], "memory_guided_llm")
        self.assertEqual(build_vote_audit([], 5, 0.6)["decision_route"], "no_match_llm")

    def test_snapshot_roundtrip_and_freeze(self):
        memory = self.make_memory([])
        with test_directory() as folder:
            path = str(Path(folder) / "memory.json")
            memory.snapshot_out = path
            for i in range(105):
                asyncio.run(memory.store_memory(["login"], [], {"malicious": True, "confidence": 5}, f"fixture-{i}"))
            restored = MEMORY["AgenticMemorySystem"](None, snapshot_in=path, freeze_writes=True)
            self.assertEqual(restored.memory_store.records, memory.memory_store.records)
            asyncio.run(restored.store_memory([], [], {"malicious": False}, "new"))
            self.assertEqual(len(restored.memory_store.records), 105)
            self.assertEqual(restored.snapshot_sha256, hashlib.sha256(Path(path).read_bytes()).hexdigest())
            with self.assertRaises(ValueError):
                MEMORY["AgenticMemorySystem"](None, snapshot_in=path, snapshot_out=path)

    def test_prepare_memory_carries_local_audit(self):
        class Crawl:
            async def arun(self, args):
                return {"text": "fixture", "screenshot": "fixture"}
        memory = self.make_memory([True, True, True, False, False])
        async def summarize(*args):
            return ["login"]
        memory.summarize_keywords = summarize
        node = MEMORY["MemoryNodes"](SimpleNamespace(crawl=Crawl()), memory)
        result = asyncio.run(node.prepare_memory(SimpleNamespace(url="fixture")))
        self.assertEqual(result["memory_audit"]["vote_group"], "3:2")
        self.assertTrue(result["memory_majority"])

    def test_fast_path_and_fallback(self):
        class LLM:
            def __init__(self):
                self.calls = 0
            def bind_tools(self, tools):
                return self
            async def ainvoke(self, prompt):
                self.calls += 1
                return Message(content="fallback")
        llm = LLM()
        nodes = HELPERS["ReactNodes"](llm, [], None, {}, SimpleNamespace())
        state = SimpleNamespace(memory_majority=True, memory_snippet="fixture",
                                url="fixture", messages=[], is_last_step=False)
        answer = asyncio.run(nodes.call_model(state))
        self.assertEqual(json.loads(answer["messages"][0].content)["verdicts"][0]["malicious"], True)
        self.assertEqual(llm.calls, 0)
        state.memory_majority = False
        asyncio.run(nodes.call_model(state))
        self.assertEqual(llm.calls, 1)

    def test_jsonl_output_and_label_separation(self):
        with test_directory() as folder:
            args = SimpleNamespace(output=str(Path(folder) / "predictions.json"),
                                   memory_audit_output=str(Path(folder) / "audit.jsonl"))
            nodes = HELPERS["ReactNodes"](None, [], SimpleNamespace(usage_metadata={}), {}, args)
            nodes.react_agent = object()
            async def fixture(url, idx):
                return {"type": "full", "url": url, "elapsed_seconds": 1,
                        "final_msg": json.dumps({"verdicts": [{"malicious": True, "confidence": 5}]}),
                        "memory_case": "memory_reuse", "completed_react_tools": {},
                        "memory_audit": build_vote_audit(hits([True] * 3 + [False] * 2), 5, 0.6)}
            nodes._process_one_url = fixture
            asyncio.run(nodes.react_judge_node({"urls": ["fixture"]}))
            row = json.loads(Path(args.memory_audit_output).read_text(encoding="utf-8"))
            self.assertNotIn("ground_truth", row)
            self.assertIsNone(row["tokens_used"])
            report, joined = evaluate([row], {"fixture": False})
            self.assertEqual(report["fast_vote_groups"]["3:2"]["fp"], 1)
            self.assertEqual(joined[0]["ground_truth"], False)

    def test_failures_and_missing_labels_are_not_scored(self):
        rows = [{"url": "failed", "status": "processing_failed"},
                {"url": "missing", "status": "ok", "original_verdict": True}]
        report, _ = evaluate(rows, {})
        self.assertEqual(report["evaluated_rows"], 0)
        self.assertIsNone(report["overall"]["precision"])
        with self.assertRaises(ValueError):
            evaluate(rows + [rows[0]], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
