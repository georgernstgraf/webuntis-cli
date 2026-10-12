---
name: fill-open-periods
description: Fill missing WebUntis lesson topics (Lehrstoff) for open periods using GRG-* git history and the webuntis-cli CLI. Use when the user wants to catch up on missing Lehrstoff entries.
---

# fill-open-periods

Automate the "Lehrstoff nachtragen" chore: list WebUntis open periods,
derive a topic text from the corresponding GRG-* teaching repository's
git history, and submit each via the webuntis-cli CLI.

## Prerequisites

- The `webuntis-cli` repo is checked out at
  `~/repos/georgernstgraf/webuntis-cli` with a working `.venv`.
- `.env` is present with `WEBUNTIS_USER` / `WEBUNTIS_PASSWORD` (see
  `.env.example`).
- All GRG-* repos under `~/repos/georgernstgraf/` are pullable.

## Workflow

1. **Run `offen vorschlag`** to fetch all open periods and
   pre-load git commits + diffs in one call:

   ```bash
   cd ~/repos/georgernstgraf/webuntis-cli
   .venv/bin/python -m webuntis_cli.cli offen vorschlag \
       --von 2025-09-01 --bis 2026-07-05
   ```

   This outputs a JSON object with two arrays:

   - `blocks`: one entry per DAY-block (class + subject + one date), each with:
     - `periodId`, `topicId`, `class`, `classId`, `subject`, `date`, `time`
     - `start`, `end` (block ISO timestamps for `lessonDetailsUrl`)
     - `blockPeriods`: list of all periodIds in the day-block
       (same-day block partners — one PUT updates them all)
     - `source`: `"git"` | `"fixed"` | `"supplier"` | `"dummy"` | `"skipped"`
     - `proposedText`: raw text from commit messages (refine this!)
     - `commits`: array of `{repo, hash, date, message, files[], diff}` per commit

   Blocks are DAY-GRANULAR: a year-long lesson (same `lsId` across many
   dates) yields one block per date, with the commits of exactly that
   date. Never reuse one text across dates of the same lesson.

   - `skipped`: periods with unknown subjects that are NOT supplier
     lessons (rare — usually means SUBJECT_REPO_MAP needs the subject)

   Fixed-text subjects (SS="Sprechstunde", BESP="Bewegung und Sport") are
   already filled with their text — no formulation needed.

   **Supplierungen** (`source: "supplier"`, proposedText already
   "Supplierung"): the own teacher appears as ADDED (or the original
   teacher as removed / substitutionText) in the class timetable.
   Supplier lessons REQUIRE a Lehrstoff entry too — the fixed text
   "Supplierung" suffices (Austrian terminology: Supplierung, not
   Vertretung). Do not derive content from git for foreign classes.

2. **Formulate the Lehrstoff text** for each block from:
   - The commit `diff` fields (what was added/changed — e.g. a Prisma
     schema, a regex exercise, a Deno project skeleton).
   - The `files` arrays (subject-area hint, e.g. `Matura-Prisma.md`).
   - The `subject` and `subjectLong` (e.g. `SWP1y` = Softwareentwicklung
     und Projektmanagement, Y-Gruppe) and the `date`.
   - Keep it concise and factual (German, e.g. "Prisma-Schema für
     Matura-Projekt; Deno-Setup; VSCode-Konfiguration" rather than
     raw commit messages like "std; fast commit").
   - The `proposedText` is a rough starting point — improve it.
   - For block partners on the SAME day (same `lsId` + date), use the
     same text — one PUT updates the whole day-block.
   - **POS lessons are the THEORIE module** (POS = 7 h/week: 5 h
     Java-Praxis taught by OTHER teachers + 2 h Theorie by GRG).
     GRG's own POS lessons carry the module marker in the lesson
     description ("Theorie", "Graphentheorie" — check via
     `lesson KLASSE/POS1 absenzen zeigen --termin-id <id>`, JSON field
     `lessonText`). Content source is GRG-POSTHEORIE (Folien_WS =
     Graphen, Folien_SS = theoretische Informatik — NO per-lesson
     commits; derive from folien sequence + README + parallel classes).
     There is NO GRG content for Java-Praxis — never invent it; own
     open POS periods are always theory lessons (open-periods is
     teacher-scoped).
   - **Parallel classes run in lockstep** (user-confirmed): 3BAIF and
     3CAIF cover the same topic with offset dates — a dated UE folder
     of one class applies to the nearest date of the other. Same for
     4AHWIT PMM x/y cohorts (GRG-PMM `4ahwit-x`/`4ahwit-y`, y usually
     3–4 days ahead). POS-Theorie topics follow `Folien_WS`/
     `Folien_SS` file numbering chronologically (README of
     GRG-POSTHEORIE has the topic table).

3. **Present a confirmation table** to the user:

   | periodId | class | subject | date | proposed text |
   |---|---|---|---|---|

   List skipped periods (unknown subjects) at the bottom.

4. **On user confirmation** (bulk "all ok" or per-row edits), write a
   JSON file with the confirmed entries:

   ```json
   [
     {"periodId": 5458590, "topicId": 2296724, "text": "...",
      "classId": 3661, "start": "2026-03-18T13:25:00",
      "end": "2026-03-18T15:15:00", "date": "2026-03-16"},
     ...
   ]
   ```

   Write it to `/tmp/opencode/batch_<timestamp>.json`.

5. **Submit** all entries:

   ```bash
   .venv/bin/python -m webuntis_cli.cli offen eintragen \
       --datei /tmp/opencode/batch_<timestamp>.json --pause 1.0 --ausfuehren
   ```

   - Writes are testlauf-default: without `--ausfuehren` only the batch is
     shown (dry run), nothing is written.
   - One PUT per entry; block partners are auto-updated by the server.
   - `--pause 1.0` avoids triggering IP rate-limiting.
   - `topicId` null → server creates new topic (id=0).
   - `classId`/`start`/`end`/`date` enable `lessonDetailsUrl` output.

6. **Check absences** for all remaining open periods:

   ```bash
   .venv/bin/python -m webuntis_cli.cli offen pruefen \
       --von 2025-09-01 --bis 2026-07-05 --pause 1.5 --ausfuehren
   ```

   - Also testlauf-default: add `--ausfuehren` to actually mark absences
     as checked.

7. **Report** which periods were submitted, failed, or skipped. Include
   `lessonDetailsUrl` from the `batch-set` output for browser verification.
   Add new subjects to `SUBJECT_REPO_MAP` when the user confirms the repo.

## Helper commands

- `offen status --von ... --bis ...` — quick overview (by subject/class)
- `offen verifizieren --von ... --bis ...` — check which periods truly
  have no text vs only missing absence check
- `offen festtexte --von ... --bis ...` — fill SS/BESP only
  (no git-log needed)

## Notes

- The `vorschlag` call replaces the old manual workflow
  (`liste --json` + per-block git lookup). One call does it all.
- Day-blocks (same `lsId` + same date, e.g. double periods) only need
  one PUT.
- Subject repo mapping currently covers POS, SWP, WMC, INF, CS, PMM
  (see `SUBJECT_REPO_MAP` in `src/webuntis_cli/client.py`).
- The `.env` file is gitignored and contains the WebUntis password —
  never print it or commit it.
- `recordings/` contains session cookies — treat as sensitive.
