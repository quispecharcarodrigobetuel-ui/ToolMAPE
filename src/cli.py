from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.macro.fred_config import load_fred_config
from src.macro.pipeline import FredPipeline
from src.news.config import load_config
from src.news.labeling.market import load_market_prices
from src.news.pipeline import NewsPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Toolmape: mercado, macro y noticias")
    modules = parser.add_subparsers(dest="module", required=True)

    news = modules.add_parser("news", help="Scraping y señales de noticias")
    news.add_argument("command", choices=("scrape", "enrich", "label", "features", "publish", "all"))
    news.add_argument("--mode", choices=("local", "supabase"))

    macro = modules.add_parser("macro", help="Datos macroeconómicos oficiales")
    macro.add_argument(
        "command", choices=("fred-download", "fred-features", "fred-publish", "fred-all")
    )
    macro.add_argument("--mode", choices=("local", "supabase"))

    all_parser = modules.add_parser("all", help="Ejecutar el pipeline integrado")
    all_parser.add_argument("--mode", choices=("local", "supabase"))
    return parser


def _summary(command: str, result: Any) -> dict[str, Any]:
    if hasattr(result, "shape"):
        return {"command": command, "records": int(result.shape[0])}
    if isinstance(result, list):
        return {"command": command, "records": len(result)}
    return {"command": command, "result": result}


def run_integrated(mode: str | None) -> dict[str, Any]:
    fred_config = load_fred_config()
    news_config = load_config()
    if mode:
        fred_config["mode"] = mode
        news_config["pipeline"]["mode"] = mode
    fred = FredPipeline(fred_config)
    news = NewsPipeline(news_config)
    results: dict[str, Any] = {}

    try:
        market_config = dict(news_config)
        market_config["pipeline"] = dict(news_config["pipeline"])
        market_config["pipeline"]["download_market_if_missing"] = True
        market = load_market_prices(market_config)
        results["market"] = len(market)
    except Exception as exc:
        results["market"] = {"status": "failed", "error": str(exc)}
    try:
        results["fred_download"] = fred.download()
    except Exception as exc:
        results["fred_download"] = {"status": "failed", "error": str(exc)}
    results["news"] = news.all()
    try:
        features = fred.features()
        results["fred_features"] = len(features)
    except Exception as exc:
        results["fred_features"] = {"status": "failed", "error": str(exc)}
    if (mode or fred_config["mode"]) == "supabase":
        try:
            results["fred_publish"] = fred.publish()
        except Exception as exc:
            results["fred_publish"] = {"status": "failed", "error": str(exc)}
    return results


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.module == "news":
            config = load_config()
            if args.mode:
                config["pipeline"]["mode"] = args.mode
            result = getattr(NewsPipeline(config), args.command)()
        elif args.module == "macro":
            config = load_fred_config()
            if args.mode:
                config["mode"] = args.mode
            command = args.command.replace("fred-", "").replace("-", "_")
            result = getattr(FredPipeline(config), command)()
        else:
            result = run_integrated(args.mode)
        print(json.dumps(_summary(getattr(args, "command", "all"), result), ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
