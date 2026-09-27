"""Every write command defaults to testlauf; only --ausfuehren writes."""

import argparse
import json

from webuntis_cli import cli_lesson, cli_offen


class _WriteFake:
    def __init__(self):
        self.topics = []
        self.checked = []

    def resolve_schoolyear_id(self, override=None):
        return 24

    def set_lesson_topic(self, period_id, topic_id, text,
                         school_year_id=None):
        self.topics.append((period_id, topic_id, text))
        return {"topics": [{"id": topic_id}]}

    def check_absences(self, pid):
        self.checked.append(pid)
        return {"success": True, "periodId": pid}


def _lehrstoff_args(**kw):
    base = dict(termin=608000, thema=222, text="Inhalt", text_file=None,
                text_stdin=False, testlauf=True, school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_lehrstoff_eintragen_testlauf_no_write(monkeypatch, capsys):
    fake = _WriteFake()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_lehrstoff_eintragen(_lehrstoff_args(testlauf=True))
    assert rc == 0
    assert fake.topics == []
    out = capsys.readouterr()
    assert "TESTLAUF" in out.out
    assert "Schreiben mit --ausfuehren" in out.err
    # Testlauf (nur --ausfuehren fehlt) zeigt KEINE Hilfe.
    assert "usage:" not in out.out
    assert "usage:" not in out.err


def test_lehrstoff_eintragen_ausfuehren_writes(monkeypatch, capsys):
    fake = _WriteFake()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_lehrstoff_eintragen(_lehrstoff_args(testlauf=False))
    assert rc == 0
    assert fake.topics == [(608000, 222, "Inhalt")]


def _offen_args(tmp_path, **kw):
    f = tmp_path / "batch.json"
    f.write_text(json.dumps([{"periodId": 111, "topicId": 222,
                              "text": "Text"}]), encoding="utf-8")
    base = dict(datei=str(f), pause=1.0, testlauf=True, school_year_id=None,
                start=None, end=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_offen_eintragen_testlauf_no_write(tmp_path, monkeypatch, capsys):
    def _boom(args):
        raise AssertionError("client must not be created in testlauf")
    monkeypatch.setattr(cli_offen, "_make_client", _boom)
    rc = cli_offen.cmd_offen_eintragen(_offen_args(tmp_path, testlauf=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == [{"periodId": 111, "topicId": 222, "text": "Text"}]


def test_offen_eintragen_ausfuehren_writes(tmp_path, monkeypatch, capsys):
    fake = _WriteFake()
    monkeypatch.setattr(cli_offen, "_make_client", lambda args: fake)
    rc = cli_offen.cmd_offen_eintragen(_offen_args(tmp_path, testlauf=False))
    assert rc == 0
    assert fake.topics == [(111, 222, "Text")]


def _absenzen_pruefen_args(**kw):
    base = dict(termin=608000, pause=1.0, start=None, end=None,
                school_year_id=None, testlauf=True, klasse_fach="5XZY/SWP1x",
                lsid=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_absenzen_pruefen_testlauf_no_write(monkeypatch, capsys):
    fake = _WriteFake()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_absenzen_pruefen(
        _absenzen_pruefen_args(testlauf=True))
    assert rc == 0
    assert fake.checked == []
    out = json.loads(capsys.readouterr().out)
    assert out == [{"periodId": 608000}]


def test_absenzen_pruefen_ausfuehren_writes(monkeypatch, capsys):
    fake = _WriteFake()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_absenzen_pruefen(
        _absenzen_pruefen_args(testlauf=False))
    assert rc == 0
    assert fake.checked == [608000]
