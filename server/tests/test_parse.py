from datetime import datetime

from app.parse import extract_term_query, glossary_lookup, parse_schedule, contains_forbidden


def test_what_is() -> None:
    assert extract_term_query("что такое RFC?") == "RFC"


def test_schedule() -> None:
    now = datetime(2026, 8, 1, 12, 0)
    got = parse_schedule("запланировать созвон 15.09.2026 18:30", now)
    assert got is not None
    title, when = got
    assert "созвон" in title
    assert when.day == 15 and when.hour == 18


def test_forbidden() -> None:
    assert contains_forbidden("ну блин хуй", ["хуй"])


def test_glossary() -> None:
    hit = glossary_lookup("RFC", {"RFC": "Request for Comments"})
    assert hit and hit[0] == "RFC"
