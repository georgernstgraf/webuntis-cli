"""`lesson roster` helpers and wiring (no network, fictitious data only)."""

import argparse
from datetime import date

import pytest

from webuntis_cli import cli_lesson


def _matrix():
    return {
        "lessonPeriods": [
            {"id": 1, "date": 20260918, "studentCount": 2},
            {"id": 2, "date": 20260925, "studentCount": 1},
        ],
        "allKlassen": [{"id": 10, "name": "3AAIF"},
                       {"id": 20, "name": "3BAIF"}],
        "allStudents": [
            {"id": 1, "name": "Muster Eri",
             "klasse": 10, "attendedPeriods": [20260918, 20260925]},
            {"id": 2, "name": "Beispiel Max",
             "klasse": 20, "attendedPeriods": [20260918]},
            {"id": 3, "name": "Auslauf Lin",
             "klasse": 10, "attendedPeriods": []},
            {"id": 4, "name": "Fremd Tom",
             "klasse": -1, "attendedPeriods": [20260918]},
        ],
    }


def _overview():
    return {1: {"firstName": "Erika", "lastName": "Muster",
                "classInfo": {"id": 10, "name": "3AAIF"}},
            2: {"firstName": "Max", "lastName": "Beispiel",
                "classInfo": {"id": 20, "name": "3BAIF"}},
            3: {"firstName": "Lina", "lastName": "Auslauf",
                "classInfo": {"id": 10, "name": "3AAIF"}}}


def test_datum_arg():
    assert cli_lesson._datum_arg("2026-09-18") == "2026-09-18"
    assert cli_lesson._datum_arg("heute") == date.today().isoformat()
    assert cli_lesson._datum_arg("HEUTE") == date.today().isoformat()
    with pytest.raises(ValueError):
        cli_lesson._datum_arg("gestern")


def test_tsv_cell_sanitizes():
    assert cli_lesson._tsv_cell("a\tb\nc") == "a b c"
    assert cli_lesson._tsv_cell(None) == ""
    assert cli_lesson._tsv_cell(10) == "10"


def test_roster_rows_filters_sorts_and_joins():
    rows, unmatched = cli_lesson._roster_rows(
        _matrix(), _overview(), 20260918)
    # Auslauf (id 3) has no attendance on the day -> excluded
    assert rows == [("Beispiel Max", "3BAIF"),
                    ("Fremd Tom", "-1"),
                    ("Muster Erika", "3AAIF")]
    # Fremd (id 4) not in overview -> short matrix name fallback
    assert unmatched == ["Fremd Tom"]


def test_roster_rows_other_date():
    rows, _ = cli_lesson._roster_rows(_matrix(), _overview(), 20260925)
    assert rows == [("Muster Erika", "3AAIF")]


class _FakeClient:
    def __init__(self, matrix):
        self._matrix = matrix

    def resolve_schoolyear_id(self, override=None):
        return 24

    def get_student_lesson_period_matrix(self, lsid, school_year_id=None):
        assert lsid == 218839
        return {"result": self._matrix}

    def get_students_overview(self):
        return {"students": [
            {"id": 1, "firstName": "Erika", "lastName": "Muster",
             "classInfo": {"id": 10, "name": "3AAIF"}},
            {"id": 2, "firstName": "Max", "lastName": "Beispiel",
             "classInfo": {"id": 20, "name": "3BAIF"}},
        ]}


def _args(**kw):
    base = dict(lsid=218839, klasse_fach=None,
                datum="2026-09-18", ohne_kopf=False, json=False,
                school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_cmd_roster_tsv(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    rc = cli_lesson.cmd_lesson_roster(_args())
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Name\tKlasse"
    assert out[1:] == ["Beispiel Max\t3BAIF",
                       "Fremd Tom\t-1",
                       "Muster Erika\t3AAIF"]


def test_cmd_roster_no_header_and_mismatch_warn(monkeypatch, capsys):
    m = _matrix()
    m["lessonPeriods"][0]["studentCount"] = 99  # force mismatch
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(m))
    rc = cli_lesson.cmd_lesson_roster(_args(ohne_kopf=True))
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines()[0].startswith("Beispiel Max\t")
    assert "studentCount=99, aber 3 Zeilen" in captured.err


def test_cmd_roster_fallback_uses_nearest_future(monkeypatch, capsys):
    import json
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    # 2026-09-20 has no unit: future 2026-09-25 wins over nearer past
    rc = cli_lesson.cmd_lesson_roster(_args(json=True, datum="2026-09-20"))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["date"] == "2026-09-25"
    assert payload["requestedDate"] == "2026-09-20"
    assert [s["name"] for s in payload["students"]] == ["Muster Erika"]
    assert "nächster Termin 2026-09-25" in captured.err


def test_cmd_roster_fallback_last_held(monkeypatch, capsys):
    import json
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    # beyond all units: last held unit wins
    rc = cli_lesson.cmd_lesson_roster(_args(json=True, datum="2027-05-01"))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["date"] == "2026-09-25"
    assert payload["requestedDate"] == "2027-05-01"


def test_cmd_roster_no_units_at_all(monkeypatch, capsys):
    from webuntis_cli.errors import NotFoundError
    m = _matrix()
    m["lessonPeriods"] = []
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(m))
    with pytest.raises(NotFoundError, match="keine Lesson-Termine"):
        cli_lesson.cmd_lesson_roster(_args(datum="2026-09-20"))


