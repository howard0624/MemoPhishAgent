# Codex 完整交接：截至 2026-10-06（Asia/Taipei）

本文件將原對話中的已確認資訊寫入專案，讓下一個 Codex 不依賴聊天記錄即可接續。它取代舊版交接的狀態描述；其他文件可能保留早期「尚未安裝依賴／尚無切分」的歷史文字，請以此文件、Git 與實際檢查為準。

## 1. 使用者目前需要什麼

學長要求以書面形式報告兩週進度，可用投影片加下週預計進度，並找一篇相關論文。使用者已選 Adaptive-RAG，提供原文 PDF，正在用另一個 GPT 產生簡報；最後詢問候選切分投影片的數字出處。本次最新請求是「完整交接給其他 Codex，這段對話不在專案裡」。

優先接續簡報、講稿、出處及研究理解；不要擅自轉去大批次偵測。所有數字標註來源，不自行增加實驗結果或新研究設定。使用者可能貼其他模型產生的整理：前三篇候選清單是 Gemini 回覆，不是使用者自己的閱讀心得；請核對原文，不將貼上的文字當作已理解或已證實。

## 2. 固定研究方向及為何研究

題目：**MemoPhishAgent 記憶投票一致性與判決可靠性：補充取證的效果與成本分析**。

此題在移轉前已定案，本次沒有重新選題。先觀察 k=5、釣魚票在前的 3:2、4:1、5:0：相似舊案的多數決何時可信，何時需要調查當前網站，補查的效果與成本為何。

原版不是雙向多數決。至少 k 筆舊案達到相似度門檻，且釣魚票過半，才直接判釣魚；正常多數交給模型，不保證模型再呼叫工具。3:2、4:1、5:0 都可能走同一快速路徑，故先研究各組真實錯誤再設計補查。快速判決之前仍有爬取、關鍵詞摘要與檢索，不能說零成本。

票數比例不是準確率，也不是校準機率。沒有證據證明5:0一定可靠或3:2必須補查。不得任意換題、預設提高門檻有效、為增加分歧样本而降低相似度門檻。

## 3. 授權邊界與協作偏好

- 使用者明確要求「先不要執行付費 API」，目前沒有後續付費授權。
- 不執行真實 LLM、SerpAPI、embedding、記憶預熱或快照載入；後兩者也可能收費。補齊憑證不等於授權執行。
- 不索取聊天中的金鑰，不印環境變數值、不提交 .env 或憑證。
- 本地是雲端 /workspace，不是使用者Windows電腦；不要承諾写入 `C:\Chat GPT專案輸出內容`。
- 一律繁體中文，白話、具體。每次說明目的、修改、證據與限制。
- 使用者希望參與實作或看到詳細報告，讓他知道如何報告。希望提升程式寫作能力，不只是自動化代做。
- 已選「逐行看離線整合測試，練習執行與修改」。曾正確將人工labels改成4:1並修改vote_group，但把decision_route誤填4:1，不理解字典欄位、路徑字串、judge_calls。應先解釋概念及既有程式，再提問，不要求憑空猜名稱。
- 現階段程式教學已暫停，先做報告。4:1／5:0練習尚未實際加入測試，不計入通過數。
- 使用現有checkout，不自行建立worktree。研究修改已授權並推送研究分支；不要合併main或改既定研究方法而不說明。

## 4. 儲存庫與版本

- 個人儲存庫：https://github.com/howard0624/MemoPhishAgent
- 上游：https://github.com/XuanChen-xc/MemoPhishAgent
- 原版commit：`732648119f4de568cc13eab24c741645679e6958`
- 研究分支：`research/memory-vote-audit-20261006`
- `31cd5fd`：套用研究audit／snapshot修改，新增候選切分與環境報告。
- `1a77054`：實際LangGraph離線整合測試、切分測試、教學與進度文件。
- 以上已推送；本次交接文件將另提交並推送。尚未合併main、未建立PR。
- 移轉包patch最初因四個檔尾空白刪除hunk無法套用；僅排除這四個hunk，全部功能修改保留。四個既有源碼與附件final files比對只差EOF空白。

## 5. 已完成的研究功能

