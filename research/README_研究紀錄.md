# Memory 投票研究：第一階段

固定題目：**MemoPhishAgent 記憶投票一致性與判決可靠性：補充取證的效果與成本分析**。

研究問題：相似舊案的多數決，什麼時候值得相信、什麼時候應重新調查？

## 目前完成什麼

已建立公開程式的研究版本，加入投票與判決路徑紀錄、記憶快照載入／保存與凍結寫入選項，以及執行後合併真實標籤的分析程式。

本階段保留原版投票規則與提示詞，尚未加入 80%／100% 門檻或強制補查。離線檢查只能證明軟體邏輯與紀錄功能，不代表偵測效能改善。

來源：https://github.com/XuanChen-xc/MemoPhishAgent

固定上游 commit：`732648119f4de568cc13eab24c741645679e6958`。

此目錄是從 GitHub 連接器取得的文字來源快照，建立了本地 Git 基準。不是完整 git clone；包含所有 agent 原始碼、執行設定及公開 SocPhish CSV，省略圖片與其他重複資料格式。未整合使用者電腦上先前新增的 Gemini 支援或工具軌跡修正。原本 `sources/` 未修改。

## 一個案件的紀錄

`memory.py` 在同一次檢索結果上建立紀錄，不額外重新檢索：

| 欄位 | 內容 |
|---|---|
| `candidates` | 所有 Top-k 候選案 ID、URL、相似度、舊判決與是否達標 |
| `accepted_memory_ids` | 真正參與投票的舊案 ID |
| `vote_distribution` | 釣魚／正常票數 |
| `vote_group` | 例如 `3:2`，固定釣魚票在前 |
| `original_fast_malicious` | 是否符合原版直接判釣魚條件 |
| `decision_route` | `fast_malicious`、`memory_guided_llm` 或 `no_match_llm` |
| `original_verdict` | 本次原版最終判決 |
| `completed_react_tools` | 後续 ReAct 中已回傳結果的工具數，含回傳錯誤的工具 |
| `initial_crawl_calls` | Memory 準備階段另有一次網站爬取；不包含在 ReAct 工具數中 |
| `elapsed_seconds` | 逐案經過時間，包含並行排隊；不是整批平均延遲 |
| `snapshot_sha256` | 載入快照的雜湊，供確認各組從同一記憶開始 |
| `tokens_used` | 暫為 `null`：原版共用 callback 的總量不能可靠拆分到並行案件 |

票數比例不是校準過的正確機率。`memory_guided_llm` 不代表一定呼叫工具。原版的快速判決也包含前面的頁面爬取與關鍵詞摘要，不能宣稱完全零成本。

失敗案件另標 `processing_failed`／`parse_failed`，不算成正常或釣魚；處理失敗時可能沒有完整中間檢索紀錄。AI Overview 捷徑標成 `ai_overview_bypass`，研究執行時關閉它。

## 現在可以執行的免費檢查

在研究版本根目錄執行：

```powershell
python research/test_offline.py
python research/demo_votes.py
```

測試用 AST 載入實際類別，替換外部服務，並與隨附的 `upstream_memory.py.txt` 原版函式比較，解壓後不需要 Git 歷史也能檢查。覆蓋 k=1、4、5 的所有標籤組合、相似度門檻邊界、快速判決、fallback、日誌輸出、快照分頁及凍結寫入。

`synthetic_vote_examples.json` 是人工案例的軟體檢查，沒有真實網站或 ground truth，不能拿來報告 Accuracy、Recall 或改善成效。

## 真實實驗前的必要準備

1. 使用具備原版依賴的 Python／Docker 執行環境，設定 API。此工作環境尚無 LangGraph、LangChain、Crawl4AI，未做完整 Agent 整合測試，沒有呼叫付費 API。
2. 整理並驗證可用網站及標籤；過期、轉址或內容已改的 URL 要另記錄，不能直接沿用歷史答案。
3. 把記憶建構資料、驗證資料、測試資料分開。去除重複 URL，盡量按同網域／同模板分組，避免洩漏。公開 CSV 有重複網址，分析程式會拒絕重複測試 URL。
4. 記憶預熱用 Agent 的原版高信心判決寫入，不把 ground truth 當成模型輸入。若另建人工驗證的乾淨記憶，要標為不同實驗設定。
5. 固定模型、embedding、k、相似度門檻與資料順序。快照載入會重建 embeddings，可能產生 API 費用；不是向量快照。

以下只是已準備好的操作命令，尚未執行。`warmup_urls.txt` 與 `test_urls.txt` 必須先依上述規則建立。

預熱並保存記憶（在 `agent/` 目錄執行；沿用原版並行行為，記錄資料順序和實際快照）：

```powershell
python src/graph.py --agent full_agent --provider openai --input ../research/warmup_urls.txt --output ../research/runs/warmup.json --use-ai-overview false --memory-audit-output ../research/runs/warmup_audit.jsonl --memory-snapshot-out ../research/snapshots/warmup.json
```

評估原版，載入相同記憶並停止新增：

```powershell
python src/graph.py --agent full_agent --provider openai --input ../research/test_urls.txt --output ../research/runs/baseline.json --use-ai-overview false --memory-audit-output ../research/runs/baseline_audit.jsonl --memory-snapshot-in ../research/snapshots/warmup.json --freeze-memory-writes -k 5 --threshold 0.60
```

快照輸入／輸出須用不同檔案，避免覆蓋基準。

執行後才合併標籤（回到研究版本根目錄）：

```powershell
python research/evaluate_votes.py --audit research/runs/baseline_audit.jsonl --labels research/test_labels.csv --output research/runs/baseline_summary.json
```

標籤 CSV 只有 `url,label`，label 使用 `malicious` 或 `benign`。它不會提供給 Agent。分析輸出整體 Precision、Recall、F1、失敗／缺標籤數、快速判決比例、各票數組案件數及錯誤率。

特別注意：快速判釣魚組的「錯誤比例」是 FP/(TP+FP)，不是全體正常網站的誤報率 FP/(FP+TN)。小樣本不能下強結論，後續正式比較需要不確定性估計與同批案件的配對分析。

## 下一步固定範圍

先取得原版 3:2、4:1、5:0 的真實分布。若 Full match 或分歧案件稀少，據實報告樣本不足，不刻意降低相似度門檻來製造結果。再設計一致性門檻及明確的額外取證流程，評估效果與成本；題目不變。
