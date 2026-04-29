"""Load OPENAI_API_KEY / SUPABASE_DB_URL before pytest collects tests so that
`@pytest.mark.skipif(not os.environ.get(...))` markers see them."""

from src.cli import load_secrets

load_secrets()
