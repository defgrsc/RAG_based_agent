# 自動探索校園資訊 Agent Bug

這是一套 local-first、scenario-based 的多輪 Agent 測試系統。它不要求人工寫完整 conversation，也不修改正常 Agent 回答流程。

## 現有架構與掛接點

目前 production 資料流：

```text
User / frontend
  → POST /chat（message + client-managed history + session_id）
  → LangGraph resolve_context
  → classify_intent
  → select_history
  → clarification / scope guard / fast answer / answer cache
  → 或 LangGraph retrieve（query rewrite → Qdrant → rerank）
  → generate（現有自架 LLM）
  → answer + sources
```

LangGraph state 原生欄位包含 topic、intent、intent source、relation、reference status、referenced turn ids、relevant history、retrieval query、retrieved docs 與 answer。production graph 的 `classify_intent` 會在選 history 前區分 application、troubleshooting、configuration、lookup 等意圖；qualifier 目前仍由 evaluation observer 從實際 standalone query 衍生。

既有 testing infrastructure：

- `tests/test_agent_graph.py`：LangGraph context isolation、topic override、retrieval filter 的 unit/regression tests。
- `test_reports/`：人工對話與回歸報告。
- `training_data/`：已知 QA、拒答、clarification 與 failure rewrite 資料。
- 導入本系統前沒有 DeepEval、Promptfoo 或 Phoenix。Promptfoo 目前保留 reviewed-failure export interface，沒有取代現有測試。

掛接點是 DeepEval `ConversationSimulator.model_callback` → 真實 `main.chat(ChatRequest)`。in-process adapter 呼叫的就是 FastAPI handler，所有 LangGraph、RAG、Qdrant、fast answer、cache 與 LLM 都是真實元件，沒有 mock。另有 `http` adapter 可打已啟動的 `/chat`。

## 安裝

在 repository 根目錄：

```bash
./venv/bin/pip install -r evals/requirements.txt
```

固定使用 `deepeval==4.1.10`。預設設定 `DEEPEVAL_TELEMETRY_OPT_OUT=1` 且 `CONFIDENT_TRACING_ENABLED=NO`，不需 Confident AI 帳號或付費 cloud。

## Simulator / evaluator model

預設 `openai_compatible` 直接沿用專案：

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`（本機端點若不驗證，可使用任意 local placeholder）
- `MODEL_NAME`

本機目前會使用與 Agent 相同的 self-hosted model。模型 wrapper 實作 DeepEval `DeepEvalBaseLLM` 並支援 Pydantic structured output。

若改用 Ollama，在 `evals/config.yaml` 將 provider 改成 `ollama`，並設定：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen3:8b
```

simulator 與 evaluator 設定分開，可替換成不同模型。沒有 simulator LLM 時，可用 `--simulator template` 驗證整條 pipeline；正式 exploratory run 建議使用 DeepEval。

## 先看 model call 預算

```bash
./venv/bin/python -m evals.bug_discovery.cli estimate --profile SMOKE
./venv/bin/python -m evals.bug_discovery.cli estimate --profile STANDARD
./venv/bin/python -m evals.bug_discovery.cli estimate --profile COLLOQUIAL
./venv/bin/python -m evals.bug_discovery.cli estimate --profile STRESS
```

估算拆成 simulator calls、Agent turns / 最大 Agent LLM calls、evaluator calls。數量都由 `evals/config.yaml` 控制，可用 `--max-conversations`、`--repeat` 再限制。

## 啟動 Agent

in-process adapter 不需另開 uvicorn。完整 RAG 驗證仍需要 Qdrant、embedding 與
LLM endpoint 可用；embedding 暫時失敗時，chat 會改走有官方來源的安全 fallback。
若使用 HTTP adapter：

```bash
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
./venv/bin/python -m evals.bug_discovery.cli run --profile SMOKE --adapter http
```

## 依賴健康檢查

`GET /health` 是不呼叫外部服務的輕量 liveness check。需要確認真實 RAG 依賴時，使用：

```bash
curl -sS http://127.0.0.1:8000/health/dependencies
```

`/health/dependencies` 會並行實測：

- embedding：送出一筆最小 embedding 請求，驗證模型及回傳向量。
- Qdrant：讀取目前 active collection，並回報 point 數量。
- LLM：讀取 OpenAI-compatible model list，確認設定的 model 存在。

三項皆正常時回傳 HTTP 200 與 `status: ready`；任一項失敗時回傳 HTTP 503 與
`status: degraded`。失敗結果會區分 `timeout`、`authentication`、
`connection`、`rate_limit`、`http_error`、`invalid_response`，且不會把
底層 endpoint、憑證或原始例外文字回傳給前端。

可調整探測及 embedding timeout：

