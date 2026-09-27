# Project State

Current status as of 2026-09-27 (klasse-Kopf + klassen-id-Ableitung).

## Current Focus
`klasse`-Default auf den Kopf reduziert (Name, `klassen-id`, KV);
Fächer/Roster nur mit `--details`. `--klassen-id` bei
`aufnehmen`/`anpassen` optional (Ableitung aus `lessonKlassen`).
Text-ID-Labels klein. Tests 148/148 grün (Unit, Fake-Clients, kein Netz).

## Completed (this cycle, 2026-09-27)
- [x] `cmd_klasse`: Standard nur Kopf inkl. `klassen-id`; `--details`
  (und `--fach`) schalten Fächer/Roster frei; JSON-Kopf mit `classId`,
  Listen nur mit `--details`
- [x] `_lesson_class_ids` + `_resolve_class_ids`; `_build_students_payload`
  nimmt `class_ids: set[int]`; `--klassen-id` bei `aufnehmen`/`anpassen`
  optional (stderr-Meldung/ Warnung)
- [x] `lesson … aufnehmen` löst `--schueler-name`/`-id` über
  `_resolve_schueler` auf (students/overview, tokenisierend) statt per
  Substring in den verkürzten Matrix-Namen
- [x] Text-ID-Labels lowercase (`lsid`, `mainstudentgroupid`,
  `absenz-id`, `lehrer-id`, `klassen-id`); JSON-Keys unverändert
- [x] Doku: man/wu.1, README, CONVENTIONS, DECISIONS, WEBUNTIS_API
- [x] Tests: test_klasse_details.py, test_lesson_aufnehmen.py,
  write-guard-Hilfe-Check, Label-Anpassungen

## Pending
- Recording-Session: `lessonKlassen`-Form belegen (read-only).
- Rate-Limit-Reverse-Engineering inkl. Logging (vom Nutzer gewünscht,
  noch nicht begonnen).
- Live-Verifikation der Fehlerklassen (Netz/Auth/Server) an echten
  Endpunkten (siehe #23).
- Code-Review ab Fixpunkt.

## Blockers
- None.

## Notes
- Pre-Push-Hook `scripts/pre-push` läuft `pytest tests/` und blockt rote
  Pushes; pro Clone per Symlink nach `.git/hooks/pre-push` (README).
- `lessonKlassen`-Form ist nicht aus dem Mitschnitt belegt — Ableitung
  deshalb defensiv (dict/int) plus Attendee-Fallback.
- `dict.get(k, default)` greift NUR bei fehlendem Key — WebUntis liefert
  Felder auch als JSON `null` (s. PITFALLS.md).
- `WuError` erbt von `RuntimeError`: Soft-Fail-Handler bleiben nutzbar.
- `wu`-Wrapper: fehlende Module → Exit 8 (= ConfigError).
- JSON-Keys bleiben camelCase (Skill-Parsing); nur Textlabels klein.

## Next Session Suggestion
- Recording-Session für `lessonKlassen`; danach Rate-Limit-Logging.
- Live-Verifikation der Fehlerklassen; Code-Review ab Fixpunkt.
- Folgeissue #22: `raum suchen` echte Freie-Raum-Suche.
