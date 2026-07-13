"""
Pachul — models.py
GObject data model (PackageItem), the virtualized package ListView factory
(make_package_listview / PackageRowContent), and the sidebar NavRow.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, GObject, Pango

from i18n import tr
from icons import themed_image, get_icon_texture

# ─── Icon helper ──────────────────────────────────────────────────────────────
# Icons are rendered directly from our own inline SVG set (icons.py) instead
# of being looked up by name in the system/GTK icon theme. This used to go
# through Gio.ThemedIcon.new_from_names() with a list of fallback names, but
# that only helps when a name is entirely *absent* from the active theme —
# if the active theme's own index claims to have the icon but its file is
# missing or broken (as happened with a KDE Breeze variant and
# "utilities-terminal-symbolic", used below for bash/zsh/fish packages),
# GTK never reaches the fallback names at all. Rendering our own SVG
# directly sidesteps the system icon theme entirely, so this can't happen
# regardless of what's wrong with the active theme.

def make_icon(icon_names, pixel_size=18):
    """Create a Gtk.Image from a single icon name or a list of fallback names."""
    return themed_image(icon_names, pixel_size)


def set_button_icon(button, icon_names, pixel_size=18):
    """Set an icon-only button's icon using a fallback chain of icon names."""
    img = make_icon(icon_names, pixel_size)
    button.set_child(img)
    button.add_css_class("image-button")


# ─── Repository badge mapping ─────────────────────────────────────────────────

REPO_BADGE_CLASS = {
    "core":         "badge-core",
    "extra":        "badge-extra",
    "aur":          "badge-aur",
    "multilib":     "badge-multilib",
    "local":        "badge-local",
    "foreign":      "badge-foreign",
    "flatpak":      "badge-flatpak",
    "snap":         "badge-snap",
    "chaotic-aur":  "badge-chaotic-aur",
}

# ─── Symbolic icon fallbacks per package name ─────────────────────────────────

PKG_ICONS = {
    "linux":                  "utilities-terminal-symbolic",
    "linux-firmware":         "drive-harddisk-symbolic",
    "base":                   "package-x-generic-symbolic",
    "bash":                   "utilities-terminal-symbolic",
    "zsh":                    "utilities-terminal-symbolic",
    "fish":                   "utilities-terminal-symbolic",
    "git":                    "preferences-system-details-symbolic",
    "python":                 "text-x-script-symbolic",
    "python-pip":             "text-x-script-symbolic",
    "nodejs":                 "text-x-script-symbolic",
    "npm":                    "text-x-script-symbolic",
    "rust":                   "application-x-executable-symbolic",
    "go":                     "application-x-executable-symbolic",
    "cmake":                  "applications-engineering-symbolic",
    "docker":                 "application-x-executable-symbolic",
    "flatpak":                "package-x-generic-symbolic",
    "pacman":                 "package-x-generic-symbolic",
    "yay":                    "package-x-generic-symbolic",
    "paru":                   "package-x-generic-symbolic",
    "networkmanager":         "network-wireless-symbolic",
    "openssh":                "network-server-symbolic",
    "pipewire":               "audio-speakers-symbolic",
    "alsa-utils":             "audio-card-symbolic",
    "htop":                   "utilities-system-monitor-symbolic",
    "curl":                   "network-transmit-receive-symbolic",
    "wget":                   "network-transmit-receive-symbolic",
    "vim":                    "text-editor-symbolic",
    "nano":                   "text-editor-symbolic",
    "mesa":                   "video-display-symbolic",
    "timeshift":              "document-revert-symbolic",
    "systemd":                "preferences-system-symbolic",
    "firefox":                "web-browser-symbolic",
    "chromium":               "web-browser-symbolic",
    "google-chrome":          "web-browser-symbolic",
    "gimp":                   "applications-graphics-symbolic",
    "vlc":                    "applications-multimedia-symbolic",
    "visual-studio-code-bin": "text-editor-symbolic",
}


def pkg_icon(name):
    return PKG_ICONS.get(name, "package-x-generic-symbolic")


# ─── GObject model ────────────────────────────────────────────────────────────

class PackageItem(GObject.Object):
    __gtype_name__ = 'PachulPackageItem'

    def __init__(self, name, version, repo="local", status="installed",
                 description="", foreign=False, source_id=None):
        super().__init__()
        self.pkg_name        = name
        self.pkg_version     = version
        self.pkg_repo        = repo
        self.pkg_status      = status
        self.pkg_description = description
        self.pkg_foreign     = foreign
        # Set for Flatpak (application ID, e.g. "org.gimp.GIMP") and Snap
        # (plain package name) entries — that's what the actual install/
        # remove commands need, kept separate from pkg_name so the display
        # name can stay human-friendly. None for ordinary pacman packages.
        self.pkg_source_id   = source_id
        # Temporärer UI-Backpointer, damit wir beim Klicken das Widget direkt refashen können
        self._bound_widget   = None