```bash
export DEPENDENCY_HEALTH_TIMEOUT_SECONDS=5
export EMBEDDING_REQUEST_TIMEOUT_SECONDS=3
export EMBEDDING_CIRCUIT_BREAKER_SECONDS=30
```

embedding 請求不做 SDK retry；第一次 timeout 後會在 circuit-breaker 期間快速
返回，避免每個問句重複等待。若 chat 的 embedding 暫時失敗，會回傳 HTTP 200
及不含內部服務名稱、model 或 URL 的安全回答，route 記為
`embedding_fallback`。健康檢查仍會繞過 circuit breaker 實測 embedding，
因此可以偵測服務恢復。

Qdrant 或 LLM 故障時，`/chat` 仍以 HTTP 503 回傳通用訊息；
eval adapter 會將這些錯誤記為 `DEPENDENCY_UNAVAILABLE`，與
`ANSWER_GENERATION_ERROR`、`UNKNOWN` 分開，且不會加入 Agent regression
candidate 清單。

## 執行

```bash
# 5 categories、小量 conversation
./venv/bin/python -m evals.bug_discovery.cli run --profile SMOKE

# 全部 categories（含口語未見案例）、每個 exact input 重播多次
./venv/bin/python -m evals.bug_discovery.cli run --profile STANDARD

# 6 個口語情境；template 模式每個情境重播 3 次，不需要 simulator LLM
./venv/bin/python -m evals.bug_discovery.cli run --profile COLLOQUIAL --simulator template

# 由 DeepEval 即時產生尚未寫死的新口語說法
./venv/bin/python -m evals.bug_discovery.cli run --profile COLLOQUIAL --simulator deepeval --repeat 1

# 大量探索；先 estimate
./venv/bin/python -m evals.bug_discovery.cli run --profile STRESS

# 對同一批自動生成的 user messages 做 10 次獨立 session replay
./venv/bin/python -m evals.bug_discovery.cli run --profile SMOKE --repeat 10
```

`--evaluator deterministic` 可停用 semantic judge。系統永遠優先檢查 deterministic intermediate state；只有 deterministic 通過時，hybrid mode 才花一次 evaluator call 檢查語意答案。

## Scenario 定義

Scenario 在 `evals/scenarios/*.yaml`。每個 scenario 只定義：

- 描述、persona、expected outcome。
- 每輪的自然語言生成 goal/examples/constraints。
- 預期 topic、intent、reference、qualifier、standalone query、history selection 與 retrieval domain。
- 只有 final answer 無法 deterministic 判斷時才使用 semantic criteria。

DeepEval 會針對 blueprint 主動產生不同說法；deterministic stopping controller 控制輪數。生成文字若不符合 must-include、must-include-groups 或 must-not-include 約束，會列為 invalid simulation，不會把 simulator 的情境漂移誤報成 Agent bug。

新增 scenario 後先執行：

```bash
./venv/bin/python -m evals.bug_discovery.cli estimate --profile STANDARD
./venv/bin/python -m pytest -q tests/test_bug_discovery.py
```

## Session isolation 與 consistency

DeepEval 為每個 conversation 提供唯一 `thread_id`，harness 原樣當作 `session_id`。同一 conversation 每輪共享相同 session 且回傳完整 history；不同 conversation 絕不共享 history。in-process profile 預設 concurrency 1，並在 conversation 前後清 cache。

Consistency 並非重新生成不同句子：先由 DeepEval 生成一次 user messages，再把完全相同的 user messages 用新的 session 重播 N 次。因此 success / wrong answer / unnecessary refusal / context contamination rate 可比較。

## Report 與 failure dataset

每次 run 產生：

```text
evals/runs/<run_id>/
  report.md
  results.json
  failures.jsonl
  invalid_simulations.jsonl

evals/failures/
  <run_id>.jsonl
  latest.jsonl
```

Failure JSONL 包含完整 conversation、expected/actual、LangGraph intermediate state、primary category、secondary symptoms、timestamp、git/model/collection config 與 consistency 統計。無法可靠分類時使用 `UNKNOWN`。

## 加入 Promptfoo regression

目前 repo 沒有 Promptfoo，因此本版只輸出 review-gated interface。流程：

```text
DeepEval discovers
  → 檢查 evals/failures/latest.jsonl
  → 確認是 Agent bug，不是 invalid simulation
  → promote
  → 修 Agent
  → 未來 Promptfoo provider 重播
  → 永久保留
```

確認後執行：

```bash
./venv/bin/python -m evals.bug_discovery.cli promote \
  --failure-id <failure_id> \
  --confirmed-by <reviewer>
```

輸出到 `evals/regressions/promptfoo_cases.jsonl`。未提供 reviewer 不允許 promotion，避免把 simulator 品質問題永久化。
