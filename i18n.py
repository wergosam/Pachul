"""
Pachul — i18n.py
Sehr einfaches Wörterbuch-basiertes Übersetzungssystem
(Deutsch / Französisch / Italienisch / Englisch).

Verwendung:
    from i18n import tr
    label = Gtk.Label(label=tr("Install"))

`tr(text)` schlägt `text` (der englische Originaltext dient als Schlüssel)
im Wörterbuch der aktuellen Sprache nach und gibt sonst den Originaltext
unverändert zurück (Englisch braucht keine Übersetzungstabelle). Für Texte
mit Platzhaltern einfach `.format(...)` nach `tr(...)` anhängen, z. B.:

    tr("Remove {name}?").format(name=pkg_name)

Die Sprache wird über backend.get_setting("language") persistiert und kann
zur Laufzeit mit set_language() geändert werden. Da GTK4-Widgets nach dem
Bau ihren Text nicht automatisch neu abfragen, baut pachulWindow bei einem
Sprachwechsel im Einstellungen-Dialog seine komplette Oberfläche einmal
neu auf (siehe pachulWindow._rebuild_for_language_change() in window.py),
damit auch länger lebende Widgets (Seitenleiste, Menü, Kopfzeile, leere
Zustände) den neuen Text sofort zeigen. Dialoge und Paketzeilen sind davon
ohnehin nicht betroffen, da sie bei jedem Öffnen/Neuladen frisch mit tr()
aufgebaut werden.
"""

import backend

_LANG = None  # lazily loaded from settings

SUPPORTED_LANGUAGES = ("en", "de", "fr", "it")


def get_language():
    global _LANG
    if _LANG is None:
        _LANG = backend.get_setting("language") or "en"
    return _LANG


def set_language(lang):
    global _LANG
    _LANG = lang
    backend.save_settings({"language": lang})


def tr(text):
    """Translate `text` into the active language. English text is the key."""
    lang = get_language()
    table = _TABLES.get(lang)
    if table is None:
        return text
    return table.get(text, text)