- `agent/src/memory_audit.py`：同次檢索的只讀投票診斷，不重查、不呼叫LLM。
- `memory.py`：候選ID／URL／相似度、接受條件、票數、判決路徑；快照輸入／輸出、雜湊、凍結寫入。
- `state.py`：逐案memory_audit欄位。
- `agent_helpers.py`：判決輸出及audit JSONL、完成的ReAct工具數、時間、失敗狀態。
- `graph.py`：新增 `--memory-audit-output`、`--memory-snapshot-in`、`--memory-snapshot-out`、`--freeze-memory-writes`。
- `research/evaluate_votes.py`：推論後才合併 `url,label` CSV，標籤不可給Agent。
- 原版判決規則與提示詞保持不變。尚未加入80%／100%門檻、強制補查、Gemini provider或交接提到的既有tool_sequence修正。
- InMemoryStore是記憶儲存；快照不是向量快照，載入會重建embeddings。各實驗應同快照、凍結寫入、固定模型與檢索條件。
- 逐案tokens為null；共用並行callback無法可靠分配。elapsed_seconds包含並行排隊；工具回傳錯誤也可能計入完成次數，不等於取證成功。
- `demo_votes.py`、`synthetic_vote_examples.json`為人工測試，不是真實偵測或ground truth。

## 6. 已執行的驗證與限制

共16項，全部通過：

| 測試 | 數量 | 證據範圍 |
|---|---:|---|
| `research/test_offline.py` | 7 | AST載入實際類別，替換服務，檢查投票、邊界、快照、凍結、輸出與標籤隔離 |
| `research/test_graph_offline.py` | 4 | 實際LangGraph編譯／狀態更新／ToolNode／InMemoryStore；模型、爬取、搜尋、embedding替身，socket連線被阻止 |
| `research/test_splits_offline.py` | 5 | 去重、隔離、網站分組、標籤不決定分配、重建一致、不覆寫、private suffix |

四項graph案例：3:2快速判釣魚（後續judge=0、初始crawl及摘要各1）、2:3交模型且可不補查、無舊案實際ToolNode追加crawl並正確計數、未凍結時高信心人工判決寫入真實store。

修正prepare_splits.py的CSV未明確關閉ResourceWarning，重跑五項通過。框架有 `StateGraph(input=...)` 棄用提示，現版本可執行，未改框架寫法。

這是邏輯及框架整合證據，不是真實外部服務驗證。人工embedding把所有文字映射同向量，不能據此評估真實檢索品質。不要宣稱真實分類效果。

## 7. 環境與重啟注意

當時Python 3.12.14；venv `/workspace/memophish-setup/venv`，144個已裝套件相容性檢查通過，checkout外有constraints.txt。Docker daemon 28.4.0可用，未build／驗證Docker image。

系統Chromium151渲染／截圖、FAISS與LangGraph store測試通過；Crawl4AI0.9.4透過系統Chromium CDP擷取HTML與截圖通過，結束有event-loop cleanup warning。

Crawl4AI預設寫唯讀家目錄，須設定：

```bash
export CRAWL4_AI_BASE_DIRECTORY=/workspace/memophish-setup
export PLAYWRIGHT_BROWSERS_PATH=/workspace/memophish-setup/browsers
export UV_CACHE_DIR=/workspace/memophish-setup/uv-cache
export PYTHONDONTWRITEBYTECODE=1
```

完整Agent仍未就緒：tools.py匯入時需要SerpAPI金鑰，graph.py --help也被阻擋；憑證未注入。預設Playwright Chromium下載曾遭cdn.playwright.dev的403 Domain forbidden。系統Chromium獨立測試不能取代主程式預設browser驗證。

雲端設定草稿已保存install_script/start_skill及網路需求：cdn.playwright.dev、storage.googleapis.com、playwright.download.prss.microsoft.com、cdn.jsdelivr.net、api.openai.com、serpapi.com。已宣告MEMOPHISH_API_KEY與SERPAPI_API_KEY需求，但沒有已保存credential binding。平台保留OPENAI_API_KEY宣告名，日後若得到執行授權，在process映射MEMOPHISH_API_KEY給OPENAI_API_KEY，不輸出值。草稿保存不表示套用／發布；新環境重新確認現況，不憑本文件假設可用。

離線重跑（此路徑若不在新機器，先安裝依賴並使用新venv；不要假設舊venv會跟Git還原）：

