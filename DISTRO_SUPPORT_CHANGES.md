# Multi-Distro-Unterstützung für Pachul

Diese Runde fügt Distro-Erkennung + native Paketmanager-Befehle für
Debian/Ubuntu (apt), Fedora (dnf) und openSUSE (zypper) hinzu, wie
besprochen: **nur Backend**, keine UI-/Menü-Anpassungen. Arch/pacman/AUR
läuft exakt wie vorher, unverändert.

## Neue Dateien

- **`distro.py`** — Erkennt anhand `/etc/os-release` (ID + ID_LIKE) die
  Distro-Familie (`arch` / `debian` / `fedora` / `suse`). Ableitungen wie
  Manjaro, Ubuntu/Mint, Nobara/RHEL, openSUSE Leap/Tumbleweed werden
  automatisch korrekt erkannt. Fallback über vorhandene Binaries, falls
  `/etc/os-release` fehlt/unbekannt ist.

- **`pkgmanager.py`** — Die eigentliche Befehls-/Parser-Schicht für
  apt/dnf/zypper: Install, Remove, Suche, Paketinfo, Dateien,
  Updates, verwaiste Pakete, Cache-Größe, Hold/Unhold, Config-Konflikte
  (.dpkg-dist/.rpmnew), Verlauf. `get_package_info_text()` erzeugt bewusst
  dasselbe "Key : Value"-Textformat wie `pacman -Qi`/`-Si`, damit die
  bestehende UI-Parsing-Logik unverändert funktioniert.

## Geänderte Funktionen in `backend.py`

Alle zentralen Funktionen verzweigen jetzt per `distro.is_arch()`:
`get_packages`, `get_package_info`, `get_package_files`,
`files_db_available`, `search_file_owner`, `check_updates`,
`get_orphans`, `get_package_cache_size`, `search_packages_cmd`,
`get_ignored_packages`, `get_pacnew_files` (→ Config-Konflikte),
`get_pacman_history` (Name beibehalten, deckt jetzt auch
apt/dnf/zypper-Logs ab), `get_explicit_packages`, `get_system_info`,
`_installed_fingerprint`, `_build_syncdb`. Neu: `build_hold_cmd()` /
`build_hold_cmd_bulk()` als einheitliche Schnittstelle für Hold/Ignore,
egal ob das intern eine pacman.conf-Bearbeitung oder ein direkter
`apt-mark`/`zypper addlock`-Befehl ist.

AUR/Arch-exklusive Funktionen (`get_pkgbuild`, `get_aur_rpc_version`,
`check_aur_ahead_of_repo`, `get_arch_news`, `_find_aur_helper`) geben auf
anderen Distros sauber `None`/leer zurück, statt zu crashen.

## Geänderte Stellen in `window.py` / `dialogs.py`

Alle Stellen, an denen bisher hart `pacman ...`-Befehle zusammengebaut
wurden (Install, Remove, Upgrade, Sync, Mark-Explicit/Asdeps,
Hold/Unhold, Orphan-Entfernung, Cache leeren, Paketliste importieren,
Datei-Suche-Install, Datei-Datenbank synchronisieren), rufen jetzt
`pkgmanager.*` bzw. `build_hold_cmd*()` auf, wenn `distro.is_arch()`
`False` ist. Menüs, Dialog-Layouts und Beschriftungen wurden **nicht**
angefasst (das war explizit nicht Teil dieser Runde).

## Getestet vs. ungetestet

- **Debian/Ubuntu (apt): live gegen ein echtes Ubuntu-24.04-System
  getestet** — Paketinfo, Dateiliste, installierte Paketliste,
  Verlauf, Suche, verfügbare Paketliste (`apt-cache dumpavail`, ~10-20s
  einmalig, danach 6h gecacht wie bei pacman), Updates/Orphans/Config-
  Konflikte (leer, da auf dem Testsystem nichts davon vorlag, aber ohne
  Fehler), sowie sämtliche Befehlsbau-Funktionen (install/remove/
  upgrade/hold/mark-explicit/mark-asdeps).

