"""Teilnehmer-Payload: Heimatklasse aus der Lesson ableiten (--klassen-id optional)."""

import argparse

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
