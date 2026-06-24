"""forge.filters.recognizers — recognizers de PII custom.

Exporta:
- all_recognizers(): devuelve la lista de las 15 instancias de PatternRecognizer custom.
"""

from forge.filters.recognizers.ar_cbu import build_cbu_recognizer
from forge.filters.recognizers.ar_cuit import build_cuit_recognizer
from forge.filters.recognizers.ar_dni import build_dni_recognizer
from forge.filters.recognizers.secrets import (
    build_anthropic_key_recognizer,
    build_aws_access_key_recognizer,
    build_aws_secret_key_recognizer,
    build_bearer_token_recognizer,
    build_connection_string_password_recognizer,
    build_github_fine_grained_recognizer,
    build_github_pat_recognizer,
    build_jwt_recognizer,
    build_openai_key_recognizer,
    build_private_key_block_recognizer,
    build_slack_token_recognizer,
    build_stripe_key_recognizer,
)


def all_recognizers():
    """Devuelve una lista con las 15 instancias de PatternRecognizer custom.

    La lista se reconstruye en cada llamada (fábrica pura — sin estado a nivel módulo).
    Registrar todas las instancias en un RecognizerRegistry antes de pasarlas al AnalyzerEngine.
    """
    return [
        # Identificadores argentinos
        build_cuit_recognizer(),
        build_dni_recognizer(),
        build_cbu_recognizer(),
        # Tokens y secretos genéricos
        build_jwt_recognizer(),
        build_aws_access_key_recognizer(),
        build_aws_secret_key_recognizer(),
        build_github_pat_recognizer(),
        build_github_fine_grained_recognizer(),
        build_openai_key_recognizer(),
        build_anthropic_key_recognizer(),
        build_slack_token_recognizer(),
        build_stripe_key_recognizer(),
        build_private_key_block_recognizer(),
        build_connection_string_password_recognizer(),
        build_bearer_token_recognizer(),
    ]
