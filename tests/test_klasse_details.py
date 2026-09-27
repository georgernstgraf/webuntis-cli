"""`klasse` Default = Kopf mit klassen-id; Fächer/Roster nur mit --details."""

import argparse
import json

from webuntis_cli import cli_klasse


def _args(**kw):
    base = dict(klassenname="3BAIF", fach=None, details=False, start=None,
                end=None, json=False, school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


class _FakeClient:
    def resolve_schoolyear_id(self, override=None):
        return 24


def _kv_info(c, sy, name):
    return {"classId": 4107, "name": "3BAIF", "longName": "Fiktive Klasse",
            "teachers": {147: "Muster, Klaus"}}


def _install(monkeypatch, calls):
    monkeypatch.setattr(cli_klasse, "_make_client", lambda args: _FakeClient())
    monkeypatch.setattr(cli_klasse, "_kv_info", _kv_info)

    def faecher(c, sy, name, start, end, fach=None):
        calls["faecher"] = True
        return [], "2026-09-14", "2026-09-19"

    def roster(c, name):
        calls["roster"] = True
        return [("Muster Erika", "3BAIF")]

    monkeypatch.setattr(cli_klasse, "_faecher_groups", faecher)
    monkeypatch.setattr(cli_klasse, "_klassen_roster", roster)


def test_default_head_only(monkeypatch, capsys):
    calls = {"faecher": False, "roster": False}
    _install(monkeypatch, calls)
    rc = cli_klasse.cmd_klasse(_args())
    assert rc == 0
    out = capsys.readouterr()
    assert "3BAIF (Fiktive Klasse)" in out.out
    assert "klassen-id: 4107" in out.out
    assert "KV: Muster, Klaus" in out.out
    assert "Fächer und Roster mit --details" in out.err
    assert calls == {"faecher": False, "roster": False}


def test_details_shows_faecher_und_roster(monkeypatch, capsys):
    calls = {"faecher": False, "roster": False}
    _install(monkeypatch, calls)
    rc = cli_klasse.cmd_klasse(_args(details=True))
    assert rc == 0
    out = capsys.readouterr()
    assert "klassen-id: 4107" in out.out
    assert "Fächer" in out.out
    assert "Roster (1 Schüler)" in out.out
    assert calls == {"faecher": True, "roster": True}


def test_fach_implies_details(monkeypatch, capsys):
    calls = {"faecher": False, "roster": False}
    _install(monkeypatch, calls)
    rc = cli_klasse.cmd_klasse(_args(fach="SWP"))
    assert rc == 0
    assert calls == {"faecher": True, "roster": True}


def test_json_default_head_only(monkeypatch, capsys):
    calls = {"faecher": False, "roster": False}
    _install(monkeypatch, calls)
    rc = cli_klasse.cmd_klasse(_args(json=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["classId"] == 4107
    assert payload["class"] == "3BAIF"
    assert "lessons" not in payload
    assert "students" not in payload
    assert calls == {"faecher": False, "roster": False}


def test_json_details_includes_lists(monkeypatch, capsys):
    calls = {"faecher": False, "roster": False}
    _install(monkeypatch, calls)
    rc = cli_klasse.cmd_klasse(_args(json=True, details=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lessons"] == []
    assert payload["students"] == [{"name": "Muster Erika", "klasse": "3BAIF"}]
    assert payload["range"] == {"start": "2026-09-14", "end": "2026-09-19"}
