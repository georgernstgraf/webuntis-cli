# Domain Knowledge

Business rules and domain relationships not obvious from code.

## Entities

- **Period**: A single school hour (e.g. 13:25–14:15). Has `periodId`, `lsId` (lesson block), `hr` (hour number), `class`, `subject`, `date`, `time`.
- **Lesson Block (lsId)**: A group of periods forming one continuous lesson (e.g. 13:25+14:25 = 2-period block). One PUT updates ALL periods in the block. A "Lesson" (Fach in einer Klasse) can MEHRERE lsIds haben — parallele Gruppen (s.u.).
- **Parallel groups**: Parallele Gruppen desselben Fachs in EINER Klasse (z.B. POS1_3BAIF_1/2/3) sind getrennte lsIds mit eigenem Primary-Lehrer. Zwei Muster: Team-Teilung (alle Schüler besuchen alle Gruppenstunden, Lehrer wechseln sich ab) und Wahl-Gruppen (Schüler besucht genau eine, z.B. E1x/E1y). Der Plan-Join bildet beides korrekt ab; die Matrix ist je lsId rechte-beschränkt (nur eigene lesbar).
- **Topic**: The Lehrstoff (lesson topic) entry for a period. Has `id` (topicId), `periodId`, `text`, `attachments`. May be `null` (no topic row yet → create with `id: 0`).
- **Absence Record**: Echte Abwesenheit im Klassenbuch (classregpage), getrennt von der Matrix-Anwesenheit (`attendedPeriods`): hat eigene `absenceId`, Zeiten, `person`, Entschuldigungsstatus; Write via insert/delete-Flow.
- **Open Period**: A period where the teacher still owes a topic (`topicNeeded=true`) or absence check (`absCheckNeeded=true`). Filter: `TOPIC_OR_ABSENCE_OPEN`.
- **Teacher**: Identified by `person_id` from JWT. Used as `teacherId` in open-periods query.
- **Schoolyear**: Has `id`, `name` (e.g. "2025/2026"), `dateRange` ({start, end}). Current schoolyear id derived from date range match.
- **"belegt" (seit 2026-09-21)**: eingeschrieben = Fach erscheint im Schüler-Stundenplan — Anwesenheit ist KEIN Teil der Definition (immer kranke Schüler bleiben belegt).

## GRG-* Repository Structure

