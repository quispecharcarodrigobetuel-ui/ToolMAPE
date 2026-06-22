from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from src.macro.fred_client import FredClient
from src.macro.fred_features import build_macro_dataset, build_macro_features


def sample_config():
    return {
        "start_date": "2003-01-01",
        "end_date": "2024-02-05",
        "request_retries": 1,
        "series": {
            "DGS10": {"name": "us_10y_yield", "frequency": "daily"},
            "DGS2": {"name": "us_2y_yield", "frequency": "daily"},
            "DFII10": {"name": "us_10y_real_yield", "frequency": "daily"},
            "FEDFUNDS": {"name": "fed_funds_rate", "frequency": "monthly"},
            "CPIAUCSL": {"name": "us_cpi", "frequency": "monthly"},
            "DTWEXBGS": {"name": "broad_usd_index", "frequency": "daily"},
            "SP500": {"name": "sp500", "frequency": "daily"},
            "BAMLH0A0HYM2": {"name": "high_yield_spread", "frequency": "daily"},
        },
    }


def frame(series_id, dates, values):
    return pd.DataFrame(
        {
            "series_id": series_id,
            "observation_date": dates,
            "value": values,
            "realtime_start": dates,
            "realtime_end": dates,
        }
    )


def test_fred_dot_becomes_nan():
    result = FredClient._to_frame(
        "DGS10",
        [
            {
                "date": "2024-01-01",
                "value": ".",
                "realtime_start": "2024-01-02",
                "realtime_end": "2024-01-02",
            }
        ],
    )
    assert pd.isna(result.loc[0, "value"])


def test_monthly_values_are_forward_filled_without_backfill():
    config = sample_config()
    raw = {
        "CPIAUCSL": frame(
            "CPIAUCSL",
            pd.date_range("2023-01-01", periods=13, freq="MS"),
            list(range(100, 113)),
        ),
        "FEDFUNDS": frame(
            "FEDFUNDS", ["2024-01-01", "2024-02-01"], [5.25, 5.5]
        ),
    }
    dataset = build_macro_dataset(raw, config)
    dataset["feature_date"] = pd.to_datetime(dataset["feature_date"])
    jan_31 = dataset.loc[dataset["feature_date"] == "2024-01-31"].iloc[0]
    feb_01 = dataset.loc[dataset["feature_date"] == "2024-02-01"].iloc[0]
    assert jan_31["fed_funds_rate"] == pytest.approx(5.25)
    assert feb_01["fed_funds_rate"] == pytest.approx(5.5)
    assert feb_01["fed_funds_change"] == pytest.approx(0.25)
    assert feb_01["cpi_yoy"] == pytest.approx(0.12)


def test_required_features_are_generated():
    config = sample_config()
    dates = pd.date_range("2023-01-01", periods=401, freq="D")
    raw = {
        series_id: frame(series_id, dates, pd.Series(range(len(dates))) + offset + 100)
        for offset, series_id in enumerate(
            ["DGS10", "DGS2", "DFII10", "DTWEXBGS", "SP500", "BAMLH0A0HYM2"]
        )
    }
    raw["CPIAUCSL"] = frame(
        "CPIAUCSL", pd.date_range("2023-01-01", periods=14, freq="MS"), range(100, 114)
    )
    raw["FEDFUNDS"] = frame(
        "FEDFUNDS", pd.date_range("2023-01-01", periods=14, freq="MS"), range(14)
    )
    features = build_macro_features(build_macro_dataset(raw, config))
    required = {
        "yield_curve_10y_2y",
        "real_yield_change_20d",
        "broad_usd_return_5d",
        "sp500_return_5d",
        "credit_stress_change_5d",
        "cpi_yoy",
        "fed_funds_change",
        "macro_stress_score",
    }
    assert required.issubset(features.columns)
    assert features["macro_stress_score"].notna().any()
