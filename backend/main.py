from pathlib import Path
import sys

import uvicorn


def _ensure_project_root_on_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


if __name__ == "__main__":
    _ensure_project_root_on_path()
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
