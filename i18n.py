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
Bau ihren Text nicht automatisch neu abfragen, baut pachulWindow bei jeder
Einstellungsänderung (Sprache, Flatpak/Snap, ...) im Einstellungen-Dialog
seine komplette Oberfläche einmal neu auf (siehe
pachulWindow._rebuild_ui_preserving_state() in window.py), damit auch
länger lebende Widgets (Seitenleiste, Menü, Kopfzeile, leere Zustände) den
neuen Text bzw. neue/entfernte Seitenleisten-Einträge sofort zeigen.
Dialoge und Paketzeilen sind davon ohnehin nicht betroffen, da sie bei
jedem Öffnen/Neuladen frisch mit tr() aufgebaut werden.
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
    'Setting up makepkg to use pkexec for build dependencies (one-time)…': 'makepkg wird für Build-Abhängigkeiten auf pkexec eingestellt (einmalig)…',
    'Build dependency prompts use pkexec': 'Abfragen für Build-Abhängigkeiten nutzen pkexec',
    '/etc/makepkg.conf already points PACMAN_AUTH at pkexec, so missing build dependencies get a native graphical prompt.': 'In /etc/makepkg.conf zeigt PACMAN_AUTH bereits auf pkexec, fehlende Build-Abhängigkeiten werden daher mit einem grafischen Dialog abgefragt.',
    'Note: this run had several steps. Steps above may have completed successfully even though the whole run is marked as failed.\n': 'Hinweis: Dieser Lauf bestand aus mehreren Schritten. Die Schritte weiter oben können erfolgreich gewesen sein, auch wenn der gesamte Lauf als fehlgeschlagen markiert ist.\n',
    'Probable cause (last error lines):\n': 'Wahrscheinliche Ursache (letzte Fehlerzeilen):\n',
    # ── Sort menu + details switch ──
    "Selected first": "Markierte zuerst",
    "Details": "Details",
    "Name": "Name",
    "Repository": "Repository",
    "Status": "Status",
    "Descending order": "Absteigend sortieren",
    "Sort packages": "Pakete sortieren",
    "Show or hide the package details (Ctrl+D)": "Paketdetails ein- oder ausblenden (Strg+D)",
    "Show/hide package details": "Paketdetails ein-/ausblenden",
    "Detected automatically from your system settings": "Automatisch anhand der Systemeinstellungen erkannt",
    "Advanced options": "Erweiterte Optionen",
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
    "New AUR Packages": "Neue AUR-Pakete",
    "New Flatpak Packages": "Neue Flatpak-Pakete",
    "New Chaotic-AUR Packages": "Neue Chaotic-AUR-Pakete",
    "AUR / Foreign": "AUR / Fremd",
    "NEW": "NEU",
    "INSTALLED PACKAGES": "INSTALLIERTE PAKETE",
    "All Installed Packages": "Alle installierten Pakete",
    "All New Packages": "Alle neuen Pakete",
    "REPOSITORIES": "REPOSITORIES",
    "TOOLS": "WERKZEUGE",
    "Check Updates": "Updates prüfen",
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
    "Find Fastest Mirrors…": "Schnellste Spiegelserver finden…",
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
    "Terminal Commands": "Terminal-Befehle",
    "Launches the main window — same as clicking the app icon.":
        "Startet das Hauptfenster — entspricht dem Klick auf das App-Symbol.",
    "Launches the standalone tray icon showing pending updates (requires libayatana-appindicator).":
        "Startet das eigenständige Tray-Symbol, das ausstehende Updates anzeigt (benötigt libayatana-appindicator).",
    "Removes a stray install.sh-based installation that's blocking an AUR package install/upgrade with a \"conflicting files\" error. Run as: sudo pachul-uninstall":
        "Entfernt eine übrig gebliebene install.sh-Installation, die eine AUR-Paketinstallation/-Aktualisierung mit einem \"conflicting files\"-Fehler blockiert. Aufruf: sudo pachul-uninstall",
    "Pachul's own minimal AUR helper, with a pacman/yay-style command-line syntax (an operation letter -S/-R/-Q/-Y plus stackable modifiers, e.g. -Ss, -Syu, -Rns). The commands below cover every combination it supports; running pachuli --help in a terminal prints the same reference.":
        "Pachuls eigener, minimaler AUR-Helfer mit einer Kommandozeilen-Syntax im pacman/yay-Stil (ein Operations-Buchstabe -S/-R/-Q/-Y plus stapelbare Modifikatoren, z.B. -Ss, -Syu, -Rns). Die folgenden Befehle decken alle unterstützten Kombinationen ab; pachuli --help im Terminal zeigt dieselbe Referenz.",
    "pachuli <suchbegriff ...>": "pachuli <suchbegriff ...>",
    "Bare mode (like \"yay <term>\"): searches like -Ss and then asks which numbered results to install directly, e.g. \"1 3\", \"1-3\", \"^4\" or \"all\".":
        "Bare-Modus (wie \"yay <begriff>\"): sucht wie -Ss und fragt danach per Nummer(n) ab, welche Treffer direkt installiert werden sollen, z.B. \"1 3\", \"1-3\", \"^4\" oder \"all\".",
    "pachuli -Ss <suchbegriff>": "pachuli -Ss <suchbegriff>",
    "Searches both the AUR and the repositories for the given term and lists the matches.":
        "Sucht im AUR und in den Repositories nach dem angegebenen Begriff und listet die Treffer auf.",
    "pachuli -S <paket ...>": "pachuli -S <paket ...>",
    "Installs the given package(s), building AUR packages with makepkg as needed.":
        "Installiert die angegebenen Pakete, AUR-Pakete werden dabei bei Bedarf mit makepkg gebaut.",
    "pachuli -Su [paket ...]": "pachuli -Su [paket ...]",
    "Checks for and installs updates without refreshing the repository database first — repo packages are upgraded from the local cache only.":
        "Prüft auf Updates und installiert sie, ohne vorher die Repository-Datenbank zu aktualisieren — Repo-Pakete werden nur aus dem lokalen Cache aktualisiert.",
    "pachuli -Syu": "pachuli -Syu",
    "Like -Su, but also refreshes the repository database first (only if it looks outdated).":
        "Wie -Su, aktualisiert aber vorher zusätzlich die Repository-Datenbank (nur falls diese veraltet wirkt).",
    "pachuli -Syyu": "pachuli -Syyu",
    "Like -Syu, but forces a repository database refresh even if it looks up to date.":
        "Wie -Syu, erzwingt aber die Aktualisierung der Repository-Datenbank, auch wenn diese aktuell wirkt.",
    "pachuli -Si <paket ...>": "pachuli -Si <paket ...>",
    "Shows sync/AUR details for package(s) that aren't installed yet.":
        "Zeigt Sync-/AUR-Details zu Paketen, die noch nicht installiert sind.",
    "pachuli -Sp <paket ...>": "pachuli -Sp <paket ...>",
    "Fetches and prints a package's PKGBUILD without building or installing it.":
        "Ruft das PKGBUILD eines Pakets ab und zeigt es an, ohne zu bauen oder zu installieren.",
    "pachuli -Sc": "pachuli -Sc",
    "Clears cached package files that are no longer the currently installed version.":
        "Leert zwischengespeicherte Paketdateien, die nicht mehr der aktuell installierten Version entsprechen.",
    "pachuli -Scc": "pachuli -Scc",
    "Clears the entire package cache, including files for currently installed versions.":
        "Leert den kompletten Paket-Cache, einschließlich der Dateien aktuell installierter Versionen.",
    "pachuli -R <paket ...>": "pachuli -R <paket ...>",
    "Removes the given package(s), keeping their configuration files.":
        "Entfernt die angegebenen Pakete, behält deren Konfigurationsdateien aber bei.",
    "pachuli -Rns <paket ...>": "pachuli -Rns <paket ...>",
    "Removes the given package(s) together with their configuration files.":
        "Entfernt die angegebenen Pakete zusammen mit ihren Konfigurationsdateien.",
    "pachuli -Qu": "pachuli -Qu",
    "Lists available updates as \"name old -> new\", the same way \"yay -Qu\" does.":
        "Listet verfügbare Updates als \"name alt -> neu\" auf, genau wie \"yay -Qu\".",
    "pachuli -Qu -q": "pachuli -Qu -q",
    "Like -Qu, but prints only the bare count — handy for status lines or scripts.":
        "Wie -Qu, gibt aber nur die nackte Anzahl aus — praktisch für Statuszeilen oder Skripte.",
    "pachuli -Qi [paket ...]": "pachuli -Qi [paket ...]",
    "Shows detailed info for installed packages, all of them if none are named, like \"pacman -Qi\".":
        "Zeigt Detailinfos zu installierten Paketen, bei leerer Angabe zu allen, wie \"pacman -Qi\".",
    "pachuli -Qii [paket ...]": "pachuli -Qii [paket ...]",
    "Like -Qi, but also lists backup configuration files and whether they were modified.":
        "Wie -Qi, listet zusätzlich Backup-Konfigurationsdateien und deren Änderungsstatus auf.",
    "pachuli -Yc": "pachuli -Yc",
    "Finds and removes orphaned dependencies — packages pulled in as dependencies that nothing needs anymore, like \"yay -Yc\".":
        "Findet und entfernt verwaiste Abhängigkeiten — als Abhängigkeit installierte Pakete, die niemand mehr benötigt, wie \"yay -Yc\".",
    "pachuli --help": "pachuli --help",
    "Prints the full built-in command reference, including all modifiers and options.":
        "Gibt die vollständige eingebaute Befehlsreferenz aus, inklusive aller Modifikatoren und Optionen.",
    "pachuli --version": "pachuli --version",
    "Prints the installed pachuli version.":
        "Gibt die installierte pachuli-Version aus.",
    "App-wide settings: language, theme, and other options.":
        "App-weite Einstellungen: Sprache, Theme und weitere Optionen.",

    # ── Startup health check ──
    "Check for fixable system problems on startup": "Beim Start auf behebbare Systemprobleme prüfen",
    "Scans for things like failed services, no active firewall, expired certificates or a broken package database, and lets you jump straight to the matching built-in tool. Read-only, no password needed.":
        "Prüft z.B. auf fehlgeschlagene Dienste, keine aktive Firewall, abgelaufene Zertifikate oder eine beschädigte Paketdatenbank, und führt direkt zum passenden eingebauten Werkzeug. Rein lesend, kein Passwort nötig.",
    "Startup Check": "Systemcheck beim Start",
    "{n} thing(s) found that a built-in tool can help with. Nothing has been changed — pick one to open the matching tool.":
        "{n} Fund(e), bei denen ein eingebautes Werkzeug helfen kann. Es wurde nichts verändert — wähle einen Eintrag, um das passende Werkzeug zu öffnen.",
    "1 thing found that a built-in tool can help with. Nothing has been changed — open it below to fix it.":
        "1 Fund, bei dem ein eingebautes Werkzeug helfen kann. Es wurde nichts verändert — öffne ihn unten, um ihn zu beheben.",
    "Findings": "Funde",
    "You can turn this check off anytime in Preferences → Behaviour.":
        "Diese Prüfung kann jederzeit in den Einstellungen → Verhalten deaktiviert werden.",
    "{n} systemd service(s) failed": "{n} systemd-Dienst(e) fehlgeschlagen",
    "SSH allows direct root login": "SSH erlaubt direkten Root-Login",
    "PermitRootLogin yes is set in /etc/ssh/sshd_config.":
        "PermitRootLogin yes ist in /etc/ssh/sshd_config gesetzt.",
    "No active firewall detected": "Keine aktive Firewall erkannt",
    "Neither UFW nor firewalld is currently active.":
        "Weder UFW noch firewalld sind derzeit aktiv.",
    "A leftover db.lck is blocking every pacman operation.":
        "Eine zurückgebliebene db.lck blockiert jede pacman-Operation.",
    "Pacman database consistency issues found": "Inkonsistenzen in der Pacman-Datenbank gefunden",
    "{n} broken/incomplete package(s) (dpkg)": "{n} defekte(s)/unvollständige(s) Paket(e) (dpkg)",
    "dnf check reports package problems": "dnf check meldet Paketprobleme",
    "{n} expired local certificate(s)": "{n} abgelaufene(s) lokale(s) Zertifikat(e)",
    "{n} orphaned license symlink(s) (safe to remove)": "{n} verwaiste(r) Lizenz-Symlink(s) (gefahrlos entfernbar)",
    "Startup check: no problems found": "Systemcheck: keine Probleme gefunden",
    "Opened": "Geöffnet",
    "zypper verify suggests possible package problems (heuristic — please double-check)":
        "zypper verify deutet auf mögliche Paketprobleme hin (heuristisch — bitte selbst nachprüfen)",
    "Check again": "Erneut prüfen",
    "Nothing Left to Fix": "Nichts mehr zu beheben",
    "A re-check no longer finds any of the earlier issues.":
        "Eine erneute Prüfung findet keinen der vorherigen Punkte mehr.",
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
    "Select only one package for this action": "Bitte für diese Aktion nur ein Paket auswählen",
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
    "Input for the running command (rarely needed) — press Enter to send": "Eingabe für den laufenden Befehl (selten nötig) — Enter zum Senden",
    "Show input": "Eingabe anzeigen",
    "Hide input": "Eingabe verbergen",
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
    "What is a repository?":
        "Was ist ein Repositorium?",
    "A repository (repo) is a package archive on a server from which pacman fetches programs and updates.":
        "Ein Repositorium (kurz Repo) ist ein Paketarchiv auf einem Server, aus dem pacman Programme und Updates bezieht.",
    "If a repository is missing: its packages can no longer be found or installed, and already installed packages from it receive no further updates (for example, without «multilib» there is no 32-bit software such as Steam or Wine; without «core» or «extra» the system itself can no longer be updated properly).":
        "Wenn ein Repositorium fehlt: Dessen Pakete sind nicht mehr auffindbar oder installierbar, und bereits installierte Pakete daraus erhalten keine Updates mehr (z. B. gibt es ohne «multilib» keine 32-Bit-Software wie Steam oder Wine; ohne «core» oder «extra» lässt sich das System selbst nicht mehr richtig aktualisieren).",
    "If additional repositories are added: their packages appear in the search and can be installed. However, this can cause dependency and version conflicts, for example when a repository offers different versions of system libraries, which can block updates or break the system. Only add third-party repositories from sources you trust.":
        "Wenn zusätzliche Repositorien hinzugefügt werden: Deren Pakete erscheinen in der Suche und können installiert werden. Das kann jedoch zu Abhängigkeits- und Versionskonflikten führen, etwa wenn ein Repositorium andere Versionen von Systembibliotheken anbietet. Dadurch können Updates blockiert werden oder das System kann beschädigt werden. Füge Repositorien von Drittanbietern nur aus vertrauenswürdigen Quellen hinzu.",
    "What are .pacnew and .pacsave files?":
        "Was sind .pacnew- und .pacsave-Dateien?",
    "If you changed a configuration file yourself and the package ships a new version of it, pacman does not overwrite your file. It saves the new default next to it as «.pacnew». If you remove a package whose configuration file you changed, your file is kept as «.pacsave».":
        "Hast du eine Konfigurationsdatei selbst geändert und das Paket bringt eine neue Version davon mit, überschreibt pacman deine Datei nicht. Stattdessen legt es die neue Standardversion daneben als «.pacnew» ab. Entfernst du ein Paket, dessen Konfigurationsdatei du geändert hast, wird deine Datei als «.pacsave» behalten.",
    "«Use New (overwrite)» replaces your file with the new one — your own settings in it are lost. «Discard» only deletes the .pacnew file and keeps your version, which may then lack new options or contain outdated ones. Check the diff first.":
        "«Neue verwenden (überschreiben)» ersetzt deine Datei durch die neue – deine eigenen Einstellungen darin gehen verloren. «Verwerfen» löscht nur die .pacnew-Datei und behält deine Version, der dann neue Optionen fehlen oder die veraltete enthalten kann. Prüfe darum zuerst den Vergleich (Diff).",
    "What does “ignored” mean?":
        "Was bedeutet «ignoriert»?",
    "Ignored (held) packages are skipped by system upgrades and stay at their current version until you unignore them.":
        "Ignorierte (festgehaltene) Pakete werden bei Systemupdates übersprungen und bleiben auf ihrer aktuellen Version, bis du sie wieder freigibst.",
    "Be careful: if a package stays old while the libraries it depends on are upgraded, it may stop working or block other updates. Hold packages only temporarily, for example until a known bug is fixed.":
        "Vorsicht: Bleibt ein Paket alt, während die Bibliotheken, von denen es abhängt, aktualisiert werden, kann es nicht mehr funktionieren oder andere Updates blockieren. Halte Pakete deshalb nur vorübergehend fest, zum Beispiel bis ein bekannter Fehler behoben ist.",
    "Arch does not officially support partial upgrades, so every ignored package is a small risk for the whole system.":
        "Arch unterstützt Teil-Updates offiziell nicht – jedes ignorierte Paket ist ein kleines Risiko für das ganze System.",
    "What is the package cache?":
        "Was ist der Paket-Cache?",
    "When you install or update software, the package manager keeps the downloaded package files. This lets you reinstall a package without downloading it again, or go back to an older version.":
        "Beim Installieren und Aktualisieren behält der Paketmanager die heruntergeladenen Paketdateien. So lässt sich ein Paket ohne neuen Download neu installieren oder auf eine ältere Version zurücksetzen.",
    "The cache keeps growing and can take up many gigabytes. Cleaning it is safe for the running system, but older versions are no longer available locally afterwards — so better not clean it right after an update that causes problems, you may still need the old version.":
        "Der Cache wächst mit der Zeit und kann viele Gigabyte belegen. Das Aufräumen ist für das laufende System unbedenklich, danach stehen ältere Versionen aber nicht mehr lokal zur Verfügung. Räume den Cache deshalb besser nicht direkt nach einem Update auf, das Probleme macht – du könntest die alte Version noch brauchen.",
    "Hide this hint":
        "Diesen Hinweis ausblenden",
    "Show the active repositories and edit pacman.conf":
        "Aktive Repositorien anzeigen und pacman.conf bearbeiten",
    "What are mirrors?":
        "Was sind Spiegelserver?",
    "Mirrors are servers that hold copies of the package archives. pacman downloads packages and updates from the servers listed in /etc/pacman.d/mirrorlist, trying them from top to bottom.":
        "Spiegelserver (Mirrors) sind Server, die Kopien der Paketarchive bereithalten. pacman lädt Pakete und Updates von den Servern in /etc/pacman.d/mirrorlist und probiert sie von oben nach unten durch.",
    "rate-mirrors measures which servers respond fastest from your location and puts them first. This helps with slow downloads, errors such as 404 or timeouts, or after moving to another country. The result is only shown first — your current list is replaced only when you save.":
        "rate-mirrors misst, welche Server von deinem Standort aus am schnellsten antworten, und setzt sie an den Anfang. Das hilft bei langsamen Downloads, bei Fehlern wie 404 oder Zeitüberschreitungen und nach einem Umzug in ein anderes Land. Das Ergebnis wird zuerst nur angezeigt – deine aktuelle Liste wird erst ersetzt, wenn du speicherst.",
    "Tip: keep «Backup current mirrorlist» switched on (only the most recent backup is kept). After saving, sync the databases so pacman uses the new servers («Sync Databases»).":
        "Tipp: Lass «Aktuelle Spiegelserverliste sichern» eingeschaltet (es wird nur die jeweils letzte Sicherung behalten). Synchronisiere nach dem Speichern die Datenbanken («Datenbanken synchronisieren»), damit pacman die neuen Server verwendet.",
    "On Manjaro this list is normally managed by pacman-mirrors; running pacman-mirrors later can replace your result.":
        "Unter Manjaro wird diese Liste normalerweise von pacman-mirrors verwaltet; ein späterer Lauf von pacman-mirrors kann dein Ergebnis wieder ersetzen.",
    "Choose how mirrors are selected and tested":
        "Lege fest, wie Spiegelserver ausgewählt und getestet werden",
    "Only use mirrors from these countries — 2-letter codes separated by commas, e.g. CH, DE, AT. Leave blank for all.":
        "Nur Spiegelserver aus diesen Ländern verwenden – 2-Buchstaben-Codes, durch Komma getrennt, z. B. CH, DE, AT. Leer lassen für alle.",
    "e.g. CH, DE, AT":
        "z. B. CH, DE, AT",
    "Order in which mirrors are picked for testing; the final order always comes from the speed test":
        "Reihenfolge, in der Spiegelserver zum Testen ausgewählt werden; die endgültige Reihenfolge ergibt sich immer aus dem Geschwindigkeitstest",
    "Ignore unencrypted HTTP mirrors (recommended)":
        "Unverschlüsselte HTTP-Spiegelserver ignorieren (empfohlen)",
    "Copies the current list to /etc/pacman.d/mirrorlist-backup before replacing it (an older backup is overwritten)":
        "Kopiert die aktuelle Liste nach /etc/pacman.d/mirrorlist-backup, bevor sie ersetzt wird (eine ältere Sicherung wird überschrieben)",
    "Skip mirrors whose last sync is older than this":
        "Spiegelserver überspringen, deren letzte Synchronisierung länger zurückliegt",
    "How many of the fastest mirrors end up in the list (0 = all). 3 is usually enough.":
        "Wie viele der schnellsten Spiegelserver in die Liste übernommen werden (0 = alle). 3 reichen meist.",
    "{n} mirrors found, fastest first. Review the list, then save it as your new mirrorlist or discard it.":
        "{n} Spiegelserver gefunden, die schnellsten zuerst. Prüfe die Liste und speichere sie dann als neue Spiegelserverliste oder verwirf sie.",
    "rate-mirrors measures how fast mirrors respond from your location and sorts your mirrorlist accordingly. Testing needs no administrator rights.":
        "rate-mirrors misst, wie schnell Spiegelserver von deinem Standort aus antworten, und sortiert deine Spiegelserverliste entsprechend. Für den Test sind keine Administratorrechte nötig.",
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
    "pachuli found but not installed": "pachuli gefunden, aber nicht installiert",
    "A pachuli.py was found next to Pachul's own files but isn't "
    "on your PATH yet, so it can't be used as the AUR helper. "
    "Installs it as-is to /usr/local/bin — same place as the "
    "pachul launcher itself — no build step, just the one-time "
    "authentication any system-wide install needs.":
        "Eine pachuli.py wurde neben den eigenen Dateien von Pachul gefunden, "
        "steht aber noch nicht im PATH und kann daher nicht als AUR-Helfer "
        "genutzt werden. Wird unverändert nach /usr/local/bin installiert — "
        "derselbe Ort wie der pachul-Launcher selbst — kein Bauvorgang nötig, "
        "nur die einmalige Authentifizierung, die jede systemweite "
        "Installation braucht.",
    "Install pachuli": "pachuli installieren",
    "Build dependency prompts still use sudo": "Abhängigkeits-Abfragen beim Bauen laufen noch über sudo",
    "While building an AUR package, makepkg installs any missing "
    "dependencies itself — outside pachuli/yay/paru's own pkexec "
    "or sudo call — and always does so via a plain sudo prompt in "
    "the terminal panel, by default. This points /etc/makepkg.conf "
    "at pkexec instead, so that step gets a native graphical "
    "prompt too, same as the rest of every upgrade.":
        "Beim Bauen eines AUR-Pakets installiert makepkg fehlende Abhängigkeiten "
        "selbst — unabhängig vom eigenen pkexec- oder sudo-Aufruf von "
        "pachuli/yay/paru — und fragt dafür standardmässig immer über eine "
        "einfache sudo-Abfrage im Terminal-Panel nach. Dies trägt in "
        "/etc/makepkg.conf stattdessen pkexec ein, sodass auch dieser "
        "Schritt einen echten grafischen Dialog erhält, wie der Rest jedes "
        "Updates.",
    "Use pkexec for build dependencies": "pkexec für Build-Abhängigkeiten verwenden",
    "Include AUR in update checks": "AUR bei Update-Prüfungen einbeziehen",
    "Additional Package Sources": "Zusätzliche Paketquellen",
    "Show installed Flatpak/Snap apps alongside pacman packages, and include them when searching. Flatpak installs use --user (no password needed); Snap always needs one, since snapd requires root.":
        "Zeigt installierte Flatpak-/Snap-Apps zusammen mit Pacman-Paketen an und bezieht sie in die Suche mit ein. Flatpak-Installationen laufen über --user (kein Passwort nötig); bei Snap wird immer eines benötigt, da snapd Root-Rechte braucht.",
    "flatpak isn't installed": "flatpak ist nicht installiert",
    "snap isn't installed": "snap ist nicht installiert",
    "snap isn't installed (AUR-only on Arch — installs snapd via pachuli)":
        "snap ist nicht installiert (auf Arch nur über AUR — installiert snapd über pachuli)",
    "snap isn't installed (AUR-only on Arch — install pachuli above first)":
        "snap ist nicht installiert (auf Arch nur über AUR — installiere zuerst pachuli weiter oben)",
    "Install Flatpak": "Flatpak installieren",
    "Install Snap": "Snap installieren",
    "Uninstall Flatpak": "Flatpak deinstallieren",
    "Uninstall Snap": "Snap deinstallieren",
    "Uninstall Flatpak?": "Flatpak deinstallieren?",
    "Removes the flatpak package. Any Flatpak apps installed through it will stop working until it's reinstalled.":
        "Entfernt das Paket flatpak. Darüber installierte Flatpak-Apps funktionieren erst wieder, wenn es neu installiert wird.",
    "Uninstall Snap?": "Snap deinstallieren?",
    "Removes snapd. Any Snap apps installed through it will stop working until it's reinstalled.":
        "Entfernt snapd. Darüber installierte Snap-Apps funktionieren erst wieder, wenn es neu installiert wird.",
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
    "Update Pachul?": "Pachul aktualisieren?",
    "A newer version of Pachul was found in this checkout "
    "than the one currently installed system-wide. Updating "
    "replaces the installed files with this version — this "
    "needs your password.":
        "In diesem Checkout wurde eine neuere Version von Pachul gefunden "
        "als die aktuell systemweit installierte. Die Aktualisierung "
        "ersetzt die installierten Dateien durch diese Version — dafür "
        "wird dein Passwort benötigt.",
    "Update": "Aktualisieren",
    "Pachul updated.": "Pachul wurde aktualisiert.",
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
    "Select all visible packages": "Alle sichtbaren Pakete auswählen",
    "Deselect all packages": "Alle Pakete abwählen",
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
    "Choose Version…": "Version wählen…",
    "Install one of the last 5 versions. The package stays ignored.":
        "Eine der letzten 5 Versionen installieren. Das Paket bleibt ignoriert.",
    "Choose Version of {pkg}": "Version von {pkg} wählen",
    "Looking for available versions…": "Suche nach verfügbaren Versionen…",
    "No other version of {pkg} was found — not in the local cache, the AUR helper build caches or the Arch Linux Archive (which only holds packages from the official repositories, and needs an internet connection).":
        "Keine andere Version von {pkg} gefunden — weder im lokalen Cache, in den Build-Caches der AUR-Helfer noch im Arch Linux Archive (das nur Pakete aus den offiziellen Repositories enthält und eine Internetverbindung braucht).",
    "No other version of {pkg} is available.": "Keine andere Version von {pkg} verfügbar.",
    "Currently installed": "Aktuell installiert",
    "AUR package: versions work differently": "AUR-Paket: Versionen funktionieren anders",
    "The AUR has no version archive like the official repositories. Pachul can only offer versions that are still on your disk: the pacman cache and the build folders of your AUR helper (yay, paru, pikaur, pachuli).":
        "Das AUR hat kein Versionsarchiv wie die offiziellen Repositories. Pachul kann nur Versionen anbieten, die noch auf deiner Festplatte liegen: im pacman-Cache und in den Build-Ordnern deines AUR-Helfers (yay, paru, pikaur, pachuli).",
    "An older version is therefore only available if you built or installed it earlier. After cleaning the helper's cache it is gone; then you would have to check out an older PKGBUILD and build it yourself.":
        "Eine ältere Version ist daher nur verfügbar, wenn du sie früher gebaut oder installiert hast. Nach dem Leeren des Helfer-Caches ist sie weg; dann müsstest du ein älteres PKGBUILD auschecken und selbst bauen.",
    "Download from Arch Linux Archive": "Download aus dem Arch Linux Archive",
    "{n} version(s) — pick one to install with pacman -U. Versions not in the local cache are downloaded from the Arch Linux Archive.":
        "{n} Version(en) — wähle eine zur Installation mit pacman -U. Versionen, die nicht im lokalen Cache liegen, werden aus dem Arch Linux Archive geladen.",
    "No package files for {pkg} were found in /var/cache/pacman/pkg or in the Arch Linux Archive.\nThe archive needs an internet connection and only holds packages from the official repositories.":
        "Für {pkg} wurden weder in /var/cache/pacman/pkg noch im Arch Linux Archive Paketdateien gefunden.\nDas Archiv braucht eine Internetverbindung und enthält nur Pakete aus den offiziellen Repositories.",
    "Show Ignored Packages ({n})…": "Ignorierte Pakete anzeigen ({n})…",
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
    'These run real apt/dpkg maintenance commands with root privileges (via pkexec) — read what each one does before running it, especially the last one.':
        'Dies sind echte apt-/dpkg-Wartungsbefehle mit Root-Rechten (via pkexec) — lies vor dem Ausführen, was jeder einzelne tut, besonders den letzten.',
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
    'These run real dnf/rpm maintenance commands with root privileges (via pkexec) — read what each one does before running it, especially the last one.':
        'Dies sind echte dnf-/rpm-Wartungsbefehle mit Root-Rechten (via pkexec) — lies vor dem Ausführen, was jeder einzelne tut, besonders den letzten.',
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
    'These run real zypper/rpm maintenance commands with root privileges (via pkexec) — read what each one does before running it, especially the last one.':
        'Dies sind echte zypper-/rpm-Wartungsbefehle mit Root-Rechten (via pkexec) — lies vor dem Ausführen, was jeder einzelne tut, besonders den letzten.',
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
    "Repair System (pacman)…": "System reparieren…",
    "These run real pacman/pacman-key commands with sudo — read what each "
    "one does before running it, especially the last one.":
        "Dies sind echte pacman-/pacman-key-Befehle mit sudo — lies vor dem "
        "Ausführen, was jeder einzelne tut, besonders den letzten.",
    "Standard Maintenance": "Standard-Wartung",
    "Last Resort": "Letzter Ausweg",
    "Force-Refresh & Full Upgrade": "Erzwungenes Neuladen & Vollupgrade",
    "Runs 'pacman -Syyu' with root privileges (via pkexec). Normally pacman only re-downloads a repo's database if its timestamp changed; this ignores that and forces a fresh download of ALL repo databases before upgrading every installed package. Use this when a mirror served you a stale or corrupted database — typical symptoms are pacman reporting packages as up to date that you know aren't, or checksum/signature errors that don't go away with a normal update. Takes longer than a regular sync since nothing is skipped, but makes no changes beyond what -Syu itself would install anyway.":
        'Führt „pacman -Syyu“ mit Root-Rechten (via pkexec) aus. Normalerweise lädt pacman die Datenbank eines Repos nur neu, wenn sich deren Zeitstempel geändert hat; das hier ignoriert das und erzwingt einen frischen Download ALLER Repo-Datenbanken, bevor jedes installierte Paket aktualisiert wird. Nutze das, wenn ein Mirror veraltete oder beschädigte Daten geliefert hat — typische Anzeichen sind, dass pacman Pakete als aktuell meldet, obwohl du weißt, dass sie es nicht sind, oder Prüfsummen-/Signaturfehler, die auch bei einem normalen Update nicht verschwinden. Dauert länger als ein normaler Sync, da nichts übersprungen wird, ändert aber nichts, was -Syu nicht ohnehin installieren würde.',
    "Check Package Database Consistency": "Paketdatenbank auf Konsistenz prüfen",
    "Runs 'pacman -Dk', a fast, read-only check. It only looks at "
    "pacman's own local database — the dependency graph and package "
    "metadata under /var/lib/pacman — for internal problems like "
    "orphaned or duplicate entries. It does NOT look at the actual "
    "installed files on disk (for that, see 'Search for Packages "
    "With Missing/Modified Files' below); the two checks are "
    "independent and catch different kinds of corruption.":
        "Führt „pacman -Dk“ aus, eine schnelle, rein lesende Prüfung. Sie "
        "betrachtet nur pacmans eigene lokale Datenbank — den "
        "Abhängigkeitsgraphen und die Paket-Metadaten unter "
        "/var/lib/pacman — auf interne Probleme wie verwaiste oder "
        "doppelte Einträge. Sie prüft NICHT die tatsächlich installierten "
        "Dateien auf der Festplatte (dafür siehe „Pakete mit fehlenden/"
        "geänderten Dateien suchen“ weiter unten); die beiden Prüfungen "
        "sind unabhängig voneinander und finden unterschiedliche Arten "
        "von Beschädigung.",
    "Reinitialize Keyring": "Keyring neu initialisieren",
    "Runs 'pacman-key --init' followed by 'pacman-key --populate archlinux' with root privileges (via pkexec). This resets and rebuilds pacman's GPG trust database from scratch and repopulates it with the official Arch Linux master keys. Use it when package signature verification keeps failing even after the lighter, automatic keyring-fix banner shown elsewhere in the app — that banner only imports one specific missing key, while this rebuilds the whole keyring. It talks to a keyserver over the network, so it can take a little while and will fail if you're offline.":
        'Führt „pacman-key --init“ und danach „pacman-key --populate archlinux“ mit Root-Rechten (via pkexec) aus. Das setzt pacmans GPG-Vertrauensdatenbank komplett zurück, baut sie neu auf und befüllt sie wieder mit den offiziellen Arch-Linux-Hauptschlüsseln. Nutze das, wenn die Signaturprüfung von Paketen weiter fehlschlägt, selbst nachdem das leichtere, automatische Keyring-Fix-Banner an anderer Stelle in der App schon lief — jenes Banner importiert nur einen bestimmten fehlenden Schlüssel, während dies den kompletten Keyring neu aufbaut. Es spricht dabei über das Netzwerk mit einem Keyserver, kann also etwas dauern und schlägt fehl, wenn du offline bist.',
    "Search for Packages With Missing/Modified Files": "Pakete mit fehlenden/geänderten Dateien suchen",
    "Runs 'pacman -Qkk' with root privileges (via pkexec) — read-only, no changes are made. Unlike 'Check Package Database Consistency' above, this actually hashes every file every installed package owns and compares it against what the package claims it should be, so it also catches files that were deleted, changed, or have the wrong permissions/ownership. On a full system this can take a couple of minutes. It's normal to see a few 'altered' hits for config files under /etc you've deliberately edited yourself — those aren't corruption, and reinstalling can't fix them since pacman never overwrites a modified config file. If any packages come back altered, you'll be asked right away which ones to repair by reinstalling.":
        'Führt „pacman -Qkk“ mit Root-Rechten (via pkexec) aus — rein lesend, es wird nichts verändert. Anders als „Paketdatenbank auf Konsistenz prüfen“ oben hasht das tatsächlich jede Datei jedes installierten Pakets und vergleicht sie mit dem, was das Paket erwartet, erkennt also auch gelöschte, geänderte oder mit falschen Rechten/Besitzer versehene Dateien. Auf einem vollen System kann das ein paar Minuten dauern. Es ist normal, ein paar „geänderte“ Treffer bei config-Dateien unter /etc zu sehen, die du selbst bewusst bearbeitet hast — das ist keine Beschädigung, und eine Neuinstallation kann das nicht beheben, da pacman eine geänderte config-Datei nie überschreibt. Werden Pakete als verändert gemeldet, wirst du sofort gefragt, welche davon durch Neuinstallation repariert werden sollen.',
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
    "Runs 'pacman -Rdd' with root privileges (via pkexec) on the single package name you type in. -Rdd removes it while skipping BOTH dependency checks that pacman normally does: it won't stop you even if other installed packages still depend on this one, and it won't try to remove anything that depends on it either — it only ever touches the one package you named. This is a genuine last resort for a package pacman refuses to touch any other way (e.g. it's stuck half-installed and blocking every other operation); it can leave dependents broken, so only use it on the one package actually causing the problem, after the steps above didn't help, and reinstall it (or whatever needed it) afterwards if you can.":
        'Führt „pacman -Rdd“ mit Root-Rechten (via pkexec) für genau das eine Paket aus, dessen Namen du eingibst. -Rdd entfernt es und überspringt dabei BEIDE Abhängigkeitsprüfungen, die pacman normalerweise macht: Es hält dich nicht auf, selbst wenn andere installierte Pakete noch von diesem abhängen, und es versucht auch nicht, irgendetwas zu entfernen, das von diesem Paket abhängt — es fasst wirklich nur das eine genannte Paket an. Das ist ein echter letzter Ausweg für ein Paket, das pacman auf keine andere Weise anfasst (z. B. weil es halb installiert feststeckt und jede andere Operation blockiert); es kann abhängige Pakete kaputt zurücklassen, also nur für das eine Paket verwenden, das tatsächlich das Problem verursacht, nachdem die obigen Schritte nicht geholfen haben, und es (bzw. was auch immer es brauchte) danach nach Möglichkeit neu installieren.',

    # ── Certificate Checker (Modul 2, cross-distro) ─────────────────────────
    "Certificate Checker": "Zertifikatsprüfung",
    "Check Certificates…": "Zertifikate prüfen…",
    "CA Certificate Bundle": "CA-Zertifikatspaket",
    "Reinstall CA Certificates & Rebuild Trust Store": "CA-Zertifikate neu installieren & Trust Store neu aufbauen",
    "Reinstalls the ca-certificates package (the bundle of root "
    "certificates your system trusts by default) and regenerates the "
    "system's trust store from it. Use this when HTTPS connections "
    "fail with certificate-verification errors across multiple, "
    "otherwise-unrelated sites at once — that pattern points at a "
    "damaged or outdated local trust store rather than a problem "
    "with any one remote site. Safe to run any time: it only "
    "reinstalls the package and rebuilds the store, it doesn't "
    "remove or add any certificate you didn't already have.":
        "Installiert das ca-certificates-Paket (das Bündel an Root-Zertifikaten, "
        "denen dein System standardmäßig vertraut) neu und baut daraus den "
        "System-Trust-Store neu auf. Nutze das, wenn HTTPS-Verbindungen bei "
        "mehreren, ansonsten unabhängigen Seiten gleichzeitig mit "
        "Zertifikatsprüfungsfehlern fehlschlagen — dieses Muster deutet auf "
        "einen beschädigten oder veralteten lokalen Trust Store hin, nicht auf "
        "ein Problem bei einer einzelnen Gegenstelle. Jederzeit gefahrlos "
        "ausführbar: Es installiert nur das Paket neu und baut den Store neu "
        "auf, entfernt oder fügt aber kein Zertifikat hinzu, das du nicht "
        "ohnehin schon hattest.",
    "Domain Certificate Expiry": "Domain-Zertifikatsablauf",
    "Checks how many days remain before each domain's TLS "
    "certificate expires — nothing is changed, purely informational.":
        "Prüft, wie viele Tage bis zum Ablauf des TLS-Zertifikats jeder Domain "
        "verbleiben — es wird nichts geändert, rein informativ.",
    "Domains": "Domains",
    "Opens a real TLS connection to each domain on port 443 and reads "
    "back the certificate it presents, then reports how many days "
    "remain until it expires (or how many days ago it already did). "
    "Comma-separated, e.g. example.com, mail.example.com — each "
    "domain needs to actually be reachable over the network right "
    "now, since this isn't a local file check like the one below, "
    "it's a live connection.":
        "Öffnet zu jeder Domain eine echte TLS-Verbindung auf Port 443, liest "
        "das dabei präsentierte Zertifikat aus und meldet dann, wie viele Tage "
        "bis zum Ablauf verbleiben (oder wie viele Tage der Ablauf schon "
        "zurückliegt). Kommagetrennt, z. B. example.com, mail.example.com — "
        "jede Domain muss dafür gerade jetzt übers Netzwerk erreichbar sein, "
        "denn anders als die Prüfung unten ist das keine lokale Dateiprüfung, "
        "sondern eine Live-Verbindung.",
    "Domains to check": "Zu prüfende Domains",
    "Check": "Prüfen",
    "Could not retrieve certificate (offline or unreachable?)": "Zertifikat konnte nicht abgerufen werden (offline oder nicht erreichbar?)",
    "EXPIRED {days} days ago": "ABGELAUFEN vor {days} Tagen",
    "Expires in {days} days (until {date})": "Läuft in {days} Tagen ab (bis {date})",
    "Valid, {days} days remaining (until {date})": "Gültig, noch {days} Tage (bis {date})",
    "Local Certificates": "Lokale Zertifikate",
    "Show Expired Local Certificates": "Abgelaufene lokale Zertifikate anzeigen",
    "Read-only: scans every .pem file under /etc/ssl/certs and checks "
    "its expiry date, without opening any network connection. This "
    "covers only that one system-wide certificate directory — not "
    "your browser's own certificate store, not a login keychain, and "
    "not certificates presented by remote servers (use the Domain "
    "check above for those). An expired entry here doesn't "
    "necessarily break anything today, since most software only "
    "cares about a certificate's validity at the moment it's "
    "actually used, but it's worth knowing about and cleaning up.":
        "Nur lesend: prüft jede .pem-Datei unter /etc/ssl/certs auf ihr "
        "Ablaufdatum, ohne eine Netzwerkverbindung zu öffnen. Das deckt nur "
        "dieses eine systemweite Zertifikatsverzeichnis ab — nicht den "
        "eigenen Zertifikatsspeicher deines Browsers, nicht einen Login-"
        "Schlüsselbund und nicht Zertifikate, die entfernte Server "
        "präsentieren (dafür die Domain-Prüfung oben nutzen). Ein "
        "abgelaufener Eintrag hier muss heute noch nichts kaputt machen, da "
        "die meiste Software die Gültigkeit eines Zertifikats nur im Moment "
        "seiner tatsächlichen Verwendung prüft — trotzdem gut zu wissen und "
        "aufzuräumen.",
    "EXPIRED: {cert}": "ABGELAUFEN: {cert}",
    "All local certificates are valid.": "Alle lokalen Zertifikate sind gültig.",

    # ── System Cleanup (Modul 4-Erweiterung, cross-distro) ──────────────────
    "System Cleanup": "System-Bereinigung",
    "Not package-related — general disk cleanup for the systemd "
    "journal, old thumbnail previews, and the trash.":
        "Nicht paketbezogen — allgemeine Datenträger-Bereinigung für das "
        "systemd-Journal, alte Thumbnail-Vorschaubilder und den Papierkorb.",
    "Clean systemd Journal": "systemd-Journal bereinigen",
    "Runs 'journalctl --vacuum-size=500M' followed by '--vacuum-time=4weeks'. This only vacuums (rotates out and discards) old log entries — it shrinks the journal down to 500 MB total and additionally removes anything older than 4 weeks, whichever removes more; it never touches today's live, currently-being-written log. Needs root privileges (via pkexec) since the journal under /var/log/journal is root-owned. Worth running if disk space is tight and 'journalctl --disk-usage' shows the journal has grown large — otherwise there's no real downside to leaving it, you just lose the ability to look further back in the logs.":
        'Führt „journalctl --vacuum-size=500M“ und danach „--vacuum-time=4weeks“ aus. Das rotiert und verwirft nur alte Log-Einträge — es verkleinert das Journal insgesamt auf 500 MB und entfernt zusätzlich alles, was älter als 4 Wochen ist, je nachdem, was mehr entfernt; das heutige, gerade geschriebene Live-Log wird dabei nie angefasst. Benötigt Root-Rechte (via pkexec), da das Journal unter /var/log/journal root-Besitz gehört. Lohnt sich, wenn der Speicherplatz knapp wird und „journalctl --disk-usage“ ein groß gewachsenes Journal zeigt — ansonsten gibt es keinen echten Nachteil, es weiter liegen zu lassen, du verlierst nur die Möglichkeit, weiter in die Vergangenheit zu schauen.',
    "Remove Old Thumbnail Previews": "Alte Thumbnail-Vorschaubilder entfernen",
    "Deletes cached preview images under ~/.cache/thumbnails that haven't been accessed in the last 30 days — the small generated thumbnails your file manager shows for images, videos, and documents, not the original files themselves. Nothing here is unique data: any thumbnail your file manager still needs gets silently regenerated the next time you browse to that folder, so this is purely reclaiming disk space with no real downside beyond a brief re-generation delay next time. No elevated privileges needed — this only touches your own user cache, never system files.":
        'Löscht zwischengespeicherte Vorschaubilder unter ~/.cache/thumbnails, auf die in den letzten 30 Tagen nicht zugegriffen wurde — die kleinen, generierten Thumbnails, die dein Dateimanager für Bilder, Videos und Dokumente anzeigt, nicht die Originaldateien selbst. Hier steckt keine einzigartige Information: Jedes Thumbnail, das dein Dateimanager noch braucht, wird beim nächsten Aufruf des Ordners automatisch neu erzeugt — es geht also rein um Speicherplatz zurückzugewinnen, ohne echten Nachteil außer einer kurzen Neuerzeugungs-Verzögerung beim nächsten Mal. Keine erhöhten Rechte nötig — betrifft nur den eigenen Benutzer-Cache, nie Systemdateien.',
    "Done.": "Fertig.",
    "No thumbnail cache found.": "Kein Thumbnail-Cache gefunden.",
    "Empty Trash": "Papierkorb leeren",
    "Permanently empties your desktop trash/recycle bin via 'gio trash --empty', following the same XDG trash location (usually ~/.local/share/Trash) your file manager already uses — so anything you see in the Trash there is exactly what this removes. Unlike a normal delete, this step is NOT recoverable through the trash/recycle-bin UI afterwards; files not already in the trash are completely unaffected. No elevated privileges needed, since it only ever touches your own account's trash.":
        'Leert den Papierkorb der Desktop-Umgebung endgültig via „gio trash --empty“ — am selben XDG-Papierkorb-Ort (meist ~/.local/share/Trash), den dein Dateimanager ohnehin schon nutzt, d. h. alles, was du dort im Papierkorb siehst, wird genau dadurch entfernt. Anders als ein normales Löschen ist dieser Schritt danach NICHT über die Papierkorb-Oberfläche wiederherstellbar; Dateien, die noch nicht im Papierkorb liegen, bleiben völlig unberührt. Keine erhöhten Rechte nötig, da es nur den Papierkorb des eigenen Kontos betrifft.',
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
    'Read-only: searches /usr and /etc for symlinks whose target no longer exists, then sorts every one it finds into one of three groups for the report — license-file leftovers (safe), Arch/Manjaro archiso build templates (safe but distro-specific, expected to exist there), and everything else (needs manual review). Nothing is ever deleted by this button, and since it only reads the filesystem, no elevated privileges are needed.':
        'Nur lesend: durchsucht /usr und /etc nach Symlinks, deren Ziel nicht mehr existiert, und ordnet jeden gefundenen einer von drei Gruppen im Bericht zu — Lizenzdatei-Reste (sicher), Arch/Manjaro-archiso-Bauvorlagen (sicher, aber distro-spezifisch, dort zu erwarten) und alles andere (manuelle Prüfung nötig). Dieser Button löscht niemals etwas, und da er nur das Dateisystem liest, ist keine erhöhte Berechtigung nötig.',
    "Scan & Remove Safe Ones": "Scannen & sichere entfernen",
    "Runs the same scan as above, but this time actually deletes the links it classified as safe — license-file leftovers under /usr/share/licenses only. The archiso-template group and everything in the review group are still just listed, never touched, no matter how many times you run this. Needs root privileges (via pkexec) because /usr/share is owned by root, so the deletion itself requires elevated permissions even though scanning doesn't.":
        'Führt denselben Scan wie oben aus, löscht diesmal aber tatsächlich die als sicher eingestuften Links — ausschließlich Lizenzdatei-Reste unter /usr/share/licenses. Die archiso-Vorlagen-Gruppe und alles in der Prüfen-Gruppe werden weiterhin nur aufgelistet, egal wie oft du das ausführst. Benötigt Root-Rechte (via pkexec), weil /usr/share root gehört — das Löschen selbst braucht also erhöhte Rechte, auch wenn das Scannen keine braucht.',
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
    "Creates a compressed archive of your system's identity and boot configuration (fstab, hostname, bootloader, package-manager config, …) plus a plain-text list of explicitly-installed packages, so a fresh install can be brought back to a similar state. Only the last 5 archives are kept; older ones are removed automatically. No elevated privileges needed — these files are normally world-readable.":
        'Erstellt ein komprimiertes Archiv der System-Identitäts- und Boot-Konfiguration (fstab, Hostname, Bootloader, Paketmanager-Konfiguration, …) sowie eine Textliste der explizit installierten Pakete, damit eine Neuinstallation wieder in einen ähnlichen Zustand gebracht werden kann. Es werden nur die letzten 5 Archive behalten; ältere werden automatisch entfernt. Keine erhöhten Rechte nötig — diese Dateien sind normalerweise für alle lesbar.',
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

    # ── Install Local Package (.tar.gz / .pkg.tar.* / .deb / .rpm) ─────────────
    'Install Local Package…':
        'Lokales Paket installieren…',
    'Install Local Package':
        'Lokales Paket installieren',
    'Package files (.tar.gz, .pkg.tar.*, .deb, .rpm, .flatpak)':
        'Paketdateien (.tar.gz, .pkg.tar.*, .deb, .rpm, .flatpak)',
    'All files':
        'Alle Dateien',
    'Checking package file…':
        'Paketdatei wird geprüft…',
    'Built Arch package (installed with pacman -U)':
        'Fertiges Arch-Paket (Installation mit pacman -U)',
    'Source package with PKGBUILD (built with makepkg, then installed)':
        'Quellpaket mit PKGBUILD (wird mit makepkg gebaut und dann installiert)',
    'Debian package (.deb)':
        'Debian-Paket (.deb)',
    'RPM package (.rpm)':
        'RPM-Paket (.rpm)',
    'Unknown':
        'Unbekannt',
    'Type':
        'Typ',
    'Version':
        'Version',
    'Size':
        'Größe',
    "Can't install this file":
        'Diese Datei kann nicht installiert werden',
    'First entries in the archive':
        'Erste Einträge im Archiv',
    'Review the PKGBUILD before building':
        'PKGBUILD vor dem Bauen prüfen',
    'Building runs the shell code from this PKGBUILD as your user. Only continue if you trust where the file came from. Missing dependencies are installed from the official repositories first (administrator password required); AUR-only dependencies must be installed beforehand.':
        'Beim Bauen wird der Shell-Code dieses PKGBUILDs mit deinen Benutzerrechten ausgeführt. Fahre nur fort, wenn du der Quelle der Datei vertraust. Fehlende Abhängigkeiten werden zuerst aus den offiziellen Repositories installiert (Administratorpasswort erforderlich); Abhängigkeiten, die nur im AUR liegen, müssen vorher installiert werden.',
    'The package is installed as-is. Dependencies are resolved by your package manager; you will be asked for the administrator password.':
        'Das Paket wird unverändert installiert. Abhängigkeiten löst dein Paketmanager auf; du wirst nach dem Administratorpasswort gefragt.',
    'Build and Install':
        'Bauen und installieren',
    'Unknown error':
        'Unbekannter Fehler',
    'A .deb file can only be installed on Debian/Ubuntu.':
        'Eine .deb-Datei kann nur unter Debian/Ubuntu installiert werden.',
    'An .rpm file can only be installed on Fedora/openSUSE.':
        'Eine .rpm-Datei kann nur unter Fedora/openSUSE installiert werden.',
    'This file is not a readable archive.':
        'Diese Datei ist kein lesbares Archiv.',
    "The archive contains unsafe paths (absolute or '..') and will not be unpacked.":
        "Das Archiv enthält unsichere Pfade (absolut oder '..') und wird nicht entpackt.",
    'This is an Arch Linux package; it can only be installed on Arch-based systems.':
        'Dies ist ein Arch-Linux-Paket; es lässt sich nur auf Arch-basierten Systemen installieren.',
    'A PKGBUILD can only be built on Arch-based systems.':
        'Ein PKGBUILD kann nur auf Arch-basierten Systemen gebaut werden.',
    'makepkg was not found. Install the "base-devel" package group first.':
        'makepkg wurde nicht gefunden. Installiere zuerst die Paketgruppe „base-devel“.',
    'Not an installable package: the archive contains neither a .PKGINFO (built Arch package) nor a PKGBUILD (source package). Pachul does not run unknown install scripts.':
        'Kein installierbares Paket: Das Archiv enthält weder eine .PKGINFO (fertiges Arch-Paket) noch ein PKGBUILD (Quellpaket). Pachul führt keine unbekannten Installationsskripte aus.',
    # ── Flatpak (local install) ──
    'Flatpak bundle (.flatpak)':
        'Flatpak-Bundle (.flatpak)',
    'Flatpak reference (.flatpakref) — the app is downloaded from its remote':
        'Flatpak-Referenz (.flatpakref) — die App wird vom zugehörigen Remote heruntergeladen',
    'Flatpak is not installed.':
        'Flatpak ist nicht installiert.',
    'The file is not a valid .flatpakref.':
        'Die Datei ist keine gültige .flatpakref.',
    'Installed for your user account (no administrator password needed). Required runtimes are fetched from your Flatpak remotes.':
        'Wird für dein Benutzerkonto installiert (kein Administratorpasswort nötig). Benötigte Runtimes werden aus deinen Flatpak-Remotes geladen.',
    # ── Tools hub ──
    'Tools (Ctrl+T)':
        'Werkzeuge (Strg+T)',
    'Search tools…':
        'Werkzeuge durchsuchen…',
    'No tools found':
        'Keine Werkzeuge gefunden',
    'Try a different search term.':
        'Versuche einen anderen Suchbegriff.',
    'Open tools':
        'Werkzeuge öffnen',
    'Software & Sources':
        'Software & Quellen',
    'Maintenance':
        'Wartung',
    'Repair':
        'Reparatur',
    'Install a downloaded .tar.gz, .pkg.tar.*, .deb, .rpm or .flatpak file':
        'Eine heruntergeladene .tar.gz-, .pkg.tar.*-, .deb-, .rpm- oder .flatpak-Datei installieren',
    'Enable, disable or add software sources':
        'Softwarequellen aktivieren, deaktivieren oder hinzufügen',
    'Rank mirrors by speed to make downloads faster':
        'Spiegelserver nach Geschwindigkeit sortieren, damit Downloads schneller werden',
    "Check developer and system tools that normal upgrades don't cover":
        'Entwickler- und Systemwerkzeuge prüfen, die normale Upgrades nicht abdecken',
    'Install all packages from a saved list':
        'Alle Pakete aus einer gespeicherten Liste installieren',
    'Save the names of your installed programs to a file':
        'Die Namen deiner installierten Programme in einer Datei speichern',
    'Remove packages that nothing depends on anymore':
        'Pakete entfernen, die von nichts mehr benötigt werden',
    'Free disk space used by downloaded package files':
        'Speicherplatz freigeben, den heruntergeladene Paketdateien belegen',
    'Compare and merge configuration files left behind by updates':
        'Von Updates hinterlassene Konfigurationsdateien vergleichen und zusammenführen',
    'Packages that are held back from upgrades':
        'Pakete, die von Upgrades ausgenommen sind',
    'See what was installed, upgraded or removed, and when':
        'Ansehen, was wann installiert, aktualisiert oder entfernt wurde',
    'Find out which package a file belongs to':
        'Herausfinden, zu welchem Paket eine Datei gehört',
    'Refresh databases, check integrity, reset the keyring':
        'Datenbanken auffrischen, Integrität prüfen, Schlüsselbund zurücksetzen',
    'Fix broken packages and interrupted installations':
        'Defekte Pakete und unterbrochene Installationen reparieren',
    'Sync with the repositories, rebuild the RPM database, clean caches':
        'Mit den Repositories abgleichen, RPM-Datenbank neu aufbauen, Caches leeren',
    'Verify packages, rebuild the RPM database, clean caches':
        'Pakete verifizieren, RPM-Datenbank neu aufbauen, Caches leeren',
    'Find expired or broken certificates':
        'Abgelaufene oder defekte Zertifikate finden',
    'Find and clean up dangling symbolic links':
        'Ins Leere zeigende symbolische Links finden und aufräumen',
    'Operating system, kernel, hardware and package statistics':
        'Betriebssystem, Kernel, Hardware und Paketstatistik',
    'Failed services, firewall and SSH settings at a glance':
        'Fehlgeschlagene Dienste, Firewall und SSH-Einstellungen auf einen Blick',
    "Back up your system's important configuration files":
        'Wichtige Konfigurationsdateien deines Systems sichern',
    # ── Appearance ──
    'Appearance':
        'Erscheinungsbild',
    'Follow System':
        'Wie das System',
    'Light':
        'Hell',
    'Dark':
        'Dunkel',
    'Toggle light/dark':
        'Hell/Dunkel umschalten',
    'Color Scheme':
        'Farbschema',
    # ── Packages hub ──
    'Updates & Sync':
        'Updates & Synchronisierung',
    'Selected Packages':
        'Ausgewählte Pakete',
    'Download the latest package lists from the repositories':
        'Lädt die neuesten Paketlisten aus den Repositories herunter',
    'See which packages have a newer version available':
        'Zeigt, für welche Pakete eine neuere Version verfügbar ist',
    'Reload the list of installed and available packages':
        'Lädt die Liste der installierten und verfügbaren Pakete neu',
    'Read the build script of the selected AUR package before installing':
        'Das Build-Skript des ausgewählten AUR-Pakets vor der Installation ansehen',
    'Keep the selected packages at their current version, or release them again':
        'Hält die ausgewählten Pakete auf ihrer aktuellen Version oder gibt sie wieder frei',
    'Treat the selected packages as installed on purpose, so they are not offered for removal as orphans':
        'Markiert die ausgewählten Pakete als bewusst installiert, damit sie nicht als verwaist zum Entfernen angeboten werden',
    'Treat the selected packages as pulled in by others, so they can be cleaned up as orphans once unused':
        'Markiert die ausgewählten Pakete als von anderen mitinstalliert, damit sie nach Nichtgebrauch als verwaist aufgeräumt werden können',
    'Dark Mode':
        'Dunkler Modus',
}


