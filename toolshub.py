"""
Pachul — toolshub.py
The "Tools" hub: one searchable overview of every tool Pachul offers,
grouped by category, opened from the header-bar button (Ctrl+T).

Each entry simply triggers the existing GAction (``app.<name>``), so all the
real work — and every distro-specific condition — stays where it already
was. To add a new tool later, add ONE line to tool_entries() below (plus the
GAction in app.py); no menu rebuilding needed.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

import distro
from i18n import tr
from models import make_icon


def _clean(title):
    """Menu labels end in '…' when they open a dialog; on a card that's noise."""
    return title.replace("…", "").strip()


def tool_entries(win):
    """[(category_title, [(action, icon, title, description), …]), …]

    Built fresh on every call so it follows the current language, and only
    contains tools that actually work on this distro (same conditions the
    old menu used)."""
    hold_ok = getattr(win, "_hold_supported", False)

    # ── Software & sources ───────────────────────────────────────────────
    software = [
        ("install_local", "package-x-generic-symbolic",
         tr("Install Local Package…"),
         tr("Install a downloaded .tar.gz, .pkg.tar.*, .deb, .rpm or .flatpak file")),
        ("manage_repos", "network-server-symbolic",
         tr("Manage Repositories…"),
         # On Arch this dialog lists the active repos and edits pacman.conf
         # (no per-repo switches — those exist only for apt/dnf/zypper).
         tr("Show the active repositories and edit pacman.conf")
         if distro.is_arch() else
         tr("Enable, disable or add software sources")),
    ]
    if distro.is_arch():
        software.append(
            ("rate_mirrors", "network-transmit-receive-symbolic",
             tr("Find Fastest Mirrors…"),
             tr("Rank mirrors by speed to make downloads faster")))
    software += [
        ("tool_updates", "software-update-available-symbolic",
         tr("More Update Sources…"),
         tr("Check developer and system tools that normal upgrades don't cover")),
        ("import_pkgs", "list-add-symbolic",
         tr("Import Package List…"),
         tr("Install all packages from a saved list")),
        ("export_pkgs", "go-down-symbolic",
         tr("Export Package List…"),
         tr("Save the names of your installed programs to a file")),
    ]

    # ── Maintenance ──────────────────────────────────────────────────────
    cfg_title = (tr("Config Files (.pacnew)…") if distro.is_arch()
                 else tr("Config File Conflicts…"))
    maintenance = [
        ("orphans", "user-trash-symbolic",
         tr("Find Orphans"),
         tr("Remove packages that nothing depends on anymore")),
        ("cache", "folder-download-symbolic",
         tr("Cache Cleaner"),
         tr("Free disk space used by downloaded package files")),
        ("pacdiff", "text-editor-symbolic",
         cfg_title,
         tr("Compare and merge configuration files left behind by updates")),
    ]
    if hold_ok:
        maintenance.append(
            ("ignored", "dialog-password-symbolic",
             tr("Ignored Packages…"),
             tr("Packages that are held back from upgrades")))
    maintenance += [
        ("history", "document-open-recent-symbolic",
         tr("Package History…"),
         tr("See what was installed, upgraded or removed, and when")),
        ("file_search", "system-search-symbolic",
         tr("Find Package by File…"),
         tr("Find out which package a file belongs to")),
    ]

    # ── Repair ───────────────────────────────────────────────────────────
    repair = []
    if distro.is_arch():
        repair.append(("pacman_repair", "utilities-terminal-symbolic",
                       tr("Repair System (pacman)…"),
                       tr("Refresh databases, check integrity, reset the keyring")))
    if distro.is_debian():
        repair.append(("apt_repair", "utilities-terminal-symbolic",
                       tr("Repair System (apt/dpkg)…"),
                       tr("Fix broken packages and interrupted installations")))
    if distro.is_fedora():
        repair.append(("dnf_repair", "utilities-terminal-symbolic",
                       tr("Repair System (dnf/rpm)…"),
                       tr("Sync with the repositories, rebuild the RPM database, clean caches")))
    if distro.is_suse():
        repair.append(("zypper_repair", "utilities-terminal-symbolic",
                       tr("Repair System (zypper/rpm)…"),
                       tr("Verify packages, rebuild the RPM database, clean caches")))
    repair += [
        ("cert_checker", "emblem-ok-symbolic",
         tr("Check Certificates…"),
         tr("Find expired or broken certificates")),
        ("broken_symlinks", "edit-clear-all-symbolic",
         tr("Find Broken Symlinks…"),
         tr("Find and clean up dangling symbolic links")),
    ]

    # ── System ───────────────────────────────────────────────────────────
    system = [
        ("sysinfo", "utilities-system-monitor-symbolic",
         tr("System Info"),
         tr("Operating system, kernel, hardware and package statistics")),
        ("services_security", "preferences-system-symbolic",
         tr("Services & Security…"),
         tr("Failed services, firewall and SSH settings at a glance")),
        ("config_backup", "drive-harddisk-symbolic",
         tr("Configuration Backup…"),
         tr("Back up your system's important configuration files")),
    ]

    return [
        (tr("Software & Sources"), software),
        (tr("Maintenance"), maintenance),
        (tr("Repair"), repair),
        (tr("System"), system),
    ]


