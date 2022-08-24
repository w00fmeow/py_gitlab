from pathlib import Path

home_dir = Path.home()

project_dir = home_dir / '.py_gitlab'

project_dir.mkdir(parents=True, exist_ok=True)

PROJECT_DIR = project_dir.resolve()
