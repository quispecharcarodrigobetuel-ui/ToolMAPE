from __future__ import annotations

import os
import time
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import requests

from src.news.gpt.prompt import SYSTEM_PROMPT
from src.news.models import EnrichedNews, GPTClassification, NewsItem


def _user_content(item: NewsItem) -> str:
    return (
        f"Fuente: {item.source_name}\n"
        f"Fecha: {item.published_at.isoformat() if item.published_at else 'desconocida'}\n"
        f"Título: {item.title}\n"
        f"Resumen: {item.summary or 'No disponible'}\n"
        f"Categoría: {item.category or 'No disponible'}"
    )


def classification_input_hash(item: NewsItem) -> str:
    payload = {
        "source_name": item.source_name,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "title": item.title,
        "summary": item.summary,
        "category": item.category,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class NewsClassifier(ABC):
    provider: str
    model: str

    def __init__(self, config: dict[str, Any]):
        pipeline = config["pipeline"]
        self.max_retries = int(pipeline.get("llm_max_retries", 3))
        self.retry_base = float(pipeline.get("llm_retry_base_seconds", 2))

    def classify(self, item: NewsItem) -> EnrichedNews:
        error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                classification = self._classify_once(item)
                return EnrichedNews(
                    news_id=item.news_id,
                    enriched_at=datetime.now(timezone.utc),
                    provider=self.provider,
                    model=self.model,
                    input_hash=classification_input_hash(item),
                    enrichment_status="completed",
                    classification=classification,
                )
            except Exception as exc:
                error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_base * (2**attempt))
        return EnrichedNews(
            news_id=item.news_id,
            enriched_at=datetime.now(timezone.utc),
            provider=self.provider,
            model=self.model,
            input_hash=classification_input_hash(item),
            enrichment_status="pending",
            error=str(error),
        )

    @abstractmethod
    def _classify_once(self, item: NewsItem) -> GPTClassification:
        raise NotImplementedError


class OllamaClassifier(NewsClassifier):
    provider = "ollama"

    def __init__(self, config: dict[str, Any], session: requests.Session | None = None):
        super().__init__(config)
        pipeline = config["pipeline"]
        self.model = pipeline.get("ollama_model", "llama3:latest")
        self.base_url = pipeline.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        self.timeout = int(pipeline.get("llm_timeout_seconds", 300))
        self.temperature = float(pipeline.get("llm_temperature", 0))
        self.seed = int(pipeline.get("llm_seed", 42))
        self.keep_alive = pipeline.get("llm_keep_alive", "10m")
        self.session = session or requests.Session()

    def _classify_once(self, item: NewsItem) -> GPTClassification:
        response = self.session.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _user_content(item)},
                ],
                "format": GPTClassification.model_json_schema(),
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": self.temperature,
                    "seed": self.seed,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("message", {}).get("content")
        if not content:
            raise RuntimeError(payload.get("error") or "Ollama devolvió una respuesta vacía")
        return GPTClassification.model_validate_json(content)


class OpenAIClassifier(NewsClassifier):
    provider = "openai"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.model = config["pipeline"].get("openai_model", "gpt-5.5")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no está configurada")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def _classify_once(self, item: NewsItem) -> GPTClassification:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_content(item)},
            ],
            text_format=GPTClassification,
        )
        if response.output_parsed is None:
            raise RuntimeError("La respuesta no contiene output_parsed")
        return response.output_parsed


def create_classifier(config: dict[str, Any]) -> NewsClassifier:
    provider = config["pipeline"].get("llm_provider", "ollama").lower()
    if provider == "ollama":
        return OllamaClassifier(config)
    if provider == "openai":
        return OpenAIClassifier(config)
    raise ValueError("NEWS_LLM_PROVIDER debe ser 'ollama' u 'openai'")


# Alias temporal para integraciones anteriores.
GPTClassifier = OpenAIClassifier
