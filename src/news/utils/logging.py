from __future__ import annotations

from pathlib import Path

from src.news.models import PipelineRun
from src.news.utils.io import write_jsonl


def log_run(path: Path, run: PipelineRun) -> None:
    write_jsonl(path, [run.model_dump(mode="json")], append=True)
