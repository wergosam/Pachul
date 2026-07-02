<div align="center">

<img src="screenshots/pachub01.webp" width="64" alt="PacHub Icon"/>

# PacHub

**A modern, graphical package manager for Arch Linux and Manjaro**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform](https://img.shields.io/badge/Platform-Arch%20%7C%20Manjaro-1793D1)](https://archlinux.org)
[![AUR](https://img.shields.io/badge/AUR-available-5277C3)](https://aur.archlinux.org)

</div>

---

## Overview

PacHub is a clean, fast GTK4 / libadwaita frontend for `pacman` and the AUR. It lets you search, install, update and manage packages without touching the terminal — while still giving you full control over repositories, orphans, mirrors and cache. PacHub follows the GNOME HIG and adapts to your system's light or dark style automatically.

---

## Screenshots

<table>
<tr>
<td align="center">
<img src="screenshots/pachub01.webp" alt="PacHub – Package Search" width="520"/><br/>
<sub><b>Package Search</b> — Browse official repos and AUR with live package counts</sub>
</td>
<td align="center">
<img src="screenshots/pachub02.webp" alt="PacHub – Tools Menu" width="520"/><br/>
<sub><b>Tools Menu</b> — Sync databases, rate mirrors, manage config files and more</sub>
</td>
</tr>
</table>

---

## Features

- **Search** official repositories and the AUR simultaneously
- **Browse** packages by repository: `core`, `extra`, `multilib`, `aur`, `chaotic-aur`
- **Installed packages** — view, filter and manage what's on your system
- **AUR / Foreign** packages tracked separately
- **Update manager** — see available updates at a glance and upgrade in one click
- **Downgrade** — reinstall an older cached version straight from `/var/cache/pacman/pkg`
- **Tools**
  - Sync Databases (`F5`)
  - Check for Updates (`Strg+U`)
  - Rate Mirrors — geo-aware ranking via `rate-mirrors`, with sort order, protocol filter, backup and mirror-count options
  - Find Orphans
  - Clean Cache
  - Manage Repositories
  - View / Merge Config Files (`.pacnew` / `.pacsave`) with side-by-side diff
  - Package History
  - System Info
  - Export / Import Package Lists
  - View PKGBUILD (AUR)
  - Hold / Unhold Selected Packages
  - Mark as Explicit or Dependency
  - Arch Linux news check before system upgrades
- **Background update checks** — an optional `systemd --user` timer checks for updates and sends a desktop notification even while PacHub is closed
- **Multi-language interface** — English, German, French and Italian, switchable in Preferences
- **Keyboard shortcuts** for all common actions
- Light and dark theme support (follows the system style)

---

## Installation

### From the AUR

```bash
yay -S pachub
```

### Manual (from source)

```bash
git clone https://github.com/wergosam/pachub.git
cd pachub
python app.py
```

**Dependencies:**

| Package | Purpose |
|---------|---------|
| `python` ≥ 3.10 | Runtime |
| `python-gobject` | GTK4 / Adwaita Python bindings |
| `gtk4` | GUI toolkit |
| `libadwaita` | GNOME-style widgets and theming |
| `pacman` | Package backend |
| `yay`, `paru` or `pikaur` | AUR support (optional, auto-detected) |
| `rate-mirrors` | Mirror ranking (optional) |
| `systemd` | Background update-check timer (optional) |

---

## Usage

| Action | Shortcut |
|--------|----------|
| Focus Search | `Strg+F` |
| Sync Databases | `F5` |
| Refresh List | `Strg+R` |
| Check for Updates | `Strg+U` |
| Preferences | `Strg+,` |
| Keyboard Shortcuts | `Strg+?` |
| Quit | `Strg+Q` |

### Background update notifications

Enable **Run background update checks** in Preferences to install a `systemd --user` timer (`pachub-update-check`). It periodically runs headlessly (no GTK dependency in this path) and sends a desktop notification via `notify-send` when updates are available — even if PacHub itself isn't running. The check interval (hourly / every 6 hours / daily) is also configurable in Preferences.

### Language

PacHub currently ships with **English, German, French and Italian** translations. Change the interface language under Preferences → Language; the change is saved immediately and takes full effect after restarting PacHub.

---

## Project Structure

```
pachub/
├── app.py         # Adw.Application entry point, GActions & accelerators
├── window.py      # Main window: sidebar, list view, detail panel, search page
├── dialogs.py      # All secondary dialogs (repos, mirrors, orphans, history,
│                    #   downgrade, PKGBUILD, pacdiff, preferences, shortcuts, news)
├── models.py       # GObject package model, virtualized ListView, sidebar rows
├── backend.py      # pacman / AUR integration, settings, systemd timer helpers
├── notifier.py     # Headless entry point for the systemd background timer
├── styles.py       # Application-wide CSS
├── i18n.py         # Dictionary-based translations (EN / DE / FR / IT)
├── screenshots/    # README assets
└── requirements.txt
```

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

New UI strings should be added to all four language tables in `i18n.py` (`STRINGS_DE`, `STRINGS_FR`, `STRINGS_IT`) to keep translations complete.

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
Made for the Arch Linux community 🐧
</div>
