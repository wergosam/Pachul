"""
Pachul — app.py
Adw.Application subclass: registers GActions and wires the About dialog.
"""

import os
import sys
import shutil

# Friendly, distro-specific dependency check BEFORE we try to import gi/Gtk/
# Adw. Running app.py directly (without going through install.sh, which
# already checks/installs these) previously crashed with a raw Python
# traceback the first time GTK4 was missing, and again the second time for
# libadwaita — confusing for anyone not used to reading tracebacks.
def _missing_dep_hint():
    try:
        from distro import get_family
        fam = get_family()
    except Exception:
        fam = None
    return {
        "debian": "sudo apt update && sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1 python3-gi",
        "fedora": "sudo dnf install gtk4 libadwaita python3-gobject",
        "suse":   "sudo zypper install typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-gobject",
        "arch":   "sudo pacman -S gtk4 libadwaita python-gobject",
    }.get(fam, "See README.md / install.sh for the right packages on your distro.")


import gi
try:
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, Gio, Gdk
except ValueError as e:
    sys.stderr.write(
        f"[pachul] Fehlende GTK4/libadwaita-Bindings ({e}).\n"
        f"[pachul] Installieren mit:\n"
        f"[pachul]   {_missing_dep_hint()}\n"
        f"[pachul] (Oder einfach install.sh erneut ausführen — das prüft das automatisch.)\n"
    )
    sys.exit(1)

from styles import load_css
from window import pachulWindow
from dialogs import show_about_dialog
from i18n import tr

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_NAME = "io.github.wergosam.pachul"

# Master-Icon liegt direkt im Projekt-Root: io.github.wergosam.pachul.svg
ICON_SOURCE = os.path.join(APP_DIR, f"{ICON_NAME}.svg")

# GTK verlangt zwingend eine hicolor/<size>/apps/-Struktur im Suchpfad,
# sonst wird der Icon-Name nicht aufgelöst. Die bauen wir versteckt
# und automatisch per Symlink, damit im Root nur die eine Datei liegt.
ICON_THEME_DIR = os.path.join(APP_DIR, ".icon-theme")
ICON_DEST_DIR = os.path.join(ICON_THEME_DIR, "hicolor", "scalable", "apps")
ICON_DEST = os.path.join(ICON_DEST_DIR, f"{ICON_NAME}.svg")

# ─── Inline SVG icons — full theme independence ──────────────────────────────
# The full icon set lives in icons.py (single source of truth, shared with
# the rest of the app for direct rendering). Here we additionally register
# them into a private icon-theme search path as defense-in-depth for any
# icon lookup we might've missed — see icons.py's module docstring for why
# this registration alone isn't a complete fix and direct rendering
# (icons.themed_image / icons.themed_paintable) is what the rest of the
# app actually uses.
from icons import ICON_SVGS as _INLINE_ICONS



class pachulApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.wergosam.pachul",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.connect("activate", self._on_activate)
        self.connect("shutdown", self._on_shutdown)

    def _register_icon_theme(self):
        """Icon aus dem Projekt-Root in die von GTK geforderte
        hicolor-Struktur verlinken und den Suchpfad registrieren."""
        if not os.path.isfile(ICON_SOURCE):
            print(f"[pachul] Icon nicht gefunden: {ICON_SOURCE}")
            return

        try:
            os.makedirs(ICON_DEST_DIR, exist_ok=True)
            # os.path.exists() follows symlinks and returns False for a
            # DANGLING link too — e.g. left over from a previous checkout
            # at a different path, or the project folder having been
            # moved/renamed. That used to make us try os.symlink() again,
            # hit FileExistsError (the link itself still exists), fall
            # back to shutil.copyfile(), and then crash with
            # FileNotFoundError because the link's target directory was
            # gone. os.path.lexists() sees the link regardless of whether
            # its target is valid, so we can detect and clear out a stale
            # one before (re)creating it.
            if os.path.lexists(ICON_DEST) and not os.path.exists(ICON_DEST):
                os.remove(ICON_DEST)
            if not os.path.exists(ICON_DEST):
                try:
                    os.symlink(ICON_SOURCE, ICON_DEST)
                except OSError:
                    # Fallback, falls Symlinks nicht unterstützt werden (z.B. manche FAT-Mounts)
                    shutil.copyfile(ICON_SOURCE, ICON_DEST)
        except OSError as e:
            # Icon-Registrierung ist ein Nice-to-have, kein Muss — ein
            # Berechtigungsproblem hier soll die App nicht mitreißen.
            print(f"[pachul] Icon-Registrierung fehlgeschlagen: {e}")
            return

        display = Gdk.Display.get_default()
        if display is None:
            return
        icon_theme = Gtk.IconTheme.get_for_display(display)
        icon_theme.add_search_path(ICON_THEME_DIR)

        # Inline‑Icons generieren (falls nicht vorhanden)
        self._create_inline_icons(icon_theme)

        # Prüfung (optional)
        # found = icon_theme.has_icon(ICON_NAME)

    def _create_inline_icons(self, icon_theme):
        """Erstellt fehlende Icons aus _INLINE_ICONS als SVG‑Dateien im Suchpfad."""
        for name, svg_data in _INLINE_ICONS.items():
            dest_path = os.path.join(ICON_DEST_DIR, f"{name}.svg")
            if os.path.exists(dest_path):
                continue
            try:
                with open(dest_path, "w", encoding="utf-8") as f:
                    f.write(svg_data)
                # Die Icon‑Theme‑Cache muss nicht neu geladen werden, da der Suchpfad bereits registriert ist.
                # GTK erkennt neue Dateien beim nächsten Zugriff.
            except OSError as e:
                print(f"[pachul] Konnte Inline‑Icon {name} nicht schreiben: {e}")

    def _on_shutdown(self, app):
        # Signal all background threads to stop and force-exit cleanly
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)

    def _on_activate(self, app):
        self._register_icon_theme()
        load_css()
        self.win = pachulWindow(app)
        self.win.connect("close-request", lambda *_: self.quit())

        actions = {
            "sync":          self.win._on_sync_db,
            "refresh":       self.win._on_refresh,
            "install":       self.win._on_install,
            "remove":        self.win._on_remove,
            "cache":         self.win._on_clean_cache,
            "check_updates": self.win._on_check_updates,
            "manage_repos":  self.win._on_manage_repos,
            "apt_repair":    self.win._on_show_apt_repair,
            "dnf_repair":    self.win._on_show_dnf_repair,
            "zypper_repair": self.win._on_show_zypper_repair,
            "pacman_repair": self.win._on_show_pacman_repair,
            "cert_checker":  self.win._on_show_cert_checker,
            "broken_symlinks": self.win._on_show_broken_symlinks,
            "services_security": self.win._on_show_services_security,
            "config_backup":     self.win._on_show_config_backup,
            "rate_mirrors":  self.win._on_rate_mirrors,
            "orphans":       self.win._on_show_orphans,
            "file_search":   self.win._on_show_file_search,
            "sysinfo":       self.win._on_show_sysinfo,
            "history":       self.win._on_show_history,
            "pacdiff":       self.win._on_show_pacdiff,
            "tool_updates":  self.win._on_show_tool_updates,
            "ignored":       self.win._on_show_ignored,
            "export_pkgs":   self.win._on_export_pkgs,
            "import_pkgs":   self.win._on_import_pkgs,
            "pkgbuild":      self.win._on_view_pkgbuild,
            "hold":          self.win._on_toggle_hold,
            "mark_explicit": self.win._on_mark_explicit,
            "mark_asdeps":   self.win._on_mark_asdeps,
            "preferences":   self.win._on_preferences,
            "shortcuts":     self.win._on_show_shortcuts,
            "search":        self.win._on_focus_search,
            "quit":          lambda *_: self.quit(),
            "about":         self._on_about,
        }
        for name, cb in actions.items():
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)

        accels = {
            "app.search":        ["<Ctrl>f"],
            "app.sync":          ["F5"],
            "app.refresh":       ["<Ctrl>r"],
            "app.check_updates": ["<Ctrl>u"],
            "app.preferences":   ["<Ctrl>comma"],
            "app.shortcuts":     ["<Ctrl>question", "F1"],
            "app.quit":          ["<Ctrl>q"],
        }
        for action, keys in accels.items():
            self.set_accels_for_action(action, keys)

        self.win.present()

    def _on_about(self, *_):
        # Custom single-page dialog instead of Adw.AboutDialog — see
        # show_about_dialog()'s docstring in dialogs.py for why: the stock
        # widget splits license/debug-info off onto separate sub-pages by
        # design, which is the opposite of "everything at a glance".
        show_about_dialog(self.win)


def main():
    return pachulApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
