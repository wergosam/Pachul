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

PacHub is a clean, fast GUI frontend for `pacman` and the AUR. It lets you search, install, update and manage packages without touching the terminal — while still giving you full control over repositories, orphans, mirrors and cache.

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
- **Tools**
  - Sync Databases (`F5`)
  - Check for Updates (`Strg+U`)
  - Rate Mirrors
  - Find Orphans
  - Clean Cache
  - Manage Repositories
  - View Config Files (`.pacnew`)
  - Package History
  - System Info
  - Export / Import Package Lists
  - View PKGBUILD (AUR)
  - Hold / Unhold Selected Packages
  - Mark as Explicit or Dependency
- **Keyboard shortcuts** for all common actions
- Light and dark theme support

---

## Installation

### From the AUR

```bash
yay -S pachub
```

### Manual (from source)

```bash
git clone https://github.com/yourname/pachub.git
cd pachub
pip install -r requirements.txt
python pachub.py
```

**Dependencies:**

| Package | Purpose |
|---------|---------|
| `python` ≥ 3.10 | Runtime |
| `python-pyqt6` | GUI framework |
| `pacman` | Package backend |
| `yay` or `paru` | AUR support (optional) |

---

## Usage

| Action | Shortcut |
|--------|----------|
| Sync Databases | `F5` |
| Check for Updates | `Strg+U` |
| Refresh List | `Strg+R` |
| Preferences | `Strg+,` |
| Keyboard Shortcuts | `Strg+?` |

---

## Project Structure

```
pachub/
├── pachub.py          # Entry point
├── ui/                # Qt UI components
├── backend/           # pacman / AUR integration
├── assets/            # Icons and themes
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

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
Made for the Arch Linux community 🐧
</div>
