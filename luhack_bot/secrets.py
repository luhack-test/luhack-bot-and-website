import os

from dotenv import load_dotenv

load_dotenv()


def env_fail(var: str):
    """Warn about an empty env var."""
    print(f"Warning, missing env var: {var}")
    exit(1)

def ensure_env(key: str):
    return os.getenv(key) or env_fail(key)

db_url = os.getenv("DB_URL")

bot_client_token = ensure_env("BOT_TOKEN")

email_encryption_key = ensure_env("EMAIL_KEY")

signing_secret = ensure_env("TOKEN_SECRET")

prospective_token = ensure_env("PROSPECTIVE_TOKEN")

tailnet = ensure_env("TS_TAILNET")

tailscale_domain_suffix = ensure_env("TS_DOMAIN_SUFFIX")