- **Fedora (dnf) und openSUSE (zypper): sorgfältig nach dokumentiertem
  CLI-Verhalten geschrieben, aber NICHT gegen ein echtes System
  getestet** — in dieser Sandbox stand kein Fedora/openSUSE zur
  Verfügung. Bitte auf echten Testsystemen gegenprüfen, besonders:
  - `dnf repoquery --available --qf ...` (verfügbare Paketliste)
  - `zypper packages` / `zypper search --details` / `zypper
    list-updates` (Tabellen-Spaltenformat kann je nach zypper-Version
    leicht variieren)
  - `dnf mark install/remove` (setzt eine ausreichend aktuelle
    dnf-Version voraus)

## Bewusst außerhalb des Scopes geblieben

Rein Arch-spezifische Zusatz-Tools (Repo-Manager für pacman.conf,
Mirror-Rater, GPG-Keyring-Fix, "Downgrade aus Cache", PKGBUILD-Viewer,
Arch-News-Dialog) bleiben Arch-only. Sie crashen auf anderen Distros
nicht, laufen dort aber ins Leere (kein Fehler, einfach keine
Wirkung/leere Liste) — echte Äquivalente (eigener apt-sources-Editor,
COPR/PPA/OBS-Integration usw.) wären eine eigene, größere Erweiterungsrunde.

## Runde 2: Arch-Tools im UI verbergen

Alles oben Genannte wird jetzt tatsächlich **entfernt** (nicht nur
deaktiviert/ausgegraut) auf Nicht-Arch-Systemen:

- Hauptmenü: "Manage Repositories…", "Rate Mirrors…", "View PKGBUILD
  (AUR)…" nur noch auf Arch sichtbar.
- "Ignored Packages…" / "Hold / Unhold Selected" nur sichtbar, wenn der
  Paketmanager das wirklich unterstützt (Arch, Debian, openSUSE — **nicht**
  Fedora, da dnf kein zuverlässiges eingebautes Hold hat).
- "Mark Selected as Explicit/Dependency" nur sichtbar auf Arch/Debian/
  Fedora (**nicht** openSUSE, da zypper kein einfaches Äquivalent hat).
- Sidebar: "Rate Mirrors"-Schnellzugriff nur auf Arch; die
  vorbelegten Repo-Kategorien "core/extra/multilib/aur" erscheinen nur
  auf Arch (auf anderen Distros bauen sich die echten Repo-Kategorien
  dynamisch aus den geladenen Paketen auf, wie schon zuvor für z. B.
  Chaotic-AUR).
- Detailansicht: "Downgrade"-Button nur auf Arch, "Ignore Updates"-Button
  nur wo Hold unterstützt wird.
- Einstellungen: kompletter "AUR"-Abschnitt (Helper-Auswahl, paru-Install,
  "AUR in Update-Checks einbeziehen") sowie "Arch-News vor Upgrades
  zeigen" nur auf Arch. Die Arch-News-Abfrage selbst wird auf anderen
  Distros gar nicht mehr angestoßen (auch falls die Einstellung aus
  einer alten Konfiguration noch auf "an" steht).
- System-Info: "AUR Helper" / "Foreign (AUR) Packages"-Zeilen nur auf
  Arch.
- Diverse Beschriftungen richtig gestellt: "pacman -Qi output" →
  "Raw package info", "Config Files (.pacnew)…" → "Config File
  Conflicts…", Hold-Dialog- und Ignored-Packages-Texte nennen jetzt den
  tatsächlichen Mechanismus (apt-mark/zypper lock) statt immer
  "/etc/pacman.conf".

Live gegen dieses Ubuntu-System geprüft: `_hold_supported=True`,
`_mark_reason_supported=True` (beide korrekt, da apt-mark beides kann),
`get_system_info()` enthält jetzt korrekt keine "AUR Helper"/"Foreign
(AUR) Packages"-Einträge mehr.

