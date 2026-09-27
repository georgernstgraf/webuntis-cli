# Conventions

Coding patterns, naming rules, and style agreements for this project.
Follow these without question. Do not deviate unless explicitly told.

## CLI-Vokabular (deutsch, seit 2026-09-21)
- Top-Level: `klasse`, `lesson`, `student`, `lehrer`, `offen`,
  `raum` (Stubs), `intern` (intern aus der Hilfe versteckt,
  s. DECISIONS.md)
- Lesson-Adresse: genau EIN Positionsargument `KLASSE/FACH`
  (z.B. `3AHWII/SWP1x`); `--lsid` nur als direkter Ausweg
- Optionen: `--schuljahr-id`, `--datum (YYYY-MM-DD|heute)`,
  `--von/--bis` (Zeiträume; bei `offen` optional, Default
  Schuljahr-Start..heute aus open-periods/meta), `--testlauf/--ausfuehren`,
  `--text-datei`, `--klassen-id`, `--termin/--thema-id`, `--datei`,
  `--pause`, `--details`; `--json` und `--lsid` bleiben (sprachneutral)
- Flags sind deutsch, `dest`s (args-Attribute) bleiben englisch
  (interner Code): z.B. `--schuljahr-id` mit `dest="school_year_id"`;
  nur sichtbare Strings werden übersetzt, kein Reader-Umbau
- **ID-Bezeichner in der Textausgabe klein** (seit 2026-09-27): `lsId`
  → `lsid`, `mainStudentgroupId` → `mainstudentgroupid`, `Absenz-ID` →
  `absenz-id`, `Lehrer-ID` → `lehrer-id`; wo ein Flag existiert, gilt
  dessen Schreibweise (`klassen-id`, `termin-id`, `thema-id`,
  `absenz-id`), damit die kopierte Bezeichnung als Option passt.
  JSON-Keys bleiben unverändert englisch-camelCase (`lsId`, `classId`,
  …) — das Skill parst sie
- Jede (Sub-)Gruppe bekommt `description` + `epilog` mit Beispielen —
  `wu` ohne Argumente muss selbsterklärend sein
- Absenzen-Schalter: `--absenzen` (opt-in, `student`) — Standardausgabe
  bleibt Matrix-frei; `student` zeigt den Detailblock (KV, Fächer,
  Absenzen) nur mit `--details`, Default ist die reine Trefferliste;
  `--absenzen` impliziert `--details` (spart sonst die teuren
  Detail-Calls, s. DECISIONS.md)
- **ALLE Writes sind testlauf-Standard** (`--testlauf` = nur zeigen, kein
  Write) und schreiben nur mit `--ausfuehren`: `lesson aufnehmen/anpassen`,
  `lesson lehrstoff eintragen/aus-git`,
  `lesson absenzen eintragen/entfernen/pruefen`,
  `offen eintragen/festtexte/pruefen`. Einzige Ausnahme sind die bewusst
  schreibfaehigen Roh-Passthroughs `intern rpc`/`intern rest`
  (Variante B, kein Testlauf-Schalter — im Man-Page dokumentiert)

## Fehler & Exit-Codes (seit 2026-09-23)
- Fehler kommen aus `errors.py` (`WuError`-Subklassen), NICHT als
  nackte `RuntimeError`/`SystemExit`. Jede Klasse trägt `exit_code`:
  2 Usage, 3 NotFound, 4 Auth, 5 Network, 6 Server, 7 NotImplemented,
  8 Config, 9 Unexpected.
- `cli.main()` ist der EINZIGE Exit-Punkt; `classify_exit()` löst
  gewrappte Fehler über die `__cause__`/`__context__`-Kette auf.
- Argument-Prüfungen nutzen `usage_error(args, msg)` (volle
  Unterbefehl-Hilfe + Fehlerzeile zuletzt, Exit 2); alle Parser sind
  `_HelpfulParser`, damit auch argparse-Fehler die Hilfe zeigen.
