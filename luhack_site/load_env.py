from pathlib import Path

from dotenv import load_dotenv

root_dir = Path(__file__).parent

load_dotenv(root_dir.parent)
