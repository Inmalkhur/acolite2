from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return text.replace("ё", "е")


def contains_forbidden(text: str, words: list[str]) -> bool:
    n = normalize(text)
    return any(normalize(w) in n for w in words if w.strip())


WHAT_IS_RE = re.compile(r"(что такое|что значит|определение)\s+(.+?)[\?!.]*$", re.I)
SCHEDULE_RE = re.compile(r"запланировать\s*[:\-]?\s*(.+)", re.I)
TODO_RE = re.compile(r"^(сделаю|todo)\s*[:\-]?\s*(.+)", re.I)
DATE_RE = re.compile(
    r"(?P<d>\d{1,2})[./](?P<m>\d{1,2})(?:[./](?P<y>\d{2,4}))?"
    r"(?:[ T]+(?P<h>\d{1,2})[:.](?P<min>\d{2}))?"
)


def extract_term_query(text: str) -> str | None:
    m = WHAT_IS_RE.search(text.strip())
    if m:
        return m.group(2).strip(" «»\"'")
    return None


def parse_schedule(text: str, now: datetime) -> tuple[str, datetime] | None:
    m = SCHEDULE_RE.search(text)
    if not m:
        return None
    rest = m.group(1).strip()
    dm = DATE_RE.search(rest)
    if not dm:
        return None
    d = int(dm.group("d"))
    mo = int(dm.group("m"))
    y = dm.group("y")
    year = now.year if not y else int(y)
    if year < 100:
        year += 2000
    h = int(dm.group("h") or 12)
    minute = int(dm.group("min") or 0)
    try:
        when = datetime(year, mo, d, h, minute)
    except ValueError:
        return None
    title = (rest[: dm.start()] + rest[dm.end() :]).strip(" —,-")
    if not title:
        title = rest
    if when < now - timedelta(minutes=1):
        return None
    return title, when


def glossary_lookup(query: str, glossary: dict[str, str]) -> tuple[str, str] | None:
    q = normalize(query)
    for term, body in glossary.items():
        if q == normalize(term) or normalize(term) in q or q in normalize(term):
            return term, body
    for term, body in glossary.items():
        if q in normalize(body[:200]):
            return term, body
    return None