# ─── Translation table: English → Français ────────────────────────────────────
STRINGS_FR = {
    'Setting up makepkg to use pkexec for build dependencies (one-time)…': 'Configuration de makepkg pour utiliser pkexec pour les dépendances de compilation (une seule fois)…',
    'Build dependency prompts use pkexec': 'Les demandes pour les dépendances de compilation utilisent pkexec',
    '/etc/makepkg.conf already points PACMAN_AUTH at pkexec, so missing build dependencies get a native graphical prompt.': 'Dans /etc/makepkg.conf, PACMAN_AUTH pointe déjà vers pkexec : les dépendances de compilation manquantes sont demandées via une fenêtre graphique.',
    'Note: this run had several steps. Steps above may have completed successfully even though the whole run is marked as failed.\n': 'Remarque : cette exécution comportait plusieurs étapes. Les étapes ci-dessus ont pu réussir, même si l’ensemble est marqué comme échoué.\n',
    'Probable cause (last error lines):\n': 'Cause probable (dernières lignes d’erreur) :\n',
    # ── Sort menu + details switch ──
    "Selected first": "Sélectionnés d’abord",
    "Details": "Détails",
    "Name": "Nom",
    "Repository": "Dépôt",
    "Status": "Statut",
    "Descending order": "Ordre décroissant",
    "Sort packages": "Trier les paquets",
    "Show or hide the package details (Ctrl+D)": "Afficher ou masquer les détails du paquet (Ctrl+D)",
    "Show/hide package details": "Afficher/masquer les détails du paquet",
    "Detected automatically from your system settings": "Détecté automatiquement d’après les réglages du système",
    "Advanced options": "Options avancées",
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
    "New AUR Packages": "Nouveaux paquets AUR",
    "New Flatpak Packages": "Nouveaux paquets Flatpak",
    "New Chaotic-AUR Packages": "Nouveaux paquets Chaotic-AUR",
    "AUR / Foreign": "AUR / Externe",
    "NEW": "NOUVEAU",
    "INSTALLED PACKAGES": "PAQUETS INSTALLÉS",
    "All Installed Packages": "Tous les paquets installés",
    "All New Packages": "Tous les nouveaux paquets",
    "REPOSITORIES": "DÉPÔTS",
    "TOOLS": "OUTILS",
    "Check Updates": "Vérifier les mises à jour",
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
    "Find Fastest Mirrors…": "Trouver les miroirs les plus rapides…",
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
    "Choose Version…": "Choisir la version…",
    "Install one of the last 5 versions. The package stays ignored.":
        "Installer l'une des 5 dernières versions. Le paquet reste ignoré.",
    "Choose Version of {pkg}": "Choisir la version de {pkg}",
    "Looking for available versions…": "Recherche des versions disponibles…",
    "No other version of {pkg} was found — not in the local cache, the AUR helper build caches or the Arch Linux Archive (which only holds packages from the official repositories, and needs an internet connection).":
        "Aucune autre version de {pkg} trouvée — ni dans le cache local, ni dans les caches de build des assistants AUR, ni dans l'Arch Linux Archive (qui ne contient que des paquets des dépôts officiels et nécessite une connexion Internet).",
    "No other version of {pkg} is available.": "Aucune autre version de {pkg} n'est disponible.",
    "Currently installed": "Actuellement installé",
    "AUR package: versions work differently": "Paquet AUR : les versions fonctionnent autrement",
    "The AUR has no version archive like the official repositories. Pachul can only offer versions that are still on your disk: the pacman cache and the build folders of your AUR helper (yay, paru, pikaur, pachuli).":
        "L'AUR n'a pas d'archive de versions comme les dépôts officiels. Pachul ne peut proposer que les versions encore présentes sur votre disque : dans le cache de pacman et dans les dossiers de build de votre assistant AUR (yay, paru, pikaur, pachuli).",
    "An older version is therefore only available if you built or installed it earlier. After cleaning the helper's cache it is gone; then you would have to check out an older PKGBUILD and build it yourself.":
        "Une version plus ancienne n'est donc disponible que si vous l'avez construite ou installée auparavant. Après le nettoyage du cache de l'assistant, elle a disparu ; il faudrait alors récupérer un ancien PKGBUILD et le construire vous-même.",
    "Download from Arch Linux Archive": "Téléchargement depuis l'Arch Linux Archive",
    "{n} version(s) — pick one to install with pacman -U. Versions not in the local cache are downloaded from the Arch Linux Archive.":
        "{n} version(s) — choisissez-en une à installer avec pacman -U. Les versions absentes du cache local sont téléchargées depuis l'Arch Linux Archive.",
    "No package files for {pkg} were found in /var/cache/pacman/pkg or in the Arch Linux Archive.\nThe archive needs an internet connection and only holds packages from the official repositories.":
        "Aucun fichier de paquet pour {pkg} trouvé dans /var/cache/pacman/pkg ni dans l'Arch Linux Archive.\nL'archive nécessite une connexion Internet et ne contient que des paquets des dépôts officiels.",
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
    "Terminal Commands": "Commandes du terminal",
    "Launches the main window — same as clicking the app icon.":
        "Lance la fenêtre principale — équivalent à cliquer sur l'icône de l'application.",
    "Launches the standalone tray icon showing pending updates (requires libayatana-appindicator).":
        "Lance l'icône de zone de notification autonome affichant les mises à jour en attente (nécessite libayatana-appindicator).",
    "Removes a stray install.sh-based installation that's blocking an AUR package install/upgrade with a \"conflicting files\" error. Run as: sudo pachul-uninstall":
        "Supprime une installation résiduelle basée sur install.sh qui bloque l'installation/mise à jour d'un paquet AUR avec une erreur « conflicting files ». Exécuter : sudo pachul-uninstall",
    "Pachul's own minimal AUR helper (pacman/yay-style CLI): -Ss search, -S install, -Su/-Syu/-Syyu update, -R/-Rns remove, -Qu list updates, -Qi/-Qii package info, -Sp view PKGBUILD, -Sc/-Scc clean cache, -Yc remove orphans. Run pachuli --help for the full reference.":
        "L'assistant AUR minimal propre à Pachul (CLI façon pacman/yay) : -Ss recherche, -S installer, -Su/-Syu/-Syyu mettre à jour, -R/-Rns supprimer, -Qu lister les mises à jour, -Qi/-Qii infos paquet, -Sp voir le PKGBUILD, -Sc/-Scc vider le cache, -Yc supprimer les orphelins. Référence complète avec pachuli --help.",
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
    "Show Ignored Packages ({n})…": "Afficher les paquets ignorés ({n})…",
    "Select only one package for this action": "Sélectionnez un seul paquet pour cette action",
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
    "Input for the running command (rarely needed) — press Enter to send": "Saisie pour la commande en cours (rarement nécessaire) — Entrée pour envoyer",
    "Show input": "Afficher la saisie",
    "Hide input": "Masquer la saisie",
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
    "What is a repository?":
        "Qu’est-ce qu’un dépôt ?",
    "A repository (repo) is a package archive on a server from which pacman fetches programs and updates.":
        "Un dépôt (repo) est une archive de paquets sur un serveur, à partir de laquelle pacman récupère les programmes et les mises à jour.",
    "If a repository is missing: its packages can no longer be found or installed, and already installed packages from it receive no further updates (for example, without «multilib» there is no 32-bit software such as Steam or Wine; without «core» or «extra» the system itself can no longer be updated properly).":
        "Si un dépôt est absent : ses paquets ne peuvent plus être trouvés ni installés, et les paquets déjà installés qui en proviennent ne reçoivent plus de mises à jour (par exemple, sans «multilib», pas de logiciels 32 bits comme Steam ou Wine ; sans «core» ou «extra», le système lui-même ne peut plus être mis à jour correctement).",
    "If additional repositories are added: their packages appear in the search and can be installed. However, this can cause dependency and version conflicts, for example when a repository offers different versions of system libraries, which can block updates or break the system. Only add third-party repositories from sources you trust.":
        "Si des dépôts supplémentaires sont ajoutés : leurs paquets apparaissent dans la recherche et peuvent être installés. Cela peut toutefois provoquer des conflits de dépendances et de versions, par exemple lorsqu’un dépôt propose d’autres versions de bibliothèques système, ce qui peut bloquer les mises à jour ou endommager le système. N’ajoutez des dépôts tiers que depuis des sources de confiance.",
    "What are .pacnew and .pacsave files?":
        "Que sont les fichiers .pacnew et .pacsave ?",
    "If you changed a configuration file yourself and the package ships a new version of it, pacman does not overwrite your file. It saves the new default next to it as «.pacnew». If you remove a package whose configuration file you changed, your file is kept as «.pacsave».":
        "Si vous avez modifié vous-même un fichier de configuration et que le paquet en fournit une nouvelle version, pacman n’écrase pas votre fichier. Il enregistre la nouvelle version par défaut à côté, sous «.pacnew». Si vous supprimez un paquet dont vous avez modifié le fichier de configuration, votre fichier est conservé sous «.pacsave».",
    "«Use New (overwrite)» replaces your file with the new one — your own settings in it are lost. «Discard» only deletes the .pacnew file and keeps your version, which may then lack new options or contain outdated ones. Check the diff first.":
        "«Utiliser la nouvelle (écraser)» remplace votre fichier par le nouveau — vos réglages personnels y sont perdus. «Ignorer» supprime uniquement le fichier .pacnew et conserve votre version, à laquelle il peut alors manquer de nouvelles options ou qui peut en contenir d’obsolètes. Consultez donc d’abord la comparaison (diff).",
    "What does “ignored” mean?":
        "Que signifie «ignoré» ?",
    "Ignored (held) packages are skipped by system upgrades and stay at their current version until you unignore them.":
        "Les paquets ignorés (retenus) sont ignorés lors des mises à jour du système et restent à leur version actuelle jusqu’à ce que vous les libériez.",
    "Be careful: if a package stays old while the libraries it depends on are upgraded, it may stop working or block other updates. Hold packages only temporarily, for example until a known bug is fixed.":
        "Attention : si un paquet reste ancien alors que les bibliothèques dont il dépend sont mises à jour, il peut cesser de fonctionner ou bloquer d’autres mises à jour. Ne retenez donc des paquets que temporairement, par exemple jusqu’à la correction d’un bug connu.",
    "Arch does not officially support partial upgrades, so every ignored package is a small risk for the whole system.":
        "Arch ne prend pas officiellement en charge les mises à jour partielles : chaque paquet ignoré représente un petit risque pour l’ensemble du système.",
    "What is the package cache?":
        "Qu’est-ce que le cache des paquets ?",
    "When you install or update software, the package manager keeps the downloaded package files. This lets you reinstall a package without downloading it again, or go back to an older version.":
        "Lors de l’installation et des mises à jour, le gestionnaire de paquets conserve les fichiers de paquets téléchargés. Cela permet de réinstaller un paquet sans le retélécharger ou de revenir à une version plus ancienne.",
    "The cache keeps growing and can take up many gigabytes. Cleaning it is safe for the running system, but older versions are no longer available locally afterwards — so better not clean it right after an update that causes problems, you may still need the old version.":
        "Le cache grossit avec le temps et peut occuper de nombreux gigaoctets. Le nettoyer est sans danger pour le système en cours d’exécution, mais les versions plus anciennes ne sont ensuite plus disponibles localement. Évitez donc de le nettoyer juste après une mise à jour qui pose problème : vous pourriez encore avoir besoin de l’ancienne version.",
    "Hide this hint":
        "Masquer cet indice",
    "Show the active repositories and edit pacman.conf":
        "Afficher les dépôts actifs et modifier pacman.conf",
    "What are mirrors?":
        "Que sont les miroirs ?",
    "Mirrors are servers that hold copies of the package archives. pacman downloads packages and updates from the servers listed in /etc/pacman.d/mirrorlist, trying them from top to bottom.":
        "Les miroirs sont des serveurs qui hébergent des copies des dépôts de paquets. pacman télécharge les paquets et les mises à jour depuis les serveurs listés dans /etc/pacman.d/mirrorlist, en les essayant de haut en bas.",
    "rate-mirrors measures which servers respond fastest from your location and puts them first. This helps with slow downloads, errors such as 404 or timeouts, or after moving to another country. The result is only shown first — your current list is replaced only when you save.":
        "rate-mirrors mesure quels serveurs répondent le plus vite depuis votre position et les place en premier. C’est utile en cas de téléchargements lents, d’erreurs comme 404 ou de délais dépassés, ou après un déménagement dans un autre pays. Le résultat est d’abord seulement affiché — votre liste actuelle n’est remplacée que si vous l’enregistrez.",
    "Tip: keep «Backup current mirrorlist» switched on (only the most recent backup is kept). After saving, sync the databases so pacman uses the new servers («Sync Databases»).":
        "Astuce : laissez «Sauvegarder la liste de miroirs actuelle» activé (seule la dernière sauvegarde est conservée). Après l’enregistrement, synchronisez les bases de données («Synchroniser les bases de données») pour que pacman utilise les nouveaux serveurs.",
    "On Manjaro this list is normally managed by pacman-mirrors; running pacman-mirrors later can replace your result.":
        "Sous Manjaro, cette liste est normalement gérée par pacman-mirrors ; une exécution ultérieure de pacman-mirrors peut remplacer votre résultat.",
    "Choose how mirrors are selected and tested":
        "Choisissez comment les miroirs sont sélectionnés et testés",
    "Only use mirrors from these countries — 2-letter codes separated by commas, e.g. CH, DE, AT. Leave blank for all.":
        "Utiliser uniquement les miroirs de ces pays — codes à 2 lettres séparés par des virgules, p. ex. CH, DE, AT. Laisser vide pour tous.",
    "e.g. CH, DE, AT":
        "p. ex. CH, DE, AT",
    "Order in which mirrors are picked for testing; the final order always comes from the speed test":
        "Ordre dans lequel les miroirs sont choisis pour le test ; l’ordre final provient toujours du test de vitesse",
    "Ignore unencrypted HTTP mirrors (recommended)":
        "Ignorer les miroirs HTTP non chiffrés (recommandé)",
    "Copies the current list to /etc/pacman.d/mirrorlist-backup before replacing it (an older backup is overwritten)":
        "Copie la liste actuelle vers /etc/pacman.d/mirrorlist-backup avant de la remplacer (une ancienne sauvegarde est écrasée)",
    "Skip mirrors whose last sync is older than this":
        "Ignorer les miroirs dont la dernière synchronisation est plus ancienne",
    "How many of the fastest mirrors end up in the list (0 = all). 3 is usually enough.":
        "Combien des miroirs les plus rapides figurent dans la liste (0 = tous). 3 suffisent généralement.",
    "{n} mirrors found, fastest first. Review the list, then save it as your new mirrorlist or discard it.":
        "{n} miroirs trouvés, les plus rapides en premier. Vérifiez la liste, puis enregistrez-la comme nouvelle liste de miroirs ou ignorez-la.",
    "rate-mirrors measures how fast mirrors respond from your location and sorts your mirrorlist accordingly. Testing needs no administrator rights.":
        "rate-mirrors mesure la vitesse de réponse des miroirs depuis votre position et trie votre liste de miroirs en conséquence. Le test ne nécessite aucun droit d’administrateur.",
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
    "snap isn't installed (AUR-only on Arch — installs snapd via pachuli)":
        "snap n'est pas installé (uniquement via AUR sous Arch — installe snapd via pachuli)",
    "snap isn't installed (AUR-only on Arch — install pachuli above first)":
        "snap n'est pas installé (uniquement via AUR sous Arch — installez d'abord pachuli ci-dessus)",
    "Install Flatpak": "Installer Flatpak",
    "Install Snap": "Installer Snap",
    "Uninstall Flatpak": "Désinstaller Flatpak",
    "Uninstall Snap": "Désinstaller Snap",
    "Uninstall Flatpak?": "Désinstaller Flatpak ?",
    "Removes the flatpak package. Any Flatpak apps installed through it will stop working until it's reinstalled.":
        "Supprime le paquet flatpak. Les applications Flatpak installées via celui-ci cesseront de fonctionner jusqu'à sa réinstallation.",
    "Uninstall Snap?": "Désinstaller Snap ?",
    "Removes snapd. Any Snap apps installed through it will stop working until it's reinstalled.":
        "Supprime snapd. Les applications Snap installées via celui-ci cesseront de fonctionner jusqu'à sa réinstallation.",
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
    "Update Pachul?": "Mettre à jour Pachul ?",
    "A newer version of Pachul was found in this checkout "
    "than the one currently installed system-wide. Updating "
    "replaces the installed files with this version — this "
    "needs your password.":
        "Une version plus récente de Pachul a été trouvée dans ce dépôt "
        "que celle actuellement installée pour tout le système. La mise à jour "
        "remplace les fichiers installés par cette version — cela nécessite "
        "votre mot de passe.",
    "Update": "Mettre à jour",
    "Pachul updated.": "Pachul mis à jour.",
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
    "Select all visible packages": "Sélectionner tous les paquets visibles",
    "Deselect all packages": "Désélectionner tous les paquets",
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

    # ── Install Local Package (.tar.gz / .pkg.tar.* / .deb / .rpm) ─────────────
    'Install Local Package…':
        'Installer un paquet local…',
    'Install Local Package':
        'Installer un paquet local',
    'Package files (.tar.gz, .pkg.tar.*, .deb, .rpm, .flatpak)':
        'Fichiers de paquets (.tar.gz, .pkg.tar.*, .deb, .rpm, .flatpak)',
    'All files':
        'Tous les fichiers',
    'Checking package file…':
        'Vérification du fichier de paquet…',
    'Built Arch package (installed with pacman -U)':
        'Paquet Arch compilé (installé avec pacman -U)',
    'Source package with PKGBUILD (built with makepkg, then installed)':
        'Paquet source avec PKGBUILD (compilé avec makepkg, puis installé)',
    'Debian package (.deb)':
        'Paquet Debian (.deb)',
    'RPM package (.rpm)':
        'Paquet RPM (.rpm)',
    'Unknown':
        'Inconnu',
    'Type':
        'Type',
    'Version':
        'Version',
    'Size':
        'Taille',
    "Can't install this file":
        'Ce fichier ne peut pas être installé',
    'First entries in the archive':
        "Premières entrées de l'archive",
    'Review the PKGBUILD before building':
        'Vérifiez le PKGBUILD avant la compilation',
    'Building runs the shell code from this PKGBUILD as your user. Only continue if you trust where the file came from. Missing dependencies are installed from the official repositories first (administrator password required); AUR-only dependencies must be installed beforehand.':
        "La compilation exécute le code shell de ce PKGBUILD avec vos droits d'utilisateur. Ne continuez que si vous faites confiance à la source du fichier. Les dépendances manquantes sont d'abord installées depuis les dépôts officiels (mot de passe administrateur requis) ; les dépendances uniquement présentes dans l'AUR doivent être installées au préalable.",
    'The package is installed as-is. Dependencies are resolved by your package manager; you will be asked for the administrator password.':
        'Le paquet est installé tel quel. Les dépendances sont résolues par votre gestionnaire de paquets ; le mot de passe administrateur vous sera demandé.',
    'Build and Install':
        'Compiler et installer',
    'Unknown error':
        'Erreur inconnue',
    'A .deb file can only be installed on Debian/Ubuntu.':
        'Un fichier .deb ne peut être installé que sous Debian/Ubuntu.',
    'An .rpm file can only be installed on Fedora/openSUSE.':
        'Un fichier .rpm ne peut être installé que sous Fedora/openSUSE.',
    'This file is not a readable archive.':
        "Ce fichier n'est pas une archive lisible.",
    "The archive contains unsafe paths (absolute or '..') and will not be unpacked.":
        "L'archive contient des chemins dangereux (absolus ou '..') et ne sera pas extraite.",
    'This is an Arch Linux package; it can only be installed on Arch-based systems.':
        'Ceci est un paquet Arch Linux ; il ne peut être installé que sur les systèmes basés sur Arch.',
    'A PKGBUILD can only be built on Arch-based systems.':
        'Un PKGBUILD ne peut être compilé que sur les systèmes basés sur Arch.',
    'makepkg was not found. Install the "base-devel" package group first.':
        "makepkg est introuvable. Installez d'abord le groupe de paquets « base-devel ».",
    'Not an installable package: the archive contains neither a .PKGINFO (built Arch package) nor a PKGBUILD (source package). Pachul does not run unknown install scripts.':
        "Paquet non installable : l'archive ne contient ni .PKGINFO (paquet Arch compilé) ni PKGBUILD (paquet source). Pachul n'exécute pas de scripts d'installation inconnus.",
    # ── Flatpak (local install) ──
    'Flatpak bundle (.flatpak)':
        'Bundle Flatpak (.flatpak)',
    'Flatpak reference (.flatpakref) — the app is downloaded from its remote':
        "Référence Flatpak (.flatpakref) — l'application est téléchargée depuis son dépôt distant",
    'Flatpak is not installed.':
        "Flatpak n'est pas installé.",
    'The file is not a valid .flatpakref.':
        "Le fichier n'est pas un .flatpakref valide.",
    'Installed for your user account (no administrator password needed). Required runtimes are fetched from your Flatpak remotes.':
        'Installé pour votre compte utilisateur (aucun mot de passe administrateur requis). Les runtimes nécessaires sont récupérés depuis vos dépôts Flatpak.',
    # ── Tools hub ──
    'Tools (Ctrl+T)':
        'Outils (Ctrl+T)',
    'Search tools…':
        'Rechercher un outil…',
    'No tools found':
        'Aucun outil trouvé',
    'Try a different search term.':
        'Essayez un autre terme de recherche.',
    'Open tools':
        'Ouvrir les outils',
    'Software & Sources':
        'Logiciels et sources',
    'Maintenance':
        'Maintenance',
    'Repair':
        'Réparation',
    'Install a downloaded .tar.gz, .pkg.tar.*, .deb, .rpm or .flatpak file':
        'Installer un fichier .tar.gz, .pkg.tar.*, .deb, .rpm ou .flatpak téléchargé',
    'Enable, disable or add software sources':
        'Activer, désactiver ou ajouter des sources de logiciels',
    'Rank mirrors by speed to make downloads faster':
        'Classer les miroirs par vitesse pour accélérer les téléchargements',
    "Check developer and system tools that normal upgrades don't cover":
        'Vérifier les outils de développement et système non couverts par les mises à jour normales',
    'Install all packages from a saved list':
        "Installer tous les paquets d'une liste enregistrée",
    'Save the names of your installed programs to a file':
        'Enregistrer les noms de vos programmes installés dans un fichier',
    'Remove packages that nothing depends on anymore':
        'Supprimer les paquets dont plus rien ne dépend',
    'Free disk space used by downloaded package files':
        "Libérer l'espace disque utilisé par les fichiers de paquets téléchargés",
    'Compare and merge configuration files left behind by updates':
        'Comparer et fusionner les fichiers de configuration laissés par les mises à jour',
    'Packages that are held back from upgrades':
        'Paquets exclus des mises à niveau',
    'See what was installed, upgraded or removed, and when':
        'Voir ce qui a été installé, mis à jour ou supprimé, et quand',
    'Find out which package a file belongs to':
        'Trouver à quel paquet appartient un fichier',
    'Refresh databases, check integrity, reset the keyring':
        "Actualiser les bases, vérifier l'intégrité, réinitialiser le trousseau de clés",
    'Fix broken packages and interrupted installations':
        'Réparer les paquets cassés et les installations interrompues',
    'Sync with the repositories, rebuild the RPM database, clean caches':
        'Synchroniser avec les dépôts, reconstruire la base RPM, nettoyer les caches',
    'Verify packages, rebuild the RPM database, clean caches':
        'Vérifier les paquets, reconstruire la base RPM, nettoyer les caches',
    'Find expired or broken certificates':
        'Trouver les certificats expirés ou défectueux',
    'Find and clean up dangling symbolic links':
        'Trouver et nettoyer les liens symboliques orphelins',
    'Operating system, kernel, hardware and package statistics':
        "Système d'exploitation, noyau, matériel et statistiques des paquets",
    'Failed services, firewall and SSH settings at a glance':
        "Services en échec, pare-feu et paramètres SSH en un coup d'œil",
    "Back up your system's important configuration files":
        'Sauvegarder les fichiers de configuration importants du système',
    'Repair System (apt/dpkg)…':
        'Réparer le système (apt/dpkg)…',
    'Repair System (dnf/rpm)…':
        'Réparer le système (dnf/rpm)…',
    'Repair System (zypper/rpm)…':
        'Réparer le système (zypper/rpm)…',
    'Check Certificates…':
        'Vérifier les certificats…',
    'Find Broken Symlinks…':
        'Trouver les liens symboliques cassés…',
    'Services & Security…':
        'Services et sécurité…',
    'Configuration Backup…':
        'Sauvegarde de la configuration…',
    # ── Appearance ──
    'Appearance':
        'Apparence',
    'Follow System':
        'Suivre le système',
    'Light':
        'Clair',
    'Dark':
        'Sombre',
    'Toggle light/dark':
        'Basculer clair/sombre',
    'Color Scheme':
        'Schéma de couleurs',
    # ── Packages hub ──
    'Updates & Sync':
        'Mises à jour et synchronisation',
    'Selected Packages':
        'Paquets sélectionnés',
    'Download the latest package lists from the repositories':
        'Télécharge les dernières listes de paquets depuis les dépôts',
    'See which packages have a newer version available':
        'Indique quels paquets ont une version plus récente disponible',
    'Reload the list of installed and available packages':
        'Recharge la liste des paquets installés et disponibles',
    'Read the build script of the selected AUR package before installing':
        "Lire le script de construction du paquet AUR sélectionné avant l'installation",
    'Keep the selected packages at their current version, or release them again':
        'Garde les paquets sélectionnés à leur version actuelle, ou les libère à nouveau',
    'Treat the selected packages as installed on purpose, so they are not offered for removal as orphans':
        "Marque les paquets sélectionnés comme installés volontairement, pour qu'ils ne soient pas proposés à la suppression comme orphelins",
    'Treat the selected packages as pulled in by others, so they can be cleaned up as orphans once unused':
        "Marque les paquets sélectionnés comme installés par d'autres, pour pouvoir les nettoyer comme orphelins une fois inutilisés",
    'Dark Mode':
        'Mode sombre',
}


