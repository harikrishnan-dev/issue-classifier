"""Thin wrapper around Microsoft Presidio for PII detection/redaction.

This is the only place in the project that talks to `presidio_analyzer`/
`presidio_anonymizer` directly. Anything that needs to redact PII should go
through this module. Uses the small spaCy English model (`en_core_web_sm`,
pinned in pyproject.toml via `[tool.uv.sources]`) rather than Presidio's
default `en_core_web_lg`, to keep the dependency lightweight.
"""

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

_NLP_CONFIGURATION = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
}


class PresidioStore:
    def __init__(self) -> None:
        nlp_engine = NlpEngineProvider(nlp_configuration=_NLP_CONFIGURATION).create_engine()
        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self._anonymizer = AnonymizerEngine()

    def redact(self, text: str, language: str = "en") -> str:
        """Replace detected PII entities in `text` with `<ENTITY_TYPE>` placeholders."""
        results = self._analyzer.analyze(text=text, language=language)
        return self._anonymizer.anonymize(text=text, analyzer_results=results).text
