# Pitfalls

Things that do not work, subtle bugs, and non-obvious constraints.
Read this file carefully before making changes in affected areas.

## API / WebUntis

- **TCP reset after many API calls**: WebUntis rate-limits by IP on TCP level (not HTTP 429). After ~50 rapid calls, new connections get reset. Solution: `--pause 1.0` between PUTs, retry-with-backoff in client. Blockade clears after ~30-60 seconds.
- **Login response is 302 in BOTH cases**: `j_spring_security_check`
  redirects to `/WebUntis/` on success AND on failure (a failed login
  still sets a fresh, anonymous JSESSIONID). The 302 is NOT a success
  signal — verify via the `"anonymousMode":true|false` marker on the
  SPA bootstrap page (`GET /WebUntis/`), as implemented in
  `client.login()`. See docs/WEBUNTIS_API.md § login.
- **httpx cookie iteration**: `self.http.cookies` yields strings, not Cookie objects. Use `self.http.cookies.jar` to get Cookie objects with `.name`/`.value`.
- **topicId can be None**: Some periods have no existing topic row (`topic: null` in getLessonTopic response). Send `id: 0` in PUT to create new.
- **open-periods fields can be JSON `null`, not just missing**: `period.subject` (reine Absenzenprüfung ohne Fach), `period.classes`, `period.teachers`, `period.rooms`, `period.dtRange` und `periods` selbst können `null` sein. `dict.get(k, default)` greift NUR bei fehlendem Key — bei `null` liefert es `None` und der Folge-`.get(...)` crasht. Raw-Perioden deshalb immer via `or {}` / `or []` absichern (`PeriodFields.from_raw`, `_open_period_entries`, `_period_summary`).
- **Block auto-update**: One PUT updates ALL periods with the same `lsId` (lesson block). Don't send separate PUTs for block partners.
- **JWT expiry ~15 min**: Must refresh before each batch. Client caches JWT and refreshes 60s before expiry.
- **School-Year-Id**: Not constant. Derive from `getSchoolyears()` REST
  endpoint (matches date range). NO arithmetic fallback — ids are not
  derivable (21 = 2025/26, 24 = 2026/27, gap exists); when no date
  range matches, `resolve_schoolyear_id()` raises instead of guessing.
   Override with `--schuljahr-id`.

## Git-Log Analysis

