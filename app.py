"""
Pachul — app.py
Adw.Application subclass: registers GActions and wires the About dialog.
"""

import os
import sys
import shutil

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, Gdk

from styles import load_css
from window import pachulWindow
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

# ─── Inline‑Icons (SVG‑Daten für Icons, die im System‑Theme fehlen könnten) ───
# Hier kann jedes Icon als SVG‑String hinterlegt werden.
_INLINE_ICONS = {
    "dialog-password-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="3" y="6" width="10" height="7" rx="1" fill="currentColor"/>
        <rect x="5" y="3" width="6" height="4" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="8" cy="9" r="1.5" fill="currentColor"/>
        <line x1="8" y1="9" x2="8" y2="11" stroke="currentColor" stroke-width="1.5"/>
    </svg>""",
    # Weitere Icons können hier ergänzt werden, z.B.:
    # "package-x-generic-symbolic": "...",
}


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

        os.makedirs(ICON_DEST_DIR, exist_ok=True)
        if not os.path.exists(ICON_DEST):
            try:
                os.symlink(ICON_SOURCE, ICON_DEST)
            except OSError:
                # Fallback, falls Symlinks nicht unterstützt werden (z.B. manche FAT-Mounts)
                shutil.copyfile(ICON_SOURCE, ICON_DEST)

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
            "rate_mirrors":  self.win._on_rate_mirrors,
            "orphans":       self.win._on_show_orphans,
            "file_search":   self.win._on_show_file_search,
            "sysinfo":       self.win._on_show_sysinfo,
            "history":       self.win._on_show_history,
            "pacdiff":       self.win._on_show_pacdiff,
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
            "app.shortcuts":     ["<Ctrl>question"],
            "app.quit":          ["<Ctrl>q"],
        }
        for action, keys in accels.items():
            self.set_accels_for_action(action, keys)

        self.win.present()

    def _on_about(self, *_):
        about = Adw.AboutDialog()
        about.set_application_name("Pachul")
        about.set_application_icon("io.github.wergosam.pachul")
        about.set_version("2.3.1")
        about.set_developer_name("Juerg Rechsteiner")
        about.set_license_type(Gtk.License.GPL_2_0)
        about.set_website("https://github.com/wergosam/Pachul")
        about.set_issue_url("https://github.com/wergosam/Pachul/issues")
        about.set_comments("A powerful Pacman/AUR front end.\n")
        about.set_developers(["Juerg Rechsteiner https://github.com/wergosam"])
        about.present(self.win)


def main():
    return pachulApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
