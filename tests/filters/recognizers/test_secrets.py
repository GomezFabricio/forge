"""Tests para los 12 secret recognizers (REQ-REC-04 a REQ-REC-15).

TDD cycle: RED — imports from secrets.py which does not exist yet.
One TestClass per entity type for isolation and readability.
"""

import pytest
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

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
from tests.filters.fixtures import (
    ANTHROPIC_KEY_VALID,
    AWS_ACCESS_KEY_EXAMPLE,
    AWS_SECRET_KEY_EXAMPLE,
    BEARER_HEADER,
    BARE_TOKEN_NO_BEARER,
    BEARER_LOWERCASE,
    CBU_VALID,
    EC_PRIVATE_KEY_BLOCK,
    GITHUB_CLASSIC_PAT,
    GITHUB_FINE_GRAINED_PAT,
    GITHUB_SHORT_PAT,
    JWT_IN_CODE,
    JWT_SHORT_SEGMENTS,
    JWT_TWO_SEGMENT,
    JWT_VALID,
    JWT_VERSION_STRING,
    MONGO_CONN_STRING,
    OPENAI_KEY_VALID,
    POSTGRES_CONN_STRING,
    POSTGRES_NO_PASSWORD,
    PUBLIC_KEY_BLOCK,
    RSA_PRIVATE_KEY_BLOCK,
    SLACK_BOT_TOKEN,
    STRIPE_LIVE_SECRET,
    STRIPE_TEST_PUBLISHABLE,
)


def _single_engine(builder):
    """Return AnalyzerEngine with only the given recognizer."""
    registry = RecognizerRegistry()
    registry.add_recognizer(builder())
    return AnalyzerEngine(registry=registry, nlp_engine=None, supported_languages=["en"])


# ---------------------------------------------------------------------------
# JWT (REQ-REC-04)
# ---------------------------------------------------------------------------

class TestJWT:
    """Tests for build_jwt_recognizer()."""

    def test_jwt_detected(self):
        """R04-A: three-segment base64url JWT is detected."""
        engine = _single_engine(build_jwt_recognizer)
        results = engine.analyze(
            text=f"Authorization: Bearer {JWT_VALID}",
            language="en",
        )
        jwt_results = [r for r in results if r.entity_type == "JWT"]
        assert len(jwt_results) >= 1
        assert jwt_results[0].score >= 0.9

    def test_dotted_domain_not_jwt(self):
        """R04-B: dotted domain name is NOT a JWT."""
        engine = _single_engine(build_jwt_recognizer)
        results = engine.analyze(text="endpoint: api.example.com", language="en")
        jwt_results = [r for r in results if r.entity_type == "JWT"]
        assert len(jwt_results) == 0

    def test_jwt_in_code_context(self):
        """R04-C: JWT in code fixture without #fg-pass is detected."""
        engine = _single_engine(build_jwt_recognizer)
        results = engine.analyze(
            text=f"test_token = {JWT_IN_CODE}",
            language="en",
        )
        jwt_results = [r for r in results if r.entity_type == "JWT"]
        assert len(jwt_results) >= 1
        assert jwt_results[0].score >= 0.9

    def test_version_string_not_jwt(self):
        """R04-D: version string '3.10' is NOT a JWT."""
        engine = _single_engine(build_jwt_recognizer)
        results = engine.analyze(text=f"version: {JWT_VERSION_STRING}", language="en")
        jwt_results = [r for r in results if r.entity_type == "JWT"]
        assert len(jwt_results) == 0

    def test_short_segments_not_jwt(self):
        """Triangulate: segments < 10 chars are not matched."""
        engine = _single_engine(build_jwt_recognizer)
        results = engine.analyze(text=JWT_SHORT_SEGMENTS, language="en")
        jwt_results = [r for r in results if r.entity_type == "JWT"]
        assert len(jwt_results) == 0

    def test_jwt_entity_label(self):
        """R04.3: entity type label is JWT."""
        assert "JWT" in build_jwt_recognizer().supported_entities


# ---------------------------------------------------------------------------
# AWS_ACCESS_KEY (REQ-REC-05)
# ---------------------------------------------------------------------------

