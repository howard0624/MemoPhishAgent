"""Actual LangGraph integration with deterministic services and blocked network.

No API credentials, website access, paid calls, or detection-performance claims.
"""
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent/src'))
os.environ.setdefault('CRAWL4_AI_BASE_DIRECTORY', str(ROOT / 'research/runs/cache'))


class OfflineSearch:
    def __init__(self, **kwargs):
        pass
    def run(self, query: str) -> str:
        raise AssertionError('Search must never be called')
    async def arun(self, query: str) -> str:
        raise AssertionError('Search must never be called')


def blocked(*args, **kwargs):
    raise AssertionError('Network access forbidden in offline integration tests')


with patch('socket.socket.connect', blocked), patch('socket.create_connection', blocked):
    with patch('langchain_community.utilities.SerpAPIWrapper', OfflineSearch):
        import graph
        import memory
        from langchain_core.embeddings import Embeddings
        from langchain_core.messages import AIMessage, ToolMessage
        from langchain_core.tools import StructuredTool


class OfflineEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]
    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


class OfflineModel:
    memo_provider = 'openai'
    def __init__(self, tool_first=False):
        self.judge_calls = 0
        self.summary_calls = 0
        self.tool_first = tool_first
    def bind_tools(self, tools):
        return self
    async def ainvoke(self, prompt):
        if 'generate up to 10 keywords' in prompt[0]['content']:
            self.summary_calls += 1
            return AIMessage(content='login, account')
        self.judge_calls += 1
        if self.tool_first and not any(isinstance(m, ToolMessage) for m in prompt):
            return AIMessage(content='', tool_calls=[{
                'name': 'crawl_content', 'args': {'url': 'https://current.example.invalid', 'screenshot': True},
                'id': 'offline-crawl', 'type': 'tool_call'}])
        return AIMessage(content=json.dumps({'verdicts': [{
            'url': 'https://current.example.invalid', 'malicious': False,
            'confidence': 5, 'reason': 'Synthetic offline verdict'}]}))


class OfflineTools:
    def __init__(self, llm):
        self.calls = []
        async def crawl(url: str, screenshot: bool = False) -> dict:
            self.calls.append({'url': url, 'screenshot': screenshot})
            return {'text': 'Offline login fixture', 'screenshot': 'fixture'}
        self.crawl = StructuredTool.from_function(coroutine=crawl, name='crawl_content', description='Offline fixture crawler')
        for attr in ['extract_targets', 'check_img', 'check_screenshot', 'serpapi_search']:
            async def forbidden(query: str = '') -> str:
                raise AssertionError('Unexpected fixture tool')
            setattr(self, attr, StructuredTool.from_function(coroutine=forbidden, name=attr, description='Forbidden fixture tool'))


class GraphOfflineTests(unittest.TestCase):
    def run_case(self, labels, tool_first=False, freeze=True):
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            folder = Path(folder)
            snapshot = folder / 'input.json'
            snapshot.write_text(json.dumps({'schema_version': 1, 'entries': [
                {'memory_id': f'case-{i}', 'value': {'url': f'https://past-{i}.example.invalid',
                 'keywords': ['login'], 'verdict': {'malicious': label, 'confidence': 5,
                 'reason': 'fixture'}, 'trace': []}} for i, label in enumerate(labels)]}))
            args = SimpleNamespace(use_ai_overview=False, use_memory=True, provider='openai',
                model='offline-fixture', output=str(folder / 'output.json'),
                memory_audit_output=str(folder / 'audit.jsonl'))
            model, stores, tools = OfflineModel(tool_first), [], []
            original = memory.AgenticMemorySystem
            def make_store(*a, **kw):
                store = original(*a, **kw); stores.append(store); return store
            def make_tools(llm):
                instance = OfflineTools(llm); tools.append(instance); return instance
            with patch('socket.socket.connect', blocked), patch('socket.create_connection', blocked), \
                 patch.object(graph, 'get_llm', return_value=model), \
                 patch.object(graph, 'AgentTools', side_effect=make_tools), \
                 patch.object(graph, 'AgenticMemorySystem', side_effect=make_store), \
                 patch.object(memory, 'get_memory_embeddings', return_value=(OfflineEmbeddings(), 3)):
                compiled = graph.build_full_agent('openai', args=args, memory_kwargs={
                    'snapshot_in': str(snapshot), 'freeze_writes': freeze, 'k': 5, 'threshold': .6})
                result = asyncio.run(compiled.ainvoke({'urls': ['https://current.example.invalid']}))
            self.assertEqual(result['failed_urls'], [])
            audit = json.loads(Path(args.memory_audit_output).read_text())
            self.assertEqual(audit['status'], 'ok')
            self.assertEqual(audit['snapshot_sha256'], hashlib.sha256(snapshot.read_bytes()).hexdigest())
            self.assertEqual(audit['initial_crawl_calls'], 1)
            self.assertEqual(model.summary_calls, 1)
            self.assertIsNone(audit['tokens_used'])
            self.assertEqual(len(stores[0].memory_store.search(('agent_memory',), limit=100)),
                             len(labels) if freeze else len(labels) + 1)
            return audit, model, tools[0]

    def test_fast_malicious_3_2_freezes_real_store(self):
        audit, model, tools = self.run_case([True, True, True, False, False])
        self.assertEqual(audit['vote_group'], '3:2')
        self.assertEqual(audit['decision_route'], 'fast_malicious')
        self.assertTrue(audit['original_verdict'])
        self.assertEqual(model.judge_calls, 0)
        self.assertEqual(audit['completed_react_tool_count'], 0)
        self.assertEqual(len(tools.calls), 1)

    def test_benign_majority_can_finish_without_tools(self):
        audit, model, tools = self.run_case([True, True, False, False, False])
        self.assertEqual(audit['decision_route'], 'memory_guided_llm')
        self.assertFalse(audit['original_verdict'])
        self.assertEqual(model.judge_calls, 1)
        self.assertEqual(audit['completed_react_tool_count'], 0)

    def test_actual_toolnode_counts_completed_crawl(self):
        audit, model, tools = self.run_case([], tool_first=True)
        self.assertEqual(audit['decision_route'], 'no_match_llm')
        self.assertEqual(audit['completed_react_tools'], {'crawl_content': 1})
        self.assertEqual(model.judge_calls, 2)
        self.assertEqual(len(tools.calls), 2)
        self.assertFalse(tools.calls[-1]['screenshot'])

    def test_unfrozen_high_confidence_verdict_writes_real_store(self):
        audit, model, tools = self.run_case([], freeze=False)
        self.assertFalse(audit['memory_writes_frozen'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
