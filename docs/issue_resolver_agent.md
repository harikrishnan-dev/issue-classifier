# Issue Resolver Agent

## Summary

`issue_resolver` is an agentic pipeline that takes a raw, free-text issue report (as might come from a support chat) and triages it: strips personal information, screens for prompt-injection attempts, and routes it to the Kpler team best positioned to handle it.

The graph is a fixed pipeline of single-purpose nodes rather than a tool-calling agent loop:

1. **`pii_redacter`** — masks personally identifiable information (emails, names, etc.) in the raw input using [Presidio](https://microsoft.github.io/presidio/), before any of it reaches an LLM.
2. **`injection_check`** — an LLM-as-a-judge guard (on a fast/cheap model, independent of the rest of the pipeline) that decides whether the redacted text is a legitimate issue report or an attempt to hijack/override the agent's own instructions. Result is one of three states — `yes`, `no`, `not_able_to_detect` — and a definite `no` is the only one that proceeds; both a confirmed injection *and* an inconclusive guard call fail safe to `fallback`.
3. **`classify`** — routes the issue to a single owning team (see [Teams](#teams)) using structured LLM output (function-calling, validated with Pydantic), with a confidence score and a `requires_human_review` flag for low-confidence assignments.
4. **`validate`** — sanity-checks that there's actually a non-empty description and a team assignment before treating the run as successful.
5. **`fallback`** — produces a safe, explanatory response for an injection attempt, an inconclusive injection check, or a failed validation, instead of continuing the pipeline.
6. **`cost_log_node`** — logs the run's outcome (team, validity, injection status) and produces the final answer.

```
pii_redacter -> injection_check -> [fallback | classify]
classify -> validate -> [fallback | cost_log_node]
fallback -> cost_log_node -> END
```

> **Current status:** `graph.py` currently wires `pii_redacter -> injection_check -> [fallback | classify]`, with `classify` going straight to `END`. `validate` and `cost_log_node` exist and are unit-tested but aren't connected into `build_graph()` yet — the full flow above is the intended end state, not what runs today.

## Teams

`classify` assigns one of these (see `AssignedTeam` in `src/models/issue_resolver_state.py`):

| Team | Owns |
| --- | --- |
| `cargo_models` | Vessel cargo-carrying information — cargo volume, product/commodity type on board |
| `freight` | Vessel congestion, vessel build dates, zone calls, how many vessels are congested near a port |
| `flows` | Overall import/export volumes of commodities (oil, diesel, petrol, agri products, etc.) between countries |
| `compliance` | Sanctioned vessels; how often a vessel's flag or MMSI changes |
| `insights` | Analysis connecting cargo flow changes to markets/wars/economic events — Kpler data + real news |
| `ui` | General bugs in the user interface, unrelated to the underlying data |
| `voyage` | Vessel voyage details — port calls, ETA/ETD, routes, voyage history *(inferred description — not explicitly specified, confirm with the team)* |
| `ais_ingress` | Vessel position (AIS) data — delayed, missing, or historic positions |
| `other` | Doesn't clearly fit any team above |

The team descriptions live in `DEFAULT_SYSTEM_PROMPT` in `src/agents/issue_resolver/nodes/classify.py` — that's what the model actually sees, so keep it in sync with this table.

## Setup

1. [uv](https://docs.astral.sh/uv/) and Python 3.13 (`uv sync` installs everything, including the `presidio`/`en-core-web-sm` PII-detection dependencies).
2. An Anthropic API key. Add it to `.env` at the repo root:
   ```bash
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```
   (`src/store/anthropic_store.py` loads `.env` itself, so this works whether the graph is run via the LangGraph CLI, a plain script, or `uvicorn`.)

No Docker/external services are needed — Presidio's PII detection runs locally.

## Run

**Via LangGraph Studio** — registered in `langgraph.json` as `issue_resolver_agent`:

```bash
uv run langgraph dev
```

**Programmatically**, via the `run` helper (no checkpointer/config needed — each call is a single, independent invocation):

```python
from src.agents.issue_resolver.graph import run

result = run("The dashboard filter dropdown is broken on Safari")
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
| `src/agents/issue_resolver/graph.py` | Builds/compiles the StateGraph; exposes `graph` (for `langgraph.json`) and `run` (for other callers) |
| `src/agents/issue_resolver/edges.py` | Routing functions (`route_after_injection_check`, `route_after_validate`) |
| `src/agents/issue_resolver/nodes/*.py` | One node function per file |
| `src/models/issue_resolver_state.py` | `IssueResolverState`, `InjectionStatus`, `AssignedTeam` |
| `src/store/presidio_store.py` | `PresidioStore` — thin wrapper over Presidio's analyzer/anonymizer |
| `src/frontend/backend_api.py` | FastAPI wrapper exposing `run()` as `POST /analyze` |
| `src/frontend/index.html` | Chat UI: message list + a results panel per message |
