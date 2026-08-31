"""Keep automated tests deterministic and independent of local live-provider settings."""

import os

os.environ["AI_PROVIDER"] = "stub"
os.environ["AI_API_KEY"] = ""
os.environ["AI_FALLBACK_PROVIDER"] = ""

_test_database_url = os.environ.get("FINTRACE_TEST_DATABASE_URL")
if _test_database_url:
    os.environ.setdefault("STORAGE_BACKEND", "postgres")
    os.environ.setdefault("DATABASE_URL", _test_database_url)
