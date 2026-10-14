# Project State

Current status as of 2026-10-14 (Absenzen-Bulk + Absenz-Existenzcheck).

## Current Focus
`absenzen eintragen --von/--bis` (Bulk-Write je gehaltenem Datum,
Block-Start, Testlauf-Standard) und `absenzen zeigen --absenz-id
--termin-id` (absencedlg-Existenzcheck; funktioniert auch für
Später-Kommende, die der classreg-Dialog historischer Termine nicht
listet). Tests 171/171 grün (Unit, Fake-Clients, kein Netz).

## Completed (this cycle, 2026-10-14)
- [x] `client.get_absence_dialog(absence_id, period_id)`:
  absencedlg.do ohne Zeit-Parameter, `parse_dojo_viewmodel`,
  ID-Mismatch → NotFoundError
- [x] `_absenzen_zeigen_absenz_id`: Dialog-Details + Teilnehmer-Check
  gegen das classreg-ViewModel (Hinweis bei Nichtlisting, stdout+stderr)
- [x] `_absenzen_eintragen_bulk`: Matrix-LessonPeriods → Zeitraum-Filter
  (≤ heute), Gruppierung je Datum auf Block-Start, Testlauf-Liste,
  Write-Loop mit `--pause` und Ergebnis-Summary
- [x] Validierung: `--termin-id` kollidiert mit `--von/--bis`
  (geerbtes `--datum`-Default bleibt erlaubt, s. PITFALLS)
- [x] Doku: man/wu.1 (zeigen/eintragen + Beispiele), README,
  DECISIONS, PITFALLS
- [x] Realer Einsatz: 11 Terminblöcke (2 Lessons) Absenzen für einen
  später-kommenden Schüler [Details: LOCAL.md], Absenzenprüfung,
  INFIx-Lehrstoff 13.10. nachgetragen — `offen` 01.09.–14.10.: 3AHWII leer

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
- `absenzen zeigen --termin-id` ist KEINE vollständige Absenz-Liste:
  Absenzen von Später-Kommenden fehlen im classreg-Dialog (PITFALLS).
- Subparser erben `lesson`-Defaults (`--datum=heute`) trotz SUPPRESS.
- `dict.get(k, default)` greift NUR bei fehlendem Key — WebUntis liefert
  Felder auch als JSON `null` (s. PITFALLS.md).
- `WuError` erbt von `RuntimeError`: Soft-Fail-Handler bleiben nutzbar.
- `wu`-Wrapper: fehlende Module → Exit 8 (= ConfigError).
- JSON-Keys bleiben camelCase (Skill-Parsing); nur Textlabels klein.

## Next Session Suggestion
- Recording-Session für `lessonKlassen`; danach Rate-Limit-Logging.
- Live-Verifikation der Fehlerklassen; Code-Review ab Fixpunkt.
- Folgeissue #22: `raum suchen` echte Freie-Raum-Suche.
