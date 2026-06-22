from __future__ import annotations

import argparse
import json
import sys

from src.news.config import load_config
from src.news.pipeline import NewsPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Toolmape: pipeline de noticias")
    modules = parser.add_subparsers(dest="module", required=True)
    news = modules.add_parser("news", help="Scraping y señales de noticias")
    news.add_argument("command", choices=("scrape", "enrich", "label", "features", "publish", "all"))
    news.add_argument("--mode", choices=("local", "supabase"), help="Sobrescribe NEWS_PIPELINE_MODE")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    if args.mode:
        config["pipeline"]["mode"] = args.mode
    pipeline = NewsPipeline(config)
    try:
        result = getattr(pipeline, args.command)()
        if isinstance(result, list):
            summary = {"command": args.command, "records": len(result)}
        else:
            summary = {"command": args.command, "result": result}
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"command": args.command, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