```bash
cd /workspace/MemoPhishAgent
PYTHONDONTWRITEBYTECODE=1 /workspace/memophish-setup/venv/bin/python research/test_offline.py
PYTHONDONTWRITEBYTECODE=1 /workspace/memophish-setup/venv/bin/python research/test_graph_offline.py
PYTHONDONTWRITEBYTECODE=1 /workspace/memophish-setup/venv/bin/python research/test_splits_offline.py
```

不需要APIkey；graph測試須獨立Python程序執行。環境快照發布、新任務還原未獨立驗證。

## 8. 資料數字、切分規則及出處

資料來源：`data/socphish/socphish_public.csv`。753筆、747個不同URL，六筆額外重複；一個URL存在衝突標籤。隔離衝突、短網址、query_redacted，合計84個不同URL，剩663。

按tldextract內建PSL（含private suffix）註冊網站整組分配，固定seed=`memophish-v1`，目標60/20/20；按组尺寸及seed排序分配，不利用標籤決定組別。URL是精確字串去重。google.com不同服務保守放同組，類別比例不平衡。

| 用途 | URL | 网站组 | 歷史釣魚 | 歷史正常 |
|---|---:|---:|---:|---:|
| warmup | 398 | 95 | 306 | 92 |
| validation | 133 | 94 | 37 | 96 |
| test | 132 | 94 | 42 | 90 |

來源CSV SHA256：`af5917bf3c59056d28bc4e0566613e02256441b3c1cff27642125d64e50aa8ac`。

本次交接保留 `research/handoff_artifacts/candidate_split_manifest_20261006.json`，不依賴忽略的runs資料夾。重建：

```bash
python research/prepare_splits.py --output research/runs/splits-NEW
```

輸出目錄必須不存在；URL清單、labels CSV、逐案manifest、隔離清單分開保存。跨組URL／網站不交叉已驗證，但現在網站標籤、重導向、跨網域模板、URL別名尚未檢查。這是本研究候選切分，不是原作者正式切分；不代表完全排除資料洩漏或可代表完整SocPhish分布。

投影片出處建議：

> 資料來源：MemoPhishAgent公開SocPhish CSV；數字為本研究於2026/10/06執行資料稽核及候選切分程式所得，非原作者正式切分。

連結：
- 原始CSV：https://github.com/howard0624/MemoPhishAgent/blob/main/data/socphish/socphish_public.csv
- 本研究程式：https://github.com/howard0624/MemoPhishAgent/blob/research/memory-vote-audit-20261006/research/prepare_splits.py
- 報告：同分支 `research/ENVIRONMENT_AND_SPLITS_20261006.md`。

## 9. Adaptive-RAG：為何選、方法與證據

正式題名：**Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity**。
中文：Adaptive-RAG：透過問題複雜度學習調整檢索增強型大型語言模型。
作者Soyeong Jeong、Jinheon Baek、Sukmin Cho、Sung Ju Hwang、Jong C. Park。
NAACL2024 Volume1 Long Papers，7036–7050。
https://aclanthology.org/2024.naacl-long.389/
https://doi.org/10.18653/v1/2024.naacl-long.389

選篇理由：同樣研究何時需更多資訊；三種取證程度直觀；同時比較效果與效率，可借鏡策略分流／成本評估。不是因它證明票數有效。

原文方法：分類器（主設定T5-Large）依問題預測A不檢索、B單步、C多步；以不同策略是否答對建標籤，優先簡單策略，皆錯則依single-hop/multi-hop資料特性補標。不是投票門檻，也不是僅依主觀難度。

六QA資料集：SQuAD、Natural Questions、TriviaQA、MuSiQue、HotpotQA、2WikiMultiHopQA。模型FLAN-T5-XL/XXL、GPT-3.5-Turbo-Instruct，BM25檢索。

Table1，GPT-3.5設定，六資料集平均：

| 方法 | QA F1 | QA Acc | Step | 相對Time |
|---|---:|---:|---:|---:|
| No Retrieval | 48.56 | 44.27 | 0.00 | 0.71 |
| Single-step | 46.99 | 45.27 | 1.00 | 1.00 |
| Adaptive-RAG | 50.91 | 48.97 | 1.03 | 1.46 |
| Multi-step | 50.87 | 49.70 | 2.81 | 3.33 |

F1接近多步、步數時間較低；Acc略低，且不是比所有方法更快。Time為以單步=1的倍率，不是秒；Step是retrieval-and-generate，不等於供應商API請求數。QA F1為詞重疊，QA Acc是答案包含ground truth，非釣魚分類指標。不能把時間步數降幅當成tokens／費用降幅。

