"""CLI-Einstieg für webuntis-cli (Domain-CLI, s. DECISIONS.md).

Top-Level: klasse, lesson, student, lehrer, offen, intern.
Eine Lesson wird immer als KLASSE/FACH adressiert (z.B. 3AHWII/SWP1x).
"""

from __future__ import annotations

import argparse
import sys
import traceback

from webuntis_cli.cli_intern import (
    cmd_login,
    cmd_logout,
    cmd_rest,
    cmd_rpc,
    cmd_session_status,
)
from webuntis_cli.cli_klasse import (
    cmd_klasse,
    cmd_klasse_faecher,
    cmd_klasse_kv,
    cmd_klasse_roster,
)
from webuntis_cli.cli_common import (
    _add_school_year_arg,
    _date_arg,
    _datum_arg,
    _HelpfulParser,
    _print_help_and_error,
)
from webuntis_cli.errors import (
    ConfigError,
    UnexpectedError,
    UsageError,
    WuError,
    classify_exit,
)
from webuntis_cli.cli_lesson import (
    cmd_absenzen_eintragen,
    cmd_absenzen_entfernen,
    cmd_absenzen_pruefen,
    cmd_absenzen_zeigen,
    cmd_lehrstoff_aus_git,
    cmd_lehrstoff_eintragen,
    cmd_lehrstoff_zeigen,
    cmd_lesson_anpassen,
    cmd_lesson_aufnehmen,
    cmd_lesson_info,
    cmd_lesson_matrix,
    cmd_lesson_roster,
    cmd_lesson_termine,
)
from webuntis_cli.cli_offen import (
    cmd_offen_eintragen,
    cmd_offen_festtexte,
    cmd_offen_liste,
    cmd_offen_pruefen,
    cmd_offen_status,
    cmd_offen_verifizieren,
    cmd_offen_vorschlag,
)
from webuntis_cli.cli_lehrer import cmd_lehrer
from webuntis_cli.cli_raum import cmd_raum_groesse, cmd_raum_suchen
from webuntis_cli.cli_student import cmd_student


def _add_testlauf(sp):
    """--testlauf (Standard) / --ausfuehren (wirklich schreiben)."""
    sp.add_argument("--testlauf", dest="testlauf", action="store_true",
                    default=True,
                    help="nur zeigen/protokollieren, nichts schreiben "
                         "(Standard)")
    sp.add_argument("--ausfuehren", dest="testlauf", action="store_false",
                    help="wirklich schreiben (Write)")


def _add_von_bis(sp, required=True, schuljahr_default=False):
    """Zeitraum --von/--bis (YYYY-MM-DD).

    Mit schuljahr_default=True (nur offen-Befehle): beide optional,
    Default ist Schuljahr-Start..heute aus open-periods/meta.
    """
    h_start = "Zeitraum-Start (JJJJ-MM-TT)"
    h_end = "Zeitraum-Ende (JJJJ-MM-TT)"
    if schuljahr_default:
        h_start += " (Standard: Schuljahr-Start)"
        h_end += " (Standard: heute)"
    sp.add_argument("--von", dest="start", type=_date_arg, required=required,
                    help=h_start)
    sp.add_argument("--bis", dest="end", type=_date_arg, required=required,
                    help=h_end)


def _add_json(sp):
    sp.add_argument("--json", action="store_true",
                    help="strukturierte JSON-Ausgabe (für Weiterverarbeitung)")


_LESSON_VALUE_OPTS = frozenset({
    "--lsid", "--datum", "--klassen-id", "--schueler-id", "--schueler-name",
    "--aufnehmen-id", "--entfernen-id", "--termin-id", "--thema-id",
    "--absenz-id", "--text", "--text-datei", "--ausgabe", "--von", "--bis",
    "--pause", "--datei", "--schuljahr-id",
})


def _extract_adresse(argv: list[str]) -> tuple[list[str], str | None]:
    """KLASSE/FACH-Token aus `lesson ...` entfernen und zurückgeben.

    Nur wenn das Top-Level-Kommando `lesson` ist. Das erste reine
    Positions-Token mit `/` (beidseitig nicht leer) ist die Adresse —
    Unterbefehle enthalten nie `/`, Options-Werte werden übersprungen.
    """
    args = list(argv)
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 1 if "=" in args[i] else 2
    if i >= len(args) or args[i] != "lesson":
        return args, None
    rest = args[:i + 1]
    adresse = None
    j = i + 1
    while j < len(args):
        tok = args[j]
        if tok in _LESSON_VALUE_OPTS:
            rest.append(tok)
            if j + 1 < len(args):
                rest.append(args[j + 1])
            j += 2
            continue
        if not tok.startswith("-") and adresse is None:
            teile = tok.split("/")
            if len(teile) == 2 and all(t.strip() for t in teile):
                adresse = tok
                j += 1
                continue
        rest.append(tok)
        j += 1
    return rest, adresse


def _attach_parsers(parser: argparse.ArgumentParser) -> None:
    """Stamp `_parser` (the owning subparser) onto every subcommand.

    Hand-rolled usage errors (`usage_error`) use it to print the matching
    subcommand help, not the top-level help. Recurses through the tree.
    """
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                child.set_defaults(_parser=child)
                _attach_parsers(child)


