# webuntis-cli

Automate the **Lehrstoff eintragen** (lesson topic entry) and **Absenzen
prüfen** (absence check) chores in [WebUntis] by reverse-engineering the
undocumented REST endpoints that the web UI calls — then replaying them from a
Python CLI.

Built for Georg Graf's teaching at [HTL Spengergasse] (Vienna). Lesson topics are
derived automatically from the Git history of the [GRG-*] teaching repositories,
so the agent fills in what was actually taught based on commits, diffs, and
README entries — no manual typing required.

> ⚠️ This is a **reverse-engineering** project. The write endpoints for lesson
> topics and absence checks are **not part of the public WebUntis JSON-RPC API**.
> They were discovered by recording browser traffic via the Chrome DevTools
> Protocol. See [`docs/WEBUNTIS_API.md`](docs/WEBUNTIS_API.md) for the full
> endpoint reference.

---

## Features

- **CDP-Recorder** — attaches to a running Brave browser via
  `--remote-debugging-port=9222` and captures all Network requests, response
  bodies, and console output for the WebUntis domain into structured JSONL
  files. No F12 or cURL copying needed.
- **WebUntis Client** — logs in, obtains JWT, and replays the discovered
  endpoints: lesson topics (GET/PUT), open periods, schoolyears, and absence
  checks (CSRF-protected POST). All dynamic values (teacherId, Tenant-Id,
  School-Year-Id) are derived at runtime from the JWT — no hardcoded constants.
- **Git-Log Analyzer** — scans the GRG-* teaching repos to find what was
  taught on a given date: handles split classes (`_X`/`_Y` groups), February
  class-name changes (`3aaif` → `4aaif`), ±10/±30-day commit windows, and
  full commit diffs.
- **Fill-Open-Periods Skill** — an [opencode] skill that orchestrates the
  full workflow: fetch open periods → derive topic text from git diffs →
  present a confirmation table → batch-submit via the CLI.
- **Retry-with-Backoff** — survives transient IP rate-limiting (TCP resets)
  from the WebUntis server after rapid API calls.

---

## Quick Start

### Prerequisites

- Python 3.11+
- A Brave (or Chromium) browser
- GRG-* teaching repos under `~/repos/georgernstgraf/GRG-*`
- A WebUntis account with teacher access

### Install

