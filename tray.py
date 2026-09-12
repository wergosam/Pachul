#!/usr/bin/env python3
"""
Pachul — tray.py
Standalone system-tray indicator, meant to be launched at login (see
io.github.wergosam.pachul-tray.desktop) and left running for the whole
session — independent of whether the main Pachul window is open.

Shows a persistent tray icon (Pachul's own app icon, always the same one —
see the ICON_THEME_DIR comment below for why) with the pending-update
count as a text label next to it, e.g. "3", empty when up to date.
A short menu offers "Check for Updates", "Open Pachul" and "Quit". The
icon re-checks periodically using the same "bg_check_interval" setting
the systemd background timer (backend.enable_update_timer) already
exposes in Preferences, and — governed by the existing "notify_updates"
setting — fires one desktop notification whenever the pending-update
count rises, mirroring pachulWindow._on_updates_loaded()'s behaviour in
the main app.

Imports only `backend` and `i18n` (no GTK4/libadwaita) — this runs as
its own GTK3 process via AppIndicator/AyatanaAppIndicator3, which is
built against GTK3. That's unrelated to, and doesn't conflict with, the
main application's GTK4 process.

Requires one of these system packages (not needed just to run the main
GTK4 app — see optdepends in PKGBUILD):
    - libayatana-appindicator  (preferred, actively maintained)
    - libappindicator-gtk3     (older fallback)
"""

import os
import shutil
import subprocess
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    try:
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3
    except (ValueError, ImportError):
        sys.stderr.write(
            "pachul-tray: neither AyatanaAppIndicator3 nor AppIndicator3 "
            "is available.\nInstall 'libayatana-appindicator' (pacman -S "
            "libayatana-appindicator) and try again.\n")
        sys.exit(1)

from gi.repository import Gtk, GLib

import backend
from i18n import tr

APP_ID = "pachul-tray"

# Directory containing io_github_wergosam_pachul_bw.svg — same layout in
# a source checkout (right next to tray.py) and after installation
# (both land in /usr/share/pachul/, see PKGBUILD).
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# The icon is handed to AppIndicator as an *absolute path*, not a name
# resolved through the icon theme. Name-based lookup (via
# set_icon_theme_path() + a copy in the user's hicolor dir) used to be
# used here, but is unreliable on Plasma: AppIndicator resolves the name
# itself just fine on startup (via our set_icon_theme_path() hint), but
# Plasma's system tray *separately* re-resolves the icon a few seconds
# later via the SNI's auto-populated DesktopEntry property (matching
# io.github.wergosam.pachul-tray.desktop's Icon= key) — and that second
# lookup goes through Plasma/KDE's own icon cache (KIconLoader/Sycoca),
# which knows nothing about our private theme-path hint and hasn't
# indexed the freshly-copied file. When that second lookup fails, Plasma
# falls back to its generic "unidentified application" icon (Breeze
# applications-other — the white A on blue). An absolute path sidesteps
# both lookups entirely: there's no name left for either AppIndicator or
# Plasma to re-resolve. backend.py's _pachul_icon_path() already uses
# this same trick for notify-send icons.
#
# The tray uses the black-and-white variant rather than the main
# (transparent) app icon: most system trays render monochrome/symbolic
# icons best at small sizes, and a single-tone glyph stays legible across
# both light and dark panel themes.
ICON_PATH = os.path.join(APP_DIR, "io_github_wergosam_pachul_bw.svg")

# Mirrors backend._TIMER_INTERVALS (hourly | 6h | daily) used by the
# systemd --user timer, so both mechanisms honour the same setting.
_INTERVAL_SECONDS = {"hourly": 3600, "6h": 6 * 3600, "daily": 24 * 3600}


class PachulTray:
    def __init__(self):
        self._prev_count = None
        # Id of the last "N updates available" notification we sent
        # (None if we haven't sent one, or already withdrew it) — see
        # _apply_result() and backend.withdraw_notification().
        self._notif_id = None

        self.indicator = AppIndicator3.Indicator.new(
            APP_ID, ICON_PATH, AppIndicator3.IndicatorCategory.SYSTEM_SERVICES)
        self.indicator.set_icon_full(ICON_PATH, tr("System is up to date"))
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Pachul")

        self.menu = Gtk.Menu()

        self.status_item = Gtk.MenuItem(label=tr("Checking for updates…"))
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)
        self.menu.append(Gtk.SeparatorMenuItem())

        check_item = Gtk.MenuItem(label=tr("Check for Updates"))
        check_item.connect("activate", lambda *_a: self._run_check(notify_on_new=False))
        self.menu.append(check_item)

        open_item = Gtk.MenuItem(label=tr("Open Pachul"))
        open_item.connect("activate", lambda *_a: self._open_pachul())
        self.menu.append(open_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label=tr("Quit"))
        quit_item.connect("activate", lambda *_a: Gtk.main_quit())
        self.menu.append(quit_item)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

        self._run_check(notify_on_new=True)
        self._schedule_next()

    def _open_pachul(self):
        """Launch the main window — the installed `pachul` launcher if
        found on PATH, otherwise app.py right next to this script (dev/
        source checkouts that haven't been installed system-wide)."""
        exe = shutil.which("pachul")
        if exe:
            subprocess.Popen([exe])
            return
        app_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
        subprocess.Popen([sys.executable or "python3", app_py])

    def _schedule_next(self):
        interval = backend.get_setting("bg_check_interval")
        seconds = _INTERVAL_SECONDS.get(interval, 24 * 3600)
        GLib.timeout_add_seconds(seconds, self._on_timer)

    def _on_timer(self):
        self._run_check(notify_on_new=True)
        self._schedule_next()
        return False  # one-shot; _schedule_next() re-arms with the current setting

    def _run_check(self, notify_on_new):
        """Runs check_updates() (external pacman/AUR-helper calls) off the
        GTK main thread, same pattern as pachulWindow._bg_check_updates()."""
        def worker():
            updates = backend.check_updates()
            GLib.idle_add(self._apply_result, updates, notify_on_new)
        threading.Thread(target=worker, daemon=True).start()

    def _apply_result(self, updates, notify_on_new):
        n = len(updates)
        if n > 0:
            self.indicator.set_label(str(n), "")
            # Not every StatusNotifierItem host renders the text label set
            # above (stock GNOME Shell's AppIndicator extension in
            # particular often doesn't) — but the hover tooltip is
            # supported essentially everywhere, so update it too as a
            # fallback that keeps the count visible either way.
            self.indicator.set_icon_full(
                ICON_PATH, tr("{n} update(s) available.").format(n=n))
            self.status_item.set_label(tr("{n} update(s) available.").format(n=n))
            if (notify_on_new and n != self._prev_count
                    and backend.get_setting("notify_updates")):
                self._notif_id = backend.send_update_notification(n)
        else:
            self.indicator.set_label("", "")
            self.indicator.set_icon_full(ICON_PATH, tr("System is up to date"))
            self.status_item.set_label(tr("System is up to date"))
            # The pending count just dropped to 0 (updates got installed,
            # whether via the main window, the CLI, or somewhere else
            # entirely) — withdraw any notification we'd sent earlier so
            # a stale "N updates available" entry doesn't keep sitting in
            # the desktop's notification history after the fact.
            if self._notif_id is not None:
                backend.withdraw_notification(self._notif_id)
                self._notif_id = None
        self._prev_count = n
        return False


def main():
    PachulTray()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
