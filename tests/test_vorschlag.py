"""offen vorschlag: Tages-Blöcke, PMM-Mapping, Supplierungs-Erkennung.

No network, fictitious data only (anonymized — no real ids/names).
"""

import argparse
import json
from collections import namedtuple
from types import SimpleNamespace

import pytest

from webuntis_cli import cli_offen
from webuntis_cli import client as client_mod
from webuntis_cli import gitlog


# ----- entry_is_supplier (reine Funktion) --------------------------------

def _grid(teachers=None, substitution_text=""):
    """Roh-Grid-Block wie timetable/entries, position1 = TEACHER-Liste."""
    pos1 = []
    for short, status, removed in (teachers or []):
        pos1.append({
            "current": {"type": "TEACHER", "status": status,
                        "shortName": short},
            "removed": removed,
        })
    return {"position1": pos1, "substitutionText": substitution_text}


def test_supplier_added_lehrer():
    assert client_mod.entry_is_supplier(
        _grid([("AAA", "ADDED", None)])) is True


def test_supplier_removed_original():
    removed = {"type": "TEACHER", "status": "REMOVED", "shortName": "BBB"}
    assert client_mod.entry_is_supplier(
        _grid([("AAA", "REGULAR", removed)])) is True


def test_supplier_substitution_text():
    assert client_mod.entry_is_supplier(
        _grid([("AAA", "REGULAR", None)], substitution_text="Vertretung")) \
        is True


def test_kein_supplier_regulaer():
    assert client_mod.entry_is_supplier(
        _grid([("AAA", "REGULAR", None)])) is False


def test_supplier_ignoriert_nicht_lehrer_status():
    # ADDED bei ROOM/CLASS zählt nicht als Supplierung
    entry = {"position3": [{"current": {"type": "ROOM", "status": "ADDED",
                                        "shortName": "A1.01"},
                            "removed": None}],
             "substitutionText": ""}
    assert client_mod.entry_is_supplier(entry) is False


# ----- PMM-Mapping --------------------------------------------------------

def test_pmm_prefix_matchet_varianten():
    for subj in ("PMM", "PMMx", "PMMy", "pmm2"):
        repos = client_mod.repos_for_subject(subj)
        assert "GRG-PMM" in repos, subj
        assert "GRG-PMM-T" in repos, subj


# ----- cmd_offen_vorschlag (Fakes, kein Netz) -----------------------------

_Fixed = namedtuple("_Fixed", "repo hash date message files")


def _raw_period(pid, topic_id, cls, cls_id, subj, subj_long, dt_start, lsid):
    return {
        "topicId": topic_id,
        "topicNeeded": True,
        "absCheckNeeded": False,
        "period": {
            "id": pid,
            "lsId": lsid,
            "dtRange": {"start": dt_start, "end": dt_start[:11] + "10:00"},
            "classes": [{"el": {"name": cls, "id": cls_id}}],
            "subject": {"el": {"nameShort": subj, "name": subj_long}},
        },
    }


class _FakeClient:
    def __init__(self, supplier_by_period):
        self._sup = supplier_by_period

    def is_supplier_period(self, class_id, period_id, day,
                           school_year_id=None):
        return self._sup.get(period_id, False)


@pytest.fixture
def vorschlag_env(monkeypatch):
    """Patcht _fetch_open_periods + gitlog; liefert (capturer, args)."""
    state = {}

    def fetch(args):
        return (state["client"], 24, state["periods"])

    monkeypatch.setattr(cli_offen, "_fetch_open_periods", fetch)

    def commits_for(cls, when, repo_filter=None, **kw):
        key = (cls, when.isoformat())
        return state.get("commits", {}).get(key, [])

    def diff_by(repo, hash_, **kw):
        return f"diff-{hash_[:6]}"

    monkeypatch.setattr(gitlog, "get_commits_for_class", commits_for)
    monkeypatch.setattr(gitlog, "get_commit_diff_by_name", diff_by)

    args = argparse.Namespace(start=None, end=None, school_year_id=None,
                              json=True)
    return state, args


def _run(state, args, capsys):
    rc = cli_offen.cmd_offen_vorschlag(args)
    out = capsys.readouterr().out
    return rc, json.loads(out)


