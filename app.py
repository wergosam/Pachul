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
    from gi.repository import Gtk, Adw, Gio, Gdk, GLib
except ValueError as e:
    sys.stderr.write(
        f"[pachul] Fehlende GTK4/libadwaita-Bindings ({e}).\n"
        f"[pachul] Installieren mit:\n"
        f"[pachul]   {_missing_dep_hint()}\n"
        f"[pachul] (Oder einfach install.sh erneut ausführen — das prüft das automatisch.)\n"
    )
    sys.exit(1)

from styles import load_css
from backend import get_setting, save_settings
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



_APP_ID = "io.github.wergosam.pachul"

# (action name, method of the main window that handles it), in registration order
_WINDOW_ACTIONS = (
    ("sync", "_on_sync_db"),
    ("refresh", "_on_refresh"),
    ("install", "_on_install"),
    ("remove", "_on_remove"),
    ("cache", "_on_clean_cache"),
    ("check_updates", "_on_check_updates"),
    ("manage_repos", "_on_manage_repos"),
    ("apt_repair", "_on_show_apt_repair"),
    ("dnf_repair", "_on_show_dnf_repair"),
    ("zypper_repair", "_on_show_zypper_repair"),
    ("pacman_repair", "_on_show_pacman_repair"),
    ("cert_checker", "_on_show_cert_checker"),
    ("broken_symlinks", "_on_show_broken_symlinks"),
    ("services_security", "_on_show_services_security"),
    ("config_backup", "_on_show_config_backup"),
    ("rate_mirrors", "_on_rate_mirrors"),
    ("orphans", "_on_show_orphans"),
    ("file_search", "_on_show_file_search"),
    ("sysinfo", "_on_show_sysinfo"),
    ("history", "_on_show_history"),
    ("pacdiff", "_on_show_pacdiff"),
    ("tool_updates", "_on_show_tool_updates"),
    ("ignored", "_on_show_ignored"),
    ("export_pkgs", "_on_export_pkgs"),
    ("import_pkgs", "_on_import_pkgs"),
    ("install_local", "_on_install_local"),
    ("pkgbuild", "_on_view_pkgbuild"),
    ("hold", "_on_toggle_hold"),
    ("mark_explicit", "_on_mark_explicit"),
    ("mark_asdeps", "_on_mark_asdeps"),
    ("tools", "_on_show_tools"),
    ("preferences", "_on_preferences"),
    ("shortcuts", "_on_show_shortcuts"),
    ("search", "_on_focus_search"),
)


class pachulApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=_APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        for signal_name, handler in (("activate", self._on_activate),
                                     ("shutdown", self._on_shutdown)):
            self.connect(signal_name, handler)

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

    # ── Appearance (light / dark / follow system) ────────────────────────────

    _SCHEMES = {
        "system": Adw.ColorScheme.DEFAULT,
        "light":  Adw.ColorScheme.FORCE_LIGHT,
        "dark":   Adw.ColorScheme.FORCE_DARK,
    }

    def _apply_color_scheme(self, value):
        if value not in self._SCHEMES:
            value = "system"
        Adw.StyleManager.get_default().set_color_scheme(self._SCHEMES[value])
        return value

    def _on_color_scheme(self, action, param):
        """Radio entries in the main menu: app.color_scheme::system|light|dark."""
        value = self._apply_color_scheme(param.get_string())
        save_settings({"color_scheme": value})
        action.set_state(GLib.Variant.new_string(value))

    def _on_toggle_dark(self, *_):
        """Light/dark toggle (Ctrl+Shift+D); the header bar button was removed."""
        dark = Adw.StyleManager.get_default().get_dark()
        value = self._apply_color_scheme("light" if dark else "dark")
        save_settings({"color_scheme": value})
        act = self.lookup_action("color_scheme")
        if act is not None:
            act.set_state(GLib.Variant.new_string(value))

    def _on_activate(self, app):
        self._register_icon_theme()
        load_css()
        saved_scheme = self._apply_color_scheme(get_setting("color_scheme") or "system")
        self.win = pachulWindow(app)
        self.win.connect("close-request", lambda *_: self.quit())

        handlers = {name: getattr(self.win, method)
                    for name, method in _WINDOW_ACTIONS}
        handlers["quit"] = lambda *_: self.quit()
        handlers["about"] = self._on_about
        for action_name, callback in handlers.items():
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", callback)
            self.add_action(action)

        # Stateful radio action for the Appearance section of the main menu
        scheme_act = Gio.SimpleAction.new_stateful(
            "color_scheme", GLib.VariantType.new("s"),
            GLib.Variant.new_string(saved_scheme))
        scheme_act.connect("activate", self._on_color_scheme)
        self.add_action(scheme_act)

        toggle_act = Gio.SimpleAction.new("toggle_dark", None)
        toggle_act.connect("activate", self._on_toggle_dark)
        self.add_action(toggle_act)

        accels = {
            "app.search":        ["<Ctrl>f"],
            "app.sync":          ["F5"],
            "app.refresh":       ["<Ctrl>r"],
            "app.check_updates": ["<Ctrl>u"],
            "app.tools":         ["<Ctrl>t"],
            "app.toggle_dark":   ["<Ctrl><Shift>d"],
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
