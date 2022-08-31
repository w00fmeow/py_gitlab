from pathlib import Path

home_dir = Path.home()

project_dir = home_dir / '.py_gitlab'

logs_dir = project_dir / 'logs'

project_dir.mkdir(parents=True, exist_ok=True)

logs_dir.mkdir(parents=True, exist_ok=True)

PROJECT_DIR = project_dir.resolve()
LOGS_DIR = logs_dir.resolve()
