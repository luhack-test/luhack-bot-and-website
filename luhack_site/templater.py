from starlette.templating import Jinja2Templates

from pathlib import Path

root_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(root_dir / "templates"))