# ─── Shared selection-mode state ──────────────────────────────────────────────

class ListSelectionState:
    """Shared mutable selection-mode state for a package ListView's row factory.

    A single instance is captured by every row's `bind()` closure, so it is
    read fresh on every (re)bind — meaning recycled/virtualized rows always
    reflect the current mode and selected set, even for rows that scroll
    into view only after the mode was toggled.
    """
    __slots__ = ("active", "selected")

    def __init__(self):
        self.active = False      # whether checkbox/batch selection mode is on
        self.selected = set()    # set of selected pkg_name strings


# ─── Package list row (virtualized ListView) ─────────────────────────────────

_STATUS_PILL_CSS = ("status-installed", "status-update")
_REPO_BADGE_CSS = tuple(set(REPO_BADGE_CLASS.values()))


class PackageRowContent(Gtk.Box):
    """Recyclable row widget for the package ListView.

    Built once per visible slot in `setup`, then re-bound to whatever
    PackageItem scrolls into it via `bind` — so only ~screenful of widgets
    ever exist, regardless of list size.
    """
    __gtype_name__ = 'PachulPackageRowContent'

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.pkg = None
        self.sel_state = None

        self.set_margin_top(9);    self.set_margin_bottom(9)
        self.set_margin_start(10); self.set_margin_end(10)
        self.add_css_class("pkg-row")

        # Selection-mode checkbox
        self.checkbox = Gtk.Box()
        self.checkbox.add_css_class("pkg-checkbox")
        self.checkbox.set_size_request(20, 20)
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.set_halign(Gtk.Align.CENTER)
        self.checkbox.set_can_target(False)

        self.checkbox_mark = Gtk.Label(label="✓")
        self.checkbox_mark.add_css_class("pkg-checkbox-mark")
        self.checkbox_mark.set_halign(Gtk.Align.CENTER)
        self.checkbox_mark.set_valign(Gtk.Align.CENTER)
        self.checkbox.append(self.checkbox_mark)
        self.checkbox.set_visible(False)
        self.append(self.checkbox)

        self.icon = Gtk.Image()
        self.icon.set_pixel_size(22)
        self.icon.set_valign(Gtk.Align.CENTER)
        self.icon.add_css_class("dim-label")
        self.append(self.icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info_box.set_hexpand(True)
        info_box.set_valign(Gtk.Align.CENTER)

        self.name_label = Gtk.Label()
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.add_css_class("body")
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_weight_new(Pango.Weight.SEMIBOLD))
        self.name_label.set_attributes(attrs)
        info_box.append(self.name_label)

        self.desc_label = Gtk.Label()
        self.desc_label.set_halign(Gtk.Align.START)
        self.desc_label.add_css_class("caption")
        self.desc_label.add_css_class("dim-label")
        self.desc_label.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(self.desc_label)
        self.append(info_box)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        right.set_valign(Gtk.Align.CENTER)
        right.set_halign(Gtk.Align.END)

        badges_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        badges_row.set_halign(Gtk.Align.END)
        self.status_badge = Gtk.Label()
        self.status_badge.add_css_class("row-status-pill")
        badges_row.append(self.status_badge)
        self.repo_badge = Gtk.Label()
        self.repo_badge.add_css_class("badge")
        badges_row.append(self.repo_badge)
        right.append(badges_row)

        self.ver_label = Gtk.Label()
        self.ver_label.add_css_class("caption")
        self.ver_label.add_css_class("dim-label")
        self.ver_label.set_halign(Gtk.Align.END)
        right.append(self.ver_label)
        self.append(right)

    def bind(self, pkg, sel_state=None):
        # Alten Backpointer entfernen, falls dieses Widget recycelt wird
        if self.pkg and hasattr(self.pkg, "_bound_widget") and self.pkg._bound_widget == self:
            self.pkg._bound_widget = None

        self.pkg = pkg
        self.sel_state = sel_state

        if pkg:
            pkg._bound_widget = self

        tex = get_icon_texture(pkg_icon(pkg.pkg_name), 22)
        if tex is not None:
            self.icon.set_from_paintable(tex)
        else:
            self.icon.set_from_icon_name(pkg_icon(pkg.pkg_name))
        self.name_label.set_label(pkg.pkg_name)
        self.desc_label.set_label(pkg.pkg_description or "")
        self.desc_label.set_visible(bool(pkg.pkg_description))

        # Visuelle Darstellung updaten
        self.update_selection_visuals()

        # Status pill — only for installed/update; clear stale classes first
        for cls in _STATUS_PILL_CSS:
            self.status_badge.remove_css_class(cls)
        if pkg.pkg_status in ("installed", "update"):
            is_update = pkg.pkg_status == "update"
            self.status_badge.set_label(tr("UPDATE") if is_update else tr("INSTALLED"))
            self.status_badge.add_css_class("status-update" if is_update else "status-installed")
            self.status_badge.set_visible(True)
        else:
            self.status_badge.set_visible(False)

        # Repo badge — swap class on every rebind
        repo_str = "aur" if pkg.pkg_foreign else (pkg.pkg_repo or "local")
        for cls in _REPO_BADGE_CSS:
            self.repo_badge.remove_css_class(cls)
        self.repo_badge.set_label(repo_str.upper())
        self.repo_badge.add_css_class(REPO_BADGE_CLASS.get(repo_str.lower(), "badge-local"))

        self.ver_label.set_label(pkg.pkg_version or "")

    def update_selection_visuals(self):
        """Aktualisiert rein die Checkbox-Anzeige ohne komplettes Rebinden der Zeile."""
        if self.pkg and self.sel_state and self.sel_state.active:
            self.checkbox.set_visible(True)
            is_selected = self.pkg.pkg_name in self.sel_state.selected
            self.checkbox_mark.set_visible(is_selected)
            if is_selected:
                self.checkbox.add_css_class("pkg-checkbox-checked")
                self.add_css_class("pkg-row-selected")
            else:
                self.checkbox.remove_css_class("pkg-checkbox-checked")
                self.remove_css_class("pkg-row-selected")
        else:
            self.checkbox.set_visible(False)
            self.remove_css_class("pkg-row-selected")


