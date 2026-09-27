"""CLI klasse-Befehle: alles zu einer Klasse (z.B. 3AHWII).

Der Default-Befehl liefert Roster (Schülerliste) und Fächer
(eigene Lessons in dieser Klasse) sowie den Klassenvorstand.
"""

from __future__ import annotations

import argparse
import json
import sys

from typing import TYPE_CHECKING

from webuntis_cli.cli_common import (
    _find_klasse,
    _make_client,
    _open_period_entries,
)
from webuntis_cli.cli_lesson import _teacher_names_for_class
from webuntis_cli.errors import NotFoundError, ServerError

if TYPE_CHECKING:
    from webuntis_cli.client import Client


def _kv_info(c: Client, sy: int, needle: int | str) -> dict:
    """KV-Info einer Klasse (ID oder exakter Name) als Dict.

    Wirft RuntimeError, wenn die Klasse nicht gefunden wird.
    """
    from webuntis_cli.cli_common import _find_klasse
    hit = _find_klasse(c, sy, needle)
    teacher_ids = [v for key in ("teacher1", "teacher2", "teacher3")
                   if (v := hit.get(key))]
    return {
        "classId": hit.get("id"),
        "name": hit.get("name"),
        "longName": hit.get("longName"),
        "teachers": _teacher_names_for_class(c, hit["id"], teacher_ids, sy),
    }


