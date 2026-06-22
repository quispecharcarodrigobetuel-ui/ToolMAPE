from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.news.collectors.generic import GenericListCollector
from src.news.config import ensure_directories, resolve_path
from src.news.features.daily import build_daily_features
from src.news.gpt.classifier import classification_input_hash, create_classifier
from src.news.labeling.market import label_news, load_market_prices
from src.news.models import NewsItem, PipelineRun
from src.news.processing.dedup import deduplicate
from src.news.processing.normalizer import normalize_item
from src.news.storage.local import LocalStorage
from src.news.storage.supabase_client import SupabaseStorage
from src.news.utils.io import read_jsonl
from src.news.utils.logging import log_run


class NewsPipeline:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        ensure_directories(config)
        self.local = LocalStorage(config)
        self.mode = config["pipeline"]["mode"]

    def _execute(self, stage: str, operation: Callable[[PipelineRun], Any]) -> Any:
        started = time.monotonic()
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            stage=stage,
            mode=self.mode,
        )
        result = None
        try:
            result = operation(run)
        except Exception as exc:
            run.errors.append({"stage": stage, "error": str(exc)})
        finally:
            run.duration_seconds = round(time.monotonic() - started, 3)
            log_run(resolve_path(self.config, "logs") / "news_pipeline_runs.jsonl", run)
            if self.mode == "supabase":
                try:
                    SupabaseStorage().upsert_runs([run.model_dump(mode="json")])
                except Exception:
                    pass
        if run.errors and result is None:
            raise RuntimeError("; ".join(error["error"] for error in run.errors))
        return result

    def scrape(self) -> list[dict[str, Any]]:
        def operation(run: PipelineRun) -> list[dict[str, Any]]:
            existing = self.local.read("processed")
            normalized: list[NewsItem] = []
            raw_rows: list[dict[str, Any]] = []
            scraped_at = datetime.now(timezone.utc)
            for source in self.config["sources"]:
                result = GenericListCollector(source, self.config["pipeline"]).collect()
                run.news_found += len(result.items)
                for error in result.errors:
                    run.errors.append({"source": source["id"], "error": error})
                for item in result.items:
                    try:
                        normalized_item = normalize_item(item, source, scraped_at, result.method)
                        normalized.append(normalized_item)
                        raw_rows.append(normalized_item.model_dump(mode="json"))
                    except Exception as exc:
                        run.errors.append({"source": source["id"], "error": f"normalización: {exc}"})

            fresh, duplicates = deduplicate(normalized, existing)
            processed_rows = [item.model_dump(mode="json") for item in fresh]
            normalized_rows = [item.model_dump(mode="json") for item in normalized]
            run.news_new = len(fresh)
            run.news_duplicates = duplicates
            self.local.save_run("raw", run.run_id, raw_rows)
            self.local.merge_latest("raw", raw_rows, "news_id")
            self.local.save_run("processed", run.run_id, processed_rows)
            # Actualiza metadatos corregidos (por ejemplo, fechas) aunque la noticia
            # ya exista; `processed_rows` sigue representando únicamente noticias nuevas.
            self.local.merge_latest("processed", normalized_rows, "news_id")
            return processed_rows

        return self._execute("scrape", operation)

    def enrich(self) -> list[dict[str, Any]]:
        def operation(run: PipelineRun) -> list[dict[str, Any]]:
            news_rows = self.local.read("processed")
            existing = {row["news_id"]: row for row in self.local.read("enriched")}
            classifier = create_classifier(self.config)
            candidates = [
                NewsItem.model_validate(row)
                for row in news_rows
                if (
                    existing.get(row["news_id"], {}).get("enrichment_status") != "completed"
                    or existing.get(row["news_id"], {}).get("provider") != classifier.provider
                    or existing.get(row["news_id"], {}).get("model") != classifier.model
                    or existing.get(row["news_id"], {}).get("input_hash")
                    != classification_input_hash(NewsItem.model_validate(row))
                )
            ]
            enriched = [classifier.classify(item).model_dump(mode="json") for item in candidates]
            run.news_enriched = sum(row["enrichment_status"] == "completed" for row in enriched)
            for row in enriched:
                if row["error"]:
                    run.errors.append({"news_id": row["news_id"], "error": row["error"]})
            self.local.save_run("enriched", run.run_id, enriched)
            self.local.merge_latest("enriched", enriched, "news_id")
            return enriched

        return self._execute("enrich", operation)

    def label(self) -> list[dict[str, Any]]:
        def operation(run: PipelineRun) -> list[dict[str, Any]]:
            labels = label_news(self.local.read("processed"), load_market_prices(self.config), self.config)
            self.local.save_run("labeled", run.run_id, labels)
            self.local.merge_latest("labeled", labels, "news_id")
            return labels

        return self._execute("label", operation)

    def features(self) -> list[dict[str, Any]]:
        def operation(run: PipelineRun) -> list[dict[str, Any]]:
            rows = build_daily_features(self.local.read("processed"), self.local.read("enriched"))
            self.local.save_features(rows)
            return rows

        return self._execute("features", operation)

    def publish(self) -> dict[str, int]:
        def operation(run: PipelineRun) -> dict[str, int]:
            storage = SupabaseStorage()
            sources = [
                {
                    "source_id": source["id"],
                    "name": source["name"],
                    "url": source["url"],
                    "expected_language": source.get("expected_language"),
                    "reliability_weight": source.get("reliability_weight", 1),
                    "suggested_frequency_minutes": source.get("suggested_frequency_minutes", 60),
                    "is_active": True,
                }
                for source in self.config["sources"]
            ]
            enriched = []
            for row in self.local.read("enriched"):
                flattened = {
                    key: value
                    for key, value in row.items()
                    if key not in ("classification", "input_hash")
                }
                flattened.update(row.get("classification") or {})
                enriched.append(flattened)
            features_path = resolve_path(self.config, "features") / "latest.jsonl"
            logs_path = resolve_path(self.config, "logs") / "news_pipeline_runs.jsonl"
            counts = {
                "sources": storage.upsert_sources(sources),
                "raw": storage.upsert_raw(self.local.read("processed")),
                "enriched": storage.upsert_enriched(enriched),
                "labels": storage.upsert_labels(self.local.read("labeled")),
                "features": storage.upsert_features(read_jsonl(features_path)),
                "runs": storage.upsert_runs(read_jsonl(logs_path)),
            }
            return counts

        return self._execute("publish", operation)

    def all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, stage in (
            ("scrape", self.scrape),
            ("enrich", self.enrich),
            ("label", self.label),
            ("features", self.features),
        ):
            try:
                value = stage()
                results[name] = len(value) if isinstance(value, list) else value
            except Exception as exc:
                results[name] = {"status": "skipped_or_failed", "error": str(exc)}
        if self.mode == "supabase":
            try:
                results["publish"] = self.publish()
            except Exception as exc:
                results["publish"] = {"status": "failed", "error": str(exc)}
        return results
