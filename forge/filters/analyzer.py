"""Analyzer factory — Presidio AnalyzerEngine wired with all custom recognizers (REQ-ANA-01).

Pattern-only mode: no spaCy, no NLP model required. Cold start budget: < 300ms on Windows.
"""

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer

from forge.filters.recognizers import all_recognizers

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
    """Return an AnalyzerEngine in pattern-only mode with all 22 recognizers.

    Registered recognizers:
    - 15 custom recognizers (forge/filters/recognizers/)
    - 7 Presidio built-in recognizers: CREDIT_CARD, EMAIL_ADDRESS, IBAN_CODE,
      IP_ADDRESS, PHONE_NUMBER, URL, CRYPTO

    Configuration:
    - No NLP engine (no spaCy model required)
    - score_threshold=0.5 (default; passed at analyze() call time)
    - context_similarity_factor=0.5 (higher than Presidio default of 0.35)
      to ensure context-required recognizers reach score >= 0.85

    Calling this function multiple times is safe — no module-level state is mutated.
    """
    # Build a fresh registry with only the recognizers we want
    registry = RecognizerRegistry()

    # Load only the specific built-in recognizers listed in R16.4
    # (load_predefined_recognizers() loads ALL — we need selective registration)
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

    return AnalyzerEngine(
        registry=registry,
        nlp_engine=None,
        supported_languages=["en"],
        context_aware_enhancer=context_enhancer,
        default_score_threshold=0.5,
    )
