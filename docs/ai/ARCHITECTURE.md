# Architecture

Living structural map of the system as of 2026-09-27 (nach klasse-Kopf +
klassen-id-Ableitung). Overwritten when structural changes occur during a
session.

## Overview

webuntis-cli is a Python CLI tool that reverse-engineers and automates
the WebUntis "Lehrstoff eintragen" (lesson topic entry) action. It
consists of a CDP recorder for endpoint discovery, an HTTP client for
API replay, a git-log analyzer for deriving topic text from GRG-*
teaching repos, and an opencode skill that orchestrates the full
fill-open-periods workflow with human confirmation.

## Components (`src/webuntis_cli/`)

| Module | Purpose |
|--------|---------|
| `recorder.py` | CDP-Recorder: attaches to Brave:9222, captures Network + Runtime events to recordings/*.jsonl |
| `client.py` | WebUntis HTTP client: login, JWT, REST/JSON-RPC endpoints, retry-with-backoff, Stundenplan-Parser (parse/group, pure), Absenz-Writes |
| `gitlog.py` | GRG-* git-log analysis: pull, class folder resolution (split/February), commit diffs |
| `cli.py` | Einstieg: Argparse-Verdrahtung + `main()` (deutsche Hilfe mit Beispielen, KLASSE/FACH-Extraktion, UnknownLessonError-Handler) |
| `cli_common.py` | Geteilte Infra: Session/Client, Schuljahr-Flag, Klassen-Lookup (`_find_klasse`), Period-/Lesson-Gruppierung, Topic-Submit, Such-Formatierung |
| `cli_klasse.py` | `klasse` (Übersicht/Roster/Fächer/KV) — Fächer aus Klassen-Stundenplan |
| `cli_lesson.py` | `lesson` (Roster/Matrix/Termine/Info/Teilnehmer/Lehrstoff/Absenzen zeigen/eintragen/entfernen/pruefen) + Plan-basierter Resolver |
| `cli_student.py` | `student` (Suche + Detail: Klasse/KV/Lessons aus Plan-Join, Absenzen opt-in) |
| `cli_lehrer.py` | `lehrer` (Suche + Steckbrief: Kürzel/ID, KV-Klassen) |
| `errors.py` | Typisierte Fehlerhierarchie + Exit-Code-Taxonomie (`classify_exit`) |
| `cli_offen.py` | `offen` (Arbeitsvorrat: Liste/Status/Verifizieren/Vorschlag/Eintragen/Festtexte/Prüfen) |
| `cli_raum.py` | `raum` (suchen/groesse — Stubs, Exit 7; Freie-Raum-Suche Folgeissue) |
| `cli_intern.py` | `intern` (versteckt: login/logout/session/record/rpc/rest) |

## Man-Page & Drift-Test

- `man/wu.1` — autoritative Bedienreferenz (groff, deutsch): Kommandos,
  Optionen, Workflows, Exit-Codes, FILES/ENVIRONMENT, Fallen, INTERNALS.
  Pflichtlektüre für Agents (AGENTS.md-Abschnitt "CLI manual").
- `tests/test_manpage.py` — Drift-Test: leitet Kommando-/Options-Inventar
  aus `add_parser`/`add_argument`-Literalen in `cli*.py` ab und assertet
  Vorkommen in `wu.1`; groff-Render-Check (`-Tutf8`).

## CLI Commands (deutsch, Stand 2026-09-21; alt→neu s. README)

| Command | Purpose |
|---------|---------|
| `klasse KLASSE` | Kopf: Name, `klassen-id`, KV; mit `--details` zusätzlich ALLE Lessons (Stundenplan) + Roster (`--fach` impliziert Details) |
| `klasse KLASSE roster\|faecher\|kv` | Teil-Sichten (TSV-Roster, Lesson-Liste mit Primary-Lehrer/Offen-Count, KV) |
| `lesson KLASSE/FACH` | Roster des Termins zu `--datum` (Standard `heute`) |
| `lesson K/F matrix\|termine\|info` | Anwesenheits-Matrix, Termine+Offen-Status, Diagnostik |
| `lesson K/F lehrstoff zeigen\|eintragen\|aus-git` | Lehrstoff je Termin |
| `lesson K/F absenzen zeigen [--termin-id]` | fehlt/gehalten je Schüler; mit --termin-id echte Absenz-Einträge |
| `lesson K/F absenzen eintragen\|entfernen` | Abwesenheit setzen/löschen (Write, Testlauf-Standard) |
| `lesson K/F absenzen pruefen` | Absenzenprüfung (Write) |
| `lesson K/F aufnehmen\|anpassen` | Teilnehmer-Writes (Testlauf-Standard) |
| `student NAME [--details] [--absenzen]` | Trefferliste (Default, schnell); mit --details Klasse/KV/belegte-nicht-belegte Lessons aus Plan-Join (0 Matrix-Calls); --absenzen (impliziert --details): eigene Lessons |
| `offen liste\|status\|verifizieren` | Arbeitsvorrat lesen (`--von/--bis` optional: Default Schuljahr-Start..heute aus `open-periods/meta`) |
| `offen vorschlag` | Vorschlag-JSON aus Git-Logs (Skill-Input, schreibt nichts) |
| `offen eintragen --datei` | bestätigte Lehrstoffe schreiben |
| `offen festtexte` | SS/BESP-Festtexte (Testlauf-Standard) |
| `offen pruefen` | Absenzenprüfung über Zeitraum/Datei (Write) |
| `raum suchen\|groesse` | Stubs (Exit 7) — Endpunkte dokumentiert, Umsetzung geplant |
| `lehrer NAME` | Suche + Steckbrief (Kürzel/ID, KV-Klassen) |
| `intern …` | versteckt: login/logout/session/record/rpc/rest |

## Lesson-Enumeration (seit 2026-09-21)

- Quelle: `timetable/entries` (CLASS, 1 Woche ± Ferien-Fallback) —
  ALLE Lessons; Gruppierung (Klasse, Fach, Primary-Lehrer) für parallele
  Gruppen (POS1_3BAIF_1/2/3); `eigen` per Slot-Match mit MY_TIMETABLE
  (eigene Lehrerposition ist dort anonymisiert)
- lsId nur im Einzelfall: `calendar-entry/detail` → `lesson.lessonId`
  (= Matrix-lsId, verifiziert); Resolver bevorzugt bei Mehrdeutigkeit
  die eigene Lesson (Matrix ist rechte-beschränkt)
- `open-periods` nur noch: Offen-Status, Arbeitsvorrat, Resolver-Fallback
- `open-periods/meta`: `schoolYear.{start,end}`/`defaultFilter` — Quelle des
  `offen`-Schuljahr-Defaults (UI-Semantik: Ende auf heute gedeckelt)
## `wu` Wrapper

Bash shortcut (tracked at repo root), symlink-fähig: `readlink -f`
auf `$BASH_SOURCE` → ROOT immer der Repo-Root, egal ob per Symlink
(z. B. `~/svn/georg/EDV/Toolset/wu`) aufgerufen. Interpreter:
bevorzugt `.venv/bin/python`, Fallback `python3` mit Import-Probe
(httpx/websockets, einzeln) + deutscher Setup-Anleitung
(Exit 1). `cli.main()` fängt zusätzlich ModuleNotFoundError (Exit 8)
für Direktaufrufe ohne `wu`.

## Skills (`.opencode/skills/`)

| Skill | Purpose |
|-------|---------|
| `fill-open-periods` | Orchestrates: `offen vorschlag` → git-log + diffs → formulate texts → confirm → `offen eintragen` |

## Knowledge Files (`docs/ai/`)

| File | Purpose | Update mode |
|------|---------|------------|
| HANDOFF.md | Open tasks for next session | Overwrite |
| DECISIONS.md | Active decisions still in force | Append; prune → HISTORY.md |
| ARCHITECTURE.md | Living structural map | Overwrite |
| CONVENTIONS.md | Ongoing rules to follow | Append |
| PITFALLS.md | Hard-won failure knowledge | Append |
| DOMAIN.md | Business/domain rules | Append |
| STATE.md | Current project status | Overwrite |
| HISTORY.md | Superseded entries archive | Append-only |

## Data Flows

- **Reverse Engineering**: Brave (CDP:9222) → recorder.py → recordings/*.jsonl → analysis → docs/WEBUNTIS_API.md
- **Lehrstoff Entry**: .env (credentials) → client.login() → JWT → get_open_periods() → gitlog.get_commits_for_class() → agent formulates text → `offen eintragen --datei` → WebUntis PUT
- **Git-Log Analysis**: GRG-* repos → pull_all_repos() → get_commits_for_class(class, date, repo_filter) → get_commit_diff() → agent reads diffs → German Lehrstoff text

## External Dependencies

- Brave Browser (with `--remote-debugging-port=9222`) — for RE only
- WebUntis API (`https://spengergasse.webuntis.com/`) — login + REST/JSON-RPC
- GRG-* git repos (`~/repos/georgernstgraf/GRG-*`) — lesson content source
- `pdftotext` — for GRG-POSTHEORIE PDF folien extraction