# ─── Translation table: English → Deutsch ─────────────────────────────────────
STRINGS_DE = {
    # ── App / window chrome ──────────────────────────────────────────────────
    "Select a Package": "Paket auswählen",
    "Choose a package to view its details, files, and dependencies.":
        "Wähle ein Paket aus, um Details, Dateien und Abhängigkeiten anzuzeigen.",
    "Package": "Paket",
    "Description": "Beschreibung",
    "INSTALLED": "INSTALLIERT",
    "UPDATE": "UPDATE",
    "AUR": "AUR",
    "Install": "Installieren",
    "Uninstall": "Deinstallieren",
    "Reinstall": "Neu installieren",
    "Downgrade": "Downgraden",
    "Update": "Aktualisieren",
    "Package Information": "Paketinformationen",
    "Raw Output": "Rohausgabe",
    "pacman -Qi output": "pacman -Qi-Ausgabe",
    "Full package information": "Vollständige Paketinformationen",
    "Info": "Info",
    "Files": "Dateien",
    "Filter…": "Filtern…",
    "Loading…": "Lade…",
    "{shown} of {total} files": "{shown} von {total} Dateien",
    "{total} files": "{total} Dateien",

    # Info field labels (DetailPanel.INFO_KEYS)
    "URL": "URL",
    "Licenses": "Lizenzen",
    "Groups": "Gruppen",
    "Depends On": "Abhängig von",
    "Optional Deps": "Optionale Abhängigkeiten",
    "Required By": "Benötigt von",
    "Conflicts With": "Konflikt mit",
    "Provides": "Stellt bereit",
    "Replaces": "Ersetzt",
    "Installed Size": "Installierte Größe",
    "Packager": "Paketersteller",
    "Build Date": "Build-Datum",
    "Install Date": "Installationsdatum",
    "Install Reason": "Installationsgrund",
    "Architecture": "Architektur",

    # Sidebar
    "Pachul": "Pachul",
    "A powerful Pacman/AUR front end.\n": "Ein leistungsstarkes Pacman/AUR-Frontend.\n",
    "TOTAL": "GESAMT",
    "UPDATES": "UPDATES",
    "BROWSE": "DURCHSUCHEN",
    "Search": "Suche",
    "Updates": "Updates",
    "Installed": "Installiert",
    "AUR / Foreign": "AUR / Fremd",
    "REPOSITORIES": "REPOSITORIEN",
    "TOOLS": "WERKZEUGE",
    "Check Updates": "Updates prüfen",
    "Rate Mirrors": "Spiegelserver bewerten",
    "Find Orphans": "Waisen finden",
    "Clean Cache": "Cache leeren",

    # Header menu
    "System upgrade (pacman -Syu)": "Systemaktualisierung (pacman -Syu)",
    "Sync Databases": "Datenbanken synchronisieren",
    "Refresh Package Lists": "Paketlisten aktualisieren",
    "Downloads the latest package lists from your enabled repositories (pacman -Sy), so Pachul knows about new versions and new packages. This only refreshes metadata — nothing on your system is installed, removed, or upgraded.":
        "Lädt die aktuellen Paketlisten deiner aktivierten Repositories herunter (pacman -Sy), damit Pachul neue Versionen und neue Pakete kennt. Dabei werden nur Metadaten aktualisiert — an deinem System wird nichts installiert, entfernt oder aktualisiert.",
    "Check for Updates": "Auf Updates prüfen",
    "Refresh List": "Liste aktualisieren",
    "Manage Repositories…": "Repositorien verwalten…",
    "Rate Mirrors…": "Spiegelserver bewerten…",
    "Config Files (.pacnew)…": "Konfigurationsdateien (.pacnew)…",
    "Package History…": "Paketverlauf…",
    "System Info": "Systeminformationen",
    "Cache Cleaner": "Cache-Reiniger",
    "Export Package List…": "Paketliste exportieren…",
    "Import Package List…": "Paketliste importieren…",
    "View PKGBUILD (AUR)…": "PKGBUILD anzeigen (AUR)…",
    "Hold / Unhold Selected": "Auswahl sperren/entsperren",
    "Mark Selected as Explicit": "Auswahl als explizit markieren",
    "Mark Selected as Dependency": "Auswahl als Abhängigkeit markieren",
    "Preferences": "Einstellungen",
    "Keyboard Shortcuts": "Tastenkombinationen",
    "About Pachul": "Über Pachul",
    "Upgrade Now": "Jetzt aktualisieren",

    # Search page
    "Search Packages": "Pakete suchen",
    "Search official repos and AUR": "Offizielle Repos und AUR durchsuchen",
    "Search packages, e.g. firefox, vlc, git…": "Pakete suchen, z. B. firefox, vlc, git…",
    "Find Packages": "Pakete finden",
    "Type above to search the official repositories and AUR.":
        "Tippe oben, um die offiziellen Repositorien und das AUR zu durchsuchen.",
    "Searching…": "Suche läuft…",
    "No Results": "Keine Ergebnisse",
    "Try different keywords or check your spelling.":
        "Versuche andere Suchbegriffe oder überprüfe die Schreibweise.",
    "{n} result": "{n} Ergebnis",
    "{n} results": "{n} Ergebnisse",

    # List panel
    "Loading packages…": "Lade Pakete…",
    "System is up to date": "System ist aktuell",
    "No pending updates found.": "Keine ausstehenden Updates gefunden.",
    "No Packages Found": "Keine Pakete gefunden",
    "Try a different filter or search term.": "Versuche einen anderen Filter oder Suchbegriff.",
    "Upgrade All": "Alle aktualisieren",
    "{shown} of {total} packages": "{shown} von {total} Paketen",
    "{total} packages": "{total} Pakete",
    "{n} update(s) available.": "{n} Update(s) verfügbar.",
    "{n} update available": "{n} Update verfügbar",
    "{n} updates available": "{n} Updates verfügbar",

    # Status pills
    "UPDATE AVAILABLE": "UPDATE VERFÜGBAR",
    "INSTALLED (AUR)": "INSTALLIERT (AUR)",
    "AVAILABLE": "VERFÜGBAR",
    "No description available.": "Keine Beschreibung verfügbar.",
    "Look up {dep}": "{dep} nachschlagen",
    "+{n} more": "+{n} weitere",
    "{n} package": "{n} Paket",
    "{n} packages": "{n} Pakete",

    # Toasts / actions
    "Select a package first": "Bitte zuerst ein Paket auswählen",
    "PKGBUILD is only available for AUR packages": "PKGBUILD ist nur für AUR-Pakete verfügbar",
    "Could not read /etc/pacman.conf": "/etc/pacman.conf konnte nicht gelesen werden",
    "Unhold": "Entsperren",
    "Hold": "Sperren",
    "Hold {pkg}": "{pkg} sperren",
    "Unhold {pkg}": "{pkg} entsperren",
    "Allow {pkg} to Update Again": "{pkg} wieder aktualisierbar machen",
    "Removes {pkg} from IgnorePkg in /etc/pacman.conf. It will be included in system upgrades again from now on.":
        "Entfernt {pkg} aus IgnorePkg in /etc/pacman.conf. Es wird ab sofort wieder bei System-Updates berücksichtigt.",
    "Pin {pkg} to Its Current Version": "{pkg} auf der aktuellen Version festhalten",
    "Adds {pkg} to IgnorePkg in /etc/pacman.conf. Held packages are skipped by system upgrades — useful if a specific version needs to stay put for compatibility — and won't update again until you unhold them.":
        "Fügt {pkg} zu IgnorePkg in /etc/pacman.conf hinzu. Gesperrte Pakete werden bei System-Updates übersprungen — nützlich, wenn eine bestimmte Version aus Kompatibilitätsgründen bleiben muss — und werden erst wieder aktualisiert, wenn du sie entsperrst.",
    "{verb} {name}": "{name} {verb}",
    "✓ {title} completed": "✓ {title} abgeschlossen",
    "✗ {title} failed (exit {code})": "✗ {title} fehlgeschlagen (Exit {code})",
    "Sync Databases ": "Datenbanken synchronisieren",
    "System Upgrade": "Systemaktualisierung",
    "Clean Cache ": "Cache leeren",
    "Mark {name} as explicit": "{name} als explizit markieren",
    "Mark {name} as dependency": "{name} als Abhängigkeit markieren",
    "Mark as Dependency": "Als Abhängigkeit markieren",
    "Only changes {pkg}'s install-reason metadata to \"installed as a dependency\" — the package itself is not touched or removed right now. The effect: once nothing else on your system depends on {pkg} anymore, it will show up as an orphan and can be cleaned up later via \"Find Orphans\".":
        "Ändert nur den Installationsgrund von {pkg} auf „als Abhängigkeit installiert\" — das Paket selbst wird jetzt nicht angefasst oder entfernt. Der Effekt: Sobald nichts mehr auf deinem System von {pkg} abhängt, taucht es als Waise auf und kann später über „Waisen finden\" bereinigt werden.",
    "Export Package List": "Paketliste exportieren",
    "pachul-packages.txt": "pachul-pakete.txt",
    "Exported {n} packages": "{n} Pakete exportiert",
    "Export failed: {err}": "Export fehlgeschlagen: {err}",
    "Save Installed Programs to a List": "Installierte Programme in einer Liste speichern",
    "Writes the names of every package you explicitly installed yourself (one per line) to a plain text file — this deliberately excludes dependencies that were only pulled in automatically. Use \"Import Package List\" later, on this or another machine, to reinstall the same set of programs.":
        "Schreibt die Namen aller von dir selbst explizit installierten Pakete (eines pro Zeile) in eine einfache Textdatei — Abhängigkeiten, die nur automatisch mitinstalliert wurden, werden dabei bewusst ausgeschlossen. Mit „Paketliste importieren\" kannst du später, auf diesem oder einem anderen Rechner, dieselben Programme wieder installieren.",
    "Choose Location…": "Speicherort auswählen…",
    "Import Package List": "Paketliste importieren",
    "Install Programs From a Saved List": "Programme aus einer gespeicherten Liste installieren",
    "Choose File…": "Datei auswählen…",
    "Could not read file: {err}": "Datei konnte nicht gelesen werden: {err}",
    "No packages found in file": "Keine Pakete in der Datei gefunden",
    "Install {n} packages": "{n} Pakete installieren",
    "{n} packages found in file": "{n} Pakete in der Datei gefunden",
    "Reads one package name per line from the file (lines starting with # are ignored), then installs every listed package via {helper}, using --needed so anything already installed is skipped automatically. Nothing else on your system is changed.":
        "Liest aus der Datei einen Paketnamen pro Zeile (Zeilen, die mit # beginnen, werden ignoriert), und installiert dann jedes gelistete Paket über {helper} — mit --needed, sodass bereits installierte Pakete automatisch übersprungen werden. Sonst wird an deinem System nichts verändert.",
    "Reads one package name per line from the file (lines starting with # are ignored), then installs every listed package via pacman -S --needed, so anything already installed is skipped automatically. AUR packages in the list can't be installed this way since no AUR helper is configured — only official-repo packages will succeed. Nothing else on your system is changed.":
        "Liest aus der Datei einen Paketnamen pro Zeile (Zeilen, die mit # beginnen, werden ignoriert), und installiert dann jedes gelistete Paket über pacman -S --needed, sodass bereits installierte Pakete automatisch übersprungen werden. AUR-Pakete in der Liste können so nicht installiert werden, da kein AUR-Helfer konfiguriert ist — nur Pakete aus offiziellen Repositories werden erfolgreich installiert. Sonst wird an deinem System nichts verändert.",
    "Install {name}": "{name} installieren",
    "Remove {name}": "{name} entfernen",
    "Reinstall {name}": "{name} neu installieren",
    "Remove {name}?": "{name} entfernen?",
    "This will remove {name} ({version}) from your system.":
        "Dadurch wird {name} ({version}) von deinem System entfernt.",
    "Cancel": "Abbrechen",
    "Remove": "Entfernen",
    "Updates Available": "Updates verfügbar",
    "{n} package update can be installed.": "{n} Paketupdate kann installiert werden.",
    "{n} package updates can be installed.": "{n} Paketupdates können installiert werden.",

    # Multi-select / batch actions
    "Select multiple packages": "Mehrere Pakete auswählen",
    "Select packages…": "Pakete auswählen …",
    "{n} selected": "{n} ausgewählt",
    "Install ({n})": "Installieren ({n})",
    "Remove ({n})": "Entfernen ({n})",
    "Remove {n} packages": "{n} Pakete entfernen",
    "Remove {n} packages?": "{n} Pakete entfernen?",
    "This will remove the {n} selected packages from your system.":
        "Dadurch werden die {n} ausgewählten Pakete von deinem System entfernt.",
    "No AUR helper found — skipped {n} AUR package(s).":
        "Kein AUR-Helper gefunden — {n} AUR-Paket(e) übersprungen.",

    # File search (pacman -F)
    "Find Package by File…": "Paket über Datei finden …",
    "Find Package by File": "Paket über Datei finden",
    "File database not synced yet — sync it to search":
        "Dateidatenbank noch nicht synchronisiert — zum Suchen synchronisieren",
    "Sync Now": "Jetzt synchronisieren",
    "e.g. libssl.so.3 or usr/bin/htop": "z. B. libssl.so.3 oder usr/bin/htop",
    "Find out which package installs a given file or command.":
        "Herausfinden, welches Paket eine bestimmte Datei oder einen Befehl installiert.",
    "No Package Found": "Kein Paket gefunden",
    "No package provides a matching file.": "Kein Paket enthält eine passende Datei.",
    "… and {n} more files": "… und {n} weitere Dateien",
    "Sync File Database": "Dateidatenbank synchronisieren",

    # GPG / signature error handling
    "Unknown GPG key {id} detected": "Unbekannter GPG-Schlüssel {id} erkannt",
    "Import & Retry": "Importieren & erneut versuchen",
    "Signature check failed — the keyring may be outdated":
        "Signaturprüfung fehlgeschlagen — Schlüsselring ist möglicherweise veraltet",
    "Update Keyring & Retry": "Schlüsselring aktualisieren & erneut versuchen",

    # Stale pacman database lock (db.lck) handling
    "Pacman database is locked (stale db.lck)": "Pacman-Datenbank ist gesperrt (veraltete db.lck)",
    "Remove Lock & Retry": "Sperre entfernen & erneut versuchen",
    "Something is still holding the database lock — not removing it.":
        "Etwas hält die Datenbank-Sperre noch — sie wird nicht entfernt.",

    # Pre-upgrade snapshot (Timeshift/Snapper)
    "Create snapshot before system upgrades": "Vor System-Upgrades einen Snapshot erstellen",
    "Safety net via Timeshift — restore point before every upgrade":
        "Sicherheitsnetz über Timeshift — Wiederherstellungspunkt vor jedem Upgrade",
    "Safety net via Snapper (config: {config})":
        "Sicherheitsnetz über Snapper (Konfiguration: {config})",
    "No Timeshift or Snapper installation found":
        "Keine Timeshift- oder Snapper-Installation gefunden",

    # AUR metadata (votes / popularity / maintainer)
    "View on AUR (votes, comments, discussion)": "Auf AUR ansehen (Votes, Kommentare, Diskussion)",
    "A PKGBUILD is the build script an AUR package uses to compile and install itself. AUR packages aren't reviewed by Arch, so it's worth skimming this before installing.":
        "Ein PKGBUILD ist das Build-Skript, mit dem ein AUR-Paket sich selbst kompiliert und installiert. AUR-Pakete werden nicht von Arch geprüft — es lohnt sich daher, kurz drüberzuschauen, bevor du installierst.",
    "This AUR package is flagged out-of-date by its maintainer":
        "Dieses AUR-Paket wurde vom Maintainer als veraltet markiert",
    "AUR info unavailable": "AUR-Infos nicht verfügbar",
    "Orphaned": "Verwaist",

    # Terminal dialog
    "Close": "Schließen",
    "Password or input — press Enter to send": "Passwort oder Eingabe — Enter zum Senden",
    "Send": "Senden",
    "Show/hide input": "Eingabe ein-/ausblenden",
    "(input sent)\n": "(Eingabe gesendet)\n",
    "\n— Cancelled —\n": "\n— Abgebrochen —\n",
    "✓  Completed successfully\n": "✓  Erfolgreich abgeschlossen\n",
    "✗  Failed  (exit code {code})\n": "✗  Fehlgeschlagen  (Exit-Code {code})\n",
    "\nInternal error: {err}\n": "\nInterner Fehler: {err}\n",

    # Repo manager
    "Manage Repositories": "Repositorien verwalten",
    "Edit pacman.conf": "pacman.conf bearbeiten",
    "Edit pacman.conf ": "pacman.conf bearbeiten",
    "Active Repositories": "Aktive Repositorien",
    "Repositories currently enabled in /etc/pacman.conf":
        "Aktuell aktivierte Repositorien in /etc/pacman.conf",
    "{n} pkgs": "{n} Pakete",
    "pacman.conf": "pacman.conf",
    "/etc/pacman.conf — read-only view": "/etc/pacman.conf — schreibgeschützte Ansicht",
    "# /etc/pacman.conf not found or not readable":
        "# /etc/pacman.conf nicht gefunden oder nicht lesbar",
    "Save": "Speichern",
    "Save pacman.conf": "pacman.conf speichern",
    "Edit directly below, then click Save. Make sure the syntax stays valid — pacman will refuse to run on a broken config.":
        "Direkt unten bearbeiten und dann auf Speichern klicken. Achte auf gültige Syntax — bei einer fehlerhaften Konfiguration verweigert pacman den Dienst.",

    # Mirror rater
    "Mirror Options": "Spiegelserver-Optionen",
    "rate-mirrors tests all Arch mirrors and shows you the result — nothing is written to /etc/pacman.d/mirrorlist until you review it and choose to save":
        "rate-mirrors testet alle Arch-Spiegelserver und zeigt dir das Ergebnis — in /etc/pacman.d/mirrorlist wird erst geschrieben, wenn du es geprüft und zum Speichern entschieden hast",
    "Countries": "Länder",
    "Sort by": "Sortieren nach",
    "How mirrors are ranked": "Wie Spiegelserver bewertet werden",
    "Score ↑  (best reliability first)": "Bewertung ↑  (beste Zuverlässigkeit zuerst)",
    "Score ↓  (worst reliability first)": "Bewertung ↓  (schlechteste Zuverlässigkeit zuerst)",
    "Delay ↑  (freshest mirrors first)": "Verzögerung ↑  (frischeste Spiegelserver zuerst)",
    "Delay ↓  (oldest mirrors first)": "Verzögerung ↓  (älteste Spiegelserver zuerst)",
    "Random   (shuffle before testing)": "Zufällig   (vor dem Test mischen)",
    "Comma-separated country names, or blank for all":
        "Kommagetrennte Ländernamen, oder leer für alle",
    "e.g. India, Germany, France": "z. B. Indien, Deutschland, Frankreich",
    "HTTPS only": "Nur HTTPS",
    "Filter out plain HTTP mirrors": "Reine HTTP-Spiegelserver herausfiltern",
    "Backup current mirrorlist": "Aktuelle Spiegelserverliste sichern",
    "Saves existing list to mirrorlist-backup first":
        "Sichert die bestehende Liste zuerst als mirrorlist-backup",
    "Max mirror delay (hours)": "Max. Verzögerung (Stunden)",
    "Skip mirrors that are behind by more than this":
        "Spiegelserver überspringen, die mehr als dies hinterherhinken",
    "Number of mirrors to keep": "Anzahl der zu behaltenden Spiegelserver",
    "0 = keep all ranked mirrors": "0 = alle bewerteten Spiegelserver behalten",
    "Find Fastest Mirrors": "Schnellste Spiegelserver finden",
    "Done — review the result below": "Fertig — Ergebnis unten prüfen",
    "Mirror Ranking Result": "Ergebnis der Spiegelserver-Bewertung",
    "{n} mirrors found — review below, then choose whether to save.":
        "{n} Spiegelserver gefunden — unten prüfen und dann entscheiden, ob gespeichert werden soll.",
    "# No output captured": "# Keine Ausgabe erfasst",
    "Save as New Mirrorlist": "Als neue Spiegelserverliste speichern",
    "Save Mirrorlist": "Spiegelserverliste speichern",
    "Done — backup saved to /etc/pacman.d/mirrorlist-backup":
        "Fertig — Sicherung gespeichert unter /etc/pacman.d/mirrorlist-backup",
    "Done — /etc/pacman.d/mirrorlist updated": "Fertig — /etc/pacman.d/mirrorlist aktualisiert",
    "rate-mirrors not installed": "rate-mirrors ist nicht installiert",
    "rate-mirrors uses geo-aware routing to benchmark\nall Arch mirrors and pick the fastest ones.":
        "rate-mirrors nutzt standortbasiertes Routing, um alle Arch-Spiegelserver\nzu testen und die schnellsten auszuwählen.",
    "Install rate-mirrors": "rate-mirrors installieren",
    "Install rate-mirrors ": "rate-mirrors installieren",

    # Orphan finder
    "Orphaned Packages": "Verwaiste Pakete",
    "No Orphans Found": "Keine Waisen gefunden",
    "Your system has no orphaned packages.": "Dein System hat keine verwaisten Pakete.",
    "{n} orphaned package(s) — pulled in automatically as a dependency at some point, but nothing on your system requires them anymore. Safe to remove, or leave them if you might need them again.":
        "{n} verwaiste(s) Paket(e) — irgendwann automatisch als Abhängigkeit mitinstalliert, aber nichts auf deinem System benötigt sie noch. Bedenkenlos entfernbar, oder einfach lassen, falls du sie doch nochmal brauchst.",
    "Remove All {n} Orphans": "Alle {n} Waisen entfernen",
    "Remove All Orphans": "Alle Waisen entfernen",

    # Clean cache dialog
    "What this does": "Was das macht",
    "Removes old cached package versions from /var/cache/pacman/pkg using paccache, keeping the 2 most recent versions of each package so you can still downgrade later if needed. Currently installed packages are never touched.":
        "Entfernt alte, zwischengespeicherte Paketversionen aus /var/cache/pacman/pkg mithilfe von paccache und behält dabei die jeweils 2 neuesten Versionen jedes Pakets, damit du bei Bedarf noch downgraden kannst. Installierte Pakete werden nie angetastet.",
    "paccache isn't installed, so this falls back to pacman's built-in cleanup (pacman -Sc), which removes cached versions of packages that are no longer installed, plus superseded old versions of packages you still have. Currently installed packages are never touched.":
        "paccache ist nicht installiert, daher wird auf die eingebaute Bereinigung von pacman (pacman -Sc) zurückgegriffen. Diese entfernt zwischengespeicherte Versionen nicht mehr installierter Pakete sowie überholte alte Versionen noch installierter Pakete. Installierte Pakete werden nie angetastet.",
    "Current Cache Size": "Aktuelle Cache-Größe",

    # System info
    "System Information": "Systeminformationen",
    "Gathering system info…": "Sammle Systeminformationen…",
    "System": "System",
    "OS": "Betriebssystem",
    "Desktop": "Desktop-Umgebung",
    "Kernel": "Kernel",
    "Hardware": "Hardware",
    "Processor": "Prozessor",
    "RAM": "RAM",
    "Disk (/)": "Festplatte (/)",
    "Disk Type": "Speichertyp",
    "Packages": "Pakete",
    "Pacman": "Pacman",
    "Installed Packages": "Installierte Pakete",
    "Foreign (AUR) Packages": "Fremde (AUR) Pakete",
    "Package Cache Size": "Größe des Paket-Caches",
    "Installed by Repository": "Installiert nach Repository",
    "How many installed packages come from each source":
        "Wie viele installierte Pakete aus welcher Quelle stammen",

    # History
    "Package History": "Paketverlauf",
    "Install, upgrade and removal events read from /var/log/pacman.log, newest first — for reference only, nothing here changes your system.":
        "Installations-, Aktualisierungs- und Entfernungs-Ereignisse aus /var/log/pacman.log, neueste zuerst — nur zur Information, hier wird nichts an deinem System verändert.",
    "Filter by package name…": "Nach Paketname filtern…",
    "No matching entries": "Keine passenden Einträge",

    # Downgrade
    "No Cached Versions": "Keine zwischengespeicherten Versionen",
    "No package files for {pkg} were found in /var/cache/pacman/pkg.\nOlder versions are only available while they remain in the cache.":
        "Für {pkg} wurden keine Paketdateien in /var/cache/pacman/pkg gefunden.\nÄltere Versionen sind nur verfügbar, solange sie im Cache vorhanden sind.",
    "{n} cached version(s) — pick one to install with pacman -U":
        "{n} zwischengespeicherte Version(en) — wähle eine zur Installation mit pacman -U",
    "Downgrade {pkg}": "{pkg} downgraden",
    "Downgrade {pkg} to {ver}": "{pkg} auf {ver} downgraden",

    # PKGBUILD
    "PKGBUILD — {pkg}": "PKGBUILD — {pkg}",
    "Loading PKGBUILD…": "Lade PKGBUILD…",

    # Pacdiff
    "Config Files (.pacnew / .pacsave)": "Konfigurationsdateien (.pacnew / .pacsave)",
    "Scanning for .pacnew/.pacsave files…": "Suche nach .pacnew-/.pacsave-Dateien…",
    "Nothing to Merge": "Nichts zusammenzuführen",
    "No .pacnew or .pacsave files were found.": "Es wurden keine .pacnew- oder .pacsave-Dateien gefunden.",
    "{n} file(s) left behind by package updates. Review the diff, then keep the new version or discard it.":
        "{n} Datei(en) wurden von Paketupdates zurückgelassen. Prüfe den Unterschied und behalte die neue Version oder verwirf sie.",
    "Loading diff…": "Lade Vergleich…",
    "Use New (overwrite)": "Neue verwenden (überschreiben)",
    "Discard": "Verwerfen",
    "Apply {name}": "{name} übernehmen",
    "Remove {name} ": "{name} entfernen",

    # Preferences
    "Preferences ": "Einstellungen",
    "General": "Allgemein",
    "AUR Helper": "AUR-Helfer",
    "Used for AUR installs, updates and PKGBUILDs":
        "Wird für AUR-Installationen, Updates und PKGBUILDs verwendet",
    "Auto-detect": "Automatisch erkennen",
    "None (pacman only)": "Keiner (nur pacman)",
    "Include AUR in update checks": "AUR bei Update-Prüfungen einbeziehen",
    "Behaviour": "Verhalten",
    "Confirm before removing packages": "Vor dem Entfernen von Paketen bestätigen",
    "Check for updates on startup": "Beim Start auf Updates prüfen",
    "Notify when updates are available": "Benachrichtigen, wenn Updates verfügbar sind",
    "Show Arch news before upgrades": "Arch-News vor Aktualisierungen anzeigen",
    "Warns about manual interventions before a system upgrade":
        "Warnt vor manuellen Eingriffen, bevor das System aktualisiert wird",
    "Background Service": "Hintergrunddienst",
    "Check for updates and notify even when Pachul is closed, via a systemd user timer":
        "Prüft auf Updates und benachrichtigt auch, wenn Pachul geschlossen ist, über einen systemd-Benutzer-Timer",
    "Check interval": "Prüfintervall",
    "Hourly": "Stündlich",
    "Every 6 hours": "Alle 6 Stunden",
    "Daily": "Täglich",
    "Run background update checks": "Update-Prüfungen im Hintergrund ausführen",
    "Language": "Sprache",
    "Changes apply immediately": "Änderungen wirken sich sofort aus",
    "English": "Englisch",
    "German": "Deutsch",
    "French": "Französisch",
    "Italian": "Italienisch",

    # Arch news
    "Arch Linux News": "Arch Linux News",
    "Fetching latest news…": "Lade aktuelle News…",
    "Could Not Fetch News": "News konnten nicht geladen werden",
    "You appear to be offline. You can still proceed with the upgrade.":
        "Du scheinst offline zu sein. Du kannst die Aktualisierung trotzdem fortsetzen.",
    "No Recent News": "Keine aktuellen News",
    "Review recent announcements before upgrading:":
        "Prüfe aktuelle Ankündigungen vor der Aktualisierung:",
    "Open": "Öffnen",

    # Keyboard shortcuts
    "Keyboard Shortcuts ": "Tastenkombinationen",
    "Focus search": "Suche fokussieren",
    "Sync databases": "Datenbanken synchronisieren",
    "Refresh package list": "Paketliste aktualisieren",
    "Check for updates": "Auf Updates prüfen",
    "Preferences  ": "Einstellungen",
    "Select all packages (batch mode)": "Alle Pakete auswählen (Batch-Modus)",
    "Deselect all packages (batch mode)": "Alle Pakete abwählen (Batch-Modus)",
    "Quit": "Beenden",
}


