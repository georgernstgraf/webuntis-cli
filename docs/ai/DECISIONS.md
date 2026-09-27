# Decisions

Active architectural and technical decisions still in force.
Superseded decisions are relocated to HISTORY.md.

## 2025-08-21: CDP-Recorder as primary RE tool
- **Choice**: Use Chrome DevTools Protocol (CDP) via WebSocket to capture Network + Runtime events from a running Brave browser
- **Reason**: `--enable-logging --v=1` only captures Chromium-internal logs, not WebApp console.log. CDP `Runtime.consoleAPICalled` captures all JS console output. CDP `Network.*` captures all HTTP requests with bodies.
- **Considered**: Browser extension, page-script injection, manual F12 copying
- **Tradeoff**: Brave must run with `--remote-debugging-port=9222`

## 2025-08-21: Python + httpx as client stack (not Playwright for replay)
- **Choice**: Use httpx for API replay, Playwright/CDP only for recording
- **Reason**: Once endpoints are known, pure HTTP calls suffice. No browser needed for normal operation.
- **Considered**: Playwright for both recording and replay
- **Tradeoff**: Session cookies must be obtained via login (`.env`) or harvested from browser

## 2025-08-21: No hardcoded constants — all dynamic from JWT/session
- **Choice**: teacherId, Tenant-Id, School-Year-Id all derived at runtime
- **Reason**: User explicitly required no hardcoded constants. JWT contains `person_id` (teacherId) and `tenant_id`. Schoolyears come from REST API.
- **Considered**: Hardcoding 514/7046800/21
- **Tradeoff**: One extra API call for schoolyears, JWT decode needed

## 2025-08-21: Subject→Repo mapping by prefix, not exact match
- **Choice**: `SUBJECT_REPO_MAP` matched by prefix (e.g. "SWP" matches SWP1x, SWP1y, SWP1)
- **Reason**: WebUntis subject short names vary by group (SWP1x, SWP1y, WMC_1, INFIx, POS1, POS2)
- **Considered**: Exact match per variant
- **Tradeoff**: Must verify no false prefix matches (e.g. "INF" matches "INFI" but also "INFO" if it existed)

## 2025-08-21: JSON-Datei statt --text-Flag für Bulk-Einträge
- **Choice**: `offen eintragen --datei <json>` für Bulk; `--text-datei`/`--text-stdin` für einzeln
- **Reason**: Shell-Quoting zerstört UTF-8 (Umlaute: "HÜ" wurde "HUe")
- **Considered**: nur `--text`
- **Tradeoff**: extra Temp-Datei, dafür UTF-8-sicher

## 2025-08-21: id=0 for new topic creation
- **Choice**: When topicId is None (no existing topic row), send `id: 0` in PUT body
- **Reason**: WebUntis server creates a new topic row when id=0. Discovered by testing.
- **Considered**: Omitting id field, using null
- **Tradeoff**: None known

## 2025-08-21: ±10 day git-log window with ±30 fallback
- **Choice**: Default ±10 days around lesson date, fallback ±30 if empty
- **Reason**: User sometimes commits days/weeks after the lesson. ±10 catches most, ±30 catches longer delays.
- **Considered**: ±10 only, ±30 only, whole schoolyear
- **Tradeoff**: ±30 may catch unrelated commits from adjacent lessons

## 2025-08-21: Skill-based architecture (not batch script or MCP server)
- **Choice**: opencode Skill `fill-open-periods` orchestrates CLI calls
- **Reason**: Agent (LLM) holds git-log context in memory, formulates good texts from diffs, human confirms. No separate LLM API needed.
- **Considered**: Autonomous batch script with local LLM, MCP server with tool calls
- **Tradeoff**: Interactive (not unattended), token cost for agent context

## 2025-08-21: Retry-with-backoff for transient TCP resets
- **Choice**: `_request_with_retry` wraps all httpx calls with 3 retries, exponential backoff
- **Reason**: WebUntis server rate-limits by IP after many API calls (TCP reset, not HTTP 429)
- **Considered**: No retry, curl_cffi for TLS fingerprinting
- **Tradeoff**: Adds latency on failures; curl_cffi installed as backup but not used (issue was IP-based, not TLS-fingerprint)

