#!/usr/bin/python3
"""
Refresh a local Apple Calendar subscription feed for Binance Wallet Alpha airdrops.

The script intentionally prefers official Binance endpoints and writes uncertain
items as reminders to check Alpha Events in the app instead of pretending a
claim rule was verified.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
CACHE_DIR = DATA_DIR / "cache"
HISTORY_FILE = PUBLIC_DIR / "history.json"
MANUAL_EVENTS_FILE = DATA_DIR / "manual_events.json"
DEFAULT_HISTORY_URL = "https://kahnchan.github.io/bn-wallet-alpha/history.json"

ALPHA_TOKEN_API = (
    "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/"
    "alpha/all/token/list"
)
CMS_LIST_API = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
)
CMS_DETAIL_API = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query"
)
BINANCE_ALPHA_URL = "https://www.binance.com/en/alpha"
TWSTALKER_URL = "https://twstalker.com/{account}"
FXTWITTER_PROFILE_API = "https://api.fxtwitter.com/2/profile/{account}/statuses"
FXTWITTER_THREAD_API = "https://api.fxtwitter.com/2/thread/{status_id}"
FXTWITTER_STATUS_API = "https://api.fxtwitter.com/2/status/{status_id}"
SHANGHAI_TZ = dt.timezone(dt.timedelta(hours=8))

# Binance announcement catalogs that commonly contain campaigns and listings.
CMS_CATALOGS = {
    93: "Latest Activities",
    48: "New Cryptocurrency Listing",
    49: "Latest Binance News",
}

KEYWORD_RE = re.compile(
    r"\b(alpha|airdrop|airdrops|claim|points?|wallet|tge|launchpool|reward)\b",
    re.IGNORECASE,
)
RULE_LINE_RE = re.compile(
    r"(claim|eligible|eligibility|alpha points?|airdrop|reward|receive|token allocation|"
    r"first come|deduct|points? balance|threshold|snapshot|distribution)",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"(?P<date>20\d{2}[-/]\d{1,2}[-/]\d{1,2})"
    r"(?:\s+(?P<time>\d{1,2}:\d{2})(?::\d{2})?)?"
    r"(?:\s*\(?(?P<tz>UTC|GMT)\)?)?",
    re.IGNORECASE,
)
ENGLISH_DATE_RE = re.compile(
    r"\b(?P<month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,\s*|\s+)?(?P<year>20\d{2})?",
    re.IGNORECASE,
)
ENGLISH_TIME_AFTER_RE = re.compile(
    r"^\s*(?:,\s*)?(?:(?:at|@|from|starting(?:\s+on)?)\s+)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?"
    r"\s*(?P<ampm>a\.?m\.?|p\.?m\.?)?"
    r"\s*(?:[（(]?\s*(?P<tz>UTC|GMT)(?:\s*\+?\s*(?P<offset>\d{1,2}))?\s*[）)]?)?",
    re.IGNORECASE,
)
ENGLISH_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
CHINESE_DATE_RE = re.compile(
    r"(?:(?P<year>20\d{2})\s*年\s*)?"
    r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
    r"(?:\s*(?P<hour>\d{1,2})\s*(?:点|:|：)\s*(?P<minute>\d{1,2})?)?"
)
RELATIVE_CHINESE_TIME_RE = re.compile(
    r"(?P<day>今天|今日|今晚|明天|明日|明晚)"
    r"\s*(?P<hour>\d{1,2})\s*(?:点|:|：)\s*(?P<minute>\d{1,2})?"
    r"(?:\s*[（(]?\s*(?:UTC|GMT)\s*\+?\s*8\s*[）)]?)?",
    re.IGNORECASE,
)
SOCIAL_ALPHA_RE = re.compile(
    r"(alpha|Alpha|空投|领取|积分|上线|首个上线|交易开放|airdrop|claim|points?|launch|list)",
    re.IGNORECASE,
)
TOKEN_IN_PARENS_RE = re.compile(
    r"(?:上线|推出|上线\s+|list(?:ing)?\s+|launch(?:ing)?\s+)?"
    r"(?P<name>[A-Za-z][A-Za-z0-9 ._-]{1,60}?)\s*[（(](?P<symbol>[A-Z0-9]{2,15})[）)]"
)
STATUS_BLOCK_RE = re.compile(
    r'<span><a href="/(?P<account>[^/]+)/status/(?P<id>\d+)">(?P<age>[^<]+)</a></span>'
    r"(?P<block>.*?)(?=<span><a href=\"/[^\"]+/status/\d+\">|\Z)",
    re.DOTALL,
)
SOCIAL_STATUS_URL_RE = re.compile(
    r"https?://(?:x\.com|twitter\.com|twstalker\.com)/(?P<account>[^/]+)/status/(?P<id>\d+)",
    re.IGNORECASE,
)
PARAGRAPH_RE = re.compile(r"<p>(?P<text>.*?)</p>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def ensure_dirs() -> None:
    for directory in (DATA_DIR, PUBLIC_DIR, CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def cache_path(name: str) -> Path:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def read_cached(name: str) -> Any | None:
    path = cache_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["data"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def write_cached(name: str, data: Any) -> None:
    path = cache_path(name)
    payload = {
        "fetched_at": now_utc().isoformat(),
        "source": name,
        "data": data,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_json(url: str, *, timeout: int = 20, allow_cache: bool = True) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "bn-wallet-alpha-calendar/0.1 (+local calendar feed)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            data = json.loads(response.read().decode(charset))
            write_cached(url, data)
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        curl_data = fetch_json_with_curl(url, timeout=timeout)
        if curl_data is not None:
            write_cached(url, curl_data)
            return curl_data
        cached = read_cached(url) if allow_cache else None
        if cached is not None:
            print(f"warning: using cached response for {url}: {exc}", file=sys.stderr)
            return cached
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def fetch_json_with_curl(url: str, *, timeout: int) -> Any | None:
    try:
        result = subprocess.run(
            [
                "/usr/bin/curl",
                "-fsSL",
                "--max-time",
                str(timeout),
                "-A",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "-H",
                "Accept: application/json,text/plain,*/*",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def fetch_text(url: str, *, timeout: int = 20, allow_cache: bool = True) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        },
    )
    cache_name = f"text:{url}"
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
            write_cached(cache_name, {"text": text})
            return text
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        curl_text = fetch_text_with_curl(url, timeout=timeout)
        if curl_text is not None:
            write_cached(cache_name, {"text": curl_text})
            return curl_text
        cached = read_cached(cache_name) if allow_cache else None
        if isinstance(cached, dict) and isinstance(cached.get("text"), str):
            print(f"warning: using cached response for {url}: {exc}", file=sys.stderr)
            return cached["text"]
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def fetch_text_with_curl(url: str, *, timeout: int) -> str | None:
    try:
        result = subprocess.run(
            [
                "/usr/bin/curl",
                "-fsSL",
                "--max-time",
                str(timeout),
                "-A",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "-H",
                "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def flatten_cms_body(node: Any) -> str:
    if isinstance(node, str):
        stripped = node.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return flatten_cms_body(json.loads(stripped))
            except json.JSONDecodeError:
                return html.unescape(stripped)
        return html.unescape(stripped)
    if isinstance(node, list):
        return " ".join(part for part in (flatten_cms_body(item) for item in node) if part)
    if isinstance(node, dict):
        if node.get("node") == "text":
            return html.unescape(str(node.get("text", "")))
        pieces = []
        if "text" in node and isinstance(node["text"], str):
            pieces.append(node["text"])
        if "child" in node:
            pieces.append(flatten_cms_body(node["child"]))
        return " ".join(part.strip() for part in pieces if part and part.strip())
    return ""


def text_lines(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    rough_lines = re.split(r"(?<=[.!?。；;])\s+", compact)
    return [line.strip() for line in rough_lines if line.strip()]


def parse_iso_dates(text: str) -> list[tuple[dt.datetime, bool]]:
    dates: list[tuple[dt.datetime, bool]] = []
    for match in DATE_RE.finditer(text):
        date_part = match.group("date").replace("/", "-")
        time_part = match.group("time") or "00:00"
        try:
            parsed = dt.datetime.fromisoformat(f"{date_part}T{time_part}:00")
        except ValueError:
            continue
        if match.group("tz"):
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        else:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        dates.append((parsed, match.group("time") is not None))
    return dates


def parse_dates(text: str) -> list[dt.datetime]:
    return [value for value, _has_time in parse_iso_dates(text)]


def parse_chinese_dates(text: str) -> list[tuple[dt.datetime, bool]]:
    current = dt.datetime.now(SHANGHAI_TZ)
    dates: list[tuple[dt.datetime, bool]] = []
    for match in RELATIVE_CHINESE_TIME_RE.finditer(text):
        day_text = match.group("day")
        day_offset = 1 if day_text in {"明天", "明日", "明晚"} else 0
        base_date = current.date() + dt.timedelta(days=day_offset)
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        try:
            parsed = dt.datetime(
                base_date.year,
                base_date.month,
                base_date.day,
                hour,
                minute,
                tzinfo=SHANGHAI_TZ,
            )
        except ValueError:
            continue
        dates.append((parsed.astimezone(dt.timezone.utc), True))
    for match in CHINESE_DATE_RE.finditer(text):
        year = int(match.group("year") or current.year)
        month = int(match.group("month"))
        day = int(match.group("day"))
        hour_text = match.group("hour")
        minute_text = match.group("minute")
        has_time = hour_text is not None
        hour = int(hour_text or 9)
        minute = int(minute_text or 0)
        try:
            parsed = dt.datetime(
                year,
                month,
                day,
                hour,
                minute,
                tzinfo=SHANGHAI_TZ,
            )
        except ValueError:
            continue
        if match.group("year") is None and parsed < current - dt.timedelta(days=180):
            parsed = parsed.replace(year=parsed.year + 1)
        dates.append((parsed.astimezone(dt.timezone.utc), has_time))
    return dates


def parse_english_dates(text: str) -> list[tuple[dt.datetime, bool]]:
    current = now_utc()
    dates: list[tuple[dt.datetime, bool]] = []
    for match in ENGLISH_DATE_RE.finditer(text):
        month_name = match.group("month").lower().rstrip(".")
        month = ENGLISH_MONTHS.get(month_name)
        if month is None:
            continue
        year = int(match.group("year") or current.year)
        day = int(match.group("day"))
        tail = text[match.end() : match.end() + 80]
        time_match = ENGLISH_TIME_AFTER_RE.match(tail)
        has_time = time_match is not None
        hour = 0
        minute = 0
        tzinfo = dt.timezone.utc
        if time_match:
            hour = int(time_match.group("hour"))
            minute = int(time_match.group("minute") or 0)
            ampm = (time_match.group("ampm") or "").replace(".", "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            offset = time_match.group("offset")
            if offset:
                tzinfo = dt.timezone(dt.timedelta(hours=int(offset)))
        try:
            parsed = dt.datetime(year, month, day, hour, minute, tzinfo=tzinfo)
        except ValueError:
            continue
        if match.group("year") is None and parsed < current - dt.timedelta(days=180):
            parsed = parsed.replace(year=parsed.year + 1)
        dates.append((parsed.astimezone(dt.timezone.utc), has_time))
    return dates


def parse_social_dates(text: str) -> list[tuple[dt.datetime, bool]]:
    return parse_chinese_dates(text) + parse_english_dates(text) + parse_iso_dates(text)


def fetch_alpha_tokens() -> list[dict[str, Any]]:
    payload = fetch_json(ALPHA_TOKEN_API)
    if payload.get("code") != "000000" or not isinstance(payload.get("data"), list):
        raise RuntimeError("unexpected Binance Alpha token API response")
    return payload["data"]


def fetch_candidate_articles(max_pages: int, page_size: int) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for catalog_id in CMS_CATALOGS:
        for page_no in range(1, max_pages + 1):
            query = urllib.parse.urlencode(
                {
                    "type": 1,
                    "catalogId": catalog_id,
                    "pageNo": page_no,
                    "pageSize": page_size,
                }
            )
            url = f"{CMS_LIST_API}?{query}"
            try:
                payload = fetch_json(url)
            except RuntimeError as exc:
                print(f"warning: skipping CMS catalog {catalog_id}: {exc}", file=sys.stderr)
                break
            catalogs = payload.get("data", {}).get("catalogs") or []
            page_articles: list[dict[str, Any]] = []
            for catalog in catalogs:
                page_articles.extend(catalog.get("articles") or [])
            if not page_articles:
                break
            for article in page_articles:
                title = str(article.get("title") or "")
                code = str(article.get("code") or "")
                if not code or code in seen_codes:
                    continue
                if KEYWORD_RE.search(title):
                    seen_codes.add(code)
                    article["catalogId"] = catalog_id
                    article["catalogName"] = CMS_CATALOGS[catalog_id]
                    articles.append(article)
    return articles


def clean_html_text(raw: str) -> str:
    without_tags = TAG_RE.sub("", raw)
    return html.unescape(without_tags).replace("\xa0", " ").strip()


def social_post_from_fxtwitter(tweet: dict[str, Any], account_hint: str | None = None) -> dict[str, Any] | None:
    status_id = str(tweet.get("id") or "")
    if not status_id:
        return None
    author = tweet.get("author") if isinstance(tweet.get("author"), dict) else {}
    account = str(author.get("screen_name") or account_hint or "").strip().lstrip("@")
    if not account:
        return None
    raw_text = tweet.get("raw_text") if isinstance(tweet.get("raw_text"), dict) else {}
    text = str(raw_text.get("text") or tweet.get("text") or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text or not SOCIAL_ALPHA_RE.search(text):
        return None
    return {
        "account": account,
        "id": status_id,
        "age": str(tweet.get("created_at") or ""),
        "text": text,
        "url": str(tweet.get("url") or f"https://x.com/{account}/status/{status_id}"),
        "mirrorUrl": FXTWITTER_STATUS_API.format(status_id=status_id),
    }


def fetch_fxtwitter_account_posts(account: str, max_posts: int) -> list[dict[str, Any]]:
    url = FXTWITTER_PROFILE_API.format(account=urllib.parse.quote(account))
    payload = fetch_json(url)
    if payload.get("code") != 200 or not isinstance(payload.get("results"), list):
        raise RuntimeError(f"unexpected FxTwitter profile response for @{account}")
    posts: list[dict[str, Any]] = []
    for tweet in payload["results"]:
        if not isinstance(tweet, dict):
            continue
        post = social_post_from_fxtwitter(tweet, account)
        if post is None:
            continue
        if post["account"].lower() != account.lower():
            continue
        posts.append(post)
        if len(posts) >= max_posts:
            break
    return posts


def fetch_twstalker_account_posts(account: str, max_posts: int) -> list[dict[str, Any]]:
    url = TWSTALKER_URL.format(account=urllib.parse.quote(account))
    page = fetch_text(url)
    posts: list[dict[str, Any]] = []
    for status_match in STATUS_BLOCK_RE.finditer(page):
        if status_match.group("account").lower() != account.lower():
            continue
        paragraph_match = PARAGRAPH_RE.search(status_match.group("block"))
        if not paragraph_match:
            continue
        text = clean_html_text(paragraph_match.group("text"))
        if not text or not SOCIAL_ALPHA_RE.search(text):
            continue
        posts.append(
            {
                "account": account,
                "id": status_match.group("id"),
                "age": clean_html_text(status_match.group("age")),
                "text": re.sub(r"\s+", " ", text),
                "url": f"https://x.com/{account}/status/{status_match.group('id')}",
                "mirrorUrl": f"https://twstalker.com/{account}/status/{status_match.group('id')}",
            }
        )
        if len(posts) >= max_posts:
            break
    return posts


def fetch_social_posts(accounts: list[str], max_posts: int) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for account in accounts:
        account = account.strip().lstrip("@")
        if not account:
            continue
        try:
            posts.extend(fetch_fxtwitter_account_posts(account, max_posts))
            continue
        except RuntimeError as exc:
            print(f"warning: FxTwitter profile skipped for @{account}: {exc}", file=sys.stderr)
        try:
            posts.extend(fetch_twstalker_account_posts(account, max_posts))
        except RuntimeError as exc:
            print(f"warning: skipping social source @{account}: {exc}", file=sys.stderr)
    return dedupe_posts(posts)


def fetch_social_thread_posts(
    status_urls: list[str], allowed_accounts: set[str], max_posts_per_thread: int
) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    seen_threads: set[str] = set()
    for status_url in status_urls:
        match = SOCIAL_STATUS_URL_RE.search(status_url)
        if not match:
            continue
        account = match.group("account").strip().lstrip("@")
        status_id = match.group("id")
        if account.lower() not in allowed_accounts or status_id in seen_threads:
            continue
        seen_threads.add(status_id)
        try:
            payload = fetch_json(FXTWITTER_THREAD_API.format(status_id=status_id))
        except RuntimeError as exc:
            print(f"warning: thread source skipped for {status_url}: {exc}", file=sys.stderr)
            continue
        thread = payload.get("thread")
        if payload.get("code") != 200 or not isinstance(thread, list):
            continue
        found = 0
        for tweet in thread:
            if not isinstance(tweet, dict):
                continue
            post = social_post_from_fxtwitter(tweet, account)
            if post is None or post["account"].lower() not in allowed_accounts:
                continue
            posts.append(post)
            found += 1
            if found >= max_posts_per_thread:
                break
    return dedupe_posts(posts)


def dedupe_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for post in posts:
        key = (str(post.get("account") or "").lower(), str(post.get("id") or ""))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(post)
    return result


def extract_token(text: str) -> tuple[str, str] | None:
    candidates = list(TOKEN_IN_PARENS_RE.finditer(text))
    if not candidates:
        return None
    match = candidates[0]
    symbol = match.group("symbol").upper()
    prefix = text[: match.start("symbol")].rsplit("(", 1)[0].rsplit("（", 1)[0]
    prefix = re.sub(r"https?://\S+", " ", prefix)
    prefix = re.split(
        r"(?:feature|featuring|list|listing|launch|launching|上线|推出|成为首个上线|首个上线)",
        prefix,
        flags=re.IGNORECASE,
    )[-1]
    prefix = re.split(r"[。.!?；;\n]", prefix)[-1]
    name = re.sub(r"\s+", " ", prefix).strip(" -:：,，")
    if not name:
        name = match.group("name").strip(" -")
    return name, symbol


def build_social_items(
    posts: list[dict[str, Any]], *, lookback_days: int, horizon_days: int
) -> list[dict[str, Any]]:
    current = now_utc()
    start = current - dt.timedelta(days=lookback_days)
    end = current + dt.timedelta(days=horizon_days)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for post in posts:
        text = str(post.get("text") or "")
        if "Alpha" not in text and "alpha" not in text:
            continue
        if not re.search(r"空投|领取|积分|airdrop|claim|points?", text, re.IGNORECASE):
            continue
        dates = parse_social_dates(text)
        token = extract_token(text)
        if not dates:
            continue
        event_time, has_time = dates[0]
        if not (start <= event_time <= end):
            continue
        has_token = token is not None
        name, symbol = token if token else ("Alpha 空投币种", "待公布")
        key = f"social:{symbol}:{event_time.date().isoformat()}:{post.get('id')}"
        if key in seen:
            continue
        seen.add(key)
        confirmation_note = (
            "已从官方 X 解析到开放时间；最终领取窗口、积分门槛和数量仍以 Binance Wallet > Alpha > Events 为准。"
            if has_time
            else "已确认日期；具体开放时间、领取门槛和领取数量以 Binance Wallet > Alpha > Events 为准。"
        )
        items.append(
            {
                "symbol": symbol,
                "name": name,
                "alphaId": None,
                "chainName": None,
                "contractAddress": None,
                "listingTime": event_time.isoformat(),
                "dateOnly": not has_time,
                "onlineAirdrop": None,
                "onlineTge": None,
                "mulPoint": None,
                "price": None,
                "source": f"官方 X 预告 @{post.get('account')}",
                "sourceUrl": post.get("url"),
                "sourceMirrorUrl": post.get("mirrorUrl"),
                "matchedAnnouncements": [],
                "ruleSummary": [
                    text,
                    confirmation_note,
                ],
                "announcementUrls": [post.get("url"), post.get("mirrorUrl")],
                "announcementDates": [event_time.isoformat()],
                "signalType": "social_alpha_notice",
                "tokenKnown": has_token,
            }
        )
    return items


def fetch_article_detail(article: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({"articleCode": article["code"]})
    payload = fetch_json(f"{CMS_DETAIL_API}?{query}")
    detail = payload.get("data") or {}
    body = flatten_cms_body(detail.get("body", ""))
    title = str(detail.get("title") or article.get("title") or "")
    code = str(detail.get("code") or article.get("code") or "")
    return {
        "code": code,
        "title": title,
        "releaseDate": detail.get("releaseDate") or article.get("releaseDate"),
        "catalogName": article.get("catalogName"),
        "url": f"https://www.binance.com/en/support/announcement/{slugify(title)}-{code}",
        "body": body,
        "ruleLines": [line for line in text_lines(body) if RULE_LINE_RE.search(line)][:8],
        "dates": [value.isoformat() for value in parse_dates(f"{title} {body}")[:8]],
    }


def slugify(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "announcement"


def ms_to_datetime(value: Any) -> dt.datetime | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    if millis <= 0:
        return None
    return dt.datetime.fromtimestamp(millis / 1000, tz=dt.timezone.utc)


def symbol_matches(article: dict[str, Any], token: dict[str, Any]) -> bool:
    haystack = f"{article.get('title', '')} {article.get('body', '')}".lower()
    symbol = str(token.get("symbol") or "").lower()
    name = str(token.get("name") or "").lower()
    return bool(symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol)}(?![a-z0-9])", haystack)) or (
        bool(name) and name in haystack
    )


def build_items(
    tokens: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    *,
    lookback_days: int,
    horizon_days: int,
) -> list[dict[str, Any]]:
    current = now_utc()
    start = current - dt.timedelta(days=lookback_days)
    end = current + dt.timedelta(days=horizon_days)
    items: list[dict[str, Any]] = []

    for token in tokens:
        listing_at = ms_to_datetime(token.get("listingTime"))
        if not token.get("onlineAirdrop") or listing_at is None:
            continue
        if not (start <= listing_at <= end):
            continue

        matched_articles = [article for article in articles if symbol_matches(article, token)]
        rule_lines: list[str] = []
        urls: list[str] = []
        detail_dates: list[str] = []
        for article in matched_articles[:3]:
            rule_lines.extend(article.get("ruleLines") or [])
            urls.append(article.get("url", ""))
            detail_dates.extend(article.get("dates") or [])

        items.append(
            {
                "symbol": token.get("symbol"),
                "name": token.get("name"),
                "alphaId": token.get("alphaId"),
                "chainName": token.get("chainName"),
                "contractAddress": token.get("contractAddress"),
                "listingTime": listing_at.isoformat(),
                "onlineAirdrop": bool(token.get("onlineAirdrop")),
                "onlineTge": bool(token.get("onlineTge")),
                "mulPoint": token.get("mulPoint"),
                "price": token.get("price"),
                "source": "Binance Alpha 币种接口",
                "sourceUrl": BINANCE_ALPHA_URL,
                "matchedAnnouncements": matched_articles[:3],
                "ruleSummary": unique(rule_lines)[:8],
                "announcementUrls": unique([url for url in urls if url])[:3],
                "announcementDates": unique(detail_dates)[:8],
            }
        )

    items.sort(key=lambda item: item["listingTime"])
    return items


def load_manual_items(path: Path = MANUAL_EVENTS_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: manual events unavailable: {exc}", file=sys.stderr)
        return []

    raw_items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return []

    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict) or not raw.get("listingTime"):
            continue
        item = dict(raw)
        try:
            starts_at = dt.datetime.fromisoformat(str(item["listingTime"]))
        except ValueError:
            print(f"warning: manual event skipped, invalid listingTime: {item.get('listingTime')}", file=sys.stderr)
            continue
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=SHANGHAI_TZ)
        starts_at = starts_at.astimezone(dt.timezone.utc)
        item["listingTime"] = starts_at.isoformat()
        item.setdefault("symbol", "测试")
        item.setdefault("name", "Apple Calendar 提醒测试")
        item.setdefault("alphaId", None)
        item.setdefault("chainName", None)
        item.setdefault("contractAddress", None)
        item.setdefault("dateOnly", False)
        item.setdefault("onlineAirdrop", None)
        item.setdefault("onlineTge", None)
        item.setdefault("mulPoint", None)
        item.setdefault("price", None)
        item.setdefault("source", "手动测试事件")
        item.setdefault("sourceUrl", "https://kahnchan.github.io/bn-wallet-alpha/")
        item.setdefault("matchedAnnouncements", [])
        item.setdefault("ruleSummary", ["用于测试 Apple Calendar 订阅事件和开始前 15 分钟提醒。"])
        item.setdefault("announcementUrls", [item["sourceUrl"]])
        item.setdefault("announcementDates", [item["listingTime"]])
        item.setdefault("signalType", "manual_test")
        item.setdefault("tokenKnown", True)
        items.append(item)
    return items


def merge_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in sorted(items, key=lambda value: value["listingTime"]):
        symbol = str(item.get("symbol") or "").upper()
        event_date = local_event_date(item) or dt.datetime.fromisoformat(item["listingTime"]).date().isoformat()
        key = (symbol, event_date)
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        merged[key] = merge_item_details(existing, item)
    return sorted(merged.values(), key=lambda item: item["listingTime"])


def history_key(item: dict[str, Any]) -> tuple[str, str]:
    symbol = str(item.get("symbol") or "").upper()
    event_date = local_event_date(item)
    if symbol and symbol not in {"UNKNOWN", "待公布"} and event_date:
        return ("symbol-date", f"{symbol}:{event_date}")
    if item.get("alphaId"):
        return ("alpha", str(item["alphaId"]))
    if item.get("sourceUrl"):
        return ("url", str(item["sourceUrl"]))
    return ("event", f"{symbol}:{item.get('listingTime')}")


def local_event_date(item: dict[str, Any]) -> str | None:
    value = item.get("listingTime")
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.astimezone(SHANGHAI_TZ).date().isoformat()


def load_history(history_url: str | None) -> list[dict[str, Any]]:
    payload: Any | None = None
    if history_url:
        try:
            payload = fetch_json(history_url, timeout=12, allow_cache=False)
        except RuntimeError as exc:
            print(f"warning: remote history unavailable: {exc}", file=sys.stderr)
    if payload is None and HISTORY_FILE.exists():
        try:
            payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: local history unavailable: {exc}", file=sys.stderr)
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def social_status_urls_from_history(
    history: list[dict[str, Any]], *, lookback_days: int, horizon_days: int, max_urls: int
) -> list[str]:
    current = now_utc()
    start = current - dt.timedelta(days=lookback_days)
    end = current + dt.timedelta(days=horizon_days)
    urls: list[str] = []
    for item in sorted(history, key=lambda value: str(value.get("listingTime") or ""), reverse=True):
        try:
            listing_at = dt.datetime.fromisoformat(str(item.get("listingTime")))
        except ValueError:
            continue
        if listing_at.tzinfo is None:
            listing_at = listing_at.replace(tzinfo=dt.timezone.utc)
        if not (start <= listing_at <= end):
            continue
        candidates: list[Any] = [
            item.get("sourceUrl"),
            item.get("sourceMirrorUrl"),
            *(item.get("announcementUrls") or []),
        ]
        for candidate in candidates:
            if not isinstance(candidate, str) or not SOCIAL_STATUS_URL_RE.search(candidate):
                continue
            urls.append(candidate)
            if len(urls) >= max_urls:
                return unique(urls)
    return unique(urls)


def merge_history(history: list[dict[str, Any]], current_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    stamp = now_utc().isoformat()

    for item in history:
        if item.get("listingTime"):
            key = history_key(item)
            existing = merged.get(key)
            merged[key] = merge_item_details(existing, item) if existing else item

    for item in current_items:
        key = history_key(item)
        existing = merged.get(key)
        if existing is None:
            item["firstSeenAt"] = stamp
            item["lastSeenAt"] = stamp
            merged[key] = item
            continue
        first_seen = existing.get("firstSeenAt")
        merged_item = merge_item_details(existing, item)
        merged_item["firstSeenAt"] = first_seen or stamp
        merged_item["lastSeenAt"] = stamp
        merged[key] = merged_item

    return sorted((normalize_merged_item(item) for item in merged.values()), key=lambda item: item.get("listingTime", ""))


def merge_item_details(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    promote_incoming = should_promote_incoming(existing, incoming)
    for field in (
        "symbol",
        "name",
        "alphaId",
        "chainName",
        "contractAddress",
        "signalType",
        "tokenKnown",
    ):
        if incoming.get(field) not in (None, ""):
            merged[field] = incoming[field]
    if promote_incoming:
        for field in ("listingTime", "sourceUrl", "sourceMirrorUrl", "dateOnly"):
            if incoming.get(field) not in (None, ""):
                merged[field] = incoming[field]
        ordered_sources = [incoming.get("source"), existing.get("source")]
    else:
        ordered_sources = [existing.get("source"), incoming.get("source")]
        if not merged.get("sourceUrl") and incoming.get("sourceUrl"):
            merged["sourceUrl"] = incoming["sourceUrl"]
        if not merged.get("sourceMirrorUrl") and incoming.get("sourceMirrorUrl"):
            merged["sourceMirrorUrl"] = incoming["sourceMirrorUrl"]
        if merged.get("dateOnly") is None and incoming.get("dateOnly") is not None:
            merged["dateOnly"] = incoming["dateOnly"]
    merged["source"] = merge_source_texts(*ordered_sources)
    for field, limit in (
        ("ruleSummary", 8),
        ("announcementUrls", 8),
        ("announcementDates", 8),
    ):
        if promote_incoming:
            first = incoming.get(field) or []
            second = existing.get(field) or []
        else:
            first = existing.get(field) or []
            second = incoming.get(field) or []
        merged[field] = unique(first + second)[:limit]
    for field in ("onlineAirdrop", "onlineTge", "mulPoint", "price"):
        if incoming.get(field) is not None:
            merged[field] = incoming[field]
    return merged


def should_promote_incoming(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    existing_date_only = bool(existing.get("dateOnly"))
    incoming_date_only = bool(incoming.get("dateOnly"))
    if existing_date_only and not incoming_date_only:
        return True
    if not existing_date_only and incoming_date_only:
        return False
    if not incoming_date_only and incoming.get("listingTime"):
        return True
    return False


def merge_source_texts(*sources: Any) -> str:
    parts: list[str] = []
    for source in sources:
        if not source:
            continue
        parts.extend(part.strip() for part in str(source).split(" + "))
    return " + ".join(unique(parts))


def normalize_merged_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    if normalized.get("source"):
        normalized["source"] = merge_source_texts(normalized["source"])
    for field, limit in (
        ("ruleSummary", 8),
        ("announcementUrls", 8),
        ("announcementDates", 8),
    ):
        normalized[field] = unique(normalized.get(field) or [])[:limit]
    return normalized


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def fold_ics_line(line: str) -> str:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    chunks: list[str] = []
    current = ""
    for char in line:
        tentative = current + char
        if len(tentative.encode("utf-8")) > 73:
            chunks.append(current)
            current = char
        else:
            current = tentative
    if current:
        chunks.append(current)
    return "\r\n ".join(chunks)


def ics_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("\n", "\\n").replace("\r", "")
    text = text.replace(";", "\\;").replace(",", "\\,")
    return text


def format_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def add_ics_line(lines: list[str], line: str) -> None:
    lines.append(fold_ics_line(line))


def build_description(item: dict[str, Any]) -> str:
    rules = item.get("ruleSummary") or []
    announcements = item.get("announcementUrls") or []
    primary_url = announcements[0] if announcements else item.get("sourceUrl")
    parts = [
        f"{item.get('symbol')} - {item.get('name')}",
        f"来源: {item.get('source')} - {item.get('sourceUrl')}",
    ]
    if item.get("dateOnly"):
        parts.append("只确认到日期，具体开放时间待官方活动页确认。")
    if item.get("alphaId"):
        parts.append(f"Alpha ID: {item.get('alphaId')}")
    if item.get("chainName"):
        parts.append(f"链: {item.get('chainName')}")
    if item.get("onlineAirdrop") is not None:
        parts.append(
            f"官方字段: onlineAirdrop={item.get('onlineAirdrop')}, onlineTge={item.get('onlineTge')}, mulPoint={item.get('mulPoint')}"
        )
    if rules:
        parts.append("规则/说明:")
        parts.extend(f"- {shorten(line, 220)}" for line in rules[:3])
    else:
        parts.append(
            "暂未从官方公告解析到明确领取规则。请打开 Binance Wallet > Alpha > Events，核验领取时间、Alpha Points 门槛和可领取内容。"
        )
    if primary_url:
        parts.append(f"链接: {primary_url}")
    if item.get("contractAddress"):
        parts.append(f"合约地址: {item.get('contractAddress')}")
    return "\n".join(parts)


def shorten(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_calendar(
    items: list[dict[str, Any]], *, include_daily_check: bool, check_time: str
) -> str:
    stamp = now_utc()
    lines: list[str] = []
    add_ics_line(lines, "BEGIN:VCALENDAR")
    add_ics_line(lines, "VERSION:2.0")
    add_ics_line(lines, "PRODID:-//Codex//Binance Wallet Alpha Airdrop Watch//EN")
    add_ics_line(lines, "CALSCALE:GREGORIAN")
    add_ics_line(lines, "METHOD:PUBLISH")
    add_ics_line(lines, "X-WR-CALNAME:Bn Wallet Alpha 空投")
    add_ics_line(lines, "X-WR-CALDESC:自动更新的 Binance Wallet Alpha 空投领取提醒")
    add_ics_line(lines, "X-WR-TIMEZONE:Asia/Shanghai")
    add_ics_line(lines, "REFRESH-INTERVAL;VALUE=DURATION:PT10M")
    add_ics_line(lines, "X-PUBLISHED-TTL:PT10M")
    add_timezone(lines)

    if include_daily_check:
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
        hour, minute = [int(part) for part in check_time.split(":", 1)]
        daily_start = dt.datetime(today.year, today.month, today.day, hour, minute, 0)
        add_ics_line(lines, "BEGIN:VEVENT")
        add_ics_line(lines, "UID:bn-wallet-alpha-daily-check@codex.local")
        add_ics_line(lines, f"DTSTAMP:{format_utc(stamp)}")
        add_ics_line(lines, f"DTSTART;TZID=Asia/Shanghai:{daily_start.strftime('%Y%m%dT%H%M%S')}")
        add_ics_line(lines, "DURATION:PT10M")
        add_ics_line(lines, "RRULE:FREQ=DAILY")
        add_ics_line(lines, "SUMMARY:检查 Binance Wallet Alpha 空投")
        add_ics_line(
            lines,
            "DESCRIPTION:"
            + ics_escape(
                "打开 Binance Wallet > Alpha > Events，核验是否有可领取空投、Alpha Points 门槛、领取窗口和可领取内容。这个循环提醒默认关闭，只在手动启用时生成。"
            ),
        )
        add_ics_line(lines, f"URL:{BINANCE_ALPHA_URL}")
        add_ics_line(lines, "BEGIN:VALARM")
        add_ics_line(lines, "TRIGGER:-PT10M")
        add_ics_line(lines, "ACTION:DISPLAY")
        add_ics_line(lines, "DESCRIPTION:检查 Binance Wallet Alpha 空投")
        add_ics_line(lines, "END:VALARM")
        add_ics_line(lines, "END:VEVENT")

    for item in items:
        start = dt.datetime.fromisoformat(item["listingTime"])
        uid_seed = f"{item.get('alphaId') or item.get('symbol')}-{item['listingTime']}"
        uid = hashlib.sha1(uid_seed.encode("utf-8")).hexdigest()[:16]
        symbol = item.get("symbol") or "UNKNOWN"
        if item.get("signalType") == "social_alpha_notice" and item.get("tokenKnown") is False:
            prefix = "空投"
        else:
            prefix = "预告" if item.get("signalType") == "social_alpha_notice" else "空投"
        summary = f"{symbol} - BN Alpha {prefix}"
        add_ics_line(lines, "BEGIN:VEVENT")
        add_ics_line(lines, f"UID:bn-wallet-alpha-{uid}@codex.local")
        add_ics_line(lines, f"DTSTAMP:{format_utc(stamp)}")
        if item.get("dateOnly"):
            event_date = start.astimezone(dt.timezone(dt.timedelta(hours=8))).date()
            add_ics_line(lines, f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}")
            add_ics_line(
                lines,
                f"DTEND;VALUE=DATE:{(event_date + dt.timedelta(days=1)).strftime('%Y%m%d')}",
            )
        else:
            end = start + dt.timedelta(minutes=30)
            add_ics_line(lines, f"DTSTART:{format_utc(start)}")
            add_ics_line(lines, f"DTEND:{format_utc(end)}")
        add_ics_line(lines, f"SUMMARY:{ics_escape(summary)}")
        add_ics_line(lines, f"DESCRIPTION:{ics_escape(build_description(item))}")
        add_ics_line(lines, f"URL:{item.get('sourceUrl') or BINANCE_ALPHA_URL}")
        add_ics_line(lines, "BEGIN:VALARM")
        add_ics_line(lines, "TRIGGER:-PT15M")
        add_ics_line(lines, "ACTION:DISPLAY")
        add_ics_line(lines, f"DESCRIPTION:{ics_escape(summary)}")
        add_ics_line(lines, "END:VALARM")
        add_ics_line(lines, "END:VEVENT")

    add_ics_line(lines, "END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def add_timezone(lines: list[str]) -> None:
    add_ics_line(lines, "BEGIN:VTIMEZONE")
    add_ics_line(lines, "TZID:Asia/Shanghai")
    add_ics_line(lines, "X-LIC-LOCATION:Asia/Shanghai")
    add_ics_line(lines, "BEGIN:STANDARD")
    add_ics_line(lines, "TZOFFSETFROM:+0800")
    add_ics_line(lines, "TZOFFSETTO:+0800")
    add_ics_line(lines, "TZNAME:CST")
    add_ics_line(lines, "DTSTART:19700101T000000")
    add_ics_line(lines, "END:STANDARD")
    add_ics_line(lines, "END:VTIMEZONE")


def write_report(items: list[dict[str, Any]], articles: list[dict[str, Any]]) -> None:
    snapshot = {
        "generatedAt": now_utc().isoformat(),
        "source": {
            "alphaTokenApi": ALPHA_TOKEN_API,
            "cmsCatalogs": CMS_CATALOGS,
            "binanceAlphaUrl": BINANCE_ALPHA_URL,
        },
        "items": items,
        "candidateAnnouncements": [
            {
                "title": article.get("title"),
                "code": article.get("code"),
                "url": article.get("url"),
                "releaseDate": article.get("releaseDate"),
                "catalogName": article.get("catalogName"),
            }
            for article in articles
        ],
    }
    (DATA_DIR / "alpha_airdrops.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    HISTORY_FILE.write_text(
        json.dumps(
            {
                "generatedAt": snapshot["generatedAt"],
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Binance Wallet Alpha 空投快照",
        "",
        f"生成时间: {snapshot['generatedAt']}",
        "",
        "本文件由 Binance 官方接口、官方公告和官方 X 账号公开信息生成。没有解析到明确规则的项目，需要在 Binance Wallet > Alpha > Events 中核验领取时间、领取门槛和领取内容。",
        "",
        "## 日历项目",
        "",
    ]
    if not items:
        lines.append("当前配置窗口内没有找到近期官方 `onlineAirdrop=true` 的 Alpha 币种。")
    for item in items:
        local_time = dt.datetime.fromisoformat(item["listingTime"]).astimezone(
            dt.timezone(dt.timedelta(hours=8))
        )
        time_text = (
            local_time.strftime("%Y-%m-%d")
            if item.get("dateOnly")
            else local_time.strftime("%Y-%m-%d %H:%M")
        )
        lines.extend(
            [
                f"### {item.get('symbol')} - {item.get('name')}",
                "",
                f"- 时间: {time_text} Asia/Shanghai",
                f"- 来源: {item.get('source')}",
            ]
        )
        if item.get("dateOnly"):
            lines.append("- 时间精度: 来源只明确到日期，具体开放时间待官方活动页确认。")
        if item.get("alphaId"):
            lines.append(f"- Alpha ID: {item.get('alphaId')}")
        if item.get("chainName"):
            lines.append(f"- 链: {item.get('chainName')}")
        if item.get("onlineAirdrop") is not None:
            lines.append(
                f"- 官方字段: onlineAirdrop={item.get('onlineAirdrop')}, onlineTge={item.get('onlineTge')}, mulPoint={item.get('mulPoint')}"
            )
        if item.get("ruleSummary"):
            lines.append("- 从官方来源解析到的规则或说明:")
            lines.extend(f"  - {line}" for line in item["ruleSummary"][:6])
        else:
            lines.append("- 规则状态: 暂未从官方公告解析到明确领取规则，请在 Alpha Events 中核验。")
        if item.get("announcementUrls"):
            lines.append("- 匹配到的官方公告:")
            lines.extend(f"  - {url}" for url in item["announcementUrls"])
        lines.append("")

    (DATA_DIR / "alpha_airdrops.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback-days", type=int, default=3)
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--cms-pages", type=int, default=1)
    parser.add_argument("--cms-page-size", type=int, default=20)
    parser.add_argument(
        "--social-accounts",
        default="binancezh,BinanceWallet",
        help="Comma-separated official X accounts to scan through public mirrors",
    )
    parser.add_argument("--social-posts", type=int, default=8, help="Max relevant posts per social account")
    parser.add_argument(
        "--social-threads",
        type=int,
        default=20,
        help="Max recent historical X status threads to rescan for follow-up updates",
    )
    parser.add_argument("--no-social", action="store_true", help="Disable social-source scanning")
    parser.add_argument(
        "--history-url",
        default=DEFAULT_HISTORY_URL,
        help="Published history.json URL to preserve previously discovered events",
    )
    parser.add_argument("--no-history", action="store_true", help="Disable durable history merging")
    parser.add_argument(
        "--include-daily-check",
        action="store_true",
        help="Also include a daily manual Alpha Events check reminder",
    )
    parser.add_argument("--check-time", default="20:30", help="Daily manual check time in Asia/Shanghai, HH:MM")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dirs()

    if not re.fullmatch(r"\d{1,2}:\d{2}", args.check_time):
        raise SystemExit("--check-time must be HH:MM")

    tokens = fetch_alpha_tokens()
    raw_articles = fetch_candidate_articles(args.cms_pages, args.cms_page_size)
    detailed_articles: list[dict[str, Any]] = []
    for article in raw_articles[:12]:
        try:
            detailed_articles.append(fetch_article_detail(article))
        except RuntimeError as exc:
            print(f"warning: article detail skipped for {article.get('title')}: {exc}", file=sys.stderr)

    history_items: list[dict[str, Any]] = []
    if not args.no_history:
        history_items = load_history(args.history_url)

    items = build_items(
        tokens,
        detailed_articles,
        lookback_days=args.lookback_days,
        horizon_days=args.horizon_days,
    )
    social_posts: list[dict[str, Any]] = []
    if not args.no_social:
        social_accounts = [account.strip() for account in args.social_accounts.split(",")]
        allowed_accounts = {account.strip().lstrip("@").lower() for account in social_accounts if account.strip()}
        social_posts = fetch_social_posts(social_accounts, args.social_posts)
        if history_items and args.social_threads > 0:
            thread_urls = social_status_urls_from_history(
                history_items,
                lookback_days=args.lookback_days,
                horizon_days=args.horizon_days,
                max_urls=args.social_threads,
            )
            social_posts.extend(fetch_social_thread_posts(thread_urls, allowed_accounts, args.social_posts))
            social_posts = dedupe_posts(social_posts)
        items.extend(
            build_social_items(
                social_posts,
                lookback_days=args.lookback_days,
                horizon_days=args.horizon_days,
            )
        )
    items.extend(load_manual_items())
    items = merge_items(items)
    if not args.no_history:
        items = merge_history(history_items, items)
    calendar = build_calendar(
        items,
        include_daily_check=args.include_daily_check,
        check_time=args.check_time,
    )
    (PUBLIC_DIR / "binance-alpha-airdrops.ics").write_text(calendar, encoding="utf-8")
    write_report(items, detailed_articles)

    generated = PUBLIC_DIR / "binance-alpha-airdrops.ics"
    print(
        textwrap.dedent(
            f"""\
            已更新 {generated}
            日历项目: {len(items)} 个 Alpha 空投提醒
            每日检查提醒: {'已启用' if args.include_daily_check else '未启用'}
            Last-Modified: {email.utils.format_datetime(now_utc(), usegmt=True)}
            """
        ).strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
