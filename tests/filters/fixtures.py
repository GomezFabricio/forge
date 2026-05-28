"""Shared synthetic test fixtures for forge.filters tests.

All values in this module are SYNTHETIC and have no relation to real persons,
accounts, or credentials. CUITs and CBUs use valid checksums generated
algorithmically. AWS, GitHub, and other token fixtures are taken from official
documentation examples or constructed from non-deployed random character
sequences.

CUIT mod-11 checksum algorithm (AFIP):
  weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2] applied to first 10 digits
  check = (11 - (sum % 11)) % 11; if check == 10 -> CUIT invalid

CBU two-block checksum algorithm (BCRA):
  block1: first 7 digits with weights [3,1,7,9,3,1,7], check = (10 - sum%10) % 10
  block2: digits 8-20 (13 digits) with weights [9,1,7,3,9,1,7,3,9,1,7,3,9],
          check = (10 - sum%10) % 10
"""

# ---------------------------------------------------------------------------
# CUIT — Argentine tax ID (XX-XXXXXXXX-X), checksum via mod-11
# Computed with AFIP weights [5,4,3,2,7,6,5,4,3,2]:
#   20-12345678-6  (total=148, rem=5, check=6)
#   20-33333333-4  (verified)
#   20-55555555-6  (verified)
#   20-77777777-8  (verified)
# Invalid: 20-12345678-9 (bad check digit — valid check is 6)
# ---------------------------------------------------------------------------
CUIT_VALID_1 = "20-12345678-6"
CUIT_VALID_2 = "20-33333333-4"
CUIT_VALID_3 = "20-55555555-6"
CUIT_INVALID_CHECKSUM = "20-12345678-9"  # valid check digit would be 6
CUIT_RAW_NO_FORMAT = "201234567891"  # no hyphens — must NOT match

# ---------------------------------------------------------------------------
# CBU — Argentine bank account code, 22 digits, two-block checksum
# Generated with BCRA weights (see module docstring):
#   0720461488000056459791 — valid, both blocks pass
#   0720461488000056459792 — tampered last digit (valid block1, invalid block2)
# ---------------------------------------------------------------------------
CBU_VALID = "0720461488000056459791"
CBU_INVALID_CHECKSUM = "0720461488000056459792"  # last digit tampered
CBU_TOO_SHORT = "072046148800005645979"  # 21 digits

# ---------------------------------------------------------------------------
# AWS credentials — from official AWS documentation (public examples)
# These are explicitly listed as example values in AWS docs and are NOT active.
# ---------------------------------------------------------------------------
AWS_ACCESS_KEY_EXAMPLE = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY_EXAMPLE = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# ---------------------------------------------------------------------------
# GitHub tokens — synthetic, not deployed
# ghp_ + exactly 36 alphanumeric = classic PAT format
# github_pat_ + exactly 82 alphanumeric/underscore = fine-grained PAT format
# ---------------------------------------------------------------------------
GITHUB_CLASSIC_PAT = "ghp_1234567890abcdefghij1234567890abcdef"  # 36 chars after ghp_
GITHUB_FINE_GRAINED_PAT = "github_pat_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w3X4y5Z6a7" + "_" * 28
GITHUB_SHORT_PAT = "ghp_short"  # wrong length — must NOT match

# ---------------------------------------------------------------------------
# JWT — dummy tokens with fake claims (synthetic, no real signing key)
# Three base64url segments, each >= 10 chars
# ---------------------------------------------------------------------------
JWT_VALID = (
    "eyJhbGciOiJIUzI1NiJ9"
    ".eyJzdWIiOiJ1c2VyMSJ9"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
JWT_IN_CODE = (
    "eyJhbGciOiJIUzI1NiJ9"
    ".eyJzdWIiOiJ0ZXN0In0"
    ".abc123def456ghi789jkl"
)
JWT_TWO_SEGMENT = "example.com"  # only 2 segments — must NOT match
JWT_SHORT_SEGMENTS = "ab.cd.ef"  # segments < 10 chars — must NOT match
JWT_VERSION_STRING = "3.10"  # not a JWT

# ---------------------------------------------------------------------------
# OpenAI API key — synthetic, not deployed
# Format: sk-[48 alphanumeric chars]
# Base score 0.4 (below threshold) — fires only with context word
# ---------------------------------------------------------------------------
OPENAI_KEY_VALID = "sk-aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789aBcDeFgHiJkL"  # 48 chars after sk-

# ---------------------------------------------------------------------------
# Anthropic API key — synthetic, not deployed
# Format: sk-ant-[93 alphanumeric/hyphen chars]
# ---------------------------------------------------------------------------
ANTHROPIC_KEY_VALID = "sk-ant-" + "api03-" + "x" * 87  # 93 chars after sk-ant-

# ---------------------------------------------------------------------------
# Slack token — synthetic, NOT a real token (avoids GitHub secret scanning)
# ---------------------------------------------------------------------------
SLACK_BOT_TOKEN = "xoxb-EXAMPLENOTREAL-EXAMPLENOTREAL-ExampleNotRealForTestsOnly0000"

# ---------------------------------------------------------------------------
# Stripe keys — synthetic, NOT real tokens (avoids GitHub secret scanning)
# ---------------------------------------------------------------------------
STRIPE_LIVE_SECRET = "sk_live_EXAMPLENOTREALNotForActualUseTests0000"
STRIPE_TEST_PUBLISHABLE = "pk_test_EXAMPLENOTREALNotForActualUseTests0000"

# ---------------------------------------------------------------------------
# RSA/EC private key blocks — synthetic (not real private keys)
# ---------------------------------------------------------------------------
RSA_PRIVATE_KEY_BLOCK = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4PAtl5synthetic==\n"
    "-----END RSA PRIVATE KEY-----"
)
EC_PRIVATE_KEY_BLOCK = (
    "-----BEGIN EC PRIVATE KEY-----\n"
    "MHQCAQEEIBkgsynthetic==\n"
    "-----END EC PRIVATE KEY-----"
)
PUBLIC_KEY_BLOCK = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQsynthetic==\n"
    "-----END PUBLIC KEY-----"
)

# ---------------------------------------------------------------------------
# Connection strings — synthetic hosts and passwords
# ---------------------------------------------------------------------------
POSTGRES_CONN_STRING = "postgresql://user:secretpassword@host:5432/dbname"
POSTGRES_NO_PASSWORD = "postgresql://host:5432/dbname"
MONGO_CONN_STRING = "mongodb://user:mongosecret@localhost:27017/mydb"

# ---------------------------------------------------------------------------
# Bearer tokens — synthetic
# ---------------------------------------------------------------------------
BEARER_HEADER = "Authorization: Bearer abc123def456ghi789jkl000xyz"
BEARER_LOWERCASE = "authorization: bearer abc123def456ghi789jkl000xyz"
BARE_TOKEN_NO_BEARER = "key: abc123def456ghi789jkl000xyz"
