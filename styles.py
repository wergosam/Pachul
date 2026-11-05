"""
Pachul — styles.py
Application-wide CSS and style loading.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, Adw

CSS = """
/* ── Nav rows ── */
.nav-row {
    border-radius: 8px;
    margin: 1px 6px;
}
.nav-row:selected {
    background: alpha(@accent_bg_color, 0.16);
}
.nav-row label {
    font-weight: 600;
    font-size: 0.88rem;
}

/* ── Package titles: ein Punkt kleiner (Standard 11pt → 10pt, title-2 15pt → 14pt) ── */
.pkg-name  { font-size: 0.91rem; }
.pkg-title { font-size: 1.27rem; }

/* ── Package rows ── */
.pkg-row { border-radius: 6px; margin: 1px 8px; }
.pkg-row:hover,
.pkg-row:selected,
.pkg-row:selected:hover { background: alpha(@accent_bg_color, 0.18); }

/* Hover-Effekt entfernen */
.pkg-row:hover { background: transparent; }

/* Der hellblaue Hintergrund ist weg, das breite Feld bleibt farbneutral */
.pkg-row-selected,
.pkg-row-selected:hover {
    background: transparent;
}

/* ── Batch-selection checkbox (custom-drawn, theme-independent) ── */
.pkg-checkbox,
.pkg-checkbox:hover,
.pkg-checkbox:focus,
.pkg-checkbox:active,
.pkg-checkbox:backdrop {
    border: 2px solid alpha(@card_fg_color, 0.4);
    border-radius: 5px;
    background-color: transparent;
    background-image: none;
    box-shadow: none;
    outline: none;
}
.pkg-checkbox-checked,
.pkg-checkbox-checked:hover,
.pkg-checkbox-checked:focus,
.pkg-checkbox-checked:active,
.pkg-checkbox-checked:backdrop {
    border-color: #3584e4;
    background-color: #3584e4;
    background-image: none;
}
.pkg-checkbox-mark,
.pkg-checkbox-mark:hover,
.pkg-checkbox-mark:focus,
.pkg-checkbox-mark:active,
.pkg-checkbox-mark:backdrop {
    color: #ffffff;
    background-color: transparent;
    background-image: none;
    font-size: 13px;
    font-weight: 800;
}

