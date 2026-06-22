from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from dateutil import parser as date_parser

try:
    from langdetect import detect
except ImportError:  # pragma: no cover
    detect = None

from src.news.models import NewsItem


TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_")
SPANISH_MONTHS = {
    "enero": "January",
    "febrero": "February",
    "marzo": "March",
    "abril": "April",
    "mayo": "May",
    "junio": "June",
    "julio": "July",
    "agosto": "August",
    "septiembre": "September",
    "setiembre": "September",
    "octubre": "October",
    "noviembre": "November",
    "diciembre": "December",
}


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip() or None


def canonical_url(url: str, base_url: str) -> str:
    absolute = urljoin(base_url, url)
    parts = urlsplit(absolute)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(TRACKING_PREFIXES)]
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def normalize_for_hash(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", value.strip()):
        try:
            parsed = date_parser.isoparse(value.strip())
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            pass
    normalized = value
    for spanish, english in SPANISH_MONTHS.items():
        normalized = re.sub(rf"\b{spanish}\b", english, normalized, flags=re.IGNORECASE)
    try:
        parsed = date_parser.parse(normalized, fuzzy=True, dayfirst=True)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def estimate_language(title: str, summary: str | None, expected: str) -> str:
    if detect is None:
        return expected
    try:
        return detect(f"{title}. {summary or ''}")
    except Exception:
        return expected


def normalize_item(raw: dict, source: dict, scraped_at: datetime, method: str) -> NewsItem:
    title = clean_text(raw.get("title")) or "(sin título)"
    summary = clean_text(raw.get("summary"))
    url = canonical_url(raw["url"], source["url"])
    published_at = parse_date(raw.get("published_at"))
    if published_at is None:
        url_date = re.search(r"/(20\d{2})-(\d{2})-(\d{2})(?:/|$)", url)
        if url_date:
            published_at = parse_date("-".join(url_date.groups()))
    if published_at is not None:
        comparison = published_at.astimezone(timezone.utc)
        scraped_utc = scraped_at.astimezone(timezone.utc)
        if comparison > scraped_utc + timedelta(days=1):
            published_at = None
    digest_input = f"{normalize_for_hash(title)}|{normalize_for_hash(summary or '')}"
    content_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    news_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    return NewsItem(
        news_id=news_id,
        source_id=source["id"],
        source_name=source["name"],
        source_url=source["url"],
        url=url,
        title=title,
        summary=summary,
        published_at=published_at,
        category=clean_text(raw.get("category") or source.get("category")),
        scraped_at=scraped_at,
        language=estimate_language(title, summary, source.get("expected_language", "und")),
        content_hash=content_hash,
        reliability_weight=float(source.get("reliability_weight", 1)),
        collector_method=method,
    )
