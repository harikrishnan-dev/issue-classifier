"""DeepEval judge model backed by this project's existing Anthropic setup.

DeepEval defaults to an OpenAI judge model (via `OPENAI_API_KEY`), but this
project only configures `ANTHROPIC_API_KEY`. Wrapping `LLMRepository` as a
`DeepEvalBaseLLM` lets every metric in `metrics.py` use the same Anthropic
model this project already talks to, instead of requiring a second provider
just for evals.
"""

from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_core.messages import HumanMessage

from src.repository.llm_repository import LLMRepository


class AnthropicEvalModel(DeepEvalBaseLLM):
    def __init__(self, model: str = "claude-sonnet-5"):
        self._llm_repository = LLMRepository()
        super().__init__(model)

    def load_model(self):
        return self._llm_repository.get_model()

    def generate(self, prompt: str) -> str:
        return self._llm_repository.invoke([HumanMessage(content=prompt)])

    async def a_generate(self, prompt: str) -> str:
        response = await self.model.ainvoke([HumanMessage(content=prompt)])
        return self._llm_repository.as_text(response.content)

    def get_model_name(self) -> str:
        return self.name


anthropic_eval_model = AnthropicEvalModel()