def package_entries(win):
    """Same shape as tool_entries(): the package actions of the \"Packages\"
    header-bar entry, with a short help text each. Entries only appear where
    their backend works on this distro (same conditions as before)."""
    updates = [
        ("sync", "network-transmit-receive-symbolic",
         tr("Sync Databases"),
         tr("Download the latest package lists from the repositories")),
        ("check_updates", "software-update-available-symbolic",
         tr("Check for Updates"),
         tr("See which packages have a newer version available")),
        ("refresh", "view-refresh-symbolic",
         tr("Refresh List"),
         tr("Reload the list of installed and available packages")),
    ]
    selected = []
    if distro.is_arch():
        selected.append(
            ("pkgbuild", "text-x-script-symbolic",
             tr("View PKGBUILD (AUR)…"),
             tr("Read the build script of the selected AUR package before installing")))
    if getattr(win, "_hold_supported", False):
        selected.append(
            ("hold", "dialog-password-symbolic",
             tr("Hold / Unhold Selected"),
             tr("Keep the selected packages at their current version, or release them again")))
    if getattr(win, "_mark_reason_supported", False):
        selected += [
            ("mark_explicit", "starred-symbolic",
             tr("Mark Selected as Explicit"),
             tr("Treat the selected packages as installed on purpose, so they are not offered for removal as orphans")),
            ("mark_asdeps", "edit-select-all-symbolic",
             tr("Mark Selected as Dependency"),
             tr("Treat the selected packages as pulled in by others, so they can be cleaned up as orphans once unused")),
        ]
    return [
        (tr("Updates & Sync"), updates),
        (tr("Selected Packages"), selected),
    ]


def show_tools_dialog(win):
    """Open the searchable tools overview over *win* (the main window)."""
    _show_hub(win, tr("Tools"), tool_entries,
              tr("Search tools…"), tr("No tools found"), searchable=True)


def show_packages_dialog(win):
    """Open the package actions overview (header-bar \"Packages\" entry),
    styled like the tools hub."""
    _show_hub(win, tr("Packages"), package_entries,
              "", "", searchable=False)


def _show_hub(win, title, entries_fn, placeholder, empty_title, searchable):
    # A real Adw.Window (like the other dialogs) instead of Adw.Dialog, so
    # it can be moved and resized freely. Its height follows the main
    # window's current height.
    dialog = Adw.Window()
    dialog.set_title(title)
    win_h = win.get_height() or 780
    dialog.set_default_size(640, max(640, win_h))
    dialog.set_resizable(True)
    dialog.set_transient_for(win)
    dialog.set_modal(True)

    esc = Gtk.EventControllerKey()
    esc.connect("key-pressed", lambda _c, kv, *_: (dialog.close(), True)[1]
                if kv == Gdk.KEY_Escape else False)
    dialog.add_controller(esc)

    tv = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    search = Gtk.SearchEntry()
    search.set_placeholder_text(placeholder)
    search.set_hexpand(True)
    if searchable:
        search_box = Gtk.Box()
        search_box.set_margin_start(12); search_box.set_margin_end(12)
        search_box.set_margin_top(6);    search_box.set_margin_bottom(6)
        search_box.append(search)
        tv.add_top_bar(search_box)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    outer.set_margin_top(6);    outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    # (group_widget, [(row, haystack), …]) — kept for live filtering
    groups = []
    all_rows = []

    def _launch(action):
        dialog.close()
        app = win.get_application()
        # idle: let the dialog finish closing first, so the next dialog is
        # presented over the main window instead of a half-closed sheet.
        GLib.idle_add(lambda: (app.activate_action(action, None), False)[1])

    for cat_title, entries in entries_fn(win):
        if not entries:
            continue
        group = Adw.PreferencesGroup()
        group.set_title(GLib.markup_escape_text(cat_title))
        rows = []
        for action, icon, title, desc in entries:
            title = _clean(title)
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(title))
            row.set_subtitle(GLib.markup_escape_text(desc))
            row.set_subtitle_lines(2)
            row.set_activatable(True)
            ic = make_icon(icon, 20)
            ic.add_css_class("dim-label")
            row.add_prefix(ic)
            arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
            arrow.add_css_class("dim-label")
            row.add_suffix(arrow)
            row.connect("activated", lambda _r, a=action: _launch(a))
            group.add(row)
            rows.append((row, f"{title} {desc} {cat_title}".casefold()))
            all_rows.append(row)
        groups.append((group, rows))
        outer.append(group)

    empty = Adw.StatusPage()
    empty.set_icon_name("system-search-symbolic")
    empty.set_title(empty_title)
    empty.set_description(tr("Try a different search term."))
    empty.set_visible(False)
    outer.append(empty)

    def _filter(*_):
        q = search.get_text().strip().casefold()
        any_visible = False
        for group, rows in groups:
            shown = 0
            for row, hay in rows:
                vis = (not q) or all(w in hay for w in q.split())
                row.set_visible(vis)
                shown += vis
            group.set_visible(shown > 0)
            any_visible = any_visible or shown > 0
        empty.set_visible(not any_visible)

    def _first_visible(*_):
        for row in all_rows:
            if row.get_visible():
                row.activate()
                return

    search.connect("search-changed", _filter)
    search.connect("activate", _first_visible)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    if searchable:
        dialog.set_focus(search)
    dialog.present()
