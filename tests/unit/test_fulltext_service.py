"""Unit tests for full-text keyword search.

Postgres isn't available in unit tests, so we mock the session's execute and
assert the function passes bound parameters (not string interpolation) and
maps rows correctly.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.fulltext_service import keyword_search


def _row(**kw):
    return SimpleNamespace(**kw)


def test_keyword_search_uses_bound_params_and_maps_rows():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        _row(id=1, name="Invoice Q1", status="completed", owner_id=7, rank=0.91),
        _row(id=2, name="Invoice Q2", status="completed", owner_id=7, rank=0.42),
    ]

    hits = keyword_search(db, "invoice", owner_id=7, limit=5)

    # bound params passed as a dict — no f-string interpolation of user input
    args, kwargs = db.execute.call_args
    params = args[1]
    assert params == {"q": "invoice", "owner_id": 7, "limit": 5}

    assert [h.id for h in hits] == [1, 2]
    assert hits[0].rank == 0.91
    assert hits[0].name == "Invoice Q1"


def test_keyword_search_handles_empty_results():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = []
    assert keyword_search(db, "nothing", limit=10) == []
