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
    "All Packages": "Alle Pakete",
    "Search packages, e.g. firefox, vlc, git…": "Pakete suchen, z. B. firefox, vlc, git…",
    "Updates": "Updates",
    "Installed": "Installiert",
    "New Packages": "Neue Pakete",
    "AUR / Foreign": "AUR / Fremd",
    "REPOSITORIES": "REPOSITORIES",
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
    "Config File Conflicts…": "Konfigurationsdatei-Konflikte…",
    "Config File Conflicts": "Konfigurationsdatei-Konflikte",
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
    "Pachul is a graphical package manager for Arch, Debian/Ubuntu, Fedora and openSUSE. Search, install, update and remove packages, review config file conflicts, keep external tools (rustup, npm, pip, Flatpak, …) up to date, and more — all from one native GTK4/libadwaita app.":
        "Pachul ist ein grafischer Paketmanager für Arch, Debian/Ubuntu, Fedora und openSUSE. Pakete suchen, installieren, aktualisieren und entfernen, Konfigurationsdatei-Konflikte prüfen, externe Tools (rustup, npm, pip, Flatpak, …) aktuell halten und mehr — alles in einer nativen GTK4/libadwaita-App.",
    "Version {v}": "Version {v}",
    "Developer": "Entwickler",
    "License": "Lizenz",
    "Distro": "Distribution",
    "Package Manager": "Paketmanager",
    "Website": "Webseite",
    "Report an Issue": "Fehler melden",
    "Copy Debug Info": "Debug-Infos kopieren",
    "Copied!": "Kopiert!",

    # Help dialog
    "Help": "Hilfe",
    "Browsing & Search": "Navigation & Suche",
    "New Packages / All Packages / Installed / Updates": "Neue Pakete / Alle Pakete / Installiert / Updates",
    "Sidebar filters for the package list — what's newly available, everything, only what's installed, or only what has an update pending.":
        "Filter in der Seitenleiste für die Paketliste — neu verfügbare, alle, nur installierte oder nur Pakete mit ausstehendem Update.",
    "Type in the search bar (or press Ctrl+F) to filter the current list by name or description.":
        "In die Suchleiste tippen (oder Strg+F drücken), um die aktuelle Liste nach Name oder Beschreibung zu filtern.",
    "Package details": "Paketdetails",
    "Click any package to see its description, version, size, dependencies and files on the right, with Install/Remove/Update actions.":
        "Auf ein Paket klicken, um rechts Beschreibung, Version, Größe, Abhängigkeiten und Dateien zu sehen, inkl. Installieren/Entfernen/Aktualisieren.",
    "Updating": "Aktualisieren",
    "Refresh the local package index from the repositories, without installing anything yet.":
        "Den lokalen Paketindex von den Repositories aktualisieren, ohne dabei schon etwas zu installieren.",
    "Sync, then rebuild the Updates list — same as pressing Ctrl+U.":
        "Synchronisiert und baut danach die Updates-Liste neu auf — entspricht Strg+U.",
    "Reload the current view from what's already known locally, without contacting the repositories.":
        "Die aktuelle Ansicht aus den lokal bereits bekannten Daten neu laden, ohne die Repositories zu kontaktieren.",
    "Install every pending update in one go — shown as a button whenever the Updates list isn't empty.":
        "Installiert alle ausstehenden Updates auf einmal — als Button sichtbar, sobald die Updates-Liste nicht leer ist.",
    "Batch mode": "Mehrfachauswahl",
    "Select several packages at once (checkboxes in the list) to install or remove them together; Ctrl+A / Ctrl+Shift+A select or deselect everything currently visible.":
        "Mehrere Pakete gleichzeitig auswählen (Kontrollkästchen in der Liste), um sie gemeinsam zu installieren oder zu entfernen; Strg+A / Strg+Umschalt+A wählt alle sichtbaren Pakete aus bzw. ab.",
    "Repositories": "Repositories",
    "View and edit which package repositories are enabled.":
        "Anzeigen und bearbeiten, welche Paket-Repositories aktiviert sind.",
    "Benchmark configured mirrors and switch to the fastest ones. Arch-only — Fedora and openSUSE already pick the fastest mirror automatically.":
        "Konfigurierte Mirrors testen und auf die schnellsten wechseln. Nur unter Arch — Fedora und openSUSE wählen den schnellsten Mirror bereits automatisch.",
    "Tools": "Werkzeuge",
    "List packages that were pulled in as dependencies but are no longer needed by anything, so you can clean them up.":
        "Listet Pakete auf, die als Abhängigkeit installiert wurden, aber von nichts mehr benötigt werden, damit du sie aufräumen kannst.",
    "Look up which installed package owns a given file path.":
        "Ermitteln, zu welchem installierten Paket ein bestimmter Dateipfad gehört.",
    "Review and merge configuration files a package update left behind instead of overwriting your local changes.":
        "Konfigurationsdateien prüfen und zusammenführen, die ein Paket-Update hinterlassen hat, statt deine lokalen Änderungen zu überschreiben.",
    "Check for updates outside the system package manager — rustup, npm, pip, Flatpak, and similar tools.":
        "Nach Updates außerhalb des System-Paketmanagers suchen — rustup, npm, pip, Flatpak und ähnliche Tools.",
    "Hold specific packages back from updates.":
        "Bestimmte Pakete von Updates ausnehmen.",
    "Browse a log of past installs, removals and updates.":
        "Ein Protokoll früherer Installationen, Entfernungen und Updates durchsuchen.",
    "Overview of the system, hardware and installed packages.":
        "Übersicht über System, Hardware und installierte Pakete.",
    "Free up disk space by clearing old cached package files.":
        "Speicherplatz freigeben, indem alte zwischengespeicherte Paketdateien gelöscht werden.",
    "Package Lists": "Paketlisten",
    "Save the list of explicitly installed packages to a file — handy for setting up another machine the same way.":
        "Die Liste der explizit installierten Pakete in eine Datei speichern — praktisch, um einen anderen Rechner gleich einzurichten.",
    "Install every package from a previously exported list.":
        "Alle Pakete aus einer zuvor exportierten Liste installieren.",
    "AUR / Advanced": "AUR / Erweitert",
    "Inspect the build script of an AUR package before installing it.":
        "Das Build-Skript eines AUR-Pakets vor der Installation prüfen.",
    "Toggle whether the selected packages are excluded from updates.":
        "Umschalten, ob die ausgewählten Pakete von Updates ausgenommen sind.",
    "Mark Selected as Explicit / as Dependency": "Auswahl als explizit / als Abhängigkeit markieren",
    "Change how a package is tracked, so orphan-cleanup treats it correctly.":
        "Ändert, wie ein Paket geführt wird, damit die Verwaisten-Bereinigung es korrekt behandelt.",
    "App-wide settings: language, theme, and other options.":
        "App-weite Einstellungen: Sprache, Theme und weitere Optionen.",
    "Version, license and system info for bug reports.":
        "Version, Lizenz und Systeminfos für Fehlerberichte.",
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
    "Hold isn't available for Flatpak/Snap packages": "Sperren ist für Flatpak-/Snap-Pakete nicht verfügbar",
    "Not applicable to Flatpak/Snap packages": "Nicht anwendbar auf Flatpak-/Snap-Pakete",
    "PKGBUILD is only available for AUR packages": "PKGBUILD ist nur für AUR-Pakete verfügbar",
    "Could not read /etc/pacman.conf": "/etc/pacman.conf konnte nicht gelesen werden",
    "Unhold": "Entsperren",
    "Hold": "Sperren",
    "Hold {pkg}": "{pkg} sperren",
    "Unhold {pkg}": "{pkg} entsperren",
    "Ignore Updates": "Update ignorieren",
    "Unignore": "Nicht mehr ignorieren",
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
    "1 additional update source is ready to run.": "1 weitere Update-Quelle ist bereit.",
    "{n} additional update sources are ready to run.": "{n} weitere Update-Quellen sind bereit.",

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
    "No AUR helper found": "Kein AUR-Helper gefunden",
    "Newer version {v} available on the AUR": "Neuere Version {v} im AUR verfügbar",
    "Install from AUR": "Aus dem AUR installieren",
    "Install {n} from AUR": "{n} aus dem AUR installieren",

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
    "Scanning for config file conflicts…": "Suche nach Konfigurationsdatei-Konflikten…",
    "Nothing to Merge": "Nichts zusammenzuführen",
    "No .pacnew or .pacsave files were found.": "Es wurden keine .pacnew- oder .pacsave-Dateien gefunden.",
    "No config file conflicts were found.": "Es wurden keine Konfigurationsdatei-Konflikte gefunden.",
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
    "paru not installed": "paru nicht installiert",
    "paru handles some AUR-vs-repo ambiguities (e.g. a package that "
    "exists both in a plain repo and on the AUR) more reliably than "
    "other helpers. Builds it from the AUR the same way any AUR "
    "package is built (needs base-devel and git).":
        "paru löst manche Mehrdeutigkeiten zwischen Repo und AUR (z. B. ein Paket, das "
        "sowohl in einem normalen Repo als auch im AUR existiert) zuverlässiger als "
        "andere Helfer. Wird aus dem AUR gebaut, genau wie jedes andere AUR-Paket "
        "(benötigt base-devel und git).",
    "Install paru": "paru installieren",
    "Include AUR in update checks": "AUR bei Update-Prüfungen einbeziehen",
    "Additional Package Sources": "Zusätzliche Paketquellen",
    "Show installed Flatpak/Snap apps alongside pacman packages, and include them when searching. Flatpak installs use --user (no password needed); Snap always needs one, since snapd requires root.":
        "Zeigt installierte Flatpak-/Snap-Apps zusammen mit Pacman-Paketen an und bezieht sie in die Suche mit ein. Flatpak-Installationen laufen über --user (kein Passwort nötig); bei Snap wird immer eines benötigt, da snapd Root-Rechte braucht.",
    "flatpak isn't installed": "flatpak ist nicht installiert",
    "snap isn't installed": "snap ist nicht installiert",
    "Flatpak (user installation)": "Flatpak (Benutzer-Installation)",
    "Snap package": "Snap-Paket",
    "Behaviour": "Verhalten",
    "Confirm before removing packages": "Vor dem Entfernen von Paketen bestätigen",
    "Check for updates on startup": "Beim Start auf Updates prüfen",
    "Notify when updates are available": "Benachrichtigen, wenn Updates verfügbar sind",
    "Show Arch news before upgrades": "Arch-News vor Aktualisierungen anzeigen",
    "Warns about manual interventions before a system upgrade":
        "Warnt vor manuellen Eingriffen, bevor das System aktualisiert wird",
    "Tray Icon": "Tray-Icon",
    "A persistent icon showing the pending update count":
        "Ein dauerhaftes Icon, das die Anzahl ausstehender Updates anzeigt",
    "Start automatically at login": "Beim Anmelden automatisch starten",
    "Install Pachul?": "Pachul installieren?",
    "Pachul isn't installed system-wide yet. Installing adds an "
    "app-menu entry and the pachul / pachul-tray commands, and "
    "installs any missing dependencies — this needs your password.":
        "Pachul ist noch nicht systemweit installiert. Die Installation fügt einen "
        "Eintrag im Anwendungsmenü sowie die Befehle pachul / pachul-tray hinzu und "
        "installiert fehlende Abhängigkeiten — dafür wird dein Passwort benötigt.",
    "Not Now": "Nicht jetzt",
    "Install Pachul": "Pachul installieren",
    "Pachul installed — available from the app menu from now on.":
        "Pachul wurde installiert — ab jetzt auch über das Anwendungsmenü verfügbar.",
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
    "(machine-translated from English)": "(maschinell aus dem Englischen übersetzt)",
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

    # Tray indicator (tray.py)
    "Open Pachul": "Pachul öffnen",
    "Checking for updates…": "Prüfe auf Updates…",

    # External tool updaters (More Update Sources…)
    "More Update Sources…": "Weitere Update-Quellen…",
    "More Update Sources": "Weitere Update-Quellen",
    "Scanning for update sources…": "Suche nach Update-Quellen…",
    "Update Selected": "Auswahl aktualisieren",
    "Update Selected Tools": "Ausgewählte Tools aktualisieren",
    "Configuration": "Konfiguration",
    "Review and merge configuration files left behind by package updates.":
        "Konfigurationsdateien prüfen und zusammenführen, die bei Paket-Updates zurückbleiben.",
    "Review…": "Prüfen…",
    "{n} outdated": "{n} veraltet",

    # Batch "Ignore" + Ignored Packages overview
    "Ignore ({n})": "Ignorieren ({n})",
    "Ignore {n} packages": "{n} Pakete ignorieren",
    "Ignore {n} packages?": "{n} Pakete ignorieren?",
    "All selected packages are already ignored": "Alle ausgewählten Pakete werden bereits ignoriert",
    "Adds {n} package(s) to IgnorePkg in /etc/pacman.conf. They'll be "
    "skipped by system upgrades until you unignore them individually.":
        "Fügt {n} Paket(e) zu IgnorePkg in /etc/pacman.conf hinzu. Sie werden bei "
        "System-Updates übersprungen, bis du sie einzeln wieder freigibst.",
    "Ignored Packages…": "Ignorierte Pakete…",
    "Ignored Packages": "Ignorierte Pakete",
    "Unignore All": "Alle nicht mehr ignorieren",
    "Unignore {n} packages": "{n} Pakete nicht mehr ignorieren",
    "No Ignored Packages": "Keine ignorierten Pakete",
    "Packages held via IgnorePkg (skipped by system upgrades) show up here.":
        "Über IgnorePkg gesperrte Pakete (werden bei System-Updates übersprungen) erscheinen hier.",
    "These packages are skipped by system upgrades until you unignore them.":
        "Diese Pakete werden bei System-Updates übersprungen, bis du sie wieder freigibst.",
    "Detected Tools": "Erkannte Tools",
    "Checked tools run automatically with every normal system upgrade from now on. "
    "\u201cUpdate Selected\u201d above also runs whatever is checked right now, once.":
        "Angehakte Tools werden ab sofort automatisch bei jedem normalen System-Update mit ausgeführt. "
        "„Auswahl aktualisieren“ oben führt die aktuell angehakten Tools zusätzlich einmalig sofort aus.",
    "No Additional Tools Found": "Keine weiteren Tools gefunden",
    "None of the supported external tools (rustup, cargo, pip/pipx, npm, "
    "gh extensions, Claude Code, Lensfun, uv, Ollama, JetBrains) were detected.":
        "Keines der unterstützten externen Tools (rustup, cargo, pip/pipx, npm, "
        "gh-Erweiterungen, Claude Code, Lensfun, uv, Ollama, JetBrains) wurde gefunden.",

    "Firmware (fwupdmgr)": "Firmware (fwupdmgr)",
    "Firmware updates for the mainboard, SSDs, and other devices via fwupd.":
        "Firmware-Updates für Mainboard, SSDs und andere Geräte über fwupd.",
    "Rust Toolchains (rustup)": "Rust-Toolchains (rustup)",
    "pip (--user packages)": "pip (--user-Pakete)",
    "Upgrades every outdated package installed with --user.":
        "Aktualisiert alle veralteten, mit --user installierten Pakete.",
    "pipx": "pipx",
    "npm (global packages)": "npm (globale Pakete)",
    "Claude Code": "Claude Code",
    "Lensfun Camera/Lens Database": "Lensfun Kamera-/Objektiv-Datenbank",
    "Fetches the latest camera/lens calibration data used by darktable, digiKam, and similar apps.":
        "Lädt die neuesten Kamera-/Objektiv-Kalibrierungsdaten für darktable, digiKam und ähnliche Programme.",
    "uv (Python package/tool manager)": "uv (Python-Paket-/Tool-Manager)",
    "Only works for the standalone uv installer — a pacman/AUR install is updated there instead.":
        "Funktioniert nur bei der eigenständigen uv-Installation — bei pacman/AUR wird uv dort aktualisiert.",
    "Cargo (crates.io binaries)": "Cargo (crates.io-Programme)",
    "Installs the 'cargo-update' helper crate first, then upgrades all cargo-installed binaries.":
        "Installiert zunächst das Hilfs-Crate „cargo-update“ und aktualisiert danach alle mit Cargo installierten Programme.",
    "GitHub CLI Extensions": "GitHub-CLI-Erweiterungen",
    "Ollama": "Ollama",
    "Re-runs the official installer script to fetch the latest release.":
        "Führt das offizielle Installationsskript erneut aus, um die neueste Version zu laden.",
    "JetBrains PyCharm Plugins": "JetBrains-PyCharm-Plugins",
    "Re-installs every detected plugin at its latest compatible version "
    "(the same trick topgrade uses) \u2014 close PyCharm first.":
        "Installiert jedes erkannte Plugin neu in der aktuellsten kompatiblen Version "
        "(derselbe Trick wie bei topgrade) \u2014 PyCharm muss dafür geschlossen sein.",
    "Couldn't determine the CLI launcher or installed plugin IDs automatically \u2014 "
    "this opens Toolbox/PyCharm so you can use Settings \u2192 Plugins \u2192 Update All instead.":
        "Kommandozeilen-Starter oder installierte Plugin-IDs konnten nicht automatisch ermittelt werden \u2014 "
        "dies öffnet stattdessen Toolbox/PyCharm, damit du Einstellungen \u2192 Plugins \u2192 Alle aktualisieren nutzen kannst.",

    "fnm (Fast Node Manager)": "fnm (Fast Node Manager)",
    "Installs the latest Node.js LTS release via fnm.":
        "Installiert die neueste Node.js-LTS-Version über fnm.",
    "nvm (Node Version Manager)": "nvm (Node Version Manager)",
    "Installs the latest Node.js LTS release and sets it as the default.":
        "Installiert die neueste Node.js-LTS-Version und setzt sie als Standard.",
    "pyenv (Python Version Manager)": "pyenv (Python Version Manager)",
    "Updates pyenv itself — install new Python versions separately with 'pyenv install'.":
        "Aktualisiert pyenv selbst — neue Python-Versionen werden separat mit „pyenv install“ installiert.",
    "SDKMAN (Java/Kotlin/Gradle/Maven)": "SDKMAN (Java/Kotlin/Gradle/Maven)",
    "Updates SDKMAN itself and its candidate index — not each installed SDK version.":
        "Aktualisiert SDKMAN selbst und dessen Kandidaten-Index — nicht jede installierte SDK-Version.",
    "Mamba (base environment)": "Mamba (Basisumgebung)",
    "Conda (base environment)": "Conda (Basisumgebung)",
    "Updates the base environment only — other environments need updating separately.":
        "Aktualisiert nur die Basisumgebung — andere Umgebungen müssen separat aktualisiert werden.",
    "TeX Live (tlmgr)": "TeX Live (tlmgr)",
    "VS Code Extensions": "VS-Code-Erweiterungen",
    "VSCodium Extensions": "VSCodium-Erweiterungen",
    "Reinstalls every extension at its latest Marketplace version.":
        "Installiert jede Erweiterung neu in der aktuellsten Marketplace-Version.",
    "ClamAV Virus Definitions": "ClamAV-Virendefinitionen",
    "Downloads the latest ClamAV signature database.":
        "Lädt die neueste ClamAV-Signaturdatenbank herunter.",
    "Docker Images": "Docker-Images",
    "Podman Images": "Podman-Images",
    "Pulls the latest version of every locally tagged image.":
        "Lädt die neueste Version jedes lokal getaggten Images herunter.",
    "Flatpak: Unused Runtimes": "Flatpak: Ungenutzte Runtimes",
    "Removes runtimes and extensions no installed app depends on anymore.":
        "Entfernt Runtimes und Erweiterungen, die keine installierte App mehr benötigt.",

    "Neovim Plugins (lazy.nvim)": "Neovim-Plugins (lazy.nvim)",
    "Neovim Plugins (packer.nvim)": "Neovim-Plugins (packer.nvim)",
    "Neovim Plugins (vim-plug)": "Neovim-Plugins (vim-plug)",
    "Vim Plugins (vim-plug)": "Vim-Plugins (vim-plug)",
    "tmux Plugins (TPM)": "tmux-Plugins (TPM)",
    "Oh My Zsh": "Oh My Zsh",
    "Zinit (zsh plugin manager)": "Zinit (Zsh-Plugin-Manager)",
    "Antigen (zsh plugin manager)": "Antigen (Zsh-Plugin-Manager)",
    "Sheldon (shell plugin manager)": "Sheldon (Shell-Plugin-Manager)",
    "Fisher (fish plugin manager)": "Fisher (Fish-Plugin-Manager)",
    "Nerd Fonts (getnf)": "Nerd Fonts (getnf)",
    "Updates already-installed Nerd Fonts to their latest release.":
        "Aktualisiert bereits installierte Nerd Fonts auf die neueste Version.",
    "tldr Pages": "tldr-Seiten",
    "Nix Packages (nix-env)": "Nix-Pakete (nix-env)",
    "Classic nix-env profile only \u2014 flake-based setups update differently.":
        "Nur klassisches nix-env-Profil \u2014 Flake-basierte Setups werden anders aktualisiert.",
    "home-manager": "home-manager",

    "What can be updated here?": "Was kann hier aktualisiert werden?",
    "Full list of supported sources \u2014 shown once installed and detected.":
        "Vollständige Liste der unterstützten Quellen \u2014 wird angezeigt, sobald installiert und erkannt.",
    "Updates installed Rust toolchains.": "Aktualisiert installierte Rust-Toolchains.",
    "Updates binaries installed via cargo install.":
        "Aktualisiert Programme, die mit cargo install installiert wurden.",
    "Upgrades every pipx-installed application.":
        "Aktualisiert jede mit pipx installierte Anwendung.",
    "Updates globally installed npm packages.":
        "Aktualisiert global installierte npm-Pakete.",
    "Updates TeX Live packages.": "Aktualisiert TeX-Live-Pakete.",
    "Updates all installed gh extensions.": "Aktualisiert alle installierten gh-Erweiterungen.",
    "Updates the Claude Code CLI.": "Aktualisiert die Claude-Code-CLI.",
    "Conda/Mamba (base environment)": "Conda/Mamba (Basisumgebung)",
    "Updates installed plugins via the command line (installPlugins) \u2014 "
    "falls back to opening Toolbox/PyCharm.":
        "Aktualisiert installierte Plugins über die Kommandozeile (installPlugins) \u2014 "
        "öffnet als Rückfallebene Toolbox/PyCharm.",
    "Vim/Neovim Plugins": "Vim-/Neovim-Plugins",
    "Updates plugins managed by lazy.nvim, packer.nvim, or vim-plug.":
        "Aktualisiert Plugins, die von lazy.nvim, packer.nvim oder vim-plug verwaltet werden.",
    "Updates everything managed through the tmux Plugin Manager.":
        "Aktualisiert alles, was über den tmux Plugin Manager verwaltet wird.",
    "Zsh/Fish Frameworks": "Zsh-/Fish-Frameworks",
    "Oh My Zsh, Zinit, Antigen, Sheldon, Fisher.": "Oh My Zsh, Zinit, Antigen, Sheldon, Fisher.",
    "Dotfiles Git Repos": "Dotfiles-Git-Repos",
    "Runs 'git pull' on detected config repos with a remote configured.":
        "Führt „git pull“ für erkannte Konfigurations-Repos mit eingerichtetem Remote aus.",
    "Nix / home-manager": "Nix / home-manager",
    "Updates Nix packages (nix-env) or applies your home-manager configuration.":
        "Aktualisiert Nix-Pakete (nix-env) oder wendet deine home-manager-Konfiguration an.",

    # ── Repair System (apt/dpkg), Debian-only ───────────────────────────────
    "Repair System (apt/dpkg)…": "System reparieren (apt/dpkg)…",
    "Repair System": "System reparieren",
    "These run real apt/dpkg maintenance commands with sudo — read what each "
    "one does before running it, especially the last one.":
        "Dies sind echte apt-/dpkg-Wartungsbefehle mit sudo — lies vor dem Ausführen, "
        "was jeder einzelne tut, besonders den letzten.",
    "Update, Upgrade & Autoremove": "Update, Upgrade & Autoremove",
    "Refreshes the package index, upgrades everything, then removes packages "
    "no longer needed by anything else.":
        "Aktualisiert den Paketindex, upgradet alles und entfernt anschließend "
        "Pakete, die von nichts mehr benötigt werden.",
    "Fix Broken Dependencies": "Kaputte Abhängigkeiten reparieren",
    "Runs 'apt --fix-broken install' to resolve broken or half-installed "
    "dependencies.":
        "Führt „apt --fix-broken install“ aus, um kaputte oder halb installierte "
        "Abhängigkeiten zu beheben.",
    "Reconfigure All Packages": "Alle Pakete neu konfigurieren",
    "Runs 'dpkg --configure -a' to finish any package configuration that was "
    "interrupted.":
        "Führt „dpkg --configure -a“ aus, um eine unterbrochene Paketkonfiguration "
        "abzuschließen.",
    "Fix Missing/Corrupt Package Files": "Fehlende/beschädigte Paketdateien beheben",
    "Refreshes the package index, then retries installing anything with "
    "missing or corrupt downloaded files.":
        "Aktualisiert den Paketindex und versucht anschließend erneut, alles mit "
        "fehlenden oder beschädigten heruntergeladenen Dateien zu installieren.",
    "Clean Package Cache": "Paket-Cache leeren",
    "Removes outdated .deb files from the local cache, then clears it "
    "completely.":
        "Entfernt veraltete .deb-Dateien aus dem lokalen Cache und leert ihn "
        "anschließend vollständig.",
    "Show Broken/Incomplete Packages": "Kaputte/unvollständige Pakete anzeigen",
    "Read-only: lists packages dpkg considers not fully installed (e.g. "
    "flagged 'reinstall required').":
        "Nur lesend: listet Pakete auf, die dpkg als nicht vollständig installiert "
        "einstuft (z. B. mit „Neuinstallation erforderlich“ markiert).",
    "Show": "Anzeigen",
    "Force-Remove Broken Package": "Kaputtes Paket erzwungen entfernen",
    "Last resort for a single package dpkg refuses to touch normally — "
    "removes it while ignoring the 'reinstall required' flag. Only use this "
    "if the steps above didn't help, and only on the one package causing "
    "the problem.":
        "Letzter Ausweg für ein einzelnes Paket, das dpkg normal nicht anfasst — "
        "entfernt es unter Ignorieren der Markierung „Neuinstallation erforderlich“. "
        "Nur verwenden, wenn die obigen Schritte nicht geholfen haben, und nur für "
        "das eine Paket, das das Problem verursacht.",
    "Package name": "Paketname",
    "Remove": "Entfernen",
    "No broken/incomplete packages found.": "Keine kaputten/unvollständigen Pakete gefunden.",

    # ── python3-apt install prompt (Preferences, Debian-only) ──────────────
    "Performance": "Leistung",
    "python3-apt not installed": "python3-apt nicht installiert",
    "Speeds up package info, listing and update checks, and lets "
    "the sidebar show repo categories for installed packages. "
    "Pachul works without it, just a bit slower. Restart Pachul "
    "after installing for it to take effect.":
        "Beschleunigt Paketinfos, Auflistung und Update-Prüfungen und lässt "
        "die Seitenleiste Repo-Kategorien für installierte Pakete anzeigen. "
        "Pachul funktioniert auch ohne, nur etwas langsamer. Nach der "
        "Installation Pachul neu starten, damit es wirksam wird.",
    "Install python3-apt": "python3-apt installieren",

    # ── Repair System (dnf/rpm), Fedora-only ────────────────────────────────
    "Repair System (dnf/rpm)…": "System reparieren (dnf/rpm)…",
    "These run real dnf/rpm maintenance commands with sudo — read what each "
    "one does before running it, especially the last one.":
        "Dies sind echte dnf-/rpm-Wartungsbefehle mit sudo — lies vor dem Ausführen, "
        "was jeder einzelne tut, besonders den letzten.",
    "Refreshes repo metadata, upgrades everything, then removes packages "
    "no longer needed by anything else.":
        "Aktualisiert die Repo-Metadaten, upgradet alles und entfernt anschließend "
        "Pakete, die von nichts mehr benötigt werden.",
    "Fix Inconsistent Package Versions": "Inkonsistente Paketversionen beheben",
    "Runs 'dnf distro-sync' to bring installed packages back in line "
    "with what the repos currently offer, after an interrupted or "
    "partial upgrade left some at mismatched versions.":
        "Führt „dnf distro-sync“ aus, um installierte Pakete wieder in Einklang "
        "mit dem aktuellen Repo-Stand zu bringen, nachdem ein unterbrochenes "
        "oder unvollständiges Upgrade manche auf abweichenden Versionen zurückließ.",
    "Rebuild RPM Database": "RPM-Datenbank neu aufbauen",
    "Runs 'rpm --rebuilddb' to rebuild a corrupted local RPM database.":
        "Führt „rpm --rebuilddb“ aus, um eine beschädigte lokale RPM-Datenbank "
        "neu aufzubauen.",
    "Runs 'dnf clean all' to clear cached package files and metadata.":
        "Führt „dnf clean all“ aus, um zwischengespeicherte Paketdateien und "
        "Metadaten zu löschen.",
    "Show Broken/Unsatisfied Packages": "Kaputte/unerfüllte Pakete anzeigen",
    "Read-only: runs 'dnf check' to list dependency, duplicate, or "
    "obsoleted-package problems in what's currently installed.":
        "Nur lesend: führt „dnf check“ aus, um Abhängigkeits-, Duplikat- oder "
        "veraltete-Paket-Probleme im aktuell installierten Bestand aufzulisten.",
    "Last resort for a single package rpm refuses to touch normally — "
    "removes it while ignoring dependency checks entirely. Only use this "
    "if the steps above didn't help, and only on the one package causing "
    "the problem.":
        "Letzter Ausweg für ein einzelnes Paket, das rpm normal nicht anfasst — "
        "entfernt es unter vollständigem Ignorieren der Abhängigkeitsprüfung. "
        "Nur verwenden, wenn die obigen Schritte nicht geholfen haben, und nur für "
        "das eine Paket, das das Problem verursacht.",

    # ── python3-libdnf5 install prompt (Preferences, Fedora-only) ──────────
    "python3-libdnf5 not installed": "python3-libdnf5 nicht installiert",
    "Speeds up package info, listing and update checks. "
    "Pachul works without it, just a bit slower. Restart Pachul "
    "after installing for it to take effect.":
        "Beschleunigt Paketinfos, Auflistung und Update-Prüfungen. Pachul "
        "funktioniert auch ohne, nur etwas langsamer. Nach der Installation "
        "Pachul neu starten, damit es wirksam wird.",
    "Install python3-libdnf5": "python3-libdnf5 installieren",

    # ── Repair System (zypper/rpm), openSUSE-only ───────────────────────────
    "Repair System (zypper/rpm)…": "System reparieren (zypper/rpm)…",
    "These run real zypper/rpm maintenance commands with sudo — read what "
    "each one does before running it, especially the last one.":
        "Dies sind echte zypper-/rpm-Wartungsbefehle mit sudo — lies vor dem "
        "Ausführen, was jeder einzelne tut, besonders den letzten.",
    "Update & Upgrade": "Update & Upgrade",
    "Refreshes repo metadata, then installs all available updates.":
        "Aktualisiert die Repo-Metadaten und installiert dann alle verfügbaren "
        "Updates.",
    "Runs 'zypper verify' — openSUSE's own solver run that finds and "
    "proposes fixes for broken or unsatisfied package dependencies.":
        "Führt „zypper verify“ aus — openSUSEs eigener Solver-Lauf, der kaputte "
        "oder unerfüllte Paketabhängigkeiten findet und Lösungen vorschlägt.",
    "Runs 'zypper clean --all' to clear cached package files and metadata.":
        "Führt „zypper clean --all“ aus, um zwischengespeicherte Paketdateien "
        "und Metadaten zu löschen.",
    "Read-only: runs 'zypper verify --dry-run' to list what it would "
    "change without actually changing anything.":
        "Nur lesend: führt „zypper verify --dry-run“ aus, um zu zeigen, was "
        "geändert würde, ohne tatsächlich etwas zu ändern.",

    # ── Repair System (pacman), Arch-only ───────────────────────────────────
    "Repair System (pacman)…": "System reparieren (pacman)…",
    "These run real pacman/pacman-key commands with sudo — read what each "
    "one does before running it, especially the last one.":
        "Dies sind echte pacman-/pacman-key-Befehle mit sudo — lies vor dem "
        "Ausführen, was jeder einzelne tut, besonders den letzten.",
    "Standard Maintenance": "Standard-Wartung",
    "Last Resort": "Letzter Ausweg",
    "Force-Refresh & Full Upgrade": "Erzwungenes Neuladen & Vollupgrade",
    "Runs 'pacman -Syyu' — forces a fresh download of all repo "
    "databases (ignoring their last-sync timestamps) before "
    "upgrading, useful when a mirror served stale or corrupt data.":
        "Führt „pacman -Syyu“ aus — erzwingt einen frischen Download aller "
        "Repo-Datenbanken (ignoriert deren letzten Sync-Zeitstempel) vor dem "
        "Upgrade, nützlich wenn ein Mirror veraltete oder beschädigte Daten "
        "geliefert hat.",
    "Check Package Database Consistency": "Paketdatenbank auf Konsistenz prüfen",
    "Runs 'pacman -Dk' to check the local package database itself "
    "for internal inconsistencies (separate from checking individual "
    "installed files).":
        "Führt „pacman -Dk“ aus, um die lokale Paketdatenbank selbst auf "
        "interne Inkonsistenzen zu prüfen (unabhängig von der Prüfung "
        "einzelner installierter Dateien).",
    "Reinitialize Keyring": "Keyring neu initialisieren",
    "Runs 'pacman-key --init' and '--populate archlinux' — a deeper "
    "fix than the automatic keyring banner elsewhere, for when "
    "signature errors persist after that lighter fix.":
        "Führt „pacman-key --init“ und „--populate archlinux“ aus — eine "
        "tiefergehende Reparatur als das automatische Keyring-Banner an "
        "anderer Stelle, für den Fall, dass Signaturfehler nach dieser "
        "leichteren Lösung weiter bestehen.",
    "Search for Packages With Missing/Modified Files": "Pakete mit fehlenden/geänderten Dateien suchen",
    "Runs 'pacman -Qkk' with sudo (read-only, no changes are made). "
    "If any packages come back altered, you'll be asked right away "
    "which ones to repair.":
        "Führt „pacman -Qkk“ mit sudo aus (nur lesend, es wird nichts "
        "verändert). Werden Pakete als verändert gemeldet, wirst du "
        "sofort gefragt, welche davon repariert werden sollen.",
    "Run": "Ausführen",
    "Repair Broken Packages": "Kaputte Pakete reparieren",
    "{n} package(s) with missing or altered files found":
        "{n} Paket(e) mit fehlenden oder geänderten Dateien gefunden",
    "Choose which ones to reinstall from your configured "
    "repositories to restore the original files:":
        "Wähle aus, welche davon aus deinen konfigurierten Repositories "
        "neu installiert werden sollen, um die Originaldateien "
        "wiederherzustellen:",
    "Repair {n} package(s)": "{n} Paket(e) reparieren",
    "(+{n} more)": "(+{n} weitere)",
    "({n} more package(s) with only config/permission "
    "differences are hidden — reinstalling never touches "
    "those.)":
        "({n} weitere(s) Paket(e) mit ausschließlich Config-/"
        "Rechte-Unterschieden sind ausgeblendet — eine Neuinstallation "
        "rührt diese nie an.)",
    "All {n} package(s) only have config/permission "
    "differences a reinstall can't fix.":
        "Alle {n} Paket(e) haben nur Config-/Rechte-Unterschiede, "
        "die eine Neuinstallation nicht beheben kann.",
    "Select All": "Alle auswählen",
    "Select None": "Keine auswählen",
    "Last resort for a single package pacman refuses to touch normally "
    "— removes it while ignoring dependency checks entirely. Only use "
    "this if the steps above didn't help, and only on the one package "
    "causing the problem.":
        "Letzter Ausweg für ein einzelnes Paket, das pacman normal nicht "
        "anfasst — entfernt es unter vollständigem Ignorieren der "
        "Abhängigkeitsprüfung. Nur verwenden, wenn die obigen Schritte "
        "nicht geholfen haben, und nur für das eine Paket, das das Problem "
        "verursacht.",

    # ── Certificate Checker (Modul 2, cross-distro) ─────────────────────────
    "Certificate Checker": "Zertifikatsprüfung",
    "Check Certificates…": "Zertifikate prüfen…",
    "CA Certificate Bundle": "CA-Zertifikatspaket",
    "Reinstall CA Certificates & Rebuild Trust Store": "CA-Zertifikate neu installieren & Trust Store neu aufbauen",
    "Reinstalls the ca-certificates package and regenerates the "
    "system's trust store. Useful if HTTPS connections fail with "
    "certificate-verification errors that aren't the remote site's "
    "fault.":
        "Installiert das ca-certificates-Paket neu und baut den System-Trust-Store "
        "neu auf. Nützlich, wenn HTTPS-Verbindungen mit Zertifikatsprüfungsfehlern "
        "fehlschlagen, die nicht an der Gegenstelle liegen.",
    "Domain Certificate Expiry": "Domain-Zertifikatsablauf",
    "Checks how many days remain before each domain's TLS "
    "certificate expires — nothing is changed, purely informational.":
        "Prüft, wie viele Tage bis zum Ablauf des TLS-Zertifikats jeder Domain "
        "verbleiben — es wird nichts geändert, rein informativ.",
    "Domains": "Domains",
    "Comma-separated, e.g. example.com, mail.example.com": "Kommagetrennt, z. B. example.com, mail.example.com",
    "Domains to check": "Zu prüfende Domains",
    "Check": "Prüfen",
    "Could not retrieve certificate (offline or unreachable?)": "Zertifikat konnte nicht abgerufen werden (offline oder nicht erreichbar?)",
    "EXPIRED {days} days ago": "ABGELAUFEN vor {days} Tagen",
    "Expires in {days} days (until {date})": "Läuft in {days} Tagen ab (bis {date})",
    "Valid, {days} days remaining (until {date})": "Gültig, noch {days} Tage (bis {date})",
    "Local Certificates": "Lokale Zertifikate",
    "Show Expired Local Certificates": "Abgelaufene lokale Zertifikate anzeigen",
    "Read-only: scans /etc/ssl/certs for .pem certificates that have "
    "already expired.":
        "Nur lesend: durchsucht /etc/ssl/certs nach bereits abgelaufenen "
        ".pem-Zertifikaten.",
    "EXPIRED: {cert}": "ABGELAUFEN: {cert}",
    "All local certificates are valid.": "Alle lokalen Zertifikate sind gültig.",

    # ── System Cleanup (Modul 4-Erweiterung, cross-distro) ──────────────────
    "System Cleanup": "System-Bereinigung",
    "Not package-related — general disk cleanup for the systemd "
    "journal, old thumbnail previews, and the trash.":
        "Nicht paketbezogen — allgemeine Datenträger-Bereinigung für das "
        "systemd-Journal, alte Thumbnail-Vorschaubilder und den Papierkorb.",
    "Clean systemd Journal": "systemd-Journal bereinigen",
    "Shrinks the journal to 500 MB and removes entries older than 4 weeks.":
        "Verkleinert das Journal auf 500 MB und entfernt Einträge, die älter "
        "als 4 Wochen sind.",
    "Remove Old Thumbnail Previews": "Alte Thumbnail-Vorschaubilder entfernen",
    "Deletes cached thumbnail images in ~/.cache/thumbnails older than "
    "30 days. No sudo needed — this only touches your own cache.":
        "Löscht zwischengespeicherte Thumbnail-Bilder in ~/.cache/thumbnails, "
        "die älter als 30 Tage sind. Kein sudo nötig — betrifft nur den "
        "eigenen Cache.",
    "Done.": "Fertig.",
    "No thumbnail cache found.": "Kein Thumbnail-Cache gefunden.",
    "Empty Trash": "Papierkorb leeren",
    "Permanently empties your desktop trash/recycle bin (via 'gio "
    "trash --empty'). No sudo needed.":
        "Leert den Papierkorb der Desktop-Umgebung endgültig (via „gio trash "
        "--empty“). Kein sudo nötig.",
    "gio not found — nothing to do.": "gio nicht gefunden — nichts zu tun.",

    # ── Broken Symlink Finder (Modul 5b, cross-distro) ──────────────────────
    "Broken Symlinks": "Kaputte Symlinks",
    "Find Broken Symlinks…": "Kaputte Symlinks suchen…",
    "Searches /usr and /etc for symlinks pointing at files that no "
    "longer exist — usually harmless leftovers from removed packages, "
    "but occasionally a sign something didn't uninstall cleanly.":
        "Durchsucht /usr und /etc nach Symlinks, die auf nicht mehr "
        "existierende Dateien zeigen — meist harmlose Reste entfernter "
        "Pakete, gelegentlich aber ein Zeichen für eine unsaubere "
        "Deinstallation.",
    "No broken symlinks found.": "Keine kaputten Symlinks gefunden.",
    "{n} broken symlinks found.": "{n} kaputte Symlinks gefunden.",
    "SAFE — license leftovers ({n}):": "SICHER — Lizenz-Reste ({n}):",
    "removed": "entfernt",
    "SAFE but skipped — archiso build templates ({n}), expected on "
    "Arch/Manjaro, not deleted:":
        "SICHER, aber übersprungen — archiso-Bau-Vorlagen ({n}), auf "
        "Arch/Manjaro erwartet, nicht gelöscht:",
    "REVIEW — not auto-deleted ({n}):": "PRÜFEN — nicht automatisch gelöscht ({n}):",
    "For each: 'pacman/dpkg/rpm/zypper -qf <path>' or equivalent tells you "
    "which package owns it, if any; a reinstall of that package usually "
    "fixes the link.":
        "Für jeden: „pacman/dpkg/rpm/zypper -qf <pfad>“ oder ein Äquivalent "
        "zeigt, welchem Paket er gehört, falls überhaupt; eine "
        "Neuinstallation dieses Pakets behebt den Symlink meist.",
    "Scan": "Scan",
    "Scan Only": "Nur scannen",
    "Read-only: lists and classifies broken symlinks without deleting "
    "anything. No sudo needed.":
        "Nur lesend: listet und klassifiziert kaputte Symlinks, ohne "
        "irgendetwas zu löschen. Kein sudo nötig.",
    "Scan & Remove Safe Ones": "Scannen & sichere entfernen",
    "Same scan, but also deletes the SAFE-category links (license "
    "leftovers only — archiso templates and anything else are still "
    "just listed, never touched). Needs sudo.":
        "Derselbe Scan, löscht aber zusätzlich die SICHER-Kategorie (nur "
        "Lizenz-Reste — archiso-Vorlagen und alles andere werden weiterhin "
        "nur aufgelistet, nie angefasst). Benötigt sudo.",
    "Clean": "Bereinigen",

    # ── Services & Security Check (Modul 7, cross-distro) ───────────────────
    "Services & Security": "Dienste & Sicherheit",
    "Services & Security…": "Dienste & Sicherheit…",
    "Services": "Dienste",
    "Show Failed Services": "Fehlgeschlagene Dienste anzeigen",
    "Read-only: lists any systemd services currently in a failed "
    "state.":
        "Nur lesend: listet alle systemd-Dienste auf, die sich aktuell "
        "in einem fehlgeschlagenen Zustand befinden.",
    "Reset shadow.service": "shadow.service zurücksetzen",
    "shadow.service has failed — this is usually a harmless "
    "password/group integrity check tripping after an update. "
    "Resets it without touching anything else.":
        "shadow.service ist fehlgeschlagen — meist eine harmlose "
        "Passwort-/Gruppen-Integritätsprüfung, die nach einem Update "
        "auslöst. Setzt ihn zurück, ohne sonst etwas zu verändern.",
    "Reset": "Zurücksetzen",
    "Security Services": "Sicherheitsdienste",
    "Check firewalld / fail2ban / apparmor": "firewalld / fail2ban / apparmor prüfen",
    "Read-only: reports whether each of these — if installed — is "
    "currently active.":
        "Nur lesend: meldet, ob jeder dieser Dienste — falls installiert — "
        "aktuell aktiv ist.",
    "running": "läuft",
    "installed but NOT active": "installiert, aber NICHT aktiv",
    "not installed": "nicht installiert",
    "Firewall (UFW)": "Firewall (UFW)",
    "Show Firewall Rules": "Firewall-Regeln anzeigen",
    "UFW is active. Read-only: shows the current rule set.":
        "UFW ist aktiv. Nur lesend: zeigt das aktuelle Regelwerk.",
    "Enable Firewall": "Firewall aktivieren",
    "UFW is installed but not active — your system currently has "
    "no active firewall. Enables it with default rules (deny "
    "incoming, allow outgoing) and rate-limited SSH if sshd is "
    "running.":
        "UFW ist installiert, aber nicht aktiv — dein System hat aktuell "
        "keine aktive Firewall. Aktiviert sie mit Standardregeln (eingehend "
        "blockieren, ausgehend erlauben) und Rate-Limiting für SSH, falls "
        "sshd läuft.",
    "Enable": "Aktivieren",
    "Install & Enable Firewall": "Firewall installieren & aktivieren",
    "UFW isn't installed — your system currently has no "
    "active firewall. Installs it, then enables it with "
    "default rules (deny incoming, allow outgoing) and "
    "rate-limited SSH if sshd is running.":
        "UFW ist nicht installiert — dein System hat aktuell keine aktive "
        "Firewall. Installiert sie und aktiviert sie anschließend mit "
        "Standardregeln (eingehend blockieren, ausgehend erlauben) und "
        "Rate-Limiting für SSH, falls sshd läuft.",
    "Install & Enable": "Installieren & aktivieren",
    "SSH": "SSH",
    "Check SSH Root Login": "SSH-Root-Login prüfen",
    "Read-only: checks /etc/ssh/sshd_config for PermitRootLogin "
    "yes, which lets root log in directly over SSH.":
        "Nur lesend: prüft /etc/ssh/sshd_config auf PermitRootLogin yes, "
        "was root den direkten SSH-Login erlaubt.",
    "SSH root login is ENABLED — consider disabling it "
    "(PermitRootLogin no).":
        "SSH-Root-Login ist AKTIVIERT — Deaktivierung empfohlen "
        "(PermitRootLogin no).",
    "SSH root login is disabled or not explicitly "
    "configured.":
        "SSH-Root-Login ist deaktiviert oder nicht explizit konfiguriert.",
    "No /etc/ssh/sshd_config found — SSH server doesn't "
    "seem to be installed.":
        "Keine /etc/ssh/sshd_config gefunden — SSH-Server scheint nicht "
        "installiert zu sein.",

    # ── Configuration Backup (Modul 6, distro-spezifische Dateiliste) ──────
    "Configuration Backup": "Konfigurationsbackup",
    "Configuration Backup…": "Konfigurationsbackup…",
    "Creates a compressed archive of your system's identity and boot "
    "configuration (fstab, hostname, bootloader, package-manager "
    "config, …) plus a plain-text list of explicitly-installed "
    "packages, so a fresh install can be brought back to a similar "
    "state. Only the last 5 archives are kept; older ones are removed "
    "automatically. No sudo needed — these files are normally "
    "world-readable.":
        "Erstellt ein komprimiertes Archiv der System-Identitäts- und "
        "Boot-Konfiguration (fstab, Hostname, Bootloader, "
        "Paketmanager-Konfiguration, …) sowie eine Textliste der explizit "
        "installierten Pakete, damit eine Neuinstallation wieder in einen "
        "ähnlichen Zustand gebracht werden kann. Es werden nur die letzten "
        "5 Archive behalten; ältere werden automatisch entfernt. Kein "
        "sudo nötig — diese Dateien sind normalerweise für alle lesbar.",
    "Backup Folder": "Backup-Ordner",
    "Included If Present": "Enthalten, falls vorhanden",
    "Also saves the list of explicitly-installed packages.":
        "Speichert außerdem die Liste der explizit installierten Pakete.",
    "Also saves the full list of installed packages (this "
    "distro has no simple way to tell explicit installs "
    "from pulled-in dependencies).":
        "Speichert außerdem die vollständige Liste aller installierten "
        "Pakete (diese Distro hat keine einfache Möglichkeit, explizit "
        "installierte von mitgezogenen Abhängigkeiten zu unterscheiden).",
    "Create Backup": "Backup erstellen",
    "Package list saved ({n} packages): $PAKETLISTE":
        "Paketliste gespeichert ({n} Pakete): $PAKETLISTE",
    "Nothing to back up — none of the expected config paths exist.":
        "Nichts zu sichern — keiner der erwarteten Konfigurationspfade existiert.",
    "Backup created ({size}): $ARCHIV": "Backup erstellt ({size}): $ARCHIV",
    "Removed old backup:": "Altes Backup entfernt:",
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
    "All Packages": "Tous les paquets",
    "Search packages, e.g. firefox, vlc, git…": "Rechercher des paquets, p. ex. firefox, vlc, git…",
    "Updates": "Mises à jour",
    "Installed": "Installés",
    "New Packages": "Nouveaux paquets",
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
    "Config File Conflicts…": "Conflits de fichiers de configuration…",
    "Config File Conflicts": "Conflits de fichiers de configuration",
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
    "Pachul is a graphical package manager for Arch, Debian/Ubuntu, Fedora and openSUSE. Search, install, update and remove packages, review config file conflicts, keep external tools (rustup, npm, pip, Flatpak, …) up to date, and more — all from one native GTK4/libadwaita app.":
        "Pachul est un gestionnaire de paquets graphique pour Arch, Debian/Ubuntu, Fedora et openSUSE. Recherchez, installez, mettez à jour et supprimez des paquets, examinez les conflits de fichiers de configuration, tenez à jour des outils externes (rustup, npm, pip, Flatpak, …), et bien plus — le tout dans une application native GTK4/libadwaita.",
    "Version {v}": "Version {v}",
    "Developer": "Développeur",
    "License": "Licence",
    "Distro": "Distribution",
    "Package Manager": "Gestionnaire de paquets",
    "Website": "Site web",
    "Report an Issue": "Signaler un problème",
    "Copy Debug Info": "Copier les infos de débogage",
    "Copied!": "Copié !",

    # Help dialog
    "Help": "Aide",
    "More Update Sources…": "Autres sources de mise à jour…",
    "Ignored Packages…": "Paquets ignorés…",
    "Browsing & Search": "Navigation et recherche",
    "New Packages / All Packages / Installed / Updates": "Nouveaux paquets / Tous les paquets / Installés / Mises à jour",
    "Sidebar filters for the package list — what's newly available, everything, only what's installed, or only what has an update pending.":
        "Filtres de la barre latérale pour la liste des paquets — nouveautés, tout, uniquement installés, ou uniquement ceux ayant une mise à jour en attente.",
    "Type in the search bar (or press Ctrl+F) to filter the current list by name or description.":
        "Saisissez dans la barre de recherche (ou appuyez sur Ctrl+F) pour filtrer la liste actuelle par nom ou description.",
    "Package details": "Détails du paquet",
    "Click any package to see its description, version, size, dependencies and files on the right, with Install/Remove/Update actions.":
        "Cliquez sur un paquet pour voir sa description, sa version, sa taille, ses dépendances et ses fichiers à droite, avec les actions Installer/Supprimer/Mettre à jour.",
    "Updating": "Mise à jour",
    "Refresh the local package index from the repositories, without installing anything yet.":
        "Actualise l'index local des paquets depuis les dépôts, sans encore rien installer.",
    "Sync, then rebuild the Updates list — same as pressing Ctrl+U.":
        "Synchronise puis reconstruit la liste des mises à jour — équivaut à Ctrl+U.",
    "Reload the current view from what's already known locally, without contacting the repositories.":
        "Recharge la vue actuelle à partir de ce qui est déjà connu localement, sans contacter les dépôts.",
    "Install every pending update in one go — shown as a button whenever the Updates list isn't empty.":
        "Installe toutes les mises à jour en attente d'un coup — affiché en bouton dès que la liste des mises à jour n'est pas vide.",
    "Batch mode": "Mode multi-sélection",
    "Select several packages at once (checkboxes in the list) to install or remove them together; Ctrl+A / Ctrl+Shift+A select or deselect everything currently visible.":
        "Sélectionnez plusieurs paquets à la fois (cases à cocher dans la liste) pour les installer ou les supprimer ensemble ; Ctrl+A / Ctrl+Maj+A sélectionne ou désélectionne tout ce qui est visible.",
    "Repositories": "Dépôts",
    "View and edit which package repositories are enabled.":
        "Afficher et modifier les dépôts de paquets activés.",
    "Benchmark configured mirrors and switch to the fastest ones. Arch-only — Fedora and openSUSE already pick the fastest mirror automatically.":
        "Teste les miroirs configurés et passe aux plus rapides. Arch uniquement — Fedora et openSUSE choisissent déjà le miroir le plus rapide automatiquement.",
    "Tools": "Outils",
    "List packages that were pulled in as dependencies but are no longer needed by anything, so you can clean them up.":
        "Liste les paquets installés comme dépendances mais qui ne sont plus nécessaires, pour pouvoir les nettoyer.",
    "Look up which installed package owns a given file path.":
        "Rechercher quel paquet installé possède un chemin de fichier donné.",
    "Review and merge configuration files a package update left behind instead of overwriting your local changes.":
        "Examine et fusionne les fichiers de configuration laissés par une mise à jour au lieu d'écraser vos modifications locales.",
    "Check for updates outside the system package manager — rustup, npm, pip, Flatpak, and similar tools.":
        "Vérifie les mises à jour en dehors du gestionnaire de paquets système — rustup, npm, pip, Flatpak et outils similaires.",
    "Hold specific packages back from updates.":
        "Exclut certains paquets des mises à jour.",
    "Browse a log of past installs, removals and updates.":
        "Parcourir un journal des installations, suppressions et mises à jour passées.",
    "Overview of the system, hardware and installed packages.":
        "Aperçu du système, du matériel et des paquets installés.",
    "Free up disk space by clearing old cached package files.":
        "Libère de l'espace disque en supprimant les anciens fichiers de paquets mis en cache.",
    "Package Lists": "Listes de paquets",
    "Save the list of explicitly installed packages to a file — handy for setting up another machine the same way.":
        "Enregistre la liste des paquets installés explicitement dans un fichier — pratique pour configurer une autre machine de la même façon.",
    "Install every package from a previously exported list.":
        "Installe tous les paquets d'une liste précédemment exportée.",
    "AUR / Advanced": "AUR / Avancé",
    "Inspect the build script of an AUR package before installing it.":
        "Examine le script de compilation d'un paquet AUR avant de l'installer.",
    "Toggle whether the selected packages are excluded from updates.":
        "Bascule l'exclusion des paquets sélectionnés des mises à jour.",
    "Mark Selected as Explicit / as Dependency": "Marquer la sélection comme explicite / comme dépendance",
    "Change how a package is tracked, so orphan-cleanup treats it correctly.":
        "Modifie la façon dont un paquet est suivi, pour que le nettoyage des orphelins le traite correctement.",
    "App-wide settings: language, theme, and other options.":
        "Paramètres globaux de l'application : langue, thème et autres options.",
    "Version, license and system info for bug reports.":
        "Version, licence et infos système pour les rapports de bugs.",
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
    "Hold isn't available for Flatpak/Snap packages": "Le verrouillage n'est pas disponible pour les paquets Flatpak/Snap",
    "Not applicable to Flatpak/Snap packages": "Non applicable aux paquets Flatpak/Snap",
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
    "Scanning for config file conflicts…": "Recherche de conflits de fichiers de configuration…",
    "Nothing to Merge": "Rien à fusionner",
    "No .pacnew or .pacsave files were found.": "Aucun fichier .pacnew ou .pacsave trouvé.",
    "No config file conflicts were found.": "Aucun conflit de fichier de configuration trouvé.",
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
    "Additional Package Sources": "Sources de paquets supplémentaires",
    "Show installed Flatpak/Snap apps alongside pacman packages, and include them when searching. Flatpak installs use --user (no password needed); Snap always needs one, since snapd requires root.":
        "Affiche les applications Flatpak/Snap installées à côté des paquets pacman, et les inclut dans la recherche. Les installations Flatpak utilisent --user (aucun mot de passe requis) ; Snap en demande toujours un, car snapd nécessite les droits root.",
    "flatpak isn't installed": "flatpak n'est pas installé",
    "snap isn't installed": "snap n'est pas installé",
    "Flatpak (user installation)": "Flatpak (installation utilisateur)",
    "Snap package": "Paquet Snap",
    "Behaviour": "Comportement",
    "Confirm before removing packages": "Confirmer avant de supprimer des paquets",
    "Check for updates on startup": "Vérifier les mises à jour au démarrage",
    "Notify when updates are available": "Notifier lorsque des mises à jour sont disponibles",
    "Show Arch news before upgrades": "Afficher les actualités Arch avant les mises à niveau",
    "Warns about manual interventions before a system upgrade":
        "Avertit des interventions manuelles avant une mise à niveau système",
    "Tray Icon": "Icône de notification",
    "A persistent icon showing the pending update count":
        "Une icône persistante affichant le nombre de mises à jour en attente",
    "Start automatically at login": "Démarrer automatiquement à la connexion",
    "Install Pachul?": "Installer Pachul ?",
    "Pachul isn't installed system-wide yet. Installing adds an "
    "app-menu entry and the pachul / pachul-tray commands, and "
    "installs any missing dependencies — this needs your password.":
        "Pachul n'est pas encore installé pour tout le système. L'installation ajoute une "
        "entrée dans le menu des applications ainsi que les commandes pachul / pachul-tray, et "
        "installe les dépendances manquantes — cela nécessite votre mot de passe.",
    "Not Now": "Pas maintenant",
    "Install Pachul": "Installer Pachul",
    "Pachul installed — available from the app menu from now on.":
        "Pachul installé — désormais disponible depuis le menu des applications.",
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
    "(machine-translated from English)": "(traduit automatiquement de l'anglais)",
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

    # Tray indicator (tray.py)
    "Open Pachul": "Ouvrir Pachul",
    "Checking for updates…": "Vérification des mises à jour…",

    # ── Repair System (pacman), Arch-only ───────────────────────────────────
    "Repair System (pacman)…": "Réparer le système (pacman)…",
    "These run real pacman/pacman-key commands with sudo — read what each "
    "one does before running it, especially the last one.":
        "Ce sont de vraies commandes pacman/pacman-key exécutées avec sudo — lis "
        "ce que fait chacune avant de l'exécuter, surtout la dernière.",
    "Standard Maintenance": "Maintenance standard",
    "Last Resort": "Dernier recours",
    "Force-Refresh & Full Upgrade": "Rechargement forcé et mise à niveau complète",
    "Runs 'pacman -Syyu' — forces a fresh download of all repo "
    "databases (ignoring their last-sync timestamps) before "
    "upgrading, useful when a mirror served stale or corrupt data.":
        "Exécute « pacman -Syyu » — force un nouveau téléchargement de toutes "
        "les bases de données des dépôts (en ignorant leur horodatage de "
        "dernière synchronisation) avant la mise à niveau, utile lorsqu'un "
        "miroir a fourni des données obsolètes ou corrompues.",
    "Check Package Database Consistency": "Vérifier la cohérence de la base de données des paquets",
    "Runs 'pacman -Dk' to check the local package database itself "
    "for internal inconsistencies (separate from checking individual "
    "installed files).":
        "Exécute « pacman -Dk » pour vérifier la base de données locale des "
        "paquets elle-même à la recherche d'incohérences internes "
        "(indépendamment de la vérification des fichiers installés individuels).",
    "Reinitialize Keyring": "Réinitialiser le trousseau de clés",
    "Runs 'pacman-key --init' and '--populate archlinux' — a deeper "
    "fix than the automatic keyring banner elsewhere, for when "
    "signature errors persist after that lighter fix.":
        "Exécute « pacman-key --init » et « --populate archlinux » — une "
        "réparation plus profonde que la bannière automatique du trousseau de "
        "clés ailleurs, pour le cas où des erreurs de signature persistent "
        "après cette solution plus légère.",
    "Search for Packages With Missing/Modified Files": "Rechercher les paquets avec fichiers manquants/modifiés",
    "Runs 'pacman -Qkk' with sudo (read-only, no changes are made). "
    "If any packages come back altered, you'll be asked right away "
    "which ones to repair.":
        "Exécute « pacman -Qkk » avec sudo (lecture seule, aucune modification "
        "n'est apportée). Si des paquets sont signalés comme altérés, tu seras "
        "immédiatement invité à choisir lesquels réparer.",
    "Run": "Exécuter",
    "Repair Broken Packages": "Réparer les paquets défectueux",
    "{n} package(s) with missing or altered files found":
        "{n} paquet(s) avec fichiers manquants ou altérés trouvé(s)",
    "Choose which ones to reinstall from your configured "
    "repositories to restore the original files:":
        "Choisis lesquels réinstaller depuis tes dépôts configurés "
        "pour restaurer les fichiers d'origine :",
    "Repair {n} package(s)": "Réparer {n} paquet(s)",
    "(+{n} more)": "(+{n} de plus)",
    "({n} more package(s) with only config/permission "
    "differences are hidden — reinstalling never touches "
    "those.)":
        "({n} paquet(s) supplémentaire(s) avec uniquement des différences de "
        "config/permissions sont masqué(s) — une réinstallation ne les touche "
        "jamais.)",
    "All {n} package(s) only have config/permission "
    "differences a reinstall can't fix.":
        "Les {n} paquet(s) n'ont que des différences de config/permissions "
        "qu'une réinstallation ne peut pas corriger.",
    "Select All": "Tout sélectionner",
    "Select None": "Tout désélectionner",
    "Last resort for a single package pacman refuses to touch normally "
    "— removes it while ignoring dependency checks entirely. Only use "
    "this if the steps above didn't help, and only on the one package "
    "causing the problem.":
        "Dernier recours pour un seul paquet que pacman refuse normalement "
        "de toucher — le supprime en ignorant entièrement les vérifications "
        "de dépendances. À utiliser uniquement si les étapes ci-dessus n'ont "
        "pas aidé, et uniquement sur le paquet à l'origine du problème.",
    "Force-Remove Broken Package": "Forcer la suppression du paquet défectueux",
    "Package name": "Nom du paquet",
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
    "All Packages": "Tutti i pacchetti",
    "Search packages, e.g. firefox, vlc, git…": "Cerca pacchetti, es. firefox, vlc, git…",
    "Updates": "Aggiornamenti",
    "Installed": "Installati",
    "New Packages": "Nuovi pacchetti",
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
    "Config File Conflicts…": "Conflitti nei file di configurazione…",
    "Config File Conflicts": "Conflitti nei file di configurazione",
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
    "Pachul is a graphical package manager for Arch, Debian/Ubuntu, Fedora and openSUSE. Search, install, update and remove packages, review config file conflicts, keep external tools (rustup, npm, pip, Flatpak, …) up to date, and more — all from one native GTK4/libadwaita app.":
        "Pachul è un gestore di pacchetti grafico per Arch, Debian/Ubuntu, Fedora e openSUSE. Cerca, installa, aggiorna e rimuovi pacchetti, controlla i conflitti nei file di configurazione, mantieni aggiornati strumenti esterni (rustup, npm, pip, Flatpak, …) e molto altro — tutto in un'unica app nativa GTK4/libadwaita.",
    "Version {v}": "Versione {v}",
    "Developer": "Sviluppatore",
    "License": "Licenza",
    "Distro": "Distribuzione",
    "Package Manager": "Gestore pacchetti",
    "Website": "Sito web",
    "Report an Issue": "Segnala un problema",
    "Copy Debug Info": "Copia informazioni di debug",
    "Copied!": "Copiato!",

    # Help dialog
    "Help": "Aiuto",
    "More Update Sources…": "Altre fonti di aggiornamento…",
    "Ignored Packages…": "Pacchetti ignorati…",
    "Browsing & Search": "Navigazione e ricerca",
    "New Packages / All Packages / Installed / Updates": "Nuovi pacchetti / Tutti i pacchetti / Installati / Aggiornamenti",
    "Sidebar filters for the package list — what's newly available, everything, only what's installed, or only what has an update pending.":
        "Filtri della barra laterale per l'elenco pacchetti — novità, tutto, solo installati, oppure solo quelli con un aggiornamento in sospeso.",
    "Type in the search bar (or press Ctrl+F) to filter the current list by name or description.":
        "Digita nella barra di ricerca (o premi Ctrl+F) per filtrare l'elenco attuale per nome o descrizione.",
    "Package details": "Dettagli del pacchetto",
    "Click any package to see its description, version, size, dependencies and files on the right, with Install/Remove/Update actions.":
        "Clicca su un pacchetto per vedere a destra descrizione, versione, dimensione, dipendenze e file, con le azioni Installa/Rimuovi/Aggiorna.",
    "Updating": "Aggiornamento",
    "Refresh the local package index from the repositories, without installing anything yet.":
        "Aggiorna l'indice locale dei pacchetti dai repository, senza installare ancora nulla.",
    "Sync, then rebuild the Updates list — same as pressing Ctrl+U.":
        "Sincronizza e poi ricostruisce l'elenco degli aggiornamenti — equivale a Ctrl+U.",
    "Reload the current view from what's already known locally, without contacting the repositories.":
        "Ricarica la vista attuale da ciò che è già noto localmente, senza contattare i repository.",
    "Install every pending update in one go — shown as a button whenever the Updates list isn't empty.":
        "Installa tutti gli aggiornamenti in sospeso in un colpo solo — mostrato come pulsante quando l'elenco aggiornamenti non è vuoto.",
    "Batch mode": "Modalità multi-selezione",
    "Select several packages at once (checkboxes in the list) to install or remove them together; Ctrl+A / Ctrl+Shift+A select or deselect everything currently visible.":
        "Seleziona più pacchetti insieme (caselle di controllo nell'elenco) per installarli o rimuoverli insieme; Ctrl+A / Ctrl+Maiusc+A seleziona o deseleziona tutto ciò che è visibile.",
    "Repositories": "Repository",
    "View and edit which package repositories are enabled.":
        "Visualizza e modifica quali repository di pacchetti sono attivi.",
    "Benchmark configured mirrors and switch to the fastest ones. Arch-only — Fedora and openSUSE already pick the fastest mirror automatically.":
        "Verifica i mirror configurati e passa a quelli più veloci. Solo Arch — Fedora e openSUSE scelgono già automaticamente il mirror più veloce.",
    "Tools": "Strumenti",
    "List packages that were pulled in as dependencies but are no longer needed by anything, so you can clean them up.":
        "Elenca i pacchetti installati come dipendenze ma non più necessari, così puoi rimuoverli.",
    "Look up which installed package owns a given file path.":
        "Verifica a quale pacchetto installato appartiene un determinato percorso di file.",
    "Review and merge configuration files a package update left behind instead of overwriting your local changes.":
        "Controlla e unisce i file di configurazione lasciati da un aggiornamento invece di sovrascrivere le tue modifiche locali.",
    "Check for updates outside the system package manager — rustup, npm, pip, Flatpak, and similar tools.":
        "Controlla gli aggiornamenti al di fuori del gestore pacchetti di sistema — rustup, npm, pip, Flatpak e strumenti simili.",
    "Hold specific packages back from updates.":
        "Esclude specifici pacchetti dagli aggiornamenti.",
    "Browse a log of past installs, removals and updates.":
        "Sfoglia un registro delle installazioni, rimozioni e aggiornamenti passati.",
    "Overview of the system, hardware and installed packages.":
        "Panoramica del sistema, dell'hardware e dei pacchetti installati.",
    "Free up disk space by clearing old cached package files.":
        "Libera spazio su disco eliminando i vecchi file dei pacchetti nella cache.",
    "Package Lists": "Elenchi pacchetti",
    "Save the list of explicitly installed packages to a file — handy for setting up another machine the same way.":
        "Salva l'elenco dei pacchetti installati esplicitamente in un file — utile per configurare allo stesso modo un'altra macchina.",
    "Install every package from a previously exported list.":
        "Installa tutti i pacchetti da un elenco esportato in precedenza.",
    "AUR / Advanced": "AUR / Avanzate",
    "Inspect the build script of an AUR package before installing it.":
        "Esamina lo script di compilazione di un pacchetto AUR prima di installarlo.",
    "Toggle whether the selected packages are excluded from updates.":
        "Attiva/disattiva l'esclusione dei pacchetti selezionati dagli aggiornamenti.",
    "Mark Selected as Explicit / as Dependency": "Segna selezione come esplicita / come dipendenza",
    "Change how a package is tracked, so orphan-cleanup treats it correctly.":
        "Modifica il modo in cui un pacchetto viene tracciato, così la pulizia degli orfani lo gestisce correttamente.",
    "App-wide settings: language, theme, and other options.":
        "Impostazioni dell'intera app: lingua, tema e altre opzioni.",
    "Version, license and system info for bug reports.":
        "Versione, licenza e informazioni di sistema per le segnalazioni di bug.",
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
    "Hold isn't available for Flatpak/Snap packages": "Il blocco non è disponibile per i pacchetti Flatpak/Snap",
    "Not applicable to Flatpak/Snap packages": "Non applicabile ai pacchetti Flatpak/Snap",
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
    "Scanning for config file conflicts…": "Ricerca di conflitti nei file di configurazione…",
    "Nothing to Merge": "Niente da unire",
    "No .pacnew or .pacsave files were found.": "Non è stato trovato alcun file .pacnew o .pacsave.",
    "No config file conflicts were found.": "Non è stato trovato alcun conflitto nei file di configurazione.",
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
    "Additional Package Sources": "Fonti di pacchetti aggiuntive",
    "Show installed Flatpak/Snap apps alongside pacman packages, and include them when searching. Flatpak installs use --user (no password needed); Snap always needs one, since snapd requires root.":
        "Mostra le app Flatpak/Snap installate insieme ai pacchetti pacman e le include nelle ricerche. Le installazioni Flatpak usano --user (nessuna password richiesta); Snap ne richiede sempre una, poiché snapd necessita di privilegi di root.",
    "flatpak isn't installed": "flatpak non è installato",
    "snap isn't installed": "snap non è installato",
    "Flatpak (user installation)": "Flatpak (installazione utente)",
    "Snap package": "Pacchetto Snap",
    "Behaviour": "Comportamento",
    "Confirm before removing packages": "Conferma prima di rimuovere i pacchetti",
    "Check for updates on startup": "Controlla aggiornamenti all'avvio",
    "Notify when updates are available": "Notifica quando sono disponibili aggiornamenti",
    "Show Arch news before upgrades": "Mostra le notizie di Arch prima degli aggiornamenti",
    "Warns about manual interventions before a system upgrade":
        "Avvisa di interventi manuali prima di un aggiornamento di sistema",
    "Tray Icon": "Icona nella barra di stato",
    "A persistent icon showing the pending update count":
        "Un'icona persistente che mostra il numero di aggiornamenti in sospeso",
    "Start automatically at login": "Avvia automaticamente all'accesso",
    "Install Pachul?": "Installare Pachul?",
    "Pachul isn't installed system-wide yet. Installing adds an "
    "app-menu entry and the pachul / pachul-tray commands, and "
    "installs any missing dependencies — this needs your password.":
        "Pachul non è ancora installato a livello di sistema. L'installazione aggiunge una "
        "voce nel menu delle applicazioni e i comandi pachul / pachul-tray, e "
        "installa le dipendenze mancanti — è necessaria la tua password.",
    "Not Now": "Non ora",
    "Install Pachul": "Installa Pachul",
    "Pachul installed — available from the app menu from now on.":
        "Pachul installato — d'ora in poi disponibile anche dal menu delle applicazioni.",
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
    "(machine-translated from English)": "(tradotto automaticamente dall'inglese)",
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

    # Tray indicator (tray.py)
    "Open Pachul": "Apri Pachul",
    "Checking for updates…": "Verifica aggiornamenti…",

    # ── Repair System (pacman), Arch-only ───────────────────────────────────
    "Repair System (pacman)…": "Ripara sistema (pacman)…",
    "These run real pacman/pacman-key commands with sudo — read what each "
    "one does before running it, especially the last one.":
        "Questi eseguono veri comandi pacman/pacman-key con sudo — leggi "
        "cosa fa ciascuno prima di eseguirlo, in particolare l'ultimo.",
    "Standard Maintenance": "Manutenzione standard",
    "Last Resort": "Ultima risorsa",
    "Force-Refresh & Full Upgrade": "Aggiornamento forzato e upgrade completo",
    "Runs 'pacman -Syyu' — forces a fresh download of all repo "
    "databases (ignoring their last-sync timestamps) before "
    "upgrading, useful when a mirror served stale or corrupt data.":
        "Esegue «pacman -Syyu» — forza un nuovo download di tutti i database "
        "dei repository (ignorando la data dell'ultima sincronizzazione) prima "
        "dell'upgrade, utile quando un mirror ha fornito dati obsoleti o "
        "corrotti.",
    "Check Package Database Consistency": "Verifica coerenza del database dei pacchetti",
    "Runs 'pacman -Dk' to check the local package database itself "
    "for internal inconsistencies (separate from checking individual "
    "installed files).":
        "Esegue «pacman -Dk» per verificare che il database locale dei "
        "pacchetti non presenti incoerenze interne (indipendentemente dalla "
        "verifica dei singoli file installati).",
    "Reinitialize Keyring": "Reinizializza il portachiavi",
    "Runs 'pacman-key --init' and '--populate archlinux' — a deeper "
    "fix than the automatic keyring banner elsewhere, for when "
    "signature errors persist after that lighter fix.":
        "Esegue «pacman-key --init» e «--populate archlinux» — una riparazione "
        "più profonda rispetto al banner automatico del portachiavi altrove, "
        "per quando gli errori di firma persistono dopo quella soluzione più "
        "leggera.",
    "Search for Packages With Missing/Modified Files": "Cerca pacchetti con file mancanti/modificati",
    "Runs 'pacman -Qkk' with sudo (read-only, no changes are made). "
    "If any packages come back altered, you'll be asked right away "
    "which ones to repair.":
        "Esegue «pacman -Qkk» con sudo (sola lettura, nessuna modifica viene "
        "apportata). Se vengono segnalati pacchetti alterati, ti verrà "
        "chiesto subito quali riparare.",
    "Run": "Esegui",
    "Repair Broken Packages": "Ripara pacchetti danneggiati",
    "{n} package(s) with missing or altered files found":
        "{n} pacchetto/i con file mancanti o alterati trovato/i",
    "Choose which ones to reinstall from your configured "
    "repositories to restore the original files:":
        "Scegli quali reinstallare dai tuoi repository configurati "
        "per ripristinare i file originali:",
    "Repair {n} package(s)": "Ripara {n} pacchetto/i",
    "(+{n} more)": "(+{n} altri)",
    "({n} more package(s) with only config/permission "
    "differences are hidden — reinstalling never touches "
    "those.)":
        "({n} altro/i pacchetto/i con solo differenze di config/permessi "
        "sono nascosti — la reinstallazione non li tocca mai.)",
    "All {n} package(s) only have config/permission "
    "differences a reinstall can't fix.":
        "Tutti i {n} pacchetto/i hanno solo differenze di config/permessi "
        "che una reinstallazione non può correggere.",
    "Select All": "Seleziona tutto",
    "Select None": "Deseleziona tutto",
    "Last resort for a single package pacman refuses to touch normally "
    "— removes it while ignoring dependency checks entirely. Only use "
    "this if the steps above didn't help, and only on the one package "
    "causing the problem.":
        "Ultima risorsa per un singolo pacchetto che pacman normalmente "
        "rifiuta di toccare — lo rimuove ignorando completamente il "
        "controllo delle dipendenze. Usa questa opzione solo se i passaggi "
        "precedenti non hanno aiutato, e solo per il pacchetto che causa il "
        "problema.",
    "Force-Remove Broken Package": "Forza rimozione pacchetto danneggiato",
    "Package name": "Nome del pacchetto",
}


_TABLES = {
    "de": STRINGS_DE,
    "fr": STRINGS_FR,
    "it": STRINGS_IT,
}

# Kept for backward compatibility (some code may still reference STRINGS directly)
STRINGS = STRINGS_DE