## Runde 3: Native Ersatz-Tools (COPR/PPA/OBS, Downgrade, Keyring-Fix)

### Downgrade
Neue Funktionen `get_downgrade_candidates()`/`build_downgrade_cmd()` in
`backend.py`, generalisieren die bisherige `get_cached_versions()`
(bleibt für Rückwärtskompatibilität erhalten). Der bestehende
Downgrade-Dialog wurde umgebaut, um beide "kind"-Arten darzustellen:
- **Debian**: `/var/cache/apt/archives` (gecachte .debs, per `dpkg-deb -f`
  ausgelesen) **plus** `apt-cache madison` (zeigt alle über aktive
  Suiten/Repos noch auflösbaren Versionen — live getestet: fand für
  `coreutils` tatsächlich 2 Versionen über `noble`/`noble-security`).
  Installation via `apt-get install --allow-downgrades pkg=version`.
- **Fedora**: `dnf --showduplicates list` + `/var/cache/dnf`-Cache;
  Installation via natives `dnf downgrade`.
- **openSUSE**: `zypper search -s` + `/var/cache/zypp/packages`-Cache;
  Installation via `zypper install --oldpackage pkg=version`.
- Der "Downgrade"-Button in der Detailansicht ist jetzt wieder auf allen
  Distros sichtbar (zeigt bei fehlenden Kandidaten einen erklärenden
  Leertext statt zu verschwinden).

### GPG-/Lock-Fix (Terminal-Banner)
Das bestehende automatische Erkennungs-/Reparatur-Banner (taucht auf,
wenn ein Terminal-Befehl mit einem Signatur- oder Lock-Fehler
fehlschlägt) wurde generalisiert:
- **GPG-Fehler-Erkennung**: eigene Regex-Muster je Familie
  (`NO_PUBKEY <id>` bei apt, generische GPG-Fehlertexte bei
  dnf/zypper). Live an einem realistischen Beispieltext getestet.
- **Fix-Befehle**: apt → Key gezielt nachladen (falls Key-ID erkannt)
  oder Basis-Keyring neu installieren; dnf → `rpm --import` bzw.
  `dnf clean all && dnf makecache`; zypper → `--gpg-auto-import-keys`.
- **Lock-Erkennung/-Fix**: je Familie eigene Lock-Datei-Pfade + Prozess-
  Check (nur entfernen, wenn nichts den Lock mehr wirklich hält) –
  apt (`dpkg`/`apt`-Locks), dnf (`rpm`-Lock), zypper (`zypp.pid`).
  Alle generierten Shell-Skripte wurden mit `bash -n` auf korrekte
  Syntax geprüft.

### Repo-Manager + COPR/PPA/OBS
Neue Funktionen in `pkgmanager.py`: `list_repos()`,
`set_repo_enabled_cmd()`, `add_third_party_cmd()`,
`remove_third_party_cmd()`, `third_party_kind_label()`,
`third_party_helper_available()`. Neuer Dialog
`show_repo_manager_native()` in `dialogs.py` (Liste aller Repos mit
An/Aus-Switch + "PPA/COPR/OBS hinzufügen/entfernen"-Bereich), ersetzt
den pacman.conf-Editor auf Nicht-Arch-Systemen. Das Menü "Manage
Repositories…" ist jetzt wieder auf allen Distros sichtbar und öffnet
automatisch den richtigen Dialog.

- **Debian/Ubuntu**: liest sowohl das klassische Einzeilen-Format
  (`sources.list`, `*.list`) als auch das neue **deb822**-Format
  (`*.sources`) — **wichtig**: Ubuntu 24.04+ nutzt deb822 standardmäßig
  für die eigenen Quellen (`ubuntu.sources`), das habe ich erst beim
  Testen auf diesem System gemerkt und die Erkennung entsprechend
  gebaut. Live getestet: korrekt 3 Einträge erkannt (Ubuntu Haupt-Repo,
  Security-Repo, plus ein Drittanbieter-Repo `nodesource.sources` — auch
  im deb822-Format!). An/Aus-Umschalten getestet (Kopie der Datei, nicht
  das echte System) — funktioniert für beide Formate korrekt.
  PPA hinzufügen/entfernen über `add-apt-repository`.