/* ── Badges ── */
.badge {
    border-radius: 999px;
    padding: 1px 7px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
}
.badge-core     { background: alpha(#3584e4, 0.18); color: #3584e4; }
.badge-extra    { background: alpha(#2ec27e, 0.18); color: #26a269; }
.badge-aur      { background: alpha(#9141ac, 0.18); color: #9141ac; }
.badge-local    { background: alpha(@card_fg_color, 0.10); color: alpha(@card_fg_color, 0.55); }
.badge-multilib { background: alpha(#e5a50a, 0.18); color: #c38600; }
.badge-foreign  { background: alpha(#e66100, 0.18); color: #e66100; }
.badge-flatpak  { background: alpha(#4a90d9, 0.18); color: #3d80c9; }
.badge-snap     { background: alpha(#e95420, 0.18); color: #e95420; }
.badge-chaotic-aur { background: alpha(#17b6a7, 0.18); color: #12968a; }

/* ── Row inline status pill (next to repo badge in list rows) ── */
.row-status-pill {
    border-radius: 999px;
    padding: 1px 6px;
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.05em;
}

.status-pill {
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}
.status-installed { background: alpha(#2ec27e, 0.15); color: #26a269; }
.status-available { background: alpha(@accent_bg_color, 0.15); color: @accent_color; }
.status-update    { background: alpha(#e5a50a, 0.15); color: #c38600; }
.status-foreign   { background: alpha(#e66100, 0.15); color: #e66100; }

/* ── Terminal ── */
.terminal-view {
    background: #f5f5f5;
    border-radius: 8px;
    font-family: "Cascadia Code","JetBrains Mono","Fira Code",monospace;
    font-size: 0.85rem;
    padding: 14px 16px;
}

/* Dunkles Systemtheme: heller Text auf hellgrauem Hintergrund wäre
   unlesbar, deshalb im Dark Mode auf klassisches dunkles Terminal
   umschalten. Wird per CSS-Klasse "terminal-view-dark" gesteuert, die
   dialogs.py abhängig von Adw.StyleManager().get_dark() setzt. Das
   helle Theme bleibt dadurch unverändert. */
.terminal-view.terminal-view-dark {
    background: #1e1e1e;
    color: #f0f0f0;
}

/* ── Detail hero ── */
.pkg-hero {
    background: alpha(@card_fg_color, 0.04);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 4px;
}

/* FlowBoxChild wrapper for the hero action buttons — reset its default
   padding/outline so the buttons sit flush, same as they did in the old
   plain Box layout. */
.hero-action-cell {
    padding: 0;
    border: none;
    outline: none;
}

/* ── Sidebar section labels (GTK4-valid CSS only) ── */
.sidebar-section {
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: alpha(@window_fg_color, 0.62);
    margin-top: 6px;
    margin-bottom: 4px;
}

/* ── Stat cards ── */
.stat-card {
    background: alpha(@accent_bg_color, 0.08);
    border-radius: 12px;
    padding: 10px 6px;
    border: 1px solid alpha(@accent_bg_color, 0.18);
}
.stat-card-aur {
    background: alpha(#9141ac, 0.08);
    border-radius: 12px;
    padding: 10px 6px;
    border: 1px solid alpha(#9141ac, 0.18);
}
.stat-card-updates {
    background: alpha(#e5a50a, 0.08);
    border-radius: 12px;
    padding: 10px 6px;
    border: 1px solid alpha(#e5a50a, 0.18);
}
.stat-number {
    font-size: 1.45rem;
    font-weight: 900;
}
.stat-label {
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: alpha(@window_fg_color, 0.60);
}

/* ── Count badges ── */
.count-badge {
    border-radius: 999px;
    background: alpha(@card_fg_color, 0.10);
    padding: 0px 7px;
    font-size: 0.70rem;
    font-weight: 700;
    min-width: 20px;
}
.count-update  { background: alpha(#e5a50a, 0.15); color: #c38600; }
.count-foreign { background: alpha(#9141ac, 0.15); color: #9141ac; }
.count-new     { background: alpha(#26a269, 0.15); color: #26a269; }

/* ── Dependency chips ── */
.dep-chip {
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 600;
    background: alpha(@card_fg_color, 0.07);
    border: 1px solid alpha(@card_fg_color, 0.12);
    min-height: 0;
}
.dep-chip:hover {
    background: alpha(@accent_bg_color, 0.15);
    border-color: alpha(@accent_bg_color, 0.35);
    color: @accent_color;
}

/* ── Misc ── */
/* Alle Buttons: gleiche runde Form wie Installieren/Deinstallieren.
   Ausgenommen: Flat-/Icon-/Kreis-/Toggle-Buttons und Fenster-Knöpfe. */
button.install-btn, button.remove-btn, button.hold-btn, button.pill-btn,
button.suggested-action, button.destructive-action,
button:not(.flat):not(.circular):not(.image-button):not(.titlebutton):not(.toggle):not(.suggested-action):not(.destructive-action) {
    border-radius: 999px;
    font-weight: 600;
    padding-left: 14px; padding-right: 14px;
}
.install-btn label, .remove-btn label, .hold-btn label, .pill-btn label,
button.suggested-action label, button.destructive-action label,
button:not(.flat):not(.circular):not(.image-button):not(.titlebutton):not(.toggle):not(.suggested-action):not(.destructive-action) label {
    font-size: 0.91rem;  /* alle Text-Buttons gleich gross wie "Installieren" */
}
button.suggested-action, button.destructive-action,
button:not(.flat):not(.circular):not(.image-button):not(.titlebutton):not(.toggle):not(.suggested-action):not(.destructive-action) {
    font-size: 0.91rem;
}
/* Menüpunkte in der Titelleiste (Pakete, Werkzeuge …): 1 Punkt kleiner */
button.header-menu-btn, button.header-menu-btn label { font-size: 0.91rem; }
/* Aktions-Buttons mit Text (Neu installieren, Downgrade, Ignorieren): Rahmen immer sichtbar */
button.pill-btn.flat {
    border: 1px solid alpha(currentColor, 0.35);
    background-image: none;
    box-shadow: none;
}
button.pill-btn.flat:hover { background-color: alpha(currentColor, 0.08); }
button.pill-btn.flat:active { background-color: alpha(currentColor, 0.14); }
button.pill-btn.flat:disabled { border-color: alpha(currentColor, 0.18); }
.orphan-row  { border-left: 3px solid alpha(#e66100, 0.6); }

progressbar.success trough progress { background: #2ec27e; }
progressbar.warning trough progress { background: #e5a50a; }
progressbar trough { border-radius: 999px; min-height: 6px; }
progressbar trough progress { border-radius: 999px; }

/* Search page large entry */
.search-page-entry {
    font-size: 1.05rem;
    padding: 6px 4px;
    min-height: 42px;
}
.search-page-entry:focus {
    outline: none;
}

/* ── Dim/secondary text app-wide: Adwaita's stock ".dim-label" dims via
   the "opacity" property, not "color". Adding only a color-alpha on top
   (as the previous rule did) doesn't replace that opacity — it multiplies
   with it, which made the text end up just as light (or lighter) than
   before. Resetting opacity to 1 here and controlling the darkness purely
   through color-alpha fixes that, and darkens dim/secondary text
   everywhere in the app (sidebar labels, subtitles, captions, the Help
   and About dialogs, etc.), not just the Help window. ── */
.dim-label {
    opacity: 1;
    color: alpha(@window_fg_color, 0.72);
}

/* ── Switches: smaller, soft light-blue instead of the strong accent blue ── */
switch {
    padding: 0;
    margin: 0;
    min-height: 0;
    min-width: 0;
    border-radius: 999px;
}
switch slider {
    min-width: 16px;
    min-height: 16px;
    margin: 2px;
    border-radius: 999px;
}

switch:checked,
switch:checked:hover,
switch:checked:backdrop {
    background-color: #E3F6FE;
    background-image: none;
    border: 1px solid #8CC4E0;
    color: #3A5F73;
}
switch:checked slider,
switch:checked:backdrop slider {
    background-color: #4A86A8;
    background-image: none;
    border-color: #4A86A8;
}

/* Help dialog: function-description subtitle text — same opacity-reset
   fix, kept a touch darker still since these are the primary readable
   content of that dialog, not a secondary hint. */
.help-row .subtitle {
    opacity: 1;
    color: alpha(@window_fg_color, 0.85);
}
"""

# Nur im hellen Modus: sanfte, helle, klare Farben für Installieren/Deinstallieren.
LIGHT_CSS = """
/* Grün: Hauptaktion (Installieren, Speichern, OK …) */
button.suggested-action {
    background-image: none;
    background-color: #c9f0dc;
    color: #1b6b45;
    border: 1px solid #a9e2c3;
    box-shadow: none;
}
button.suggested-action:hover { background-color: #b8eacf; }
button.suggested-action:active { background-color: #a9e2c3; }
/* Rosé: zerstörerische Aktion (Deinstallieren, Entfernen …) */
button.destructive-action {
    background-image: none;
    background-color: #fcd9dc;
    color: #a3262f;
    border: 1px solid #f6bcc1;
    box-shadow: none;
}
button.destructive-action:hover { background-color: #fac8cc; }
button.destructive-action:active { background-color: #f6bcc1; }
/* Hellblau: alle übrigen Text-Buttons (Schließen, Abbrechen, Neu installieren, Ignorieren …) */
button.pill-btn.flat,
button:not(.flat):not(.circular):not(.image-button):not(.titlebutton):not(.toggle):not(.suggested-action):not(.destructive-action) {
    background-image: none;
    background-color: #e6eff9;
    color: #2c5278;
    border: 1px solid #cddff0;
    box-shadow: none;
}
button.pill-btn.flat:hover,
button:not(.flat):not(.circular):not(.image-button):not(.titlebutton):not(.toggle):not(.suggested-action):not(.destructive-action):hover { background-color: #d8e7f6; }
button.pill-btn.flat:active,
button:not(.flat):not(.circular):not(.image-button):not(.titlebutton):not(.toggle):not(.suggested-action):not(.destructive-action):active { background-color: #cddff0; }
"""


def load_css():
    display = Gdk.Display.get_default()
    p = Gtk.CssProvider()
    p.load_from_data(CSS.encode())
    Gtk.StyleContext.add_provider_for_display(
        display, p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # Pastellfarben der Buttons nur im hellen Modus aktiv; folgt dem Umschalter live.
    light = Gtk.CssProvider()
    light.load_from_data(LIGHT_CSS.encode())
    state = {"on": False}

    def _sync(*_):
        dark = Adw.StyleManager.get_default().get_dark()
        if not dark and not state["on"]:
            Gtk.StyleContext.add_provider_for_display(
                display, light, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
            state["on"] = True
        elif dark and state["on"]:
            Gtk.StyleContext.remove_provider_for_display(display, light)
            state["on"] = False

    Adw.StyleManager.get_default().connect("notify::dark", _sync)
    _sync()
