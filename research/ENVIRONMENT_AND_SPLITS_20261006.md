# 2026-10-06 接續結果與實驗準備

研究題目維持「MemoPhishAgent 記憶投票一致性與判決可靠性：補充取證的效果與成本分析」。本次沒有呼叫付費 API、沒有取得真實偵測結果，也沒有建立記憶快照。

## 移轉與驗證

來源 commit 為 `732648119f4de568cc13eab24c741645679e6958`，本地研究分支為 `research/memory-vote-audit-20261006`。

原始 patch 的四個檔尾空白行刪除區塊不適用於實際 checkout；排除這四個純空白區塊後 `git apply --check` 通過，功能修改全部保留。套用後的四個既有原始碼檔與 ZIP 的 final files 比對一致，僅檔尾空白不同。保留原版投票與提示詞，沒有加入 80%／100% 門檻或強制補查。

`python research/test_offline.py`：7/7 通過；在既有 Python 及專案 venv 都通過。這些測試以 AST／服務替身驗證邏輯，並非完整 Agent 整合測試。`synthetic_vote_examples.json` 是移轉包內的人工案例，不是實際分類結果。

## 執行環境

- 工作目錄：`/workspace/MemoPhishAgent`，不是使用者 Windows 電腦，沒有写入 C 槽。
- Python：3.12.14；venv：`/workspace/memophish-setup/venv`。
- 144 個已安裝套件的 `uv pip check` 通過；受測版本保存於 checkout 外的 `constraints.txt`。
- Docker daemon 可用，版本 28.4.0；本次未建置或驗證 Docker image。
- 系統 Chromium 151 渲染與截圖、FAISS 檢索、LangGraph InMemoryStore 讀寫驗證通過。
- 前一階段 Crawl4AI 0.9.4 透過系統 Chromium CDP 的原始 HTML 擷取／截圖通過，但結束時有 event-loop cleanup warning。
- Crawl4AI 快取需設 `CRAWL4_AI_BASE_DIRECTORY=/workspace/memophish-setup`，避免預設唯讀家目錄。
- 完整程式仍不可直接啟動：`tools.py` 匯入時就需要 SerpAPI 金鑰，因此 `graph.py --help` 也失敗。OpenAI／SerpAPI 所需變數目前未注入，設定草稿亦沒有已保存的憑證 binding。
- Playwright 預設 Chromium 尚未安裝；前次下載遭 `cdn.playwright.dev` 的 403 Domain forbidden。系統 Chromium 的獨立測試不能取代程式預設 browser 的驗證。
- 網路/API 需求及安裝指令已保存於環境設定草稿，草稿不代表已套用或發布。啟動指引已更新為禁止付費 API。`OPENAI_API_KEY` 是平台保留宣告名稱，使用 `MEMOPHISH_API_KEY` binding，再於執行時映射，不能把金鑰寫進 Git。

目前可進行離線研究開發；完整 Agent、真實 URL 可用性、LLM/search 與新任務還原尚未驗證。依使用者指示，補上憑證也不代表授權開始付費實驗。

## 資料稽核與候選切分

原始 CSV：753 筆、747 個不同 URL，多出 6 筆重複；1 個 URL 的歷史標籤互相衝突。隔離標籤衝突、短網址及 query_redacted 案件，共 84 個不同 URL（原因可能重疊），剩下 663 個候選 URL。

`research/prepare_splits.py` 不連網、不呼叫 API，使用 tldextract 內建 PSL（含 private suffix）按註冊網站分組；整組分配到記憶建構、驗證或測試，目標為 60/20/20。固定 seed 決定同尺寸組的順序，分配不讀取標籤。保守地將 google.com 下不同服務放在同組，避免以 URL 隨機切分造成明顯同網站洩漏，但會造成標籤不平衡。

| 清單 | URL 數 | 網站組數 | 歷史釣魚標籤 | 歷史正常標籤 |
|---|---:|---:|---:|---:|
| warmup | 398 | 95 | 306 | 92 |
| validation | 133 | 94 | 37 | 96 |
| test | 132 | 94 | 42 | 90 |

已產生的本地候選清單位於忽略的 `research/runs/splits-20261006/`，包含純 URL、獨立 label CSV、逐案 manifest、隔離清單、來源 SHA-256 與切分摘要。Git 只保存產生程式與本報告，不提交執行產物。重建：

```bash
cd /workspace/MemoPhishAgent
PYTHONDONTWRITEBYTECODE=1 /workspace/memophish-setup/venv/bin/python research/prepare_splits.py --output research/runs/splits-NEW
```

程式拒絕覆寫現有目錄。已驗證重建輸出逐位元組一致、URL 去重、跨組 URL／網站不相交、隔離案不進入清單。URL 清單不帶標籤；label CSV 只能提供給執行後分析程式，不能提供給 Agent。

**這是候選切分，不是正式可用資料。** 尚未檢查網站現況與現在的標籤、跨網域相同模板、重導向目的地、URL 別名；精確字串去重不能排除所有同頁面別名。短網址／遮蔽案先隔離不等於永遠排除；日後解析並確認現況後需重新分組、版本化清單。此候選子集亦不能代表完整 SocPhish 分布。

## 下一步順序

1. 在允許的網路下確認 URL 現況與標籤、辨識重導向和同模板群組，失敗案單獨記錄；更新候選切分，凍結正式 manifest。
2. 完成預設 Playwright browser 與所需憑證設定，但不自動呼叫付費 API。
3. 取得付費執行授權後，先以獨立 warmup 預熱；沿用高信心 Agent 判決寫入，ground truth 不作為輸入。快照載入重建 embeddings 也可能收費。
4. 固定模型／embedding、k=5、threshold=0.60，關閉 AI Overview，各組載入相同快照並凍結寫入；驗證集用於設計，測試集最後評估。
5. 先量測原版 3:2、4:1、5:0 的真實票數與錯誤，再研究門檻／補查。若樣本不足據實報告。逐案 tokens 尚為 null，解決並行 callback 歸屬後才能比較 token 成本。