# ─── Translation table: English → Italiano ─────────────────────────────────────
STRINGS_IT = {
    'Setting up makepkg to use pkexec for build dependencies (one-time)…': 'Configurazione di makepkg per usare pkexec per le dipendenze di compilazione (una sola volta)…',
    'Build dependency prompts use pkexec': 'Le richieste per le dipendenze di compilazione usano pkexec',
    '/etc/makepkg.conf already points PACMAN_AUTH at pkexec, so missing build dependencies get a native graphical prompt.': 'In /etc/makepkg.conf PACMAN_AUTH punta già a pkexec: le dipendenze di compilazione mancanti vengono richieste con una finestra grafica.',
    'Note: this run had several steps. Steps above may have completed successfully even though the whole run is marked as failed.\n': 'Nota: questa esecuzione comprendeva più passaggi. I passaggi sopra potrebbero essere riusciti, anche se l’intera esecuzione è segnata come fallita.\n',
    'Probable cause (last error lines):\n': 'Causa probabile (ultime righe di errore):\n',
    # ── Sort menu + details switch ──
    "Selected first": "Selezionati per primi",
    "Details": "Dettagli",
    "Name": "Nome",
    "Repository": "Repository",
    "Status": "Stato",
    "Descending order": "Ordine decrescente",
    "Sort packages": "Ordina i pacchetti",
    "Show or hide the package details (Ctrl+D)": "Mostra o nascondi i dettagli del pacchetto (Ctrl+D)",
    "Show/hide package details": "Mostra/nascondi i dettagli del pacchetto",
    "Detected automatically from your system settings": "Rilevato automaticamente dalle impostazioni di sistema",
    "Advanced options": "Opzioni avanzate",
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
    "New AUR Packages": "Nuovi pacchetti AUR",
    "New Flatpak Packages": "Nuovi pacchetti Flatpak",
    "New Chaotic-AUR Packages": "Nuovi pacchetti Chaotic-AUR",
    "AUR / Foreign": "AUR / Esterni",
    "NEW": "NUOVO",
    "INSTALLED PACKAGES": "PACCHETTI INSTALLATI",
    "All Installed Packages": "Tutti i pacchetti installati",
    "All New Packages": "Tutti i pacchetti nuovi",
    "REPOSITORIES": "REPOSITORY",
    "TOOLS": "STRUMENTI",
    "Check Updates": "Controlla aggiornamenti",
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
    "Find Fastest Mirrors…": "Trova i mirror più veloci…",
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
    "Choose Version…": "Scegli versione…",
    "Install one of the last 5 versions. The package stays ignored.":
        "Installa una delle ultime 5 versioni. Il pacchetto resta ignorato.",
    "Choose Version of {pkg}": "Scegli la versione di {pkg}",
    "Looking for available versions…": "Ricerca delle versioni disponibili…",
    "No other version of {pkg} was found — not in the local cache, the AUR helper build caches or the Arch Linux Archive (which only holds packages from the official repositories, and needs an internet connection).":
        "Nessun'altra versione di {pkg} trovata — né nella cache locale, né nelle cache di build degli helper AUR, né nell'Arch Linux Archive (che contiene solo pacchetti dei repository ufficiali e richiede una connessione a Internet).",
    "No other version of {pkg} is available.": "Nessun'altra versione di {pkg} è disponibile.",
    "Currently installed": "Attualmente installato",
    "AUR package: versions work differently": "Pacchetto AUR: le versioni funzionano diversamente",
    "The AUR has no version archive like the official repositories. Pachul can only offer versions that are still on your disk: the pacman cache and the build folders of your AUR helper (yay, paru, pikaur, pachuli).":
        "L'AUR non ha un archivio delle versioni come i repository ufficiali. Pachul può offrire solo le versioni ancora presenti sul disco: nella cache di pacman e nelle cartelle di build del tuo helper AUR (yay, paru, pikaur, pachuli).",
    "An older version is therefore only available if you built or installed it earlier. After cleaning the helper's cache it is gone; then you would have to check out an older PKGBUILD and build it yourself.":
        "Una versione più vecchia è quindi disponibile solo se l'hai compilata o installata in precedenza. Dopo la pulizia della cache dell'helper non c'è più; dovresti allora recuperare un vecchio PKGBUILD e compilarlo da solo.",
    "Download from Arch Linux Archive": "Download dall'Arch Linux Archive",
    "{n} version(s) — pick one to install with pacman -U. Versions not in the local cache are downloaded from the Arch Linux Archive.":
        "{n} versione/i — scegline una da installare con pacman -U. Le versioni non presenti nella cache locale vengono scaricate dall'Arch Linux Archive.",
    "No package files for {pkg} were found in /var/cache/pacman/pkg or in the Arch Linux Archive.\nThe archive needs an internet connection and only holds packages from the official repositories.":
        "Nessun file del pacchetto {pkg} trovato in /var/cache/pacman/pkg né nell'Arch Linux Archive.\nL'archivio richiede una connessione a Internet e contiene solo pacchetti dei repository ufficiali.",
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
    "Terminal Commands": "Comandi da terminale",
    "Launches the main window — same as clicking the app icon.":
        "Avvia la finestra principale — equivale a cliccare sull'icona dell'app.",
    "Launches the standalone tray icon showing pending updates (requires libayatana-appindicator).":
        "Avvia l'icona autonoma nel vassoio di sistema che mostra gli aggiornamenti in sospeso (richiede libayatana-appindicator).",
    "Removes a stray install.sh-based installation that's blocking an AUR package install/upgrade with a \"conflicting files\" error. Run as: sudo pachul-uninstall":
        "Rimuove un'installazione residua basata su install.sh che blocca l'installazione/aggiornamento di un pacchetto AUR con un errore \"conflicting files\". Eseguire: sudo pachul-uninstall",
    "Pachul's own minimal AUR helper (pacman/yay-style CLI): -Ss search, -S install, -Su/-Syu/-Syyu update, -R/-Rns remove, -Qu list updates, -Qi/-Qii package info, -Sp view PKGBUILD, -Sc/-Scc clean cache, -Yc remove orphans. Run pachuli --help for the full reference.":
        "L'helper AUR minimale di Pachul (CLI in stile pacman/yay): -Ss ricerca, -S installa, -Su/-Syu/-Syyu aggiorna, -R/-Rns rimuovi, -Qu elenca aggiornamenti, -Qi/-Qii info pacchetto, -Sp visualizza PKGBUILD, -Sc/-Scc svuota cache, -Yc rimuovi orfani. Riferimento completo con pachuli --help.",
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
    "Show Ignored Packages ({n})…": "Mostra i pacchetti ignorati ({n})…",
    "Select only one package for this action": "Seleziona un solo pacchetto per questa azione",
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
    "Input for the running command (rarely needed) — press Enter to send": "Input per il comando in esecuzione (raramente necessario) — Invio per inviare",
    "Show input": "Mostra input",
    "Hide input": "Nascondi input",
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
    "What is a repository?":
        "Che cos’è un repository?",
    "A repository (repo) is a package archive on a server from which pacman fetches programs and updates.":
        "Un repository (repo) è un archivio di pacchetti su un server da cui pacman scarica programmi e aggiornamenti.",
    "If a repository is missing: its packages can no longer be found or installed, and already installed packages from it receive no further updates (for example, without «multilib» there is no 32-bit software such as Steam or Wine; without «core» or «extra» the system itself can no longer be updated properly).":
        "Se un repository manca: i suoi pacchetti non possono più essere trovati o installati e i pacchetti già installati da esso non ricevono più aggiornamenti (ad esempio, senza «multilib» non c’è software a 32 bit come Steam o Wine; senza «core» o «extra» il sistema stesso non può più essere aggiornato correttamente).",
    "If additional repositories are added: their packages appear in the search and can be installed. However, this can cause dependency and version conflicts, for example when a repository offers different versions of system libraries, which can block updates or break the system. Only add third-party repositories from sources you trust.":
        "Se vengono aggiunti repository aggiuntivi: i loro pacchetti compaiono nella ricerca e possono essere installati. Ciò può però causare conflitti di dipendenze e di versione, ad esempio quando un repository offre versioni diverse delle librerie di sistema, bloccando gli aggiornamenti o danneggiando il sistema. Aggiungi repository di terze parti solo da fonti attendibili.",
    "What are .pacnew and .pacsave files?":
        "Che cosa sono i file .pacnew e .pacsave?",
    "If you changed a configuration file yourself and the package ships a new version of it, pacman does not overwrite your file. It saves the new default next to it as «.pacnew». If you remove a package whose configuration file you changed, your file is kept as «.pacsave».":
        "Se hai modificato tu stesso un file di configurazione e il pacchetto ne include una nuova versione, pacman non sovrascrive il tuo file. Salva invece la nuova versione predefinita accanto, come «.pacnew». Se rimuovi un pacchetto di cui hai modificato il file di configurazione, il tuo file viene conservato come «.pacsave».",
    "«Use New (overwrite)» replaces your file with the new one — your own settings in it are lost. «Discard» only deletes the .pacnew file and keeps your version, which may then lack new options or contain outdated ones. Check the diff first.":
        "«Usa nuovo (sovrascrivi)» sostituisce il tuo file con quello nuovo: le tue impostazioni personali vanno perse. «Scarta» elimina solo il file .pacnew e mantiene la tua versione, alla quale possono mancare nuove opzioni o che può contenerne di obsolete. Controlla quindi prima il confronto (diff).",
    "What does “ignored” mean?":
        "Che cosa significa «ignorato»?",
    "Ignored (held) packages are skipped by system upgrades and stay at their current version until you unignore them.":
        "I pacchetti ignorati (bloccati) vengono saltati negli aggiornamenti di sistema e restano alla versione attuale finché non li sblocchi.",
    "Be careful: if a package stays old while the libraries it depends on are upgraded, it may stop working or block other updates. Hold packages only temporarily, for example until a known bug is fixed.":
        "Attenzione: se un pacchetto resta vecchio mentre le librerie da cui dipende vengono aggiornate, può smettere di funzionare o bloccare altri aggiornamenti. Blocca quindi i pacchetti solo temporaneamente, ad esempio finché un bug noto non viene corretto.",
    "Arch does not officially support partial upgrades, so every ignored package is a small risk for the whole system.":
        "Arch non supporta ufficialmente gli aggiornamenti parziali: ogni pacchetto ignorato è un piccolo rischio per l’intero sistema.",
    "What is the package cache?":
        "Che cos’è la cache dei pacchetti?",
    "When you install or update software, the package manager keeps the downloaded package files. This lets you reinstall a package without downloading it again, or go back to an older version.":
        "Durante l’installazione e gli aggiornamenti il gestore di pacchetti conserva i file dei pacchetti scaricati. Così puoi reinstallare un pacchetto senza scaricarlo di nuovo o tornare a una versione precedente.",
    "The cache keeps growing and can take up many gigabytes. Cleaning it is safe for the running system, but older versions are no longer available locally afterwards — so better not clean it right after an update that causes problems, you may still need the old version.":
        "La cache cresce nel tempo e può occupare molti gigabyte. Pulirla è sicuro per il sistema in uso, ma poi le versioni precedenti non sono più disponibili in locale. Evita quindi di pulirla subito dopo un aggiornamento che causa problemi: potresti aver ancora bisogno della vecchia versione.",
    "Hide this hint":
        "Nascondi questo suggerimento",
    "Show the active repositories and edit pacman.conf":
        "Mostra i repository attivi e modifica pacman.conf",
    "What are mirrors?":
        "Che cosa sono i mirror?",
    "Mirrors are servers that hold copies of the package archives. pacman downloads packages and updates from the servers listed in /etc/pacman.d/mirrorlist, trying them from top to bottom.":
        "I mirror sono server che ospitano copie degli archivi di pacchetti. pacman scarica pacchetti e aggiornamenti dai server elencati in /etc/pacman.d/mirrorlist, provandoli dall’alto verso il basso.",
    "rate-mirrors measures which servers respond fastest from your location and puts them first. This helps with slow downloads, errors such as 404 or timeouts, or after moving to another country. The result is only shown first — your current list is replaced only when you save.":
        "rate-mirrors misura quali server rispondono più velocemente dalla tua posizione e li mette in cima. Aiuta in caso di download lenti, errori come 404 o timeout, o dopo un trasferimento in un altro paese. Il risultato viene prima solo mostrato: la lista attuale viene sostituita solo se la salvi.",
    "Tip: keep «Backup current mirrorlist» switched on (only the most recent backup is kept). After saving, sync the databases so pacman uses the new servers («Sync Databases»).":
        "Suggerimento: lascia attivo «Backup della lista mirror attuale» (viene conservato solo l’ultimo backup). Dopo il salvataggio sincronizza i database («Sincronizza database») perché pacman usi i nuovi server.",
    "On Manjaro this list is normally managed by pacman-mirrors; running pacman-mirrors later can replace your result.":
        "Su Manjaro questa lista è normalmente gestita da pacman-mirrors; una successiva esecuzione di pacman-mirrors può sostituire il tuo risultato.",
    "Choose how mirrors are selected and tested":
        "Scegli come vengono selezionati e testati i mirror",
    "Only use mirrors from these countries — 2-letter codes separated by commas, e.g. CH, DE, AT. Leave blank for all.":
        "Usa solo i mirror di questi paesi — codici di 2 lettere separati da virgole, ad es. CH, DE, AT. Lascia vuoto per tutti.",
    "e.g. CH, DE, AT":
        "ad es. CH, DE, AT",
    "Order in which mirrors are picked for testing; the final order always comes from the speed test":
        "Ordine in cui i mirror vengono scelti per il test; l’ordine finale deriva sempre dal test di velocità",
    "Ignore unencrypted HTTP mirrors (recommended)":
        "Ignora i mirror HTTP non cifrati (consigliato)",
    "Copies the current list to /etc/pacman.d/mirrorlist-backup before replacing it (an older backup is overwritten)":
        "Copia la lista attuale in /etc/pacman.d/mirrorlist-backup prima di sostituirla (un backup precedente viene sovrascritto)",
    "Skip mirrors whose last sync is older than this":
        "Salta i mirror la cui ultima sincronizzazione è più vecchia di questo valore",
    "How many of the fastest mirrors end up in the list (0 = all). 3 is usually enough.":
        "Quanti dei mirror più veloci finiscono nella lista (0 = tutti). Di solito ne bastano 3.",
    "{n} mirrors found, fastest first. Review the list, then save it as your new mirrorlist or discard it.":
        "{n} mirror trovati, i più veloci per primi. Controlla l’elenco, poi salvalo come nuova lista mirror o scartalo.",
    "rate-mirrors measures how fast mirrors respond from your location and sorts your mirrorlist accordingly. Testing needs no administrator rights.":
        "rate-mirrors misura la velocità di risposta dei mirror dalla tua posizione e ordina di conseguenza la tua lista mirror. Per il test non servono diritti di amministratore.",
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
    "snap isn't installed (AUR-only on Arch — installs snapd via pachuli)":
        "snap non è installato (su Arch disponibile solo via AUR — installa snapd tramite pachuli)",
    "snap isn't installed (AUR-only on Arch — install pachuli above first)":
        "snap non è installato (su Arch disponibile solo via AUR — installa prima pachuli qui sopra)",
    "Install Flatpak": "Installa Flatpak",
    "Install Snap": "Installa Snap",
    "Uninstall Flatpak": "Disinstalla Flatpak",
    "Uninstall Snap": "Disinstalla Snap",
    "Uninstall Flatpak?": "Disinstallare Flatpak?",
    "Removes the flatpak package. Any Flatpak apps installed through it will stop working until it's reinstalled.":
        "Rimuove il pacchetto flatpak. Le app Flatpak installate tramite esso smetteranno di funzionare finché non viene reinstallato.",
    "Uninstall Snap?": "Disinstallare Snap?",
    "Removes snapd. Any Snap apps installed through it will stop working until it's reinstalled.":
        "Rimuove snapd. Le app Snap installate tramite esso smetteranno di funzionare finché non viene reinstallato.",
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
    "Update Pachul?": "Aggiornare Pachul?",
    "A newer version of Pachul was found in this checkout "
    "than the one currently installed system-wide. Updating "
    "replaces the installed files with this version — this "
    "needs your password.":
        "In questo checkout è stata trovata una versione più recente di Pachul "
        "rispetto a quella attualmente installata a livello di sistema. "
        "L'aggiornamento sostituisce i file installati con questa versione — "
        "è necessaria la tua password.",
    "Update": "Aggiorna",
    "Pachul updated.": "Pachul aggiornato.",
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
    "Select all visible packages": "Seleziona tutti i pacchetti visibili",
    "Deselect all packages": "Deseleziona tutti i pacchetti",
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

    # ── Install Local Package (.tar.gz / .pkg.tar.* / .deb / .rpm) ─────────────
    'Install Local Package…':
        'Installa pacchetto locale…',
    'Install Local Package':
        'Installa pacchetto locale',
    'Package files (.tar.gz, .pkg.tar.*, .deb, .rpm, .flatpak)':
        'File di pacchetto (.tar.gz, .pkg.tar.*, .deb, .rpm, .flatpak)',
    'All files':
        'Tutti i file',
    'Checking package file…':
        'Controllo del file del pacchetto…',
    'Built Arch package (installed with pacman -U)':
        'Pacchetto Arch già compilato (installato con pacman -U)',
    'Source package with PKGBUILD (built with makepkg, then installed)':
        'Pacchetto sorgente con PKGBUILD (compilato con makepkg, poi installato)',
    'Debian package (.deb)':
        'Pacchetto Debian (.deb)',
    'RPM package (.rpm)':
        'Pacchetto RPM (.rpm)',
    'Unknown':
        'Sconosciuto',
    'Type':
        'Tipo',
    'Version':
        'Versione',
    'Size':
        'Dimensione',
    "Can't install this file":
        'Impossibile installare questo file',
    'First entries in the archive':
        "Prime voci dell'archivio",
    'Review the PKGBUILD before building':
        'Controlla il PKGBUILD prima della compilazione',
    'Building runs the shell code from this PKGBUILD as your user. Only continue if you trust where the file came from. Missing dependencies are installed from the official repositories first (administrator password required); AUR-only dependencies must be installed beforehand.':
        "La compilazione esegue il codice shell di questo PKGBUILD con i tuoi permessi utente. Procedi solo se ti fidi della provenienza del file. Le dipendenze mancanti vengono prima installate dai repository ufficiali (password di amministratore richiesta); le dipendenze presenti solo nell'AUR vanno installate prima.",
    'The package is installed as-is. Dependencies are resolved by your package manager; you will be asked for the administrator password.':
        "Il pacchetto viene installato così com'è. Le dipendenze sono risolte dal gestore pacchetti; ti verrà chiesta la password di amministratore.",
    'Build and Install':
        'Compila e installa',
    'Unknown error':
        'Errore sconosciuto',
    'A .deb file can only be installed on Debian/Ubuntu.':
        'Un file .deb può essere installato solo su Debian/Ubuntu.',
    'An .rpm file can only be installed on Fedora/openSUSE.':
        'Un file .rpm può essere installato solo su Fedora/openSUSE.',
    'This file is not a readable archive.':
        'Questo file non è un archivio leggibile.',
    "The archive contains unsafe paths (absolute or '..') and will not be unpacked.":
        "L'archivio contiene percorsi non sicuri (assoluti o '..') e non verrà estratto.",
    'This is an Arch Linux package; it can only be installed on Arch-based systems.':
        'Questo è un pacchetto Arch Linux; può essere installato solo su sistemi basati su Arch.',
    'A PKGBUILD can only be built on Arch-based systems.':
        'Un PKGBUILD può essere compilato solo su sistemi basati su Arch.',
    'makepkg was not found. Install the "base-devel" package group first.':
        'makepkg non trovato. Installa prima il gruppo di pacchetti «base-devel».',
    'Not an installable package: the archive contains neither a .PKGINFO (built Arch package) nor a PKGBUILD (source package). Pachul does not run unknown install scripts.':
        "Pacchetto non installabile: l'archivio non contiene né un .PKGINFO (pacchetto Arch compilato) né un PKGBUILD (pacchetto sorgente). Pachul non esegue script di installazione sconosciuti.",
    # ── Flatpak (local install) ──
    'Flatpak bundle (.flatpak)':
        'Bundle Flatpak (.flatpak)',
    'Flatpak reference (.flatpakref) — the app is downloaded from its remote':
        "Riferimento Flatpak (.flatpakref) — l'app viene scaricata dal suo remote",
    'Flatpak is not installed.':
        'Flatpak non è installato.',
    'The file is not a valid .flatpakref.':
        'Il file non è un .flatpakref valido.',
    'Installed for your user account (no administrator password needed). Required runtimes are fetched from your Flatpak remotes.':
        'Installato per il tuo account utente (nessuna password di amministratore necessaria). I runtime richiesti vengono scaricati dai tuoi remote Flatpak.',
    # ── Tools hub ──
    'Tools (Ctrl+T)':
        'Strumenti (Ctrl+T)',
    'Search tools…':
        'Cerca strumenti…',
    'No tools found':
        'Nessuno strumento trovato',
    'Try a different search term.':
        'Prova con un altro termine di ricerca.',
    'Open tools':
        'Apri gli strumenti',
    'Software & Sources':
        'Software e sorgenti',
    'Maintenance':
        'Manutenzione',
    'Repair':
        'Riparazione',
    'Install a downloaded .tar.gz, .pkg.tar.*, .deb, .rpm or .flatpak file':
        'Installa un file .tar.gz, .pkg.tar.*, .deb, .rpm o .flatpak scaricato',
    'Enable, disable or add software sources':
        'Attiva, disattiva o aggiungi sorgenti software',
    'Rank mirrors by speed to make downloads faster':
        'Ordina i mirror per velocità per scaricare più rapidamente',
    "Check developer and system tools that normal upgrades don't cover":
        'Controlla strumenti di sviluppo e di sistema non coperti dagli aggiornamenti normali',
    'Install all packages from a saved list':
        'Installa tutti i pacchetti da un elenco salvato',
    'Save the names of your installed programs to a file':
        'Salva in un file i nomi dei programmi installati',
    'Remove packages that nothing depends on anymore':
        'Rimuovi i pacchetti da cui non dipende più nulla',
    'Free disk space used by downloaded package files':
        'Libera lo spazio occupato dai file dei pacchetti scaricati',
    'Compare and merge configuration files left behind by updates':
        'Confronta e unisci i file di configurazione lasciati dagli aggiornamenti',
    'Packages that are held back from upgrades':
        'Pacchetti esclusi dagli aggiornamenti',
    'See what was installed, upgraded or removed, and when':
        'Vedi cosa è stato installato, aggiornato o rimosso e quando',
    'Find out which package a file belongs to':
        'Scopri a quale pacchetto appartiene un file',
    'Refresh databases, check integrity, reset the keyring':
        "Aggiorna i database, verifica l'integrità, reimposta il portachiavi",
    'Fix broken packages and interrupted installations':
        'Ripara pacchetti danneggiati e installazioni interrotte',
    'Sync with the repositories, rebuild the RPM database, clean caches':
        'Sincronizza con i repository, ricostruisci il database RPM, pulisci le cache',
    'Verify packages, rebuild the RPM database, clean caches':
        'Verifica i pacchetti, ricostruisci il database RPM, pulisci le cache',
    'Find expired or broken certificates':
        'Trova certificati scaduti o danneggiati',
    'Find and clean up dangling symbolic links':
        'Trova e ripulisci i collegamenti simbolici orfani',
    'Operating system, kernel, hardware and package statistics':
        'Sistema operativo, kernel, hardware e statistiche dei pacchetti',
    'Failed services, firewall and SSH settings at a glance':
        "Servizi falliti, firewall e impostazioni SSH a colpo d'occhio",
    "Back up your system's important configuration files":
        'Esegui il backup dei file di configurazione importanti del sistema',
    'Repair System (apt/dpkg)…':
        'Ripara il sistema (apt/dpkg)…',
    'Repair System (dnf/rpm)…':
        'Ripara il sistema (dnf/rpm)…',
    'Repair System (zypper/rpm)…':
        'Ripara il sistema (zypper/rpm)…',
    'Check Certificates…':
        'Controlla i certificati…',
    'Find Broken Symlinks…':
        'Trova collegamenti simbolici interrotti…',
    'Services & Security…':
        'Servizi e sicurezza…',
    'Configuration Backup…':
        'Backup della configurazione…',
    # ── Appearance ──
    'Appearance':
        'Aspetto',
    'Follow System':
        'Segui il sistema',
    'Light':
        'Chiaro',
    'Dark':
        'Scuro',
    'Toggle light/dark':
        'Passa tra chiaro/scuro',
    'Color Scheme':
        'Schema colori',
    # ── Packages hub ──
    'Updates & Sync':
        'Aggiornamenti e sincronizzazione',
    'Selected Packages':
        'Pacchetti selezionati',
    'Download the latest package lists from the repositories':
        'Scarica gli ultimi elenchi di pacchetti dai repository',
    'See which packages have a newer version available':
        'Mostra quali pacchetti hanno una versione più recente disponibile',
    'Reload the list of installed and available packages':
        "Ricarica l'elenco dei pacchetti installati e disponibili",
    'Read the build script of the selected AUR package before installing':
        "Leggi lo script di compilazione del pacchetto AUR selezionato prima dell'installazione",
    'Keep the selected packages at their current version, or release them again':
        'Mantiene i pacchetti selezionati alla versione attuale, oppure li rilascia di nuovo',
    'Treat the selected packages as installed on purpose, so they are not offered for removal as orphans':
        'Segna i pacchetti selezionati come installati di proposito, così non vengono proposti per la rimozione come orfani',
    'Treat the selected packages as pulled in by others, so they can be cleaned up as orphans once unused':
        'Segna i pacchetti selezionati come installati da altri, così possono essere ripuliti come orfani quando non servono più',
    'Dark Mode':
        'Modalità scura',
}


