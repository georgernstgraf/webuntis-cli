"""Absenz-Writes: set_absence/delete_absence/client wiring + CLI-Flow.

No network, fictitious ids only (anonymized — no real ids/names).
"""

import argparse
import json

import pytest

from webuntis_cli import cli_lesson
from webuntis_cli.client import (
    Client,
    _untis_date_to_iso,
    _untis_time_to_hhmm,
)


class _FakeHttp:
    """Fängt _request_with_retry ab und zeichnet Requests auf."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, params=None, data=None, **kwargs):
        self.calls.append({"method": method, "url": url,
                           "params": params, "data": dict(data or {})})
        return self.responses.pop(0)


class _Resp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200
        self.headers = {}
        self.is_redirect = False

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


def _classreg_html(csrf="CSRF1", rows=None, lesson_id=218000):
    vm = {"lessonId": lesson_id, "absenceRows": rows or [],
          "blockStartTime": 1145, "blockEndTime": 1325}
    import html as _h
    escaped = json.dumps(vm).replace('"', "&quot;")
    return (f'<form data-dojo-props="viewModel: {escaped}" action="/x">'
            f'<input type="hidden" name="_csrf" value="{csrf}"/></form>')


def _client(responses):
    c = Client.__new__(Client)
    c.http = _FakeHttp(responses)
    c.host = "https://example.invalid"
    c._session = None
    return c


class _SessionStub:
    cookie_header = "JSESSIONID=x; schoolname=y"


def test_untis_date_and_time_helpers():
    assert _untis_date_to_iso(20260925) == "2026-09-25"
    assert _untis_time_to_hhmm(1145) == "11:45"
    assert _untis_time_to_hhmm(900) == "09:00"
    assert _untis_time_to_hhmm(1755) == "17:55"


def test_set_absence_insert_post():
    rows = [{"absence": {"id": 317000, "startTime": 1145, "endTime": 1325,
                         "startDate": 20260925, "endDate": 20260925,
                         "person": {"id": 21000, "type": 5}}}]
    c = _client([
        _Resp(_classreg_html(csrf="CSRF1")),                 # GET vm
        _Resp(json.dumps({"args": [{"absenceRows": rows}],
                          "success": True})),                 # POST insert
    ])
    c._session = _SessionStub()
    c.session  # property ok
    res = Client.set_absence(c, 608000, 21000, block=True)
    assert res["success"] is True
    get, post = c.http.calls
    assert get["method"] == "GET"
    assert get["params"]["ttid"] == 608000
    assert get["params"]["isBlockSelected"] == "true"
    assert post["method"] == "POST"
    assert post["data"]["insert"] == "insert"
    assert post["data"]["selId"] == "21000"
    assert post["data"]["ttid"] == "608000"
    assert post["data"]["_csrf"] == "CSRF1"
    assert post["data"]["isBlockSelected"] == "true"


def test_delete_absence_dialog_csrf_flow():
    # 1) GET absencedlg (FRISCHES CSRF), 2) POST delete mit genau diesem
    dlg_html = ('<input type="hidden" name="_csrf" value="DLGCSRF"/>'
                '<form data-dojo-props="viewModel: {}" action="/x">')
    c = _client([
        _Resp(dlg_html),
        _Resp(json.dumps({"_data": {"removedAbsenceIds": [317000]},
                          "success": True})),
    ])
    c._session = _SessionStub()
    absence = {"id": 317000, "startTime": 1145, "endTime": 1325,
               "startDate": 20260925, "endDate": 20260925}
    res = Client.delete_absence(c, absence, 608000)
    assert res["success"] is True
    get, post = c.http.calls
    assert get["params"]["selId"] == 317000
    assert get["params"]["abTimetableId"] == 608000
    assert get["params"]["abStartTime"] == 1145
    assert post["data"]["delete"] == "delete"
    assert post["data"]["_csrf"] == "DLGCSRF"
    assert post["data"]["startDate"] == "2026-09-25"
    assert post["data"]["endDate"] == "2026-09-25"
    assert post["data"]["startTime"] == "T11:45"
    assert post["data"]["endTime"] == "T13:25"
    assert post["data"]["absenceReason"] == "-1"


def _abs_args(**kw):
    base = dict(lsId=None, klasse_fach="5xzy/pos1", termin=None,
                datum="2026-09-25", schueler_id=21000, schueler_name=None,
                absenz_id=None, kein_block=False, testlauf=True,
                school_year_id=None)
    base.update(kw)
    return argparse.Namespace(**base)


class _AbsFakeClient:
    def __init__(self):
        self.set_calls = []
        self.vm = {"lessonId": 218000, "absenceRows": [],
                   "blockStartTime": 1145, "blockEndTime": 1325}

    def resolve_schoolyear_id(self, override=None):
        return 24

    def get_students_overview(self):
        return {"students": [
            {"id": 21000, "firstName": "Erika", "lastName": "Muster",
             "shortName": "MusterEri",
             "classInfo": {"id": 111, "name": "5XZY"}}]}

    def get_timetable_entries(self, resource_type, resource_id, start, end,
                              timetable_type="STANDARD",
                              school_year_id=None):
        def cur(typ, short):
            return {"type": typ, "shortName": short, "longName": short,
                    "status": "REGULAR"}
        e = {"ids": [608000, 608001],
             "duration": {"start": "2026-09-25T11:45",
                          "end": "2026-09-25T13:25"},
             "position1": [{"current": cur("TEACHER", "MUS")}],
             "position2": [{"current": cur("SUBJECT", "POS1")}],
             "position4": [{"current": cur("CLASS", "5XZY")}]}
        day = {"date": "2026-09-25", "resourceType": "CLASS",
               "resource": {"id": 111, "shortName": "5XZY",
                            "longName": "K"}, "status": "REGULAR",
               "dayEntries": [], "gridEntries": [e], "backEntries": []}
        return {"format": 1, "days": [day], "errors": []}

    def get_klassen(self, schoolyear_id=None):
        return {"result": [{"id": 111, "name": "5XZY"}]}

    def get_calendar_entry_detail(self, element_type, element_id,
                                  start_datetime, end_datetime,
                                  school_year_id=None):
        return {"calendarEntries": [
            {"lesson": {"lessonId": 218000}}]}

    def get_classreg_viewmodel(self, period_id, block=True):
        return {"viewModel": self.vm, "csrf": "CSRFX"}

    def set_absence(self, period_id, student_id, block=True):
        self.set_calls.append((period_id, student_id, block))
        rows = [{"absence": {"id": 317000, "person": {"id": 21000}}}]
        return {"args": [{"absenceRows": rows}], "success": True}


def test_cmd_absenzen_eintragen_testlauf_no_write(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _AbsFakeClient())
    rc = cli_lesson.cmd_absenzen_eintragen(_abs_args())
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["student"]["id"] == 21000
    assert payload["periodId"] == 608000
    assert payload["block"] is True
    assert "TESTLAUF" in captured.err


def test_cmd_absenzen_eintragen_execute_writes(monkeypatch, capsys):
    fake = _AbsFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_absenzen_eintragen(_abs_args(testlauf=False))
    assert rc == 0
    assert fake.set_calls == [(608000, 21000, True)]
    captured = capsys.readouterr()
    assert "317000" in captured.err  # Absenz-ID aus der Response


def test_cmd_absenzen_entfernen_by_student_lookup(monkeypatch, capsys):
    fake = _AbsFakeClient()
    fake.vm["absenceRows"] = [
        {"absence": {"id": 317000, "startTime": 1145, "endTime": 1325,
                     "startDate": 20260925, "endDate": 20260925,
                     "person": {"id": 21000, "displayName": "Muster Erika"}}}]
    deletes = []
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)

    def _delete(ab, pid):
        deletes.append((ab["id"], pid))
        return {"_data": {"removedAbsenceIds": [ab["id"]]},
                "success": True}
    fake.delete_absence = _delete
    args = _abs_args(termin=608000, schueler_id=None,
                     schueler_name="Erika Muster", testlauf=False)
    rc = cli_lesson.cmd_absenzen_entfernen(args)
    assert rc == 0
    assert deletes == [(317000, 608000)]
    captured = capsys.readouterr()
    assert "317000" in captured.err


def test_cmd_absenzen_entfernen_no_absence_found(monkeypatch, capsys):
    from webuntis_cli.errors import NotFoundError
    fake = _AbsFakeClient()  # vm ohne absenceRows
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    args = _abs_args(termin=608000, schueler_name="Erika Muster",
                     testlauf=False)
    with pytest.raises(NotFoundError, match="Keine Abwesenheit"):
        cli_lesson.cmd_absenzen_entfernen(args)


def test_cmd_absenzen_zeigen_termin_lists_rows(monkeypatch, capsys):
    fake = _AbsFakeClient()
    fake.vm["period"] = {"id": 608000, "lesson": {
        "id": 218000, "text": "Graphentheorie", "subjects": "POS1"}}
    fake.vm["absenceRows"] = [
        {"absence": {"id": 317000, "startTime": 1145, "endTime": 1325,
                     "person": {"id": 21000, "displayName": "Muster Erika"}}}]
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    args = argparse.Namespace(termin=608000, nur_fehlende=False,
                              alle=False, json=True, school_year_id=None,
                              lsid=None, klasse_fach=None)
    rc = cli_lesson.cmd_absenzen_zeigen(args)
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["periodId"] == 608000
    assert payload["lessonId"] == 218000
    assert payload["lessonText"] == "Graphentheorie"
    assert payload["absenceRows"][0]["absenceId"] == 317000
    assert payload["absenceRows"][0]["studentName"] == "Muster Erika"


def test_cmd_absenzen_zeigen_termin_text_includes_desc(monkeypatch, capsys):
    fake = _AbsFakeClient()
    fake.vm["period"] = {"id": 608000, "lesson": {
        "id": 218000, "text": "Theorie", "subjects": "POS1"}}
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    args = argparse.Namespace(termin=608000, nur_fehlende=False,
                              alle=False, json=False, school_year_id=None,
                              lsid=None, klasse_fach=None)
    rc = cli_lesson.cmd_absenzen_zeigen(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "lsid 218000, Theorie)" in out.splitlines()[0]


# ---------- zeigen --absenz-id (Dialog-Existenzcheck) ----------

def _absdlg_html(absence_id=317000, person_id=21000, name="Muster Erika"):
    vm = {"students": [{"id": person_id, "type": 5, "displayName": name}],
          "absence": {"id": absence_id, "startTime": 1145, "endTime": 1325,
                      "startDate": 20260925, "endDate": 20260925,
                      "text": "",
                      "person": {"id": person_id, "type": 5,
                                 "displayName": name, "fullName": name},
                      "excuseStatus": {"isOpen": True, "isExcused": False}}}
    import html as _h
    escaped = json.dumps(vm).replace('"', "&quot;")
    return (f'<form data-dojo-props="viewModel: {escaped}" action="/x">'
            f'</form>')


def test_get_absence_dialog_gets_without_times():
    c = _client([_Resp(_absdlg_html())])
    c._session = _SessionStub()
    vm = Client.get_absence_dialog(c, 317000, 608000)
    get = c.http.calls[0]
    assert get["params"]["selId"] == 317000
    assert get["params"]["abTimetableId"] == 608000
    assert "abStartTime" not in get["params"]
    assert vm["absence"]["id"] == 317000


def test_get_absence_dialog_wrong_id_raises(monkeypatch):
    from webuntis_cli.errors import NotFoundError
    c = _client([_Resp(_absdlg_html(absence_id=999999))])
    c._session = _SessionStub()
    with pytest.raises(NotFoundError, match="317000"):
        Client.get_absence_dialog(c, 317000, 608000)


def test_cmd_absenzen_zeigen_absenz_id_json(monkeypatch, capsys):
    fake = _AbsFakeClient()
    fake.vm["students"] = []  # Person NICHT in der Teilnehmerliste
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    fake.get_absence_dialog = lambda aid, pid: json.loads(json.dumps(
        {"students": [{"id": 21000}],
         "absence": {"id": 317000, "startTime": 1145, "endTime": 1325,
                     "startDate": 20260925, "endDate": 20260925,
                     "text": "", "excuseStatus": {"isOpen": True},
                     "person": {"id": 21000,
                                "displayName": "Muster Erika"}}}))
    args = argparse.Namespace(termin=608000, absenz_id=317000,
                              nur_fehlende=False, alle=False, json=True,
                              school_year_id=None, lsid=None,
                              klasse_fach=None)
    rc = cli_lesson.cmd_absenzen_zeigen(args)
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["absenceId"] == 317000
    assert payload["studentName"] == "Muster Erika"
    assert payload["date"] == "2026-09-25"
    assert payload["inTeilnehmerliste"] is False
    assert "NICHT in der Teilnehmerliste" in captured.err


def test_cmd_absenzen_zeigen_absenz_id_braucht_termin(monkeypatch):
    from webuntis_cli.errors import UsageError
    fake = _AbsFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    args = argparse.Namespace(termin=None, absenz_id=317000,
                              nur_fehlende=False, alle=False, json=False,
                              school_year_id=None, lsid=None,
                              klasse_fach=None)
    with pytest.raises(UsageError):
        cli_lesson.cmd_absenzen_zeigen(args)


# ---------- Bulk-Modus (--von/--bis) ----------

def _bulk_matrix():
    return {"result": {"lessonPeriods": [
        {"id": 608000, "date": 20260908, "startTime": 850, "endTime": 940},
        {"id": 608001, "date": 20260908, "startTime": 955, "endTime": 1045},
        {"id": 608010, "date": 20260915, "startTime": 1145, "endTime": 1235},
        {"id": 608020, "date": 20261201, "startTime": 850, "endTime": 940},
        {"id": 608030, "date": 20260825, "startTime": 850, "endTime": 940},
    ]}}


class _BulkFakeClient(_AbsFakeClient):
    def __init__(self):
        super().__init__()
        self.matrix = _bulk_matrix()

    def get_schoolyears(self):
        return [{"id": 24,
                 "dateRange": {"start": "2026-09-01", "end": "2027-07-15"}}]

    def get_student_lesson_period_matrix(self, ls_id, school_year_id=None):
        return self.matrix


def _bulk_args(**kw):
    base = dict(lsid=218000, klasse_fach=None, termin=None,
                schueler_id=21000, schueler_name=None, absenz_id=None,
                kein_block=False, testlauf=True, school_year_id=None,
                start="2026-09-01", end="2026-09-30", pause=0.0,
                datum=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_bulk_eintragen_testlauf_selects_block_starts(monkeypatch, capsys):
    monkeypatch.setattr(cli_lesson, "_make_client",
                        lambda args: _BulkFakeClient())
    rc = cli_lesson.cmd_absenzen_eintragen(_bulk_args(end="2026-12-31"))
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    # erstes Datum: nur Block-Start 608000 (nicht 608001); Zukunft
    # (2026-12-01) und Vor-Schuljahr (2026-08-25) uebersprungen
    assert payload == [{"periodId": 608000, "date": "2026-09-08",
                        "block": True},
                       {"periodId": 608010, "date": "2026-09-15",
                        "block": True}]
    assert "TESTLAUF" in captured.err
    assert "1 Termin(e) nach heute" in captured.err


def test_bulk_eintragen_execute_writes_per_date(monkeypatch, capsys):
    fake = _BulkFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    rc = cli_lesson.cmd_absenzen_eintragen(_bulk_args(testlauf=False))
    assert rc == 0
    assert fake.set_calls == [(608000, 21000, True), (608010, 21000, True)]
    captured = capsys.readouterr()
    assert "2/2 Termin(e)" in captured.err


def test_bulk_eintragen_kein_termin_im_zeitraum(monkeypatch):
    from webuntis_cli.errors import NotFoundError
    fake = _BulkFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    with pytest.raises(NotFoundError, match="keine gehaltenen Termine"):
        cli_lesson.cmd_absenzen_eintragen(
            _bulk_args(start="2027-02-01", end="2027-02-28"))


def test_bulk_eintragen_kein_block_und_termin_kombis(monkeypatch):
    from webuntis_cli.errors import UsageError
    fake = _BulkFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    with pytest.raises(UsageError, match="nicht kombinierbar"):
        cli_lesson.cmd_absenzen_eintragen(_bulk_args(termin=608000))
    with pytest.raises(UsageError, match="ganzen Block"):
        cli_lesson.cmd_absenzen_eintragen(_bulk_args(kein_block=True))


def test_bulk_eintragen_geerbtes_datum_ist_ok(monkeypatch):
    """Subparser erben das lesson-Parser-Default datum='heute' (heute als
    ISO-String) — der Bulk-Modus darf darauf nicht mit UsageError
    reagieren, nur --termin-id ist ein echter Konflikt."""
    fake = _BulkFakeClient()
    monkeypatch.setattr(cli_lesson, "_make_client", lambda args: fake)
    from datetime import date as _date
    rc = cli_lesson.cmd_absenzen_eintragen(
        _bulk_args(datum=_date.today().isoformat()))
    assert rc == 0
