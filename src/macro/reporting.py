from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.macro.fred_config import macro_path


def write_fred_report(
    config: dict[str, Any],
    raw_by_series: dict[str, pd.DataFrame],
    features: pd.DataFrame | None = None,
    warnings: list[str] | None = None,
) -> None:
    counts = {
        series_id: len(frame)
        for series_id, frame in raw_by_series.items()
    }
    dates = [
        pd.to_datetime(frame["observation_date"], errors="coerce")
        for frame in raw_by_series.values()
        if not frame.empty
    ]
    start = min((series.min() for series in dates), default=None)
    end = max((series.max() for series in dates), default=None)
    lines = [
        "# Reporte macroeconómico FRED",
        "",
        f"- Ejecución: {datetime.now(timezone.utc).isoformat()}",
        f"- Rango observado: {start.date() if start is not None else 'sin datos'} a "
        f"{end.date() if end is not None else 'sin datos'}",
        f"- Features diarias: {len(features) if features is not None else 0}",
        "",
        "## Series",
        "",
        "| Serie | Variable | Frecuencia | Observaciones | Faltantes | Propósito |",
        "|---|---|---:|---:|---:|---|",
    ]
    for series_id, metadata in config["series"].items():
        frame = raw_by_series.get(series_id, pd.DataFrame())
        missing = int(frame["value"].isna().sum()) if "value" in frame else 0
        lines.append(
            f"| {series_id} | {metadata['name']} | {metadata['frequency']} | "
            f"{counts.get(series_id, 0)} | {missing} | {metadata['description']} |"
        )
    lines.extend(
        [
            "",
            "## Integración",
            "",
            "Las variables se unen por fecha como `daily_market_features + "
            "daily_macro_features + daily_news_features` para reentrenar el modelo del precio "
            "del oro en soles por gramo.",
            "",
            "## Limitaciones",
            "",
            "- CPI y FEDFUNDS se propagan desde su fecha de observación. Esta simplificación no "
            "modela todavía la fecha real de publicación y puede introducir un desfase temporal.",
            "- FRED puede revisar observaciones históricas; la actualización vuelve a consultar "
            "una ventana reciente configurable.",
            "- El macro_stress_score es exploratorio y debe calibrarse contra validación fuera de muestra.",
        ]
    )
    for warning in warnings or []:
        lines.append(f"- {warning}")
    path = macro_path(config, "reports") / "fred_macro_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