def cmd_klasse_kv(args: argparse.Namespace) -> int:
    """Klassenvorstand einer Klasse anzeigen (Name oder ID)."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    info = _kv_info(c, sy, args.klassenname)
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    print(f"{info['name']} ({info['longName']}):")
    for tid, name in info["teachers"].items():
        print(f"  KV: {name} (lehrer-id {tid})")
    return 0


def _faecher_groups(c: Client, sy: int, klassenname: str,
                    start: str | None, end: str | None,
                    fach: str | None = None) -> tuple[list[dict], str, str]:
    """Lessons einer Klasse als Gruppen — aus dem Klassen-Stundenplan.

    Quelle: timetable/entries (CLASS) — ALLE Lessons der Klasse (auch
    erledigte), anders als open-periods. Default-Zeitraum: die Woche um
    heute (eine Woche genügt — Lessons laufen übers Semester); mit
    --von/--bis werden die Wochen des Bereichs iteriert (max. 8, dann
    Warnung). Je Gruppe: `eigen` (eigene Lesson, via Mein Stundenplan),
    `offen` (offene Perioden im Zeitraum, nur eigene Lessons — die
    Zählung ist teacher-scoped). KEINE lsId (nur im Einzelfall via
    `lesson K/F`-Resolver per calendar-entry/detail).
    """
    from datetime import date as _date, timedelta as _td
    from webuntis_cli.cli_lesson import _week_bounds
    from webuntis_cli.client import (
        group_timetable_lessons,
        parse_timetable_entries,
    )
    k = _find_klasse(c, sy, klassenname)
    class_id = int(k["id"])
    if start and end:
        first = _date.fromisoformat(start)
        last = _date.fromisoformat(end)
        weeks = []
        cur = first - _td(days=first.weekday())
        while cur <= last and len(weeks) < 8:
            weeks.append(_week_bounds(cur))
            cur += _td(days=7)
        if cur <= last:
            print("Hinweis: Zeitraum über 8 Wochen gedeckelt — "
                  "Lessons laufen übers Semester, weniger Wochen genügen.",
                  file=sys.stderr)
    else:
        weeks = [_week_bounds(_date.today())]
    entries: list[dict] = []
    for ws, we in weeks:
        entries += parse_timetable_entries(
            c.get_timetable_entries("CLASS", class_id, ws, we))
    lessons = group_timetable_lessons(entries)
    if fach:
        fl = fach.lower()
        lessons = [g for g in lessons
                   if (g.get("subject") or "").lower().startswith(fl)]
    kl_l = (k.get("name") or klassenname).lower()
    # eigene Lessons: mein Termin-Slot (Fach, Datum, Start) liegt per
    # Definition in meiner Gruppe — Lehrer-Positionen im eigenen Plan
    # sind anonymisiert (own short fehlt), Slot-Matching ist exakt.
    my_slots: set[tuple[str, str, str]] | None = None
    try:
        my = parse_timetable_entries(c.get_timetable_entries(
            "TEACHER", c.teacher_id, weeks[0][0], weeks[0][1],
            timetable_type="MY_TIMETABLE"))
        my_slots = {
            ((e.get("subject") or "").lower(), e.get("date"),
             (e.get("start") or "")[:16])
            for e in my
            if (e.get("class") or "").lower() == kl_l and e.get("subject")}
    except Exception:
        my_slots = None
    offen_by_subject: dict[str, int] = {}
    try:
        range_start = weeks[0][0]
        range_end = weeks[-1][1]
        for e in _open_period_entries(c, sy, range_start, range_end):
            if (e.get("class") or "").lower() != kl_l:
                continue
            key = (e.get("subject") or "").lower()
            offen_by_subject[key] = offen_by_subject.get(key, 0) + 1
    except Exception as e:
        print(f"Hinweis: Offen-Status nicht ladbar ({e})", file=sys.stderr)
    groups: list[dict] = []
    for g in lessons:
        subj_l = (g.get("subject") or "").lower()
        if my_slots is None:
            eigen = None
        else:
            eigen = any(
                (subj_l, e.get("date"), (e.get("start") or "")[:16])
                in my_slots for e in g["entries"])
        weekday_times: list[str] = []
        for e in g["entries"]:
            wd = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][
                _date.fromisoformat(e["date"]).weekday()]
            t = (e.get("start") or "")[11:16]
            label = f"{wd} {t}"
            if label not in weekday_times:
                weekday_times.append(label)
        groups.append({
            "subject": g["subject"], "subjectLong": g.get("subjectLong"),
            "class": g.get("class"), "classLong": g.get("classLong"),
            "primaryTeacher": g.get("primaryTeacher"),
            "parallel": bool(g.get("parallel")),
            "teachers": g.get("teachers"),
            "teacherLongs": g.get("teacherLongs"),
            "rooms": g.get("rooms"),
            "dates": g.get("dates"),
            "weekdayTimes": weekday_times,
            "periods": len(g["entries"]),
            "eigen": eigen,
            "offen": offen_by_subject.get(subj_l, 0),
        })
    groups.sort(key=lambda g: (g["subject"] or "",
                               g["primaryTeacher"] or ""))
    range_start = weeks[0][0]
    range_end = weeks[-1][1]
    return groups, range_start, range_end


def cmd_klasse_faecher(args: argparse.Namespace) -> int:
    """Lessons (Fächer) einer Klasse auflisten — aus dem Stundenplan."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    groups, start, end = _faecher_groups(
        c, sy, args.klassenname, args.start, args.end, args.fach)
    if not groups:
        print(f"(keine Lessons für {args.klassenname}"
              + (f"/{args.fach}" if args.fach else "")
              + f" in {start}..{end})")
        return 0
    full_by_short: dict[str, str] = {}
    if args.volle_namen:
        shorts = sorted({t for g in groups for t in g["teachers"]})
        for short in shorts:
            hits = c.search_timetable(short, school_year_id=sy)
            match = next((h["resource"] for h in hits
                          if h.get("type") == "TEACHER"
                          and h["resource"].get("shortName") == short), None)
            if match:
                full_by_short[short] = (match.get("displayName")
                                        or match.get("longName") or short)
    if args.json:
        print(json.dumps({
            "class": args.klassenname,
            "range": {"start": start, "end": end},
            "lessons": groups,
        }, indent=2, ensure_ascii=False))
        return 0
    for g in groups:
        teachers = [full_by_short.get(t, t) for t in g["teachers"]] \
            if args.volle_namen else g["teachers"]
        eigen = " (eigen)" if g["eigen"] else ""
        parallel = (f" [{g['primaryTeacher']}]"
                    if g["parallel"] and g["primaryTeacher"] else "")
        print(f"{g['subject']:8}{parallel} — {g['subjectLong']}{eigen}")
        zeiten = ", ".join(g["weekdayTimes"])
        print(f"  {g['class']}  Termine/Woche: {g['periods']}  {zeiten}")
        if teachers:
            print(f"  Lehrer: {' + '.join(teachers)}")
        if g["rooms"]:
            print(f"  Räume:  {' + '.join(g['rooms'])}")
        if g["offen"]:
            print(f"  offen: {g['offen']} Perioden im Zeitraum")
    print("Hinweis: alle Lessons der Klasse aus dem Stundenplan; "
          "'eigen' = eigene Lessons, 'offen' nur für eigene zählbar.",
          file=sys.stderr)
    return 0