- „nicht gefunden“, Server-, Netzwerk- und Auth-Fehler NICHT als
  Usage behandeln; Soft-Fail-Handler (`except RuntimeError: print`)
  bleiben erlaubt, weil `WuError` von `RuntimeError` erbt.

## Naming
- Class names from WebUntis are UPPERCASE (e.g. `5AHWII`); git folder names are lowercase (e.g. `5ahwii/`). Always lowercase for git pathspec.
- WebUntis subject short names: `SWP1x`, `SWP1y`, `WMC_1`, `INFIx`, `POS1`, `POS2` — prefix-matched against `SUBJECT_REPO_MAP`
- Recording files: `{timestamp}_{domain_with_underscores}_{type}.jsonl`

## File Layout
- `src/webuntis_cli/` — Python-Paket: recorder, client, gitlog,
  errors, cli (Verdrahtung) + cli_common (Infra), cli_klasse,
  cli_lesson, cli_student, cli_lehrer, cli_offen, cli_raum, cli_intern
- `scripts/` — shell scripts (brave-debug.sh, pre-push) and helper scripts (show-cookies.py)
- `recordings/` — gitignored, contains session cookies and captured traffic
- `docs/WEBUNTIS_API.md` — authoritative API reference
- `docs/ai/` — knowledge persistence files
- `.opencode/skills/` — opencode skills (fill-open-periods)
- `.env` — gitignored, contains WEBUNTIS_USER/PASSWORD
- `wu` — CLI shortcut wrapper: resolves symlinks (`readlink -f`) so it works from any directory; prefers the repo's `.venv/bin/python`, falls back to `python3` with an import-probe of httpx/websockets and a German setup guide (exit 8 = ConfigError) when modules are missing; `cli.main()` additionally catches ModuleNotFoundError (exit 8) for direct `python -m` calls

## Doku-Schablonen (API-Referenz, seit 2026-09-21)
- Jeder neu entdeckte Endpunkt bekommt in `docs/WEBUNTIS_API.md` EINE
  Schablone: Zweck, Methode/Pfad, Query-/Body-Params (Typ, Pflicht,
  Beispiel), Header, Response-Form (Felder + Typen + Semantik
  kritischer Felder), Write-Warnung falls zutreffend, CLI-Mapping,
  Recording-Quelle.
- **Anonymisierung (verbindlich)**: KEINE echten IDs und KEINE echten
  Personen-/Klassen-/Raumnamen in Beispielen — Platzhalter
  (`CLASS_ID`, `STUDENT_ID`, `LESSON_ID`, `PERIOD_ID`, `ABSENCE_ID`,
  `ROOM_ID`) oder offenkundig fiktive Werte (`Erika Musterfrau`,
  `5XZY`). Hinweis aufnehmen, dass Live-IDs jederzeit per CLI
  (`--json`, `intern rest`) in Sekunden erhältlich sind. Echte Werte
  nur in `recordings/` (gitignored) bzw. `docs/ai/LOCAL.md` (gitignored,
  nur auf Wunsch).

## Lesson-Enumeration (seit 2026-09-21)
- „Lesson" = Fach in einer Klasse (1–2 Semester); Termine sind
  Detail-Sicht (Absenzen/Lehrstoff), keine eigene Entität der CLI-Adresse
- Enumerations-Quelle ist der KLASSEN-STUNDENPLAN
  (`timetable/entries`, resourceType=CLASS) — ALLE Lessons; `open-periods`
  nur für Offen-Status/Arbeitsvorrat/Resolver-Fallback
- `belegt` = eingeschrieben (Fach im Schüler-Stundenplan) — Anwesenheit
  ist NICHT Teil der Definition; krank-immer-abwesende bleiben belegt
- lsId nur im Einzelfall auflösen (Resolver, `--absenzen`): ein
  `calendar-entry/detail`-Call — keine lsId-Spalten in Listen

