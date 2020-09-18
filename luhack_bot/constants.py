import yarl
import os

from dotenv import load_dotenv

load_dotenv()


def env_fail(var: str):
    """Warn about an empty env var."""
    print(f"Warning, missing env var: {var}")
    exit(1)

luhack_guild_id = 485103891298385923
potential_luhacker_role_id = 486250289691754496
prospective_luhacker_role_id = 588429073018126336
verified_luhacker_role_id = 486249689050644480
disciple_role_id = 506420426419732499
furry_master_cyber_wizard_role_id = 502203959239245854
master_cyber_wizard_role_id = 502197689434374144
trusted_role_ids = {
    disciple_role_id,
    furry_master_cyber_wizard_role_id,
    master_cyber_wizard_role_id,
}
bot_log_channel_id = 588443109994528816
inner_magic_circle_id = 631618075254325257
writeups_base_url = yarl.URL("https://scc-luhack.lancs.ac.uk/writeups")

from_email_address = os.getenv("FROM_EMAIL_ADDRESS") or env_fail("FROM_EMAIL_ADDRESS")
is_test_mode = (os.getenv("TEST_MODE") or "0") == "1"