限制：自動標籤與分類器會出錯，Oracle有改善空間。Table4的54.52%分類器Accuracy是FLAN-T5-XL相關設定，不能混同GPT3.5 QA Acc。

頁碼：Figure2=PDF2；§3.2=PDF5；Table1/§4.3=PDF6；Limitations=PDF9。完整已核對導讀：`research/Adaptive-RAG_論文導讀與簡報素材.md`。

關聯：本研究要驗證投票一致性是否能當取證決策訊號；論文用問題複雜度，不是舊案票數。5:0=簡單、3:2=複雜、高共識=可靠皆未證明。Adaptive-RAG不檢索也不同於本Agent有初始crawl的快速路徑。

Gemini其他候選有書目錯誤，已核對官方資料庫：
- ACL2025.319正式標題 `Adaptive Retrieval Without Self-Knowledge? Bringing Uncertainty Back Home`，Viktor Moskvoretskii et al.；比較35方法、6資料集、10指標，不宜簡化成一個新門檻方法。
- Findings2024.675為 `When Do LLMs Need Retrieval Augmentation? Mitigating LLMs’ Overconfidence Helps Retrieval Augmentation`，Shiyu Ni et al.，不是Shi-Qi Yan。

原文由使用者上傳；未將全文PDF放入Git。公開官方PDF可由上述Anthology取得。當時直接Anthology請求曾被403阻擋，書目先從官方GitHub XML核對，後續實際讀上傳PDF確認方法／Table1，不再僅依摘要。

## 10. 簡報與檔案可攜性

Google Slides：https://docs.google.com/presentation/d/1AJR7nC7CjhkDAnJLEmMr2aAvq5m1kJdqahlKs3t6tyo/edit

最初401，分享更新後export/txt與pptx可讀。對話沒有Google Slides編輯工具，**未修改線上原檔**。使用者已表示交給另一個GPT生簡報，本地PPTX是参考版本，不保證等於最新線上內容。

本次交接已將原八頁export與更新十頁PPTX保存進 `research/handoff_artifacts/`。更新版沿用原版型，在第三頁後加兩頁Adaptive-RAG方法／結果／關聯，更新下週計畫與講稿。驗證10頁、數值與PPTX archive，未在PowerPoint/Google視覺渲染檢查；匯入後檢查字型換行。

其他文件：
- `research/PROGRESS_AND_WALKTHROUGH_20261006.md`：完成事項、真實/替身區分、可報告用語。
- `research/INTEGRATION_TEST_TUTORIAL_繁體中文.md`：逐行解釋3:2測試與4:1/5:0未執行練習。
- `research/ENVIRONMENT_AND_SPLITS_20261006.md`：環境與資料細節。
- `research/README_研究紀錄.md`、provenance.json：保留移轉時历史資訊，不當最新驗證狀態。

不要依賴 /workspace/research-reports、附件、venv、runs會出現在另一個機器；必要報告、簡報與切分摘要已移入Git，清單由程式重建，原文由官方來源取得。

## 11. 下一步及不能宣稱的成果

目前無真實偵測、無真實記憶快照、無Precision/Recall/F1/Accuracy結果、無成本改善證據、無付費授權。

先服務報告需要：核對出處、完善簡報與講稿，區分原版、軟體驗證、本研究假設、相關論文。

之後研究順序：
1. 確認網站現況與標籤、重導向、同模板；失敗單獨記錄，完成正式manifest。
2. 完成環境及憑證，但不自動執行付費API。
3. 與使用者確認小批次、模型及預算，獲授權後warmup，不把ground truth提供給Agent。
4. 固定模型／embedding、k=5、threshold=.60、關閉AI Overview，使用同快照並凍結寫入。
5. 先量測原版3:2/4:1/5:0分布与錯誤，再設計補查／門檻，解決逐案tokens歸屬後報成本。

快速判釣魚組錯誤比例FP/(TP+FP)不同於整體正常網站誤報率FP/(FP+TN)。样本少時不下強結論，後續配對比較與不確定性估計尚未實作。

下一個Codex開始時，先讀本文件、確認branch與git status，再問使用者目前簡報/研究/教學的優先需求；不要重跑付費步驟、擅自更換題目，或把歷史候選方案描述為完成的研究成果。
