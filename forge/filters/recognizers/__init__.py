"""forge.filters.recognizers — custom PII recognizers.

Exports:
- all_recognizers(): returns list of all 15 custom PatternRecognizer instances.
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
    """Return a list of all 15 custom PatternRecognizer instances.

    The list is rebuilt on every call (pure factory — no module-level state).
    Register all instances with a RecognizerRegistry before passing to AnalyzerEngine.
    """
    return [
        # Argentine identifiers
        build_cuit_recognizer(),
        build_dni_recognizer(),
        build_cbu_recognizer(),
        # Generic tokens and secrets
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