```bash
cd ~/repos/georgernstgraf/webuntis-cli
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Configure

```bash
cp .env.example .env
# Edit .env and fill in your WebUntis credentials:
#   user=grafg
#   password=<your-password>
#   school=spengergasse
#   host=https://spengergasse.webuntis.com
```

---

## Verwendung

Kurzbefehl: `./wu …` — z.B. `./wu student "Erika Muster"`.
Er setzt `PYTHONPATH=src` und reicht an `webuntis_cli.cli` durch.

Domain-Objekte: **Klasse** (`wu klasse 3AHWII`), **Lesson** als
`KLASSE/FACH` (`wu lesson 3AHWII/SWP1x`), **Student**
(`wu student "Erika Muster"`). Alle Ausgaben sind deutsch;
`wu --help` (und jede Gruppen-Hilfe) erklärt mit Beispielen.

> **Bedienungsanleitung:** Die vollständige Referenz — alle Befehle,
> Optionen, Arbeitsabläufe, Exit-Codes und Fallen, mehr als `--help` —
> steht in der Man-Page `man/wu.1`. Systemweit mit `man wu`
> (s. u.), sonst direkt aus dem Repo: `man --local-file man/wu.1`.

### Man-Page für den eigenen Nutzer verfügbar machen (`man wu`)

Damit `man wu` in jedem Verzeichnis funktioniert, verlinke die Man-Page
in dein Nutzer-Man-Verzeichnis — ganz ohne Root-Rechte. Als Symlink
wirken spätere Änderungen an `man/wu.1` sofort, kein erneutes Kopieren
nötig. Aus dem Repo-Wurzelverzeichnis:

```bash
mkdir -p ~/.local/share/man/man1
ln -sf "$PWD/man/wu.1" ~/.local/share/man/man1/wu.1
mandb -q ~/.local/share/man     # optional: whatis/apropos-Index
man wu
```

`~/.local/share/man` steht auf den meisten Systemen bereits in
`manpath`; prüfen mit `manpath`. Falls nicht, einmalig ergänzen:

```bash
export MANPATH="$HOME/.local/share/man:$MANPATH"   # z. B. in ~/.bashrc
```

### Tests vor jedem Push (Git-Hook)

`scripts/pre-push` lässt vor jedem `git push` die pytest-Suite laufen und
bricht den Push bei roten Tests ab. Einmalig pro Clone verlinken (das
Hook-Verzeichnis ist nicht versioniert, das Skript schon):

```bash
ln -sf ../../scripts/pre-push .git/hooks/pre-push
```

Der Hook nutzt bevorzugt `.venv/bin/python`, sonst `python3`; fehlt
pytest, wird der Push nicht blockiert (nur ein Hinweis). Bewusst
umgehen: `git push --no-verify`.

### Offene Perioden (Arbeitsvorrat: Lehrstoff oder Absenzen fehlen)

```bash
./wu offen status --von 2025-09-01 --bis 2026-07-05
./wu offen liste --von 2025-09-01 --bis 2026-07-05 --json
```

### Klasse und Lesson

```bash
./wu klasse 3AHWII                    # Kopf: Name, klassen-id, KV
./wu klasse 3AHWII --details          # + alle Lessons der Klasse, Roster
./wu klasse 3AHWII faecher            # Lessons aus dem Stundenplan
./wu lesson 3AHWII/SWP1x              # Roster des nächsten Termins
./wu lesson 3AHWII/SWP1x termine --mit-lehrstoff
./wu lesson 3AHWII/SWP1x absenzen zeigen
./wu student "Erika Muster"           # nur Trefferliste (schnell)
./wu student "Erika Muster" --details # + Klasse, KV, belegte Lessons (ohne Matrix)
./wu student --id 4711 --details      # derselbe Detail-Zugriff per Schüler-ID
./wu student "Erika Muster" --absenzen  # + fehlt/gehalten der eigenen Lessons
```

`klasse` zeigt standardmäßig nur den Kopf (Name, `klassen-id` für
`--klassen-id`, KV); Fächer und Roster kommen mit `--details` (spart
API-Calls). In der Textausgabe sind ID-Felder klein geschrieben und
folgen dem Flag (`lsid`, `klassen-id`, …); JSON-Keys bleiben camelCase.

`student` liefert standardmäßig nur die Trefferliste (keine
Detail-Calls). Mit `--details` kommt je Treffer die Detailausgabe:
belegt/nicht belegt aus dem Schüler-Stundenplan (belegt = eingeschrieben,
Anwesenheit egal); parallele Gruppen desselben Fachs werden über den
Primary-Lehrer getrennt, `eigen`-Lessons erkannt. `--details` läuft ohne
Matrix-Calls; `--absenzen` impliziert `--details` und ist opt-in.

### Schüler in eine Lesson aufnehmen

```bash
./wu klasse 3BAIF                       # zeigt klassen-id (kann --klassen-id überschreiben)
./wu lesson --lsid 215940 aufnehmen --schueler-name "Erika Muster"
./wu lesson --lsid 215940 aufnehmen --schueler-name "Erika Muster" --ausfuehren
```

Die Heimatklasse wird ohne `--klassen-id` aus der Lesson abgeleitet
(Quelle `lessonKlassen`, Fallback über die Klassen der Anwesenden); die
abgeleitete klassen-id wird nach stderr gemeldet.

### Einzelnen Lehrstoff schreiben

```bash
./wu lesson 3AHWII/SWP1x lehrstoff zeigen --termin-id 5458590
./wu lesson 3AHWII/SWP1x lehrstoff eintragen \
    --termin-id 5458590 --text-datei /tmp/topic.txt --ausfuehren
