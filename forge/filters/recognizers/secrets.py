"""Secret recognizers — API keys, tokens, and credentials (REQ-REC-04 to REQ-REC-15).

Each builder function returns a PatternRecognizer with:
- No I/O side effects
- Importable without instantiating Presidio's full engine
- Entity type label matching the spec (UPPER_SNAKE_CASE)

Scoring notes (see ADR-2 in design):
- ANTHROPIC_KEY: 1.0 — most specific prefix (sk-ant-)
- OPENAI_KEY: base 0.4 (< threshold) + context boost to 0.85; lookahead excludes sk-ant-
- AWS_ACCESS_KEY: 0.95 — AKIA/ABIA/ACCA/ASIA prefix is highly specific
- AWS_SECRET_KEY: base 0.4 (below 0.5 threshold, never fires alone) + context boost to 0.85
- BEARER_TOKEN: base 0.3 (< threshold) + context boost to 0.85
- All others: high-specificity patterns at their respective scores
"""

import re

from presidio_analyzer import Pattern, PatternRecognizer

# ---------------------------------------------------------------------------
# JWT (REQ-REC-04)
# ---------------------------------------------------------------------------


def build_jwt_recognizer() -> PatternRecognizer:
    """Three base64url segments separated by dots, each >= 10 chars.

    Score 0.9, entity JWT.
    Avoids two-segment strings (domains, version numbers) by requiring
    the pattern to have exactly two dots with >= 10 chars per segment.
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
    """AKIA/ABIA/ACCA/ASIA prefix followed by exactly 16 uppercase alphanumeric chars.

    Score 0.95, entity AWS_ACCESS_KEY.
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
    """40-char base64 string. Base score 0.4 — requires AWS context to fire.

    Base score 0.4 is below the 0.5 firing threshold so the pattern never
    triggers alone. Context words boost the score to 0.85 (fires).
    Context words: aws_secret, secret_access_key, AWS_SECRET_ACCESS_KEY,
    aws.secretAccessKey, plus Spanish cues (aws, clave, secreto, contraseña,
    credencial) so a Spanish prose hint also fires it.
    Entity AWS_SECRET_KEY.
    """
    return PatternRecognizer(
        supported_entity="AWS_SECRET_KEY",
        patterns=[
            Pattern(
                name="aws_secret_key",
                regex=r"[A-Za-z0-9/+=]{40}",
                # Base 0.4: below threshold (0.5) so it won't fire alone.
                # With context boost (+0.5, via build_analyzer()), final score = 0.90 >= 0.85 (fires).
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
    """Classic GitHub PAT: ghp_ + exactly 36 alphanumeric chars.

    Score 0.95, entity GITHUB_PAT.
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
    """Fine-grained GitHub PAT: github_pat_ + exactly 82 alphanumeric/underscore chars.

    Score 0.98, entity GITHUB_FINE_GRAINED.
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
    """OpenAI API key: sk- (not followed by ant-) + 48 alphanumeric chars.

    Base score 0.4 (< threshold 0.5) — requires openai context to fire.
    Context boost to 0.85. Entity OPENAI_KEY.

    The negative lookahead ``(?!ant-)`` prevents matching Anthropic keys.
    Context includes Spanish cues (clave, credencial, contraseña) so a Spanish
    prose hint also fires it, not only the English/identifier form.
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
    """Anthropic API key: sk-ant- + exactly 93 alphanumeric/hyphen chars.

    Score 1.0, entity ANTHROPIC_KEY. No context required.
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
    """Slack API token: xox[bpoas]- prefix + alphanumeric/hyphen chars.

    Score 0.9, entity SLACK_TOKEN.
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
    """Stripe API key: (sk|pk|rk)_(live|test)_ + at least 24 alphanumeric chars.

    Score 0.9, entity STRIPE_KEY.
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
    """PEM private key block: -----BEGIN * PRIVATE KEY----- ... -----END * PRIVATE KEY-----.

    Score 1.0, entity PRIVATE_KEY_BLOCK. Matches across newlines (DOTALL).
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
    """Password embedded in connection string.

    Captures the password value between : and @ in jdbc:/postgresql://mongodb://
    mysql://redis:// URIs. Score 0.85, entity CONNECTION_STRING_PASSWORD.
    """
    return PatternRecognizer(
        supported_entity="CONNECTION_STRING_PASSWORD",
        patterns=[
            Pattern(
                name="conn_string_password",
                # Capture group not supported by Presidio — we match the password portion only
                # by anchoring after ://[user]: and before @
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
    """Bearer token in HTTP Authorization header.

    Pattern includes the 'bearer ' prefix (case-insensitive) + token.
    Base score 0.6 already above threshold when pattern matches (bearer + 20+ chars).
    Context words boost to 0.85. Entity BEARER_TOKEN.
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
