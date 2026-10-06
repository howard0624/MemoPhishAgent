# Codex 接續工作

## 固定研究問題

MemoPhishAgent 記憶投票一致性與判決可靠性：補充取證的效果與成本分析。

研究相似舊案的多數決何時可信、何時應調查當前網站。先分析 k=5 時釣魚票在前的 3:2、4:1、5:0，不把票數比例當成正確機率，不預設提高門檻有效，也不要自行換題目。

## 已完成

- 原版來源 commit：732648119f4de568cc13eab24c741645679e6958。
- GitHub 個人儲存庫：https://github.com/howard0624/MemoPhishAgent。
- `memory.py` 增加只讀投票診斷；`state.py` 保存逐案 audit；`agent_helpers.py` 輸出 JSONL。
- `graph.py` 新增 `--memory-audit-output`、`--memory-snapshot-in`、`--memory-snapshot-out`、`--freeze-memory-writes`。
- 原版判決與提示詞保持不變。只有足夠達標舊案且釣魚票過半，才直接判釣魚。正常多數交由 LLM，並不保證呼叫工具。
- 記憶是 InMemoryStore；快照保存記憶紀錄，重載需要重建 embeddings，可能收費。
- `research/evaluate_votes.py` 執行後才合併 CSV 的 url,label；標籤不可給 Agent。
- `research/test_offline.py` 七項離線測試通過，使用 AST 與外部服務替身；它不是完整 LangGraph 整合測試。
- `research/demo_votes.py`／`synthetic_vote_examples.json` 只是人工軟體案例，不能報為偵測效果。

## 實際尚未完成

- 尚未安裝／驗證完整 Agent 的執行依賴，未執行真實網站偵測，也未呼叫付費 API。
- 尚未加入 80%／100% 門檻與強制補查。
- 逐案 tokens 暫為 null，共用並行 callback 的總用量不能可靠分配；需要先解決追蹤歸屬再比較成本。
- 未整合使用者電腦上先前 Gemini provider 與 tool_sequence 修正。不要假設已存在。
- 尚無記憶建構／驗證／測試切分。公開 URL 可能失效；要驗證現況與標籤，記錄失敗，不把失敗當正常。
- 網址去重並分離同網站／模板，避免洩漏。對各组載入同一記憶快照、凍結寫入、固定模型與檢索設定。
- 3:2 等樣本可能很少；若不足據實報告，不為製造分歧而任意改相似度門檻。

## 下一步

1. 閱讀 `research/README_研究紀錄.md`，執行免費離線檢查。
2. 檢查此 Codex 任務的實際工作目錄、Python／Docker 與網路權限；不要在未確認權限時承諾能写入任意 C 槽路徑。
3. 檢查並建立完整執行環境；API key 留在環境變數或未追蹤的 `.env`，不貼出、不提交。
4. 整理獨立記憶建構與測試清單，預熱保存快照。
5. 以固定快照先跑原版小批次，產出真實票數分布與各組錯誤率；不要預先宣稱研究假設已成立。
6. 後續再設計補查與門檻實驗，量測 Precision、Recall、F1、快速路徑比例、工具、時間與 tokens。

## 協作偏好

全部使用繁體中文。教學先概念與流程，再解釋程式；白話、具體例子、一步一步。程式工作每次說明修改目的、驗證結果與限制。使用者偏好輸出資料夾 `C:\Chat GPT專案輸出內容`；此路徑尚未在原對話取得權限。研究方向已定案，新增觀察先記錄，不任意改題。

原對話生成了來源快照與下載 ZIP；此次 GitHub 移轉以個人 Fork 的完整原版 tree 為基礎，因此保留其其他檔案與來源歷史。
