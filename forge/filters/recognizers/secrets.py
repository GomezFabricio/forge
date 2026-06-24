"""Recognizers de secretos — API keys, tokens y credenciales (REQ-REC-04 a REQ-REC-15).

Cada función builder devuelve un PatternRecognizer con:
- Sin efectos de I/O
- Importable sin instanciar el engine completo de Presidio
- Label de tipo de entidad según la spec (UPPER_SNAKE_CASE)

Notas de scoring (ver ADR-2 en el diseño):
- ANTHROPIC_KEY: 1.0 — el prefijo más específico (sk-ant-)
- OPENAI_KEY: base 0.4 (< umbral) + boost de contexto a 0.85; el lookahead excluye sk-ant-
- AWS_ACCESS_KEY: 0.95 — el prefijo AKIA/ABIA/ACCA/ASIA es muy específico
- AWS_SECRET_KEY: base 0.4 (debajo del umbral 0.5, nunca dispara solo) + boost de contexto a 0.85
- BEARER_TOKEN: base 0.3 (< umbral) + boost de contexto a 0.85
- Todos los demás: patrones de alta especificidad con sus respectivos scores
"""

import re

from presidio_analyzer import Pattern, PatternRecognizer

# ---------------------------------------------------------------------------
# JWT (REQ-REC-04)
# ---------------------------------------------------------------------------


