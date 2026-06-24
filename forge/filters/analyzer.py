"""Fábrica del analyzer — AnalyzerEngine de Presidio cableado con todos los recognizers custom (REQ-ANA-01).

La detección es por patrones, pero Presidio SIEMPRE tokeniza el texto — y el
context-aware enhancer necesita lemas — antes de correr cualquier recognizer, así
que SÍ hace falta un modelo spaCy. Fijamos el modelo chico de inglés (en_core_web_sm,
~12MB): aporta tokenización más un lematizador para el boost de contexto, y es mucho
más liviano que el default en_core_web_lg que Presidio traería si no (~560MB). El
modelo viaja como dependencia declarada (pyproject) y nunca se autodescarga en runtime
(ver ``_ForgeSpacyNlpEngine``).
"""

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.context_aware_enhancers import LemmaContextAwareEnhancer
from presidio_analyzer.nlp_engine import SpacyNlpEngine

from forge.filters.recognizers import all_recognizers

# Modelo spaCy usado para tokenización + lemas (lo necesita el context-aware
# enhancer). Modelo chico: ~12MB. Declarado como dependencia en pyproject para que
# esté siempre presente en el venv de instalación.
_SPACY_MODEL_NAME = "en_core_web_sm"


class _ForgeSpacyNlpEngine(SpacyNlpEngine):
    """SpacyNlpEngine fijado a nuestro modelo que nunca autodescarga en runtime.

    El engine de fábrica de Presidio intenta pip-instalar un modelo ausente al
    cargar, invocando el downloader del CLI de spaCy, que llama a ``sys.exit()`` si
    falla — un ``SystemExit`` (``BaseException``). El fail-open del hook PII solo
    atrapa ``Exception``, así que un modelo ausente crashearía el hook (exit 1, error
    de spaCy en stdout) en vez de dejar pasar el prompt sin modificar.

    Hacer la descarga un no-op convierte un modelo ausente en un ``OSError`` común de
    ``spacy.load()``, que el fail-open del hook atrapa limpio. En una instalación
    correcta el modelo está presente (dependencia declarada), así que esto nunca se dispara.
    """

    def _download_spacy_model_if_needed(self, model_name: str) -> None:
        # Nunca descargar en runtime; el modelo viaja como dependencia declarada.
        return

# Nombres de los recognizers built-in de Presidio que habilitamos (R16.4)
_BUILTIN_RECOGNIZERS = [
    "CreditCardRecognizer",
    "EmailRecognizer",
    "IbanRecognizer",
    "IpRecognizer",
    "PhoneRecognizer",
    "UrlRecognizer",
    "CryptoRecognizer",
]

# Factor de boost de contexto para el engine completo.
# El default de Presidio es 0.35. Usamos 0.5 para que:
#   - AWS_SECRET_KEY (base 0.4) + 0.5 = 0.90 >= 0.85 ✓
#   - OPENAI_KEY (base 0.4) + 0.5 = 0.90 >= 0.85 ✓
#   - Todos los demás tipos con boost de contexto queden bien sobre el umbral
_CONTEXT_SIMILARITY_FACTOR = 0.5


def build_analyzer() -> AnalyzerEngine:
    """Devuelve un AnalyzerEngine con los 22 recognizers y un modelo spaCy fijado.

    Recognizers registrados:
    - 15 recognizers custom (forge/filters/recognizers/)
    - 7 recognizers built-in de Presidio: CREDIT_CARD, EMAIL_ADDRESS, IBAN_CODE,
      IP_ADDRESS, PHONE_NUMBER, URL, CRYPTO

    Configuración:
    - Engine NLP: en_core_web_sm vía _ForgeSpacyNlpEngine (explícito, nunca el
      default en_core_web_lg; nunca autodescargado). Solo tokenización + lemas;
      el NER del modelo no se usa — toda la detección viene de los recognizers de arriba.
    - score_threshold=0.5 (default; se pasa al momento de llamar analyze())
    - context_similarity_factor=0.5 (más alto que el default 0.35 de Presidio)
      para asegurar que los recognizers que requieren contexto lleguen a score >= 0.85

    Nota: AnalyzerEngine carga el modelo spaCy de forma eager acá, así que esta
    llamada paga la carga del modelo (~0.5s en frío). Llamarla varias veces es seguro
    — no se muta estado a nivel módulo.
    """
    # Construir un registry nuevo solo con los recognizers que queremos
    registry = RecognizerRegistry()

    # Cargar todos los recognizers built-in predefinidos y después quitar los que no están en la lista permitida (R16.4)
    registry.load_predefined_recognizers(languages=["en"])

    # Quitar todos los recognizers built-in que NO están en nuestra lista permitida
    allowed_names = set(_BUILTIN_RECOGNIZERS)
    to_remove = [
        rec
        for rec in registry.recognizers
        if rec.__class__.__name__ not in allowed_names
    ]
    for rec in to_remove:
        registry.remove_recognizer(rec.__class__.__name__)

    # Registrar los 15 recognizers custom
    for recognizer in all_recognizers():
        registry.add_recognizer(recognizer)

    # Construir el context enhancer con un factor de boost más alto para los recognizers que requieren contexto
    context_enhancer = LemmaContextAwareEnhancer(
        context_similarity_factor=_CONTEXT_SIMILARITY_FACTOR,
        min_score_with_context_similarity=0.5,
        context_prefix_count=10,
        context_suffix_count=5,
    )

    # Engine explícito con el modelo chico — nunca el default lg, nunca una descarga en runtime.
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