## 2026-09-17: `cookies` command removed — browser-harvest kept as manual escape hatch
- **Choice**: Remove the `cookies` TODO-stub command entirely; document the browser cookie-harvest path as a manual fallback instead
- **Reason**: Since `client.login()` (.env credentials) + session cache exist, the harvested-cookies path is obsolete for normal operation; a TODO stub in the help is a broken promise. BUT the harvest path remains valuable as an escape hatch when programmatic login is blocked (temporary lockout / captcha after failed attempts — observed before).
- **Escape hatch (if captcha/lockout strikes)**: log in once in the browser (started via `scripts/brave-debug.sh`), run the recorder (`wu record`), perform any page action, stop it — the recorder writes `recordings/<ts>_spengergasse_webuntis_com_cookies.json` (via CDP `Network.getAllCookies`) at session end. Build `~/.webuntis_session.json` manually from it:
  `{"jsessionid": "<JSESSIONID>", "schoolname": "<schoolname cookie>", "school": "spengergasse", "host": "https://spengergasse.webuntis.com", "savedAt": "<iso>"}`
  — then all CLI commands use the harvested session like a cached login.
- **Tradeoff**: single-session suspicion — using the harvested session in the CLI may invalidate the browser session (or vice versa); browser login itself bypasses captcha, the CLI cannot.
- **Considered**: implementing `cookies` (find newest recordings/*_cookies.json, seed the session cache, masked display + --json)

## 2026-09-16: Person data policy — anonymized tracked files, LOCAL.md on user request
- **Choice**: Keep `HANDOFF.md`/`STATE.md` tracked but anonymized; introduce gitignored `docs/ai/LOCAL.md` as the only file where agents may write student names/IDs, and only on explicit user request
- **Reason**: Repo is public; past exposures of student names/IDs accepted as uncritical, but no new person data may be committed. No git-history rewrite.
- **Considered**: Untracking HANDOFF/STATE entirely; full history rewrite (filter-repo)
- **Tradeoff**: Old person data remains in git history (accepted); agents must actively route person data to LOCAL.md

## 2026-09-21: Domain-CLI (harter Schnitt, alles deutsch)
- **Choice**: Befehle heißen `klasse`, `lesson`, `student`, `lehrer`,
  `offen`, `raum`, `intern` — alte Namen (`students`, `lessons`,
  `lehrstoff`, `absences`, `kv`, …) ersatzlos gestrichen, keine Aliase.
  Eine Lesson wird immer als `KLASSE/FACH` adressiert
  (z.B. `3AHWII/SWP1x`). Lehrstoff ist Unterbefehl von `lesson`,
  Absenzen stehen in `lesson` (fehlt/gehalten je Schüler) und im
  `student`-Detail. `offen` ist die Top-Level-Arbeitsvorratssicht
  offener Perioden; `student` (Detail) und `lehrer` (Steckbrief +
  KV-Klassen) sind die Namenssuche. `intern`
  (login/logout/session/record/rpc/rest) ist aus der Hilfe versteckt
  (`help=SUPPRESS`), bleibt aber als Escape-Hatch funktionsfähig.
  (Das ursprünglich englische `search` wurde am 2026-09-23 durch
  `lehrer` bzw. die eingebettete Suche in `student`/`klasse` ersetzt.)
- **Reason**: Domain-Objekte (Klasse, Lesson, Student) statt
  Endpoint-Namen; WebUntis ist DACH-only → UI deutsch.
- **Considered**: Alias-Modell (abgelehnt — zwei Namenswelten),
  nur-Hilfe-ohne-Umbau (abgelehnt — löst Singular/Plural-Chaos nicht)
- **Tradeoff**: bricht alle bestehenden Aufrufe/Notizen/Skripte sofort —
  Migrationsliste alt→neu in README pflegen; Skill synchron migrieren
- **Scope**: UI (Hilfe, Meldungen, Befehls-/Optionsnamen) deutsch;
  JSON-Keys bleiben englisch (Skill-Parsing), interner Code englisch

## 2026-09-21: Lesson-Enumeration aus dem Stundenplan (nicht open-periods)
- **Choice**: `klasse … faecher`, `student` und der `lesson KLASSE/FACH`-
  Resolver enumerieren Lessons primär aus dem KLASSEN-STUNDENPLAN
  (`GET rest/view/v1/timetable/entries`, resourceType=CLASS, eine Woche
  um das Referenzdatum mit Nachbarwochen-Fallback). lsId nur im
  Einzelfall per `GET v2/calendar-entry/detail` (`lesson.lessonId` =
  Matrix-lsId, verifiziert). `open-periods` bleibt nur für Offen-Status,
  Arbeitsvorrat (`offen …`) und als Resolver-FALLBACK (heute−7/+13),
  wenn der Plan nicht ladbar ist. `student` ohne Matrix-Call
  (2 Plan-Calls, Join Klasse×Schüler), Absenzen opt-in via
  `--absenzen` (nur EIGENE Lessons via MY_TIMETABLE, da die Matrix
  rechte-beschränkt ist); `belegt` = eingeschrieben (Fach im
  Schüler-Plan), Anwesenheit irrelevant. Parallele Gruppen desselben
  Fachs (POS1_3BAIF_1/2/3) werden per Primary-Lehrer getrennt, eigene
  Lessons per Slot-Match markiert (MY_TIMETABLE anonymisiert die
  eigene Lehrerposition).
- **Reason**: open-periods kennt nur OPEN-Filter — erledigte Lessons
  fehlten (WMC_1 verschwand aus `student`, Unterzählung der Absenzen);
  10–12 Matrix-Calls pro Schüler wurden vom Nutzer explizit abgelehnt.
- **Considered**: open-periods-Enumeration belassen (abgelehnt — lückig),
  lsId-Spalten in Listen (abgelehnt — 10–12 Detail-Calls), Voll-Scan
  über Matrizen (abgelehnt)
- **Tradeoff**: Stundenplan-Quelle braucht 2–3 leichte Calls statt 1
  open-periods-Call; Ferien-Fenster-Fallback nötig

## 2026-09-21: Absenz-Write-Workflow (setzen/löschen) an der Lesson
- **Choice**: `lesson K/F absenzen eintragen|entfernen` (Testlauf-Standard,
  Block-Standard, `--kein-block` nur mit --termin-id) implementieren;
  `absenzen zeigen --termin-id` listet echte Absenz-Einträge
  (classregpage-ViewModel) als Discovery. `raum suchen|groesse` nur als
  verdrahtete Stubs (Exit 3) — Endpunkte (rooms/form mit capacity,
  ROOM-entries) sind dokumentiert, echte Freie-Raum-Suche ist
  Folgeissue.
- **Reason**: Nutzer-Anforderung nach dem CDP-Recording (Setzen/Löschen
  einer Abwesenheit wurde manuell aufgezeichnet und reverse-engineered);
  Raumsuche explizit Zukunftsmusik, aber Vokabular soll reserviert sein.
- **Considered**: Absenz-Write unter `student` (abgelehnt — Abwesenheit
  ist (Schüler × Termin einer Lesson), gehört zur Lesson-Adresse);
  Raumbefehle ganz weglassen (abgelehnt — Nutzer will CLI-Nutzen später)
- **Tradeoff**: zwei .do-CSRF-Flows (classregpage + absencedlg mit
  frischem Token pro GET) — dokumentiert und getestet

## 2026-09-21: Doku anonymisiert — Platzhalter-IDs, keine echten Werte
- **Choice**: API-Referenz (WEBUNTIS_API.md) mit Schablone je Endpunkt;
  Beispiele NUR mit Platzhaltern (`CLASS_ID`, `STUDENT_ID`, `LESSON_ID`,
  `PERIOD_ID`, `ABSENCE_ID`, `ROOM_ID`) bzw. offenkundig fiktiven Namen
  (Erika Musterfrau, 5XZY) — KEINE echten IDs mehr in neuen
  Dokumentations-Abschnitten (alt-committede lsId/classId-Beispiele
  bleiben unverändert stehen). Hinweis, dass Live-IDs per CLI in
  Sekunden erhältlich sind.
- **Reason**: Nutzer-Vorgabe („keine echten IDs und keine echten
  Personennamen, weil das verboten ist"); lsIds/classIds sind zwar laut
  CONVENTIONS erlaubt, die strengere Regel gewinnt.
- **Considered**: echte IDs weiterhin erlauben (abgelehnt)
- **Tradeoff**: Beispiele sind nicht 1:1 reproduzierbar — Weg zu
  Live-IDs ist je dokumentiert

## 2026-09-18: roster falls back to nearest unit and labels the effective date
- **Choice**: `lesson roster` with no unit on the requested date lists the nearest upcoming unit (else last held) instead of erroring; the stdout header then carries the effective date (`3AAIF/WMC_1 (2026-09-22)`), `--json` reports `date` + `requestedDate`
- **Reason**: User always wants a class list (attendance check happens anyway); a mislabeled list would be worse than a substituted one, hence the visible date + stderr note
- **Considered**: Hard error on missing unit (first version); nearest-by-distance with future tie-break (rejected — no date tricks)
- **Tradeoff**: Pasted lists may cover a different day than requested — mitigated by the visible effective date

## 2026-09-21: offen-Zeitraum-Default aus open-periods/meta (Schuljahr bis heute)
- **Choice**: `--von/--bis` bei allen `offen`-Befehlen optional; ohne
  Angabe gilt Schuljahr-Start..heute aus `GET open-periods/meta`
  (`schoolYear.start`, Ende auf heute gedeckelt — UI-Semantik der
  /open-periods-Schuljahr-Ansicht, per CDP-Mitschnitt verifiziert:
  OnLoad heute..heute, Schuljahr-Wahl Start..heute, Zukunft nie offen).
  Halb angegeben (nur eins) ist Usage-Fehler (Exit 2); der Default wird
  nach stderr gemeldet. Neuer Client-Call `get_open_periods_meta()`.
- **Reason**: Nutzer-Vorgabe („Standardmäßig immer das gesamte
  Schuljahr"); Meta statt Schuljahr-Range aus getSchoolyears, weil die
  UI exakt diese Quelle nutzt.
- **Considered**: --von/--bis weiter Pflicht (abgelehnt — Reibung im
  Standard-Workflow); Default Schuljahr-Start..Schuljahr-Ende
  (abgelehnt — Zukunft ist nie offen, UI kappt bei heute)
- **Tradeoff**: ein zusätzlicher Meta-Call pro offen-Aufruf ohne
  Zeitraum; Meta-Ausfall ohne expliziten Zeitraum wirft ServerError
  statt zu raten

## 2026-09-23: Exit-Code-Taxonomie + typisierte Fehler (`errors.py`)
- **Choice**: `errors.py` definiert `WuError` (+ `UsageError`,
  `NotFoundError`, `AuthError`, `NetworkError`, `ServerError`,
  `NotImplementedYet`, `ConfigError`, `UnexpectedError`), jeder mit
  eigenem `exit_code` (2–9). `classify_exit()` läuft die
  `__cause__`/`__context__`-Kette ab, damit in Meldungstext gewrappte
  Fehler ihren Root-Typ behalten. Der Client übersetzt
  `httpx.TransportError`→NetworkError und klassifiziert via
  `_check_status()` (401/403→Auth, 404→NotFound, 5xx→Server);
  JSON-RPC-Fehler→ServerError. `cli.main()` ist der EINZIGE
  Exit-Punkt (catch `WuError`/`UsageError`, `ModuleNotFoundError`→8,
  `KeyboardInterrupt`→130, Rest→9 mit Traceback). Codes: 0 ok, 1 kein
  Befehl, 2 Usage (HTTP 400), 3 Not-Found (404), 4 Auth (401/403),
  5 Netzwerk, 6 Server (5xx), 7 nicht implementiert, 8 Konfig/Setup,
  9 unerwartet.
- **Reason**: Nutzer-Vorgabe — ein Nutzungsfehler soll ein
  Verwendungsfehler sein (wie HTTP 400), und bei korrekter Eingabe
  sollen Server-/Netz-/Not-Found-Fehler unterscheidbar sein.
- **Considered**: sysexits (64+) abgelehnt — mappt schlecht auf die
  Kategorien und bricht alle Doku; HTTP-Codes gespiegelt (400/404/…)
  abgelehnt — 500+ überschreitet den Exit-Bereich 0–255.
- **Tradeoff**: ~30 frühere `return 2`-Stellen und einige
  `RuntimeError` wurden auf typisierte Fehler umgestellt; Tests, die
  Exit 2 erwartet haben (UnknownLesson→3, raum-Stub→7), wurden
  angepasst. `WuError` erbt von `RuntimeError`, damit
  Soft-Fail-Handler (`except RuntimeError: print(...)`) unverändert
  greifen.

## 2026-09-23: `search` entfernt — `lehrer` + eingebettete Suche
- **Choice**: Der generische Top-Level-Befehl `search` (samt
  `cli_suche.py` und `_dispatch_*`) wurde entfernt. `student` (Detail)
  und `klasse` (Kandidaten bei Namens-Fehltreffer via
  `search_timetable_tokens`) tragen die Suche jetzt selbst; für den
  einzigen verbleibenden Fall (Lehrer) gibt es den neuen Befehl
  `lehrer NAME` (Kürzel/ID, KV-Klassen). `_find_klasse` schlägt bei
  einem String-Fehltreffer Kandidaten vor und wirft `NotFoundError`
  (Exit 3).
- **Reason**: `search --detail` duplizierte Student-/Klassen-Detail
  bereits; der Befehl war die einzige englische Ausnahme und eine
  zweite Namenswelt. Nutzer-Vorgabe: die Suche in die Subbefehle
  auflösen (oder streichen).
- **Considered**: `search` behalten (abgelehnt — Duplikat), Lehrer-Suche
  ganz streichen (abgelehnt — einzige Lücke).
- **Tradeoff**: bricht Shell-Aliase auf `search`; Migrationshinweis in
  README. `raum suchen` bleibt unberührt (deutsches Verb, kein
  Suchbefehl).

## 2026-09-23: Usage-Fehler drucken die volle Unterbefehl-Hilfe
- **Choice**: `_HelpfulParser` (Basis ALLER Parser, Subparser erben via
  `parser_class=type(self)`) überschreibt `error()` → volle Hilfe nach
  stderr, danach die Fehlerzeile (Hilfe zuerst, Fehler zuletzt).
  `usage_error(args, …)` tut dasselbe für handgeschriebene
  Argument-Prüfungen und nutzt `args._parser` (via `_attach_parsers`
  rekursiv an jeden Subparser gehängt). Beide werfen `UsageError`
  (Exit 2); `main()` rendert zentral. Kein Befehl (`wu`) druckt die
  Top-Hilfe und liefert den dokumentierten Exit 1.
- **Reason**: Nutzer-Vorgabe — ein Verwendungsfehler soll dieselbe
  Ausgabe zeigen wie `-h`, mit konsistenter Position der Fehlerzeile.
- **Considered**: nur die „kein Befehl“-Fälle (abgelehnt — inkonsistent),
  Fehlerzeile oben (abgelehnt — Nutzer wollte sie unten).
- **Tradeoff**: jede Fehleingabe druckt jetzt die volle Hilfe (gewollt).

## 2026-09-23: Alle Writes testlauf-Standard (`--testlauf`/`--ausfuehren`)
- **Choice**: Jeder Befehl, der WebUntis-Daten schreibt, hat
  `--testlauf` (Standard: nur zeigen, kein Write) und schreibt nur mit
  `--ausfuehren`. Nachgerüstet: `lesson lehrstoff eintragen`,
  `lesson absenzen pruefen`, `offen eintragen`, `offen pruefen`
  (die übrigen Writes hatten den Schalter bereits). Ausgenommen:
  `intern rpc`/`intern rest` (bewusst schreibfähiger Roh-Passthrough,
  Variante B — JSON-RPC ist auch für Reads POST, Methoden-Gating wäre
  falsch) und `intern login/logout` (nur Session-Cache, keine
  WebUntis-Daten).
- **Reason**: Nutzer-Vorgabe — keine versehentlichen Daten im System;
  ein versehentlicher Write soll ohne explizites `--ausfuehren`
  unmöglich sein. Deckt sich mit der bereits dokumentierten
  Man-Page-Aussage (die zuvor für `offen eintragen`/`offen pruefen`
  eine Ausnahme nannte).
- **Considered**: `offen eintragen`/`offen pruefen` als bereits
  menschlich bestätigten Schritt ohne Schalter lassen (abgelehnt —
  Inkonsistenz und Restrisiko); `intern` ebenfalls gaten (abgelehnt —
  Diagnose-Passthroughs wären unbrauchbar).
- **Tradeoff**: Workflows/Skill/README müssen `--ausfuehren` ergänzen;
  Testlauf-Ausgaben der vier Befehle sind neu (JSON-Plan bzw.
  TESTLAUF-Zeile).

## 2026-09-23: Git-Nutzung nicht mehr reglementiert (AGENTS.md)
- **Choice**: Die Anweisung „Do NOT run `git` commands unless the user
  asks you to commit" wurde aus `AGENTS.md` entfernt; jeder Agent
  entscheidet selbst über Git. Die `recordings/`-Gitignore-Notiz bleibt.
- **Reason**: Nutzer-Vorgabe.

## 2026-09-24: Fach-Match nur in EINE Richtung (Query ist Kürzung)
- **Choice**: `_subject_matches` (Lesson-Resolver) matcht nur noch
  exakt (case-insensitiv) ODER Subject beginnt mit der Query
  (`pmm` → `PMMx`). Die Rückrichtung (`n.startswith(s)`) wurde entfernt:
  eine längere/präzisere Query darf ein kürzeres Sammel-Fach NICHT
  treffen (`pmmx` matchte fälschlich `PMM` als „mehrdeutig").
- **Reason**: Nutzer-Beobachtung `wu lesson 4ahwit/pmmx` — zwei
  Kandidaten (`PMM`, `PMMx`), obwohl `pmmx` eindeutig `PMMx` meint.
- **Considered**: Exact-Priority zusätzlich (exakter Treffer schlägt
  Präfix) — abgelehnt, Nutzer wollte nur die Richtung korrigiert;
  Exact-only (abgelehnt — verliert Abkürzungen wie `WMC` → `WMC_1`).
- **Tradeoff**: `pmm` bleibt bewusst mehrdeutig zwischen `PMM` und
  `PMMx` (Warnung + eigene/nahe Lesson); Abkürzung ist weiter erlaubt.

## 2026-09-24: `student` default kurz, Details mit `--details`
- **Choice**: `wu student NAME` liefert standardmäßig nur die
  Trefferliste (schnell, keine Detail-Calls). Der Detailblock (Klasse,
  KV, belegte/nicht belegte Lessons, ggf. Absenzen) erscheint nur mit
  `--details`; `--absenzen` impliziert `--details`. Gilt für Text UND
  `--json` (`details` nur bei `--details`).
- **Reason**: Nutzer-Vorgabe — Default soll schnell sein und wenige
  API-Calls brauchen; Details nur bei Bedarf.
- **Considered**: Details in `--json` immer liefern (abgelehnt —
  inkonsistent, spart keine Calls); `--absenzen` ohne `--details`
  als Usage-Fehler (abgelehnt — bricht bestehende Aufrufe).
- **Tradeoff**: Bestehende Skripte, die ohne `--details` auf den
  Detailblock setzten, müssen `--details` ergänzen; spart pro Treffer
  ~4 API-Calls (`_kv_info` + `_faecher_aus_plaenen`).

## 2026-09-27: `klasse`-Default kurz + klassen-id immer im Kopf
- **Choice**: `wu klasse KLASSE` (ohne Unterbefehl) zeigt standardmäßig
  nur den Kopf: Klassenname, `klassen-id` (der Wert für
  `--klassen-id`) und KV. Fächer und Roster erscheinen nur mit
  `--details`; `--fach` impliziert `--details`. `--json` liefert den Kopf
  (`class`/`classId`/`longName`/`kv`) immer, `range`/`lessons`/`students`
  nur mit `--details`.
- **Reason**: Nutzer-Vorgabe — die class-id wird fürs Aufnehmen
  gebraucht, war aber aus der Textausgabe nicht ermittelbar; Roster/
  Fächer sind selten nötig und kosteten Plan-/Overview-Calls.
- **Considered**: class-id nur per `--json`/`intern` (abgelehnt — der
  Nutzer will sie im normalen Aufruf sehen); KV ebenfalls hinter
  `--details` (abgelehnt — KV gehört laut Nutzer zum „Kopf").
- **Tradeoff**: bestehende Skripte, die `klasse --json` auf `lessons`/
  `students` setzten, brauchen `--details`; Default spart die
  Stundenplan- und Overview-Calls.

## 2026-09-27: `--klassen-id` bei `aufnehmen`/`anpassen` optional (Ableitung)
- **Choice**: `lesson … aufnehmen/anpassen` leitet die Heimatklasse
  automatisch aus der Matrix ab (`lessonKlassen`; Fallback: Klassen der
  anwesenden Schüler), wenn `--klassen-id` fehlt. `--klassen-id`
  überschreibt weiterhin. `_build_students_payload` nimmt jetzt eine
  Menge `class_ids`. Die abgeleitete ID wird nach stderr gemeldet; ist
  nichts ableitbar, warnt der Befehl und es bleiben nur Anwesende.
- **Reason**: Nutzer-Beispiel `wu lesson --lsid X aufnehmen
  --schueler-name …` scheiterte an der Pflicht `--klassen-id`, obwohl
  die Information in der Lesson-Matrix steckt.
- **Considered**: `--klassen-id` Pflicht lassen und nur `klasse` die ID
  zeigen (abgelehnt — der Nutzer will den Aufruf ohne Zusatzflag);
  `allKlassen` als Primärquelle (abgelehnt — das sind ALLE Klassen der
  Schule, `lessonKlassen` ist die Lesson-Menge).
- **Tradeoff**: `lessonKlassen`-Form ist aus dem Mitschnitt nicht belegt
  → defensiv (dict/int) plus Attendee-Fallback; Multi-Klassen-Lessons
  werden jetzt korrekt als Menge behandelt.

## 2026-09-27: Text-ID-Labels klein (JSON-Keys unverändert)
- **Choice**: In der menschenlesbaren Ausgabe heißen ID-Bezeichner klein
  und folgen dem Flag (`lsid`, `klassen-id`, `termin-id`, `thema-id`,
  `absenz-id`; `mainstudentgroupid`, `lehrer-id`). JSON-Keys bleiben
  englisch-camelCase (`lsId`, `classId`, …).
- **Reason**: Nutzer-Vorgabe — das Programm druckte `lsId`/`classId`,
  erwartet als Option aber `lsid`/`--klassen-id`; kopierte Bezeichner
  sollen direkt passen.
- **Considered**: auch JSON-Keys kleinschreiben (abgelehnt — bricht das
  `fill-open-periods`-Skill-Parsing und die dokumentierte Entscheidung
  „JSON-Keys bleiben englisch").
- **Tradeoff**: gemischte Konvention (Text klein, JSON camelCase) ist
  bewusst und in CONVENTIONS.md/man/wu.1 dokumentiert.

## 2026-09-27: `aufnehmen` löst Namen über `_resolve_schueler` auf
- **Choice**: `lesson … aufnehmen` löst `--schueler-name`/`--schueler-id`
  über `_resolve_schueler` (students/overview, volle Namen, tokenisierendes
  AND) auf — derselbe Resolver wie `student` und `absenzen eintragen`.
  Die frühere Substring-Suche in den Matrix-`allStudents` entfällt.
- **Reason**: Bug — die Matrix-Namen sind verkürzt/umgedreht
  (`"Khalil Amm"`), sodass `--schueler-name "ammar khalil"` 0 Treffer
  lieferte, obwohl `wu student` den Schüler eindeutig fand. Wer per
  `student` genau einen Treffer hat, muss ihn auch aufnehmen können.
- **Considered**: Token-Match gegen Matrix-`allStudents` gejoint mit
  Overview-Vollnamen (abgelehnt — mehr Code/Pfade; `aufnehmen` betrifft
  aktuelle Schüler, für die `students/overview` die maßgebliche Quelle ist).
- **Tradeoff**: `summary["student"]` hat jetzt die Overview-Form
  (`{id,name,class}`) statt der Matrix-Form; Ex-Schüler aus früheren
  Schuljahren sind über `aufnehmen` nicht mehr per Name auflösbar (wie
  bei `student` ohne `--alle-jahre`).




