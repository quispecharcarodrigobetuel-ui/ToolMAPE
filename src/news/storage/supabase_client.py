from __future__ import annotations

import os
from typing import Any


class SupabaseStorage:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("Instala la dependencia 'supabase'") from exc
        self.client = create_client(url, key)

    def _upsert(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> int:
        if not rows:
            return 0
        self.client.table(table).upsert(rows, on_conflict=on_conflict).execute()
        return len(rows)

    def upsert_sources(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("news_sources", rows, "source_id")

    def upsert_raw(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("news_raw", rows, "news_id")

    def upsert_enriched(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("news_gpt_enriched", rows, "news_id")

    def upsert_labels(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("news_market_labels", rows, "news_id")

    def upsert_features(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("daily_news_features", rows, "feature_date")

    def upsert_runs(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert("news_pipeline_runs", rows, "run_id")