def test_tagesbloecke_nicht_jahreslsid(vorschlag_env, capsys):
    """Gleiche lsId an zwei Tagen -> zwei Blöcke mit je eigenem Commit."""
    state, args = vorschlag_env
    state["client"] = _FakeClient({})
    state["commits"] = {
        ("3AAIFI", "2026-09-08"): [_Fixed("GRG-WMC", "a" * 40,
                                          "2026-09-08", "thema tag1",
                                          ["a.md"])],
        ("3AAIFI", "2026-09-15"): [_Fixed("GRG-WMC", "b" * 40,
                                          "2026-09-15", "thema tag2",
                                          ["b.md"])],
    }
    state["periods"] = [
        _raw_period(1, 11, "3AAIFI", 101, "WMC_1", "Medieninformatik",
                    "2026-09-08T08:00", lsid=900),
        _raw_period(2, 12, "3AAIFI", 101, "WMC_1", "Medieninformatik",
                    "2026-09-15T08:00", lsid=900),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    blocks = out["blocks"]
    assert len(blocks) == 2
    texts = {b["date"]: b["proposedText"] for b in blocks}
    assert texts["2026-09-08"] == "thema tag1"
    assert texts["2026-09-15"] == "thema tag2"
    # Blockpartner: ein Block umfasst die Perioden je Tag
    for b in blocks:
        assert len(b["blockPeriods"]) == 1


def test_blockpartner_am_selben_tag_vereinigt(vorschlag_env, capsys):
    """Doppelperiode (gleiche lsId, gleicher Tag) -> EIN Block."""
    state, args = vorschlag_env
    state["client"] = _FakeClient({})
    state["periods"] = [
        _raw_period(1, 11, "3AAIFI", 101, "WMC_1", "Medieninformatik",
                    "2026-09-08T08:00", lsid=900),
        _raw_period(2, 11, "3AAIFI", 101, "WMC_1", "Medieninformatik",
                    "2026-09-08T08:55", lsid=900),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    assert len(out["blocks"]) == 1
    assert sorted(out["blocks"][0]["blockPeriods"]) == [1, 2]


def test_unmapped_supplier_periode_wird_festtext(vorschlag_env, capsys):
    """Fach ohne Repo-Mapping, aber Supplierung -> Festtext 'Supplierung'."""
    state, args = vorschlag_env
    state["client"] = _FakeClient({7: True})
    state["periods"] = [
        _raw_period(7, 77, "3ZZZZT", 777, "XX9", "Fremdfach",
                    "2026-09-09T09:55", lsid=555),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    blocks = out["blocks"]
    assert len(blocks) == 1 and not out["skipped"]
    assert blocks[0]["source"] == "supplier"
    assert blocks[0]["proposedText"] == client_mod.SUPPLIER_TEXT


def test_unmapped_kein_supplier_bleibt_skipped(vorschlag_env, capsys):
    state, args = vorschlag_env
    state["client"] = _FakeClient({})  # keine Supplierung
    state["periods"] = [
        _raw_period(8, 88, "3ZZZZT", 777, "XX9", "Fremdfach",
                    "2026-09-09T09:55", lsid=556),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    assert not out["blocks"]
    assert len(out["skipped"]) == 1
    assert "SUBJECT_REPO_MAP" in out["skipped"][0]["warning"]


def test_gitblock_ohne_commits_und_nicht_supplier_dummy(
        vorschlag_env, capsys):
    state, args = vorschlag_env
    state["client"] = _FakeClient({})
    state["periods"] = [
        _raw_period(9, 99, "3AAIFI", 101, "WMC_1", "Medieninformatik",
                    "2026-09-16T08:00", lsid=901),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    assert out["blocks"][0]["source"] == "dummy"


def test_supplier_check_fehler_blockt_nicht(vorschlag_env, capsys):
    """is_supplier_period wirft -> Warnung, Periode bleibt skipped."""
    state, args = vorschlag_env

    class _Boom(_FakeClient):
        def is_supplier_period(self, *a, **kw):
            raise RuntimeError("netz weg")

    state["client"] = _Boom({})
    state["periods"] = [
        _raw_period(10, 10, "3ZZZZT", 777, "XX9", "Fremdfach",
                    "2026-09-09T09:55", lsid=557),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    assert len(out["skipped"]) == 1
    assert "Supplier-Check" in out["skipped"][0]["warning"]


def test_festtextfach_bleibt_fixed(vorschlag_env, capsys):
    state, args = vorschlag_env
    state["client"] = _FakeClient({})
    state["periods"] = [
        _raw_period(11, 111, "SB", 1, "SS", "Sprechstunde",
                    "2026-09-09T12:35", lsid=560),
    ]
    rc, out = _run(state, args, capsys)
    assert rc == 0
    assert out["blocks"][0]["source"] == "fixed"
    assert out["blocks"][0]["proposedText"] == "Sprechstunde"


def test_lehrstoff_ist_grossgeschrieben_und_at_terminologie():
    assert client_mod.SUPPLIER_TEXT == "Supplierung"
