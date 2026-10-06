# 一起讀離線整合測試

本導讀對應 `research/test_graph_offline.py`。先理解一個案例，再看共用流程；不必一次背完整個框架。這是軟體整合練習，沒有真實網站或偵測成效。

## 第一步：只執行一個案例

在雲端環境終端執行：

```bash
cd /workspace/MemoPhishAgent
PYTHONDONTWRITEBYTECODE=1 /workspace/memophish-setup/venv/bin/python research/test_graph_offline.py GraphOfflineTests.test_fast_malicious_3_2_freezes_real_store
```

應看到 `Ran 1 test` 和 `OK`。輸出的 URL 與判決是人工測試資料。LangGraph 的 `input` 棄用提示可能出現，現版本測試仍通過。

## 第二步：逐行讀 3:2 案例

```python
def test_fast_malicious_3_2_freezes_real_store(self):
    audit, model, tools = self.run_case([True, True, True, False, False])
    self.assertEqual(audit['vote_group'], '3:2')
    self.assertEqual(audit['decision_route'], 'fast_malicious')
    self.assertTrue(audit['original_verdict'])
    self.assertEqual(model.judge_calls, 0)
    self.assertEqual(audit['completed_react_tool_count'], 0)
    self.assertEqual(len(tools.calls), 1)
```

| 程式 | 白話意思 | 若失敗代表什麼 |
|---|---|---|
| `def test_...` | unittest 會自動執行以 test 開頭的方法 | 測試名稱或執行入口可能不正確 |
| `self.run_case([...])` | 準備三筆釣魚、兩筆正常舊案，走一次實際 graph；回傳紀錄與替身的呼叫數 | 共用流程或框架整合可能失敗 |
| `vote_group == '3:2'` | 確認釣魚票在前，票數紀錄正確 | 記錄或檢索接受條件可能有問題 |
| `decision_route == 'fast_malicious'` | 確認走原版快速判釣魚路徑 | 條件或狀態傳遞可能與預期不同 |
| `assertTrue(original_verdict)` | 確認這個人工案例的輸出是釣魚 | 最終判決或 JSONL 映射可能不同 |
| `judge_calls == 0` | 沒有再呼叫後續判決模型 | 快速路徑可能未跳過後續判決 |
| `completed_react_tool_count == 0` | 沒有在後續 ReAct 階段追加工具 | 工具紀錄或流程可能不同 |
| `len(tools.calls) == 1` | 仍有一次記憶準備階段的初始爬取 | 初始取證缺失或有額外爬取 |

`True` 表示舊案判決是釣魚，`False` 表示正常。它們不是待判定 URL 的真實標籤。所有 embedding 替身回傳相同向量，讓這五筆人工舊案確定能參與投票。

`judge_calls == 0` 不代表完全沒有模型工作。共用流程另檢查 `summary_calls == 1`，表示關鍵詞摘要仍被呼叫一次；正式執行時它也可能收費。

## 第三步：看看 run_case 做了什麼

依程式中的順序閱讀：

1. `TemporaryDirectory`：在 `/tmp` 建立測試資料夾，結束後自動刪除。
2. `snapshot.write_text(...)`：建立人工記憶快照，每筆有 ID、URL、keywords、verdict、trace。
3. `SimpleNamespace(...)`：模擬 CLI 參數，關閉 AI Overview，開啟記憶，指定測試 JSON 與 audit JSONL。
4. `OfflineModel`：固定回應並計算摘要／判決呼叫數，不呼叫 OpenAI。
5. `make_store`：仍建立真正的 `AgenticMemorySystem` 和 `InMemoryStore`，只是把實例留下來供檢查。
6. `make_tools`：建立具有真實 StructuredTool 介面的人工工具，記錄呼叫，回傳固定內容。
7. `patch(socket...)`：任何受此區塊控制的 socket 連線會拋錯，避免測試意外連網。
8. `patch(get_llm...)`：替換模型建立入口。`provider='openai'` 在本測試是流程參數，不會啟動真實 OpenAI 請求。
9. `patch(get_memory_embeddings...)`：替換 embedding，避免快照載入重建向量時收費。
10. `build_full_agent(...)`：實際建立並編譯專案的 LangGraph，固定 k=5、threshold=0.6。
11. `compiled.ainvoke(...)`：執行 graph；`asyncio.run` 將非同步入口接到同步測試。
12. 讀出結果與 audit：檢查沒有失敗案、雜湊一致、初始 crawl 與摘要各一次、tokens 未被誤填成真實用量。
13. 記憶筆數檢查：凍結時應保持原筆數；未凍結的高信心人工判決會新增一筆。

這裡的「真正」是指程式和框架類別真的執行，外部模型與網站服務則是替身。因此可以報告框架整合通過，但不能報告真實模型判斷或外部服務已驗證。

## 第四步：你的第一個修改練習

在 `GraphOfflineTests` 類別內、其他 `test_...` 方法旁新增下面這個方法。這段目前是教學範例，尚未加入測試檔或列入通過數；你實作後測試总數才會增加。

```python
def test_fast_malicious_4_1(self):
    audit, model, tools = self.run_case([True, True, True, True, False])
    self.assertEqual(audit['vote_group'], '4:1')
    self.assertEqual(audit['decision_route'], 'fast_malicious')
    self.assertTrue(audit['original_verdict'])
    self.assertEqual(model.judge_calls, 0)
    self.assertEqual(audit['completed_react_tool_count'], 0)
    self.assertEqual(len(tools.calls), 1)
```

先預測：它會有幾次判決模型呼叫？是否有初始爬取？記憶是否增加？再執行：

```bash
PYTHONDONTWRITEBYTECODE=1 /workspace/memophish-setup/venv/bin/python research/test_graph_offline.py GraphOfflineTests.test_fast_malicious_4_1
```

若通過，接著自行建立 5:0 案例，把 labels 改為五個 True，把 `vote_group` 的預期改為 `5:0`。

你也可以刻意把預期票數寫错，觀察 AssertionError，再改回來。這能理解測試如何發現問題。不要為了讓測試通過而改主程式投票門檻；本練習只更換人工輸入與預期。

## 第五步：如何報告這次練習

可以說：「我新增了 4:1／5:0 的人工整合案例，確認它們維持原版快速判決流程，並檢查工具與模型呼叫數。」

不能說：「4:1 代表 80% 準確，5:0 代表 100% 準確。」票數比例與真實準確率是不同的量，需要真實標籤與實驗才能估計。

若目前沒有可操作的終端或編輯器，不需要先安裝 Windows 或填 API key。可以先把新增方法貼回對話，我會幫你檢查、放到研究分支並執行，再一起解讀結果。