class TestAWSAccessKey:
    """Tests for build_aws_access_key_recognizer()."""

    def test_aws_key_detected(self):
        """R05-A: AKIA-prefixed key is detected."""
        engine = _single_engine(build_aws_access_key_recognizer)
        results = engine.analyze(
            text=f"export AWS_ACCESS_KEY_ID={AWS_ACCESS_KEY_EXAMPLE}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "AWS_ACCESS_KEY"]
        assert len(results) >= 1
        assert results[0].score >= 0.95

    def test_non_akia_prefix_not_detected(self):
        """R05-B: string without AKIA/ABIA/ACCA/ASIA prefix is NOT detected."""
        engine = _single_engine(build_aws_access_key_recognizer)
        results = engine.analyze(text="token: XKIAIOSFODNN7EXAMPLE", language="en")
        results = [r for r in results if r.entity_type == "AWS_ACCESS_KEY"]
        assert len(results) == 0

    def test_aws_access_key_entity_label(self):
        """R05.3: entity type label is AWS_ACCESS_KEY."""
        assert "AWS_ACCESS_KEY" in build_aws_access_key_recognizer().supported_entities

    @pytest.mark.parametrize("prefix", ["AKIA", "ABIA", "ACCA", "ASIA"])
    def test_all_valid_prefixes_detected(self, prefix):
        """R05.1: all four valid prefixes trigger detection."""
        engine = _single_engine(build_aws_access_key_recognizer)
        key = prefix + "IOSFODNN7EXAMPLE"  # 16 uppercase alphanumeric after prefix
        results = engine.analyze(text=f"KEY={key}", language="en")
        results = [r for r in results if r.entity_type == "AWS_ACCESS_KEY"]
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# AWS_SECRET_KEY (REQ-REC-06)
# ---------------------------------------------------------------------------

class TestAWSSecretKey:
    """Tests for build_aws_secret_key_recognizer()."""

    def test_secret_with_context_detected(self):
        """R06-A: 40-char base64 string with AWS_SECRET_ACCESS_KEY context is detected."""
        engine = _single_engine(build_aws_secret_key_recognizer)
        results = engine.analyze(
            text=f"AWS_SECRET_ACCESS_KEY={AWS_SECRET_KEY_EXAMPLE}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "AWS_SECRET_KEY"]
        assert len(results) >= 1
        assert results[0].score >= 0.85

    def test_15_bare_base64_strings_not_detected(self):
        """R06-B: 40-char base64 strings without AWS context are NOT detected."""
        engine = _single_engine(build_aws_secret_key_recognizer)
        bare_strings = [
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # the real example, no context
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmn",
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcd",
            "aaaabbbbccccddddeeeeffffgggghhhhiiiijjjjkk",
            "ZZZZYYYYXXXXWWWWVVVVUUUUTTTTSSSSRRRRQQQQpp",
        ]
        for s in bare_strings[:15]:
            results = engine.analyze(text=s, language="en", score_threshold=0.5)
            results = [r for r in results if r.entity_type == "AWS_SECRET_KEY"]
            assert len(results) == 0, f"False positive on: {s}"

    def test_aws_secret_key_entity_label(self):
        """R06.4: entity type label is AWS_SECRET_KEY."""
        assert "AWS_SECRET_KEY" in build_aws_secret_key_recognizer().supported_entities


# ---------------------------------------------------------------------------
# GITHUB_PAT (REQ-REC-07)
# ---------------------------------------------------------------------------

class TestGitHubPAT:
    """Tests for build_github_pat_recognizer()."""

    def test_classic_pat_detected(self):
        """R07-A: ghp_ + 36 alphanumeric PAT is detected."""
        engine = _single_engine(build_github_pat_recognizer)
        results = engine.analyze(
            text=f"GITHUB_TOKEN={GITHUB_CLASSIC_PAT}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "GITHUB_PAT"]
        assert len(results) >= 1
        assert results[0].score >= 0.95

    def test_wrong_length_not_detected(self):
        """R07-B: ghp_ with wrong length is NOT detected."""
        engine = _single_engine(build_github_pat_recognizer)
        results = engine.analyze(text=f"ref: {GITHUB_SHORT_PAT}", language="en")
        results = [r for r in results if r.entity_type == "GITHUB_PAT"]
        assert len(results) == 0

    def test_github_pat_entity_label(self):
        """R07.3: entity type label is GITHUB_PAT."""
        assert "GITHUB_PAT" in build_github_pat_recognizer().supported_entities


# ---------------------------------------------------------------------------
# GITHUB_FINE_GRAINED (REQ-REC-08)
# ---------------------------------------------------------------------------

class TestGitHubFineGrained:
    """Tests for build_github_fine_grained_recognizer()."""

    def test_fine_grained_detected(self):
        """R08-A: github_pat_ + 82 char fine-grained PAT is detected."""
        engine = _single_engine(build_github_fine_grained_recognizer)
        results = engine.analyze(
            text=f"token: {GITHUB_FINE_GRAINED_PAT}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "GITHUB_FINE_GRAINED"]
        assert len(results) >= 1
        assert results[0].score >= 0.98

    def test_classic_pat_not_matched_by_fine_grained(self):
        """R08-B: classic ghp_ token does NOT match GITHUB_FINE_GRAINED."""
        engine = _single_engine(build_github_fine_grained_recognizer)
        results = engine.analyze(text=GITHUB_CLASSIC_PAT, language="en")
        results = [r for r in results if r.entity_type == "GITHUB_FINE_GRAINED"]
        assert len(results) == 0

    def test_github_fine_grained_entity_label(self):
        """R08.3: entity type label is GITHUB_FINE_GRAINED."""
        assert "GITHUB_FINE_GRAINED" in build_github_fine_grained_recognizer().supported_entities


# ---------------------------------------------------------------------------
# OPENAI_KEY (REQ-REC-09)
# ---------------------------------------------------------------------------

class TestOpenAIKey:
    """Tests for build_openai_key_recognizer()."""

    def test_key_with_context_detected(self):
        """R09-A: sk-[48 chars] with OPENAI_API_KEY context is detected."""
        engine = _single_engine(build_openai_key_recognizer)
        results = engine.analyze(
            text=f"OPENAI_API_KEY={OPENAI_KEY_VALID}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "OPENAI_KEY"]
        assert len(results) >= 1
        assert results[0].score >= 0.85

    def test_bare_sk_not_detected(self):
        """R09-B: sk-[48 chars] without openai context is NOT detected."""
        engine = _single_engine(build_openai_key_recognizer)
        results = engine.analyze(
            text=f"token: {OPENAI_KEY_VALID}",
            language="en",
            score_threshold=0.5,
        )
        results = [r for r in results if r.entity_type == "OPENAI_KEY"]
        assert len(results) == 0

    def test_anthropic_key_not_stolen(self):
        """R09-C: Anthropic sk-ant- key is NOT classified as OPENAI_KEY."""
        engine = _single_engine(build_openai_key_recognizer)
        results = engine.analyze(text=ANTHROPIC_KEY_VALID, language="en")
        results = [r for r in results if r.entity_type == "OPENAI_KEY"]
        assert len(results) == 0

    def test_openai_key_entity_label(self):
        """R09.5: entity type label is OPENAI_KEY."""
        assert "OPENAI_KEY" in build_openai_key_recognizer().supported_entities


# ---------------------------------------------------------------------------
# ANTHROPIC_KEY (REQ-REC-10)
# ---------------------------------------------------------------------------

class TestAnthropicKey:
    """Tests for build_anthropic_key_recognizer()."""

    def test_anthropic_key_detected(self):
        """R10-A: sk-ant-[93 chars] is detected with score 1.0."""
        engine = _single_engine(build_anthropic_key_recognizer)
        results = engine.analyze(
            text=f"key = {ANTHROPIC_KEY_VALID}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "ANTHROPIC_KEY"]
        assert len(results) >= 1
        assert results[0].score == 1.0

    def test_shorter_string_not_detected(self):
        """R10-B: sk-ant-short is NOT detected (suffix too short)."""
        engine = _single_engine(build_anthropic_key_recognizer)
        results = engine.analyze(text="sk-ant-short", language="en")
        results = [r for r in results if r.entity_type == "ANTHROPIC_KEY"]
        assert len(results) == 0

    def test_anthropic_key_entity_label(self):
        """R10.3: entity type label is ANTHROPIC_KEY."""
        assert "ANTHROPIC_KEY" in build_anthropic_key_recognizer().supported_entities


# ---------------------------------------------------------------------------
# SLACK_TOKEN (REQ-REC-11)
# ---------------------------------------------------------------------------

class TestSlackToken:
    """Tests for build_slack_token_recognizer()."""

    def test_slack_bot_detected(self):
        """R11-A: xoxb- prefixed Slack token is detected."""
        engine = _single_engine(build_slack_token_recognizer)
        results = engine.analyze(
            text=f"SLACK_BOT_TOKEN={SLACK_BOT_TOKEN}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "SLACK_TOKEN"]
        assert len(results) >= 1
        assert results[0].score >= 0.9

    def test_wrong_prefix_not_detected(self):
        """R11-B: xoy- prefix is NOT a Slack token."""
        engine = _single_engine(build_slack_token_recognizer)
        results = engine.analyze(text="xoyb-123456789012-abc", language="en")
        results = [r for r in results if r.entity_type == "SLACK_TOKEN"]
        assert len(results) == 0

    def test_slack_token_entity_label(self):
        """R11.3: entity type label is SLACK_TOKEN."""
        assert "SLACK_TOKEN" in build_slack_token_recognizer().supported_entities

    @pytest.mark.parametrize("prefix", ["xoxb", "xoxp", "xoxo", "xoxa", "xoxs"])
    def test_all_valid_slack_prefixes(self, prefix):
        """R11.1: all xox[bpoas] prefixes are matched."""
        engine = _single_engine(build_slack_token_recognizer)
        token = f"{prefix}-123456789012-1234567890123-abcDEF"
        results = engine.analyze(text=token, language="en")
        results = [r for r in results if r.entity_type == "SLACK_TOKEN"]
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# STRIPE_KEY (REQ-REC-12)
# ---------------------------------------------------------------------------

class TestStripeKey:
    """Tests for build_stripe_key_recognizer()."""

    def test_live_secret_detected(self):
        """R12-A: sk_live_ key is detected."""
        engine = _single_engine(build_stripe_key_recognizer)
        results = engine.analyze(
            text=f"STRIPE_SECRET_KEY={STRIPE_LIVE_SECRET}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "STRIPE_KEY"]
        assert len(results) >= 1
        assert results[0].score >= 0.9

    def test_test_publishable_detected(self):
        """R12-B: pk_test_ key is detected."""
        engine = _single_engine(build_stripe_key_recognizer)
        results = engine.analyze(text=STRIPE_TEST_PUBLISHABLE, language="en")
        results = [r for r in results if r.entity_type == "STRIPE_KEY"]
        assert len(results) >= 1
        assert results[0].score >= 0.9

    def test_stripe_key_entity_label(self):
        """R12.3: entity type label is STRIPE_KEY."""
        assert "STRIPE_KEY" in build_stripe_key_recognizer().supported_entities


# ---------------------------------------------------------------------------
# PRIVATE_KEY_BLOCK (REQ-REC-13)
# ---------------------------------------------------------------------------

class TestPrivateKeyBlock:
    """Tests for build_private_key_block_recognizer()."""

    def test_rsa_block_detected(self):
        """R13-A: RSA PRIVATE KEY block is detected."""
        engine = _single_engine(build_private_key_block_recognizer)
        results = engine.analyze(text=RSA_PRIVATE_KEY_BLOCK, language="en")
        results = [r for r in results if r.entity_type == "PRIVATE_KEY_BLOCK"]
        assert len(results) >= 1
        assert results[0].score == 1.0

    def test_ec_block_detected(self):
        """R13-B: EC PRIVATE KEY block is detected."""
        engine = _single_engine(build_private_key_block_recognizer)
        results = engine.analyze(text=EC_PRIVATE_KEY_BLOCK, language="en")
        results = [r for r in results if r.entity_type == "PRIVATE_KEY_BLOCK"]
        assert len(results) >= 1
        assert results[0].score == 1.0

    def test_public_block_not_detected(self):
        """R13-C: PUBLIC KEY block is NOT detected (no 'PRIVATE' in header)."""
        engine = _single_engine(build_private_key_block_recognizer)
        results = engine.analyze(text=PUBLIC_KEY_BLOCK, language="en")
        results = [r for r in results if r.entity_type == "PRIVATE_KEY_BLOCK"]
        assert len(results) == 0

    def test_private_key_block_entity_label(self):
        """R13.3: entity type label is PRIVATE_KEY_BLOCK."""
        assert "PRIVATE_KEY_BLOCK" in build_private_key_block_recognizer().supported_entities


# ---------------------------------------------------------------------------
# CONNECTION_STRING_PASSWORD (REQ-REC-14)
# ---------------------------------------------------------------------------

class TestConnectionStringPassword:
    """Tests for build_connection_string_password_recognizer()."""

    def test_postgres_password_detected(self):
        """R14-A: PostgreSQL connection string password is detected."""
        engine = _single_engine(build_connection_string_password_recognizer)
        results = engine.analyze(
            text=f"DB_URL={POSTGRES_CONN_STRING}",
            language="en",
        )
        results = [r for r in results if r.entity_type == "CONNECTION_STRING_PASSWORD"]
        assert len(results) >= 1

    def test_no_password_not_detected(self):
        """R14-B: PostgreSQL connection string without password is NOT detected."""
        engine = _single_engine(build_connection_string_password_recognizer)
        results = engine.analyze(text=POSTGRES_NO_PASSWORD, language="en")
        results = [r for r in results if r.entity_type == "CONNECTION_STRING_PASSWORD"]
        assert len(results) == 0

    def test_mongo_password_detected(self):
        """Triangulate: MongoDB connection string password is also detected."""
        engine = _single_engine(build_connection_string_password_recognizer)
        results = engine.analyze(text=MONGO_CONN_STRING, language="en")
        results = [r for r in results if r.entity_type == "CONNECTION_STRING_PASSWORD"]
        assert len(results) >= 1

    def test_connection_string_entity_label(self):
        """R14.2: entity type label is CONNECTION_STRING_PASSWORD."""
        assert (
            "CONNECTION_STRING_PASSWORD"
            in build_connection_string_password_recognizer().supported_entities
        )


# ---------------------------------------------------------------------------
# BEARER_TOKEN (REQ-REC-15)
# ---------------------------------------------------------------------------

class TestBearerToken:
    """Tests for build_bearer_token_recognizer()."""

    def test_auth_header_detected(self):
        """R15-A: Authorization Bearer header is detected."""
        engine = _single_engine(build_bearer_token_recognizer)
        results = engine.analyze(text=BEARER_HEADER, language="en")
        results = [r for r in results if r.entity_type == "BEARER_TOKEN"]
        assert len(results) >= 1
        assert results[0].score >= 0.85

    def test_lowercase_bearer_detected(self):
        """R15-B: lowercase 'bearer' is also detected."""
        engine = _single_engine(build_bearer_token_recognizer)
        results = engine.analyze(text=BEARER_LOWERCASE, language="en")
        results = [r for r in results if r.entity_type == "BEARER_TOKEN"]
        assert len(results) >= 1
        assert results[0].score >= 0.85

    def test_bare_string_not_detected(self):
        """R15-C: random 20+ char string without bearer prefix is NOT detected."""
        engine = _single_engine(build_bearer_token_recognizer)
        results = engine.analyze(
            text=BARE_TOKEN_NO_BEARER,
            language="en",
            score_threshold=0.5,
        )
        results = [r for r in results if r.entity_type == "BEARER_TOKEN"]
        assert len(results) == 0

    def test_bearer_token_entity_label(self):
        """R15.3: entity type label is BEARER_TOKEN."""
        assert "BEARER_TOKEN" in build_bearer_token_recognizer().supported_entities
