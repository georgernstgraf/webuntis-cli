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

Last updated: 2026-09-27