- **Fedora**: `dnf repolist --all` (Spalten-Parsing über die Header-
  Position statt naives `split()`, da Repo-Namen Leerzeichen enthalten
  können), Ein/Aus über `dnf config-manager --set-enabled/-disabled`.
  COPR über `dnf copr enable/disable/list` (braucht `dnf-plugins-core`,
  Installations-Button falls fehlt).
- **openSUSE**: `zypper repos` (Tabellen-Parsing), Ein/Aus über
  `zypper modifyrepo -e/-d`. OBS-Repo hinzufügen über
  `zypper addrepo obs://project/repo`.

**Wichtig zur Ehrlichkeit**: Der Debian/apt-Teil ist live gegen dieses
Ubuntu-System getestet (inkl. des für mich überraschenden deb822-Fundes
— ohne den Test hätte ich das klassische Format als einzigen Fall
angenommen und wäre auf modernem Ubuntu ins Leere gelaufen). Fedora/COPR
und openSUSE/OBS sind sorgfältig nach Dokumentation gebaut, aber nicht
gegen echte Systeme verifiziert — v. a. das Spalten-Parsing von
`dnf repolist --all`/`zypper repos` und ob `dnf config-manager` bei
dnf5 exakt gleich heißt, würde ich auf einer echten Maschine
gegenprüfen.

## Runde 4: Performance — python-apt/python-dnf statt CLI-Parsing

Neue Datei **`pkgmanager_native.py`**: optionale native Bindings als
reiner Beschleuniger. Jede Funktion in `pkgmanager.py` versucht zuerst
den nativen Pfad und fällt bei JEDER Exception (nicht nur ImportError)
automatisch auf den bisherigen, funktionierenden CLI-Pfad zurück — nativ
kann also bestenfalls schneller sein, nie kaputter als vorher.

### python3-apt (Debian/Ubuntu) — live getestet
Dieses Sandbox-System hat `python3-apt` installiert, daher konnte ich
den kompletten Pfad live benchmarken:

| Operation | CLI (vorher) | Nativ (jetzt) | Speedup |
|---|---|---|---|
| Alle verfügbaren Pakete (96'851) auflisten | ~19-21 s | ~2,7-5 s | ~4-7× |
| Paketinfo (einzeln) | ~50-100 ms (mehrere Subprozesse: dpkg -s/apt-cache show/apt-mark) | ~2 ms | ~30× |
| Verwaiste Pakete finden | Subprozess `apt-get --simulate autoremove` | `pkg.is_auto_removable`-Flag direkt | schneller + robuster |
| Explizit installierte Pakete | Subprozess `apt-mark showmanual` | `pkg.is_auto_installed`-Flag direkt | schneller |
| Update-Check | Subprozess + Regex auf `apt list --upgradable` | `pkg.is_upgradable`-Flag direkt | schneller + robuster (keine Locale/Format-Abhängigkeit) |

Ein `apt.Cache()`-Objekt wird als Singleton gehalten (Öffnen kostet
~2-4 s, danach sind Zugriffe fast gratis) und über `invalidate_cache()`/
`invalidate_syncdb_cache()` synchron mit den bestehenden Cache-Dateien
zurückgesetzt — getestet, dass die Invalidierung korrekt greift.

Eine Falle, auf die ich beim Testen gestoßen bin: `Version.origins`
(für den genauen Repo-Namen) ist für ein einzelnes Paket praktisch
gratis, aber beim Durchlaufen aller 96'851 Pakete allein 18 Sekunden
gekostet — deutlich mehr als alle anderen Felder zusammen. Der
Bulk-Aufbau der Paketliste lässt „repo" deshalb bewusst leer (wie
schon beim CLI-Fallback), der Einzel-Lookup für die Detailansicht nutzt
`origins` weiterhin.