- **Class name case sensitivity**: WebUntis returns UPPERCASE class names (`5AHWII`), but git folders are lowercase (`5ahwii/`). Always `.lower()` before git pathspec.
- **Folder name `3HWII` vs `3AHWII`**: GRG-SWP has a `3HWII/` folder (next year's planning) that is NOT the same as `3ahwii/` (current year's class). The `3ahwii` SWP content is actually in GRG-CS (C# OOP), not GRG-SWP.
- **POS-Theorie has no per-lesson commits**: GRG-POSTHEORIE uses PDF folien (Folien_WS/Folien_SS), not dated folders. Derive topics from folien sequence + README + parallel classes. GRG teaches ONLY the Theorie module of POS (2 h/Woche-Block; Java-Praxis 5 h unterrichten ANDERE Lehrer — dazu gibt es keinen GRG-Content, s. DOMAIN.md § POS-Modulstruktur).
- **Lektionsbeschreibung steckt NICHT in der Matrix**: `lessonSubject` ist nur der Fach-Name; die Beschreibung (Modul-Marker wie "Graphentheorie") steht im classregpage-ViewModel `period.lesson.text` — via `lesson K/F absenzen zeigen --termin-id <id>` (JSON: `lessonText`) lesbar.
- **3BAIF POS1 has no repo**: 3baif is not in any GRG-* repo. Derive from parallel classes (4baif, 6acif in GRG-POSTHEORIE) or PDF folien.
- **February name change boundary**: For dates near February, search BOTH pre- and post-change folder names (e.g. both `3aaif/` and `4aaif/`).
- **Split class folders**: `5ahwii_X/` and `5ahwii_Y/` — must search all `_X/_Y/_Z` variants, not just `5ahwii/`.

## CLI / Shell

- **UTF-8 in --text arg**: Bash mangles Umlaute ("HÜ" → "HUe") when passing via `--text "..."`. Use `--text-datei <path>` or `offen eintragen --datei <json>` instead.
- **.env key names**: `.env` may use short keys (`user`, `password`) or full keys (`WEBUNTIS_USER`). `_load_env()` maps short→full via aliases dict.
- **argparse subparser defaults overwrite globals**: a subparser `--schuljahr-id` with `default=None` wipes a globally given value when the flag is absent after the subcommand. Subparser copies must use `default=argparse.SUPPRESS` so only an explicit flag overwrites.
- **argparse `nargs="?"` positional loses against subparsers**: ein optionales Positionsargument vor Subparsern wird als Unterbefehl gedeutet (1 Token) bzw. frisst den Sub (2 Token). Daher wird `KLASSE/FACH` in `main()` vorab extrahiert (`_extract_adresse`: erstes `/`-haltiges Positions-Token außerhalb von Options-Werten) — kein Positionsargument in argparse, dafür explizite `usage=`-Zeile.

## Recorder

- **Brave-Debug-Rauschen ist kein Recorder-Fehler**: `[OpenH264]`- und
  `puffin ... Operation not permitted`-Meldungen stammen aus Brave
  selbst (Codec/Sandbox des Component-Updaters) — der Recorder fährt
  sauber herunter, wenn er Cookies erntet
  (`harvesting cookies … done`). Echte Recorder-Fehler stünden in
  `[recorder]`-Zeilen.

- **Response body capture**: `Network.getResponseBody` must be called AFTER `Network.loadingFinished` (not after `responseReceived`). The body isn't available until loading completes.
- **No console output file**: If the page doesn't use `console.*`, no `_console.jsonl` is created. This is normal, not a bug.
- **Brave must be started with debug port**: `scripts/brave-debug.sh` starts Brave with `--remote-debugging-port=9222`. If Brave is already running without the port, the recorder can't attach.

## Absences

- **CSRF token required**: The absence-check POST needs a `_csrf` token that must be fetched per-period from `GET classregpage.do` (HTML hidden field). Cannot be reused across periods.
- **No JWT for absences**: The `classregpage.do` endpoint uses session cookie + CSRF, not Bearer JWT. Different from the lesson-topic REST endpoints.
- **Block partner auto-marked**: One POST marks both periods in the block (response contains `args:[[periodId, blockPartnerId]]`).
- **X-CSRF-TOKEN header + _csrf body**: Both must carry a valid token. Live observation (2026-09-21): the header may carry a session-level token while the body carries the per-GET token — replaying the per-GET token in BOTH places works (proven by `check_absences`).
- **absencedlg CSRF is per-GET FRESH**: two consecutive `GET absencedlg.do` calls return DIFFERENT `_csrf` values; the delete POST must carry exactly the token of the immediately preceding dialog GET.
- **Zwei selId-Namensräume**: `classregpage.do insert=insert&selId=` trägt die SCHÜLER-ID, `absencedlg.do selId=` die ABSenz-ID. Nie vermischen.
- **Absenz-Record ≠ Matrix-Anwesenheit**: Eine eingetragene Abwesenheit (classregpage) ändert `attendedPeriods` (Matrix) NICHT — zwei getrennte Systeme.
- **delete_absence braucht die Zeiten**: Der POST verlangt `abStartTime/abEndTime/startDate/endDate/startTime/endTime` aus der absenceRow (Ints HHMM/YYYYMMDD) — ohne Zeilen-Lookup (viewModel.absenceRows) ist keine Löschung möglich.
- **Open-only-Falle (historisch, 2026-09-21 gefixt)**: `open-periods`
  kennt nur `TOPIC_OR_ABSENCE_OPEN/ABSENCE_OPEN/TOPIC_OPEN` — erledigte
  Lessons FEHLEN. Lesson-Enumeration daher primär aus dem
  Klassen-Stundenplan; open-periods nur noch für Offen-Status
  (`klasse faecher`), Arbeitsvorrat (`offen …`) und als Resolver- FALLBACK
  (Fenster heute−7/+13), wenn der Plan nicht ladbar ist.
- **Lesson-Adressierung außerhalb der Plan-Woche**: Resolver lädt die
  Woche um --datum (± Nachbarwochen-Fallback). Für exotische Daten
  ( weit außerhalb, Ferien) bleibt `--lsid` der Ausweg.

## Timetable / Stundenpläne

- **entries.ids sind PERIODEN-IDs, keine lsId**: Der Stundenplan-Endpunkt trägt keine Lesson-ID. lsId nur via `calendar-entry/detail` (`lesson.lessonId` = Matrix-lsId, verifiziert 2026-09-21) oder aus dem classregpage-ViewModel (`lessonId`).
- **Positions-Felder sind nicht fest numeriert**: `position1..7` sind je nach resourceType anders belegt (Klassen-Plan: Klasse in `day.resource`, position4=null; Schüler-Plan: Klasse in position4; Raum-Plan: Klasse in position1). Immer über das `type`-Feld jedes Elements klassifizieren, nie über die Positionsnummer.
- **Parallele Gruppen desselben Fachs in EINER Klasse existieren**: z.B. POS1_3BAIF_1/2/3 — gleiches Fach-Kürzel, gleiche Klasse, VERSCHIEDENE lsIds/Lehrer (Team-Teilung); Schüler können alle besuchen (Team-Unterricht) oder genau eine (E1x/E1y-Gruppenwahl). Gruppierung deshalb nach (Klasse, Fach, Primary-Lehrer): ein Entry gehört zur Gruppe, deren Primary in seinem Lehrer-Set steht — Ko-Lehrer-Variation innerhalb EINER lsId (EDJ vs. EDJ+WES) splittet dann NICHT, disjunkte Lehrer-Sets (parallele Gruppen) schon.
- **MY_TIMETABLE/TEACHER-Plan anonymisiert die eigene Lehrerposition**: position1 trägt nur die KO-Lehrer (WMC_1 zeigte nur LEA, POS1 gar keinen Lehrer) — der eigene Short fehlt. Lehrer-basiertes Matching der eigenen Lessons ist unmöglich; eigen-Markierung daher per SLOT-Match (mein (Fach, Datum, Start) liegt in der Gruppen-Entry).
- **Die Matrix ist RECHTE-BESCHRÄNKT**: fremde lsIds (andere Lehrer derselben Klasse, verifiziert 2026-09-21) melden `code 0: Internal server error` — nicht nur unbekannte lsIds! Der Resolver bevorzugt bei Mehrdeutigkeit deshalb die eigene Lesson (Slot-Match gegen MY_TIMETABLE).
- ** Eine Woche genügt zur Lesson-Enumeration** (Lessons laufen übers Semester), aber Ferienwochen sind leer — Fallback auf Nachbarwochen (max. 4 probieren), wie bei der KV-Auflösung.
- **filter?resourceType=STUDENT ist ~1,5 MB**: Schüler-Filter-Liste nur sparsam rufen; Schüler-Pläne besser direkt per bekannter STUDENT_ID (entries ist klein).
- **ROOM-Plan kann NO_DATA liefern**: Räume ohne Stundenplan (z.B. Funktionsräume) antworten mit leeren days/`status: NO_DATA` — keine Fehler, einfach leer.
- **`availability` in rooms/form ist SEMANTISCH UNGEKLÄRT**: beide aufgenommenen Slots lieferten für ALLE Räume `NONE` — für Freie-Raum-Suche nicht verwendbar; Belegung aus ROOM-entries ableiten.
- **ViewModel-JSON in .do-Seiten ist HTML-escaped**: `data-dojo-props="viewModel: {&quot;…}"` — erst `html.unescape`, dann `raw_decode` ab `viewModel: ` (genau ein Objekt, robust gegen folgendes Markup). Reihenfolge beim Escaping beachten: `&` vor `"`.

## Class Register / Students

- **Timetable search matches no multi-word phrases**: `q="<Vorname Nachname>"`
  returns [], while the single tokens hit (teacher Kürzel, student
  `<Nachname><Vorname[:3]>`). Always tokenize (see `search_timetable_tokens()`,
   CLI `student --wortteile` / `lehrer --wortteile`) instead of trusting
  the exact phrase.
- **Student displayNames are anonymized** (last name only); the first
  name survives only in `shortName` (`<lastname><firstname[:3]>`) and in
  `students/overview` (`firstName`/`lastName`).
  The shortname pattern is a heuristic — always flag it
  (`searchNote: shortname-hint`), never silently.
- **Matrix student names are shortened too** (`allStudents[].name` is
  `"Nachname Vorname"` with the first name cut) — join
   `students/overview` by student id for full names (as `lesson roster`
  does); matrix name is only the fallback for ids missing from overview.
- **Matrix dates are int YYYYMMDD** (`lessonPeriods[].date`,
  `attendedPeriods[]`), while open-periods/dtRange use ISO strings —
  convert explicitly when comparing (`int(day.replace("-", ""))`).
- **Former students vanish from current-year search**: timetable/search
  is schoolyear-sensitive (a student id may exist in an older SJ and be
  gone in the current one),
  while `students/overview` always returns the CURRENT roster. Year
  fallback must therefore use timetable/search per year (max ~3 older
  years), and every non-current hit must be flagged NICHT AKTUELL
   (`current: false`). Only `student` falls back automatically;
  everything else keeps the current-year default.
- **Unknown lsIds report as `code 0: Internal server error`**: a bogus
  lsId in `getStudentLessonPeriodMatrix` (verified with 1, 22288,
  999999999 in every schoolyear) does NOT yield "not found" — the
  server answers with a generic internal error. DASSELBE gilt für
  RECHTE-fremde lsIds (Lesson eines anderen Lehrers derselben Klasse,
  verifiziert 2026-09-21)! `Client` therefore maps
  exactly that signature to `UnknownLessonError` (lsId + schoolyear in
  the message, findings hint included); `cli.main()` catches it
  centrally (stderr + exit 3 (NotFound), no traceback) for all matrix
  consumers (`lesson matrix/aufnehmen/anpassen/roster`, `lesson info`).
  Other RuntimeErrors pass through unwrapped — do NOT broaden the match.
- **Fremde Lehrer-Stundenpläne sind nicht lesbar**: Public-Endpoint
  mit elementType=2/Lehrer-ID → 403 (`no right for anonymous user`);
  JSON-RPC `getTimetable` (Typ 2) → Code -8520 (`not authenticated`).
  Der `lehrer`-Befehl zeigt daher Steckbrief + KV-Klassen (aus
  `getKlassen` teacher1/2/3-Match), keinen Wochenplan.
- **Student lists are admin-only**: `getStudents` (JSON-RPC) returns 0 and
  `/api/rest/view/v1/students` returns 500 for teacher accounts. Use
  `lessonstudentlist.do?lsid=X` (lesson participant page) to obtain
  student ids of a class, or `students/overview` for class ids only.
- **The class register is a legacy JSP app in an iframe** (`embedded.do#...`),
  NOT part of the SPA. Its routes (`lessonstudentlist.do`,
  `classregpage.do`) are NOT in the SPA bundles — hash routes are mapped
  in `webuntis-embedded/main.js` on the Dojo CDN.
- **Dojo CDN needs Referer**: `https://content.webuntis.com/WebUntis/static/...`
  returns 403 without `Referer: {host}/WebUntis/embedded.do`.
- **`ajaxCommand` params on `.do` pages are ignored** (server returns the
  full page regardless) — except the ones actually wired server-side
  (e.g. `getEmails` used as TitlePane href).
- **Schoolyear ids change every year** (21 = 2025/26, 24 = 2026/27 — gap
  exists). Always resolve dynamically via schoolyears date-range match.
- **`setSchoolyear` accepts invalid schoolyear ids silently**: passing
  a non-existent id (e.g. 999999) to the jsonrpc_web `setSchoolyear`
  call does NOT fail — the server just accepts it. Don't rely on it
  for validation.
- **Teilnehmer-Payload muss die VOLLE Edit-Semantik-Liste sein**: bereits
  anwesende Schüler aus dem `students`-Array (Wire-Format, englisch) zu
  streichen meldet sie ab. Immer via `_build_students_payload()` bauen
  (Klassen-Roster + alle Anwesenden jeder Klasse bleiben).
- **Heimatklasse der Lesson-Payload**: `_build_students_payload` braucht die
  Klassen-Menge der Lesson; ohne `--klassen-id` leitet
  `_lesson_class_ids()` sie aus `lessonKlassen` der Matrix ab (Fallback:
  Klassen der Anwesenden). Die Form von `lessonKlassen` (Liste von
  `{id,…}` oder IDs) ist noch nicht per Mitschnitt belegt — defensiv lesen.
- **UI-Schuljahr-Ansicht endet heute**: Die /open-periods-Ansicht
  „gesamtes Schuljahr" sendet `schoolYear.start`..heute (nie
  Schuljahr-Ende) — Zukunft ist per Definition nie offen. Der
  `offen`-Schuljahr-Default bildet exakt das ab (s. DECISIONS.md).

## Privacy

- **Tracked knowledge files are public**: HANDOFF.md/STATE.md/PITFALLS.md
  are committed to a public repo and history is NEVER rewritten — a
  student name or student id written here is permanently exposed. Write
  person data ONLY to gitignored `docs/ai/LOCAL.md`, and ONLY on explicit
  user request. Tracked entries reference it via `[Details: LOCAL.md]`.
- **Allowed in tracked files**: counts, lesson ids (lsId), class ids,
  period ids, subject names. NOT allowed: person names, student ids,
  teacher names/ids, person-linked details.