- **GRG-WMC**: Web & Mobile Computing — classes 3aaif, 3akif, 3bkif, 3caif, 4aaif, 4akif, 4bkif, 4caif
- **GRG-SWP**: Softwareentwicklung und Projektmanagement — classes 2ahwii, 3ahwii, 5ahwii (split into _X/_Y)
- **GRG-INFI**: Informatik und Informationssysteme — class 2ahwii
- **GRG-POSTHEORIE**: POS-Theorie (PrOgrammieren und Software) — classes 4baif, 6acif; uses PDF folien not per-lesson folders
- **GRG-JAVA**: Java-Programmierung — class 3aaif
- **GRG-CS**: Computer Science — class 3ahwii (C# OOP, NOT in GRG-SWP despite SWP subject)
- **-T suffix**: Teacher-only companion repo (same classes as main repo)

## Class Name Rules

- **Abteilungs-/Formklassen** (suffix aif, cif, kif): advance year in February (3aaif→4aaif, 3bkif→4bkif)
- **Tagesklassen** (suffix hwii, hwit): keep name across February
- **Split classes**: `5ahwii_X` and `5ahwii_Y` = two groups of the same class, taught separately
- **Cross-repo anomaly**: 3AHWII SWP1x content is in GRG-CS (C#), not GRG-SWP (Deno/TS). The `3HWII/` folder in GRG-SWP is next year's planning.

## WebUntis Subject Mapping

| WebUntis subject | Full name | GRG repos |
|---|---|---|
| POS1/POS | Programmieren und Softwareengineering | GRG-POSTHEORIE, GRG-JAVA |
| SWP1x/SWP1y/SWP1 | Softwareentwicklung und Projektmanagement | GRG-SWP (and GRG-CS for 3AHWII) |
| WMC_1/WMC1 | Webprogrammierung und Mobile Computing | GRG-WMC |
| INFIx/INF | Informatik und Informationssysteme | GRG-INFI |
| CS | Computer Science | GRG-CS |
| PMM/PMMx/PMMy | Prozessmanagement | GRG-PMM, GRG-PMM-T |
| SS | Sprech- & Supplierbereitschaft | (none — skip) |
| BESP | Berufsspezifische Praxis | (none — skip, ask user) |

## Supplierungen (seit 2026-10-12 bekannt)

- **AT-Terminologie: "Supplierung"** (nicht "Vertretung"). Eine
  supplierene Periode erscheint im eigenen Arbeitsvorrat, weil
  open-periods teacher-scoped ist — der supplierende Lehrer steht im
  Klassen-Stundenplan-Block als `ADDED` (Original als `removed`, oder
  `substitutionText` gesetzt).
- **Auch supplierene Perioden verpflichten zur Lehrstoff-Eintragung.**
  Festtext `SUPPLIER_TEXT = "Supplierung"` genügt für so eine Stunde;
  aus den eigenen GRG-Repos ist für eine fremde Klasse nichts ableitbar.
- `offen vorschlag` erkennt Supplierungen automatisch (source
  `"supplier"`) und muss dafür keinen Git-Lookup-Ersatz erfinden.

## Parallelklassen & Folien-Ableitung (seit 2026-10-12 bekannt)

- **3BAIF und 3CAIF laufen "quasi immer gleich auf"** (Nutzer-Vorgabe):
  dieselbe Thematik, versetzte Termine. Ein belegter UE-Ordner der einen
  Klasse (z.B. `3caif/2026-09-23__bipartit`) gilt damit auch für den
  nächstliegenden Termin der Parallelklasse.
- **POS-Theorie-Inhalte kommen chronologisch aus `GRG-POSTHEORIE/
  Folien_WS`** (Wintersemester: Graphentheorie) bzw. `Folien_SS`
  (Sommer) — nach Dateinamen-Nummerierung vorgehen:
  01 Einleitung → 02 Spezielle Graphen → 03 Planare Graphen →
  04 Kantenfolgen/Euler/Hamilton → 05 Eigenschaften → 06 Zusammenhang
  → 07 Matrizen → 08 Bäume → 09 Kirchhoff → 11 Starker Zusammenhang
  → 12 Dijkstra (Thementabelle im README von GRG-POSTHEORIE).
- **4AHWIT PMM: X/Y-Kohorten laufen ebenso gleich auf** (Ordner
  `4ahwit-x`/`4ahwit-y` in GRG-PMM, y meist 3–4 Tage voraus):
  y 25.09 „R-Kennzahlen und Verteilungen" → x 29.09; y 02.10
  „Binomialkoeffizient/Pascalsches Dreieck" → x 06.10.

## POS-Modulstruktur (seit 2026-09-21 bekannt)

POS (Programmieren und Software Engineering) wird in vielen Klassen
**7 Stunden pro Woche** unterrichtet und ist in zwei Module aufgeteilt:

| Modul | Umfang | Lehrer | GRG repo |
|---|---|---|---|
| **Java-Praxis** | 5 h/Woche | andere Lehrer (z.B. EDJ, WES, HOA) | GRG-JAVA — NICHT GRGs Content, keine Lehrstoff-Ableitung möglich |
| **Theorie** | 2 h/Woche (Block) | GRG | GRG-POSTHEORIE (Folien_WS=Graphen, Folien_SS=theoretische Informatik) |

- **Lektionsbeschreibung** = classregpage-ViewModel
  `period.lesson.text` (NICHT in der Matrix/lessonSubject!): sie trägt
  den Modul-Marker — z.B. "Graphentheorie" bzw. "Theorie" für GRGs
  Lessons. Sichtbar via
  `lesson K/F absenzen zeigen --termin-id <id>` (Feld `lessonText`).
- Die **parallelen POS-Gruppen** einer Klasse (`klasse … faecher`,
  z.B. POS1_…_1/2/3) sind die Modul-/Lehrer-Teilung: GRGs 1 Termin
  (2-h-Block) ist das Theorie-Modul, die übrigen (3BAIF: EDJ/WES) sind
  Java-Praxis.
- **open-periods ist teacher-scoped** → GRGs offene POS-Perioden sind
  IMMER Theorie-Lessons. Java-Praxis-Inhalte können nicht aus GRGs
  Repos abgeleitet werden — Repos für eigene POS-Lehrstoffe sind
  GRG-POSTHEORIE(+T); GRG-JAVA(-T) dient nur fremden Jahren/Lehrern.

## Lesson Topic Derivation Priority

1. Git folder names with date prefix (e.g. `2025-10-02_cases_click_images/`) — highest confidence
2. README files with dated entries (e.g. `## 2025-10-06 Tests`)
3. Git diffs (`git show <hash>`) — actual file content
4. PDF folien (POS-Theorie: Folien_WS=Graphen, Folien_SS=Algorithmen)
5. Parallel classes (same subject, same curriculum)
6. Dummy text: `(kein Unterricht gefunden für <class> am <date>)`
