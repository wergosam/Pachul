"""
PacHub — i18n.py
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
Bau ihren Text nicht automatisch neu abfragen, wird ein Sprachwechsel erst
nach einem Neustart von PacHub vollständig wirksam (siehe Hinweis im
Einstellungen-Dialog).
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
    "PacHub": "PacHub",
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
    "About PacHub": "Über PacHub",
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
    "{verb} {name}": "{name} {verb}",
    "✓ {title} completed": "✓ {title} abgeschlossen",
    "✗ {title} failed (exit {code})": "✗ {title} fehlgeschlagen (Exit {code})",
    "Sync Databases ": "Datenbanken synchronisieren",
    "System Upgrade": "Systemaktualisierung",
    "Clean Cache ": "Cache leeren",
    "Mark {name} as explicit": "{name} als explizit markieren",
    "Mark {name} as dependency": "{name} als Abhängigkeit markieren",
    "Export Package List": "Paketliste exportieren",
    "pachub-packages.txt": "pachub-pakete.txt",
    "Exported {n} packages": "{n} Pakete exportiert",
    "Export failed: {err}": "Export fehlgeschlagen: {err}",
    "Import Package List": "Paketliste importieren",
    "Could not read file: {err}": "Datei konnte nicht gelesen werden: {err}",
    "No packages found in file": "Keine Pakete in der Datei gefunden",
    "Install {n} packages": "{n} Pakete installieren",
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

    # Mirror rater
    "Mirror Options": "Spiegelserver-Optionen",
    "rate-mirrors tests all Arch mirrors and saves the fastest to /etc/pacman.d/mirrorlist":
        "rate-mirrors testet alle Arch-Spiegelserver und speichert die schnellsten in /etc/pacman.d/mirrorlist",
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
    "rate-mirrors not installed": "rate-mirrors ist nicht installiert",
    "rate-mirrors uses geo-aware routing to benchmark\nall Arch mirrors and pick the fastest ones.":
        "rate-mirrors nutzt standortbasiertes Routing, um alle Arch-Spiegelserver\nzu testen und die schnellsten auszuwählen.",
    "Install rate-mirrors": "rate-mirrors installieren",
    "Install rate-mirrors ": "rate-mirrors installieren",

    # Orphan finder
    "Orphaned Packages": "Verwaiste Pakete",
    "No Orphans Found": "Keine Waisen gefunden",
    "Your system has no orphaned packages.": "Dein System hat keine verwaisten Pakete.",
    "{n} orphaned package(s) — installed as dependencies but no longer required":
        "{n} verwaiste(s) Paket(e) — als Abhängigkeit installiert, aber nicht mehr benötigt",
    "Remove All {n} Orphans": "Alle {n} Waisen entfernen",
    "Remove All Orphans": "Alle Waisen entfernen",

    # System info
    "System Information": "Systeminformationen",
    "Gathering system info…": "Sammle Systeminformationen…",
    "System": "System",
    "OS": "Betriebssystem",
    "Kernel": "Kernel",
    "Hardware": "Hardware",
    "RAM": "RAM",
    "Disk (/)": "Festplatte (/)",
    "Packages": "Pakete",
    "Pacman": "Pacman",
    "Installed Packages": "Installierte Pakete",
    "Foreign (AUR) Packages": "Fremde (AUR) Pakete",
    "Package Cache Size": "Größe des Paket-Caches",

    # History
    "Package History": "Paketverlauf",
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
    "Check for updates and notify even when PacHub is closed, via a systemd user timer":
        "Prüft auf Updates und benachrichtigt auch, wenn PacHub geschlossen ist, über einen systemd-Benutzer-Timer",
    "Check interval": "Prüfintervall",
    "Hourly": "Stündlich",
    "Every 6 hours": "Alle 6 Stunden",
    "Daily": "Täglich",
    "Run background update checks": "Update-Prüfungen im Hintergrund ausführen",
    "Language": "Sprache",
    "Changes apply after restarting PacHub": "Änderungen wirken sich nach einem Neustart von PacHub aus",
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
    "PacHub": "PacHub",
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
    "About PacHub": "À propos de PacHub",
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
    "{verb} {name}": "{name} {verb}",
    "✓ {title} completed": "✓ {title} terminé",
    "✗ {title} failed (exit {code})": "✗ {title} a échoué (code {code})",
    "Sync Databases ": "Synchroniser les bases de données",
    "System Upgrade": "Mise à niveau du système",
    "Clean Cache ": "Vider le cache",
    "Mark {name} as explicit": "Marquer {name} comme explicite",
    "Mark {name} as dependency": "Marquer {name} comme dépendance",
    "Export Package List": "Exporter la liste des paquets",
    "pachub-packages.txt": "pachub-paquets.txt",
    "Exported {n} packages": "{n} paquets exportés",
    "Export failed: {err}": "Échec de l'exportation : {err}",
    "Import Package List": "Importer une liste de paquets",
    "Could not read file: {err}": "Impossible de lire le fichier : {err}",
    "No packages found in file": "Aucun paquet trouvé dans le fichier",
    "Install {n} packages": "Installer {n} paquets",
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

    # Mirror rater
    "Mirror Options": "Options des miroirs",
    "rate-mirrors tests all Arch mirrors and saves the fastest to /etc/pacman.d/mirrorlist":
        "rate-mirrors teste tous les miroirs Arch et enregistre les plus rapides dans /etc/pacman.d/mirrorlist",
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
    "rate-mirrors not installed": "rate-mirrors n'est pas installé",
    "rate-mirrors uses geo-aware routing to benchmark\nall Arch mirrors and pick the fastest ones.":
        "rate-mirrors utilise un routage géolocalisé pour évaluer\ntous les miroirs Arch et choisir les plus rapides.",
    "Install rate-mirrors": "Installer rate-mirrors",
    "Install rate-mirrors ": "Installer rate-mirrors",

    # Orphan finder
    "Orphaned Packages": "Paquets orphelins",
    "No Orphans Found": "Aucun orphelin trouvé",
    "Your system has no orphaned packages.": "Votre système n'a aucun paquet orphelin.",
    "{n} orphaned package(s) — installed as dependencies but no longer required":
        "{n} paquet(s) orphelin(s) — installé(s) comme dépendance(s) mais plus nécessaire(s)",
    "Remove All {n} Orphans": "Supprimer les {n} orphelins",
    "Remove All Orphans": "Supprimer tous les orphelins",

    # System info
    "System Information": "Informations système",
    "Gathering system info…": "Collecte des informations système…",
    "System": "Système",
    "OS": "Système d'exploitation",
    "Kernel": "Noyau",
    "Hardware": "Matériel",
    "RAM": "RAM",
    "Disk (/)": "Disque (/)",
    "Packages": "Paquets",
    "Pacman": "Pacman",
    "Installed Packages": "Paquets installés",
    "Foreign (AUR) Packages": "Paquets externes (AUR)",
    "Package Cache Size": "Taille du cache des paquets",

    # History
    "Package History": "Historique des paquets",
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
    "Check for updates and notify even when PacHub is closed, via a systemd user timer":
        "Vérifie les mises à jour et notifie même lorsque PacHub est fermé, via un timer systemd utilisateur",
    "Check interval": "Intervalle de vérification",
    "Hourly": "Toutes les heures",
    "Every 6 hours": "Toutes les 6 heures",
    "Daily": "Quotidien",
    "Run background update checks": "Exécuter les vérifications en arrière-plan",
    "Language": "Langue",
    "Changes apply after restarting PacHub": "Les changements s'appliquent après le redémarrage de PacHub",
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
    "PacHub": "PacHub",
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
    "About PacHub": "Informazioni su PacHub",
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
    "{verb} {name}": "{name} {verb}",
    "✓ {title} completed": "✓ {title} completato",
    "✗ {title} failed (exit {code})": "✗ {title} non riuscito (uscita {code})",
    "Sync Databases ": "Sincronizza database",
    "System Upgrade": "Aggiornamento del sistema",
    "Clean Cache ": "Pulisci cache",
    "Mark {name} as explicit": "Segna {name} come esplicito",
    "Mark {name} as dependency": "Segna {name} come dipendenza",
    "Export Package List": "Esporta elenco pacchetti",
    "pachub-packages.txt": "pachub-pacchetti.txt",
    "Exported {n} packages": "{n} pacchetti esportati",
    "Export failed: {err}": "Esportazione non riuscita: {err}",
    "Import Package List": "Importa elenco pacchetti",
    "Could not read file: {err}": "Impossibile leggere il file: {err}",
    "No packages found in file": "Nessun pacchetto trovato nel file",
    "Install {n} packages": "Installa {n} pacchetti",
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

    # Mirror rater
    "Mirror Options": "Opzioni mirror",
    "rate-mirrors tests all Arch mirrors and saves the fastest to /etc/pacman.d/mirrorlist":
        "rate-mirrors testa tutti i mirror Arch e salva i più veloci in /etc/pacman.d/mirrorlist",
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
    "rate-mirrors not installed": "rate-mirrors non installato",
    "rate-mirrors uses geo-aware routing to benchmark\nall Arch mirrors and pick the fastest ones.":
        "rate-mirrors utilizza un instradamento geolocalizzato per testare\ntutti i mirror Arch e scegliere i più veloci.",
    "Install rate-mirrors": "Installa rate-mirrors",
    "Install rate-mirrors ": "Installa rate-mirrors",

    # Orphan finder
    "Orphaned Packages": "Pacchetti orfani",
    "No Orphans Found": "Nessun orfano trovato",
    "Your system has no orphaned packages.": "Il sistema non ha pacchetti orfani.",
    "{n} orphaned package(s) — installed as dependencies but no longer required":
        "{n} pacchetto/i orfano/i — installato/i come dipendenza ma non più necessario/i",
    "Remove All {n} Orphans": "Rimuovi tutti i {n} orfani",
    "Remove All Orphans": "Rimuovi tutti gli orfani",

    # System info
    "System Information": "Informazioni di sistema",
    "Gathering system info…": "Raccolta informazioni di sistema…",
    "System": "Sistema",
    "OS": "Sistema operativo",
    "Kernel": "Kernel",
    "Hardware": "Hardware",
    "RAM": "RAM",
    "Disk (/)": "Disco (/)",
    "Packages": "Pacchetti",
    "Pacman": "Pacman",
    "Installed Packages": "Pacchetti installati",
    "Foreign (AUR) Packages": "Pacchetti esterni (AUR)",
    "Package Cache Size": "Dimensione cache pacchetti",

    # History
    "Package History": "Cronologia pacchetti",
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
    "Check for updates and notify even when PacHub is closed, via a systemd user timer":
        "Controlla gli aggiornamenti e notifica anche quando PacHub è chiuso, tramite un timer utente systemd",
    "Check interval": "Intervallo di controllo",
    "Hourly": "Ogni ora",
    "Every 6 hours": "Ogni 6 ore",
    "Daily": "Giornaliero",
    "Run background update checks": "Esegui controlli aggiornamenti in background",
    "Language": "Lingua",
    "Changes apply after restarting PacHub": "Le modifiche si applicano dopo il riavvio di PacHub",
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
    "Quit": "Esci",
}


_TABLES = {
    "de": STRINGS_DE,
    "fr": STRINGS_FR,
    "it": STRINGS_IT,
}

# Kept for backward compatibility (some code may still reference STRINGS directly)
STRINGS = STRINGS_DE
