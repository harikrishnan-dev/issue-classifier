# Issue Classifier Agent

## Summary

`issue_classifier` is a pipeline that takes a raw, free-text issue report (as might come from a bank's customer support chat) and triages it: strips personal information, screens for prompt-injection attempts, and routes it to the internal bank team/tribe best positioned to handle it.

The graph is a fixed pipeline of single-purpose nodes rather than a tool-calling agent loop:

1. **`pii_redacter`** — masks personally identifiable information (emails, names, etc.) in the raw input using [Presidio](https://microsoft.github.io/presidio/), before any of it reaches an LLM.
2. **`injection_check`** — an LLM-as-a-judge guard (on a fast/cheap model, independent of the rest of the pipeline) that decides whether the redacted text is a legitimate issue report or an attempt to hijack/override the agent's own instructions. Result is one of three states — `yes`, `no`, `not_able_to_detect` — and a definite `no` is the only one that proceeds; both a confirmed injection *and* an inconclusive guard call skip straight to `final`.
3. **`classify`** — routes the issue to a single owning team (see [Teams](#teams)) using structured LLM output (function-calling, validated with Pydantic), with a `requires_human_review` flag the model sets directly for assignments it's unsure about. There's deliberately no numeric confidence score -- a verbalized confidence number from an LLM isn't a calibrated probability, so a boolean judgment call is used instead of thresholding a number that was never trustworthy.
4. **`validate`** — sanity-checks that there's actually a non-empty description and a team assignment before treating the run as successful.
5. **`final`** — the graph's single terminal node. Every path (a blocked injection, an inconclusive injection check, a failed validation, or a successful classification) converges here; it picks the right response message for whichever state it sees and logs a one-line run summary. This used to be two separate nodes (`fallback` for the safe/error paths, `cost_log_node` for the success path + logging) that both fed into the same terminal step and were merged since they were just picking one message from the same state fields the graph already routes on.

```
pii_redacter -> injection_check -> [final | classify]
classify -> validate -> final -> END
```

## Teams

`classify` assigns one of these (see `AssignedTeam` in `src/models/issue_classifier_state.py`). The six teams were derived by grouping the 77 intent labels from the [PolyAI banking77 dataset](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data) into team-sized clusters:

| Team | Owns |
| --- | --- |
| `card_lifecycle` | Acquiring/maintaining a card: ordering, activation, delivery, expiry, limits, supported networks — before or independent of any specific payment |
| `card_payments` | Disputes/failures on a specific card transaction: declines, duplicate charges, wrong FX rate, contactless/wallet failures, statement fees |
| `transfers` | Bank-to-bank money movement: failed/pending/cancelled transfers, money not received, direct debits, blocked beneficiaries |
| `topup_cash` | Funding the account (top-ups) and physical cash handling (ATM withdrawals) |
| `identity_security` | Identity verification (KYC), account access, and account/card/phone safety — lost, stolen, or compromised |
| `currency_fees` | FX rates, currency/country coverage, and general refund requests not tied to a specific transaction type |
| `other` | Doesn't clearly fit any team above |

The team descriptions live in `CLASSIFY_SYSTEM_PROMPT` in `src/agents/issue_classifier/prompts.py` — that's what the model actually sees, so keep it in sync with this table.

## Setup

1. [uv](https://docs.astral.sh/uv/) and Python 3.13 (`uv sync` installs everything, including the `presidio`/`en-core-web-sm` PII-detection dependencies).
2. An Anthropic API key. Add it to `.env` at the repo root:
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```
   (`src/store/anthropic_store.py` loads `.env` itself, so this works whether the graph is run via the LangGraph CLI, a plain script, or `uvicorn`.)

No Docker/external services are needed — Presidio's PII detection runs locally.

## Dependency injection

`classify` and `injection_check` are the two LLM-backed nodes. Rather than each one constructing its own module-level `LLMRepository` at import time, they're built by factory functions — `make_classify_node(llm_repository)` and `make_injection_check_node(llm_repository)` — that close over an injected `LLMRepository` and return the actual node function. `build_graph()` is the composition root: it takes optional `llm_repository`/`guard_llm_repository` parameters (defaulting to real Anthropic-backed repositories if omitted) and passes them to the factories when wiring the graph. This means a test can call `build_graph(llm_repository=fake, guard_llm_repository=fake)` to exercise the whole pipeline (or `make_classify_node(fake)` for just one node) without patching module state or making a real API call.

## Run

**Via LangGraph Studio** — registered in `langgraph.json` as `issue_classifier_agent`:

```bash
uv run langgraph dev
```

**Programmatically**, via the `run` helper (no checkpointer/config needed — each call is a single, independent invocation):

```python
from src.agents.issue_classifier.graph import run

result = run("I was charged twice for the same purchase at a grocery store")
print(result)
```

**Via the chat frontend**, backed by a small FastAPI wrapper:

```bash
uv run uvicorn src.frontend.backend_api:app --reload --port 8000
```

then open `src/frontend/index.html` in a browser — it POSTs each message to `/analyze` and renders the redacted text, team, sentiment/priority (heuristic for now — not model-driven), and reasoning.

## Key files

| File | Role |
| --- | --- |
| `src/agents/issue_classifier/graph.py` | Builds/compiles the StateGraph; exposes `graph` (for `langgraph.json`) and `run` (for other callers) |
| `src/agents/issue_classifier/edges.py` | Routing functions (`route_after_injection_check`) |
| `src/agents/issue_classifier/nodes/*.py` | One node function per file |
| `src/agents/issue_classifier/prompts.py` | System prompts used by the LLM-backed nodes (`classify`, `injection_check`) |
| `src/models/issue_classifier_state.py` | `IssueClassifierState`, `InjectionStatus`, `AssignedTeam` |
| `src/store/presidio_store.py` | `PresidioStore` — thin wrapper over Presidio's analyzer/anonymizer |
| `src/frontend/backend_api.py` | FastAPI wrapper exposing `run()` as `POST /analyze` |
| `src/frontend/index.html` | Chat UI: message list + a results panel per message |