def build_jwt_recognizer() -> PatternRecognizer:
    """Tres segmentos base64url separados por puntos, cada uno >= 10 chars.

    Score 0.9, entidad JWT.
    Evita strings de dos segmentos (dominios, números de versión) exigiendo
    que el patrón tenga exactamente dos puntos con >= 10 chars por segmento.
    """
    return PatternRecognizer(
        supported_entity="JWT",
        patterns=[
            Pattern(
                name="jwt_three_segments",
                regex=r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
                score=0.9,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# AWS_ACCESS_KEY (REQ-REC-05)
# ---------------------------------------------------------------------------


def build_aws_access_key_recognizer() -> PatternRecognizer:
    """Prefijo AKIA/ABIA/ACCA/ASIA seguido de exactamente 16 chars alfanuméricos en mayúscula.

    Score 0.95, entidad AWS_ACCESS_KEY.
    """
    return PatternRecognizer(
        supported_entity="AWS_ACCESS_KEY",
        patterns=[
            Pattern(
                name="aws_access_key",
                regex=r"\b(AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b",
                score=0.95,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# AWS_SECRET_KEY (REQ-REC-06)
# ---------------------------------------------------------------------------


def build_aws_secret_key_recognizer() -> PatternRecognizer:
    """String base64 de 40 chars. Score base 0.4 — requiere contexto de AWS para disparar.

    El score base 0.4 está por debajo del umbral de disparo 0.5, así que el patrón
    nunca se dispara solo. Las palabras de contexto suben el score a 0.85 (dispara).
    Palabras de contexto: aws_secret, secret_access_key, AWS_SECRET_ACCESS_KEY,
    aws.secretAccessKey, más pistas en español (aws, clave, secreto, contraseña,
    credencial) para que una pista en prosa española también lo dispare.
    Entidad AWS_SECRET_KEY.
    """
    return PatternRecognizer(
        supported_entity="AWS_SECRET_KEY",
        patterns=[
            Pattern(
                name="aws_secret_key",
                regex=r"[A-Za-z0-9/+=]{40}",
                # Base 0.4: debajo del umbral (0.5) así que no dispara solo.
                # Con boost de contexto (+0.5, vía build_analyzer()), score final = 0.90 >= 0.85 (dispara).
                score=0.4,
            )
        ],
        context=[
            "aws_secret",
            "secret_access_key",
            "AWS_SECRET_ACCESS_KEY",
            "aws.secretAccessKey",
            # Pistas en español. El modelo spaCy es inglés y no lematiza el español
            # a su raíz, así que listamos las formas de superficie tal como se
            # escriben (con y sin tilde).
            "aws",
            "clave",
            "secreta",
            "secreto",
            "credencial",
            "credenciales",
            "contraseña",
            "contrasena",
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# GITHUB_PAT (REQ-REC-07)
# ---------------------------------------------------------------------------


def build_github_pat_recognizer() -> PatternRecognizer:
    """PAT clásico de GitHub: ghp_ + exactamente 36 chars alfanuméricos.

    Score 0.95, entidad GITHUB_PAT.
    """
    return PatternRecognizer(
        supported_entity="GITHUB_PAT",
        patterns=[
            Pattern(
                name="github_classic_pat",
                regex=r"\bghp_[A-Za-z0-9]{36}\b",
                score=0.95,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# GITHUB_FINE_GRAINED (REQ-REC-08)
# ---------------------------------------------------------------------------


def build_github_fine_grained_recognizer() -> PatternRecognizer:
    """PAT fine-grained de GitHub: github_pat_ + exactamente 82 chars alfanuméricos/guión bajo.

    Score 0.98, entidad GITHUB_FINE_GRAINED.
    """
    return PatternRecognizer(
        supported_entity="GITHUB_FINE_GRAINED",
        patterns=[
            Pattern(
                name="github_fine_grained_pat",
                regex=r"\bgithub_pat_[A-Za-z0-9_]{82}\b",
                score=0.98,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# OPENAI_KEY (REQ-REC-09)
# ---------------------------------------------------------------------------


def build_openai_key_recognizer() -> PatternRecognizer:
    """API key de OpenAI: sk- (no seguido de ant-) + 48 chars alfanuméricos.

    Score base 0.4 (< umbral 0.5) — requiere contexto de openai para disparar.
    Boost de contexto a 0.85. Entidad OPENAI_KEY.

    El lookahead negativo ``(?!ant-)`` evita matchear keys de Anthropic.
    El contexto incluye pistas en español (clave, credencial, contraseña) para que
    una pista en prosa española también lo dispare, no solo la forma inglesa/identificador.
    """
    return PatternRecognizer(
        supported_entity="OPENAI_KEY",
        patterns=[
            Pattern(
                name="openai_key",
                regex=r"\bsk-(?!ant-)[A-Za-z0-9]{48}\b",
                score=0.4,
            )
        ],
        context=[
            "openai",
            "OPENAI_API_KEY",
            "openai.api_key",
            "sk-",
            # Pistas en español (formas de superficie; el modelo es inglés).
            "clave",
            "credencial",
            "credenciales",
            "contraseña",
            "contrasena",
        ],
        supported_language="en",
        global_regex_flags=re.DOTALL | re.MULTILINE,
    )


# ---------------------------------------------------------------------------
# ANTHROPIC_KEY (REQ-REC-10)
# ---------------------------------------------------------------------------


def build_anthropic_key_recognizer() -> PatternRecognizer:
    """API key de Anthropic: sk-ant- + exactamente 93 chars alfanuméricos/guión.

    Score 1.0, entidad ANTHROPIC_KEY. No requiere contexto.
    """
    return PatternRecognizer(
        supported_entity="ANTHROPIC_KEY",
        patterns=[
            Pattern(
                name="anthropic_key",
                regex=r"\bsk-ant-[A-Za-z0-9\-]{93}\b",
                score=1.0,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# SLACK_TOKEN (REQ-REC-11)
# ---------------------------------------------------------------------------


def build_slack_token_recognizer() -> PatternRecognizer:
    """Token de API de Slack: prefijo xox[bpoas]- + chars alfanuméricos/guión.

    Score 0.9, entidad SLACK_TOKEN.
    """
    return PatternRecognizer(
        supported_entity="SLACK_TOKEN",
        patterns=[
            Pattern(
                name="slack_token",
                regex=r"\bxox[bpoas]-[A-Za-z0-9\-]+\b",
                score=0.9,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# STRIPE_KEY (REQ-REC-12)
# ---------------------------------------------------------------------------


def build_stripe_key_recognizer() -> PatternRecognizer:
    """API key de Stripe: (sk|pk|rk)_(live|test)_ + al menos 24 chars alfanuméricos.

    Score 0.9, entidad STRIPE_KEY.
    """
    return PatternRecognizer(
        supported_entity="STRIPE_KEY",
        patterns=[
            Pattern(
                name="stripe_key",
                regex=r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{24,}\b",
                score=0.9,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# PRIVATE_KEY_BLOCK (REQ-REC-13)
# ---------------------------------------------------------------------------


def build_private_key_block_recognizer() -> PatternRecognizer:
    """Bloque de clave privada PEM: -----BEGIN * PRIVATE KEY----- ... -----END * PRIVATE KEY-----.

    Score 1.0, entidad PRIVATE_KEY_BLOCK. Matchea a través de saltos de línea (DOTALL).
    """
    return PatternRecognizer(
        supported_entity="PRIVATE_KEY_BLOCK",
        patterns=[
            Pattern(
                name="pem_private_key",
                regex=r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----",
                score=1.0,
            )
        ],
        supported_language="en",
        global_regex_flags=re.DOTALL | re.MULTILINE,
    )


# ---------------------------------------------------------------------------
# CONNECTION_STRING_PASSWORD (REQ-REC-14)
# ---------------------------------------------------------------------------


def build_connection_string_password_recognizer() -> PatternRecognizer:
    """Contraseña embebida en un connection string.

    Captura el valor de la contraseña entre : y @ en URIs jdbc:/postgresql://mongodb://
    mysql://redis://. Score 0.85, entidad CONNECTION_STRING_PASSWORD.
    """
    return PatternRecognizer(
        supported_entity="CONNECTION_STRING_PASSWORD",
        patterns=[
            Pattern(
                name="conn_string_password",
                # Presidio no soporta grupos de captura — matcheamos solo la porción de la
                # contraseña anclando después de ://[user]: y antes de @
                regex=r"(?:jdbc:|postgresql://|mongodb://|mysql://|redis://)[^@\s]*:[^\s:@/][^@\s]*@",
                score=0.85,
            )
        ],
        supported_language="en",
    )


# ---------------------------------------------------------------------------
# BEARER_TOKEN (REQ-REC-15)
# ---------------------------------------------------------------------------


def build_bearer_token_recognizer() -> PatternRecognizer:
    """Token Bearer en el header Authorization de HTTP.

    El patrón incluye el prefijo 'bearer ' (case-insensitive) + el token.
    El score base 0.6 ya está sobre el umbral cuando el patrón matchea (bearer + 20+ chars).
    Las palabras de contexto suben a 0.85. Entidad BEARER_TOKEN.
    """
    return PatternRecognizer(
        supported_entity="BEARER_TOKEN",
        patterns=[
            Pattern(
                name="bearer_token",
                regex=r"(?i)bearer\s+[A-Za-z0-9\-_\.=]{20,}",
                score=0.6,
            )
        ],
        context=[
            "Authorization",
            "authorization",
            "Bearer",
            "bearer",
        ],
        supported_language="en",
    )
