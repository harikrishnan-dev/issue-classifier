# issue-resolver

An agentic pipeline, built with [LangGraph](https://langchain-ai.github.io/langgraph/) and managed with [uv](https://docs.astral.sh/uv/), that takes a raw free-text issue report, redacts PII, screens for prompt injection, and routes it to the owning team.

Split out from `lang-graph-learn` so the issue-resolver agent has its own project and dependency set.

See [`docs/issue_resolver_agent.md`](docs/issue_resolver_agent.md) for the full node-by-node breakdown, team ownership table, and how to run it (Studio, programmatically, or via the chat frontend + FastAPI backend in `src/frontend/`).

## Setup

```bash
uv sync
```

Add your Anthropic API key to `.env` at the repo root:

```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

No Docker or external services are needed — Presidio's PII detection runs locally.

## Run

**Via LangGraph Studio** — registered in `langgraph.json` as `issue_resolver_agent`:

```bash
uv run langgraph dev
```

**Programmatically**:

```python
from src.agents.issue_resolver.graph import run

result = run("The dashboard filter dropdown is broken on Safari")
print(result)
```

**Via the chat frontend**, backed by a small FastAPI wrapper:

```bash
uv run uvicorn src.frontend.backend_api:app --reload --port 8000
```

then open `src/frontend/index.html` in a browser.

## Tests

```bash
uv run pytest -q
```

The `tests/evals/` suite uses [DeepEval](https://deepeval.com/) to grade the agent's team-routing correctness, prompt-injection resistance, and PII-leakage prevention against the golden dataset in `tests/evals/.dataset.json`:

```bash
uv run deepeval test run tests/evals/test_issue_resolver.py
```

## Structure

```
src/
    agents/issue_resolver/
        graph.py        # builds/compiles the StateGraph; exposes `graph` and `run`
        edges.py         # routing functions
        nodes/            # one node per file: pii_redacter, injection_check, classify, validate, fallback, cost_log_node
    models/issue_resolver_state.py   # IssueResolverState, InjectionStatus, AssignedTeam
    dto/agent_io.py                    # AgentInput / AgentOutput contracts
    repository/llm_repository.py       # LLM abstraction
    store/anthropic_store.py           # Anthropic chat model wrapper
    store/presidio_store.py            # PII redaction wrapper
    frontend/                          # FastAPI backend + static chat UI
tests/
    evals/                              # DeepEval end-to-end suite
```
