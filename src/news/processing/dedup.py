from __future__ import annotations

from src.news.models import NewsItem


def deduplicate(items: list[NewsItem], existing: list[dict]) -> tuple[list[NewsItem], int]:
    urls = {row["url"] for row in existing}
    hashes = {row["content_hash"] for row in existing}
    fresh: list[NewsItem] = []
    duplicates = 0
    for item in items:
        if item.url in urls or item.content_hash in hashes:
            duplicates += 1
            continue
        urls.add(item.url)
        hashes.add(item.content_hash)
        fresh.append(item)
    return fresh, duplicates