def test_cmd_roster_json(monkeypatch, capsys):
    import json
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    rc = cli_lesson.cmd_lesson_roster(_args(json=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lsId"] == 218839
    assert payload["date"] == "2026-09-18"
    assert [s["name"] for s in payload["students"]] == [
        "Beispiel Max", "Fremd Tom", "Muster Erika"]


def test_pick_closest_lesson():
    pick = cli_lesson._pick_closest_lesson
    matches = {10: ["2026-09-15", "2026-09-22"],
               20: ["2026-09-11", "2026-09-18"]}
    # exact date hit wins
    assert pick(matches, "2026-09-18") == 20
    assert pick(matches, "2026-09-22") == 10
    # otherwise smallest day distance (09-19: 20 is 1 away, 10 is 3 away)
    assert pick(matches, "2026-09-19") == 20
    # tie -> smallest lsId (09-16: both 2 and 1... 10:{15,22}->1, 20:{11,18}->2 => 10)
    assert pick(matches, "2026-09-16") == 10
    # single match returned as-is
    assert pick({7: ["2026-01-01"]}, "2026-09-18") == 7


def _open_entries():
    # enriched entries as _open_period_entries returns them (fake data)
    return [
        {"periodId": 1, "class": "4AHWIT", "classId": 1,
         "subject": "PMM1x", "date": "2026-09-15", "lsId": 215910},
        {"periodId": 2, "class": "4AHWIT", "classId": 1,
         "subject": "PMM1y", "date": "2026-09-11", "lsId": 215916},
        {"periodId": 3, "class": "4AHWIT", "classId": 1,
         "subject": "PMM1y", "date": "2026-09-18", "lsId": 215916},
    ]


def _pos(typ, short, long_):
    return [{"current": {"type": typ, "shortName": short,
                         "longName": long_}, "removed": None}]


def _plan_entry(day, start, end, ids, subject):
    return {"ids": ids,
            "duration": {"start": f"{day}T{start}", "end": f"{day}T{end}"},
            "type": "NORMAL_TEACHING_PERIOD", "status": "REGULAR",
            "position1": _pos("TEACHER", "MUS", "Musterlehrer"),
            "position2": _pos("SUBJECT", subject, f"Fach {subject}"),
            "position3": _pos("ROOM", "A1.01", "Stammklasse"),
            "position4": None}


def _plan_response():
    # timetable/entries-Response (Woche Mo 2026-09-14..Sa 2026-09-19),
    # Klassen-Plan: Klasse steht im day.resource, position4 ist null
    days = {}
    for day, entries in {
        "2026-09-15": [_plan_entry("2026-09-15", "08:00", "08:50",
                                   [101], "PMM1x")],
        "2026-09-16": [_plan_entry("2026-09-16", "09:55", "10:45",
                                   [102], "PMM1y")],
        "2026-09-18": [_plan_entry("2026-09-18", "08:00", "09:40",
                                   [103, 104], "PMM1y")],
    }.items():
        days[day] = {"date": day, "resourceType": "CLASS",
                     "resource": {"id": 1, "shortName": "4AHWIT",
                                  "longName": "Fiktive Klasse"},
                     "status": "REGULAR", "dayEntries": [],
                     "gridEntries": entries, "backEntries": []}
    return {"format": 1, "days": [days[d] for d in sorted(days)],
            "errors": []}


_LSID_BY_KEY = {  # (start-datetime) -> lessonId der Fake-Detail-Response
    "2026-09-15T08:00:00": 215910,
    "2026-09-16T09:55:00": 215916,
    "2026-09-18T08:00:00": 215916,
}


class _FakeResolverClient:
    """Plan-Primärpfad: get_klassen + entries + detail (Fakedaten)."""

    fail_plan = False

    def resolve_schoolyear_id(self, override=None):
        return 24

    def get_klassen(self, schoolyear_id=None):
        if self.fail_plan:
            raise AttributeError("plan nicht verfügbar")
        return {"result": [{"id": 1, "name": "4AHWIT",
                            "longName": "Fiktive Klasse"}]}

    def get_timetable_entries(self, resource_type, resource_id,
                              start, end, timetable_type="STANDARD",
                              school_year_id=None):
        if self.fail_plan:
            raise AttributeError("plan nicht verfügbar")
        return _plan_response()

    def get_calendar_entry_detail(self, element_type, element_id,
                                  start_datetime, end_datetime,
                                  school_year_id=None):
        assert element_type == 1 and element_id == 1
        lsid = _LSID_BY_KEY[start_datetime]
        return {"calendarEntries": [
            {"id": 1, "lesson": {"lessonId": lsid, "lessonNumber": 1},
             "klasses": [{"id": 1, "shortName": "4AHWIT"}],
             "singleEntries": [{"id": 103}]}]}


def test_resolve_lesson_picks_closest_and_warns(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    lesson = cli_lesson._resolve_lesson_from_class_subject(
        _FakeResolverClient(), 24, "4ahwit", "pmm",
        ref_date="2026-09-18")
    assert lesson["lsId"] == 215916
    assert lesson["class"] == "4AHWIT"
    assert lesson["subject"] == "PMM1y"
    assert lesson["classId"] == 1
    assert lesson["candidates"] == [215910, 215916]
    err = capsys.readouterr().err.splitlines()
    assert err[0] == ("Warnung: mehrdeutige Lesson für 4ahwit/pmm: "
                      "2 Kandidaten, gewählt lsid=215916 "
                      "(nächste zu 2026-09-18)")
    assert err[1:] == ["4AHWIT/PMM1x (2026-09-15)",
                       "4AHWIT/PMM1y (2026-09-18)"]


def test_nearest_date():
    near = cli_lesson._nearest_date
    assert near(["2026-09-15", "2026-09-22", "2026-09-29"],
                "2026-09-18") == "2026-09-15"
    assert near(["2026-09-11", "2026-09-18"], "2026-09-18") == "2026-09-18"
    # tie (09-16 between 09-15 and 09-17) -> earlier date
    assert near(["2026-09-15", "2026-09-17"], "2026-09-16") == "2026-09-15"


def test_resolve_lesson_single_no_warning(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    lesson = cli_lesson._resolve_lesson_from_class_subject(
        _FakeResolverClient(), 24, "4AHWIT", "PMM1x")
    assert lesson["lsId"] == 215910
    assert capsys.readouterr().err == ""


def test_resolve_lesson_fallback_open_periods(monkeypatch, capsys):
    # Plan nicht nutzbar -> Hinweis + Fallback über offene Perioden
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    fake = _FakeResolverClient()
    fake.fail_plan = True
    lesson = cli_lesson._resolve_lesson_from_class_subject(
        fake, 24, "4AHWIT", "PMM1y", ref_date="2026-09-18")
    assert lesson["lsId"] == 215916
    err = capsys.readouterr().err
    assert "Fallback über offene Perioden" in err


def test_cmd_roster_class_subject_prints_exact_label(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _FakeClient(_matrix()))
    # matrix only spans 20260918/20260925; resolve against that date
    args = _args(lsid=None, klasse_fach="4ahwit/PMM",
                 datum="2026-09-18")
    # fake matrix lsIds differ from resolver lsIds — bypass resolver pick:
    # point the fake entries at the matrix lsId for this end-to-end check
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e:
                        [{**en, "lsId": 218839} for en in _open_entries()])
    rc = cli_lesson.cmd_lesson_roster(args)
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "4AHWIT/PMM1y"
    assert out[1] == "Name\tKlasse"


def test_resolve_lesson_no_match_raises(monkeypatch):
    monkeypatch.setattr(cli_lesson, "_open_period_entries",
                        lambda c, sy, s, e: _open_entries())
    with pytest.raises(RuntimeError, match="keine Lesson für"):
        cli_lesson._resolve_lesson_from_class_subject(
            _FakeResolverClient(), 24, "9ZZZ", "PMM")
