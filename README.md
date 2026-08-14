<div align="center">

<img src="screenshots/pachul01.webp" width="72" alt="Pachul Icon"/>

# Pachul

**A modern, graphical package manager for Arch Linux, Manjaro, Debian/Ubuntu, Fedora and openSUSE**
**Ein moderner, grafischer Paketmanager für Arch Linux, Manjaro, Debian/Ubuntu, Fedora und openSUSE**

[![License: GPL v2](https://img.shields.io/badge/License-GPLv2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0)
[![Platform](https://img.shields.io/badge/Platform-Arch%20%7C%20Debian%2FUbuntu%20%7C%20Fedora%20%7C%20openSUSE-1793D1)](https://archlinux.org)
[![AUR](https://img.shields.io/badge/AUR-available-5277C3)](https://aur.archlinux.org)
[![GTK4](https://img.shields.io/badge/GTK-4-4A90D9)](https://gtk.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org)
[![Languages](https://img.shields.io/badge/i18n-EN%20%7C%20DE%20%7C%20FR%20%7C%20IT-success)](#-language--sprache)

**[English](#-english)** · **[Deutsch](#-deutsch)**

</div>

---

<a id="-english"></a>
# 🇬🇧 English

## Table of Contents

- [Overview](#overview)
- [What's New](#whats-new)
- [Screenshots](#screenshots)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Background Update Notifications](#background-update-notifications)
- [Language](#language)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Pachul is a clean, fast GTK4 / libadwaita frontend for `pacman` and the AUR — and, since the multi-distro backend was added, for `apt` (Debian/Ubuntu), `dnf`/`dnf5` (Fedora) and `zypper` (openSUSE) as well. The distro family is detected automatically, so the same app searches, installs, updates and manages packages without touching the terminal — while still giving you full, transparent control: every privileged action runs through a visible terminal panel, so you always see exactly what command is being executed.

Arch-only tools (Mirror Rater, PKGBUILD viewer, Arch news check, the `pacman.conf` repo editor) only appear on Arch/Manjaro; on other distros their native equivalents are used instead (see [What's New](#whats-new)), or they're simply hidden rather than shown greyed-out.

Pachul follows the GNOME Human Interface Guidelines and adapts automatically to your system's light or dark style.

**Repository:** [github.com/wergosam/Pachul](https://github.com/wergosam/Pachul)

---

## What's New

- **Multi-distro support** — Pachul now runs natively on **Debian/Ubuntu (`apt`)**, **Fedora (`dnf`/`dnf5`)** and **openSUSE (`zypper`)**, in addition to Arch/Manjaro. The distro family is auto-detected from `/etc/os-release`, and Arch-exclusive tools stay hidden on other distros so the UI only ever shows what's actually supported there.
- **Native package-manager bindings** — optional `python-apt` / `python3-dnf` / `python3-libdnf5` bindings are used automatically when available for a large speed boost (package-info lookups up to ~30× faster on Debian/Ubuntu), with a transparent fallback to the previous CLI-based path if anything goes wrong.
- **Downgrade on every distro** — reinstall an older cached `.deb`/`.rpm`, or on Debian/Ubuntu any version still resolvable via `apt-cache madison`, installed through each distro's native downgrade command (`apt-get install --allow-downgrades`, `dnf downgrade`, `zypper install --oldpackage`).
- **Third-party repository management** — the Repository Manager now also handles **PPAs** (Debian/Ubuntu, incl. modern deb822 `.sources` files), **COPR** (Fedora) and **OBS** repositories (openSUSE), alongside the existing `pacman.conf` editor for Arch.
- **Generalized GPG & database-lock recovery** — the one-click **Import & Retry** / **Remove Lock & Retry** fixes now recognize and repair signature and lock errors across `apt`, `dnf` and `zypper`, not just `pacman`.
- **Multi-select batch actions** — tick packages via checkbox (the selection survives search and filter changes) and install, remove, hold, or mark them all as explicit/dependency in one batch instead of one at a time.
- **File → Package search** — find out which package owns a given file path via `pacman -Fx`, with a one-click prompt to sync the files database (`pacman -Fy`) first if it's missing.
- **GPG signature-failure recovery** — Pachul recognizes unknown-key and outdated-keyring signature errors in the terminal output and offers a one-click **Import & Retry** or **Update Keyring & Retry** fix, the same way it already handles stale database locks.
- **Pre-upgrade snapshot safety net** — optionally create a Timeshift or Snapper snapshot automatically before every system upgrade (off by default, since Timeshift's rsync mode can be slow).
- **Live progress bar** — upgrade/install/remove operations show a real, percentage-based progress bar parsed straight from pacman's own output.
- **AUR package metadata** — vote count, popularity, maintainer and out-of-date status now appear in the detail panel for AUR packages, pulled live from the official AUR RPC API.
- **Chaotic-AUR support** — packages from Chaotic-AUR get their own badge and sidebar filter, alongside any other repository configured in `pacman.conf`.

See [Troubleshooting](#troubleshooting) below for the database-lock and GPG-signature fixes in more detail.

---

## Screenshots

<table>
<tr>
<td align="center">
<img src="screenshots/pachul01.webp" alt="Pachul – Package Search" width="520"/><br/>
<sub>Deutsch</sub>
</td>
<td align="center">
<img src="screenshots/pachul02.webp" alt="Pachul – Tools Menu" width="520"/><br/>
<sub>Englisch</sub>
</td>
</tr>
<tr>
<td align="center">
<img src="screenshots/pachul03.webp" alt="Pachul – Package Search" width="520"/><br/>
<sub>Francais</sub>
</td>
<td align="center">
<img src="screenshots/pachul04.webp" alt="Pachul – Tools Menu" width="520"/><br/>
<sub>Italian</sub>
</td>
</tr>
</table>

---

## Features

### Package management
- **Multi-distro backend** — Arch/Manjaro (`pacman`/AUR), Debian/Ubuntu (`apt`), Fedora (`dnf`/`dnf5`) and openSUSE (`zypper`), auto-detected; optional native bindings (`python-apt`, `python3-dnf`, `python3-libdnf5`) speed things up further where available
- **Search** official repositories and the AUR simultaneously, with live result counts
- **Browse** packages by repository: `core`, `extra`, `multilib`, `aur`, `chaotic-aur`, and any other repo configured in `pacman.conf` — each gets its own sidebar filter and badge automatically
- **Installed packages** — view, filter and manage everything on your system
- **AUR / Foreign** packages tracked separately, with source clearly badged
- **AUR package metadata** — vote count, popularity, maintainer and out-of-date status, pulled live from the AUR RPC API and shown right in the detail panel
- **Update manager** — see all available updates at a glance and upgrade in one click, or one at a time, with a live percentage progress bar during the operation
- **Multi-select batch actions** — tick packages via checkbox and install, remove, hold, or mark them all as explicit/dependency in one batch; the selection survives search and filter changes
- **Downgrade** — reinstall an older cached version straight from `/var/cache/pacman/pkg`
- **Detail panel** — description, dependencies, size, install reason, build/install dates, and full `pacman -Qi` raw output for every package

### Tools
- Sync Databases (`F5`)
- Check for Updates (`Strg+U` / `Ctrl+U`)
- **File → Package Search** — find out which package owns a given file path, via `pacman -Fx` (offers a one-click files-database sync if it's missing)
- **Rate Mirrors** — geo-aware ranking via `rate-mirrors`, with sort order, HTTPS-only filter, automatic backup and configurable mirror count
- Find Orphans — bulk-remove packages that are no longer required by anything
- Clean Cache
- Manage Repositories — inspect and toggle enabled repos; edit `pacman.conf` directly on Arch, or add/remove **PPAs** (Debian/Ubuntu), **COPR** (Fedora) and **OBS repositories** (openSUSE) on other distros
- View / Merge Config Files (`.pacnew` / `.pacsave`) with a side-by-side diff view
- Package History
- System Info — OS, kernel, hardware, package counts and cache size at a glance
- Export / Import Package Lists — great for reproducing a setup on a new machine
- View PKGBUILD (AUR) before installing
- Hold / Unhold Selected Packages (via `IgnorePkg`)
- Mark Selected as Explicit or as Dependency
- Arch Linux news check before system upgrades, so you never miss a manual-intervention notice

### Safety & recovery
- **Pre-upgrade snapshots** — optionally create a Timeshift or Snapper snapshot automatically before every system upgrade, as a safety net if something goes wrong (off by default)
- **GPG signature-failure recovery** — recognizes unknown-key and outdated-keyring errors and offers a one-click **Import & Retry** or **Update Keyring & Retry** fix
- **Stale database-lock recovery** — detects a locked pacman database (`db.lck`), confirms (via `fuser`) nothing is genuinely still using it, and offers a one-click **Remove Lock & Retry** fix
- Confirmation dialogs before destructive actions (configurable)

### Quality of life
- **Background update checks** — an optional `systemd --user` timer checks for updates and sends a desktop notification even while Pachul is closed
- **Multi-language interface** — English, German, French and Italian, switchable in Preferences
- **Keyboard shortcuts** for all common actions
- Light and dark theme support, following your system style automatically

---

## Installation

### From the AUR (Arch / Manjaro)

```bash
yay -S pachul
```

### Manual (from source, any supported distro)

Works the same way on Arch/Manjaro, Debian/Ubuntu, Fedora and openSUSE — Pachul detects the distro family automatically at startup:

```bash
git clone https://github.com/wergosam/Pachul.git
cd Pachul
python3 app.py
```

**Dependencies:**

| Package | Purpose |
|---------|---------|
| `python` ≥ 3.10 | Runtime |
| `python-gobject` | GTK4 / Adwaita Python bindings |
| `gtk4` | GUI toolkit |
| `libadwaita` | GNOME-style widgets and theming |
| `pacman` (Arch) / `apt` (Debian, Ubuntu) / `dnf` (Fedora) / `zypper` (openSUSE) | Package backend, whichever matches your distro |
| `yay`, `paru` or `pikaur` | AUR support on Arch (optional, auto-detected) |
| `python-apt` / `python3-dnf` or `python3-libdnf5` | Optional native bindings for faster package operations on Debian/Ubuntu or Fedora (falls back to CLI automatically if absent) |
| `rate-mirrors` | Mirror ranking on Arch (optional) |
| `timeshift` or `snapper` | Pre-upgrade snapshot safety net (optional, either one) |
| `systemd` | Background update-check timer (optional) |

---

## Usage

| Action | Shortcut |
|--------|----------|
| Focus Search | `Strg+F` / `Ctrl+F` |
| Sync Databases | `F5` |
| Refresh List | `Strg+R` / `Ctrl+R` |
| Check for Updates | `Strg+U` / `Ctrl+U` |
| Preferences | `Strg+,` / `Ctrl+,` |
| Keyboard Shortcuts | `Strg+?` / `Ctrl+?` |
| Quit | `Strg+Q` / `Ctrl+Q` |

---

## Background Update Notifications

Enable **Run background update checks** in Preferences to install a `systemd --user` timer (`pachul-update-check`). It runs headlessly on a schedule (no GTK dependency in this code path) and sends a desktop notification via `notify-send` when updates are available — even if Pachul itself isn't running.

The check interval — **hourly**, **every 6 hours**, or **daily** — is configurable in Preferences alongside the toggle.

### Tray icon

For a persistent, always-visible indicator instead of (or alongside) the popup notification, `pachul-tray` shows a system-tray icon reflecting the current update status — the normal Pachul icon when the system is up to date, or a small update-count badge when updates are pending. It starts automatically at login via an autostart entry installed with the package, and its own menu lets you check now, open Pachul, or quit it. It re-checks on the same interval configured above.

Requires `libayatana-appindicator` (optional dependency — install with `sudo pacman -S libayatana-appindicator` if the icon doesn't appear).

---

## Language

Pachul currently ships with **English, German, French and Italian** translations, covering the entire interface: menus, dialogs, toasts, and terminal-panel messages.

Change the interface language under **Preferences → Language**. The choice is saved immediately; the change takes full effect after restarting Pachul.

---

## Project Structure

```
pachul/
├── app.py          # Adw.Application entry point, GActions & accelerators
├── window.py       # Main window: sidebar, list view, detail panel, search page
├── dialogs.py      # Secondary dialogs (repos, mirrors, orphans, history,
│                    #   downgrade, PKGBUILD, pacdiff, preferences, shortcuts, news)
├── models.py       # GObject package model, virtualized ListView, sidebar rows
├── backend.py      # pacman / AUR integration, settings, systemd timer helpers
├── distro.py       # Distro-family detection (Arch / Debian / Fedora / openSUSE)
├── pkgmanager.py   # CLI-based apt / dnf / zypper command & parser layer
├── pkgmanager_native.py  # Optional native bindings (python-apt, python3-dnf/dnf5) with CLI fallback
├── notifier.py     # Headless entry point for the systemd background timer
├── styles.py       # Application-wide CSS
├── icons.py        # Icon theme handling
├── i18n.py         # Dictionary-based translations (EN / DE / FR / IT)
├── screenshots/    # README assets
└── requirements.txt
```

---

## Troubleshooting

- **No AUR results / AUR actions fail** — install `yay`, `paru`, or `pikaur`, or set the helper explicitly in Preferences → AUR Helper.
- **Background notifications never appear** — check the timer is enabled in Preferences, and that `notify-send` (usually part of `libnotify`) is installed.
- **Mirror rating tool missing** — install `rate-mirrors` from the AUR; Pachul offers a one-click install button when it's absent.
- **Language doesn't fully change** — some UI elements are only re-translated after a full restart of Pachul; this is expected.
- **"Failed to lock database" / `db.lck` errors, especially right after every single operation** — usually caused by another package-management daemon running alongside Pachul and briefly re-locking the same database (commonly PackageKit, or on Manjaro, `pamac-daemon` together with its tray icon). Pachul offers an automatic **Remove Lock & Retry** fix for one-off cases, but if it keeps recurring, disable the conflicting service for good, e.g.:
  ```bash
  sudo systemctl mask pamac-daemon
  ```
  and disable its tray-icon autostart if you use Pachul as your primary package manager. To confirm what's actually holding the lock at the moment it happens, run `sudo fuser -v /var/lib/pacman/db.lck`.

Found a bug that isn't covered here? Please [open an issue](https://github.com/wergosam/Pachul/issues).

---

## Contributing

Pull requests are welcome. For major changes, please [open an issue](https://github.com/wergosam/Pachul/issues) first to discuss what you'd like to change.

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

New UI strings should be added to all four language tables in `i18n.py` (`STRINGS_DE`, `STRINGS_FR`, `STRINGS_IT`) to keep translations complete.

---

## License

This project is licensed under the **GNU General Public License v2.0** — see the [LICENSE](https://github.com/wergosam/Pachul/blob/main/LICENSE) file for details.

---

<div align="center">

[⬆ Back to top](#pachul)

</div>

<br>

---

<a id="-deutsch"></a>
# 🇩🇪 Deutsch

## Inhaltsverzeichnis

- [Übersicht](#übersicht)
- [Neuigkeiten](#neuigkeiten)
- [Screenshots](#screenshots-1)
- [Funktionen](#funktionen)
- [Installation](#installation-1)
- [Verwendung](#verwendung)
- [Hintergrund-Update-Benachrichtigungen](#hintergrund-update-benachrichtigungen)
- [Sprache](#sprache)
- [Projektstruktur](#projektstruktur)
- [Fehlerbehebung](#fehlerbehebung)
- [Mitwirken](#mitwirken)
- [Lizenz](#lizenz-1)

---

## Übersicht

Pachul ist ein schlankes, schnelles GTK4- / libadwaita-Frontend für `pacman` und das AUR. Es ermöglicht das Suchen, Installieren, Aktualisieren und Verwalten von Paketen, ohne das Terminal anzufassen — und behält dabei volle, transparente Kontrolle: Jede privilegierte Aktion läuft über ein sichtbares Terminal-Panel, sodass du immer genau siehst, welcher Befehl ausgeführt wird.

Pachul folgt den GNOME-Gestaltungsrichtlinien (HIG) und passt sich automatisch an den hellen oder dunklen Stil deines Systems an.

**Repository:** [github.com/wergosam/Pachul](https://github.com/wergosam/Pachul)

---

## Neuigkeiten

- **Multi-Distro-Unterstützung** — Pachul läuft jetzt nativ auch auf **Debian/Ubuntu (`apt`)**, **Fedora (`dnf`/`dnf5`)** und **openSUSE (`zypper`)**, zusätzlich zu Arch/Manjaro. Die Distro-Familie wird automatisch anhand von `/etc/os-release` erkannt; rein Arch-spezifische Werkzeuge bleiben auf anderen Distros verborgen, sodass die Oberfläche immer nur das zeigt, was dort tatsächlich unterstützt wird.
- **Native Paketmanager-Anbindung** — optionale `python-apt`- / `python3-dnf`- / `python3-libdnf5`-Bindings werden automatisch genutzt, wenn vorhanden, und bringen einen deutlichen Geschwindigkeitsschub (Paketinfo-Abfragen auf Debian/Ubuntu bis zu ~30× schneller), mit transparentem Rückfall auf den bisherigen CLI-Pfad, falls etwas schiefgeht.
- **Downgrade auf jeder Distro** — eine ältere zwischengespeicherte `.deb`/`.rpm`-Version neu installieren, auf Debian/Ubuntu zusätzlich jede über `apt-cache madison` noch auflösbare Version, jeweils über den nativen Downgrade-Befehl der jeweiligen Distro (`apt-get install --allow-downgrades`, `dnf downgrade`, `zypper install --oldpackage`).
- **Drittanbieter-Repository-Verwaltung** — der Repository-Manager beherrscht jetzt auch **PPAs** (Debian/Ubuntu, inkl. moderner deb822-`.sources`-Dateien), **COPR** (Fedora) und **OBS-Repositories** (openSUSE), zusätzlich zum bestehenden `pacman.conf`-Editor für Arch.
- **Verallgemeinerte GPG- und Datenbank-Sperre-Behebung** — die Ein-Klick-Fixes „Importieren & erneut versuchen" / „Sperre entfernen & erneut versuchen" erkennen und beheben Signatur- und Sperrfehler jetzt auch bei `apt`, `dnf` und `zypper`, nicht nur bei `pacman`.
- **Mehrfachauswahl-Sammelaktionen** — Pakete per Checkbox ankreuzen (die Auswahl bleibt auch bei Such-/Filteränderungen erhalten) und alle zusammen installieren, entfernen, sperren oder als explizit/Abhängigkeit markieren, statt einzeln.
- **Datei-→-Paket-Suche** — herausfinden, welches Paket einen bestimmten Dateipfad besitzt (über `pacman -Fx`), mit Ein-Klick-Angebot zum Synchronisieren der Dateien-Datenbank (`pacman -Fy`), falls diese fehlt.
- **GPG-Signaturfehler-Behebung** — Pachul erkennt unbekannte Schlüssel und veraltete Keyring-Signaturfehler in der Terminal-Ausgabe und bietet einen Ein-Klick-Fix **„Importieren & erneut versuchen"** oder **„Keyring aktualisieren & erneut versuchen"** an — genauso wie bereits bei veralteten Datenbank-Sperren.
- **Snapshot-Sicherheitsnetz vor Upgrades** — optional automatisch einen Timeshift- oder Snapper-Snapshot vor jedem Systemupgrade erstellen (standardmässig deaktiviert, da Timeshifts Rsync-Modus langsam sein kann).
- **Live-Fortschrittsbalken** — Upgrade-/Installations-/Entfernungsvorgänge zeigen jetzt einen echten, prozentbasierten Fortschrittsbalken, direkt aus der Ausgabe von Pacman selbst ausgelesen.
- **AUR-Paketmetadaten** — Stimmenzahl, Popularität, Maintainer und Veraltet-Status erscheinen jetzt in der Detailansicht für AUR-Pakete, live über die offizielle AUR-RPC-API abgerufen.
- **Chaotic-AUR-Unterstützung** — Pakete aus Chaotic-AUR erhalten ein eigenes Badge und einen eigenen Filter in der Seitenleiste, wie jedes andere in `pacman.conf` konfigurierte Repository auch.

Siehe [Fehlerbehebung](#fehlerbehebung) weiter unten für Details zu den Datenbank-Sperre- und GPG-Signatur-Fixes.

---

## Screenshots

<table>
<tr>
<td align="center">
<img src="screenshots/pachul01.webp" alt="Pachul – Paketsuche" width="520"/><br/>
<sub><b>Paketsuche</b> — Offizielle Repos und AUR durchsuchen, mit Live-Paketzahlen</sub>
</td>
<td align="center">
<img src="screenshots/pachul02.webp" alt="Pachul – Werkzeuge-Menü" width="520"/><br/>
<sub><b>Werkzeuge-Menü</b> — Datenbanken synchronisieren, Spiegelserver bewerten, Konfigurationsdateien verwalten und mehr</sub>
</td>
</tr>
</table>

---

## Funktionen

### Paketverwaltung
- **Multi-Distro-Backend** — Arch/Manjaro (`pacman`/AUR), Debian/Ubuntu (`apt`), Fedora (`dnf`/`dnf5`) und openSUSE (`zypper`), automatisch erkannt; optionale native Bindings (`python-apt`, `python3-dnf`, `python3-libdnf5`) beschleunigen zusätzlich, wo verfügbar
- **Suche** gleichzeitig in offiziellen Repositorien und im AUR, mit Live-Trefferzahl
- **Durchsuchen** nach Repository: `core`, `extra`, `multilib`, `aur`, `chaotic-aur` sowie jedem weiteren, in `pacman.conf` konfigurierten Repository — jedes erhält automatisch einen eigenen Filter und ein eigenes Badge in der Seitenleiste
- **Installierte Pakete** — alles auf deinem System ansehen, filtern und verwalten
- **AUR / Fremde** Pakete werden separat erfasst, mit klar erkennbarer Herkunfts-Badge
- **AUR-Paketmetadaten** — Stimmenzahl, Popularität, Maintainer und Veraltet-Status, live über die AUR-RPC-API abgerufen und direkt in der Detailansicht angezeigt
- **Update-Verwaltung** — alle verfügbaren Updates auf einen Blick, mit einem Klick alle oder einzeln aktualisieren, mit Live-Fortschrittsbalken in Prozent während des Vorgangs
- **Mehrfachauswahl-Sammelaktionen** — Pakete per Checkbox ankreuzen und alle zusammen installieren, entfernen, sperren oder als explizit/Abhängigkeit markieren; die Auswahl bleibt auch bei Such-/Filteränderungen erhalten
- **Downgrade** — eine ältere zwischengespeicherte Version direkt aus `/var/cache/pacman/pkg` neu installieren
- **Detailansicht** — Beschreibung, Abhängigkeiten, Größe, Installationsgrund, Build-/Installationsdatum sowie die vollständige `pacman -Qi`-Rohausgabe zu jedem Paket

### Werkzeuge
- Datenbanken synchronisieren (`F5`)
- Auf Updates prüfen (`Strg+U`)
- **Datei-→-Paket-Suche** — herausfinden, welches Paket einen bestimmten Dateipfad besitzt, über `pacman -Fx` (bietet bei fehlender Dateien-Datenbank einen Ein-Klick-Sync an)
- **Spiegelserver bewerten** — standortbasiertes Ranking über `rate-mirrors`, mit Sortieroptionen, Nur-HTTPS-Filter, automatischer Sicherung und einstellbarer Anzahl der Spiegelserver
- Waisen finden — nicht mehr benötigte Pakete gesammelt entfernen
- Cache leeren
- Repositorien verwalten — aktivierte Repos einsehen und umschalten; unter Arch `pacman.conf` direkt bearbeiten, auf anderen Distros **PPAs** (Debian/Ubuntu), **COPR** (Fedora) und **OBS-Repositories** (openSUSE) hinzufügen/entfernen
- Konfigurationsdateien anzeigen/zusammenführen (`.pacnew` / `.pacsave`) mit Diff-Ansicht nebeneinander
- Paketverlauf
- Systeminformationen — Betriebssystem, Kernel, Hardware, Paketanzahl und Cache-Größe auf einen Blick
- Paketlisten exportieren/importieren — praktisch, um ein Setup auf einem neuen Rechner zu reproduzieren
- PKGBUILD (AUR) vor der Installation ansehen
- Ausgewählte Pakete sperren/entsperren (über `IgnorePkg`)
- Auswahl als explizit oder als Abhängigkeit markieren
- Arch-Linux-News-Prüfung vor Systemaktualisierungen, damit manuelle Eingriffe nie übersehen werden

### Sicherheit & Wiederherstellung
- **Snapshots vor Upgrades** — optional automatisch einen Timeshift- oder Snapper-Snapshot vor jedem Systemupgrade erstellen, als Sicherheitsnetz falls etwas schiefgeht (standardmässig deaktiviert)
- **GPG-Signaturfehler-Behebung** — erkennt unbekannte Schlüssel und veraltete Keyring-Fehler und bietet einen Ein-Klick-Fix „Importieren & erneut versuchen" oder „Keyring aktualisieren & erneut versuchen" an
- **Behebung veralteter Datenbank-Sperren** — erkennt eine gesperrte Pacman-Datenbank (`db.lck`), bestätigt per `fuser`, dass wirklich nichts mehr darauf zugreift, und bietet einen Ein-Klick-Fix „Sperre entfernen & erneut versuchen" an
- Bestätigungsdialoge vor destruktiven Aktionen (einstellbar)

### Komfortfunktionen
- **Hintergrund-Update-Prüfung** — ein optionaler `systemd --user`-Timer prüft auf Updates und sendet eine Desktop-Benachrichtigung, auch wenn Pachul geschlossen ist
- **Mehrsprachige Oberfläche** — Englisch, Deutsch, Französisch und Italienisch, umschaltbar in den Einstellungen
- **Tastenkombinationen** für alle gängigen Aktionen
- Unterstützung für helles und dunkles Design, folgt automatisch dem Systemstil

---

## Installation

### Aus dem AUR (Arch / Manjaro)

```bash
yay -S pachul
```

### Manuell (aus dem Quellcode, auf jeder unterstützten Distro)

Funktioniert gleichermassen auf Arch/Manjaro, Debian/Ubuntu, Fedora und openSUSE — Pachul erkennt die Distro-Familie beim Start automatisch:

```bash
git clone https://github.com/wergosam/Pachul.git
cd Pachul
python3 app.py
```

**Abhängigkeiten:**

| Paket | Zweck |
|---------|---------|
| `python` ≥ 3.10 | Laufzeitumgebung |
| `python-gobject` | GTK4-/Adwaita-Python-Bindings |
| `gtk4` | GUI-Toolkit |
| `libadwaita` | GNOME-typische Widgets und Theming |
| `pacman` (Arch) / `apt` (Debian, Ubuntu) / `dnf` (Fedora) / `zypper` (openSUSE) | Paket-Backend, je nach Distro |
| `yay`, `paru` oder `pikaur` | AUR-Unterstützung auf Arch (optional, automatisch erkannt) |
| `python-apt` / `python3-dnf` bzw. `python3-libdnf5` | Optionale native Bindings für schnellere Paketoperationen auf Debian/Ubuntu bzw. Fedora (fällt automatisch auf CLI zurück, falls nicht vorhanden) |
| `rate-mirrors` | Spiegelserver-Bewertung auf Arch (optional) |
| `timeshift` oder `snapper` | Snapshot-Sicherheitsnetz vor Upgrades (optional, eines von beiden) |
| `systemd` | Timer für Hintergrund-Update-Prüfung (optional) |

---

## Verwendung

| Aktion | Tastenkombination |
|--------|----------|
| Suche fokussieren | `Strg+F` |
| Datenbanken synchronisieren | `F5` |
| Liste aktualisieren | `Strg+R` |
| Auf Updates prüfen | `Strg+U` |
| Einstellungen | `Strg+,` |
| Tastenkombinationen | `Strg+?` |
| Beenden | `Strg+Q` |

---

## Hintergrund-Update-Benachrichtigungen

Aktiviere **Update-Prüfungen im Hintergrund ausführen** in den Einstellungen, um einen `systemd --user`-Timer (`pachul-update-check`) einzurichten. Dieser läuft nach Zeitplan headless (in diesem Codepfad ohne GTK-Abhängigkeit) und sendet über `notify-send` eine Desktop-Benachrichtigung, sobald Updates verfügbar sind — auch wenn Pachul selbst nicht läuft.

Das Prüfintervall — **stündlich**, **alle 6 Stunden** oder **täglich** — lässt sich zusammen mit dem Schalter in den Einstellungen konfigurieren.

### Tray-Icon

Für eine dauerhaft sichtbare Anzeige statt (oder zusätzlich zu) der Popup-Benachrichtigung zeigt `pachul-tray` ein Tray-Icon mit dem aktuellen Update-Status — das normale Pachul-Icon, wenn das System aktuell ist, oder ein Icon mit kleinem Zähler, wenn Updates anstehen. Es startet automatisch bei der Anmeldung über einen mit dem Paket installierten Autostart-Eintrag; über sein eigenes Menü lässt sich manuell prüfen, Pachul öffnen oder beenden. Es prüft im selben Intervall wie oben konfiguriert.

Benötigt `libayatana-appindicator` (optionale Abhängigkeit — mit `sudo pacman -S libayatana-appindicator` nachinstallieren, falls das Icon nicht erscheint).

---

## Sprache

Pachul wird aktuell mit Übersetzungen in **Englisch, Deutsch, Französisch und Italienisch** ausgeliefert und deckt die gesamte Oberfläche ab: Menüs, Dialoge, Toasts und Terminal-Panel-Meldungen.

Die Sprache lässt sich unter **Einstellungen → Sprache** ändern. Die Auswahl wird sofort gespeichert; die Änderung wirkt sich vollständig nach einem Neustart von Pachul aus.

---

## Projektstruktur

```
pachul/
├── app.py          # Adw.Application-Einstiegspunkt, GActions & Tastenkürzel
├── window.py       # Hauptfenster: Seitenleiste, Listenansicht, Detailansicht, Suchseite
├── dialogs.py      # Alle weiteren Dialoge (Repos, Spiegelserver, Waisen, Verlauf,
│                    #   Downgrade, PKGBUILD, Pacdiff, Einstellungen, Kurzbefehle, News)
├── models.py       # GObject-Paketmodell, virtualisierte ListView, Seitenleisten-Zeilen
├── backend.py      # pacman-/AUR-Integration, Einstellungen, systemd-Timer-Hilfsfunktionen
├── distro.py       # Distro-Familien-Erkennung (Arch / Debian / Fedora / openSUSE)
├── pkgmanager.py   # CLI-basierte Befehls-/Parser-Schicht für apt / dnf / zypper
├── pkgmanager_native.py  # Optionale native Bindings (python-apt, python3-dnf/dnf5) mit CLI-Fallback
├── notifier.py     # Headless-Einstiegspunkt für den systemd-Hintergrund-Timer
├── styles.py       # Anwendungsweites CSS
├── icons.py        # Icon-Theme-Verwaltung
├── i18n.py         # Wörterbuch-basierte Übersetzungen (EN / DE / FR / IT)
├── screenshots/    # README-Grafiken
└── requirements.txt
```

---

## Fehlerbehebung

- **Keine AUR-Ergebnisse / AUR-Aktionen schlagen fehl** — installiere `yay`, `paru` oder `pikaur`, oder lege den Helfer explizit unter Einstellungen → AUR-Helfer fest.
- **Hintergrund-Benachrichtigungen erscheinen nie** — prüfe, ob der Timer in den Einstellungen aktiviert ist und ob `notify-send` (üblicherweise Teil von `libnotify`) installiert ist.
- **Werkzeug zur Spiegelserver-Bewertung fehlt** — installiere `rate-mirrors` aus dem AUR; Pachul bietet dafür einen Ein-Klick-Installationsbutton an, falls es fehlt.
- **Sprache wechselt nicht vollständig** — manche UI-Elemente werden erst nach einem vollständigen Neustart von Pachul neu übersetzt; das ist beabsichtigt.
- **„Datenbank kann nicht gesperrt werden" / `db.lck`-Fehler, besonders nach jedem einzelnen Vorgang** — meist verursacht durch einen weiteren, parallel laufenden Paketverwaltungs-Dienst, der dieselbe Datenbank kurz danach erneut sperrt (häufig PackageKit, oder unter Manjaro `pamac-daemon` zusammen mit dessen Tray-Icon). Pachul bietet für Einzelfälle einen automatischen Fix **„Sperre entfernen & erneut versuchen"** an — tritt es aber wiederholt auf, den störenden Dienst dauerhaft deaktivieren, z. B.:
  ```bash
  sudo systemctl mask pamac-daemon
  ```
  und dessen Tray-Icon-Autostart deaktivieren, falls du Pachul als deinen Haupt-Paketmanager nutzt. Um herauszufinden, was die Sperre im konkreten Moment tatsächlich hält, hilft `sudo fuser -v /var/lib/pacman/db.lck`.

Einen Fehler gefunden, der hier nicht behandelt wird? Bitte [ein Issue eröffnen](https://github.com/wergosam/Pachul/issues).

---

## Mitwirken

Pull Requests sind willkommen. Bei größeren Änderungen bitte zuerst [ein Issue eröffnen](https://github.com/wergosam/Pachul/issues), um das gewünschte Vorhaben zu besprechen.

1. Repository forken
2. Feature-Branch erstellen: `git checkout -b feature/my-feature`
3. Änderungen committen: `git commit -m 'Add my feature'`
4. Branch pushen: `git push origin feature/my-feature`
5. Pull Request eröffnen

Neue UI-Texte sollten in allen vier Sprachtabellen in `i18n.py` (`STRINGS_DE`, `STRINGS_FR`, `STRINGS_IT`) ergänzt werden, damit die Übersetzungen vollständig bleiben.

---

## Lizenz

Dieses Projekt steht unter der **GNU General Public License v2.0** — siehe die [LICENSE](https://github.com/wergosam/Pachul/blob/main/LICENSE)-Datei für Details.

---

<div align="center">

[⬆ Nach oben](#pachul)

</div>

<br>

---

<div align="center">
Made for the Arch Linux community 🐧 · Gemacht für die Arch-Linux-Community 🐧
</div>