def make_package_listview(on_activate, on_selection_change=None, sel_state=None):
    """Build a virtualized package ListView backed by a Gio.ListStore.

    Returns (listview, store, selection, sel_state).
    """
    store = Gio.ListStore(item_type=PackageItem)
    selection = Gtk.SingleSelection(model=store)
    selection.set_autoselect(False)
    selection.set_can_unselect(True)

    if sel_state is None:
        sel_state = ListSelectionState()

    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", lambda f, li: li.set_child(PackageRowContent()))
    factory.connect("bind", lambda f, li: li.get_child().bind(li.get_item(), sel_state))

    listview = Gtk.ListView(model=selection, factory=factory)
    listview.add_css_class("navigation-sidebar")
    listview.set_single_click_activate(True)

    def _activate(lv, pos):
        item = store.get_item(pos)
        if item is None:
            return
        if sel_state.active:
            name = item.pkg_name
            if name in sel_state.selected:
                sel_state.selected.discard(name)
            else:
                sel_state.selected.add(name)
            
            # Anstatt store.splice aufzurufen (was das Selektionsmodell bricht),
            # triggern wir das Update direkt auf dem aktuell sichtbaren Widget.
            if hasattr(item, "_bound_widget") and item._bound_widget:
                item._bound_widget.update_selection_visuals()
            
            if on_selection_change:
                on_selection_change()
        else:
            on_activate(item)

    listview.connect("activate", _activate)
    return listview, store, selection, sel_state


# ─── Sidebar navigation row ───────────────────────────────────────────────────

class NavRow(Gtk.ListBoxRow):
    def __init__(self, icon_name, label, count=None, badge_css=None):
        super().__init__()
        self.add_css_class("nav-row")
        self.set_activatable(True)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(7);    box.set_margin_bottom(7)
        box.set_margin_start(10); box.set_margin_end(10)

        icon = make_icon(icon_name, 18)
        icon.set_valign(Gtk.Align.CENTER)
        icon.add_css_class("dim-label")
        box.append(icon)

        lbl = Gtk.Label(label=label)
        lbl.set_hexpand(True)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_valign(Gtk.Align.CENTER)
        box.append(lbl)

        self.count_lbl = None
        if count is not None:
            self.count_lbl = Gtk.Label(label=str(count))
            self.count_lbl.add_css_class("count-badge")
            if badge_css:
                self.count_lbl.add_css_class(badge_css)
            self.count_lbl.set_valign(Gtk.Align.CENTER)
            self.count_lbl.set_visible(int(str(count)) > 0 if str(count).isdigit() else True)
            box.append(self.count_lbl)

        self._badge_css = badge_css
        self.set_child(box)

    def set_count(self, n):
        if self.count_lbl:
            self.count_lbl.set_label(str(n))
            self.count_lbl.set_visible(n > 0)