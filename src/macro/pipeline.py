from __future__ import annotations

import time
import uuid
from datetime import date, datetime, timezone
from typing import Any, Callable

import pandas as pd

from src.macro.fred_client import FredClient
from src.macro.fred_config import ensure_macro_directories, macro_path
from src.macro.fred_features import build_macro_dataset, build_macro_features
from src.macro.fred_storage import FredLocalStorage, FredSupabaseStorage
from src.macro.integration import build_final_feature_dataset
from src.macro.reporting import write_fred_report


class FredPipeline:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        ensure_macro_directories(config)
        self.local = FredLocalStorage(config)

    def _run(self, stage: str, operation: Callable[[dict[str, Any]], Any]) -> Any:
        started = time.monotonic()
        log = {
            "run_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "stage": stage,
            "series_requested": list(self.config["series"]),
            "series_succeeded": [],
            "series_failed": [],
            "start_date": self.config["start_date"],
            "end_date": self.config.get("end_date") or date.today().isoformat(),
            "observations_downloaded": 0,
            "features_generated": 0,
            "mode": self.config["mode"],
            "duration_seconds": 0,
            "errors": [],
        }
        result = None
        try:
            result = operation(log)
        except Exception as exc:
            log["errors"].append({"stage": stage, "error": str(exc)})
        finally:
            log["duration_seconds"] = round(time.monotonic() - started, 3)
            self.local.append_log(log)
        if result is None and log["errors"]:
            raise RuntimeError("; ".join(error["error"] for error in log["errors"]))
        return result

    def download(self) -> dict[str, int]:
        def operation(log: dict[str, Any]) -> dict[str, int]:
            client = FredClient(self.config)
            counts: dict[str, int] = {}
            for series_id in self.config["series"]:
                try:
                    path = self.local.raw_path(series_id)
                    start = client.incremental_start(path)
                    incoming = client.download_series(series_id, start, client.configured_end())
                    combined = self.local.merge_raw(series_id, incoming)
                    counts[series_id] = len(combined)
                    log["series_succeeded"].append(series_id)
                    log["observations_downloaded"] += len(incoming)
                except Exception as exc:
                    log["series_failed"].append(series_id)
                    log["errors"].append({"series_id": series_id, "error": str(exc)})
            if not log["series_succeeded"]:
                raise RuntimeError("No se pudo descargar ninguna serie FRED")
            write_fred_report(self.config, self._raw_frames())
            return counts

        return self._run("fred-download", operation)

    def _raw_frames(self) -> dict[str, pd.DataFrame]:
        return {
            series_id: self.local.read_raw(series_id)
            for series_id in self.config["series"]
            if self.local.raw_path(series_id).exists()
        }

    def features(self) -> pd.DataFrame:
        def operation(log: dict[str, Any]) -> pd.DataFrame:
            raw = self._raw_frames()
            dataset = build_macro_dataset(raw, self.config)
            features = build_macro_features(dataset)
            self.local.save_processed("fred_macro_dataset.csv", dataset)
            self.local.save_processed("daily_macro_features.csv", features)
            final, warnings = build_final_feature_dataset(self.config)
            log["features_generated"] = len(features)
            write_fred_report(self.config, raw, features, warnings)
            return features

        return self._run("fred-features", operation)

    def publish(self) -> dict[str, int]:
        def operation(log: dict[str, Any]) -> dict[str, int]:
            storage = FredSupabaseStorage()
            metadata = [
                {
                    "series_id": series_id,
                    "name": item["name"],
                    "description": item["description"],
                    "frequency": item["frequency"],
                    "source": "FRED",
                    "is_active": True,
                }
                for series_id, item in self.config["series"].items()
            ]
            observations: list[dict[str, Any]] = []
            for frame in self._raw_frames().values():
                observations.extend(frame.to_dict(orient="records"))
            features_path = macro_path(self.config, "processed") / "daily_macro_features.csv"
            features = pd.read_csv(features_path).to_dict(orient="records")
            return {
                "metadata": storage.upsert_metadata(metadata),
                "observations": storage.upsert_observations(observations),
                "features": storage.upsert_features(features),
            }

        return self._run("fred-publish", operation)

    def all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, action in (("download", self.download), ("features", self.features)):
            try:
                value = action()
                results[name] = len(value) if isinstance(value, pd.DataFrame) else value
            except Exception as exc:
                results[name] = {"status": "failed", "error": str(exc)}
        if self.config["mode"] == "supabase":
            try:
                results["publish"] = self.publish()
            except Exception as exc:
                results["publish"] = {"status": "failed", "error": str(exc)}
        return results
