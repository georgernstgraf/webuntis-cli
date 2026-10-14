Open tasks:

- Live-Verifikation der neuen Fehlerklassen (Netz 5 / Auth 4 / Server 6)
  an echten Endpunkten — bisher nur Unit-Tests mit Fake-Clients
  (siehe #23).
- Recording-Session (vom Nutzer gewünscht): die Form von
  `lessonKlassen` in der Matrix belegen (read-only
  `wu lesson --lsid X info --json` bzw. CDP-Mitschnitt), damit die
  class-id-Ableitung bei `aufnehmen/anpassen` nicht nur defensiv
  (dict/int) + Attendee-Fallback ist. Doku in `docs/WEBUNTIS_API.md`.
- Rate-Limit-Reverse-Engineering (vom Nutzer gewünscht, noch nicht
  begonnen): Call-/Fehler-Logging einbauen, um die TCP-Reset-Schwelle
  und das Erholverhalten des Servers aufzuzeichnen (s. PITFALLS.md).
- Code-Review ab dem Fixpunkt dieses Commits (`git log`).

Offen für später:
- #22 `raum suchen` echte Freie-Raum-Suche (ROOM-Belegung je Slot,
  capacity-Filter; `availability`-Semantik ungeklärt).

Erledigt (Session 2026-10-14, Commit s. `git log`):
- Später-kommenden Schüler [Details: LOCAL.md] nachträglich in allen
  gehaltenen Stunden seit Schuljahresstart abwesend gesetzt:
  3AHWII/SWP1x (lsid 218231, 6 Terminblöcke) und 3AHWII/INFIx
  (lsid 214624, 5 Terminblöcke) — je Datum ein Block-Write,
  Absenzenprüfung beider Lessons 01.09.–14.10. ausgeführt. Der
  classreg-Dialog historischer Termine zeigt die Einträge nicht
  (Schüler fehlt in der Teilnehmerliste) — Verifikation via
  absencedlg.do (s. PITFALLS.md).
- INFIx-Lehrstoff 13.10. (Perioden 6239637/6239640) eingetragen
  (Text „Innolab", Block schreibt beide Perioden); `offen`-Status
  01.09.–14.10. danach: 3AHWII leer.
- Neue Features: `absenzen eintragen --von/--bis` (Bulk: ein
  Block-Write je gehaltenem Datum, nur ≤ heute, Testlauf-Standard,
  --pause) und `absenzen zeigen --absenz-id --termin-id`
  (Dialog-Existenzcheck, funktioniert auch für Später-Kommende;
  meldet Person-Nichtlisting als Hinweis). Client:
  `get_absence_dialog()` (absencedlg.do ohne Zeit-Parameter).
  Tests 171/171; man/wu.1, README, DECISIONS, PITFALLS nachgezogen.
- Befund: Subparser erben das lesson-Parser-Default `--datum=heute`
  trotz SUPPRESS (PITFALLS.md) — Bulk-Modus prüft nur `--termin-id`.

Erledigt (Session 2026-10-12, Commit s. `git log`):
- Open-Perioden 2026/27 ausräumen: 32 Tages-Blöcke / 57 Perioden
  eingetragen (30 Git-Befunde, 2 Supplierungen, POS aus Folien_WS,
  PMM über Parallelklassen-Regel), 3 Absenzenprüfungen —
  `offen verifizieren` 01.09.–12.10.: leer. Nachzug nötig für
  Block-Partner 6236553 (Server aktualisiert Partner nicht immer).
- `offen vorschlag` tagesgenau ((lsId, Datum), nicht Jahrgangs-lsId),
  Supplierungs-Erkennung (ADDED-Lehrer/removed-Original/
  substitutionText) mit Festtext „Supplierung",
  `SUBJECT_REPO_MAP` + PMM. Tests `tests/test_vorschlag.py` (14),
  Manpage/SKILL.md/DOMAIN.md nachgezogen.
- Befund: 5BHIF/WMC_1 (16.09.) und 3AHWIT/NW2 (09.09.) 2026/27 sind
  Supplierungen — erscheinen zurecht im teacher-scoped Arbeitsvorrat.

Erledigt (Session 2026-09-27, Commit s. `git log`):
- `klasse`-Default zeigt nur Kopf (Name, `klassen-id`, KV); Fächer und
  Roster nur mit `--details` (`--fach` impliziert `--details`);
  `--json` liefert `classId` immer.
- `--klassen-id` bei `lesson … aufnehmen/anpassen` optional: Ableitung
  aus `lessonKlassen` (Fallback: Klassen der Anwesenden);
  `_build_students_payload` nimmt eine Klassen-Menge.
- Text-ID-Labels klein (`lsid`, `klassen-id`, `absenz-id`, …);
  JSON-Keys bleiben camelCase.
- `lesson … aufnehmen` löst `--schueler-name`/`-id` über
  `_resolve_schueler` auf (students/overview, tokenisierend); Bug: die
  Substring-Suche gegen die verkürzten Matrix-Namen lieferte 0 Treffer
  für `"ammar khalil"`.
- Tests 148/148; `groff` warnungsfrei.

Erledigt (Session 2026-09-24, #25, s. HISTORY):
- Null-Feld-Crashs bei open-periods, `_subject_matches` nur eine
  Richtung, `student`-KeyError 'class' gefixt.

Last updated: 2026-10-14