# ─── Expanded help texts (Help window) ─────────────────────────────────────────
# setdefault(): never overrides a translation that already exists above.
for _k, _v in {
    'Getting Started':
        'Erste Schritte',
    'Installing & Removing':
        'Installieren & Entfernen',
    'Window layout':
        'Aufbau des Fensters',
    'Header bar buttons':
        'Schaltflächen der Kopfzeile',
    'Sidebar counters':
        'Zähler in der Seitenleiste',
    'Status badges':
        'Status-Markierungen',
    'Administrator rights':
        'Administratorrechte',
    'Tooltips and info boxes':
        'Tooltipps und Infoboxen',
    'All Packages / Updates':
        'Alle Pakete / Updates',
    'NEW section':
        'Bereich NEU',
    'INSTALLED PACKAGES section':
        'Bereich INSTALLIERTE PAKETE',
    'Dependencies':
        'Abhängigkeiten',
    'Ignore Updates':
        'Update ignorieren',
    'Bottom action bar':
        'Aktionsleiste unten',
    'Updates outside the package manager':
        'Updates außerhalb der Paketverwaltung',
    'Notifications and background checks':
        'Benachrichtigungen und Hintergrundprüfung',
    'Repair System (apt/dpkg)…':
        'System reparieren (apt/dpkg)…',
    'Repair System (dnf/rpm)…':
        'System reparieren (dnf/rpm)…',
    'Repair System (zypper/rpm)…':
        'System reparieren (zypper/rpm)…',
    'Confirmations and notifications':
        'Bestätigungen und Benachrichtigungen',
    'Startup health check':
        'Systemprüfung beim Start',
    'Snapshot before upgrades':
        'Snapshot vor Upgrades',
    'Tray icon and background service':
        'Tray-Icon und Hintergrunddienst',
    'Python bindings (apt / dnf)':
        'Python-Anbindung (apt / dnf)',
    'Preferences Explained':
        'Einstellungen erklärt',
    'The window has three parts: the sidebar on the left (filters and counters), the package list in the middle (with the search bar) and the details of the selected package on the right. The header bar at the top gives access to Packages, Tools, Preferences, Help and About Pachul.':
        'Das Fenster besteht aus drei Teilen: links die Seitenleiste (Filter und Zähler), in der Mitte die Paketliste (mit der Suchleiste) und rechts die Details des ausgewählten Pakets. Über die Kopfzeile oben erreichst du Pakete, Werkzeuge, Einstellungen, Hilfe und Über Pachul.',
    'Packages: sync, check for updates and actions for the selected packages. Tools (Ctrl+T): a searchable overview of all maintenance, repair and system tools — type a word and press Enter to open the first match. Preferences (Ctrl+,): all settings. Help (F1): this window. About Pachul: version, license and system info for bug reports.':
        'Pakete: Synchronisieren, Updates prüfen und Aktionen für die ausgewählten Pakete. Werkzeuge (Strg+T): durchsuchbare Übersicht aller Wartungs-, Reparatur- und Systemwerkzeuge – Suchbegriff eintippen und Enter drücken öffnet den ersten Treffer. Einstellungen (Strg+,): alle Optionen. Hilfe (F1): dieses Fenster. Über Pachul: Version, Lizenz und Systeminfos für Fehlerberichte.',
    'The three cards at the top of the sidebar show the total number of packages, how many of them come from the AUR, and how many updates are pending.':
        'Die drei Karten oben in der Seitenleiste zeigen die Gesamtzahl der Pakete, wie viele davon aus dem AUR stammen und wie viele Updates anstehen.',
    'INSTALLED marks a package that is already on your system, UPDATE marks an installed package for which a newer version is available. Next to the name, small badges show the version, the repository it comes from and its architecture.':
        'INSTALLIERT kennzeichnet ein Paket, das schon auf deinem System ist; UPDATE kennzeichnet ein installiertes Paket, für das eine neuere Version verfügbar ist. Neben dem Namen zeigen kleine Markierungen Version, Repository und Architektur.',
    "Actions that change the system (installing, removing, repairing …) ask for your password through pkexec and show their progress in a terminal window. Read-only checks and scans run without elevated rights; each tool's description says which is which.":
        'Aktionen, die das System verändern (Installieren, Entfernen, Reparieren …), fragen über pkexec nach deinem Passwort und zeigen den Fortschritt in einem Terminalfenster. Reine Prüfungen und Scans laufen ohne erhöhte Rechte; die Beschreibung jedes Werkzeugs sagt, was gilt.',
    'Many rows in the tools carry a tooltip with the exact command that is run and what it affects — hold the mouse over a row to read it before pressing its button. Info boxes explain a topic once; those with a close button stay hidden after you dismiss them.':
        'Viele Zeilen in den Werkzeugen haben einen Tooltipp mit dem genauen Befehl und seinen Auswirkungen – halte die Maus über eine Zeile, um ihn zu lesen, bevor du auf die Schaltfläche klickst. Infoboxen erklären ein Thema; solche mit Schließen-Knopf bleiben ausgeblendet, nachdem du sie weggeklickt hast.',
    'At the top of the sidebar: All Packages lists everything the package manager knows about; Updates lists only installed packages with a newer version available, with a count badge.':
        'Ganz oben in der Seitenleiste: Alle Pakete zeigt alles, was die Paketverwaltung kennt; Updates zeigt nur installierte Pakete mit einer neueren Version, mit Zähler.',
    'Everything that is not installed yet — either all at once (All New Packages) or per source such as core, extra, multilib, aur, Flatpak or Snap. A good place to discover software.':
        'Alles, was noch nicht installiert ist – entweder komplett (Alle neuen Pakete) oder nach Quelle wie core, extra, multilib, aur, Flatpak oder Snap. Ein guter Ort, um Software zu entdecken.',
    'Everything that is already on your system — all of it (All Installed Packages) or per origin. Every repository appears in both sections, each with its own package counter.':
        'Alles, was schon auf deinem System ist – komplett (Alle installierten Pakete) oder nach Herkunft. Jedes Repository erscheint in beiden Bereichen, jeweils mit eigenem Zähler.',
    'Type in the search bar (or press Ctrl+F) to filter the list that is currently shown by name or description. Pick All Packages in the sidebar first if you want to search everything.':
        'Tippe in die Suchleiste (oder drücke Strg+F), um die aktuell angezeigte Liste nach Name oder Beschreibung zu filtern. Wähle zuerst „Alle Pakete“ in der Seitenleiste, wenn du alles durchsuchen willst.',
    'Click a package to see its description and actions on the right. The Info tab shows version, size, license, dependencies and more; the Files tab lists every file the installed package placed on your system, with a filter field and a file counter.':
        'Klicke auf ein Paket, um rechts Beschreibung und Aktionen zu sehen. Der Reiter Info zeigt Version, Größe, Lizenz, Abhängigkeiten und mehr; der Reiter Dateien listet jede Datei, die das installierte Paket auf deinem System abgelegt hat, mit Filterfeld und Zähler.',
    'Dependency entries in the Info tab are buttons: click one to look that package up. Long lists can be expanded.':
        'Abhängigkeiten im Reiter Info sind Schaltflächen: Ein Klick schlägt das jeweilige Paket nach. Lange Listen lassen sich aufklappen.',
    'Installs the selected package from its source — repository, AUR, Flatpak or Snap. A terminal window shows the progress, and your password is asked via pkexec when needed.':
        'Installiert das ausgewählte Paket aus seiner Quelle – Repository, AUR, Flatpak oder Snap. Ein Terminalfenster zeigt den Fortschritt; das Passwort wird bei Bedarf über pkexec abgefragt.',
    'Removes the selected package. If “Confirm before removing packages” is switched on in Preferences, you are asked first.':
        'Entfernt das ausgewählte Paket. Ist in den Einstellungen „Vor dem Entfernen von Paketen bestätigen“ aktiv, wirst du vorher gefragt.',
    'Installs the same version of an installed package again — useful when some of its files are damaged or missing.':
        'Installiert dieselbe Version eines installierten Pakets erneut – nützlich, wenn einzelne Dateien beschädigt sind oder fehlen.',
    'Shows older versions of the package — those still in the package cache first, others from the repository if available — and installs the one you pick. Afterwards use Ignore Updates, or the next upgrade will install the newer version again.':
        'Zeigt ältere Versionen des Pakets – zuerst die noch im Paket-Cache vorhandenen, sonst die aus dem Repository, falls verfügbar – und installiert die gewählte. Nutze danach „Update ignorieren“, sonst installiert das nächste Upgrade wieder die neuere Version.',
    'Pins a package at its current version so system upgrades skip it until you release it again (Arch: IgnorePkg in /etc/pacman.conf, Debian: apt-mark hold, openSUSE: package lock). Use it only temporarily — a package that falls behind its libraries can break or block other updates. All held packages are listed under Tools → Ignored Packages.':
        'Hält ein Paket auf seiner aktuellen Version fest, sodass System-Upgrades es überspringen, bis du es wieder freigibst (Arch: IgnorePkg in /etc/pacman.conf, Debian: apt-mark hold, openSUSE: Paketsperre). Nur vorübergehend verwenden – ein Paket, das hinter seinen Bibliotheken zurückbleibt, kann kaputtgehen oder andere Updates blockieren. Alle gesperrten Pakete stehen unter Werkzeuge → Ignorierte Pakete.',
    'Tick the checkboxes in the package list to select several packages. The right side then lists the selection, and the bottom bar offers Install, Uninstall and Ignore Updates for all of them at once. Ctrl+A selects everything currently visible, Ctrl+Shift+A clears the selection.':
        'Setze Häkchen in der Paketliste, um mehrere Pakete auszuwählen. Rechts erscheint dann die Auswahl, und die untere Leiste bietet Installieren, Deinstallieren und Update ignorieren für alle auf einmal. Strg+A wählt alles aktuell Sichtbare aus, Strg+Umschalt+A hebt die Auswahl auf.',
    'Left: buttons to select or deselect all visible packages, then Install. Right: Uninstall and Ignore Updates. Upgrade All appears whenever updates are pending, and Check for Updates is available in the Updates view.':
        'Links: Schaltflächen zum Auswählen bzw. Abwählen aller sichtbaren Pakete, dann Installieren. Rechts: Deinstallieren und Update ignorieren. „Alle aktualisieren“ erscheint, sobald Updates anstehen; „Auf Updates prüfen“ gibt es in der Ansicht Updates.',
    'Downloads the latest package lists from the repositories without installing anything (F5). A confirmation dialog explains what happens first.':
        'Lädt die aktuellen Paketlisten aus den Repositorien herunter, ohne etwas zu installieren (F5). Vorher erklärt ein Bestätigungsdialog, was passiert.',
    'Syncs, then rebuilds the Updates list (Ctrl+U, or the button in the Updates view). AUR packages are included if enabled in Preferences.':
        'Synchronisiert und baut danach die Update-Liste neu auf (Strg+U oder die Schaltfläche in der Ansicht Updates). AUR-Pakete werden einbezogen, wenn das in den Einstellungen aktiviert ist.',
    'Reloads the view from what is already known locally, without contacting the repositories (Ctrl+R).':
        'Lädt die Ansicht aus dem lokal bereits Bekannten neu, ohne die Repositorien zu kontaktieren (Strg+R).',
    'Installs every pending update in one go. If Timeshift or Snapper is found and enabled in Preferences, a restore point is created first. Flatpak and Snap updates are included when those sources are enabled.':
        'Installiert alle anstehenden Updates auf einmal. Wird Timeshift oder Snapper gefunden und ist es in den Einstellungen aktiviert, wird vorher ein Wiederherstellungspunkt angelegt. Flatpak- und Snap-Updates sind enthalten, wenn diese Quellen aktiviert sind.',
    "Developer and system tools that normal upgrades don't cover (rustup, npm, pip, firmware …) are handled under Tools → More Update Sources.":
        'Entwickler- und Systemwerkzeuge, die normale Upgrades nicht abdecken (rustup, npm, pip, Firmware …), findest du unter Werkzeuge → Weitere Update-Quellen.',
    'Preferences can check for updates on startup and notify you when some are available. With the tray icon and the background service, checks also run periodically while Pachul is closed.':
        'In den Einstellungen kannst du beim Start nach Updates suchen und dich benachrichtigen lassen. Mit Tray-Icon und Hintergrunddienst laufen Prüfungen auch regelmäßig, während Pachul geschlossen ist.',
    'Installs a downloaded file: a built package (.pkg.tar.*, installed with pacman -U), a .tar.gz with a PKGBUILD (built with makepkg first), .deb, .rpm, .flatpak or .flatpakref. Pachul recognises the type, shows what it found and asks before installing. Only formats your distribution can handle work.':
        'Installiert eine heruntergeladene Datei: ein fertiges Paket (.pkg.tar.*, mit pacman -U), ein .tar.gz mit PKGBUILD (wird zuerst mit makepkg gebaut), .deb, .rpm, .flatpak oder .flatpakref. Pachul erkennt den Typ, zeigt, was es gefunden hat, und fragt vor der Installation nach. Es funktionieren nur Formate, die deine Distribution verarbeiten kann.',
    'Arch: shows the active repositories and lets you edit pacman.conf (for example to enable multilib) — a wrong entry can stop updates from working, so change it with care. Other distributions: enable, disable or add software sources without editing files by hand.':
        'Arch: zeigt die aktiven Repositorien und lässt dich die pacman.conf bearbeiten (z. B. um multilib zu aktivieren) – ein falscher Eintrag kann Updates lahmlegen, also mit Bedacht ändern. Andere Distributionen: Softwarequellen aktivieren, deaktivieren oder hinzufügen, ohne Dateien von Hand zu bearbeiten.',
    'Tests the configured mirrors, ranks them by speed and lets you apply the fastest ones to make downloads quicker. Arch only — Fedora and openSUSE already pick the fastest mirror automatically. An info box in the dialog explains what mirrors are.':
        'Testet die konfigurierten Spiegelserver, ordnet sie nach Geschwindigkeit und übernimmt auf Wunsch die schnellsten, damit Downloads schneller werden. Nur für Arch – Fedora und openSUSE wählen automatisch den schnellsten Spiegel. Eine Infobox im Dialog erklärt, was Spiegelserver sind.',
    "Checks tools that normal upgrades don't cover: rustup, cargo, pip/pipx, npm, fnm/nvm, firmware (fwupd), Docker/Podman images, editor plugins and more. Update them once with “Update Selected”, or tick a tool to have it run automatically with every normal system upgrade. The “What can be updated here?” list shows everything supported, even if it isn't installed.":
        'Prüft Werkzeuge, die normale Upgrades nicht abdecken: rustup, cargo, pip/pipx, npm, fnm/nvm, Firmware (fwupd), Docker-/Podman-Images, Editor-Plugins und mehr. Aktualisiere sie einmalig mit „Auswahl aktualisieren“ oder hake ein Werkzeug an, damit es bei jedem normalen System-Upgrade automatisch mitläuft. Die Liste „Was kann hier aktualisiert werden?“ zeigt alles Unterstützte, auch wenn es nicht installiert ist.',
    'Installs packages from a list file you exported earlier. After you pick the file, the packages found in it are shown before anything is installed.':
        'Installiert Pakete aus einer Listendatei, die du zuvor exportiert hast. Nach der Dateiauswahl werden die gefundenen Pakete angezeigt, bevor etwas installiert wird.',
    'Saves the names of your explicitly installed programs to a text file — handy for setting up another machine the same way (use Import Package List there). You choose the target location first.':
        'Speichert die Namen deiner ausdrücklich installierten Programme in einer Textdatei – praktisch, um einen anderen Rechner genauso einzurichten (dort „Paketliste importieren“ nutzen). Zuerst wählst du den Speicherort.',
    'Lists packages that were installed as dependencies and are no longer needed by anything, so you can remove them and free space. Check the list first: a program you use directly can show up here if it was marked as a dependency — use Mark Selected as Explicit to protect it.':
        'Listet Pakete auf, die als Abhängigkeit installiert wurden und von nichts mehr gebraucht werden, damit du sie entfernen und Platz schaffen kannst. Prüfe die Liste vorher: Ein Programm, das du direkt nutzt, kann hier auftauchen, wenn es als Abhängigkeit markiert war – mit „Auswahl als explizit markieren“ schützt du es.',
    'Frees disk space used by downloaded package files. On Arch it keeps the 2 newest versions of each package (paccache), so a downgrade stays possible; installed packages are never touched. The dialog also offers general cleanup: shrink the systemd journal (500 MB / 4 weeks), delete thumbnails older than 30 days and empty the trash — emptying the trash cannot be undone.':
        'Schafft Platz, der von heruntergeladenen Paketdateien belegt wird. Unter Arch bleiben die 2 neuesten Versionen jedes Pakets erhalten (paccache), damit ein Downgrade möglich bleibt; installierte Pakete werden nie angetastet. Der Dialog bietet auch allgemeines Aufräumen: systemd-Journal verkleinern (500 MB / 4 Wochen), Vorschaubilder älter als 30 Tage löschen und den Papierkorb leeren – Letzteres lässt sich nicht rückgängig machen.',
    'After an update, a package can leave a new default configuration file (.pacnew) or a backup (.pacsave) next to yours instead of overwriting your changes. This tool shows the differences and helps you merge or discard them.':
        'Nach einem Update kann ein Paket eine neue Standard-Konfigurationsdatei (.pacnew) oder eine Sicherung (.pacsave) neben deiner ablegen, statt deine Änderungen zu überschreiben. Dieses Werkzeug zeigt die Unterschiede und hilft beim Zusammenführen oder Verwerfen.',
    'After an update, a package can leave a new default configuration file (such as .rpmnew or .dpkg-dist) next to yours instead of overwriting your changes. This tool shows the differences and helps you merge or discard them.':
        'Nach einem Update kann ein Paket eine neue Standard-Konfigurationsdatei (z. B. .rpmnew oder .dpkg-dist) neben deiner ablegen, statt deine Änderungen zu überschreiben. Dieses Werkzeug zeigt die Unterschiede und hilft beim Zusammenführen oder Verwerfen.',
    'Overview of all packages currently held back from upgrades, with an Unignore button for each (and Unignore All). An info box explains why holding packages for long is risky.':
        'Übersicht aller Pakete, die gerade von Upgrades ausgenommen sind, mit je einer Schaltfläche „Nicht mehr ignorieren“ (und „Alle nicht mehr ignorieren“). Eine Infobox erklärt, warum langes Zurückhalten riskant ist.',
    'A log of past installs, upgrades and removals with dates — useful to find out what changed before something stopped working.':
        'Ein Protokoll früherer Installationen, Upgrades und Entfernungen mit Datum – hilfreich, um herauszufinden, was sich geändert hat, bevor etwas nicht mehr funktionierte.',
    "Finds out which package a file belongs to: enter a file name or path. If the file database hasn't been synced yet, you are offered to do that first.":
        'Findet heraus, zu welchem Paket eine Datei gehört: Dateiname oder Pfad eingeben. Ist die Dateidatenbank noch nicht synchronisiert, wirst du zuerst dazu aufgefordert.',
    'Standard Maintenance: Force-Refresh & Full Upgrade (pacman -Syyu), a read-only database consistency check, and Reinitialize Keyring (helps with signature errors). Diagnose: search for packages with missing or modified files and reinstall the ones you pick. Last Resort: force-remove a broken package while ignoring dependencies — only when nothing else works.':
        'Standard-Wartung: Erzwungene Aktualisierung & vollständiges Upgrade (pacman -Syyu), eine schreibgeschützte Prüfung der Paketdatenbank und „Keyring neu initialisieren“ (hilft bei Signaturfehlern). Diagnose: Pakete mit fehlenden oder veränderten Dateien suchen und ausgewählte neu installieren. Letzter Ausweg: ein defektes Paket unter Missachtung der Abhängigkeiten zwangsweise entfernen – nur, wenn nichts anderes hilft.',
    'Standard Maintenance: update, upgrade & autoremove, fix broken dependencies, reconfigure all packages, fix missing or corrupt package files and clean the package cache. Diagnose lists broken or incomplete packages; Last Resort offers a forced removal.':
        'Standard-Wartung: Update, Upgrade & Autoremove, defekte Abhängigkeiten reparieren, alle Pakete neu konfigurieren, fehlende oder beschädigte Paketdateien reparieren und den Paket-Cache leeren. Diagnose listet defekte oder unvollständige Pakete auf; der letzte Ausweg bietet ein erzwungenes Entfernen.',
    'Standard Maintenance: update, upgrade & autoremove, fix inconsistent package versions, rebuild the RPM database and clean the package cache. Diagnose shows broken or unsatisfied packages; Last Resort offers a forced removal.':
        'Standard-Wartung: Update, Upgrade & Autoremove, inkonsistente Paketversionen beheben, die RPM-Datenbank neu aufbauen und den Paket-Cache leeren. Diagnose zeigt defekte oder unerfüllte Pakete; der letzte Ausweg bietet ein erzwungenes Entfernen.',
    'Standard Maintenance: update & upgrade, fix broken dependencies, rebuild the RPM database and clean the package cache. Diagnose shows broken or unsatisfied packages; Last Resort offers a forced removal.':
        'Standard-Wartung: Update & Upgrade, defekte Abhängigkeiten reparieren, die RPM-Datenbank neu aufbauen und den Paket-Cache leeren. Diagnose zeigt defekte oder unerfüllte Pakete; der letzte Ausweg bietet ein erzwungenes Entfernen.',
    'Domain check: connects live to the domains you enter (port 443) and reports the days left until the certificate expires. Local check: read-only scan of the .pem files in /etc/ssl/certs. There is also a one-click reinstall of the CA certificate bundle for when HTTPS errors hit many unrelated sites at once.':
        'Domain-Prüfung: verbindet sich live mit den eingegebenen Domains (Port 443) und nennt die verbleibenden Tage bis zum Ablauf des Zertifikats. Lokale Prüfung: schreibgeschützter Scan der .pem-Dateien in /etc/ssl/certs. Außerdem gibt es eine Ein-Klick-Neuinstallation des CA-Zertifikatspakets für den Fall, dass HTTPS-Fehler viele unabhängige Seiten gleichzeitig betreffen.',
    'Scans /usr and /etc for symbolic links whose target no longer exists and sorts them into license leftovers (safe), archiso templates (expected) and everything else (review by hand). Scanning is read-only; the clean-up button deletes only the safe license leftovers and needs administrator rights.':
        'Durchsucht /usr und /etc nach symbolischen Links, deren Ziel nicht mehr existiert, und sortiert sie in Lizenz-Überreste (unbedenklich), archiso-Vorlagen (erwartet) und alles Übrige (von Hand prüfen). Das Scannen ist schreibgeschützt; die Aufräum-Schaltfläche löscht nur die unbedenklichen Lizenz-Überreste und braucht Administratorrechte.',
    'Operating system, kernel, hardware and package statistics in one place — a good thing to include in a bug report.':
        'Betriebssystem, Kernel, Hardware und Paketstatistik an einem Ort – gut geeignet für Fehlerberichte.',
    'Shows failed systemd services (with a one-click reset for the usually harmless shadow.service), whether firewalld, fail2ban and apparmor are active, the UFW firewall (show rules, install and enable) and a check of the SSH root-login setting. Most checks are read-only.':
        'Zeigt fehlgeschlagene systemd-Dienste (mit Ein-Klick-Zurücksetzen für den meist harmlosen shadow.service), ob firewalld, fail2ban und apparmor aktiv sind, die UFW-Firewall (Regeln anzeigen, installieren und aktivieren) und eine Prüfung der SSH-Root-Anmeldung. Die meisten Prüfungen sind schreibgeschützt.',
    'Creates a compressed archive of important system configuration (fstab, hostname, bootloader, package-manager config …) plus a list of installed packages in the folder you choose (default: ~/pachul-backup). Only the last 5 archives are kept. No administrator rights needed.':
        'Erstellt ein komprimiertes Archiv wichtiger Systemkonfiguration (fstab, Hostname, Bootloader, Paketverwaltungs-Konfiguration …) plus eine Liste der installierten Pakete im gewählten Ordner (Standard: ~/pachul-backup). Es bleiben nur die letzten 5 Archive erhalten. Keine Administratorrechte nötig.',
    "Shows the build script of an AUR package before you install it, so you can see what it will do — always worth a look for unfamiliar packages. A link button in the viewer opens the package's AUR page (votes, comments, discussion).":
        'Zeigt das Build-Skript eines AUR-Pakets vor der Installation, damit du siehst, was es tun wird – bei unbekannten Paketen immer einen Blick wert. Ein Link-Knopf im Fenster öffnet die AUR-Seite des Pakets (Stimmen, Kommentare, Diskussion).',
    'Same as Ignore Updates, but from the Packages menu: toggles whether the selected packages are excluded from upgrades. A dialog explains the effect and asks for confirmation.':
        'Wie „Update ignorieren“, aber aus dem Menü Pakete: schaltet um, ob die ausgewählten Pakete von Upgrades ausgenommen sind. Ein Dialog erklärt die Wirkung und fragt nach Bestätigung.',
    'Changes how a package is tracked. Explicit means installed on purpose, so it is never offered for removal as an orphan; Dependency means installed for other packages, so it shows up in Find Orphans once nothing needs it any more. Only this label changes — nothing is installed or removed.':
        'Ändert, wie ein Paket verfolgt wird. „Explizit“ heißt absichtlich installiert und wird nie als Waise zum Entfernen angeboten; „Abhängigkeit“ heißt für andere Pakete installiert und taucht in „Waisen finden“ auf, sobald es nichts mehr braucht. Nur diese Markierung ändert sich – es wird nichts installiert oder entfernt.',
    "Chooses the program used for AUR installs, updates and PKGBUILDs: auto-detect, pachuli (Pachul's own minimal helper), yay, paru, pikaur or none (pacman only). A missing helper can be installed right from the Preferences. “Include AUR in update checks” also looks for newer AUR versions — switch it off if checks are slow or you don't use the AUR.":
        'Legt fest, welches Programm für AUR-Installationen, -Updates und PKGBUILDs genutzt wird: automatisch erkennen, pachuli (Pachuls eigener schlanker Helfer), yay, paru, pikaur oder keiner (nur pacman). Ein fehlender Helfer lässt sich direkt in den Einstellungen installieren. „AUR bei Update-Prüfungen einbeziehen“ sucht auch nach neueren AUR-Versionen – schalte es aus, wenn Prüfungen langsam sind oder du das AUR nicht nutzt.',
    'If python3-apt (Debian/Ubuntu) or python3-libdnf5 (Fedora) is missing, Preferences offers to install it. It speeds up package info, listing and update checks; Pachul works without it, just more slowly. Restart Pachul afterwards.':
        'Fehlt python3-apt (Debian/Ubuntu) oder python3-libdnf5 (Fedora), bieten die Einstellungen die Installation an. Das beschleunigt Paketinfos, Listen und Update-Prüfungen; Pachul funktioniert auch ohne, nur langsamer. Danach Pachul neu starten.',
    'Switch Flatpak and Snap support on or off, and install or uninstall flatpak/snapd itself. When enabled, their apps appear in the sidebar and are included in searches and upgrades. Flatpak installs run without a password; Snap always needs one.':
        'Schaltet Flatpak- und Snap-Unterstützung ein oder aus und installiert bzw. deinstalliert flatpak/snapd selbst. Sind sie aktiv, erscheinen ihre Apps in der Seitenleiste und werden bei Suche und Upgrades einbezogen. Flatpak-Installationen laufen ohne Passwort; Snap braucht immer eines.',
    '“Confirm before removing packages” asks before anything is uninstalled. “Check for updates on startup” and “Notify when updates are available” control the automatic update check and its desktop notification.':
        '„Vor dem Entfernen von Paketen bestätigen“ fragt nach, bevor etwas deinstalliert wird. „Beim Start auf Updates prüfen“ und „Benachrichtigen, wenn Updates verfügbar sind“ steuern die automatische Update-Prüfung und ihre Desktop-Benachrichtigung.',
    'Scans at startup for fixable problems such as failed services or no active firewall. If something is found, a summary dialog lets you open the matching tool — nothing is changed automatically. Turn it off under Preferences → Behaviour.':
        'Prüft beim Start auf behebbare Probleme wie fehlgeschlagene Dienste oder fehlende Firewall. Wird etwas gefunden, öffnet eine Zusammenfassung das passende Werkzeug – es wird nichts automatisch geändert. Abschalten unter Einstellungen → Verhalten.',
    'If Timeshift or Snapper is installed, a restore point can be created before every system upgrade as a safety net.':
        'Ist Timeshift oder Snapper installiert, kann vor jedem System-Upgrade ein Wiederherstellungspunkt als Sicherheitsnetz angelegt werden.',
    "“Follow System” uses the desktop's light or dark setting; “Dark Mode” switches manually (Ctrl+Shift+D toggles). Changes apply immediately.":
        '„Wie das System“ übernimmt die helle oder dunkle Einstellung des Desktops; „Dunkler Modus“ schaltet von Hand um (Strg+Umschalt+D wechselt). Änderungen gelten sofort.',
    'Switches between English, German, French and Italian. The interface is rebuilt right away, no restart needed.':
        'Wechselt zwischen Englisch, Deutsch, Französisch und Italienisch. Die Oberfläche wird sofort neu aufgebaut, ein Neustart ist nicht nötig.',
    'Start the tray icon automatically at login to see pending updates at a glance. The background service checks for updates through a systemd user timer (hourly, every 6 hours or daily), even when Pachul is closed.':
        'Starte das Tray-Icon automatisch beim Anmelden, um anstehende Updates auf einen Blick zu sehen. Der Hintergrunddienst prüft über einen systemd-Benutzer-Timer (stündlich, alle 6 Stunden oder täglich) auf Updates, auch wenn Pachul geschlossen ist.',
    'Opens this window (F1). Type in the search field at the top to find a topic quickly.':
        'Öffnet dieses Fenster (F1). Tippe oben ins Suchfeld, um schnell ein Thema zu finden.',
    'Search help…':
        'Hilfe durchsuchen…',
    'No matching help topics':
        'Keine passenden Hilfethemen',
    'Update Selected':
        'Auswahl aktualisieren',
    'What can be updated here?':
        'Was kann hier aktualisiert werden?',
    'Unignore':
        'Nicht mehr ignorieren',
    'Unignore All':
        'Alle nicht mehr ignorieren',
    'Check for fixable system problems on startup':
        'Beim Start auf behebbare Systemprobleme prüfen',
}.items():
    STRINGS_DE.setdefault(_k, _v)