## API Patterns
- All REST calls go through `Client._rest_headers()` which injects Cookie, Authorization (Bearer JWT), Tenant-Id, X-Webuntis-Api-School-Year-Id
- `_request_with_retry(..., headers=...)` MUST receive auth-dependent headers as a CALLABLE (not a dict) — after a transparent re-login the retry must pick up the NEW cookie/JWT; a static dict replays the dead session
- HTTP method does NOT imply read/write in this API: `open-periods` and all JSON-RPC are POST but read-only; writes are `PUT classreg/lesson-topics`, `submitStudentLessonPeriodData`, `absencechecked` POST. Generic passthrough (`rpc`/`rest` CLI) is therefore write-capable by design (Variante B), method+body echoed to stderr
- REST view routes live under `/WebUntis/api/rest/view/v1/...` (e.g. `app/data` = `/api/rest/view/v1/app/data`, NOT `/api/app/data`)
- Person search: exact `search_timetable()` matches NO multi-word phrases and student displayNames are anonymized — use the shared `search_timetable_tokens()` fallback (tokenize + shortname heuristic, flagged via `searchNote`); only `student` falls back to older years automatically, everything else keeps the current-year default; non-current hits must always be flagged NICHT AKTUELL (`current: false`)
- JWT is auto-refreshed 60s before expiry
- Login via `POST /WebUntis/j_spring_security_check` (form-encoded, not JSON); the 302 redirect is NOT a success signal — verify via the `anonymousMode` marker (see `client.login()`, docs/WEBUNTIS_API.md § login)
- `offen eintragen` uses `--pause 1.0` (1 second between PUTs) to avoid IP rate-limiting
- `id: 0` in PUT body creates a new topic; existing `id` updates
- `--schuljahr-id` works before AND after the subcommand (subparser copies use `default=SUPPRESS`, subcommand wins on double use)
- `offen festtexte --json`: JSON with the flag, human-readable lines without — in BOTH testlauf and write paths
- Export commands keep stdout paste-clean (TSV/JSON only); all diagnostics, warnings and notes go to stderr
- Ambiguous `KLASSE/FACH` lessons auto-pick the closest `lsId` to the reference date with a stderr label block (one `class/subject (date)` line per candidate)

## Git-Log Analysis
- `get_commits_for_class(class, date, repo_filter=repos)` — always pass `repo_filter` to scope to candidate repos
- `resolve_class_folders_for_date(class, date)` — includes `_X/_Y/_Z` split variants AND February name-change variants
- `get_commit_diff(repo, hash, max_bytes=4000)` — full diff, truncated
- Class names may change in February: Abteilungsklassen (aif/cif/kif) advance year (3aaif→4aaif); Tagesklassen (hwii/hwit) stay same

## Testing
- `pytest tests/test_gitlog.py` — 8 tests covering split classes, February name change, ±10/±30 window, known examples
- Tests use real git repos (not mocked) — run from the repo with GRG-* repos present
- Pre-Push-Hook `scripts/pre-push` läuft `pytest tests/` und blockiert rote
  Pushes (Exit 1); Installation pro Clone per Symlink nach
  `.git/hooks/pre-push` (README); Bypass `git push --no-verify`; fehlt
  pytest, wird nicht blockiert (Hinweis)

## Privacy
- This repo is PUBLIC. No person data in any tracked file: no student or
  teacher names, no student IDs, no person-linked details — in any file
  (docs/ai/*, docs/*, code, tests, commit messages).
- Person data (names, student IDs) may be written ONLY to
  `docs/ai/LOCAL.md` (gitignored, local-only, NOT synced between
  machines) and ONLY on explicit user request.
- `HANDOFF.md`/`STATE.md` stay tracked but anonymized; person-specific
  entries point to LOCAL.md via `[Details: LOCAL.md]`.
- Allowed in tracked files: counts, lesson ids (lsId), class ids,
  period ids, subject names.
- Git history is never rewritten — exposure, once committed, stays.
  Be careful BEFORE writing.
