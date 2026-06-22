from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def load_fred_config() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    with (ROOT / "config" / "macro_fred.yaml").open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    config["mode"] = os.getenv("MACRO_PIPELINE_MODE", config.get("mode", "local"))
    config["root"] = ROOT
    return config


def macro_path(config: dict[str, Any], key: str) -> Path:
    return Path(config["root"]) / config["paths"][key]


def ensure_macro_directories(config: dict[str, Any]) -> None:
    for key in ("raw", "processed", "logs", "reports"):
        macro_path(config, key).mkdir(parents=True, exist_ok=True)
    macro_path(config, "final_features").parent.mkdir(parents=True, exist_ok=True)