for _k, _v in {
    'Getting Started':
        'Premiers pas',
    'Installing & Removing':
        'Installer et supprimer',
    'Window layout':
        'Disposition de la fenêtre',
    'Header bar buttons':
        "Boutons de la barre d'en-tête",
    'Sidebar counters':
        'Compteurs de la barre latérale',
    'Status badges':
        "Pastilles d'état",
    'Administrator rights':
        "Droits d'administrateur",
    'Tooltips and info boxes':
        "Info-bulles et encadrés d'information",
    'All Packages / Updates':
        'Tous les paquets / Mises à jour',
    'NEW section':
        'Section NOUVEAU',
    'INSTALLED PACKAGES section':
        'Section PAQUETS INSTALLÉS',
    'Dependencies':
        'Dépendances',
    'Ignore Updates':
        'Ignorer les mises à jour',
    'Bottom action bar':
        "Barre d'actions en bas",
    'Updates outside the package manager':
        'Mises à jour hors du gestionnaire de paquets',
    'Notifications and background checks':
        'Notifications et vérifications en arrière-plan',
    'Repair System (apt/dpkg)…':
        'Réparer le système (apt/dpkg)…',
    'Repair System (dnf/rpm)…':
        'Réparer le système (dnf/rpm)…',
    'Repair System (zypper/rpm)…':
        'Réparer le système (zypper/rpm)…',
    'Confirmations and notifications':
        'Confirmations et notifications',
    'Startup health check':
        'Vérification du système au démarrage',
    'Snapshot before upgrades':
        'Instantané avant les mises à niveau',
    'Tray icon and background service':
        'Icône de notification et service en arrière-plan',
    'Python bindings (apt / dnf)':
        'Liaisons Python (apt / dnf)',
    'Preferences Explained':
        'Préférences expliquées',
    'The window has three parts: the sidebar on the left (filters and counters), the package list in the middle (with the search bar) and the details of the selected package on the right. The header bar at the top gives access to Packages, Tools, Preferences, Help and About Pachul.':
        "La fenêtre comporte trois parties : à gauche la barre latérale (filtres et compteurs), au centre la liste des paquets (avec la barre de recherche) et à droite les détails du paquet sélectionné. La barre d'en-tête en haut donne accès à Paquets, Outils, Préférences, Aide et À propos de Pachul.",
    'Packages: sync, check for updates and actions for the selected packages. Tools (Ctrl+T): a searchable overview of all maintenance, repair and system tools — type a word and press Enter to open the first match. Preferences (Ctrl+,): all settings. Help (F1): this window. About Pachul: version, license and system info for bug reports.':
        'Paquets : synchroniser, rechercher des mises à jour et actions sur les paquets sélectionnés. Outils (Ctrl+T) : aperçu consultable de tous les outils de maintenance, de réparation et système — tapez un mot et appuyez sur Entrée pour ouvrir le premier résultat. Préférences (Ctrl+,) : tous les réglages. Aide (F1) : cette fenêtre. À propos de Pachul : version, licence et infos système pour les rapports de bogue.',
    'The three cards at the top of the sidebar show the total number of packages, how many of them come from the AUR, and how many updates are pending.':
        "Les trois cartes en haut de la barre latérale indiquent le nombre total de paquets, combien proviennent de l'AUR et combien de mises à jour sont en attente.",
    'INSTALLED marks a package that is already on your system, UPDATE marks an installed package for which a newer version is available. Next to the name, small badges show the version, the repository it comes from and its architecture.':
        "INSTALLÉ désigne un paquet déjà présent sur votre système, MISE À JOUR un paquet installé pour lequel une version plus récente existe. À côté du nom, de petites pastilles indiquent la version, le dépôt d'origine et l'architecture.",
    "Actions that change the system (installing, removing, repairing …) ask for your password through pkexec and show their progress in a terminal window. Read-only checks and scans run without elevated rights; each tool's description says which is which.":
        "Les actions qui modifient le système (installation, suppression, réparation …) demandent votre mot de passe via pkexec et affichent leur progression dans une fenêtre de terminal. Les vérifications et analyses en lecture seule s'exécutent sans droits élevés ; la description de chaque outil précise lequel c'est.",
    'Many rows in the tools carry a tooltip with the exact command that is run and what it affects — hold the mouse over a row to read it before pressing its button. Info boxes explain a topic once; those with a close button stay hidden after you dismiss them.':
        "De nombreuses lignes des outils ont une info-bulle indiquant la commande exacte exécutée et son effet — survolez une ligne pour la lire avant d'appuyer sur son bouton. Les encadrés d'information expliquent un sujet ; ceux qui ont un bouton de fermeture restent masqués une fois fermés.",
    'At the top of the sidebar: All Packages lists everything the package manager knows about; Updates lists only installed packages with a newer version available, with a count badge.':
        'En haut de la barre latérale : Tous les paquets liste tout ce que connaît le gestionnaire de paquets ; Mises à jour ne liste que les paquets installés ayant une version plus récente, avec un compteur.',
    'Everything that is not installed yet — either all at once (All New Packages) or per source such as core, extra, multilib, aur, Flatpak or Snap. A good place to discover software.':
        "Tout ce qui n'est pas encore installé — soit en bloc (Tous les nouveaux paquets), soit par source comme core, extra, multilib, aur, Flatpak ou Snap. Un bon endroit pour découvrir des logiciels.",
    'Everything that is already on your system — all of it (All Installed Packages) or per origin. Every repository appears in both sections, each with its own package counter.':
        'Tout ce qui est déjà sur votre système — en bloc (Tous les paquets installés) ou par origine. Chaque dépôt apparaît dans les deux sections, avec son propre compteur.',
    'Type in the search bar (or press Ctrl+F) to filter the list that is currently shown by name or description. Pick All Packages in the sidebar first if you want to search everything.':
        "Saisissez du texte dans la barre de recherche (ou appuyez sur Ctrl+F) pour filtrer la liste affichée par nom ou description. Choisissez d'abord Tous les paquets dans la barre latérale pour tout rechercher.",
    'Click a package to see its description and actions on the right. The Info tab shows version, size, license, dependencies and more; the Files tab lists every file the installed package placed on your system, with a filter field and a file counter.':
        "Cliquez sur un paquet pour voir à droite sa description et ses actions. L'onglet Infos affiche version, taille, licence, dépendances et plus ; l'onglet Fichiers liste chaque fichier installé par le paquet, avec un champ de filtre et un compteur.",
    'Dependency entries in the Info tab are buttons: click one to look that package up. Long lists can be expanded.':
        "Les dépendances de l'onglet Infos sont des boutons : cliquez sur l'un d'eux pour rechercher ce paquet. Les longues listes peuvent être déployées.",
    'Installs the selected package from its source — repository, AUR, Flatpak or Snap. A terminal window shows the progress, and your password is asked via pkexec when needed.':
        'Installe le paquet sélectionné depuis sa source — dépôt, AUR, Flatpak ou Snap. Une fenêtre de terminal affiche la progression et le mot de passe est demandé via pkexec si nécessaire.',
    'Removes the selected package. If “Confirm before removing packages” is switched on in Preferences, you are asked first.':
        'Supprime le paquet sélectionné. Si « Confirmer avant de supprimer des paquets » est activé dans les préférences, une confirmation est demandée.',
    'Installs the same version of an installed package again — useful when some of its files are damaged or missing.':
        "Réinstalle la même version d'un paquet installé — utile lorsque certains de ses fichiers sont endommagés ou manquants.",
    'Shows older versions of the package — those still in the package cache first, others from the repository if available — and installs the one you pick. Afterwards use Ignore Updates, or the next upgrade will install the newer version again.':
        "Affiche les versions plus anciennes du paquet — d'abord celles encore dans le cache, puis celles du dépôt si disponibles — et installe celle que vous choisissez. Utilisez ensuite Ignorer les mises à jour, sinon la prochaine mise à niveau réinstallera la version récente.",
    'Pins a package at its current version so system upgrades skip it until you release it again (Arch: IgnorePkg in /etc/pacman.conf, Debian: apt-mark hold, openSUSE: package lock). Use it only temporarily — a package that falls behind its libraries can break or block other updates. All held packages are listed under Tools → Ignored Packages.':
        "Fige un paquet à sa version actuelle : les mises à niveau du système l'ignorent jusqu'à ce que vous le libériez (Arch : IgnorePkg dans /etc/pacman.conf, Debian : apt-mark hold, openSUSE : verrou de paquet). À n'utiliser que temporairement — un paquet qui reste en retard sur ses bibliothèques peut cesser de fonctionner ou bloquer d'autres mises à jour. Tous les paquets retenus figurent sous Outils → Paquets ignorés.",
    'Tick the checkboxes in the package list to select several packages. The right side then lists the selection, and the bottom bar offers Install, Uninstall and Ignore Updates for all of them at once. Ctrl+A selects everything currently visible, Ctrl+Shift+A clears the selection.':
        'Cochez les cases dans la liste pour sélectionner plusieurs paquets. La partie droite affiche alors la sélection et la barre du bas propose Installer, Désinstaller et Ignorer les mises à jour pour tous à la fois. Ctrl+A sélectionne tout ce qui est visible, Ctrl+Maj+A efface la sélection.',
    'Left: buttons to select or deselect all visible packages, then Install. Right: Uninstall and Ignore Updates. Upgrade All appears whenever updates are pending, and Check for Updates is available in the Updates view.':
        'À gauche : boutons pour sélectionner ou désélectionner tous les paquets visibles, puis Installer. À droite : Désinstaller et Ignorer les mises à jour. Tout mettre à niveau apparaît dès que des mises à jour sont en attente, et Vérifier les mises à jour est disponible dans la vue Mises à jour.',
    'Downloads the latest package lists from the repositories without installing anything (F5). A confirmation dialog explains what happens first.':
        "Télécharge les dernières listes de paquets depuis les dépôts sans rien installer (F5). Une boîte de confirmation explique d'abord ce qui va se passer.",
    'Syncs, then rebuilds the Updates list (Ctrl+U, or the button in the Updates view). AUR packages are included if enabled in Preferences.':
        'Synchronise, puis reconstruit la liste des mises à jour (Ctrl+U, ou le bouton dans la vue Mises à jour). Les paquets AUR sont inclus si cela est activé dans les préférences.',
    'Reloads the view from what is already known locally, without contacting the repositories (Ctrl+R).':
        'Recharge la vue à partir de ce qui est déjà connu localement, sans contacter les dépôts (Ctrl+R).',
    'Installs every pending update in one go. If Timeshift or Snapper is found and enabled in Preferences, a restore point is created first. Flatpak and Snap updates are included when those sources are enabled.':
        "Installe d'un coup toutes les mises à jour en attente. Si Timeshift ou Snapper est détecté et activé dans les préférences, un point de restauration est créé d'abord. Les mises à jour Flatpak et Snap sont incluses lorsque ces sources sont activées.",
    "Developer and system tools that normal upgrades don't cover (rustup, npm, pip, firmware …) are handled under Tools → More Update Sources.":
        'Les outils de développement et système que les mises à niveau normales ne couvrent pas (rustup, npm, pip, firmware …) se gèrent sous Outils → Autres sources de mise à jour.',
    'Preferences can check for updates on startup and notify you when some are available. With the tray icon and the background service, checks also run periodically while Pachul is closed.':
        "Les préférences permettent de rechercher des mises à jour au démarrage et d'être notifié. Avec l'icône de notification et le service en arrière-plan, des vérifications périodiques ont lieu même lorsque Pachul est fermé.",
    'Installs a downloaded file: a built package (.pkg.tar.*, installed with pacman -U), a .tar.gz with a PKGBUILD (built with makepkg first), .deb, .rpm, .flatpak or .flatpakref. Pachul recognises the type, shows what it found and asks before installing. Only formats your distribution can handle work.':
        "Installe un fichier téléchargé : un paquet construit (.pkg.tar.*, installé avec pacman -U), un .tar.gz avec PKGBUILD (construit d'abord avec makepkg), .deb, .rpm, .flatpak ou .flatpakref. Pachul reconnaît le type, montre ce qu'il a trouvé et demande confirmation avant d'installer. Seuls les formats pris en charge par votre distribution fonctionnent.",
    'Arch: shows the active repositories and lets you edit pacman.conf (for example to enable multilib) — a wrong entry can stop updates from working, so change it with care. Other distributions: enable, disable or add software sources without editing files by hand.':
        'Arch : affiche les dépôts actifs et permet de modifier pacman.conf (par exemple pour activer multilib) — une entrée erronée peut empêcher les mises à jour, modifiez donc avec prudence. Autres distributions : activer, désactiver ou ajouter des sources logicielles sans modifier de fichiers à la main.',
    'Tests the configured mirrors, ranks them by speed and lets you apply the fastest ones to make downloads quicker. Arch only — Fedora and openSUSE already pick the fastest mirror automatically. An info box in the dialog explains what mirrors are.':
        'Teste les miroirs configurés, les classe par vitesse et applique à votre demande les plus rapides pour accélérer les téléchargements. Arch uniquement — Fedora et openSUSE choisissent déjà automatiquement le miroir le plus rapide. Un encadré dans la fenêtre explique ce que sont les miroirs.',
    "Checks tools that normal upgrades don't cover: rustup, cargo, pip/pipx, npm, fnm/nvm, firmware (fwupd), Docker/Podman images, editor plugins and more. Update them once with “Update Selected”, or tick a tool to have it run automatically with every normal system upgrade. The “What can be updated here?” list shows everything supported, even if it isn't installed.":
        "Vérifie les outils que les mises à niveau normales ne couvrent pas : rustup, cargo, pip/pipx, npm, fnm/nvm, firmware (fwupd), images Docker/Podman, extensions d'éditeur et plus. Mettez-les à jour une fois avec « Mettre à jour la sélection », ou cochez un outil pour qu'il s'exécute automatiquement à chaque mise à niveau du système. La liste « Que peut-on mettre à jour ici ? » montre tout ce qui est pris en charge, même non installé.",
    'Installs packages from a list file you exported earlier. After you pick the file, the packages found in it are shown before anything is installed.':
        "Installe des paquets à partir d'un fichier de liste exporté auparavant. Après le choix du fichier, les paquets trouvés sont affichés avant toute installation.",
    'Saves the names of your explicitly installed programs to a text file — handy for setting up another machine the same way (use Import Package List there). You choose the target location first.':
        "Enregistre les noms des programmes installés explicitement dans un fichier texte — pratique pour configurer une autre machine à l'identique (utilisez-y Importer une liste de paquets). Vous choisissez d'abord l'emplacement.",
    'Lists packages that were installed as dependencies and are no longer needed by anything, so you can remove them and free space. Check the list first: a program you use directly can show up here if it was marked as a dependency — use Mark Selected as Explicit to protect it.':
        "Liste les paquets installés comme dépendances et dont plus rien n'a besoin, afin que vous puissiez les supprimer et libérer de l'espace. Vérifiez d'abord la liste : un programme que vous utilisez directement peut apparaître ici s'il était marqué comme dépendance — utilisez Marquer la sélection comme explicite pour le protéger.",
    'Frees disk space used by downloaded package files. On Arch it keeps the 2 newest versions of each package (paccache), so a downgrade stays possible; installed packages are never touched. The dialog also offers general cleanup: shrink the systemd journal (500 MB / 4 weeks), delete thumbnails older than 30 days and empty the trash — emptying the trash cannot be undone.':
        "Libère l'espace occupé par les fichiers de paquets téléchargés. Sous Arch, les 2 versions les plus récentes de chaque paquet sont conservées (paccache), pour qu'un retour en arrière reste possible ; les paquets installés ne sont jamais touchés. La fenêtre propose aussi un nettoyage général : réduire le journal systemd (500 Mo / 4 semaines), supprimer les miniatures de plus de 30 jours et vider la corbeille — cette dernière action est irréversible.",
    'After an update, a package can leave a new default configuration file (.pacnew) or a backup (.pacsave) next to yours instead of overwriting your changes. This tool shows the differences and helps you merge or discard them.':
        "Après une mise à jour, un paquet peut laisser un nouveau fichier de configuration par défaut (.pacnew) ou une sauvegarde (.pacsave) à côté du vôtre au lieu d'écraser vos modifications. Cet outil montre les différences et aide à les fusionner ou à les rejeter.",
    'After an update, a package can leave a new default configuration file (such as .rpmnew or .dpkg-dist) next to yours instead of overwriting your changes. This tool shows the differences and helps you merge or discard them.':
        "Après une mise à jour, un paquet peut laisser un nouveau fichier de configuration par défaut (comme .rpmnew ou .dpkg-dist) à côté du vôtre au lieu d'écraser vos modifications. Cet outil montre les différences et aide à les fusionner ou à les rejeter.",
    'Overview of all packages currently held back from upgrades, with an Unignore button for each (and Unignore All). An info box explains why holding packages for long is risky.':
        'Aperçu de tous les paquets actuellement exclus des mises à niveau, avec un bouton Ne plus ignorer pour chacun (et Tout ne plus ignorer). Un encadré explique pourquoi retenir longtemps des paquets est risqué.',
    'A log of past installs, upgrades and removals with dates — useful to find out what changed before something stopped working.':
        "Un journal des installations, mises à niveau et suppressions passées, avec les dates — utile pour savoir ce qui a changé avant qu'un problème n'apparaisse.",
    "Finds out which package a file belongs to: enter a file name or path. If the file database hasn't been synced yet, you are offered to do that first.":
        "Détermine à quel paquet appartient un fichier : saisissez un nom de fichier ou un chemin. Si la base de fichiers n'est pas encore synchronisée, il vous est d'abord proposé de le faire.",
    'Standard Maintenance: Force-Refresh & Full Upgrade (pacman -Syyu), a read-only database consistency check, and Reinitialize Keyring (helps with signature errors). Diagnose: search for packages with missing or modified files and reinstall the ones you pick. Last Resort: force-remove a broken package while ignoring dependencies — only when nothing else works.':
        "Maintenance standard : actualisation forcée et mise à niveau complète (pacman -Syyu), vérification de cohérence de la base en lecture seule et Réinitialiser le trousseau de clés (aide en cas d'erreurs de signature). Diagnostic : rechercher les paquets avec fichiers manquants ou modifiés et réinstaller ceux que vous choisissez. Dernier recours : supprimer de force un paquet défectueux en ignorant les dépendances — uniquement si rien d'autre ne fonctionne.",
    'Standard Maintenance: update, upgrade & autoremove, fix broken dependencies, reconfigure all packages, fix missing or corrupt package files and clean the package cache. Diagnose lists broken or incomplete packages; Last Resort offers a forced removal.':
        'Maintenance standard : mise à jour, mise à niveau et autoremove, réparation des dépendances cassées, reconfiguration de tous les paquets, réparation des fichiers de paquets manquants ou corrompus et nettoyage du cache. Le diagnostic liste les paquets cassés ou incomplets ; le dernier recours propose une suppression forcée.',
    'Standard Maintenance: update, upgrade & autoremove, fix inconsistent package versions, rebuild the RPM database and clean the package cache. Diagnose shows broken or unsatisfied packages; Last Resort offers a forced removal.':
        'Maintenance standard : mise à jour, mise à niveau et autoremove, correction des versions de paquets incohérentes, reconstruction de la base RPM et nettoyage du cache. Le diagnostic affiche les paquets cassés ou aux dépendances non satisfaites ; le dernier recours propose une suppression forcée.',
    'Standard Maintenance: update & upgrade, fix broken dependencies, rebuild the RPM database and clean the package cache. Diagnose shows broken or unsatisfied packages; Last Resort offers a forced removal.':
        'Maintenance standard : mise à jour et mise à niveau, réparation des dépendances cassées, reconstruction de la base RPM et nettoyage du cache. Le diagnostic affiche les paquets cassés ou aux dépendances non satisfaites ; le dernier recours propose une suppression forcée.',
    'Domain check: connects live to the domains you enter (port 443) and reports the days left until the certificate expires. Local check: read-only scan of the .pem files in /etc/ssl/certs. There is also a one-click reinstall of the CA certificate bundle for when HTTPS errors hit many unrelated sites at once.':
        "Vérification de domaine : se connecte en direct aux domaines saisis (port 443) et indique les jours restants avant l'expiration du certificat. Vérification locale : analyse en lecture seule des fichiers .pem dans /etc/ssl/certs. Il existe aussi une réinstallation en un clic du lot de certificats CA, utile lorsque des erreurs HTTPS touchent simultanément de nombreux sites sans rapport.",
    'Scans /usr and /etc for symbolic links whose target no longer exists and sorts them into license leftovers (safe), archiso templates (expected) and everything else (review by hand). Scanning is read-only; the clean-up button deletes only the safe license leftovers and needs administrator rights.':
        "Analyse /usr et /etc à la recherche de liens symboliques dont la cible n'existe plus et les classe en restes de licences (sans risque), modèles archiso (attendus) et tout le reste (à examiner à la main). L'analyse est en lecture seule ; le bouton de nettoyage ne supprime que les restes de licences sans risque et nécessite des droits d'administrateur.",
    'Operating system, kernel, hardware and package statistics in one place — a good thing to include in a bug report.':
        "Système d'exploitation, noyau, matériel et statistiques de paquets au même endroit — utile à joindre à un rapport de bogue.",
    'Shows failed systemd services (with a one-click reset for the usually harmless shadow.service), whether firewalld, fail2ban and apparmor are active, the UFW firewall (show rules, install and enable) and a check of the SSH root-login setting. Most checks are read-only.':
        "Affiche les services systemd en échec (avec réinitialisation en un clic du shadow.service, généralement sans gravité), l'état actif de firewalld, fail2ban et apparmor, le pare-feu UFW (afficher les règles, installer et activer) et une vérification de la connexion root par SSH. La plupart des vérifications sont en lecture seule.",
    'Creates a compressed archive of important system configuration (fstab, hostname, bootloader, package-manager config …) plus a list of installed packages in the folder you choose (default: ~/pachul-backup). Only the last 5 archives are kept. No administrator rights needed.':
        "Crée une archive compressée de la configuration système importante (fstab, nom d'hôte, chargeur d'amorçage, configuration du gestionnaire de paquets …) plus une liste des paquets installés dans le dossier choisi (par défaut : ~/pachul-backup). Seules les 5 dernières archives sont conservées. Aucun droit d'administrateur requis.",
    "Shows the build script of an AUR package before you install it, so you can see what it will do — always worth a look for unfamiliar packages. A link button in the viewer opens the package's AUR page (votes, comments, discussion).":
        "Affiche le script de construction d'un paquet AUR avant son installation, pour voir ce qu'il fera — toujours utile pour un paquet inconnu. Un bouton lien dans la fenêtre ouvre la page AUR du paquet (votes, commentaires, discussion).",
    'Same as Ignore Updates, but from the Packages menu: toggles whether the selected packages are excluded from upgrades. A dialog explains the effect and asks for confirmation.':
        "Comme Ignorer les mises à jour, mais depuis le menu Paquets : bascule l'exclusion des paquets sélectionnés des mises à niveau. Une boîte de dialogue explique l'effet et demande confirmation.",
    'Changes how a package is tracked. Explicit means installed on purpose, so it is never offered for removal as an orphan; Dependency means installed for other packages, so it shows up in Find Orphans once nothing needs it any more. Only this label changes — nothing is installed or removed.':
        "Modifie la façon dont un paquet est suivi. Explicite signifie installé volontairement : il n'est jamais proposé à la suppression comme orphelin ; Dépendance signifie installé pour d'autres paquets : il apparaît dans Trouver les orphelins dès que plus rien n'en a besoin. Seule cette étiquette change — rien n'est installé ni supprimé.",
    "Chooses the program used for AUR installs, updates and PKGBUILDs: auto-detect, pachuli (Pachul's own minimal helper), yay, paru, pikaur or none (pacman only). A missing helper can be installed right from the Preferences. “Include AUR in update checks” also looks for newer AUR versions — switch it off if checks are slow or you don't use the AUR.":
        "Choisit le programme utilisé pour les installations, mises à jour et PKGBUILD de l'AUR : détection automatique, pachuli (l'assistant minimal de Pachul), yay, paru, pikaur ou aucun (pacman seul). Un assistant manquant peut être installé directement depuis les préférences. « Inclure l'AUR dans les vérifications » cherche aussi des versions AUR plus récentes — désactivez-le si les vérifications sont lentes ou si vous n'utilisez pas l'AUR.",
    'If python3-apt (Debian/Ubuntu) or python3-libdnf5 (Fedora) is missing, Preferences offers to install it. It speeds up package info, listing and update checks; Pachul works without it, just more slowly. Restart Pachul afterwards.':
        "Si python3-apt (Debian/Ubuntu) ou python3-libdnf5 (Fedora) est absent, les préférences proposent de l'installer. Cela accélère les infos de paquets, les listes et les vérifications de mises à jour ; Pachul fonctionne sans, mais plus lentement. Redémarrez ensuite Pachul.",
    'Switch Flatpak and Snap support on or off, and install or uninstall flatpak/snapd itself. When enabled, their apps appear in the sidebar and are included in searches and upgrades. Flatpak installs run without a password; Snap always needs one.':
        'Active ou désactive la prise en charge de Flatpak et Snap, et installe ou désinstalle flatpak/snapd lui-même. Une fois activées, leurs applications apparaissent dans la barre latérale et sont incluses dans les recherches et mises à niveau. Les installations Flatpak se font sans mot de passe ; Snap en exige toujours un.',
    '“Confirm before removing packages” asks before anything is uninstalled. “Check for updates on startup” and “Notify when updates are available” control the automatic update check and its desktop notification.':
        '« Confirmer avant de supprimer des paquets » demande confirmation avant toute désinstallation. « Vérifier les mises à jour au démarrage » et « Notifier lorsque des mises à jour sont disponibles » contrôlent la vérification automatique et sa notification sur le bureau.',
    'Scans at startup for fixable problems such as failed services or no active firewall. If something is found, a summary dialog lets you open the matching tool — nothing is changed automatically. Turn it off under Preferences → Behaviour.':
        "Recherche au démarrage les problèmes réparables, comme des services en échec ou l'absence de pare-feu actif. Si quelque chose est trouvé, un récapitulatif permet d'ouvrir l'outil adapté — rien n'est modifié automatiquement. Désactivation sous Préférences → Comportement.",
    'If Timeshift or Snapper is installed, a restore point can be created before every system upgrade as a safety net.':
        'Si Timeshift ou Snapper est installé, un point de restauration peut être créé avant chaque mise à niveau du système comme filet de sécurité.',
    "“Follow System” uses the desktop's light or dark setting; “Dark Mode” switches manually (Ctrl+Shift+D toggles). Changes apply immediately.":
        "« Suivre le système » reprend le réglage clair ou sombre du bureau ; « Mode sombre » bascule manuellement (Ctrl+Maj+D alterne). Les changements s'appliquent immédiatement.",
    'Switches between English, German, French and Italian. The interface is rebuilt right away, no restart needed.':
        "Bascule entre anglais, allemand, français et italien. L'interface est reconstruite immédiatement, aucun redémarrage n'est nécessaire.",
    'Start the tray icon automatically at login to see pending updates at a glance. The background service checks for updates through a systemd user timer (hourly, every 6 hours or daily), even when Pachul is closed.':
        "Lancez automatiquement l'icône de notification à l'ouverture de session pour voir d'un coup d'œil les mises à jour en attente. Le service en arrière-plan recherche les mises à jour via un minuteur utilisateur systemd (toutes les heures, toutes les 6 heures ou chaque jour), même lorsque Pachul est fermé.",
    'Opens this window (F1). Type in the search field at the top to find a topic quickly.':
        'Ouvre cette fenêtre (F1). Saisissez du texte dans le champ de recherche en haut pour trouver rapidement un sujet.',
    'Search help…':
        "Rechercher dans l'aide…",
    'No matching help topics':
        "Aucun sujet d'aide correspondant",
    'Update Selected':
        'Mettre à jour la sélection',
    'What can be updated here?':
        'Que peut-on mettre à jour ici ?',
    'Unignore':
        'Ne plus ignorer',
    'Unignore All':
        'Tout ne plus ignorer',
    'Check for fixable system problems on startup':
        'Rechercher au démarrage les problèmes système réparables',
}.items():
    STRINGS_FR.setdefault(_k, _v)

