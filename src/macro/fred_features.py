from __future__ import annotations

from typing import Any

import pandas as pd


LEVEL_COLUMNS = [
    "us_10y_yield",
    "us_2y_yield",
    "us_10y_real_yield",
    "fed_funds_rate",
    "us_cpi",
    "broad_usd_index",
    "sp500",
    "high_yield_spread",
]

DERIVED_COLUMNS = [
    "yield_curve_10y_2y",
    "real_yield_change_1d",
    "real_yield_change_5d",
    "real_yield_change_20d",
    "nominal_10y_change_1d",
    "nominal_10y_change_5d",
    "broad_usd_return_1d",
    "broad_usd_return_5d",
    "sp500_return_1d",
    "sp500_return_5d",
    "credit_stress_change_1d",
    "credit_stress_change_5d",
    "cpi_yoy",
    "cpi_mom",
    "fed_funds_change",
    "macro_stress_score",
]


def build_macro_dataset(
    raw_by_series: dict[str, pd.DataFrame], config: dict[str, Any]
) -> pd.DataFrame:
    """Alinea observaciones a calendario diario usando únicamente forward fill."""
    native: dict[str, pd.Series] = {}
    for series_id, frame in raw_by_series.items():
        if frame.empty:
            continue
        name = config["series"][series_id]["name"]
        clean = frame.copy()
        clean["observation_date"] = pd.to_datetime(clean["observation_date"], errors="coerce")
        clean["value"] = pd.to_numeric(clean["value"], errors="coerce")
        native[name] = (
            clean.dropna(subset=["observation_date"])
            .drop_duplicates("observation_date", keep="last")
            .set_index("observation_date")["value"]
            .sort_index()
        )
    if not native:
        return pd.DataFrame(columns=["feature_date", *LEVEL_COLUMNS])

    start = min(series.index.min() for series in native.values())
    configured_end = pd.Timestamp(config.get("end_date") or pd.Timestamp.today().date())
    observed_end = max(series.index.max() for series in native.values())
    end = min(configured_end, max(observed_end, configured_end))
    calendar = pd.date_range(start=start, end=end, freq="D")
    result = pd.DataFrame(index=calendar)
    for name in LEVEL_COLUMNS:
        series = native.get(name)
        result[name] = series.reindex(calendar).ffill() if series is not None else pd.NA

    # CPI y Fed se calculan en frecuencia mensual antes de propagar, evitando que
    # "12" signifique doce días después del forward fill.
    cpi = native.get("us_cpi")
    if cpi is not None:
        result["cpi_yoy"] = cpi.pct_change(12, fill_method=None).reindex(calendar).ffill()
        result["cpi_mom"] = cpi.pct_change(1, fill_method=None).reindex(calendar).ffill()
    else:
        result["cpi_yoy"] = pd.NA
        result["cpi_mom"] = pd.NA
    fed = native.get("fed_funds_rate")
    result["fed_funds_change"] = (
        fed.diff().reindex(calendar).ffill() if fed is not None else pd.NA
    )
    return result.rename_axis("feature_date").reset_index()


def build_macro_features(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(columns=["feature_date", *LEVEL_COLUMNS, *DERIVED_COLUMNS])
    frame = dataset.copy().sort_values("feature_date")
    frame["yield_curve_10y_2y"] = frame["us_10y_yield"] - frame["us_2y_yield"]
    frame["real_yield_change_1d"] = frame["us_10y_real_yield"].diff(1)
    frame["real_yield_change_5d"] = frame["us_10y_real_yield"].diff(5)
    frame["real_yield_change_20d"] = frame["us_10y_real_yield"].diff(20)
    frame["nominal_10y_change_1d"] = frame["us_10y_yield"].diff(1)
    frame["nominal_10y_change_5d"] = frame["us_10y_yield"].diff(5)
    frame["broad_usd_return_1d"] = frame["broad_usd_index"].pct_change(1, fill_method=None)
    frame["broad_usd_return_5d"] = frame["broad_usd_index"].pct_change(5, fill_method=None)
    frame["sp500_return_1d"] = frame["sp500"].pct_change(1, fill_method=None)
    frame["sp500_return_5d"] = frame["sp500"].pct_change(5, fill_method=None)
    frame["credit_stress_change_1d"] = frame["high_yield_spread"].diff(1)
    frame["credit_stress_change_5d"] = frame["high_yield_spread"].diff(5)

    # Primera versión modificable: promedio de z-scores móviles (solo pasado y presente)
    # de spread HY al alza, S&P a la baja, USD al alza y rendimiento real al alza.
    components = pd.DataFrame(
        {
            "credit": frame["credit_stress_change_5d"],
            "equity": -frame["sp500_return_5d"],
            "usd": frame["broad_usd_return_5d"],
            "real_yield": frame["real_yield_change_5d"],
        },
        index=frame.index,
    )
    standardized = pd.DataFrame(index=frame.index)
    for column in components:
        rolling = components[column].rolling(252, min_periods=20)
        standardized[column] = (components[column] - rolling.mean()) / rolling.std()
    frame["macro_stress_score"] = standardized.mean(axis=1, skipna=True)
    frame["feature_date"] = pd.to_datetime(frame["feature_date"]).dt.date
    return frame