```

(`--text-datei` statt `--text "…"` verwenden — die Shell verstümmelt
Umlaute wie `HÜ`, `ä`, `ö`.)

OHNE `--ausfuehren` ist jeder Write nur ein Testlauf (zeigt, was
geschrieben würde) — es wird nie versehentlich etwas eingetragen.

### Lehrstoffe aus Git-Historie vorschlagen + batchweise eintragen

```bash
./wu offen vorschlag --von 2025-09-01 --bis 2026-07-05 > vorschlag.json
# Texte prüfen/bestätigen, dann (--ausfuehren ist Pflicht zum Schreiben):
./wu offen eintragen --datei batch.json --pause 1.0 --ausfuehren
```

Vorschlags-JSON-Format je Block: `periodId`, `topicId`, `text`,
`classId`, `start`, `end`, `date` (+ `commits`/`diffs` als Quelle).

### Lehrstoff-Text aus Git-Historie ableiten (einzeln)

```bash
./wu lesson 5AHWII/SWP1y lehrstoff aus-git --datum 2026-03-18
```

Sucht in den GRG-*-Repos nach Commits zu Klasse+Datum (±10 Tage,
±30 Fallback), zeigt Commits + Diffs und schlägt einen Text vor.
Mit `--ausfuehren` (+ `--termin-id`/`--thema-id`) direkt eintragen.

### Absenzen prüfen

Einzelner Termin oder ganze Lesson:

```bash
./wu lesson 3AHWII/SWP1x absenzen pruefen --termin-id 5457498 --ausfuehren
./wu offen pruefen --von 2025-09-01 --bis 2026-07-05 --pause 1.5 --ausfuehren
```

### Abwesenheit eintragen / entfernen (Write, Testlauf-Standard)

Echte Abwesenheits-Einträge im Klassenbuch (getrennt von der
Matrix-Anwesenheit). Termin via `--termin-id` oder `--datum` (Standard
heute, KLASSE/FACH-Adresse); Block-Standard wie in der Untis-UI
(`--kein-block` für eine Einzelstunde, nur mit `--termin-id`).

```bash
./wu lesson 3AHWII/SWP1x absenzen eintragen --schueler-name "Erika Muster" --datum 2026-09-25
./wu lesson 3AHWII/SWP1x absenzen zeigen --termin-id 5457498   # Absenz-IDs listen
./wu lesson 3AHWII/SWP1x absenzen entfernen --absenz-id 3170001 --termin-id 5457498
```

### Räume (vorbereitet, noch nicht implementiert)

```bash
./wu raum suchen --datum 2026-09-25 --stunde 7 --max-plaetze 20   # Exit 7: Stub
./wu raum groesse B3.07                                          # Exit 7: Stub
```

Die Endpunkte (Raum-Stundenplan, Raumverzeichnis mit Sitzplätzen) sind
dokumentiert (`docs/WEBUNTIS_API.md`); die Freie-Raum-Suche ist als
Folgeissue geplant.

### Migration (alte → neue Befehle, Stand 2026-09-21)

Harter Schnitt ohne Aliase. Entsprechungstabelle:

| alt | neu |
|---|---|
| `students roster KLASSE FACH` | `lesson KLASSE/FACH [roster]` |
| `students list --lsid X` | `lesson --lsid X matrix` |
| `students add/edit …` | `lesson KLASSE/FACH aufnehmen/anpassen …` |
| `students find NAME` | `student NAME` |
| `lessons KLASSE` | `klasse KLASSE faecher` |
| `lesson info LSID` | `lesson --lsid LSID info` / `lesson KLASSE/FACH info` |
| `lehrstoff list/status/verify` | `offen liste/status/verifizieren` |
| `lehrstoff fill` (Vorschlag) | `offen vorschlag` |
| `lehrstoff batch-set --file` | `offen eintragen --datei` |
| `lehrstoff fill-fixed` | `offen festtexte` |
| `lehrstoff get/set/from-git` | `lesson KLASSE/FACH lehrstoff zeigen/eintragen/aus-git` |
| `absences check-all/batch-check` | `offen pruefen` |
| `absences check --period` | `lesson KLASSE/FACH absenzen pruefen --termin-id` |
| `kv KLASSE` / `kv --student` | `klasse KLASSE kv` / `student NAME` |
| `search NAME --detail` | `student NAME` / `lehrer NAME` / `klasse KLASSE` (je nach Treffer) |
| `login/logout/session/record/rpc/rest` | `intern …` (aus der Hilfe versteckt) |

Neu (Stundenplan-Serie, 2026-09-21): `student --absenzen` (Absenzen
opt-in, eigene Lessons), `lesson KLASSE/FACH absenzen
eintragen/entfernen` (echte Abwesenheits-Einträge, Write),
`lesson KLASSE/FACH absenzen zeigen --termin-id` (Absenz-IDs listen),
`raum suchen/groesse` (Stubs). `klasse … faecher` zeigt jetzt ALLE
Lessons der Klasse aus dem Stundenplan statt nur offener.

Neu (2026-09-27): `klasse KLASSE` zeigt standardmäßig nur den Kopf
(Name, `klassen-id`, KV) — Fächer und Roster nur mit `--details`.
`--klassen-id` bei `lesson … aufnehmen/anpassen` ist optional und wird
sonst aus der Lesson abgeleitet. ID-Felder in der Textausgabe sind klein
geschrieben (`lsid`, `klassen-id`, …); JSON-Keys bleiben camelCase.

Flag-Umbenennungen: `--school-year-id` → `--schuljahr-id`,
`--start/--end` → `--von/--bis`, `--dry-run/--no-dry-run` →
`--testlauf/--ausfuehren`, `--date` → `--datum` (`heute` statt `now`),
`--text-file` → `--text-datei`, `--file` → `--datei`,
`--delay` → `--pause`, `--class-id` → `--klassen-id`,
`--period` → `--termin-id`, `--topic-id` → `--thema-id`.
JSON-Schlüssel bleiben englisch.

### Exit-Codes

Jede Fehlerklasse hat einen eigenen Exit-Code (Details: `man/wu.1`):

| Code | Bedeutung |
---|---|---|
| 0 | Erfolg |
| 1 | Kein Befehl (volle Hilfe gedruckt) |
| 2 | Verwendungsfehler (Unterbefehl-Hilfe + Fehlerzeile) |
| 3 | Nicht gefunden (Klasse/Schüler/Lesson/Absenz/Schuljahr) |
| 4 | Anmeldung/Session (401/403, Sperre) |
| 5 | Netzwerkfehler (Verbindung/Timeout) |
| 6 | Serverfehler (5xx, JSON-RPC) |
| 7 | Noch nicht implementiert (`raum`-Stubs) |
| 8 | Konfiguration/Setup (fehlendes Modul/`.env`) |
| 9 | Unerwarteter interner Fehler (Bug, mit Traceback) |

### Reverse-engineer new endpoints (CDP-Recorder)

1. Start Brave with the debug port:

   ```bash
   scripts/brave-debug.sh
   ```

2. In Brave, open WebUntis and log in.

3. Start the recorder:

   ```bash
   .venv/bin/python -m webuntis_cli.recorder
   ```

4. Perform the action you want to capture (e.g. enter a lesson topic, check
   absences) in the WebUntis UI as usual.

5. Stop the recorder (Ctrl-C). Inspect `recordings/` for the captured
   requests, response bodies, and cookies.

---

## How It Works

### Reverse-Engineering Workflow

```
Brave (CDP :9222)
  └── recorder.py captures Network + Runtime events
       └── recordings/*.jsonl (requests, responses, cookies)
            └── analysis → docs/WEBUNTIS_API.md
                 └── client.py replays the endpoints
```

The recorder attaches to Brave via the Chrome DevTools Protocol and
subscribes to `Network.*` and `Runtime.*` events. It captures:

- `Network.requestWillBeSent` — URL, method, headers, POST body
- `Network.responseReceived` — status, headers, MIME type
- `Network.getResponseBody` — full response body (after `loadingFinished`)
- `Runtime.consoleAPICalled` — all `console.log/error/warn` output
- `Network.getAllCookies` — session cookies (harvested at session end)

Output goes to `recordings/{timestamp}_network.jsonl`,
`recordings/{timestamp}_console.jsonl`, and `recordings/{timestamp}_cookies.json`
(all gitignored — they contain session cookies).

### Fill-Open-Periods Workflow

```
.env (credentials)
  └── client.login() → JSESSIONID + schoolname cookies
       └── client.get_jwt() → Bearer JWT (person_id, tenant_id)
            └── client.get_open_periods() → list of owed lessons
                 └── gitlog.get_commits_for_class() → matching commits
                      └── gitlog.get_commit_diff() → full diffs
                           └── agent formulates German topic text
                                └── user confirms → batch-set → WebUntis PUT
```

### Subject → Repository Mapping

The agent maps WebUntis subject short names to candidate GRG-* repos by
prefix matching (so `SWP1x`, `SWP1y`, `SWP1` all match `SWP`):

| WebUntis subject | GRG repos |
|---|---|
| `POS1` / `POS` | GRG-POSTHEORIE, GRG-JAVA |
| `SWP1x` / `SWP1y` / `SWP` | GRG-SWP, GRG-CS |
| `WMC_1` / `WMC` | GRG-WMC |
| `INFIx` / `INF` | GRG-INFI |
| `CS` | GRG-CS |
| `SS` | _(fixed text: "Sprechstunde")_ |
| `BESP` | _(fixed text: "Bewegung und Sport")_ |

Unknown subjects trigger a warning so the mapping can be extended. See
`SUBJECT_REPO_MAP` in [`src/webuntis_cli/client.py`](src/webuntis_cli/client.py).

---

## Project Layout

```
webuntis-cli/
├── src/webuntis_cli/
│   ├── recorder.py       # CDP-Recorder: Network + Runtime → recordings/
│   ├── client.py         # WebUntis API client (login, JWT, REST, absences)
│   ├── gitlog.py         # GRG-* git-log analysis (split classes, diffs)
│   ├── cli.py            # CLI-Verdrahtung: klasse/lesson/student/offen/…
│   ├── cli_common.py     # geteilte Infra (Session, Period-Helpers, Suche)
│   ├── cli_klasse.py     # klasse: Übersicht, Roster, Fächer, KV
│   ├── cli_lesson.py     # lesson: Roster, Termine, Lehrstoff, Absenzen
│   ├── cli_student.py    # student: Suche + Detail (Fächer, Absenzen)
│   ├── cli_lehrer.py     # lehrer: Suche + Steckbrief (Kürzel, KV-Klassen)
│   ├── cli_offen.py      # offen: Arbeitsvorrat (Vorschlag, Eintragen, Prüfen)
│   ├── cli_raum.py       # raum: Stubs (Freie-Raum-Suche, Exit 7)
│   └── cli_intern.py     # intern: Session, Recorder, rpc/rest (versteckt)
├── scripts/
│   ├── brave-debug.sh     # start Brave with --remote-debugging-port=9222
│   ├── pre-push           # git hook: pytest vor jedem Push
│   └── show-cookies.py    # inspect harvested cookies
├── tests/                 # pytest-Suite (Fake-Clients, keine Netz-Calls)
├── docs/
│   ├── WEBUNTIS_API.md    # authoritative endpoint reference
│   └── ai/                # knowledge persistence (DECISIONS, PITFALLS, …)
├── .opencode/skills/
│   └── fill-open-periods/SKILL.md  # opencode skill for the full workflow
├── .env.example          # template for credentials (copy to .env)
├── .gitignore            # ignores .env, .venv, recordings/, *.jsonl
├── AGENTS.md             # agent instructions + knowledge bootstrap
└── pyproject.toml        # Python package config
```

---

## Key Design Decisions

- **No hardcoded constants** — teacherId, Tenant-Id, and School-Year-Id are
  all derived at runtime from the JWT and REST API.
- **Python + httpx for replay** (not Playwright) — once endpoints are known,
  pure HTTP calls suffice; no browser needed for normal operation.
- **Skill-based architecture** — an opencode skill orchestrates the CLI
  calls; the agent (LLM) holds git-log context in memory and formulates
  topic texts from diffs with human confirmation before submission.
- **±10/±30-day git-log window** — catches commits made shortly after the
  lesson, with a wider fallback for longer delays.

See [`docs/ai/DECISIONS.md`](docs/ai/DECISIONS.md) for the full list.

---

## License

Private project. Not for redistribution.

[WebUntis]: https://www.untis.at/de/produkte/webuntis-die-online-erweiterung
[HTL Spengergasse]: https://www.spengergasse.at
[GRG-*]: https://github.com/georgernstgraf?tab=repositories&q=GRG
[opencode]: https://opencode.ai
