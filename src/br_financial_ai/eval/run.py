from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from subprocess import CalledProcessError, TimeoutExpired, run

from br_financial_ai.core.settings import Settings, get_settings
from br_financial_ai.eval.profile import EvalProfile

GitMetadataReader = Callable[[], tuple[str | None, str | None]]


@dataclass(frozen=True, slots=True)
class EvalRun:
    id: str
    timestamp: datetime
    profile: EvalProfile
    model_provider: str | None
    model_name: str | None
    git_commit: str | None
    git_branch: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.astimezone(UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ",
            ),
            "profile": self.profile.value,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
        }


def run_id_from_timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H%M%SZ")


def parse_eval_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_git_metadata() -> tuple[str | None, str | None]:
    commit = _git_output(["git", "rev-parse", "HEAD"])
    branch = _git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        branch = None
    return commit, branch


def build_eval_run(
    *,
    profile: EvalProfile,
    timestamp: datetime | None = None,
    settings: Settings | None = None,
    git_reader: GitMetadataReader | None = None,
    run_id: str | None = None,
) -> EvalRun:
    resolved = (timestamp or datetime.now(UTC)).astimezone(UTC)
    app_settings = settings or get_settings()
    reader = git_reader or read_git_metadata
    commit, branch = reader()
    return EvalRun(
        id=run_id or run_id_from_timestamp(resolved),
        timestamp=resolved,
        profile=profile,
        model_provider=app_settings.llm_provider,
        model_name=app_settings.llm_model,
        git_commit=commit,
        git_branch=branch,
    )


def _git_output(command: list[str]) -> str | None:
    try:
        completed = run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (
        FileNotFoundError,
        CalledProcessError,
        TimeoutExpired,
        OSError,
    ):
        return None

    value = completed.stdout.strip()
    return value or None