### python3-dnf (Fedora) — NICHT verifiziert
Für Fedora gibt es in dieser Sandbox keine Testmöglichkeit. Der Code
ist nach der klassischen `dnf`-Python-API (dnf4/yum-Ära) geschrieben,
**aber**: Fedora 41+ nutzt standardmäßig dnf5, das eine komplett andere
Bindung (`libdnf5`) mit anderer API verwendet. Ich kann diesen
Unterschied ohne echtes Fedora-System nicht erkennen oder behandeln.
Jeder `dnf_*`-Aufruf ist so abgesichert, dass JEDE Exception auf den
CLI-Pfad zurückfällt — im schlimmsten Fall bedeutet das "keine
Beschleunigung", nie einen Absturz. Vor produktivem Einsatz unbedingt
auf einer echten Fedora-Maschine (idealerweise sowohl dnf4- als auch
dnf5-basiert) gegenprüfen, ob der native Pfad überhaupt greift oder
immer in den Fallback läuft.

### openSUSE (zypper)
Keine Änderung — es gibt keine verbreitete, stabile Python-Bindung für
libzypp, die sich für diesen Zweck eignet. Bleibt beim CLI-Pfad aus
Runde 1.

## Runde 5: dnf5 als Standard-Pfad für Fedora

Fedora 41+ nutzt standardmässig **dnf5** statt der klassischen dnf4-Linie
— und dnf5 hat eine komplett andere Python-Anbindung (`libdnf5`, nicht
`dnf`). Reihenfolge in `pkgmanager_native.py` jetzt: **dnf5 zuerst**,
dann klassisches dnf4 als Fallback für ältere Fedora/RHEL/CentOS-Systeme,
dann der CLI-Pfad als letzte Absicherung. Neue Funktionen:
`dnf5_build_available_packages()`, `dnf5_is_installed()`,
`dnf5_check_updates()`, `dnf5_package_reason()` (für "Installed
Reason" in der Paketinfo). Ein `libdnf5.base.Base()` wird — wie beim
`apt.Cache()`-Singleton — einmal lazy aufgebaut und wiederverwendet,
und über `invalidate_cache()`/`invalidate_syncdb_cache()` synchron
zurückgesetzt.

**Sehr wichtig zur Ehrlichkeit**: Das hier ist der unsicherste Teil der
gesamten Multi-Distro-Arbeit. `libdnf5`s Python-Bindings sind
SWIG-generiert aus einer noch in Entwicklung befindlichen C++-API, und
ich hatte keine Möglichkeit, sie gegen ein echtes Fedora-System zu
testen (weder dnf4 noch dnf5 sind in dieser Sandbox verfügbar). Die
Methodennamen (`base.get_repo_sack()`, `repo_sack.update_and_load_repos()`,
`PackageQuery.filter_available()`, `pkg.get_reason()` usw.) stammen aus
meinem Wissen über dokumentierte Beispiele, nicht aus verifiziertem,
lauffähigem Code. Jede einzelne `dnf5_*`-Funktion ist so abgesichert,
dass eine Exception automatisch zuerst auf dnf4, dann auf den CLI-Pfad
zurückfällt — im schlimmsten Fall bedeutet ein falscher Methodenname
also "läuft einfach über CLI weiter wie bisher", nie einen Absturz. Aber
ob der native dnf5-Pfad auf einem echten System überhaupt einmal
erfolgreich durchläuft oder immer sofort in den Fallback springt, kann
ich von hier aus nicht sagen — das würde ich vor jeder Aussage über
tatsächliche Performance-Gewinne auf Fedora zwingend auf einer echten
Maschine gegenprüfen (am besten mit einem kurzen Debug-Print oder Log,
welcher Pfad tatsächlich greift).




