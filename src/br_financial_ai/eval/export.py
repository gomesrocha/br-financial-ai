from pathlib import Path
from shutil import copy2

from br_financial_ai.eval.history import HISTORY_DIRNAME, INDEX_FILENAME, history_dir

FRONTEND_EVALS_DIRNAME = "evals"


def default_frontend_public_dir(repo_root: Path) -> Path:
    return repo_root.parent / "br-financial-ai-web" / "public"


def export_eval_artifacts(
    reports_dir: Path,
    frontend_public_dir: Path | None = None,
) -> Path | None:
    if frontend_public_dir is None:
        repo_root = reports_dir.parent.parent
        frontend_public_dir = default_frontend_public_dir(repo_root)
    if not frontend_public_dir.exists():
        return None

    destination = frontend_public_dir / FRONTEND_EVALS_DIRNAME
    destination.mkdir(parents=True, exist_ok=True)
    history_destination = destination / HISTORY_DIRNAME
    history_destination.mkdir(parents=True, exist_ok=True)

    latest = reports_dir / "latest.json"
    if latest.exists():
        copy2(latest, destination / "latest.json")
        copy2(latest, frontend_public_dir / "evaluation-summary.json")

    index = history_dir(reports_dir) / INDEX_FILENAME
    if index.exists():
        copy2(index, destination / "index.json")

    for path in history_dir(reports_dir).glob("*.json"):
        if path.name == INDEX_FILENAME:
            continue
        copy2(path, history_destination / path.name)

    return destination
