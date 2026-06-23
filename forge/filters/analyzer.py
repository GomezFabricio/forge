"""Analyzer factory — Presidio AnalyzerEngine wired with all custom recognizers (REQ-ANA-01).

Detection is pattern-based, but Presidio always tokenizes the text — and the
context-aware enhancer needs lemmas — before running any recognizer, so a spaCy
model IS required. We pin the small English model (en_core_web_sm, ~12MB): it
provides tokenization plus a lemmatizer for context boosting, and is far lighter
than the en_core_web_lg default Presidio would otherwise pull (~560MB). The model
ships as a declared dependency (pyproject) and is never auto-downloaded at runtime
(see ``_ForgeSpacyNlpEngine``).
"""

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer
from presidio_analyzer.nlp_engine import SpacyNlpEngine

from forge.filters.recognizers import all_recognizers

# spaCy model used for tokenization + lemmas (needed by the context-aware
# enhancer). Small model: ~12MB. Declared as a dependency in pyproject so it is
# always present in the install venv.
_SPACY_MODEL_NAME = "en_core_web_sm"


class _ForgeSpacyNlpEngine(SpacyNlpEngine):
    """SpacyNlpEngine pinned to our model that never auto-downloads at runtime.

    Presidio's stock engine tries to pip-install a missing model on load by
    shelling out to spaCy's CLI downloader, which calls ``sys.exit()`` on failure
    — a ``SystemExit`` (``BaseException``). The PII hook's fail-open guard only
    catches ``Exception``, so a missing model would crash the hook (exit 1, spaCy
    error on stdout) instead of passing the prompt through unmodified.

    Making the download a no-op turns an absent model into a plain ``OSError`` from
    ``spacy.load()``, which the hook's fail-open path catches cleanly. In a correct
    install the model is present (declared dependency), so this never fires.
    """

    def _download_spacy_model_if_needed(self, model_name: str) -> None:
        # Never download at runtime; the model ships as a declared dependency.
        return

# Presidio built-in recognizer names to enable (R16.4)
_BUILTIN_RECOGNIZERS = [
    "CreditCardRecognizer",
    "EmailRecognizer",
    "IbanRecognizer",
    "IpRecognizer",
    "PhoneRecognizer",
    "UrlRecognizer",
    "CryptoRecognizer",
]

# Context boost factor for the full engine.
# Presidio's default is 0.35. We use 0.5 so that:
#   - AWS_SECRET_KEY (base 0.4) + 0.5 = 0.90 >= 0.85 ✓
#   - OPENAI_KEY (base 0.4) + 0.5 = 0.90 >= 0.85 ✓
#   - All other context-boosted types are well above threshold
_CONTEXT_SIMILARITY_FACTOR = 0.5


def build_analyzer() -> AnalyzerEngine:
    """Return an AnalyzerEngine with all 22 recognizers and a pinned spaCy model.

    Registered recognizers:
    - 15 custom recognizers (forge/filters/recognizers/)
    - 7 Presidio built-in recognizers: CREDIT_CARD, EMAIL_ADDRESS, IBAN_CODE,
      IP_ADDRESS, PHONE_NUMBER, URL, CRYPTO

    Configuration:
    - NLP engine: en_core_web_sm via _ForgeSpacyNlpEngine (explicit, never the
      en_core_web_lg default; never auto-downloaded). Tokenization + lemmas only;
      the model's NER is unused — all detection comes from the recognizers above.
    - score_threshold=0.5 (default; passed at analyze() call time)
    - context_similarity_factor=0.5 (higher than Presidio default of 0.35)
      to ensure context-required recognizers reach score >= 0.85

    Note: AnalyzerEngine loads the spaCy model eagerly here, so this call pays the
    model load (~0.5s cold). Calling it multiple times is safe — no module-level
    state is mutated.
    """
    # Build a fresh registry with only the recognizers we want
    registry = RecognizerRegistry()

    # Load all predefined built-in recognizers, then remove those not in our allowed list (R16.4)
    registry.load_predefined_recognizers(languages=["en"])

    # Remove all built-in recognizers NOT in our allowed list
    allowed_names = set(_BUILTIN_RECOGNIZERS)
    to_remove = [
        rec
        for rec in registry.recognizers
        if rec.__class__.__name__ not in allowed_names
    ]
    for rec in to_remove:
        registry.remove_recognizer(rec.__class__.__name__)

    # Register all 15 custom recognizers
    for recognizer in all_recognizers():
        registry.add_recognizer(recognizer)

    # Build context enhancer with higher boost factor for context-required recognizers
    context_enhancer = LemmaContextAwareEnhancer(
        context_similarity_factor=_CONTEXT_SIMILARITY_FACTOR,
        min_score_with_context_similarity=0.5,
        context_prefix_count=10,
        context_suffix_count=5,
    )

    # Explicit small-model engine — never the lg default, never a runtime download.
    nlp_engine = _ForgeSpacyNlpEngine(
        models=[{"lang_code": "en", "model_name": _SPACY_MODEL_NAME}]
    )

    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["en"],
        context_aware_enhancer=context_enhancer,
        default_score_threshold=0.5,
    )