# ─── Translation table: English → Français ────────────────────────────────────
STRINGS_FR = {
    # ── App / window chrome ──────────────────────────────────────────────────
    "Select a Package": "Sélectionner un paquet",
    "Choose a package to view its details, files, and dependencies.":
        "Choisissez un paquet pour voir ses détails, ses fichiers et ses dépendances.",
    "Package": "Paquet",
    "Description": "Description",
    "INSTALLED": "INSTALLÉ",
    "UPDATE": "MISE À JOUR",
    "AUR": "AUR",
    "Install": "Installer",
    "Uninstall": "Désinstaller",
    "Reinstall": "Réinstaller",
    "Downgrade": "Rétrograder",
    "Update": "Mettre à jour",
    "Package Information": "Informations sur le paquet",
    "Raw Output": "Sortie brute",
    "pacman -Qi output": "Sortie de pacman -Qi",
    "Full package information": "Informations complètes sur le paquet",
    "Info": "Infos",
    "Files": "Fichiers",
    "Filter…": "Filtrer…",
    "Loading…": "Chargement…",
    "{shown} of {total} files": "{shown} sur {total} fichiers",
    "{total} files": "{total} fichiers",

    # Info field labels (DetailPanel.INFO_KEYS)
    "URL": "URL",
    "Licenses": "Licences",
    "Groups": "Groupes",
    "Depends On": "Dépend de",
    "Optional Deps": "Dépendances optionnelles",
    "Required By": "Requis par",
    "Conflicts With": "En conflit avec",
    "Provides": "Fournit",
    "Replaces": "Remplace",
    "Installed Size": "Taille installée",
    "Packager": "Empaqueteur",
    "Build Date": "Date de compilation",
    "Install Date": "Date d'installation",
    "Install Reason": "Motif d'installation",
    "Architecture": "Architecture",

    # Sidebar
    "Pachul": "Pachul",
    "A powerful Pacman/AUR front end.\n": "Une interface puissante pour Pacman/AUR.\n",
    "TOTAL": "TOTAL",
    "UPDATES": "MISES À JOUR",
    "BROWSE": "PARCOURIR",
    "Search": "Rechercher",
    "Updates": "Mises à jour",
    "Installed": "Installés",
    "AUR / Foreign": "AUR / Externe",
    "REPOSITORIES": "DÉPÔTS",
    "TOOLS": "OUTILS",
    "Check Updates": "Vérifier les mises à jour",
    "Rate Mirrors": "Évaluer les miroirs",
    "Find Orphans": "Trouver les orphelins",
    "Clean Cache": "Vider le cache",

    # Header menu
    "System upgrade (pacman -Syu)": "Mise à niveau du système (pacman -Syu)",
    "Sync Databases": "Synchroniser les bases de données",
    "Refresh Package Lists": "Actualiser les listes de paquets",
    "Downloads the latest package lists from your enabled repositories (pacman -Sy), so Pachul knows about new versions and new packages. This only refreshes metadata — nothing on your system is installed, removed, or upgraded.":
        "Télécharge les dernières listes de paquets de vos dépôts activés (pacman -Sy), afin que Pachul connaisse les nouvelles versions et les nouveaux paquets. Cela ne fait qu'actualiser les métadonnées — rien n'est installé, supprimé ou mis à niveau sur votre système.",
    "Check for Updates": "Vérifier les mises à jour",
    "Refresh List": "Actualiser la liste",
    "Manage Repositories…": "Gérer les dépôts…",
    "Rate Mirrors…": "Évaluer les miroirs…",
    "Config Files (.pacnew)…": "Fichiers de configuration (.pacnew)…",
    "Package History…": "Historique des paquets…",
    "System Info": "Informations système",
    "Cache Cleaner": "Nettoyeur de cache",
    "Export Package List…": "Exporter la liste des paquets…",
    "Import Package List…": "Importer une liste de paquets…",
    "View PKGBUILD (AUR)…": "Voir le PKGBUILD (AUR)…",
    "Hold / Unhold Selected": "Verrouiller/déverrouiller la sélection",
    "Mark Selected as Explicit": "Marquer la sélection comme explicite",
    "Mark Selected as Dependency": "Marquer la sélection comme dépendance",
    "Preferences": "Préférences",
    "Keyboard Shortcuts": "Raccourcis clavier",
    "About Pachul": "À propos de Pachul",
    "Upgrade Now": "Mettre à niveau maintenant",

    # Search page
    "Search Packages": "Rechercher des paquets",
    "Search official repos and AUR": "Rechercher dans les dépôts officiels et l'AUR",
    "Search packages, e.g. firefox, vlc, git…": "Rechercher des paquets, p. ex. firefox, vlc, git…",
    "Find Packages": "Trouver des paquets",
    "Type above to search the official repositories and AUR.":
        "Tapez ci-dessus pour rechercher dans les dépôts officiels et l'AUR.",
    "Searching…": "Recherche en cours…",
    "No Results": "Aucun résultat",
    "Try different keywords or check your spelling.":
        "Essayez d'autres mots-clés ou vérifiez l'orthographe.",
    "{n} result": "{n} résultat",
    "{n} results": "{n} résultats",

    # List panel
    "Loading packages…": "Chargement des paquets…",
    "System is up to date": "Le système est à jour",
    "No pending updates found.": "Aucune mise à jour en attente.",
    "No Packages Found": "Aucun paquet trouvé",
    "Try a different filter or search term.": "Essayez un autre filtre ou terme de recherche.",
    "Upgrade All": "Tout mettre à niveau",
    "{shown} of {total} packages": "{shown} sur {total} paquets",
    "{total} packages": "{total} paquets",
    "{n} update(s) available.": "{n} mise(s) à jour disponible(s).",
    "{n} update available": "{n} mise à jour disponible",
    "{n} updates available": "{n} mises à jour disponibles",

    # Status pills
    "UPDATE AVAILABLE": "MISE À JOUR DISPONIBLE",
    "INSTALLED (AUR)": "INSTALLÉ (AUR)",
    "AVAILABLE": "DISPONIBLE",
    "No description available.": "Aucune description disponible.",
    "Look up {dep}": "Rechercher {dep}",
    "+{n} more": "+{n} de plus",
    "{n} package": "{n} paquet",
    "{n} packages": "{n} paquets",

    # Toasts / actions
    "Select a package first": "Sélectionnez d'abord un paquet",
    "PKGBUILD is only available for AUR packages": "Le PKGBUILD n'est disponible que pour les paquets AUR",
    "Could not read /etc/pacman.conf": "Impossible de lire /etc/pacman.conf",
    "Unhold": "Déverrouiller",
    "Hold": "Verrouiller",
    "Hold {pkg}": "Verrouiller {pkg}",
    "Unhold {pkg}": "Déverrouiller {pkg}",
    "Allow {pkg} to Update Again": "Permettre à nouveau les mises à jour de {pkg}",
    "Removes {pkg} from IgnorePkg in /etc/pacman.conf. It will be included in system upgrades again from now on.":
        "Retire {pkg} de IgnorePkg dans /etc/pacman.conf. Il sera de nouveau inclus dans les mises à niveau du système à partir de maintenant.",
    "Pin {pkg} to Its Current Version": "Épingler {pkg} à sa version actuelle",
    "Adds {pkg} to IgnorePkg in /etc/pacman.conf. Held packages are skipped by system upgrades — useful if a specific version needs to stay put for compatibility — and won't update again until you unhold them.":
        "Ajoute {pkg} à IgnorePkg dans /etc/pacman.conf. Les paquets verrouillés sont ignorés lors des mises à niveau du système — utile si une version précise doit rester en place pour des raisons de compatibilité — et ne seront plus mis à jour tant que vous ne les déverrouillez pas.",
    "{verb} {name}": "{name} {verb}",
    "✓ {title} completed": "✓ {title} terminé",
    "✗ {title} failed (exit {code})": "✗ {title} a échoué (code {code})",
    "Sync Databases ": "Synchroniser les bases de données",
    "System Upgrade": "Mise à niveau du système",
    "Clean Cache ": "Vider le cache",
    "Mark {name} as explicit": "Marquer {name} comme explicite",
    "Mark {name} as dependency": "Marquer {name} comme dépendance",
    "Mark as Dependency": "Marquer comme dépendance",
    "Only changes {pkg}'s install-reason metadata to \"installed as a dependency\" — the package itself is not touched or removed right now. The effect: once nothing else on your system depends on {pkg} anymore, it will show up as an orphan and can be cleaned up later via \"Find Orphans\".":
        "Ne modifie que les métadonnées de raison d'installation de {pkg} en « installé comme dépendance » — le paquet lui-même n'est ni touché ni supprimé maintenant. Effet : dès que plus rien sur votre système ne dépend de {pkg}, il apparaîtra comme orphelin et pourra être nettoyé plus tard via « Trouver les orphelins ».",
    "Export Package List": "Exporter la liste des paquets",
    "pachul-packages.txt": "pachul-paquets.txt",
    "Exported {n} packages": "{n} paquets exportés",
    "Export failed: {err}": "Échec de l'exportation : {err}",
    "Save Installed Programs to a List": "Enregistrer les programmes installés dans une liste",
    "Writes the names of every package you explicitly installed yourself (one per line) to a plain text file — this deliberately excludes dependencies that were only pulled in automatically. Use \"Import Package List\" later, on this or another machine, to reinstall the same set of programs.":
        "Écrit les noms de tous les paquets que vous avez explicitement installés vous-même (un par ligne) dans un fichier texte brut — les dépendances installées uniquement automatiquement sont volontairement exclues. Utilisez ensuite « Importer une liste de paquets », sur cette machine ou une autre, pour réinstaller le même ensemble de programmes.",
    "Choose Location…": "Choisir un emplacement…",
    "Import Package List": "Importer une liste de paquets",
    "Install Programs From a Saved List": "Installer des programmes depuis une liste enregistrée",
    "Choose File…": "Choisir un fichier…",
    "Could not read file: {err}": "Impossible de lire le fichier : {err}",
    "No packages found in file": "Aucun paquet trouvé dans le fichier",
    "Install {n} packages": "Installer {n} paquets",
    "{n} packages found in file": "{n} paquets trouvés dans le fichier",
    "Reads one package name per line from the file (lines starting with # are ignored), then installs every listed package via {helper}, using --needed so anything already installed is skipped automatically. Nothing else on your system is changed.":
        "Lit un nom de paquet par ligne dans le fichier (les lignes commençant par # sont ignorées), puis installe chaque paquet listé via {helper}, avec --needed afin que tout ce qui est déjà installé soit automatiquement ignoré. Rien d'autre sur votre système n'est modifié.",
    "Reads one package name per line from the file (lines starting with # are ignored), then installs every listed package via pacman -S --needed, so anything already installed is skipped automatically. AUR packages in the list can't be installed this way since no AUR helper is configured — only official-repo packages will succeed. Nothing else on your system is changed.":
        "Lit un nom de paquet par ligne dans le fichier (les lignes commençant par # sont ignorées), puis installe chaque paquet listé via pacman -S --needed, afin que tout ce qui est déjà installé soit automatiquement ignoré. Les paquets AUR de la liste ne peuvent pas être installés ainsi puisqu'aucun assistant AUR n'est configuré — seuls les paquets des dépôts officiels réussiront. Rien d'autre sur votre système n'est modifié.",
    "Install {name}": "Installer {name}",
    "Remove {name}": "Supprimer {name}",
    "Reinstall {name}": "Réinstaller {name}",
    "Remove {name}?": "Supprimer {name} ?",
    "This will remove {name} ({version}) from your system.":
        "Cela supprimera {name} ({version}) de votre système.",
    "Cancel": "Annuler",
    "Remove": "Supprimer",
    "Updates Available": "Mises à jour disponibles",
    "{n} package update can be installed.": "{n} mise à jour de paquet peut être installée.",
    "{n} package updates can be installed.": "{n} mises à jour de paquets peuvent être installées.",

    # Multi-select / batch actions
    "Select multiple packages": "Sélectionner plusieurs paquets",
    "Select packages…": "Sélectionner des paquets…",
    "{n} selected": "{n} sélectionné(s)",
    "Install ({n})": "Installer ({n})",
    "Remove ({n})": "Supprimer ({n})",
    "Remove {n} packages": "Supprimer {n} paquets",
    "Remove {n} packages?": "Supprimer {n} paquets ?",
    "This will remove the {n} selected packages from your system.":
        "Cela supprimera les {n} paquets sélectionnés de votre système.",
    "No AUR helper found — skipped {n} AUR package(s).":
        "Aucun assistant AUR trouvé — {n} paquet(s) AUR ignoré(s).",

    # File search (pacman -F)
    "Find Package by File…": "Trouver un paquet par fichier…",
    "Find Package by File": "Trouver un paquet par fichier",
    "File database not synced yet — sync it to search":
        "Base de données des fichiers non synchronisée — synchronisez-la pour rechercher",
    "Sync Now": "Synchroniser maintenant",
    "e.g. libssl.so.3 or usr/bin/htop": "p. ex. libssl.so.3 ou usr/bin/htop",
    "Find out which package installs a given file or command.":
        "Découvrez quel paquet installe un fichier ou une commande donnée.",
    "No Package Found": "Aucun paquet trouvé",
    "No package provides a matching file.": "Aucun paquet ne fournit de fichier correspondant.",
    "… and {n} more files": "… et {n} fichiers supplémentaires",
    "Sync File Database": "Synchroniser la base de données des fichiers",

    # GPG / signature error handling
    "Unknown GPG key {id} detected": "Clé GPG inconnue {id} détectée",
    "Import & Retry": "Importer et réessayer",
    "Signature check failed — the keyring may be outdated":
        "Échec de la vérification de signature — le trousseau de clés est peut-être obsolète",
    "Update Keyring & Retry": "Mettre à jour le trousseau et réessayer",

    # Verrou de base de données pacman obsolète (db.lck)
    "Pacman database is locked (stale db.lck)": "La base de données pacman est verrouillée (db.lck obsolète)",
    "Remove Lock & Retry": "Supprimer le verrou et réessayer",
    "Something is still holding the database lock — not removing it.":
        "Quelque chose détient encore le verrou de la base de données — il n'est pas supprimé.",

    # Pre-upgrade snapshot (Timeshift/Snapper)
    "Create snapshot before system upgrades": "Créer un instantané avant les mises à jour système",
    "Safety net via Timeshift — restore point before every upgrade":
        "Filet de sécurité via Timeshift — point de restauration avant chaque mise à jour",
    "Safety net via Snapper (config: {config})":
        "Filet de sécurité via Snapper (config : {config})",
    "No Timeshift or Snapper installation found":
        "Aucune installation de Timeshift ou Snapper trouvée",

    # AUR metadata (votes / popularity / maintainer)
    "View on AUR (votes, comments, discussion)": "Voir sur AUR (votes, commentaires, discussion)",
    "A PKGBUILD is the build script an AUR package uses to compile and install itself. AUR packages aren't reviewed by Arch, so it's worth skimming this before installing.":
        "Un PKGBUILD est le script de compilation qu'utilise un paquet AUR pour se compiler et s'installer lui-même. Les paquets AUR ne sont pas vérifiés par Arch, il vaut donc la peine d'y jeter un œil avant d'installer.",
    "This AUR package is flagged out-of-date by its maintainer":
        "Ce paquet AUR est signalé comme obsolète par son mainteneur",
    "AUR info unavailable": "Infos AUR indisponibles",
    "Orphaned": "Orphelin",

    # Terminal dialog
    "Close": "Fermer",
    "Password or input — press Enter to send": "Mot de passe ou saisie — Entrée pour envoyer",
    "Send": "Envoyer",
    "Show/hide input": "Afficher/masquer la saisie",
    "(input sent)\n": "(saisie envoyée)\n",
    "\n— Cancelled —\n": "\n— Annulé —\n",
    "✓  Completed successfully\n": "✓  Terminé avec succès\n",
    "✗  Failed  (exit code {code})\n": "✗  Échec  (code de sortie {code})\n",
    "\nInternal error: {err}\n": "\nErreur interne : {err}\n",

    # Repo manager
    "Manage Repositories": "Gérer les dépôts",
    "Edit pacman.conf": "Modifier pacman.conf",
    "Edit pacman.conf ": "Modifier pacman.conf",
    "Active Repositories": "Dépôts actifs",
    "Repositories currently enabled in /etc/pacman.conf":
        "Dépôts actuellement activés dans /etc/pacman.conf",
    "{n} pkgs": "{n} paquets",
    "pacman.conf": "pacman.conf",
    "/etc/pacman.conf — read-only view": "/etc/pacman.conf — vue en lecture seule",
    "# /etc/pacman.conf not found or not readable":
        "# /etc/pacman.conf introuvable ou illisible",
    "Save": "Enregistrer",
    "Save pacman.conf": "Enregistrer pacman.conf",
    "Edit directly below, then click Save. Make sure the syntax stays valid — pacman will refuse to run on a broken config.":
        "Modifiez directement ci-dessous, puis cliquez sur Enregistrer. Veillez à garder une syntaxe valide — pacman refusera de fonctionner avec une configuration incorrecte.",

    # Mirror rater
    "Mirror Options": "Options des miroirs",
    "rate-mirrors tests all Arch mirrors and shows you the result — nothing is written to /etc/pacman.d/mirrorlist until you review it and choose to save":
        "rate-mirrors teste tous les miroirs Arch et vous montre le résultat — rien n'est écrit dans /etc/pacman.d/mirrorlist tant que vous ne l'avez pas vérifié et choisi de l'enregistrer",
    "Countries": "Pays",
    "Sort by": "Trier par",
    "How mirrors are ranked": "Comment les miroirs sont classés",
    "Score ↑  (best reliability first)": "Score ↑  (meilleure fiabilité en premier)",
    "Score ↓  (worst reliability first)": "Score ↓  (pire fiabilité en premier)",
    "Delay ↑  (freshest mirrors first)": "Délai ↑  (miroirs les plus récents en premier)",
    "Delay ↓  (oldest mirrors first)": "Délai ↓  (miroirs les plus anciens en premier)",
    "Random   (shuffle before testing)": "Aléatoire   (mélanger avant le test)",
    "Comma-separated country names, or blank for all":
        "Noms de pays séparés par des virgules, ou vide pour tous",
    "e.g. India, Germany, France": "p. ex. Inde, Allemagne, France",
    "HTTPS only": "HTTPS uniquement",
    "Filter out plain HTTP mirrors": "Exclure les miroirs HTTP non sécurisés",
    "Backup current mirrorlist": "Sauvegarder la liste de miroirs actuelle",
    "Saves existing list to mirrorlist-backup first":
        "Enregistre d'abord la liste existante dans mirrorlist-backup",
    "Max mirror delay (hours)": "Délai maximal des miroirs (heures)",
    "Skip mirrors that are behind by more than this":
        "Ignorer les miroirs en retard de plus que cette valeur",
    "Number of mirrors to keep": "Nombre de miroirs à conserver",
    "0 = keep all ranked mirrors": "0 = conserver tous les miroirs classés",
    "Find Fastest Mirrors": "Trouver les miroirs les plus rapides",
    "Done — review the result below": "Terminé — vérifiez le résultat ci-dessous",
    "Mirror Ranking Result": "Résultat du classement des miroirs",
    "{n} mirrors found — review below, then choose whether to save.":
        "{n} miroirs trouvés — vérifiez ci-dessous, puis choisissez d'enregistrer ou non.",
    "# No output captured": "# Aucune sortie capturée",
    "Save as New Mirrorlist": "Enregistrer comme nouvelle liste de miroirs",
    "Save Mirrorlist": "Enregistrer la liste de miroirs",
    "Done — backup saved to /etc/pacman.d/mirrorlist-backup":
        "Terminé — sauvegarde enregistrée dans /etc/pacman.d/mirrorlist-backup",
    "Done — /etc/pacman.d/mirrorlist updated": "Terminé — /etc/pacman.d/mirrorlist mis à jour",
    "rate-mirrors not installed": "rate-mirrors n'est pas installé",
    "rate-mirrors uses geo-aware routing to benchmark\nall Arch mirrors and pick the fastest ones.":
        "rate-mirrors utilise un routage géolocalisé pour évaluer\ntous les miroirs Arch et choisir les plus rapides.",
    "Install rate-mirrors": "Installer rate-mirrors",
    "Install rate-mirrors ": "Installer rate-mirrors",

    # Orphan finder
    "Orphaned Packages": "Paquets orphelins",
    "No Orphans Found": "Aucun orphelin trouvé",
    "Your system has no orphaned packages.": "Votre système n'a aucun paquet orphelin.",
    "{n} orphaned package(s) — pulled in automatically as a dependency at some point, but nothing on your system requires them anymore. Safe to remove, or leave them if you might need them again.":
        "{n} paquet(s) orphelin(s) — installé(s) automatiquement comme dépendance à un moment donné, mais plus rien sur votre système n'en a besoin. Peuvent être supprimés sans risque, ou laissés si vous pourriez en avoir de nouveau besoin.",
    "Remove All {n} Orphans": "Supprimer les {n} orphelins",
    "Remove All Orphans": "Supprimer tous les orphelins",

    # Clean cache dialog
    "What this does": "Ce que ça fait",
    "Removes old cached package versions from /var/cache/pacman/pkg using paccache, keeping the 2 most recent versions of each package so you can still downgrade later if needed. Currently installed packages are never touched.":
        "Supprime les anciennes versions de paquets mises en cache dans /var/cache/pacman/pkg via paccache, en conservant les 2 versions les plus récentes de chaque paquet afin de pouvoir revenir en arrière si besoin. Les paquets actuellement installés ne sont jamais touchés.",
    "paccache isn't installed, so this falls back to pacman's built-in cleanup (pacman -Sc), which removes cached versions of packages that are no longer installed, plus superseded old versions of packages you still have. Currently installed packages are never touched.":
        "paccache n'est pas installé, donc ceci utilise le nettoyage intégré de pacman (pacman -Sc), qui supprime les versions mises en cache des paquets qui ne sont plus installés, ainsi que les anciennes versions dépassées des paquets encore présents. Les paquets actuellement installés ne sont jamais touchés.",
    "Current Cache Size": "Taille actuelle du cache",

    # System info
    "System Information": "Informations système",
    "Gathering system info…": "Collecte des informations système…",
    "System": "Système",
    "OS": "Système d'exploitation",
    "Desktop": "Environnement de bureau",
    "Kernel": "Noyau",
    "Hardware": "Matériel",
    "Processor": "Processeur",
    "RAM": "RAM",
    "Disk (/)": "Disque (/)",
    "Disk Type": "Type de stockage",
    "Packages": "Paquets",
    "Pacman": "Pacman",
    "Installed Packages": "Paquets installés",
    "Foreign (AUR) Packages": "Paquets externes (AUR)",
    "Package Cache Size": "Taille du cache des paquets",
    "Installed by Repository": "Installés par dépôt",
    "How many installed packages come from each source":
        "Combien de paquets installés proviennent de chaque source",

    # History
    "Package History": "Historique des paquets",
    "Install, upgrade and removal events read from /var/log/pacman.log, newest first — for reference only, nothing here changes your system.":
        "Événements d'installation, de mise à niveau et de suppression lus dans /var/log/pacman.log, du plus récent au plus ancien — à titre informatif uniquement, rien ici ne modifie votre système.",
    "Filter by package name…": "Filtrer par nom de paquet…",
    "No matching entries": "Aucune entrée correspondante",

    # Downgrade
    "No Cached Versions": "Aucune version en cache",
    "No package files for {pkg} were found in /var/cache/pacman/pkg.\nOlder versions are only available while they remain in the cache.":
        "Aucun fichier de paquet pour {pkg} n'a été trouvé dans /var/cache/pacman/pkg.\nLes anciennes versions ne sont disponibles que tant qu'elles restent dans le cache.",
    "{n} cached version(s) — pick one to install with pacman -U":
        "{n} version(s) en cache — choisissez-en une à installer avec pacman -U",
    "Downgrade {pkg}": "Rétrograder {pkg}",
    "Downgrade {pkg} to {ver}": "Rétrograder {pkg} vers {ver}",

    # PKGBUILD
    "PKGBUILD — {pkg}": "PKGBUILD — {pkg}",
    "Loading PKGBUILD…": "Chargement du PKGBUILD…",

    # Pacdiff
    "Config Files (.pacnew / .pacsave)": "Fichiers de configuration (.pacnew / .pacsave)",
    "Scanning for .pacnew/.pacsave files…": "Recherche de fichiers .pacnew/.pacsave…",
    "Nothing to Merge": "Rien à fusionner",
    "No .pacnew or .pacsave files were found.": "Aucun fichier .pacnew ou .pacsave trouvé.",
    "{n} file(s) left behind by package updates. Review the diff, then keep the new version or discard it.":
        "{n} fichier(s) laissé(s) par les mises à jour de paquets. Examinez les différences, puis conservez la nouvelle version ou ignorez-la.",
    "Loading diff…": "Chargement des différences…",
    "Use New (overwrite)": "Utiliser la nouvelle (écraser)",
    "Discard": "Ignorer",
    "Apply {name}": "Appliquer {name}",
    "Remove {name} ": "Supprimer {name}",

    # Preferences
    "Preferences ": "Préférences",
    "General": "Général",
    "AUR Helper": "Assistant AUR",
    "Used for AUR installs, updates and PKGBUILDs":
        "Utilisé pour les installations, mises à jour et PKGBUILDs AUR",
    "Auto-detect": "Détection automatique",
    "None (pacman only)": "Aucun (pacman uniquement)",
    "Include AUR in update checks": "Inclure l'AUR dans la vérification des mises à jour",
    "Behaviour": "Comportement",
    "Confirm before removing packages": "Confirmer avant de supprimer des paquets",
    "Check for updates on startup": "Vérifier les mises à jour au démarrage",
    "Notify when updates are available": "Notifier lorsque des mises à jour sont disponibles",
    "Show Arch news before upgrades": "Afficher les actualités Arch avant les mises à niveau",
    "Warns about manual interventions before a system upgrade":
        "Avertit des interventions manuelles avant une mise à niveau système",
    "Background Service": "Service en arrière-plan",
    "Check for updates and notify even when Pachul is closed, via a systemd user timer":
        "Vérifie les mises à jour et notifie même lorsque Pachul est fermé, via un timer systemd utilisateur",
    "Check interval": "Intervalle de vérification",
    "Hourly": "Toutes les heures",
    "Every 6 hours": "Toutes les 6 heures",
    "Daily": "Quotidien",
    "Run background update checks": "Exécuter les vérifications en arrière-plan",
    "Language": "Langue",
    "Changes apply immediately": "Les changements s'appliquent immédiatement",
    "English": "Anglais",
    "German": "Allemand",
    "French": "Français",
    "Italian": "Italien",

    # Arch news
    "Arch Linux News": "Actualités Arch Linux",
    "Fetching latest news…": "Récupération des dernières actualités…",
    "Could Not Fetch News": "Impossible de récupérer les actualités",
    "You appear to be offline. You can still proceed with the upgrade.":
        "Vous semblez être hors ligne. Vous pouvez tout de même poursuivre la mise à niveau.",
    "No Recent News": "Aucune actualité récente",
    "Review recent announcements before upgrading:":
        "Examinez les annonces récentes avant la mise à niveau :",
    "Open": "Ouvrir",

    # Keyboard shortcuts
    "Keyboard Shortcuts ": "Raccourcis clavier",
    "Focus search": "Focaliser la recherche",
    "Sync databases": "Synchroniser les bases de données",
    "Refresh package list": "Actualiser la liste des paquets",
    "Check for updates": "Vérifier les mises à jour",
    "Preferences  ": "Préférences",
    "Select all packages (batch mode)": "Sélectionner tous les paquets (mode batch)",
    "Deselect all packages (batch mode)": "Désélectionner tous les paquets (mode batch)",
    "Quit": "Quitter",
}


