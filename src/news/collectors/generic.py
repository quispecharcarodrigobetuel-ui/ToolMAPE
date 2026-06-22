from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from src.news.collectors.base import CollectorError, CollectorResult


DATE_SELECTORS = ("time", "[datetime]", "[class*='date']", "[class*='fecha']", "[class*='time']")
SUMMARY_SELECTORS = ("p", "[class*='summary']", "[class*='excerpt']", "[class*='description']")


class GenericListCollector:
    def __init__(self, source: dict[str, Any], pipeline_config: dict[str, Any]):
        self.source = source
        self.config = pipeline_config
        self.headers = {
            "User-Agent": pipeline_config["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.7",
        }

    def collect(self) -> CollectorResult:
        result = CollectorResult(source_id=self.source["id"])
        try:
            html = self._request(self.source["url"])
            result.items = self._parse_html(html)
        except Exception as exc:
            result.errors.append(f"requests: {exc}")

        if not result.items:
            for fallback in self.source.get("fallback_urls", []):
                try:
                    body = self._request(fallback)
                    result.items = self._parse_feed(body)
                    if result.items:
                        result.method = "rss"
                        break
                except Exception as exc:
                    result.errors.append(f"fallback {fallback}: {exc}")

        if not result.items and self.source.get("allow_playwright_fallback"):
            try:
                html = self._playwright()
                result.items = self._parse_html(html)
                result.method = "playwright"
            except Exception as exc:
                result.errors.append(f"playwright: {exc}")
        return result

    def _request(self, url: str) -> str:
        retries = int(self.config.get("request_retries", 2))
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=int(self.config.get("request_timeout_seconds", 20)),
                )
                response.raise_for_status()
                return response.text
            except requests.RequestException as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(2**attempt)
        raise CollectorError(str(last_error))

    def _parse_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        items = [item for item in self._parse_json_ld(soup) if self._allowed_url(item["url"])]
        seen = {item["url"] for item in items}
        containers = []
        for selector in self.source.get("article_selectors", ["article"]):
            containers.extend(soup.select(selector))

        if not containers:
            items = [item for item in items if self._matches_keywords(item)]
            return items[: int(self.config.get("max_items_per_source", 50))]

        for container in containers:
            link = container if container.name == "a" else container.select_one("a[href]")
            if not link or not link.get("href"):
                continue
            href = urljoin(self.source["url"], link["href"])
            if urlsplit(href).netloc != urlsplit(self.source["url"]).netloc:
                continue
            if not self._allowed_url(href):
                continue
            title_node = container.select_one("h1,h2,h3,h4,[class*='title']") if container.name != "a" else None
            title = (title_node or link).get_text(" ", strip=True)
            if len(title) < 15 or href in seen:
                continue
            summary_node = container.select_one(",".join(SUMMARY_SELECTORS))
            date_node = (
                container.select_one("time[datetime]")
                or container.select_one("[datetime]")
                or container.select_one(",".join(DATE_SELECTORS))
            )
            published = None
            if date_node:
                published = date_node.get("datetime") or date_node.get_text(" ", strip=True)
            category_node = container.select_one("[class*='category'],[class*='tag']")
            items.append(
                {
                    "url": href,
                    "title": title,
                    "summary": summary_node.get_text(" ", strip=True) if summary_node else None,
                    "published_at": published,
                    "category": category_node.get_text(" ", strip=True) if category_node else None,
                }
            )
            seen.add(href)
        items = [item for item in items if self._matches_keywords(item)]
        return items[: int(self.config.get("max_items_per_source", 50))]

    def _allowed_url(self, url: str) -> bool:
        patterns = self.source.get("link_patterns", [])
        excluded = self.source.get("exclude_link_patterns", [])
        return (not patterns or any(pattern in url for pattern in patterns)) and not any(
            pattern in url for pattern in excluded
        )

    def _matches_keywords(self, item: dict[str, Any]) -> bool:
        keywords = self.source.get("required_keywords", [])
        if not keywords:
            return True
        text = " ".join(
            str(item.get(field) or "") for field in ("title", "summary", "category")
        ).lower()
        return any(keyword.lower() in text for keyword in keywords)

    def _parse_json_ld(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for script in soup.select("script[type='application/ld+json']"):
            try:
                payload = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            nodes = payload if isinstance(payload, list) else [payload]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                candidates = node.get("itemListElement", []) if node.get("@type") == "ItemList" else []
                if node.get("@type") in ("NewsArticle", "Article", "BlogPosting"):
                    candidates = [node]
                for candidate in candidates:
                    if isinstance(candidate, dict) and "item" in candidate:
                        candidate = candidate["item"]
                    if not isinstance(candidate, dict):
                        continue
                    url = candidate.get("url") or candidate.get("@id")
                    title = candidate.get("headline") or candidate.get("name")
                    if url and title:
                        rows.append(
                            {
                                "url": url,
                                "title": title,
                                "summary": candidate.get("description"),
                                "published_at": candidate.get("datePublished"),
                                "category": candidate.get("articleSection"),
                            }
                        )
        return rows

    def _parse_feed(self, body: str) -> list[dict[str, Any]]:
        root = ET.fromstring(body)
        rows: list[dict[str, Any]] = []
        for node in root.findall(".//item"):
            link = node.findtext("link")
            title = node.findtext("title")
            if link and title:
                rows.append(
                    {
                        "url": link,
                        "title": title,
                        "summary": self._strip_markup(node.findtext("description")),
                        "published_at": node.findtext("pubDate"),
                        "category": node.findtext("category"),
                    }
                )
        if not rows:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for node in root.findall(".//atom:entry", ns):
                link_node = node.find("atom:link", ns)
                title = node.findtext("atom:title", namespaces=ns)
                if link_node is not None and title:
                    rows.append(
                        {
                            "url": link_node.get("href"),
                            "title": title,
                            "summary": self._strip_markup(node.findtext("atom:summary", namespaces=ns)),
                            "published_at": node.findtext("atom:published", namespaces=ns)
                            or node.findtext("atom:updated", namespaces=ns),
                        }
                    )
        rows = [row for row in rows if self._matches_keywords(row)]
        return rows[: int(self.config.get("max_items_per_source", 50))]

    @staticmethod
    def _strip_markup(value: str | None) -> str | None:
        return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if value else None

    def _playwright(self) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CollectorError("Playwright no está instalado; es una alternativa opcional") from exc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.headers["User-Agent"])
            page.goto(self.source["url"], wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(2_000)
            html = page.content()
            browser.close()
            return html