def main() -> int:
    p = _HelpfulParser(
        prog="wu",
        description="WebUntis-CLI: Klassenbuch-Arbeit vom Terminal aus — "
                    "Roster, Lehrstoff und Absenzen für den eigenen Unterricht.\n\n"
                    "Domain-Objekte: KLASSE (z.B. 3AHWII), LESSON als "
                    "KLASSE/FACH (z.B. 3AHWII/SWP1x), STUDENT und LEHRER "
                    "per Name.\n"
                    "Alle Ausgaben sind deutsch; --json liefert maschinenlesbare "
                    "Strukturen (Schlüssel englisch).",
        epilog="Beispiele:\n"
               "  wu klasse 3AHWII               Übersicht: KV, Fächer, Roster\n"
               "  wu lesson 3AHWII/SWP1x         Roster des nächsten Termins\n"
               "  wu student \"Erika Muster\"       Treffer zu einer Schülerin\n"
               "  wu student --id 4711 --details  Details (KV, Fächer, Absenzen)\n"
               "  wu lehrer MK                   Steckbrief + KV-Klassen\n"
               "  wu offen status --von 2026-09-01 --bis 2026-09-30",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--schuljahr-id", dest="school_year_id", type=int,
                   default=None,
                   help="Schuljahr-ID festlegen "
                        "(Standard: über Datumsbereich auflösen)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # -- klasse --
    kla = sub.add_parser(
        "klasse", help="Klasse: Übersicht, Roster, Fächer, KV",
        description="Alles zu einer Klasse (z.B. 3AHWII). Ohne Unterbefehl: "
                    "Klassen-Kopf mit Klassenvorstand und klassen-id. "
                    "Fächer und Roster nur mit --details.",
        epilog="Beispiele:\n"
               "  wu klasse 3AHWII\n"
               "  wu klasse 3AHWII --details\n"
               "  wu klasse 3AHWII roster --ohne-kopf\n"
               "  wu klasse 3AHWII faecher --fach SWP",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    kla.add_argument("klassenname", help="Klassenname, z.B. 3AHWII")
    kla.add_argument("--fach", default=None,
                     help="nur dieses Fach (impliziert --details)")
    kla.add_argument("--details", dest="details", action="store_true",
                     help="zusätzlich Fächer und Roster zeigen")
    _add_von_bis(kla, required=False)
    _add_json(kla)
    _add_school_year_arg(kla)
    kla_sub = kla.add_subparsers(dest="sub")
    kla_roster = kla_sub.add_parser(
        "roster", help="Schülerliste der Klasse (TSV, Excel-einfügbare)",
        description="Roster der Klasse aus dem aktuellen Roster — volle "
                    "Namen, sortiert, als TSV (Name<TAB>Klasse).")
    kla_roster.add_argument("--ohne-kopf", dest="ohne_kopf",
                            action="store_true",
                            help="Kopfzeile 'Name<TAB>Klasse' weglassen")
    _add_json(kla_roster)
    _add_school_year_arg(kla_roster)
    kla_roster.set_defaults(func=cmd_klasse_roster)
    kla_faecher = kla_sub.add_parser(
        "faecher", help="eigene Lessons (Fächer) der Klasse auflisten",
        description="Eigene Lessons der Klasse, gruppiert je Lesson (lsId) "
                    "mit Lehrern, Räumen und Zeitraum. Quelle: offene "
                    "Perioden im Zeitraum (Standard: Schuljahr bis heute).")
    kla_faecher.add_argument("--fach", default=None,
                             help="nur Fächer mit diesem Präfix, z.B. SWP")
    kla_faecher.add_argument("--volle-namen", dest="volle_namen",
                             action="store_true",
                             help="Lehrer-Kürzel zu Vollnamen auflösen")
    _add_von_bis(kla_faecher, required=False)
    _add_json(kla_faecher)
    _add_school_year_arg(kla_faecher)
    kla_faecher.set_defaults(func=cmd_klasse_faecher)
    kla_kv = kla_sub.add_parser(
        "kv", help="Klassenvorstand der Klasse anzeigen")
    _add_json(kla_kv)
    _add_school_year_arg(kla_kv)
    kla_kv.set_defaults(func=cmd_klasse_kv)
    kla.set_defaults(func=cmd_klasse)

    # -- lesson --
    les = sub.add_parser(
        "lesson",
        help="Lesson (KLASSE/FACH): Roster, Termine, Lehrstoff, Absenzen",
        usage="wu lesson KLASSE/FACH [--lsid LSID] [--datum DATUM] "
              "[--ohne-kopf] [--json] [--schuljahr-id ID]\n"
              "       wu lesson KLASSE/FACH "
              "{roster,matrix,termine,info,aufnehmen,anpassen,\n"
              "                                lehrstoff,absenzen} [...]",
        description="Alles zu einer Lesson — einem Fach innerhalb einer "
                    "Klasse, adressiert als KLASSE/FACH (z.B. 3AHWII/SWP1x). "
                    "Ohne Unterbefehl: Roster (Teilnehmerliste) des Termins "
                    "zu --datum.",
        epilog="Beispiele:\n"
               "  wu lesson 3AHWII/SWP1x\n"
               "  wu lesson 3AHWII/SWP1x --datum 2026-09-22\n"
               "  wu lesson 3AHWII/SWP1x termine --mit-lehrstoff\n"
               "  wu lesson 3AHWII/SWP1x lehrstoff zeigen --termin-id 6055348\n"
               "  wu lesson 3AHWII/SWP1x absenzen zeigen",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    # KLASSE/FACH wird in _extract_adresse vorab herausgezogen (ein
    # nargs-Positionsargument vor Subparsern deutet argparse sonst als
    # Unterbefehl) — hier kein Positionsargument, args.klasse_fach wird
    # in main() gesetzt.
    les.add_argument("--lsid", type=int, default=None,
                     help="Lesson-ID direkt (statt KLASSE/FACH aufzulösen)")
    les.add_argument("--datum", dest="datum", type=_datum_arg,
                     default="heute",
                     help="Termin-Tag: JJJJ-MM-TT oder 'heute' (Standard)")
    les.add_argument("--ohne-kopf", dest="ohne_kopf", action="store_true",
                     help="Kopfzeile 'Name<TAB>Klasse' weglassen "
                          "(Default/roster)")
    _add_json(les)
    _add_school_year_arg(les)
    les_sub = les.add_subparsers(dest="sub")
    les_roster = les_sub.add_parser(
        "roster",
        help="Teilnehmerliste des Termins (TSV, Excel-einfügbare)",
        description="Excel-einfügbare TSV-Teilnehmerliste für den "
                    "Lesson-Termin zu --datum. Ohne Termin an diesem Tag: "
                    "nächster Termin (sonst letzter gehaltener) mit Hinweis.")
    les_roster.add_argument("--datum", dest="datum", type=_datum_arg,
                            default=argparse.SUPPRESS,
                            help="Termin-Tag: JJJJ-MM-TT oder 'heute'")
    les_roster.add_argument("--ohne-kopf", dest="ohne_kopf",
                            action="store_true",
                            help="Kopfzeile 'Name<TAB>Klasse' weglassen")
    _add_json(les_roster)
    _add_school_year_arg(les_roster)
    les_roster.set_defaults(func=cmd_lesson_roster)
    les.set_defaults(func=cmd_lesson_roster)
    les_matrix = les_sub.add_parser(
        "matrix", help="Anwesenheits-Matrix: Termine je Schüler",
        description="Anwesenheits-Matrix der Lesson: je Schüler alle "
                    "besuchten Termine. Textansicht zeigt nur Anwesende "
                    "(--alle für alle); --json immer alles.")
    les_matrix.add_argument("--klassen-id", dest="klassen_id", type=int,
                            default=None,
                            help="nur Schüler dieser Klassen-ID")
    les_matrix.add_argument("--nur-anwesende", dest="nur_anwesende",
                            action="store_true",
                            help="nur Schüler mit Anwesenheit")
    les_matrix.add_argument("--alle", action="store_true",
                            help="Textansicht: alle Schüler zeigen")
    _add_json(les_matrix)
    _add_school_year_arg(les_matrix)
    les_matrix.set_defaults(func=cmd_lesson_matrix)
    les_termine = les_sub.add_parser(
        "termine", help="alle Termine der Lesson mit Offen-Status",
        description="Alle Termine der Lesson: Offen-Status (Lehrstoff fehlt "
                    "oder Absenzen ungeprüft) vs. erledigt. Mit "
                    "--mit-lehrstoff zusätzlich die eingetragenen Texte "
                    "(gedrosselt, je ein Call pro Termin).")
    _add_von_bis(les_termine, required=False)
    les_termine.add_argument("--mit-lehrstoff", dest="mit_lehrstoff",
                             action="store_true",
                             help="eingetragene Lehrstoff-Texte mitladen")
    les_termine.add_argument("--pause", dest="pause", type=float, default=1.0,
                             help="Sekunden zwischen Calls (Standard 1.0)")
    _add_json(les_termine)
    _add_school_year_arg(les_termine)
    les_termine.set_defaults(func=cmd_lesson_termine)
    les_info = les_sub.add_parser(
        "info", help="Lesson-Diagnostik: Lehrer, Klassen, Verteilung",
        description="Diagnostik: Lehrer, Klassen, mainStudentgroupId und "
                    "Roster- vs. Anwesenheits-Verteilung je Klasse.")
    _add_json(les_info)
    _add_school_year_arg(les_info)
    les_info.set_defaults(func=cmd_lesson_info)
    les_aufnehmen = les_sub.add_parser(
        "aufnehmen", help="Schüler in die Lesson aufnehmen (Testlauf)",
        description="Schüler auf alle Lesson-Termine setzen und Payload "
                    "schicken. Die Heimatklasse wird standardmäßig aus der "
                    "Lesson abgeleitet (--klassen-id überschreibt). "
                    "--testlauf (Standard) schickt NICHT ab; "
                    "mit --ausfuehren wirklich aufnehmen.")
    les_aufnehmen.add_argument("--klassen-id", dest="klassen_id", type=int,
                               default=None,
                               help="Klassen-ID der Lesson-Heimatklasse "
                                    "(deren Schüler bleiben unverändert; "
                                    "Standard: aus der Lesson abgeleitet)")
    les_aufnehmen.add_argument("--schueler-id", dest="schueler_id", type=int,
                               default=None,
                               help="Schüler-ID (alternativ --schueler-name)")
    les_aufnehmen.add_argument("--schueler-name", dest="schueler_name",
                               default=None,
                               help="Namenssuche (braucht genau 1 Treffer)")
    les_aufnehmen.add_argument("--ausgabe", dest="ausgabe", default=None,
                               help="Submit-Payload als JSON in Datei schreiben")
    les_aufnehmen.add_argument("--details", dest="details",
                               action="store_true",
                               help="Payload in der Testlauf-Ausgabe zeigen")
    _add_testlauf(les_aufnehmen)
    _add_school_year_arg(les_aufnehmen)
    les_aufnehmen.set_defaults(func=cmd_lesson_aufnehmen)
    les_anpassen = les_sub.add_parser(
        "anpassen", help="Lesson-Anwesenheit ändern: +/- Schüler (Testlauf)",
        description="Aufnehmen und/oder entfernen in einem Write (volle "
                    "Edit-Semantik: Entfernte verlieren alle Termine). "
                    "Die Heimatklasse wird standardmäßig aus der Lesson "
                    "abgeleitet (--klassen-id überschreibt). "
                    "--testlauf (Standard) schickt NICHT ab.")
    les_anpassen.add_argument("--klassen-id", dest="klassen_id", type=int,
                              default=None,
                              help="Klassen-ID der Lesson-Heimatklasse "
                                   "(Standard: aus der Lesson abgeleitet)")
    les_anpassen.add_argument("--aufnehmen-id", dest="aufnehmen_id",
                              type=int, action="append", default=None,
                              help="aufzunehmende Schüler-ID (wiederholbar)")
    les_anpassen.add_argument("--entfernen-id", dest="entfernen_id",
                              type=int, action="append", default=None,
                              help="zu entfernende Schüler-ID (wiederholbar)")
    les_anpassen.add_argument("--ausgabe", dest="ausgabe", default=None,
                              help="Submit-Payload als JSON in Datei schreiben")
    les_anpassen.add_argument("--details", dest="details",
                              action="store_true",
                              help="Payload in der Testlauf-Ausgabe zeigen")
    _add_testlauf(les_anpassen)
    _add_school_year_arg(les_anpassen)
    les_anpassen.set_defaults(func=cmd_lesson_anpassen)
    les_lehr = les_sub.add_parser(
        "lehrstoff", help="Lehrstoff eines Termins: zeigen/eintragen/aus-git",
        description="Der Lehrstoff gehört zur Lesson: zu jedem Termin gibt "
                    "es den entsprechenden Lehrstoff-Eintrag.")
    les_lehr_sub = les_lehr.add_subparsers(dest="sub2", required=True)
    les_lehr_zeigen = les_lehr_sub.add_parser(
        "zeigen", help="eingetragenen Lehrstoff eines Termins anzeigen")
    les_lehr_zeigen.add_argument("--termin-id", dest="termin", type=int,
                                 required=True, help="Termin-ID (periodId)")
    _add_school_year_arg(les_lehr_zeigen)
    les_lehr_zeigen.set_defaults(func=cmd_lehrstoff_zeigen)
    les_lehr_eintragen = les_lehr_sub.add_parser(
        "eintragen", help="Lehrstoff für einen Termin eintragen (Write)",
        description="Einzelner Lehrstoff-Write. --testlauf (Standard) zeigt "
                    "nur; mit --ausfuehren wird geschrieben. Quelle: --text "
                    "(Achtung: Shell/Umlaute — lieber --text-datei), "
                    "--text-datei oder --text-stdin.")
    les_lehr_eintragen.add_argument("--termin-id", dest="termin", type=int,
                                    required=True,
                                    help="Termin-ID (periodId)")
    les_lehr_eintragen.add_argument("--thema-id", dest="thema", type=int,
                                    default=None,
                                    help="Lehrstoff-Zeilen-ID (Standard: "
                                         "auflösen, 0 = neu anlegen)")
    les_lehr_eintragen.add_argument("--text", default=None,
                                    help="Lehrstoff-Text (Umlaute: Datei!)")
    les_lehr_eintragen.add_argument("--text-datei", dest="text_file",
                                    default=None, help="Text aus Datei lesen")
    les_lehr_eintragen.add_argument("--text-stdin", dest="text_stdin",
                                    action="store_true",
                                    help="Text von stdin lesen")
    _add_testlauf(les_lehr_eintragen)
    _add_school_year_arg(les_lehr_eintragen)
    les_lehr_eintragen.set_defaults(func=cmd_lehrstoff_eintragen)
    les_lehr_git = les_lehr_sub.add_parser(
        "aus-git", help="Lehrstoff-Text aus GRG-*-Git-Logs ableiten",
        description="Text aus Unterrichts-Repos ableiten: Commits + Diffs "
                    "zeigen (--testlauf, Standard) oder mit --ausfuehren "
                    "(braucht --termin-id/--thema-id) direkt eintragen.")
    les_lehr_git.add_argument("--datum", dest="datum", type=_datum_arg,
                              required=True,
                              help="Unterrichts-Datum (JJJJ-MM-TT oder 'heute')")
    les_lehr_git.add_argument("--termin-id", dest="termin", type=int,
                              default=None, help="Termin-ID (nur --ausfuehren)")
    les_lehr_git.add_argument("--thema-id", dest="thema", type=int,
                              default=None,
                              help="Lehrstoff-Zeilen-ID (nur --ausfuehren)")
    _add_testlauf(les_lehr_git)
    _add_school_year_arg(les_lehr_git)
    les_lehr_git.set_defaults(func=cmd_lehrstoff_aus_git)
    les_abs = les_sub.add_parser(
        "absenzen", help="Absenzen der Lesson: Übersicht/Eintrag/Entfernung",
        description="Absenzen-Sicht der Lesson: Übersicht je Schüler "
                    "(Matrix, nur bis heute), ECHTE Abwesenheits-Einträge "
                    "eines Termins (mit --termin-id), Abwesenheit "
                    "eintragen/entfernen (Writes, Testlauf-Standard) oder "
                    "Absenzenprüfung durchführen (Write).")
    les_abs_sub = les_abs.add_subparsers(dest="sub2", required=True)
    les_abs_zeigen = les_abs_sub.add_parser(
        "zeigen", help="fehlende vs. gehaltene Stunden je Schüler "
                       "oder Abwesenheiten eines Termins")
    les_abs_zeigen.add_argument("--nur-fehlende", dest="nur_fehlende",
                                action="store_true",
                                help="nur Schüler mit Fehlstunden")
    les_abs_zeigen.add_argument("--alle", action="store_true",
                                help="alle Schüler der Matrix zeigen "
                                     "(auch nie Anwesende)")
    les_abs_zeigen.add_argument("--termin-id", dest="termin", type=int,
                                default=None,
                                help="statt Matrix: echte Abwesenheits-"
                                     "Einträge dieses Termins aus dem "
                                     "Klassenbuch (mit Absenz-IDs)")
    _add_json(les_abs_zeigen)
    _add_school_year_arg(les_abs_zeigen)
    les_abs_zeigen.set_defaults(func=cmd_absenzen_zeigen)
    les_abs_eintragen = les_abs_sub.add_parser(
        "eintragen", help="Schüler abwesend eintragen (Write)",
        description="Abwesenheit für einen Schüler setzen. Termin: "
                    "--termin-id oder --datum (Standard heute, via "
                    "KLASSE/FACH). Block-Standard (ganzer Stundenblock "
                    "wie in der UI); --kein-block für eine Einzelstunde "
                    "(braucht --termin-id). --testlauf (Standard) "
                    "schreibt NICHT.")
    les_abs_eintragen.add_argument("--schueler-id", dest="schueler_id",
                                   type=int, default=None,
                                   help="Schüler-ID (alternativ "
                                        "--schueler-name)")
    les_abs_eintragen.add_argument("--schueler-name", dest="schueler_name",
                                   default=None,
                                   help="Namenssuche (braucht genau 1 "
                                        "Treffer, volle Namen)")
    les_abs_eintragen.add_argument("--termin-id", dest="termin", type=int,
                                   default=None,
                                   help="Termin-ID (periodId), sonst "
                                        "--datum")
    les_abs_eintragen.add_argument("--datum", dest="datum", type=_datum_arg,
                                   default=argparse.SUPPRESS,
                                   help="Termin-Tag: JJJJ-MM-TT oder "
                                        "'heute'")
    les_abs_eintragen.add_argument("--kein-block", dest="kein_block",
                                   action="store_true",
                                   help="nur diese Einzelstunde "
                                        "(braucht --termin-id)")
    _add_testlauf(les_abs_eintragen)
    _add_school_year_arg(les_abs_eintragen)
    les_abs_eintragen.set_defaults(func=cmd_absenzen_eintragen)
    les_abs_entfernen = les_abs_sub.add_parser(
        "entfernen", help="Abwesenheit entfernen (Write)",
        description="Bestehende Abwesenheit löschen (Dialog-CSRF-Flow). "
                    "Ziel: --absenz-id (aus `absenzen zeigen --termin-id`) "
                    "oder --schueler-id/--schueler-name plus Termin "
                    "(--termin-id oder --datum). --testlauf (Standard) "
                    "schreibt NICHT.")
    les_abs_entfernen.add_argument("--absenz-id", dest="absenz_id", type=int,
                                   default=None,
                                   help="Absenz-ID (direkt, aus "
                                        "`absenzen zeigen --termin-id`)")
    les_abs_entfernen.add_argument("--schueler-id", dest="schueler_id",
                                   type=int, default=None,
                                   help="Schüler-ID (alternativ "
                                        "--schueler-name)")
    les_abs_entfernen.add_argument("--schueler-name", dest="schueler_name",
                                   default=None,
                                   help="Namenssuche (braucht genau 1 "
                                        "Treffer)")
    les_abs_entfernen.add_argument("--termin-id", dest="termin", type=int,
                                   default=None,
                                   help="Termin-ID (periodId), sonst "
                                        "--datum")
    les_abs_entfernen.add_argument("--datum", dest="datum", type=_datum_arg,
                                   default=argparse.SUPPRESS,
                                   help="Termin-Tag: JJJJ-MM-TT oder "
                                        "'heute'")
    _add_testlauf(les_abs_entfernen)
    _add_school_year_arg(les_abs_entfernen)
    les_abs_entfernen.set_defaults(func=cmd_absenzen_entfernen)
    les_abs_pruefen = les_abs_sub.add_parser(
        "pruefen", help="Absenzenprüfung durchführen (Write)",
        description="Mit --termin-id: genau dieser Termin. Ohne: alle "
                    "ungeprüften Termine dieser Lesson im Zeitraum "
                    "(Standard: Schuljahresstart bis heute). --testlauf "
                    "(Standard) zeigt nur; mit --ausfuehren wird geprüft.")
    les_abs_pruefen.add_argument("--termin-id", dest="termin", type=int,
                                 default=None,
                                 help="einzelner Termin (periodId)")
    _add_von_bis(les_abs_pruefen, required=False)
    les_abs_pruefen.add_argument("--pause", dest="pause", type=float,
                                 default=1.0,
                                 help="Sekunden zwischen Calls (Standard 1.0)")
    _add_testlauf(les_abs_pruefen)
    _add_school_year_arg(les_abs_pruefen)
    les_abs_pruefen.set_defaults(func=cmd_absenzen_pruefen)

    # -- student --
    stu = sub.add_parser(
        "student", help="Schüler: Treffer suchen (Details mit --details)",
        description="Schüler-Suche (tokenisierend, mit Fallback in ältere "
                    "Schuljahre). Standardmäßig NUR die Trefferliste "
                    "(schnell, keine Detail-Calls). Mit --details zusätzlich "
                    "Klasse, Klassenvorstand und belegte/nicht belegte "
                    "Lessons aus dem Schüler-Stundenplan (Anwesenheit egal — "
                    "belegt = eingeschrieben); mit --absenzen (impliziert "
                    "--details) zusätzlich Matrix-Scans der eigenen Lessons. "
                    "Treffer aus älteren Jahren sind NICHT AKTUELL markiert. "
                    "Mit --id direkter Zugriff per Schüler-ID statt "
                    "Namenssuche (nur aktuelles Roster).",
        epilog="Beispiele:\n"
               "  wu student \"Erika Muster\"\n"
               "  wu student --id 4711 --details\n"
               "  wu student Muster --klasse 5BAIF --absenzen --json",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    stu.add_argument("name", nargs="?", default=None,
                     help="Name, z.B. 'Erika Muster' (alternativ --id)")
    stu.add_argument("--id", dest="student_id", type=int, default=None,
                     help="Schüler-ID direkt (statt Namenssuche; nur "
                          "aktuelles Roster)")
    stu.add_argument("--klasse", dest="klasse", default=None,
                     help="auf Klasse filtern, z.B. 5BAIF")
    stu.add_argument("--wortteile", dest="wortteile", action="store_true",
                     help="Vor-/Nachname einzeln suchen und zusammenführen")
    stu.add_argument("--alle-jahre", dest="alle_jahre", action="store_true",
                     help="zusätzlich ältere Schuljahre durchsuchen "
                          "(NICHT AKTUELL markiert)")
    stu.add_argument("--details", dest="details", action="store_true",
                     help="Detailblock je Treffer zeigen (KV, Fächer, ggf. "
                          "Absenzen); Default ist nur die Trefferliste")
    stu.add_argument("--absenzen", dest="absenzen", action="store_true",
                     help="Absenzen der EIGENEN Lessons der Klasse anzeigen "
                          "(impliziert --details; je Lesson Matrix-Call, "
                          "gedrosselt)")
    stu.add_argument("--pause", dest="pause", type=float, default=1.0,
                     help="Sekunden zwischen Matrix-Calls (Standard 1.0, "
                          "nur --absenzen)")
    _add_json(stu)
    _add_school_year_arg(stu)
    stu.set_defaults(func=cmd_student)

    # -- offen --
    off = sub.add_parser(
        "offen", help="Arbeitsvorrat: offene Perioden (Lehrstoff/Absenzen)",
        description="Offene Perioden schulden noch Lehrstoff oder "
                    "Absenzenprüfung. Arbeitsvorrat im Schuljahr-Default "
                    "(Schuljahr-Start bis heute, einengbar per --von/--bis): "
                    "auflisten, Überblick, verifizieren, Vorschläge aus Git "
                    "bauen, bestätigte Texte eintragen, Festtexte füllen, "
                    "Absenzen prüfen.",
        epilog="Beispiele:\n"
               "  wu offen status --von 2026-09-01 --bis 2026-09-30\n"
               "  wu offen vorschlag --von 2026-09-01 --bis 2026-09-30 > vorschlag.json\n"
               "  wu offen eintragen --datei batch.json\n"
               "  wu offen pruefen --von 2026-09-01 --bis 2026-09-30",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    off_sub = off.add_subparsers(dest="sub", required=True)
    off_liste = off_sub.add_parser(
        "liste", help="offene Perioden im Zeitraum auflisten")
    _add_von_bis(off_liste, required=False, schuljahr_default=True)
    _add_json(off_liste)
    _add_school_year_arg(off_liste)
    off_liste.set_defaults(func=cmd_offen_liste)
    off_status = off_sub.add_parser(
        "status", help="Überblick: Zählung nach Fach und Klasse+Fach")
    _add_von_bis(off_status, required=False, schuljahr_default=True)
    _add_json(off_status)
    _add_school_year_arg(off_status)
    off_status.set_defaults(func=cmd_offen_status)
    off_verif = off_sub.add_parser(
        "verifizieren",
        help="welche Perioden wirklich ohne Lehrstoff-Text sind",
        description="Trennt 'wirklich leer' (kein Text) von 'hat Text, nur "
                    "Absenzenprüfung fehlt' — je Termin ein API-Call.")
    _add_von_bis(off_verif, required=False, schuljahr_default=True)
    _add_json(off_verif)
    _add_school_year_arg(off_verif)
    off_verif.set_defaults(func=cmd_offen_verifizieren)
    off_vorschlag = off_sub.add_parser(
        "vorschlag",
        help="Vorschlag-JSON aus Git-Logs bauen (Testlauf, für Skill/Agent)",
        description="Lädt offene Perioden + Commits/Diffs je Block und gibt "
                    "Vorschlag-JSON aus (blocks + skipped). Schreibt nichts. "
                    "Texte prüfen/bestätigen, dann `offen eintragen --datei`.")
    _add_von_bis(off_vorschlag, required=False, schuljahr_default=True)
    _add_school_year_arg(off_vorschlag)
    off_vorschlag.set_defaults(func=cmd_offen_vorschlag)
    off_eintragen = off_sub.add_parser(
        "eintragen", help="bestätigte Lehrstoffe aus Datei eintragen (Write)",
        description="JSON-Datei [{periodId, topicId, text, classId, start, "
                    "end, date}, ...]: je Eintrag ein PUT (+Lesson-Details-URL). "
                    "--testlauf (Standard) zeigt nur; mit --ausfuehren wird "
                    "geschrieben.")
    off_eintragen.add_argument("--datei", dest="datei", required=True,
                               help="bestätigte Batch-JSON-Datei")
    off_eintragen.add_argument("--pause", dest="pause", type=float,
                               default=1.0,
                               help="Sekunden zwischen PUTs (Standard 1.0, "
                                    "gegen IP-Rate-Limit)")
    _add_testlauf(off_eintragen)
    _add_school_year_arg(off_eintragen)
    off_eintragen.set_defaults(func=cmd_offen_eintragen)
    off_fest = off_sub.add_parser(
        "festtexte", help="Festtext-Fächer (SS, BESP) füllen",
        description="Offene Perioden mit Festtext (SS/BESP) füllen. "
                    "--testlauf (Standard) zeigt nur.")
    _add_von_bis(off_fest, required=False, schuljahr_default=True)
    _add_json(off_fest)
    off_fest.add_argument("--pause", dest="pause", type=float, default=1.0,
                          help="Sekunden zwischen PUTs (Standard 1.0)")
    _add_testlauf(off_fest)
    _add_school_year_arg(off_fest)
    off_fest.set_defaults(func=cmd_offen_festtexte)
    off_pruefen = off_sub.add_parser(
        "pruefen", help="Absenzenprüfung für offene Perioden (Write)",
        description="Mit --datei: Perioden aus Datei ([{periodId}, ...]). "
                    "Ohne: alle prüfbedürftigen Perioden im Zeitraum "
                    "(Standard: Schuljahr-Start bis heute). --testlauf "
                    "(Standard) zeigt nur; mit --ausfuehren wird geprüft.")
    off_pruefen.add_argument("--datei", dest="datei", default=None,
                             help="JSON-Datei [{periodId}, ...] statt Zeitraum")
    _add_von_bis(off_pruefen, required=False, schuljahr_default=True)
    off_pruefen.add_argument("--pause", dest="pause", type=float, default=1.0,
                             help="Sekunden zwischen Calls (Standard 1.0)")
    _add_testlauf(off_pruefen)
    _add_school_year_arg(off_pruefen)
    off_pruefen.set_defaults(func=cmd_offen_pruefen)

    # -- raum --
    rau = sub.add_parser(
        "raum", help="Räume: suchen/groesse (vorbereitet, noch Stubs)",
        description="Raum-Sichten. Die nötigen Endpunkte sind reverse-"
                    "engineered und dokumentiert (Raum-Stundenplan + "
                    "Raumverzeichnis mit Sitzplätzen), die Befehle sind "
                    "noch nicht implementiert (Exit 3) und reservieren "
                    "das CLI-Vokabular für die geplante Freie-Raum-Suche.",
        epilog="Beispiele (geplante Semantik):\n"
               "  wu raum suchen --datum morgen --stunde 7 --max-plaetze 20\n"
               "  wu raum suchen --datum 2026-09-25 --stunde 7 --min-plaetze 36\n"
               "  wu raum groesse B3.07",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    rau_sub = rau.add_subparsers(dest="sub", required=True)
    rau_suchen = rau_sub.add_parser(
        "suchen", help="freien Raum für eine Stunde suchen (noch Stub)")
    rau_suchen.add_argument("--datum", dest="datum", type=_datum_arg,
                            default="heute",
                            help="Tag: JJJJ-MM-TT oder 'heute'/'morgen' "
                                 "(geplant)")
    rau_suchen.add_argument("--stunde", dest="stunde", type=int, default=None,
                            help="Schulstunde (1-11, laut Stundengitter; "
                                 "geplant)")
    rau_suchen.add_argument("--min-plaetze", dest="min_plaetze", type=int,
                            default=None,
                            help="mindestens so viele Sitzplätze (geplant)")
    rau_suchen.add_argument("--max-plaetze", dest="max_plaetze", type=int,
                            default=None,
                            help="höchstens so viele Sitzplätze (geplant)")
    rau_suchen.add_argument("--nur-freie", dest="nur_freie",
                            action="store_true",
                            help="belegte Räume ausblenden (geplant)")
    _add_json(rau_suchen)
    _add_school_year_arg(rau_suchen)
    rau_suchen.set_defaults(func=cmd_raum_suchen)
    rau_groesse = rau_sub.add_parser(
        "groesse", help="Sitzplätze eines Raums (noch Stub)")
    rau_groesse.add_argument("raum", help="Raum-Kürzel, z.B. B3.07")
    _add_json(rau_groesse)
    _add_school_year_arg(rau_groesse)
    rau_groesse.set_defaults(func=cmd_raum_groesse)

    # -- lehrer --
    leh = sub.add_parser(
        "lehrer", help="Lehrer: Treffer, Kürzel, KV-Klassen",
        description="Alles zu einem Lehrer: Suche per Kürzel/Name "
                    "(tokenisierend, mit optionalem Fallback in ältere "
                    "Schuljahre), Kürzel/Lehrer-ID und die KV-Klassen. "
                    "Fremde Lehrer-Stundenpläne sind via API nicht lesbar.",
        epilog="Beispiele:\n"
               "  wu lehrer MK\n"
               "  wu lehrer \"Muster, Klaus\" --wortteile\n"
               "  wu lehrer Must --alle-jahre --json",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    leh.add_argument("name", help="Name oder Kürzel, z. B. MK")
    leh.add_argument("--wortteile", dest="wortteile", action="store_true",
                     help="Vor-/Nachname einzeln suchen und zusammenführen")
    leh.add_argument("--alle-jahre", dest="alle_jahre", action="store_true",
                     help="zusätzlich ältere Schuljahre durchsuchen "
                          "(Treffer als NICHT AKTUELL markiert)")
    _add_json(leh)
    _add_school_year_arg(leh)
    leh.set_defaults(func=cmd_lehrer)

    # -- intern (versteckt) --
    inter = sub.add_parser(
        "intern", help="Interna: Session, Recorder, API-Passthroughs",
        description="Interna für Entwicklung, Session-Management und das "
                    "Agenten-Setup (login, logout, session, record, rpc, "
                    "rest). Im Alltag nicht nötig.")
    inter_sub = inter.add_subparsers(dest="sub", required=True)
    login_parser = inter_sub.add_parser("login", help=argparse.SUPPRESS)
    login_parser.set_defaults(func=cmd_login)
    logout_parser = inter_sub.add_parser("logout", help=argparse.SUPPRESS)
    logout_parser.set_defaults(func=cmd_logout)
    sess = inter_sub.add_parser("session", help=argparse.SUPPRESS)
    sess_sub = sess.add_subparsers(dest="sub2", required=True)
    sess_status = sess_sub.add_parser("status", help=argparse.SUPPRESS)
    sess_status.add_argument("--json", action="store_true")
    sess_status.set_defaults(func=cmd_session_status)
    rec = inter_sub.add_parser("record", help=argparse.SUPPRESS)
    rec.add_argument("--host", default="localhost")
    rec.add_argument("--port", type=int, default=9222)
    rec.add_argument("--domain", default="spengergasse.webuntis.com")
    rp = inter_sub.add_parser("rpc", help=argparse.SUPPRESS)
    rp.add_argument("method", help="JSON-RPC-Methode, z.B. getKlassen")
    rp.add_argument("params_json", nargs="?", default=None,
                    help="Parameter als JSON-String, Standard {}")
    rp.set_defaults(func=cmd_rpc)
    rst = inter_sub.add_parser("rest", help=argparse.SUPPRESS)
    rst.add_argument("path", help="Pfad relativ zu /WebUntis/api")
    rst.add_argument("--method", default="GET",
                     choices=["GET", "POST", "PUT", "DELETE"])
    rst.add_argument("--data-json", default=None,
                     help="Body als JSON-String (POST/PUT)")
    _add_school_year_arg(rst)
    rst.set_defaults(func=cmd_rest)

    _attach_parsers(p)

    argv = sys.argv[1:]
    if not argv:
        # Kein Befehl: volle Hilfe, dokumentierter Exit 1.
        p.print_help()
        return 1
    # KLASSE/FACH (enthält immer `/`, Subs nie) wird vorab herausgezogen:
    # ein `nargs="?"`-Positionsargument vor Subparsern deutet argparse
    # sonst als Unterbefehl (1 Token) bzw. frisst den Sub (2 Token nach
    # Pop). Options-Werte (z.B. --text "a/b", Dateipfade) werden dabei
    # übersprungen. Nach dem Parsen wieder einsetzen.
    adresse = None
    argv, adresse = _extract_adresse(argv)
    try:
        args = p.parse_args(argv)
        if getattr(args, "cmd", None) == "lesson":
            args.klasse_fach = adresse
        if args.cmd == "intern" and args.sub == "record":
            from webuntis_cli.recorder import main as rec_main
            return rec_main([f"--host={args.host}", f"--port={args.port}",
                             f"--domain={args.domain}"])
        if hasattr(args, "func"):
            return args.func(args)
        p.print_help()
        return 1
    except UsageError as e:
        if e.parser is not None:
            _print_help_and_error(e.parser, str(e))
        else:
            print(f"Fehler: {e}", file=sys.stderr)
        return e.exit_code
    except WuError as e:
        # Erwarteter Fehler: Meldung (+ optionaler Hinweis), kein Traceback.
        print(str(e), file=sys.stderr)
        if e.hint:
            print(e.hint, file=sys.stderr)
        return e.exit_code
    except ModuleNotFoundError as e:
        print(
            f"Fehler: Python-Modul fehlt ({e.name}).\n\n"
            "Anleitung — venv im Repo anlegen:\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/pip install -e .\n\n"
            "Danach wu (.venv/bin/python) verwenden oder "
            "PYTHON_BIN auf das venv-Python setzen.",
            file=sys.stderr,
        )
        return ConfigError.exit_code
    except KeyboardInterrupt:
        print("Abgebrochen.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except Exception as e:
        code = classify_exit(e)
        if code == UnexpectedError.exit_code:
            print(f"Interner Fehler: {type(e).__name__}: {e}",
                  file=sys.stderr)
            traceback.print_exc()
        else:
            print(str(e), file=sys.stderr)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
