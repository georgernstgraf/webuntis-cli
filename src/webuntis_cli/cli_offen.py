"""CLI offen-Befehle: Arbeitsvorrat offener Perioden (Top-Level).

Eine offene Periode schuldet noch Lehrstoff (`topicNeeded`) oder
Absenzenprüfung (`absCheckNeeded`). Filter: `TOPIC_OR_ABSENCE_OPEN`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date

from webuntis_cli.cli_common import (
    _fetch_open_periods,
    _make_client,
    _no_open_periods,
    _open_period_entries,
    _period_summary,
    _resolve_von_bis,
    _sleep_between,
    _submit_topic_entries,
)


def cmd_offen_liste(args: argparse.Namespace) -> int:
    """Offene Perioden im Zeitraum auflisten (Default: Schuljahr bis heute)."""
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    start, end = _resolve_von_bis(args, c, sy)
    entries = _open_period_entries(c, sy, start, end)
    if not entries:
        return _no_open_periods(args)
    if args.json:
        clean = [{k: v for k, v in e.items() if not k.startswith("_")}
                 for e in entries]
        print(json.dumps(clean, indent=2, ensure_ascii=False))
        return 0
    for e in entries:
        print(
            f"{e['periodId']:>10}  {e['date']}T{e['time']}  "
            f"{e['class'] or '':8} {e['subject'] or '':8} "
            f"topicId={e['topicId']}"
        )
    return 0


def cmd_offen_status(args: argparse.Namespace) -> int:
    """Überblick offener Perioden, gruppiert nach Fach, Klasse, Monat."""
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        return _no_open_periods(args)
    summaries = [_period_summary(p) for p in periods]
    if args.json:
        print(json.dumps(summaries, indent=2, ensure_ascii=False))
        return 0
    by_subject = Counter(s["subject"] for s in summaries)
    print(f"offene Perioden gesamt: {len(summaries)}")
    print("\n--- nach Fach ---")
    for subj, cnt in by_subject.most_common():
        print(f"  {subj or '':8} {cnt}")
    combos: dict[tuple, int] = defaultdict(int)
    for s in summaries:
        combos[(s["class"], s["subject"])] += 1
    print("\n--- nach Klasse + Fach ---")
    for (cls, subj), cnt in sorted(combos.items()):
        print(f"  {cls or '':8} {subj or '':8} {cnt:3}")
    return 0


def cmd_offen_verifizieren(args: argparse.Namespace) -> int:
    """Prüfen, welche offenen Perioden wirklich ohne Lehrstoff-Text sind
    (vs. nur fehlender Absenzenprüfung)."""
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        return _no_open_periods(args)

    wirklich_leer: list[dict] = []
    mit_text: list[dict] = []
    for p in periods:
        per = p.get("period", {})
        pid = per.get("id")
        summary = _period_summary(p)
        try:
            topic = c.get_lesson_topic(pid, school_year_id=sy)
            pts = topic.get("periodTopics", [])
            if pts and pts[0].get("topic") and pts[0]["topic"].get("text"):
                summary["topicText"] = pts[0]["topic"]["text"][:80]
                mit_text.append(summary)
            else:
                summary["topicText"] = None
                wirklich_leer.append(summary)
        except Exception as e:
            summary["error"] = str(e)
            wirklich_leer.append(summary)

    if args.json:
        print(json.dumps({
            "trulyEmpty": wirklich_leer,
            "hasText": mit_text,
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"offene Perioden: {len(periods)}")
    print(f"  wirklich leer (kein Lehrstoff-Text): {len(wirklich_leer)}")
    print(f"  mit Text (nur Absenzenprüfung fehlt): {len(mit_text)}")
    if wirklich_leer:
        print("\n--- wirklich leer ---")
        for s in wirklich_leer:
            print(f"  {s['periodId']:>10} {s['class'] or '':6} "
                  f"{s['subject'] or '':6} {s['date']}")
    if mit_text:
        print(f"\n--- mit Text ({len(mit_text)}) — erste 5 ---")
        for s in mit_text[:5]:
            print(f"  {s['periodId']:>10} {s['class'] or '':6} "
                  f"{s['subject'] or '':6} {s['date']} "
                  f"text={s.get('topicText', '')!r}")
    return 0


def cmd_offen_vorschlag(args: argparse.Namespace) -> int:
    """Offene Perioden + Git-Commits/Diffs je Tages-Block laden,
    Vorschlag-JSON für den Skill/Agenten ausgeben (immer Testlauf —
    schreibt nichts).

    Ausgabe: JSON mit `blocks` (je Tages-Block: Perioden, Commits, Diffs,
    proposedText) und `skipped` (weder Repo-Mapping noch Supplierung).
    Texte prüfen, bestätigen, dann `offen eintragen --datei <json>`
    ausführen.

    Gruppierung ist TAGESGENAU: (lsId, Datum) — eine Jahrgangs-Lesson
    (gleiche lsId über Monate) liefert je Tag einen eigenen Block mit
    den Commits genau dieses Datums. Blockpartner am selben Tag
    (Doppelperiode) werden vom Server mit-aktualisiert.

    Textquellen in Priorität:
    1. Festtext (FIXED_TEXT_SUBJECTS: SS, BESP)
    2. Git-Verlauf des gemappten Fach-Repos für genau diesen Tag
    3. Supplierungs-Erkennung (eigener Lehrer als ADDED im Block,
       removed-Original oder substitutionText) -> SUPPLIER_TEXT
       (auch supplierene Perioden verpflichten zur Lehrstoff-Eintragung)
    4. sonst: dummy (kein Unterricht im Repo gefunden) bzw. skipped
    """
    from webuntis_cli.client import (
        SUPPLIER_TEXT,
        FIXED_TEXT_SUBJECTS,
        repos_for_subject,
    )
    from webuntis_cli.gitlog import (
        get_commit_diff_by_name,
        get_commits_for_class,
    )

    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        return _no_open_periods(args)

    summaries = [_period_summary(p) for p in periods]
    # Tages-Blöcke: (lsId, Datum) — Fallback (Klasse, Fach, Datum) nur
    # ohne lsId. NICHT über die Jahrgangs-lsId gruppieren: der Text ist
    # tagesbezogen, ein PUT je Block-Partner am selben Tag reicht.
    blocks: dict[tuple, list[dict]] = defaultdict(list)
    for s in summaries:
        lsid = s.get("lsId")
        key = ("lsid", lsid, s["date"]) if lsid is not None else \
            ("fallback", s["class"], s["subject"], s["date"])
        blocks[key].append(s)

    blocks_out: list[dict] = []
    skipped: list[dict] = []
    for key, block_periods in blocks.items():
        p0 = block_periods[0]
        cls = p0["class"]
        subj = p0["subject"]
        d = p0["date"]
        entry = {
            "periodId": p0["periodId"],
            "topicId": p0["topicId"],
            "class": cls,
            "classId": p0["classId"],
            "subject": subj,
            "subjectLong": p0["subjectLong"],
            "date": d,
            "time": p0["time"],
            "lsId": p0["lsId"],
            "blockPeriods": [bp["periodId"] for bp in block_periods],
        }
        starts = [bp["startIso"] for bp in block_periods if bp.get("startIso")]
        ends = [bp["endIso"] for bp in block_periods if bp.get("endIso")]
        start_iso = min(starts) if starts else f"{d}T{p0['time']}:00"
        if ends:
            end_iso = max(ends)
        else:
            end_iso = start_iso
            entry["warning"] = "kein dtRange.end in open-periods-Payload"
        entry["start"] = start_iso
        entry["end"] = end_iso

        if subj in FIXED_TEXT_SUBJECTS:
            entry["source"] = "fixed"
            entry["proposedText"] = FIXED_TEXT_SUBJECTS[subj]
            entry["commits"] = []
            blocks_out.append(entry)
            continue

        repos = repos_for_subject(subj)
        commits: list = []
        if repos:
            commits = get_commits_for_class(
                cls, date.fromisoformat(d), repo_filter=repos,
            )

        if commits:
            commit_data: list[dict] = []
            for ci in commits:
                commit_data.append({
                    "repo": ci.repo,
                    "hash": ci.hash,
                    "date": ci.date,
                    "message": ci.message,
                    "files": ci.files[:5],
                    "diff": get_commit_diff_by_name(ci.repo, ci.hash),
                })
            entry["commits"] = commit_data
            entry["source"] = "git"
            msgs = [cd["message"] for cd in commit_data if cd["message"]]
            entry["proposedText"] = (
                "; ".join(dict.fromkeys(msgs))[:240] if msgs else "(no messages)"
            )
            blocks_out.append(entry)
            continue

        # kein Git-Befund (oder Fach unmapped): Supplierung? Auch
        # supplierene Perioden schulden Lehrstoff — Festtext genügt.
        cls_id = p0.get("classId")
        supplier = False
        if cls_id is not None:
            try:
                supplier = c.is_supplier_period(
                    cls_id, p0["periodId"], d, school_year_id=sy)
            except Exception as e:  # Netz/Rechte: konservativ weiter
                entry.setdefault("warning", f"Supplier-Check fehlgeschlagen: {e}")
        if supplier:
            entry["commits"] = []
            entry["source"] = "supplier"
            entry["proposedText"] = SUPPLIER_TEXT
            blocks_out.append(entry)
            continue

        if not repos:
            entry["source"] = "skipped"
            entry["proposedText"] = None
            entry["commits"] = []
            warn = entry.pop("warning", None)
            msg = (
                f"Fach '{subj}' nicht in SUBJECT_REPO_MAP und keine "
                "Supplierung — in src/webuntis_cli/client.py ergänzen "
                "oder Text manuell formulieren"
            )
            entry["warning"] = msg if warn is None else f"{warn}; {msg}"
            skipped.append(entry)
            continue

        entry["commits"] = []
        entry["source"] = "dummy"
        entry["proposedText"] = (
            f"(kein Unterricht gefunden für {cls} am {d})"
        )
        blocks_out.append(entry)

    blocks_out.sort(key=lambda e: e.get("start") or "")
    skipped.sort(key=lambda e: e.get("start") or "")
    output = {"blocks": blocks_out, "skipped": skipped}
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print(
        f"\n{len(blocks_out)} Tages-Blöcke ({len(skipped)} übersprungen) — "
        f"Texte prüfen, dann `offen eintragen --datei <json>` ausführen",
        file=sys.stderr,
    )
    return 0


def cmd_offen_eintragen(args: argparse.Namespace) -> int:
    """Bestätigte Lehrstoffe aus einer JSON-Datei eintragen (Write).

    Format: [{periodId, topicId, text, classId, start, end, date}, ...].
    Je Eintrag ein PUT (+Lesson-Details-URL bei classId/start/end/date).
    Zwischen PUTs --pause Sekunden (IP-Rate-Limit).
    --testlauf (Standard) zeigt nur; mit --ausfuehren wird geschrieben.
    """
    from pathlib import Path
    items = json.loads(Path(args.datei).read_text(encoding="utf-8"))
    if args.testlauf:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        print(f"\nTESTLAUF: {len(items)} Eintrag/Einträge würden geschrieben "
              "(kein Write); mit --ausfuehren ausführen.", file=sys.stderr)
        return 0
    c = _make_client(args)
    sy = c.resolve_schoolyear_id(override=args.school_year_id)
    results = _submit_topic_entries(
        c, sy, items, delay=args.pause, url_fields=True)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} aktualisiert", file=sys.stderr)
    return 0 if ok == len(results) else 1


def cmd_offen_festtexte(args: argparse.Namespace) -> int:
    """Offene Perioden mit Festtext-Fächern (SS, BESP) füllen.

    --testlauf (Standard) zeigt nur, --ausfuehren trägt wirklich ein.
    """
    from webuntis_cli.client import FIXED_TEXT_SUBJECTS
    c, sy, periods = _fetch_open_periods(args)
    if not periods:
        return _no_open_periods(args)

    fixed_periods = []
    for p in periods:
        s = _period_summary(p)
        if s["subject"] in FIXED_TEXT_SUBJECTS:
            entry = dict(s)
            entry["text"] = FIXED_TEXT_SUBJECTS[s["subject"]]
            fixed_periods.append(entry)

    if not fixed_periods:
        print("(keine Festtext-Fächer in offenen Perioden)" if not args.json
              else "[]")
        return 0

    if args.testlauf:
        if args.json:
            print(json.dumps(fixed_periods, indent=2, ensure_ascii=False))
        else:
            print(f"{len(fixed_periods)} Festtext-Perioden (TESTLAUF):")
            for e in fixed_periods:
                print(f"  {e['periodId']:>10} {e['class'] or '':6} "
                      f"{e['subject'] or '':6} {e['date']} "
                      f"text={e['text']!r}")
            print("Eintragen mit --ausfuehren.", file=sys.stderr)
        return 0

    results = _submit_topic_entries(c, sy, fixed_periods, delay=args.pause)
    ok = sum(1 for r in results if r.get("ok"))
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        by_period = {e["periodId"]: e for e in fixed_periods}
        for r in results:
            e = by_period.get(r.get("periodId"), {})
            status = "ok" if r.get("ok") else f"FEHLER: {r.get('error', '?')}"
            print(f"  {r.get('periodId'):>10} {e.get('class') or '':6} "
                  f"{e.get('subject') or '':6} {e.get('date') or ''} "
                  f"{status}")
    print(f"\n{ok}/{len(results)} Festtext-Perioden eingetragen",
          file=sys.stderr)
    return 0 if ok == len(results) else 1


def cmd_offen_pruefen(args: argparse.Namespace) -> int:
    """Absenzenprüfung für offene Perioden durchführen (Write).

    Mit --datei: Perioden aus JSON-Datei ([{periodId}, ...]).
    Ohne: alle prüfbedürftigen Perioden im Zeitraum (Default: Schuljahr
    bis heute). Zwischen den Calls --pause Sekunden (IP-Rate-Limit).
    --testlauf (Standard) zeigt nur; mit --ausfuehren wird geprüft.
    """
    from pathlib import Path
    c = None
    if args.datei:
        items = json.loads(Path(args.datei).read_text(encoding="utf-8"))
        pids = [it["periodId"] for it in items]
    else:
        c, sy, periods = _fetch_open_periods(args)
        need = [p for p in periods if p.get("absCheckNeeded")]
        print(f"offene Perioden: {len(periods)}, "
              f"prüfbedürftig: {len(need)}", file=sys.stderr)
        pids = [p.get("period", {}).get("id") for p in need]
    if args.testlauf:
        print(json.dumps([{"periodId": p} for p in pids], indent=2,
                         ensure_ascii=False))
        print(f"\nTESTLAUF: {len(pids)} Periode(n) würden geprüft (kein "
              "Write); mit --ausfuehren ausführen.", file=sys.stderr)
        return 0
    if c is None:
        c = _make_client(args)
    results: list[dict] = []
    for i, pid in enumerate(pids):
        _sleep_between(i, args.pause)
        entry: dict = {"periodId": pid}
        try:
            res = c.check_absences(pid)
            entry["ok"] = res.get("success", False)
        except Exception as e:
            entry["ok"] = False
            entry["error"] = str(e)
        results.append(entry)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} Absenzen geprüft", file=sys.stderr)
    return 0 if ok == len(results) else 1