# ─── Translation table: English → Italiano ─────────────────────────────────────
STRINGS_IT = {
    # ── App / window chrome ──────────────────────────────────────────────────
    "Select a Package": "Seleziona un pacchetto",
    "Choose a package to view its details, files, and dependencies.":
        "Scegli un pacchetto per visualizzarne dettagli, file e dipendenze.",
    "Package": "Pacchetto",
    "Description": "Descrizione",
    "INSTALLED": "INSTALLATO",
    "UPDATE": "AGGIORNAMENTO",
    "AUR": "AUR",
    "Install": "Installa",
    "Uninstall": "Disinstalla",
    "Reinstall": "Reinstalla",
    "Downgrade": "Retrocedi",
    "Update": "Aggiorna",
    "Package Information": "Informazioni sul pacchetto",
    "Raw Output": "Output grezzo",
    "pacman -Qi output": "Output di pacman -Qi",
    "Full package information": "Informazioni complete sul pacchetto",
    "Info": "Info",
    "Files": "File",
    "Filter…": "Filtra…",
    "Loading…": "Caricamento…",
    "{shown} of {total} files": "{shown} di {total} file",
    "{total} files": "{total} file",

    # Info field labels (DetailPanel.INFO_KEYS)
    "URL": "URL",
    "Licenses": "Licenze",
    "Groups": "Gruppi",
    "Depends On": "Dipende da",
    "Optional Deps": "Dipendenze opzionali",
    "Required By": "Richiesto da",
    "Conflicts With": "In conflitto con",
    "Provides": "Fornisce",
    "Replaces": "Sostituisce",
    "Installed Size": "Dimensione installata",
    "Packager": "Responsabile pacchetto",
    "Build Date": "Data di compilazione",
    "Install Date": "Data di installazione",
    "Install Reason": "Motivo dell'installazione",
    "Architecture": "Architettura",

    # Sidebar
    "Pachul": "Pachul",
    "A powerful Pacman/AUR front end.\n": "Un'interfaccia potente per Pacman/AUR.\n",
    "TOTAL": "TOTALE",
    "UPDATES": "AGGIORNAMENTI",
    "BROWSE": "ESPLORA",
    "Search": "Cerca",
    "Updates": "Aggiornamenti",
    "Installed": "Installati",
    "AUR / Foreign": "AUR / Esterni",
    "REPOSITORIES": "REPOSITORY",
    "TOOLS": "STRUMENTI",
    "Check Updates": "Controlla aggiornamenti",
    "Rate Mirrors": "Valuta i mirror",
    "Find Orphans": "Trova orfani",
    "Clean Cache": "Pulisci cache",

    # Header menu
    "System upgrade (pacman -Syu)": "Aggiornamento del sistema (pacman -Syu)",
    "Sync Databases": "Sincronizza database",
    "Refresh Package Lists": "Aggiorna elenchi pacchetti",
    "Downloads the latest package lists from your enabled repositories (pacman -Sy), so Pachul knows about new versions and new packages. This only refreshes metadata — nothing on your system is installed, removed, or upgraded.":
        "Scarica gli elenchi aggiornati dei pacchetti dai repository abilitati (pacman -Sy), così Pachul conosce le nuove versioni e i nuovi pacchetti disponibili. Vengono aggiornati solo i metadati — nulla viene installato, rimosso o aggiornato sul sistema.",
    "Check for Updates": "Controlla aggiornamenti",
    "Refresh List": "Aggiorna elenco",
    "Manage Repositories…": "Gestisci repository…",
    "Rate Mirrors…": "Valuta i mirror…",
    "Config Files (.pacnew)…": "File di configurazione (.pacnew)…",
    "Package History…": "Cronologia pacchetti…",
    "System Info": "Informazioni di sistema",
    "Cache Cleaner": "Pulizia cache",
    "Export Package List…": "Esporta elenco pacchetti…",
    "Import Package List…": "Importa elenco pacchetti…",
    "View PKGBUILD (AUR)…": "Visualizza PKGBUILD (AUR)…",
    "Hold / Unhold Selected": "Blocca/sblocca selezione",
    "Mark Selected as Explicit": "Segna selezione come esplicita",
    "Mark Selected as Dependency": "Segna selezione come dipendenza",
    "Preferences": "Preferenze",
    "Keyboard Shortcuts": "Scorciatoie da tastiera",
    "About Pachul": "Informazioni su Pachul",
    "Upgrade Now": "Aggiorna ora",

    # Search page
    "Search Packages": "Cerca pacchetti",
    "Search official repos and AUR": "Cerca nei repository ufficiali e nell'AUR",
    "Search packages, e.g. firefox, vlc, git…": "Cerca pacchetti, es. firefox, vlc, git…",
    "Find Packages": "Trova pacchetti",
    "Type above to search the official repositories and AUR.":
        "Digita qui sopra per cercare nei repository ufficiali e nell'AUR.",
    "Searching…": "Ricerca in corso…",
    "No Results": "Nessun risultato",
    "Try different keywords or check your spelling.":
        "Prova con altre parole chiave o controlla l'ortografia.",
    "{n} result": "{n} risultato",
    "{n} results": "{n} risultati",

    # List panel
    "Loading packages…": "Caricamento pacchetti…",
    "System is up to date": "Il sistema è aggiornato",
    "No pending updates found.": "Nessun aggiornamento in sospeso.",
    "No Packages Found": "Nessun pacchetto trovato",
    "Try a different filter or search term.": "Prova un filtro o un termine di ricerca diverso.",
    "Upgrade All": "Aggiorna tutto",
    "{shown} of {total} packages": "{shown} di {total} pacchetti",
    "{total} packages": "{total} pacchetti",
    "{n} update(s) available.": "{n} aggiornamento/i disponibile/i.",
    "{n} update available": "{n} aggiornamento disponibile",
    "{n} updates available": "{n} aggiornamenti disponibili",

    # Status pills
    "UPDATE AVAILABLE": "AGGIORNAMENTO DISPONIBILE",
    "INSTALLED (AUR)": "INSTALLATO (AUR)",
    "AVAILABLE": "DISPONIBILE",
    "No description available.": "Nessuna descrizione disponibile.",
    "Look up {dep}": "Cerca {dep}",
    "+{n} more": "+{n} altri",
    "{n} package": "{n} pacchetto",
    "{n} packages": "{n} pacchetti",

    # Toasts / actions
    "Select a package first": "Seleziona prima un pacchetto",
    "PKGBUILD is only available for AUR packages": "Il PKGBUILD è disponibile solo per i pacchetti AUR",
    "Could not read /etc/pacman.conf": "Impossibile leggere /etc/pacman.conf",
    "Unhold": "Sblocca",
    "Hold": "Blocca",
    "Hold {pkg}": "Blocca {pkg}",
    "Unhold {pkg}": "Sblocca {pkg}",
    "Allow {pkg} to Update Again": "Permetti di nuovo l'aggiornamento di {pkg}",
    "Removes {pkg} from IgnorePkg in /etc/pacman.conf. It will be included in system upgrades again from now on.":
        "Rimuove {pkg} da IgnorePkg in /etc/pacman.conf. D'ora in poi sarà di nuovo incluso negli aggiornamenti di sistema.",
    "Pin {pkg} to Its Current Version": "Blocca {pkg} alla versione attuale",
    "Adds {pkg} to IgnorePkg in /etc/pacman.conf. Held packages are skipped by system upgrades — useful if a specific version needs to stay put for compatibility — and won't update again until you unhold them.":
        "Aggiunge {pkg} a IgnorePkg in /etc/pacman.conf. I pacchetti bloccati vengono saltati durante gli aggiornamenti di sistema — utile se una versione specifica deve restare invariata per motivi di compatibilità — e non verranno aggiornati finché non li sblocchi.",
    "{verb} {name}": "{name} {verb}",
    "✓ {title} completed": "✓ {title} completato",
    "✗ {title} failed (exit {code})": "✗ {title} non riuscito (uscita {code})",
    "Sync Databases ": "Sincronizza database",
    "System Upgrade": "Aggiornamento del sistema",
    "Clean Cache ": "Pulisci cache",
    "Mark {name} as explicit": "Segna {name} come esplicito",
    "Mark {name} as dependency": "Segna {name} come dipendenza",
    "Mark as Dependency": "Segna come dipendenza",
    "Only changes {pkg}'s install-reason metadata to \"installed as a dependency\" — the package itself is not touched or removed right now. The effect: once nothing else on your system depends on {pkg} anymore, it will show up as an orphan and can be cleaned up later via \"Find Orphans\".":
        "Cambia solo i metadati del motivo di installazione di {pkg} in \"installato come dipendenza\" — il pacchetto stesso non viene toccato o rimosso ora. L'effetto: quando nient'altro sul sistema dipenderà più da {pkg}, comparirà come orfano e potrà essere rimosso in seguito tramite \"Trova orfani\".",
    "Export Package List": "Esporta elenco pacchetti",
    "pachul-packages.txt": "pachul-pacchetti.txt",
    "Exported {n} packages": "{n} pacchetti esportati",
    "Export failed: {err}": "Esportazione non riuscita: {err}",
    "Save Installed Programs to a List": "Salva i programmi installati in un elenco",
    "Writes the names of every package you explicitly installed yourself (one per line) to a plain text file — this deliberately excludes dependencies that were only pulled in automatically. Use \"Import Package List\" later, on this or another machine, to reinstall the same set of programs.":
        "Scrive i nomi di tutti i pacchetti che hai installato esplicitamente tu stesso (uno per riga) in un file di testo semplice — le dipendenze installate solo automaticamente vengono deliberatamente escluse. Usa poi \"Importa elenco pacchetti\", su questo o un altro computer, per reinstallare lo stesso insieme di programmi.",
    "Choose Location…": "Scegli posizione…",
    "Import Package List": "Importa elenco pacchetti",
    "Install Programs From a Saved List": "Installa programmi da un elenco salvato",
    "Choose File…": "Scegli file…",
    "Could not read file: {err}": "Impossibile leggere il file: {err}",
    "No packages found in file": "Nessun pacchetto trovato nel file",
    "Install {n} packages": "Installa {n} pacchetti",
    "{n} packages found in file": "{n} pacchetti trovati nel file",
    "Reads one package name per line from the file (lines starting with # are ignored), then installs every listed package via {helper}, using --needed so anything already installed is skipped automatically. Nothing else on your system is changed.":
        "Legge un nome di pacchetto per riga dal file (le righe che iniziano con # vengono ignorate), quindi installa ogni pacchetto elencato tramite {helper}, usando --needed in modo che ciò che è già installato venga saltato automaticamente. Nient'altro sul sistema viene modificato.",
    "Reads one package name per line from the file (lines starting with # are ignored), then installs every listed package via pacman -S --needed, so anything already installed is skipped automatically. AUR packages in the list can't be installed this way since no AUR helper is configured — only official-repo packages will succeed. Nothing else on your system is changed.":
        "Legge un nome di pacchetto per riga dal file (le righe che iniziano con # vengono ignorate), quindi installa ogni pacchetto elencato tramite pacman -S --needed, in modo che ciò che è già installato venga saltato automaticamente. I pacchetti AUR nell'elenco non possono essere installati in questo modo poiché non è configurato alcun helper AUR — riusciranno solo i pacchetti dei repository ufficiali. Nient'altro sul sistema viene modificato.",
    "Install {name}": "Installa {name}",
    "Remove {name}": "Rimuovi {name}",
    "Reinstall {name}": "Reinstalla {name}",
    "Remove {name}?": "Rimuovere {name}?",
    "This will remove {name} ({version}) from your system.":
        "Questo rimuoverà {name} ({version}) dal sistema.",
    "Cancel": "Annulla",
    "Remove": "Rimuovi",
    "Updates Available": "Aggiornamenti disponibili",
    "{n} package update can be installed.": "È disponibile {n} aggiornamento di pacchetto da installare.",
    "{n} package updates can be installed.": "Sono disponibili {n} aggiornamenti di pacchetti da installare.",

    # Multi-select / batch actions
    "Select multiple packages": "Seleziona più pacchetti",
    "Select packages…": "Seleziona pacchetti…",
    "{n} selected": "{n} selezionati",
    "Install ({n})": "Installa ({n})",
    "Remove ({n})": "Rimuovi ({n})",
    "Remove {n} packages": "Rimuovi {n} pacchetti",
    "Remove {n} packages?": "Rimuovere {n} pacchetti?",
    "This will remove the {n} selected packages from your system.":
        "Questo rimuoverà i {n} pacchetti selezionati dal sistema.",
    "No AUR helper found — skipped {n} AUR package(s).":
        "Nessun helper AUR trovato — {n} pacchetto/i AUR saltato/i.",

    # File search (pacman -F)
    "Find Package by File…": "Trova pacchetto per file…",
    "Find Package by File": "Trova pacchetto per file",
    "File database not synced yet — sync it to search":
        "Database dei file non ancora sincronizzato — sincronizzalo per cercare",
    "Sync Now": "Sincronizza ora",
    "e.g. libssl.so.3 or usr/bin/htop": "es. libssl.so.3 o usr/bin/htop",
    "Find out which package installs a given file or command.":
        "Scopri quale pacchetto installa un determinato file o comando.",
    "No Package Found": "Nessun pacchetto trovato",
    "No package provides a matching file.": "Nessun pacchetto fornisce un file corrispondente.",
    "… and {n} more files": "… e altri {n} file",
    "Sync File Database": "Sincronizza database dei file",

    # GPG / signature error handling
    "Unknown GPG key {id} detected": "Chiave GPG sconosciuta {id} rilevata",
    "Import & Retry": "Importa e riprova",
    "Signature check failed — the keyring may be outdated":
        "Verifica della firma non riuscita — il portachiavi potrebbe non essere aggiornato",
    "Update Keyring & Retry": "Aggiorna portachiavi e riprova",

    # Blocco obsoleto del database pacman (db.lck)
    "Pacman database is locked (stale db.lck)": "Il database di pacman è bloccato (db.lck obsoleto)",
    "Remove Lock & Retry": "Rimuovi blocco e riprova",
    "Something is still holding the database lock — not removing it.":
        "Qualcosa detiene ancora il blocco del database — non viene rimosso.",

    # Pre-upgrade snapshot (Timeshift/Snapper)
    "Create snapshot before system upgrades": "Crea uno snapshot prima degli aggiornamenti di sistema",
    "Safety net via Timeshift — restore point before every upgrade":
        "Rete di sicurezza tramite Timeshift — punto di ripristino prima di ogni aggiornamento",
    "Safety net via Snapper (config: {config})":
        "Rete di sicurezza tramite Snapper (configurazione: {config})",
    "No Timeshift or Snapper installation found":
        "Nessuna installazione di Timeshift o Snapper trovata",

    # AUR metadata (votes / popularity / maintainer)
    "View on AUR (votes, comments, discussion)": "Vedi su AUR (voti, commenti, discussione)",
    "A PKGBUILD is the build script an AUR package uses to compile and install itself. AUR packages aren't reviewed by Arch, so it's worth skimming this before installing.":
        "Un PKGBUILD è lo script di compilazione che un pacchetto AUR usa per compilarsi e installarsi da solo. I pacchetti AUR non vengono controllati da Arch, quindi vale la pena darci un'occhiata prima di installare.",
    "This AUR package is flagged out-of-date by its maintainer":
        "Questo pacchetto AUR è segnalato come obsoleto dal manutentore",
    "AUR info unavailable": "Informazioni AUR non disponibili",
    "Orphaned": "Orfano",

    # Terminal dialog
    "Close": "Chiudi",
    "Password or input — press Enter to send": "Password o input — premi Invio per inviare",
    "Send": "Invia",
    "Show/hide input": "Mostra/nascondi input",
    "(input sent)\n": "(input inviato)\n",
    "\n— Cancelled —\n": "\n— Annullato —\n",
    "✓  Completed successfully\n": "✓  Completato con successo\n",
    "✗  Failed  (exit code {code})\n": "✗  Non riuscito  (codice di uscita {code})\n",
    "\nInternal error: {err}\n": "\nErrore interno: {err}\n",

    # Repo manager
    "Manage Repositories": "Gestisci repository",
    "Edit pacman.conf": "Modifica pacman.conf",
    "Edit pacman.conf ": "Modifica pacman.conf",
    "Active Repositories": "Repository attivi",
    "Repositories currently enabled in /etc/pacman.conf":
        "Repository attualmente abilitati in /etc/pacman.conf",
    "{n} pkgs": "{n} pacchetti",
    "pacman.conf": "pacman.conf",
    "/etc/pacman.conf — read-only view": "/etc/pacman.conf — vista di sola lettura",
    "# /etc/pacman.conf not found or not readable":
        "# /etc/pacman.conf non trovato o non leggibile",
    "Save": "Salva",
    "Save pacman.conf": "Salva pacman.conf",
    "Edit directly below, then click Save. Make sure the syntax stays valid — pacman will refuse to run on a broken config.":
        "Modifica direttamente qui sotto, poi fai clic su Salva. Assicurati che la sintassi resti valida — pacman si rifiuterà di funzionare con una configurazione non corretta.",

    # Mirror rater
    "Mirror Options": "Opzioni mirror",
    "rate-mirrors tests all Arch mirrors and shows you the result — nothing is written to /etc/pacman.d/mirrorlist until you review it and choose to save":
        "rate-mirrors testa tutti i mirror Arch e mostra il risultato — non viene scritto nulla in /etc/pacman.d/mirrorlist finché non lo controlli e scegli di salvare",
    "Countries": "Paesi",
    "Sort by": "Ordina per",
    "How mirrors are ranked": "Come vengono classificati i mirror",
    "Score ↑  (best reliability first)": "Punteggio ↑  (migliore affidabilità prima)",
    "Score ↓  (worst reliability first)": "Punteggio ↓  (peggiore affidabilità prima)",
    "Delay ↑  (freshest mirrors first)": "Ritardo ↑  (mirror più recenti prima)",
    "Delay ↓  (oldest mirrors first)": "Ritardo ↓  (mirror più vecchi prima)",
    "Random   (shuffle before testing)": "Casuale   (mescola prima del test)",
    "Comma-separated country names, or blank for all":
        "Nomi dei paesi separati da virgola, o vuoto per tutti",
    "e.g. India, Germany, France": "es. India, Germania, Francia",
    "HTTPS only": "Solo HTTPS",
    "Filter out plain HTTP mirrors": "Escludi i mirror HTTP non protetti",
    "Backup current mirrorlist": "Backup della lista mirror attuale",
    "Saves existing list to mirrorlist-backup first":
        "Salva prima la lista esistente in mirrorlist-backup",
    "Max mirror delay (hours)": "Ritardo massimo mirror (ore)",
    "Skip mirrors that are behind by more than this":
        "Salta i mirror che sono indietro più di questo valore",
    "Number of mirrors to keep": "Numero di mirror da mantenere",
    "0 = keep all ranked mirrors": "0 = mantieni tutti i mirror classificati",
    "Find Fastest Mirrors": "Trova i mirror più veloci",
    "Done — review the result below": "Fatto — controlla il risultato qui sotto",
    "Mirror Ranking Result": "Risultato della classifica dei mirror",
    "{n} mirrors found — review below, then choose whether to save.":
        "{n} mirror trovati — controlla qui sotto, poi scegli se salvare.",
    "# No output captured": "# Nessun output acquisito",
    "Save as New Mirrorlist": "Salva come nuova lista mirror",
    "Save Mirrorlist": "Salva lista mirror",
    "Done — backup saved to /etc/pacman.d/mirrorlist-backup":
        "Fatto — backup salvato in /etc/pacman.d/mirrorlist-backup",
    "Done — /etc/pacman.d/mirrorlist updated": "Fatto — /etc/pacman.d/mirrorlist aggiornato",
    "rate-mirrors not installed": "rate-mirrors non installato",
    "rate-mirrors uses geo-aware routing to benchmark\nall Arch mirrors and pick the fastest ones.":
        "rate-mirrors utilizza un instradamento geolocalizzato per testare\ntutti i mirror Arch e scegliere i più veloci.",
    "Install rate-mirrors": "Installa rate-mirrors",
    "Install rate-mirrors ": "Installa rate-mirrors",

    # Orphan finder
    "Orphaned Packages": "Pacchetti orfani",
    "No Orphans Found": "Nessun orfano trovato",
    "Your system has no orphaned packages.": "Il sistema non ha pacchetti orfani.",
    "{n} orphaned package(s) — pulled in automatically as a dependency at some point, but nothing on your system requires them anymore. Safe to remove, or leave them if you might need them again.":
        "{n} pacchetto/i orfano/i — installato/i automaticamente come dipendenza in un certo momento, ma nulla sul sistema ne ha più bisogno. Puoi rimuoverli senza problemi, oppure lasciarli se pensi di poterne aver bisogno di nuovo.",
    "Remove All {n} Orphans": "Rimuovi tutti i {n} orfani",
    "Remove All Orphans": "Rimuovi tutti gli orfani",

    # Clean cache dialog
    "What this does": "Cosa fa questa funzione",
    "Removes old cached package versions from /var/cache/pacman/pkg using paccache, keeping the 2 most recent versions of each package so you can still downgrade later if needed. Currently installed packages are never touched.":
        "Rimuove le vecchie versioni dei pacchetti in cache da /var/cache/pacman/pkg usando paccache, mantenendo le 2 versioni più recenti di ciascun pacchetto in modo da poter fare comunque un downgrade in seguito, se necessario. I pacchetti attualmente installati non vengono mai toccati.",
    "paccache isn't installed, so this falls back to pacman's built-in cleanup (pacman -Sc), which removes cached versions of packages that are no longer installed, plus superseded old versions of packages you still have. Currently installed packages are never touched.":
        "paccache non è installato, quindi viene usata la pulizia integrata di pacman (pacman -Sc), che rimuove le versioni in cache dei pacchetti non più installati, oltre alle vecchie versioni superate dei pacchetti ancora presenti. I pacchetti attualmente installati non vengono mai toccati.",
    "Current Cache Size": "Dimensione attuale della cache",

    # System info
    "System Information": "Informazioni di sistema",
    "Gathering system info…": "Raccolta informazioni di sistema…",
    "System": "Sistema",
    "OS": "Sistema operativo",
    "Desktop": "Ambiente desktop",
    "Kernel": "Kernel",
    "Hardware": "Hardware",
    "Processor": "Processore",
    "RAM": "RAM",
    "Disk (/)": "Disco (/)",
    "Disk Type": "Tipo di archiviazione",
    "Packages": "Pacchetti",
    "Pacman": "Pacman",
    "Installed Packages": "Pacchetti installati",
    "Foreign (AUR) Packages": "Pacchetti esterni (AUR)",
    "Package Cache Size": "Dimensione cache pacchetti",
    "Installed by Repository": "Installati per repository",
    "How many installed packages come from each source":
        "Quanti pacchetti installati provengono da ciascuna fonte",

    # History
    "Package History": "Cronologia pacchetti",
    "Install, upgrade and removal events read from /var/log/pacman.log, newest first — for reference only, nothing here changes your system.":
        "Eventi di installazione, aggiornamento e rimozione letti da /var/log/pacman.log, dal più recente — solo a titolo informativo, qui non viene modificato nulla nel sistema.",
    "Filter by package name…": "Filtra per nome pacchetto…",
    "No matching entries": "Nessuna voce corrispondente",

    # Downgrade
    "No Cached Versions": "Nessuna versione in cache",
    "No package files for {pkg} were found in /var/cache/pacman/pkg.\nOlder versions are only available while they remain in the cache.":
        "Non sono stati trovati file del pacchetto {pkg} in /var/cache/pacman/pkg.\nLe versioni precedenti sono disponibili solo finché restano nella cache.",
    "{n} cached version(s) — pick one to install with pacman -U":
        "{n} versione/i in cache — scegline una da installare con pacman -U",
    "Downgrade {pkg}": "Retrocedi {pkg}",
    "Downgrade {pkg} to {ver}": "Retrocedi {pkg} a {ver}",

    # PKGBUILD
    "PKGBUILD — {pkg}": "PKGBUILD — {pkg}",
    "Loading PKGBUILD…": "Caricamento PKGBUILD…",

    # Pacdiff
    "Config Files (.pacnew / .pacsave)": "File di configurazione (.pacnew / .pacsave)",
    "Scanning for .pacnew/.pacsave files…": "Ricerca file .pacnew/.pacsave…",
    "Nothing to Merge": "Niente da unire",
    "No .pacnew or .pacsave files were found.": "Non è stato trovato alcun file .pacnew o .pacsave.",
    "{n} file(s) left behind by package updates. Review the diff, then keep the new version or discard it.":
        "{n} file lasciato/i dagli aggiornamenti dei pacchetti. Controlla le differenze, poi mantieni la nuova versione oppure scartala.",
    "Loading diff…": "Caricamento differenze…",
    "Use New (overwrite)": "Usa nuovo (sovrascrivi)",
    "Discard": "Scarta",
    "Apply {name}": "Applica {name}",
    "Remove {name} ": "Rimuovi {name}",

    # Preferences
    "Preferences ": "Preferenze",
    "General": "Generale",
    "AUR Helper": "Helper AUR",
    "Used for AUR installs, updates and PKGBUILDs":
        "Usato per installazioni, aggiornamenti e PKGBUILD dell'AUR",
    "Auto-detect": "Rilevamento automatico",
    "None (pacman only)": "Nessuno (solo pacman)",
    "Include AUR in update checks": "Includi l'AUR nel controllo aggiornamenti",
    "Behaviour": "Comportamento",
    "Confirm before removing packages": "Conferma prima di rimuovere i pacchetti",
    "Check for updates on startup": "Controlla aggiornamenti all'avvio",
    "Notify when updates are available": "Notifica quando sono disponibili aggiornamenti",
    "Show Arch news before upgrades": "Mostra le notizie di Arch prima degli aggiornamenti",
    "Warns about manual interventions before a system upgrade":
        "Avvisa di interventi manuali prima di un aggiornamento di sistema",
    "Background Service": "Servizio in background",
    "Check for updates and notify even when Pachul is closed, via a systemd user timer":
        "Controlla gli aggiornamenti e notifica anche quando Pachul è chiuso, tramite un timer utente systemd",
    "Check interval": "Intervallo di controllo",
    "Hourly": "Ogni ora",
    "Every 6 hours": "Ogni 6 ore",
    "Daily": "Giornaliero",
    "Run background update checks": "Esegui controlli aggiornamenti in background",
    "Language": "Lingua",
    "Changes apply immediately": "Le modifiche si applicano immediatamente",
    "English": "Inglese",
    "German": "Tedesco",
    "French": "Francese",
    "Italian": "Italiano",

    # Arch news
    "Arch Linux News": "Notizie di Arch Linux",
    "Fetching latest news…": "Recupero ultime notizie…",
    "Could Not Fetch News": "Impossibile recuperare le notizie",
    "You appear to be offline. You can still proceed with the upgrade.":
        "Sembra che tu sia offline. Puoi comunque procedere con l'aggiornamento.",
    "No Recent News": "Nessuna notizia recente",
    "Review recent announcements before upgrading:":
        "Rivedi gli annunci recenti prima di aggiornare:",
    "Open": "Apri",

    # Keyboard shortcuts
    "Keyboard Shortcuts ": "Scorciatoie da tastiera",
    "Focus search": "Vai alla ricerca",
    "Sync databases": "Sincronizza database",
    "Refresh package list": "Aggiorna elenco pacchetti",
    "Check for updates": "Controlla aggiornamenti",
    "Preferences  ": "Preferenze",
    "Select all packages (batch mode)": "Seleziona tutti i pacchetti (modalità batch)",
    "Deselect all packages (batch mode)": "Deseleziona tutti i pacchetti (modalità batch)",
    "Quit": "Esci",
}


_TABLES = {
    "de": STRINGS_DE,
    "fr": STRINGS_FR,
    "it": STRINGS_IT,
}

# Kept for backward compatibility (some code may still reference STRINGS directly)
STRINGS = STRINGS_DE