def _klassen_roster(c: Client, klassenname: str) -> list[tuple[str, str]]:
    """Roster einer Klasse aus students/overview (volle Namen).

    Liefert sortierte (Name, Klasse)-Zeilen; wirft RuntimeError ohne Treffer.
    """
    try:
        overview = c.get_students_overview()
    except Exception as e:
        raise ServerError(f"students/overview fehlgeschlagen ({e})") from e
    kl_l = klassenname.lower()
    rows = []
    for s in overview.get("students", []):
        ci = s.get("classInfo") or {}
        if (ci.get("name") or "").lower() != kl_l:
            continue
        name = f"{s.get('lastName', '')} {s.get('firstName', '')}".strip()
        rows.append(((s.get("lastName", "").lower(),
                      s.get("firstName", "").lower()),
                     name, ci.get("name", "")))
    if not rows:
        raise NotFoundError(
            f"keine Schüler für Klasse '{klassenname}' im aktuellen Roster")
    rows.sort(key=lambda r: r[0])
    return [(name, klass) for _, name, klass in rows]


def cmd_klasse_roster(args: argparse.Namespace) -> int:
    """Schülerliste (Roster) einer Klasse, Excel-einfügbare TSV-Ausgabe."""
    from webuntis_cli.cli_lesson import _tsv_cell
    c = _make_client(args)
    rows = _klassen_roster(c, args.klassenname)
    if args.json:
        print(json.dumps({
            "class": args.klassenname,
            "students": [{"name": n, "klasse": k} for n, k in rows],
        }, indent=2, ensure_ascii=False))
        return 0
    if not args.ohne_kopf:
        print("Name\tKlasse")
    for name, klass in rows:
        print(f"{_tsv_cell(name)}\t{_tsv_cell(klass)}")
    return 0


def cmd_klasse(args: argparse.Namespace) -> int:
    """Klassen-Übersicht (Default): Kopf mit klassen-id und KV.

    Nur lesend. Standardmäßig nur der Kopf (Name, klassen-id, KV) —
    Fächer und Roster nur mit --details (spart die Plan-/Overview-Calls).
    --json liefert den Kopf immer; `range`/`lessons`/`students` nur mit
    --details.
    """
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    info = _kv_info(c, sy, args.klassenname)
    details = bool(getattr(args, "details", False)
                   or getattr(args, "fach", None))
    groups: list[dict] = []
    rows: list[tuple[str, str]] = []
    start = end = None
    if details:
        groups, start, end = _faecher_groups(c, sy, args.klassenname,
                                             args.start, args.end, args.fach)
        try:
            rows = _klassen_roster(c, args.klassenname)
        except RuntimeError as e:
            print(f"Hinweis: {e}", file=sys.stderr)
            rows = []
    if args.json:
        payload = {
            "class": info["name"],
            "classId": info["classId"],
            "longName": info["longName"],
            "kv": info["teachers"],
        }
        if details:
            payload["range"] = {"start": start, "end": end}
            payload["lessons"] = groups
            payload["students"] = [{"name": n, "klasse": k} for n, k in rows]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(f"{info['name']} ({info['longName']})")
    print(f"  klassen-id: {info['classId']}")
    for tid, name in info["teachers"].items():
        print(f"  KV: {name}")
    if not details:
        print("(Fächer und Roster mit --details)", file=sys.stderr)
        return 0
    print(f"\nFächer (alle Lessons der Klasse, Stundenplan {start}..{end}):")
    if not groups:
        print("  (keine)")
    for g in groups:
        lehrer = f" ({' + '.join(g['teachers'])})" if g["teachers"] else ""
        eigen = " (eigen)" if g["eigen"] else ""
        parallel = (f" [{g['primaryTeacher']}]"
                    if g["parallel"] and g["primaryTeacher"] else "")
        print(f"  {g['subject']:8}{parallel} — {g['subjectLong']}{lehrer}"
              f"{eigen}")
    print(f"\nRoster ({len(rows)} Schüler):")
    for name, klass in rows:
        print(f"  {name}")
    return 0
