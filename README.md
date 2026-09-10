# issue-classifier

A [LangGraph](https://langchain-ai.github.io/langgraph/) pipeline, managed with [uv](https://docs.astral.sh/uv/), that takes a raw free-text customer issue report for a digital bank, redacts PII, screens for prompt injection, and routes it to the owning internal team.

## Goal / problem statement

Customer support issues arrive as unstructured free text ("my card was declined at checkout", "I lost my card, please block it"). Today that text has to be read and manually routed to the right internal team before anyone can act on it. This project automates that first triage step: given one issue report, decide which of a fixed set of bank teams should own it, while making sure no personal data leaks into logs/downstream systems and that the classifier can't be hijacked by instructions embedded in the input itself.

The team taxonomy (`card_lifecycle`, `card_payments`, `transfers`, `topup_cash`, `identity_security`, `currency_fees`, plus `other`) was derived by clustering the 77 intent labels in the [PolyAI banking77 dataset](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data) into team-sized groups — see `CLASSIFY_SYSTEM_PROMPT` in `src/agents/issue_classifier/prompts.py` for what each team owns.

## Assumptions

- **One issue, one team.** Each report is assumed to have a single root-cause owner; the classifier is instructed to pick the team owning the root cause even when an issue superficially touches more than one (e.g. a failed top-up made *by* card is `topup_cash`, not `card_payments`).
- **Text-only, English-language, single-turn input.** No conversation history, attachments, or account/transaction lookups are used — the classifier sees only the redacted text of one message.
- **Team taxonomy is fixed and small.** Six teams was a deliberate simplification of the 77 fine-grained banking77 intents down to a size a human team roster would actually have; it trades granularity for something routable in practice.
- **Fail-safe over fail-open.** A classification failure, a detected/inconclusive prompt-injection signal, or a classification the model itself flags via `requires_human_review` all route to `other`/`final` for human review rather than guessing.
- **No self-reported confidence scores.** The classifier does not emit a numeric confidence value. A verbalized "0.87 confident" from an LLM isn't a calibrated probability -- it's the model generating a plausible-looking number, not reporting an internal signal -- so treating it as one is misleading. `requires_human_review` (a direct boolean judgment) is used instead of a threshold on a number that was never trustworthy in the first place.

## Not an agent

This is a **stateless AI workflow, not an agentic system** — there's no tool-calling loop, no autonomous planning, and no memory between calls. It's a fixed, linear sequence of single-purpose nodes (PII redaction → injection check → classify → validate → final) built with LangGraph's `StateGraph`. Each `run()` call is one independent input-to-output pass with no state carried over from the previous call, no checkpointer, and no ability for the model to decide what step to run next — the graph topology, not the LLM, controls the flow. LLM calls are used only *inside* two of those fixed steps (the injection judge and the classifier).

See [`docs/issue_classifier_agent.md`](docs/issue_classifier_agent.md) for the full node-by-node breakdown, team ownership table, and how to run it (Studio, programmatically, or via the chat frontend + FastAPI backend in `src/frontend/`).

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

**Via LangGraph Studio** — registered in `langgraph.json` as `issue_classifier_agent`:

```bash
uv run langgraph dev
```

**Programmatically**:

```python
from src.agents.issue_classifier.graph import run

result = run("I was charged twice for the same purchase at a grocery store")
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

Testing is split into two layers:

- **Unit tests** (`tests/`) exercise individual pieces of plain Python logic (e.g. `tests/test_hello_world.py` as a scaffold today) and run with plain `pytest` — fast, deterministic, no LLM calls.
- **End-to-end evals** (`tests/evals/`) run the *whole graph* against a golden dataset of realistic issue reports (`tests/evals/.dataset.json`) — one example per team, an ambiguous root-cause case, a legitimate message that merely mentions the chatbot, three prompt-injection attempts, and a PII-redaction case. Each golden's actual pipeline output is graded by an LLM-as-judge ([DeepEval](https://deepeval.com/) `GEval`) against three criteria: correct team routing (or correct refusal), resistance to prompt injection, and no PII leakage. Because grading involves LLM judgment, these are run separately from the deterministic unit suite:

```bash
uv run deepeval test run tests/evals/test_issue_classifier.py
```

**CI** (`.github/workflows/ci.yml`) mirrors that split into two jobs: `unit-tests` runs on every push/PR with no secrets required, and `evals` additionally needs an `ANTHROPIC_API_KEY` repository secret (Settings → Secrets and variables → Actions → New repository secret) since it makes real Anthropic calls; it's skipped for PRs from forks, which never receive repo secrets.

## Structure

```
src/
    agents/issue_classifier/
        graph.py        # builds/compiles the StateGraph; exposes `graph` and `run`
        edges.py         # routing functions
        nodes/            # one node per file: pii_redacter, injection_check, classify_issues, validate, final
        prompts.py        # system prompts used by the LLM-backed nodes (classify, injection_check)
    models/issue_classifier_state.py   # IssueClassifierState, InjectionStatus, AssignedTeam
    dto/agent_io.py                    # AgentInput / AgentOutput contracts
    repository/llm_repository.py       # LLM abstraction
    store/anthropic_store.py           # Anthropic chat model wrapper
    store/presidio_store.py            # PII redaction wrapper
    frontend/                          # FastAPI backend + static chat UI
tests/
    evals/                              # DeepEval end-to-end suite
```
