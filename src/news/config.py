from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    config = deepcopy(_load_yaml(ROOT / "config" / "news_pipeline.yaml"))
    config.update(_load_yaml(ROOT / "config" / "news_sources.yaml"))
    pipeline = config.setdefault("pipeline", {})
    pipeline["mode"] = os.getenv("NEWS_PIPELINE_MODE", pipeline.get("mode", "local"))
    pipeline["market_prices_path"] = os.getenv(
        "NEWS_MARKET_PRICES_PATH", pipeline.get("market_prices_path", "data/market/market_prices.csv")
    )
    pipeline["llm_provider"] = os.getenv(
        "NEWS_LLM_PROVIDER", pipeline.get("llm_provider", "ollama")
    ).lower()
    pipeline["ollama_base_url"] = os.getenv(
        "OLLAMA_BASE_URL", pipeline.get("ollama_base_url", "http://localhost:11434")
    ).rstrip("/")
    pipeline["ollama_model"] = os.getenv(
        "OLLAMA_MODEL", pipeline.get("ollama_model", "llama3:latest")
    )
    config["root"] = ROOT
    return config


def resolve_path(config: dict[str, Any], key: str) -> Path:
    return Path(config["root"]) / config["paths"][key]


def ensure_directories(config: dict[str, Any]) -> None:
    for key in ("raw", "processed", "enriched", "labeled", "features", "logs", "reports"):
        resolve_path(config, key).mkdir(parents=True, exist_ok=True)
