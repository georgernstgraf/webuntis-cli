"""Teilnehmer-Payload: Heimatklasse aus der Lesson ableiten (--klassen-id optional)."""

import argparse
import json

import pytest

from webuntis_cli import cli_lesson


def _matrix(lesson_klassen=None):
    m = {
        "allStudents": [
            {"id": 1, "name": "Muster Eri", "klasse": 10,
             "attendedPeriods": [20260918]},
            {"id": 2, "name": "Auslauf Lin", "klasse": 10,
             "attendedPeriods": []},
            {"id": 3, "name": "Beispiel Max", "klasse": 20,
             "attendedPeriods": [20260918]},
            {"id": 4, "name": "Leer Gast", "klasse": 20,
             "attendedPeriods": []},
            {"id": 5, "name": "Fremd Tom", "klasse": -1,
             "attendedPeriods": [20260918]},
        ],
    }
    if lesson_klassen is not None:
        m["lessonKlassen"] = lesson_klassen
    return m


def test_lesson_class_ids_from_dicts():
    assert cli_lesson._lesson_class_ids(_matrix([{"id": 10}])) == {10}
    assert cli_lesson._lesson_class_ids(
        _matrix([{"id": 10}, {"id": 20}])) == {10, 20}


def test_lesson_class_ids_from_ints():
    assert cli_lesson._lesson_class_ids(_matrix([10, 20])) == {10, 20}


def test_lesson_class_ids_fallback_attending_classes():
    # ohne lessonKlassen: Klassen der Anwesenden (ohne -1)
    assert cli_lesson._lesson_class_ids(_matrix()) == {10, 20}


def test_build_students_keeps_class_roster_and_attendees():
    keep = cli_lesson._build_students_payload(
        _matrix()["allStudents"], {10}, add_ids=[2], remove_ids=[],
        lesson_dates=[20260918])
    by_id = {e["id"]: e for e in keep}
    # Klasse 10 unverändert (Anwesender + nicht anwesender Roster)
    assert 1 in by_id and 2 in by_id
    # attendee of other class stays, non-attending other-class student drops
    assert 3 in by_id
    assert 4 not in by_id
    # attending student without class stays
    assert 5 in by_id
    # added student gets all lesson dates (union with existing)
    assert by_id[2]["attendedPeriods"] == [20260918]


def test_build_students_remove_empties():
    keep = cli_lesson._build_students_payload(
        _matrix()["allStudents"], {10}, add_ids=[], remove_ids=[1],
        lesson_dates=[20260918, 20260925])
    by_id = {e["id"]: e for e in keep}
    assert by_id[1]["attendedPeriods"] == []
    # lesson class roster otherwise unchanged incl. its empty entry
    assert 2 in by_id


def test_resolve_class_ids_explicit_overrides():
    args = argparse.Namespace(klassen_id=99)
    assert cli_lesson._resolve_class_ids(args, _matrix([{"id": 10}])) == {99}


def test_resolve_class_ids_derives_and_reports(capsys):
    args = argparse.Namespace(klassen_id=None)
    ids = cli_lesson._resolve_class_ids(args, _matrix([{"id": 4107}]))
    assert ids == {4107}
    err = capsys.readouterr().err
    assert "Klassen-ID 4107 (aus Lesson abgeleitet" in err


def test_resolve_class_ids_warns_when_underivable(capsys):
    args = argparse.Namespace(klassen_id=None)
    m = {"allStudents": [{"id": 1, "name": "A", "klasse": -1,
                          "attendedPeriods": []}]}
    assert cli_lesson._resolve_class_ids(args, m) == set()
    assert "keine Lesson-Klasse ableitbar" in capsys.readouterr().err


class _AufnehmenFakeClient:
    """`lesson aufnehmen`: Matrix + students/overview (kein Netz)."""

    def __init__(self):
        self.submitted = None

    def resolve_schoolyear_id(self, override=None):
        return 24

    def get_student_lesson_period_matrix(self, lsid, school_year_id=None):
        assert lsid == 218839
        return {"result": {
            "lessonKlassen": [{"id": 4110}],
            "mainStudentgroupId": 77,
            "startDate": 20260911,
            "endDate": 20260925,
            "lessonPeriods": [
                {"id": 1, "date": 20260918},
                {"id": 2, "date": 20260925},
            ],
            "allStudents": [
                {"id": 1, "name": "Muster Eri", "klasse": 4110,
                 "attendedPeriods": [20260918]},
                {"id": 2, "name": "Leer Lin", "klasse": 4110,
                 "attendedPeriods": []},
                # Matrix-Name verkürzt/umgedreht ("Khalil Amm"),
                # Fremdklasse (nicht Lesson-Heimatklasse 4110)
                {"id": 19492, "name": "Khalil Amm", "klasse": 5500,
                 "attendedPeriods": []},
            ],
        }}

    def get_students_overview(self):
        return {"students": [
            {"id": 1, "firstName": "Erika", "lastName": "Muster",
             "shortName": "MusterEri",
             "classInfo": {"id": 4110, "name": "3BAIF"}},
            {"id": 2, "firstName": "Lina", "lastName": "Leer",
             "shortName": "LeerLin",
             "classInfo": {"id": 4110, "name": "3BAIF"}},
            {"id": 19492, "firstName": "Ammar", "lastName": "Khalil",
             "shortName": "KhalilAmm",
             "classInfo": {"id": 5500, "name": "5AAIF"}},
        ]}

    def submit_student_lesson_period_data(self, ls_id, main_studentgroup_id,
                                          students, start_date, end_date,
                                          school_year_id=None):
        self.submitted = {"ls_id": ls_id, "main": main_studentgroup_id,
                          "students": students, "start": start_date,
                          "end": end_date}
        return {"success": True}


def _auf_args(**kw):
    base = dict(lsid=218839, klasse_fach=None, klassen_id=None,
                schueler_id=None, schueler_name=None, ausgabe=None,
                details=False, testlauf=True, school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_aufnehmen_resolves_external_student_by_full_name(monkeypatch, capsys):
    fake = _AufnehmenFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_lesson_aufnehmen(
        _auf_args(schueler_name="ammar khalil", details=True))
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["student"]["id"] == 19492
    assert summary["student"]["class"] == "5AAIF"
    by_id = {s["id"]: s for s in summary["payload"]["students"]}
    # Heimatklasse-Roster bleibt, aufgenommener externer Schüler kommt dazu
    assert {1, 2, 19492} <= set(by_id)
    assert by_id[19492]["attendedPeriods"] == [20260918, 20260925]
    assert by_id[1]["attendedPeriods"] == [20260918]


def test_aufnehmen_resolves_student_by_id(monkeypatch, capsys):
    fake = _AufnehmenFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_lesson_aufnehmen(
        _auf_args(schueler_id=19492, details=True))
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["student"]["id"] == 19492


def test_aufnehmen_ambiguous_name_is_usage_error(monkeypatch, capsys):
    from webuntis_cli.errors import UsageError
    fake = _AufnehmenFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    with pytest.raises(UsageError, match="trifft 2"):
        cli_lesson.cmd_lesson_aufnehmen(_auf_args(schueler_name="li"))


def test_aufnehmen_execute_submits(monkeypatch, capsys):
    fake = _AufnehmenFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_lesson_aufnehmen(
        _auf_args(schueler_id=19492, testlauf=False))
    assert rc == 0
    assert fake.submitted["ls_id"] == 218839
    by_id = {s["id"]: s for s in fake.submitted["students"]}
    assert by_id[19492]["attendedPeriods"] == [20260918, 20260925]