for _k, _v in {
    'Getting Started':
        'Per iniziare',
    'Installing & Removing':
        'Installare e rimuovere',
    'Window layout':
        'Struttura della finestra',
    'Header bar buttons':
        'Pulsanti della barra del titolo',
    'Sidebar counters':
        'Contatori della barra laterale',
    'Status badges':
        'Indicatori di stato',
    'Administrator rights':
        'Diritti di amministratore',
    'Tooltips and info boxes':
        'Suggerimenti e riquadri informativi',
    'All Packages / Updates':
        'Tutti i pacchetti / Aggiornamenti',
    'NEW section':
        'Sezione NUOVI',
    'INSTALLED PACKAGES section':
        'Sezione PACCHETTI INSTALLATI',
    'Dependencies':
        'Dipendenze',
    'Ignore Updates':
        'Ignora aggiornamenti',
    'Bottom action bar':
        'Barra delle azioni in basso',
    'Updates outside the package manager':
        'Aggiornamenti esterni al gestore pacchetti',
    'Notifications and background checks':
        'Notifiche e controlli in background',
    'Repair System (apt/dpkg)…':
        'Ripara sistema (apt/dpkg)…',
    'Repair System (dnf/rpm)…':
        'Ripara sistema (dnf/rpm)…',
    'Repair System (zypper/rpm)…':
        'Ripara sistema (zypper/rpm)…',
    'Confirmations and notifications':
        'Conferme e notifiche',
    'Startup health check':
        "Controllo del sistema all'avvio",
    'Snapshot before upgrades':
        'Snapshot prima degli aggiornamenti',
    'Tray icon and background service':
        'Icona nella barra di stato e servizio in background',
    'Python bindings (apt / dnf)':
        'Binding Python (apt / dnf)',
    'Preferences Explained':
        'Preferenze spiegate',
    'The window has three parts: the sidebar on the left (filters and counters), the package list in the middle (with the search bar) and the details of the selected package on the right. The header bar at the top gives access to Packages, Tools, Preferences, Help and About Pachul.':
        "La finestra ha tre parti: a sinistra la barra laterale (filtri e contatori), al centro l'elenco dei pacchetti (con la barra di ricerca) e a destra i dettagli del pacchetto selezionato. La barra del titolo in alto dà accesso a Pacchetti, Strumenti, Preferenze, Aiuto e Informazioni su Pachul.",
    'Packages: sync, check for updates and actions for the selected packages. Tools (Ctrl+T): a searchable overview of all maintenance, repair and system tools — type a word and press Enter to open the first match. Preferences (Ctrl+,): all settings. Help (F1): this window. About Pachul: version, license and system info for bug reports.':
        'Pacchetti: sincronizzazione, controllo aggiornamenti e azioni per i pacchetti selezionati. Strumenti (Ctrl+T): panoramica ricercabile di tutti gli strumenti di manutenzione, riparazione e di sistema — digita una parola e premi Invio per aprire il primo risultato. Preferenze (Ctrl+,): tutte le impostazioni. Aiuto (F1): questa finestra. Informazioni su Pachul: versione, licenza e info di sistema per le segnalazioni di errori.',
    'The three cards at the top of the sidebar show the total number of packages, how many of them come from the AUR, and how many updates are pending.':
        "Le tre schede in alto nella barra laterale mostrano il numero totale di pacchetti, quanti provengono dall'AUR e quanti aggiornamenti sono in sospeso.",
    'INSTALLED marks a package that is already on your system, UPDATE marks an installed package for which a newer version is available. Next to the name, small badges show the version, the repository it comes from and its architecture.':
        'INSTALLATO indica un pacchetto già presente nel sistema, AGGIORNAMENTO un pacchetto installato per cui esiste una versione più recente. Accanto al nome, piccoli indicatori mostrano versione, repository di origine e architettura.',
    "Actions that change the system (installing, removing, repairing …) ask for your password through pkexec and show their progress in a terminal window. Read-only checks and scans run without elevated rights; each tool's description says which is which.":
        "Le azioni che modificano il sistema (installazione, rimozione, riparazione …) chiedono la password tramite pkexec e mostrano l'avanzamento in una finestra di terminale. I controlli e le scansioni di sola lettura non richiedono privilegi elevati; la descrizione di ogni strumento indica quale caso si applica.",
    'Many rows in the tools carry a tooltip with the exact command that is run and what it affects — hold the mouse over a row to read it before pressing its button. Info boxes explain a topic once; those with a close button stay hidden after you dismiss them.':
        'Molte righe degli strumenti hanno un suggerimento con il comando esatto eseguito e i suoi effetti — passa il mouse su una riga per leggerlo prima di premere il pulsante. I riquadri informativi spiegano un argomento; quelli con un pulsante di chiusura restano nascosti dopo la chiusura.',
    'At the top of the sidebar: All Packages lists everything the package manager knows about; Updates lists only installed packages with a newer version available, with a count badge.':
        'In cima alla barra laterale: Tutti i pacchetti elenca tutto ciò che il gestore pacchetti conosce; Aggiornamenti elenca solo i pacchetti installati con una versione più recente, con un contatore.',
    'Everything that is not installed yet — either all at once (All New Packages) or per source such as core, extra, multilib, aur, Flatpak or Snap. A good place to discover software.':
        'Tutto ciò che non è ancora installato — tutto insieme (Tutti i pacchetti nuovi) oppure per fonte come core, extra, multilib, aur, Flatpak o Snap. Un buon posto per scoprire software.',
    'Everything that is already on your system — all of it (All Installed Packages) or per origin. Every repository appears in both sections, each with its own package counter.':
        'Tutto ciò che è già nel sistema — tutto insieme (Tutti i pacchetti installati) oppure per origine. Ogni repository compare in entrambe le sezioni, ciascuno con il proprio contatore.',
    'Type in the search bar (or press Ctrl+F) to filter the list that is currently shown by name or description. Pick All Packages in the sidebar first if you want to search everything.':
        "Scrivi nella barra di ricerca (o premi Ctrl+F) per filtrare per nome o descrizione l'elenco attualmente mostrato. Scegli prima Tutti i pacchetti nella barra laterale per cercare ovunque.",
    'Click a package to see its description and actions on the right. The Info tab shows version, size, license, dependencies and more; the Files tab lists every file the installed package placed on your system, with a filter field and a file counter.':
        'Fai clic su un pacchetto per vedere a destra descrizione e azioni. La scheda Info mostra versione, dimensione, licenza, dipendenze e altro; la scheda File elenca ogni file che il pacchetto installato ha messo nel sistema, con campo filtro e contatore.',
    'Dependency entries in the Info tab are buttons: click one to look that package up. Long lists can be expanded.':
        'Le dipendenze nella scheda Info sono pulsanti: fai clic su uno per cercare quel pacchetto. Gli elenchi lunghi possono essere espansi.',
    'Installs the selected package from its source — repository, AUR, Flatpak or Snap. A terminal window shows the progress, and your password is asked via pkexec when needed.':
        "Installa il pacchetto selezionato dalla sua fonte — repository, AUR, Flatpak o Snap. Una finestra di terminale mostra l'avanzamento e la password viene richiesta tramite pkexec quando serve.",
    'Removes the selected package. If “Confirm before removing packages” is switched on in Preferences, you are asked first.':
        'Rimuove il pacchetto selezionato. Se nelle preferenze è attiva «Conferma prima di rimuovere i pacchetti», viene chiesta una conferma.',
    'Installs the same version of an installed package again — useful when some of its files are damaged or missing.':
        'Reinstalla la stessa versione di un pacchetto installato — utile quando alcuni suoi file sono danneggiati o mancanti.',
    'Shows older versions of the package — those still in the package cache first, others from the repository if available — and installs the one you pick. Afterwards use Ignore Updates, or the next upgrade will install the newer version again.':
        'Mostra le versioni precedenti del pacchetto — prima quelle ancora nella cache, poi quelle del repository se disponibili — e installa quella scelta. Usa poi Ignora aggiornamenti, altrimenti il prossimo aggiornamento reinstallerà la versione più recente.',
    'Pins a package at its current version so system upgrades skip it until you release it again (Arch: IgnorePkg in /etc/pacman.conf, Debian: apt-mark hold, openSUSE: package lock). Use it only temporarily — a package that falls behind its libraries can break or block other updates. All held packages are listed under Tools → Ignored Packages.':
        'Blocca un pacchetto alla versione attuale: gli aggiornamenti di sistema lo saltano finché non lo rilasci (Arch: IgnorePkg in /etc/pacman.conf, Debian: apt-mark hold, openSUSE: blocco pacchetto). Usalo solo temporaneamente — un pacchetto rimasto indietro rispetto alle sue librerie può smettere di funzionare o bloccare altri aggiornamenti. Tutti i pacchetti bloccati sono elencati in Strumenti → Pacchetti ignorati.',
    'Tick the checkboxes in the package list to select several packages. The right side then lists the selection, and the bottom bar offers Install, Uninstall and Ignore Updates for all of them at once. Ctrl+A selects everything currently visible, Ctrl+Shift+A clears the selection.':
        "Spunta le caselle nell'elenco per selezionare più pacchetti. A destra compare la selezione e la barra in basso offre Installa, Disinstalla e Ignora aggiornamenti per tutti insieme. Ctrl+A seleziona tutto ciò che è visibile, Ctrl+Maiusc+A annulla la selezione.",
    'Left: buttons to select or deselect all visible packages, then Install. Right: Uninstall and Ignore Updates. Upgrade All appears whenever updates are pending, and Check for Updates is available in the Updates view.':
        'A sinistra: pulsanti per selezionare o deselezionare tutti i pacchetti visibili, poi Installa. A destra: Disinstalla e Ignora aggiornamenti. Aggiorna tutto compare quando ci sono aggiornamenti in sospeso e Controlla aggiornamenti è disponibile nella vista Aggiornamenti.',
    'Downloads the latest package lists from the repositories without installing anything (F5). A confirmation dialog explains what happens first.':
        'Scarica gli elenchi pacchetti più recenti dai repository senza installare nulla (F5). Una finestra di conferma spiega prima cosa accadrà.',
    'Syncs, then rebuilds the Updates list (Ctrl+U, or the button in the Updates view). AUR packages are included if enabled in Preferences.':
        "Sincronizza e poi ricostruisce l'elenco degli aggiornamenti (Ctrl+U, o il pulsante nella vista Aggiornamenti). I pacchetti AUR sono inclusi se abilitato nelle preferenze.",
    'Reloads the view from what is already known locally, without contacting the repositories (Ctrl+R).':
        'Ricarica la vista con ciò che è già noto localmente, senza contattare i repository (Ctrl+R).',
    'Installs every pending update in one go. If Timeshift or Snapper is found and enabled in Preferences, a restore point is created first. Flatpak and Snap updates are included when those sources are enabled.':
        'Installa tutti gli aggiornamenti in sospeso in un colpo solo. Se Timeshift o Snapper è presente e attivato nelle preferenze, prima viene creato un punto di ripristino. Gli aggiornamenti Flatpak e Snap sono inclusi quando queste fonti sono attive.',
    "Developer and system tools that normal upgrades don't cover (rustup, npm, pip, firmware …) are handled under Tools → More Update Sources.":
        'Gli strumenti di sviluppo e di sistema che gli aggiornamenti normali non coprono (rustup, npm, pip, firmware …) si gestiscono in Strumenti → Altre fonti di aggiornamento.',
    'Preferences can check for updates on startup and notify you when some are available. With the tray icon and the background service, checks also run periodically while Pachul is closed.':
        "Nelle preferenze puoi controllare gli aggiornamenti all'avvio ed essere avvisato. Con l'icona nella barra di stato e il servizio in background i controlli vengono eseguiti periodicamente anche a Pachul chiuso.",
    'Installs a downloaded file: a built package (.pkg.tar.*, installed with pacman -U), a .tar.gz with a PKGBUILD (built with makepkg first), .deb, .rpm, .flatpak or .flatpakref. Pachul recognises the type, shows what it found and asks before installing. Only formats your distribution can handle work.':
        'Installa un file scaricato: un pacchetto già compilato (.pkg.tar.*, con pacman -U), un .tar.gz con PKGBUILD (compilato prima con makepkg), .deb, .rpm, .flatpak o .flatpakref. Pachul riconosce il tipo, mostra cosa ha trovato e chiede conferma prima di installare. Funzionano solo i formati supportati dalla tua distribuzione.',
    'Arch: shows the active repositories and lets you edit pacman.conf (for example to enable multilib) — a wrong entry can stop updates from working, so change it with care. Other distributions: enable, disable or add software sources without editing files by hand.':
        'Arch: mostra i repository attivi e permette di modificare pacman.conf (ad esempio per abilitare multilib) — una voce errata può bloccare gli aggiornamenti, quindi modifica con cautela. Altre distribuzioni: abilita, disabilita o aggiungi sorgenti software senza modificare file a mano.',
    'Tests the configured mirrors, ranks them by speed and lets you apply the fastest ones to make downloads quicker. Arch only — Fedora and openSUSE already pick the fastest mirror automatically. An info box in the dialog explains what mirrors are.':
        'Prova i mirror configurati, li ordina per velocità e applica a richiesta i più veloci per rendere i download più rapidi. Solo Arch — Fedora e openSUSE scelgono già automaticamente il mirror più veloce. Un riquadro nella finestra spiega cosa sono i mirror.',
    "Checks tools that normal upgrades don't cover: rustup, cargo, pip/pipx, npm, fnm/nvm, firmware (fwupd), Docker/Podman images, editor plugins and more. Update them once with “Update Selected”, or tick a tool to have it run automatically with every normal system upgrade. The “What can be updated here?” list shows everything supported, even if it isn't installed.":
        "Controlla gli strumenti che gli aggiornamenti normali non coprono: rustup, cargo, pip/pipx, npm, fnm/nvm, firmware (fwupd), immagini Docker/Podman, plugin degli editor e altro. Aggiornali una volta con «Aggiorna selezionati», oppure spunta uno strumento per eseguirlo automaticamente a ogni aggiornamento di sistema. L'elenco «Cosa si può aggiornare qui?» mostra tutto ciò che è supportato, anche se non installato.",
    'Installs packages from a list file you exported earlier. After you pick the file, the packages found in it are shown before anything is installed.':
        'Installa i pacchetti da un file di elenco esportato in precedenza. Dopo aver scelto il file, i pacchetti trovati vengono mostrati prima di installare qualsiasi cosa.',
    'Saves the names of your explicitly installed programs to a text file — handy for setting up another machine the same way (use Import Package List there). You choose the target location first.':
        'Salva in un file di testo i nomi dei programmi installati esplicitamente — utile per configurare un altro computer allo stesso modo (lì usa Importa elenco pacchetti). Prima scegli la posizione di destinazione.',
    'Lists packages that were installed as dependencies and are no longer needed by anything, so you can remove them and free space. Check the list first: a program you use directly can show up here if it was marked as a dependency — use Mark Selected as Explicit to protect it.':
        "Elenca i pacchetti installati come dipendenze e di cui nulla ha più bisogno, così puoi rimuoverli e liberare spazio. Controlla prima l'elenco: un programma che usi direttamente può comparire qui se era segnato come dipendenza — usa Segna selezione come esplicita per proteggerlo.",
    'Frees disk space used by downloaded package files. On Arch it keeps the 2 newest versions of each package (paccache), so a downgrade stays possible; installed packages are never touched. The dialog also offers general cleanup: shrink the systemd journal (500 MB / 4 weeks), delete thumbnails older than 30 days and empty the trash — emptying the trash cannot be undone.':
        "Libera lo spazio occupato dai file dei pacchetti scaricati. Su Arch vengono mantenute le 2 versioni più recenti di ogni pacchetto (paccache), così il downgrade resta possibile; i pacchetti installati non vengono mai toccati. La finestra offre anche una pulizia generale: ridurre il journal di systemd (500 MB / 4 settimane), eliminare le miniature più vecchie di 30 giorni e svuotare il cestino — quest'ultima azione non è reversibile.",
    'After an update, a package can leave a new default configuration file (.pacnew) or a backup (.pacsave) next to yours instead of overwriting your changes. This tool shows the differences and helps you merge or discard them.':
        'Dopo un aggiornamento un pacchetto può lasciare accanto al tuo file un nuovo file di configurazione predefinito (.pacnew) o una copia (.pacsave) invece di sovrascrivere le tue modifiche. Questo strumento mostra le differenze e aiuta a unirle o scartarle.',
    'After an update, a package can leave a new default configuration file (such as .rpmnew or .dpkg-dist) next to yours instead of overwriting your changes. This tool shows the differences and helps you merge or discard them.':
        'Dopo un aggiornamento un pacchetto può lasciare accanto al tuo file un nuovo file di configurazione predefinito (come .rpmnew o .dpkg-dist) invece di sovrascrivere le tue modifiche. Questo strumento mostra le differenze e aiuta a unirle o scartarle.',
    'Overview of all packages currently held back from upgrades, with an Unignore button for each (and Unignore All). An info box explains why holding packages for long is risky.':
        'Panoramica di tutti i pacchetti attualmente esclusi dagli aggiornamenti, con un pulsante Non ignorare più per ciascuno (e Non ignorare più tutti). Un riquadro spiega perché trattenere a lungo i pacchetti è rischioso.',
    'A log of past installs, upgrades and removals with dates — useful to find out what changed before something stopped working.':
        'Un registro di installazioni, aggiornamenti e rimozioni passate con le date — utile per capire cosa è cambiato prima che qualcosa smettesse di funzionare.',
    "Finds out which package a file belongs to: enter a file name or path. If the file database hasn't been synced yet, you are offered to do that first.":
        'Scopre a quale pacchetto appartiene un file: inserisci un nome file o un percorso. Se il database dei file non è ancora sincronizzato, ti viene prima proposto di farlo.',
    'Standard Maintenance: Force-Refresh & Full Upgrade (pacman -Syyu), a read-only database consistency check, and Reinitialize Keyring (helps with signature errors). Diagnose: search for packages with missing or modified files and reinstall the ones you pick. Last Resort: force-remove a broken package while ignoring dependencies — only when nothing else works.':
        "Manutenzione standard: aggiornamento forzato e aggiornamento completo (pacman -Syyu), controllo di coerenza del database in sola lettura e Reinizializza il portachiavi (aiuta con gli errori di firma). Diagnosi: cerca i pacchetti con file mancanti o modificati e reinstalla quelli scelti. Ultima risorsa: rimuovere a forza un pacchetto difettoso ignorando le dipendenze — solo se nient'altro funziona.",
    'Standard Maintenance: update, upgrade & autoremove, fix broken dependencies, reconfigure all packages, fix missing or corrupt package files and clean the package cache. Diagnose lists broken or incomplete packages; Last Resort offers a forced removal.':
        "Manutenzione standard: update, upgrade e autoremove, correzione delle dipendenze difettose, riconfigurazione di tutti i pacchetti, riparazione dei file mancanti o corrotti e pulizia della cache. La diagnosi elenca i pacchetti difettosi o incompleti; l'ultima risorsa offre una rimozione forzata.",
    'Standard Maintenance: update, upgrade & autoremove, fix inconsistent package versions, rebuild the RPM database and clean the package cache. Diagnose shows broken or unsatisfied packages; Last Resort offers a forced removal.':
        "Manutenzione standard: update, upgrade e autoremove, correzione delle versioni incoerenti dei pacchetti, ricostruzione del database RPM e pulizia della cache. La diagnosi mostra i pacchetti difettosi o con dipendenze non soddisfatte; l'ultima risorsa offre una rimozione forzata.",
    'Standard Maintenance: update & upgrade, fix broken dependencies, rebuild the RPM database and clean the package cache. Diagnose shows broken or unsatisfied packages; Last Resort offers a forced removal.':
        "Manutenzione standard: update e upgrade, correzione delle dipendenze difettose, ricostruzione del database RPM e pulizia della cache. La diagnosi mostra i pacchetti difettosi o con dipendenze non soddisfatte; l'ultima risorsa offre una rimozione forzata.",
    'Domain check: connects live to the domains you enter (port 443) and reports the days left until the certificate expires. Local check: read-only scan of the .pem files in /etc/ssl/certs. There is also a one-click reinstall of the CA certificate bundle for when HTTPS errors hit many unrelated sites at once.':
        "Controllo dominio: si connette in tempo reale ai domini inseriti (porta 443) e indica i giorni rimanenti prima della scadenza del certificato. Controllo locale: scansione in sola lettura dei file .pem in /etc/ssl/certs. C'è anche la reinstallazione con un clic del pacchetto dei certificati CA, utile quando errori HTTPS colpiscono insieme molti siti non correlati.",
    'Scans /usr and /etc for symbolic links whose target no longer exists and sorts them into license leftovers (safe), archiso templates (expected) and everything else (review by hand). Scanning is read-only; the clean-up button deletes only the safe license leftovers and needs administrator rights.':
        'Analizza /usr e /etc alla ricerca di collegamenti simbolici il cui bersaglio non esiste più e li ordina in resti di licenze (sicuri), modelli archiso (previsti) e tutto il resto (da controllare a mano). La scansione è di sola lettura; il pulsante di pulizia elimina solo i resti di licenze sicuri e richiede diritti di amministratore.',
    'Operating system, kernel, hardware and package statistics in one place — a good thing to include in a bug report.':
        'Sistema operativo, kernel, hardware e statistiche dei pacchetti in un unico posto — utile da allegare a una segnalazione di errore.',
    'Shows failed systemd services (with a one-click reset for the usually harmless shadow.service), whether firewalld, fail2ban and apparmor are active, the UFW firewall (show rules, install and enable) and a check of the SSH root-login setting. Most checks are read-only.':
        "Mostra i servizi systemd falliti (con ripristino in un clic dello shadow.service, di solito innocuo), se firewalld, fail2ban e apparmor sono attivi, il firewall UFW (mostra regole, installa e abilita) e un controllo dell'accesso root via SSH. La maggior parte dei controlli è di sola lettura.",
    'Creates a compressed archive of important system configuration (fstab, hostname, bootloader, package-manager config …) plus a list of installed packages in the folder you choose (default: ~/pachul-backup). Only the last 5 archives are kept. No administrator rights needed.':
        'Crea un archivio compresso della configurazione di sistema importante (fstab, hostname, bootloader, configurazione del gestore pacchetti …) più un elenco dei pacchetti installati nella cartella scelta (predefinita: ~/pachul-backup). Vengono conservati solo gli ultimi 5 archivi. Non servono diritti di amministratore.',
    "Shows the build script of an AUR package before you install it, so you can see what it will do — always worth a look for unfamiliar packages. A link button in the viewer opens the package's AUR page (votes, comments, discussion).":
        "Mostra lo script di compilazione di un pacchetto AUR prima dell'installazione, così vedi cosa farà — vale sempre la pena per i pacchetti sconosciuti. Un pulsante nella finestra apre la pagina AUR del pacchetto (voti, commenti, discussione).",
    'Same as Ignore Updates, but from the Packages menu: toggles whether the selected packages are excluded from upgrades. A dialog explains the effect and asks for confirmation.':
        "Come Ignora aggiornamenti, ma dal menu Pacchetti: attiva o disattiva l'esclusione dei pacchetti selezionati dagli aggiornamenti. Una finestra spiega l'effetto e chiede conferma.",
    'Changes how a package is tracked. Explicit means installed on purpose, so it is never offered for removal as an orphan; Dependency means installed for other packages, so it shows up in Find Orphans once nothing needs it any more. Only this label changes — nothing is installed or removed.':
        'Cambia il modo in cui un pacchetto viene tracciato. Esplicito significa installato di proposito, quindi non viene mai proposto per la rimozione come orfano; Dipendenza significa installato per altri pacchetti, quindi compare in Trova orfani quando nulla ne ha più bisogno. Cambia solo questa etichetta — nulla viene installato o rimosso.',
    "Chooses the program used for AUR installs, updates and PKGBUILDs: auto-detect, pachuli (Pachul's own minimal helper), yay, paru, pikaur or none (pacman only). A missing helper can be installed right from the Preferences. “Include AUR in update checks” also looks for newer AUR versions — switch it off if checks are slow or you don't use the AUR.":
        "Sceglie il programma usato per installazioni, aggiornamenti e PKGBUILD dell'AUR: rilevamento automatico, pachuli (l'helper minimale di Pachul), yay, paru, pikaur o nessuno (solo pacman). Un helper mancante può essere installato direttamente dalle preferenze. «Includi AUR nei controlli» cerca anche versioni AUR più recenti — disattivalo se i controlli sono lenti o non usi l'AUR.",
    'If python3-apt (Debian/Ubuntu) or python3-libdnf5 (Fedora) is missing, Preferences offers to install it. It speeds up package info, listing and update checks; Pachul works without it, just more slowly. Restart Pachul afterwards.':
        'Se python3-apt (Debian/Ubuntu) o python3-libdnf5 (Fedora) manca, le preferenze propongono di installarlo. Velocizza info sui pacchetti, elenchi e controlli degli aggiornamenti; Pachul funziona anche senza, solo più lentamente. Riavvia poi Pachul.',
    'Switch Flatpak and Snap support on or off, and install or uninstall flatpak/snapd itself. When enabled, their apps appear in the sidebar and are included in searches and upgrades. Flatpak installs run without a password; Snap always needs one.':
        'Attiva o disattiva il supporto a Flatpak e Snap e installa o disinstalla flatpak/snapd stesso. Quando attivi, le loro app compaiono nella barra laterale e sono incluse in ricerche e aggiornamenti. Le installazioni Flatpak non richiedono password; Snap la richiede sempre.',
    '“Confirm before removing packages” asks before anything is uninstalled. “Check for updates on startup” and “Notify when updates are available” control the automatic update check and its desktop notification.':
        "«Conferma prima di rimuovere i pacchetti» chiede conferma prima di disinstallare qualcosa. «Controlla aggiornamenti all'avvio» e «Notifica quando sono disponibili aggiornamenti» controllano il controllo automatico e la relativa notifica sul desktop.",
    'Scans at startup for fixable problems such as failed services or no active firewall. If something is found, a summary dialog lets you open the matching tool — nothing is changed automatically. Turn it off under Preferences → Behaviour.':
        "All'avvio cerca problemi risolvibili, come servizi falliti o assenza di firewall attivo. Se trova qualcosa, un riepilogo permette di aprire lo strumento adatto — nulla viene modificato automaticamente. Si disattiva in Preferenze → Comportamento.",
    'If Timeshift or Snapper is installed, a restore point can be created before every system upgrade as a safety net.':
        'Se Timeshift o Snapper è installato, prima di ogni aggiornamento di sistema può essere creato un punto di ripristino come rete di sicurezza.',
    "“Follow System” uses the desktop's light or dark setting; “Dark Mode” switches manually (Ctrl+Shift+D toggles). Changes apply immediately.":
        "«Segui il sistema» usa l'impostazione chiara o scura del desktop; «Modalità scura» passa manualmente (Ctrl+Maiusc+D alterna). Le modifiche si applicano subito.",
    'Switches between English, German, French and Italian. The interface is rebuilt right away, no restart needed.':
        "Passa tra inglese, tedesco, francese e italiano. L'interfaccia viene ricostruita subito, senza riavvio.",
    'Start the tray icon automatically at login to see pending updates at a glance. The background service checks for updates through a systemd user timer (hourly, every 6 hours or daily), even when Pachul is closed.':
        "Avvia automaticamente l'icona nella barra di stato all'accesso per vedere a colpo d'occhio gli aggiornamenti in sospeso. Il servizio in background controlla gli aggiornamenti tramite un timer utente systemd (ogni ora, ogni 6 ore o ogni giorno), anche a Pachul chiuso.",
    'Opens this window (F1). Type in the search field at the top to find a topic quickly.':
        'Apre questa finestra (F1). Scrivi nel campo di ricerca in alto per trovare rapidamente un argomento.',
    'Search help…':
        "Cerca nell'aiuto…",
    'No matching help topics':
        'Nessun argomento di aiuto corrispondente',
    'Update Selected':
        'Aggiorna selezionati',
    'What can be updated here?':
        'Cosa si può aggiornare qui?',
    'Unignore':
        'Non ignorare più',
    'Unignore All':
        'Non ignorare più tutti',
    'Check for fixable system problems on startup':
        "Cerca all'avvio problemi di sistema risolvibili",
}.items():
    STRINGS_IT.setdefault(_k, _v)


_TABLES = {
    "de": STRINGS_DE,
    "fr": STRINGS_FR,
    "it": STRINGS_IT,
}

# Kept for backward compatibility (some code may still reference STRINGS directly)
STRINGS = STRINGS_DE
