"""
Pachul — window.py
Main application window: sidebar, package list with an integrated search
entry, detail panel, filtering, and all action handlers.
"""

import os
import shlex
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Pango

from backend import (
    get_packages, get_package_info, get_package_files,
    check_updates, search_packages_cmd, run_command,
    invalidate_cache, invalidate_syncdb_cache, get_explicit_packages,
    get_ignored_packages, set_package_ignored, get_setting,
    build_snapshot_cmd, flatpak_available, snap_available,
    is_pachul_installed, build_install_command,
)
from models import (
    PackageItem, NavRow, REPO_BADGE_CLASS, pkg_icon, make_package_listview,
    make_icon, set_button_icon, ListSelectionState,
)
from icons import themed_image, themed_paintable, get_icon_texture

# Directory this module (and app.py) live in — used to find install.sh
# next to a source checkout, and as the tray.py path for the autostart
# entry before Pachul has been installed system-wide.
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Fallback chains for icon names that are missing in some icon themes
# (notably KDE Breeze), which otherwise show up as a red/pink broken icon.
ICON_UPDATE_AVAILABLE = [
    "software-update-available-symbolic", "software-update-available",
    "system-software-update-symbolic", "view-refresh-symbolic",
]
ICON_RATE_MIRRORS = [
    "network-transmit-receive-symbolic", "network-wired-symbolic",
    "network-workgroup-symbolic", "preferences-system-network-symbolic",
    "view-refresh-symbolic",
]
ICON_CLEAN_CACHE = [
    "folder-download-symbolic", "edit-clear-all-symbolic",
    "user-trash-symbolic", "folder-symbolic",
]
from i18n import tr, get_language
from dialogs import (
    run_terminal_dialog,
    show_sync_db_dialog,
    show_repo_manager,
    show_mirror_rater,
    show_orphan_finder,
    show_clean_cache_dialog,
    show_import_pkgs_dialog,
    show_import_pkgs_intro,
    show_export_pkgs_intro,
    show_hold_dialog,
    show_mark_asdeps_dialog,
    show_file_search_dialog,
    show_sysinfo_dialog,
    show_history_dialog,
    show_downgrade_dialog,
    show_pkgbuild_dialog,
    show_pacdiff_dialog,
    show_preferences,
    show_news_dialog,
    show_shortcuts_dialog,
)


class DetailPanel:
    """Right-hand package detail view: hero header + Info tab + Files tab.

    One instance is built for the main list page and one for the search page.
    pachulWindow drives both through the same _show_detail / _populate_detail
    methods, so the two views can never drift apart.

    Widget references live on the instance (icon, name, status, info_rows, …);
    `dep_callback` is set by the window to route dependency-chip clicks. The
    Files tab is a virtualized ListView whose FilterListModel does the
    filtering, so the search box never rebuilds rows.
    """

    INFO_KEYS = [
        "URL", "Licenses", "Groups", "Depends On", "Optional Deps", "Required By",
        "Conflicts With", "Provides", "Replaces",
        "Installed Size", "Packager", "Build Date", "Install Date", "Install Reason",
    ]
    # Fields rendered as expandable clickable-chip flows rather than plain rows
    DEP_KEYS = ("Depends On", "Optional Deps", "Required By")

    def __init__(self, action_btn, on_install, on_remove, on_reinstall, on_downgrade):
        self.dep_callback = None   # set by the window: takes a dependency name
        self.info_rows = {}        # key -> ActionRow / ExpanderRow
        self.dep_rows = {}         # key -> (ExpanderRow, FlowBox)
        self._files_query = ""     # current Files-tab filter text (lowercased)
        self._files_loading = False
        self._build(action_btn, on_install, on_remove, on_reinstall, on_downgrade)

    def _build(self, action_btn, on_install, on_remove, on_reinstall, on_downgrade):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty.set_valign(Gtk.Align.CENTER); empty.set_halign(Gtk.Align.CENTER)
        empty.set_vexpand(True); empty.set_hexpand(True)
        empty_icon = themed_image("package-x-generic-symbolic", 36)
        empty_icon.add_css_class("dim-label")
        empty_icon.set_halign(Gtk.Align.CENTER)
        empty.append(empty_icon)
        empty_title = Gtk.Label(label=tr("Select a Package"))
        empty_title.add_css_class("title-4")
        empty_title.set_halign(Gtk.Align.CENTER)
        empty_title.set_justify(Gtk.Justification.CENTER)
        empty.append(empty_title)
        empty_desc = Gtk.Label(
            label=tr("Choose a package to view its details, files, and dependencies."))
        empty_desc.add_css_class("dim-label")
        empty_desc.set_halign(Gtk.Align.CENTER)
        empty_desc.set_justify(Gtk.Justification.CENTER)
        empty_desc.set_wrap(True)
        empty_desc.set_max_width_chars(40)
        empty.append(empty_desc)
        self.stack.add_named(empty, "empty")

        # Batch selection overview
        batch_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        batch_page.set_margin_top(16); batch_page.set_margin_bottom(24)
        batch_page.set_margin_start(20); batch_page.set_margin_end(20)

        batch_header = Gtk.Label(label=tr("Selected Packages"))
        batch_header.add_css_class("title-2")
        batch_header.set_halign(Gtk.Align.START)
        batch_page.append(batch_header)

        self.batch_listbox = Gtk.ListBox()
        self.batch_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.batch_listbox.add_css_class("boxed-list")
        batch_scroll = Gtk.ScrolledWindow()
        batch_scroll.set_vexpand(True)
        batch_scroll.set_child(self.batch_listbox)
        batch_page.append(batch_scroll)

        self.stack.add_named(batch_page, "batch")
        self.stack.set_visible_child_name("empty")

        # ---- Detail view (unchanged) ----
        detail_scroll = Gtk.ScrolledWindow()
        detail_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        detail_box.set_margin_top(16);   detail_box.set_margin_bottom(24)
        detail_box.set_margin_start(20); detail_box.set_margin_end(20)

        # Hero
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        hero.add_css_class("pkg-hero")
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.icon = Gtk.Image()
        self.icon.set_pixel_size(58); self.icon.set_valign(Gtk.Align.CENTER)
        _tex = get_icon_texture("package-x-generic-symbolic", 58)
        if _tex is not None:
            self.icon.set_from_paintable(_tex)
        else:
            self.icon.set_from_icon_name("package-x-generic-symbolic")
        top_row.append(self.icon)
        title_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_col.set_hexpand(True); title_col.set_valign(Gtk.Align.CENTER)
        self.name = Gtk.Label(label=tr("Package"))
        self.name.set_halign(Gtk.Align.START); self.name.add_css_class("title-2")
        title_col.append(self.name)
        self.desc = Gtk.Label(label=tr("Description"))
        self.desc.set_halign(Gtk.Align.START); self.desc.add_css_class("body")
        self.desc.add_css_class("dim-label"); self.desc.set_wrap(True)
        self.desc.set_wrap_mode(Pango.WrapMode.WORD)
        title_col.append(self.desc)
        top_row.append(title_col)
        self.status = Gtk.Label(label=tr("INSTALLED"))
        self.status.add_css_class("status-pill"); self.status.add_css_class("status-installed")
        self.status.set_valign(Gtk.Align.START)
        top_row.append(self.status)
        hero.append(top_row)

        meta_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.ver_badge = Gtk.Label(label="1.0.0")
        self.ver_badge.add_css_class("badge"); self.ver_badge.add_css_class("badge-local")
        meta_row.append(self.ver_badge)
        self.repo_badge = Gtk.Label(label="CORE")
        self.repo_badge.add_css_class("badge"); self.repo_badge.add_css_class("badge-core")
        meta_row.append(self.repo_badge)
        self.arch_badge = Gtk.Label(label="x86_64")
        self.arch_badge.add_css_class("badge"); self.arch_badge.add_css_class("badge-local")
        meta_row.append(self.arch_badge)
        hero.append(meta_row)

        hero_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.btn_install = action_btn(
            "package-x-generic-symbolic", tr("Install"),
            "suggested-action", "install-btn", callback=on_install)
        self.btn_install.set_sensitive(False)
        self.btn_remove = action_btn(
            "user-trash-symbolic", tr("Uninstall"),
            "destructive-action", "remove-btn", callback=on_remove)
        self.btn_remove.set_sensitive(False)
        self.btn_reinstall = action_btn(
            "view-refresh-symbolic", tr("Reinstall"), callback=on_reinstall)
        self.btn_reinstall.set_sensitive(False)
        self.btn_reinstall.add_css_class("flat")
        self.btn_downgrade = action_btn(
            "go-down-symbolic", tr("Downgrade"), callback=on_downgrade)
        self.btn_downgrade.set_sensitive(False)
        self.btn_downgrade.add_css_class("flat")
        hero_actions.append(self.btn_install)
        hero_actions.append(self.btn_remove)
        hero_actions.append(self.btn_reinstall)
        hero_actions.append(self.btn_downgrade)
        hero.append(hero_actions)
        detail_box.append(hero)

        # Tabs
        self.view_stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(self.view_stack)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        detail_box.append(switcher)

        # Info tab
        info_scroll = Gtk.ScrolledWindow()
        info_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        info_scroll.set_min_content_height(200)
        info_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        info_inner.set_margin_start(4); info_inner.set_margin_end(4)
        info_group = Adw.PreferencesGroup()
        info_group.set_title(tr("Package Information"))
        info_inner.append(info_group)
        for key in self.INFO_KEYS:
            if key in self.DEP_KEYS:
                exp_row = Adw.ExpanderRow()
                exp_row.set_title(tr(key)); exp_row.set_subtitle("—")
                flow = Gtk.FlowBox()
                flow.set_selection_mode(Gtk.SelectionMode.NONE)
                flow.set_column_spacing(6); flow.set_row_spacing(6)
                flow.set_margin_start(12); flow.set_margin_end(12)
                flow.set_margin_top(8); flow.set_margin_bottom(10)
                flow_row = Gtk.ListBoxRow()
                flow_row.set_activatable(False)
                flow_row.set_child(flow)
                exp_row.add_row(flow_row)
                info_group.add(exp_row)
                self.dep_rows[key] = (exp_row, flow)
                self.info_rows[key] = exp_row
            else:
                row = Adw.ActionRow()
                row.set_title(tr(key)); row.set_subtitle("—")
                row.set_subtitle_selectable(True)
                info_group.add(row)
                self.info_rows[key] = row

        raw_group = Adw.PreferencesGroup()
        raw_group.set_title(tr("Raw Output"))
        info_inner.append(raw_group)
        raw_exp = Adw.ExpanderRow()
        raw_exp.set_title(tr("pacman -Qi output"))
        raw_exp.set_subtitle(tr("Full package information"))
        raw_group.add(raw_exp)
        raw_scroll = Gtk.ScrolledWindow()
        raw_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        raw_scroll.set_min_content_height(120); raw_scroll.set_max_content_height(240)
        self.raw_text = Gtk.Label(label="")
        self.raw_text.set_selectable(True); self.raw_text.set_wrap(True)
        self.raw_text.set_wrap_mode(Pango.WrapMode.CHAR)
        self.raw_text.add_css_class("monospace"); self.raw_text.add_css_class("caption")
        self.raw_text.set_xalign(0)
        self.raw_text.set_margin_start(12); self.raw_text.set_margin_end(12)
        self.raw_text.set_margin_top(8); self.raw_text.set_margin_bottom(8)
        raw_scroll.set_child(self.raw_text)
        raw_exp.add_row(raw_scroll)
        info_scroll.set_child(info_inner)
        self.view_stack.add_titled_with_icon(
            info_scroll, "info", tr("Info"), "dialog-information-symbolic")

        # Files tab — virtualized ListView with a FilterListModel doing the
        # filtering, so typing in the search box never rebuilds the rows.
        files_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        files_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        files_hdr.set_margin_start(6); files_hdr.set_margin_end(6)
        files_hdr.set_margin_top(6); files_hdr.set_margin_bottom(4)
        self.files_search = Gtk.SearchEntry()
        self.files_search.set_placeholder_text(tr("Filter…"))
        self.files_search.set_hexpand(True)
        self.files_search.connect("search-changed", self._on_files_filter_changed)
        files_hdr.append(self.files_search)
        self.files_count_lbl = Gtk.Label(label="")
        self.files_count_lbl.add_css_class("caption"); self.files_count_lbl.add_css_class("dim-label")
        self.files_count_lbl.set_halign(Gtk.Align.END)
        files_hdr.append(self.files_count_lbl)
        files_box.append(files_hdr)

        self.files_model = Gtk.StringList()
        self.files_filter = Gtk.CustomFilter.new(self._files_match)
        self.files_filter_model = Gtk.FilterListModel(model=self.files_model,
                                                      filter=self.files_filter)
        self.files_filter_model.connect("items-changed", self._update_files_count)

        files_factory = Gtk.SignalListItemFactory()
        files_factory.connect("setup", self._files_setup)
        files_factory.connect("bind",
                              lambda f, li: li.get_child().set_label(li.get_item().get_string()))
        files_scroll = Gtk.ScrolledWindow()
        files_scroll.set_vexpand(True)
        self.files_listview = Gtk.ListView(
            model=Gtk.NoSelection(model=self.files_filter_model), factory=files_factory)
        self.files_listview.add_css_class("navigation-sidebar")
        files_scroll.set_child(self.files_listview)
        files_box.append(files_scroll)
        self.view_stack.add_titled_with_icon(
            files_box, "files", tr("Files"), "folder-symbolic")

        detail_box.append(self.view_stack)
        detail_scroll.set_child(detail_box)
        self.stack.add_named(detail_scroll, "detail")
        self.stack.set_visible_child_name("empty")

    # ── Files tab helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _files_setup(factory, list_item):
        lbl = Gtk.Label()
        lbl.set_halign(Gtk.Align.START); lbl.set_selectable(True)
        lbl.add_css_class("monospace"); lbl.add_css_class("caption")
        lbl.set_margin_start(12); lbl.set_margin_top(4); lbl.set_margin_bottom(4)
        list_item.set_child(lbl)

    def _files_match(self, item):
        return (not self._files_query) or (self._files_query in item.get_string().lower())

    def _on_files_filter_changed(self, entry):
        self._files_query = entry.get_text().strip().lower()
        self.files_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _update_files_count(self, *args):
        if self._files_loading:
            return
        total = self.files_model.get_n_items()
        shown = self.files_filter_model.get_n_items()
        self.files_count_lbl.set_label(
            tr("{shown} of {total} files").format(shown=shown, total=total)
            if self._files_query
            else tr("{total} files").format(total=total))

    def set_files_loading(self):
        """Clear the Files tab and show a loading placeholder."""
        self._files_loading = True
        self.files_model.splice(0, self.files_model.get_n_items(), [])
        self.files_count_lbl.set_label(tr("Loading…"))

    def set_files(self, files):
        """Populate the Files tab from raw `pacman -Ql` lines ("pkg /path")."""
        paths = []
        for line in files:
            parts = line.split(None, 1)
            paths.append(parts[1] if len(parts) == 2 else line)
        self._files_loading = False
        self.files_model.splice(0, self.files_model.get_n_items(), paths)
        self._update_files_count()

    # ── Batch selection display ──────────────────────────────────────────────

    def show_batch(self, pkg_names):
        """Display a list of selected package names in the detail panel."""
        # Clear the listbox
        while self.batch_listbox.get_first_child():
            self.batch_listbox.remove(self.batch_listbox.get_first_child())

        if not pkg_names:
            self.stack.set_visible_child_name("empty")
            return

        for name in sorted(pkg_names):
            row = Adw.ActionRow()
            row.set_title(name)
            icon = themed_image("package-x-generic-symbolic", 18)
            icon.add_css_class("dim-label")
            row.add_prefix(icon)
            self.batch_listbox.append(row)

        self.stack.set_visible_child_name("batch")


class pachulWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Pachul")
        self.set_default_size(1240, 780)
        self.set_size_request(900, 560)
        self._all_packages     = []
        self._selected_pkg     = None
        self._current_filter   = "not_installed"  # matches the "New Packages" row _build_sidebar()
                                          # selects by default (nav_listbox.select_row() below
                                          # doesn't fire row-activated, so this has to be set here too)
        self._search_query     = ""      # current text in the always-visible search entry
        self._updates          = None
        self._aur_helper_cache = None
        self._search_timer     = None   # GLib source id for debounced search
        self._alive            = True   # set False on close to stop background workers
        self._current_lang     = get_language()
        self.connect("close-request", self._on_close_request)
        self._build_ui()
        self._load_packages()
        GLib.idle_add(self._maybe_offer_install)

        # Add "select all" action with Ctrl+A shortcut
        select_all_action = Gio.SimpleAction.new("select_all", None)
        select_all_action.connect("activate", self._on_select_all)
        self.add_action(select_all_action)
        app.set_accels_for_action("win.select_all", ["<Ctrl>a"])

        # Add "deselect all" action with Ctrl+Shift+A shortcut
        deselect_all_action = Gio.SimpleAction.new("deselect_all", None)
        deselect_all_action.connect("activate", self._on_deselect_all)
        self.add_action(deselect_all_action)
        app.set_accels_for_action("win.deselect_all", ["<Ctrl><Shift>a"])

    def _on_close_request(self, *_):
        self._alive = False
        self._cancel_search_timer()
        return False   # allow window to close

    def _maybe_offer_install(self):
        """Offer to run install.sh if Pachul is running from a source
        checkout that was never installed system-wide. A no-op once
        installed (or when there's no install.sh next to this copy, e.g.
        an installed copy itself, which doesn't ship one)."""
        if is_pachul_installed():
            return False
        cmd = build_install_command(APP_DIR)
        if not cmd:
            return False

        d = Adw.AlertDialog()
        d.set_heading(tr("Install Pachul?"))
        d.set_body(tr(
            "Pachul isn't installed system-wide yet. Installing adds an "
            "app-menu entry and the pachul / pachul-tray commands, and "
            "installs any missing dependencies — this needs your password."))
        d.add_response("skip", tr("Not Now"))
        d.add_response("install", tr("Install"))
        d.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("install")
        d.set_close_response("skip")

        def _on_response(_dlg, resp):
            if resp == "install":
                run_terminal_dialog(
                    self, cmd, tr("Install Pachul"),
                    on_success=lambda: self._toast(
                        tr("Pachul installed — available from the app menu from now on.")))
        d.connect("response", _on_response)
        d.present(self)
        return False   # GLib.idle_add: run once

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.nav_split = Adw.NavigationSplitView()
        self.nav_split.set_max_sidebar_width(230)
        self.nav_split.set_min_sidebar_width(190)
        self.nav_split.set_sidebar_width_fraction(0.20)

        # Sidebar
        sidebar_page = Adw.NavigationPage()
        sidebar_page.set_title("Pachul")
        sidebar_tv  = Adw.ToolbarView()
        sidebar_hdr = Adw.HeaderBar()
        sidebar_hdr.set_show_end_title_buttons(False)
        title_lbl = Gtk.Label(label="Pachul")
        title_lbl.add_css_class("heading")
        sidebar_hdr.set_title_widget(title_lbl)
        sidebar_tv.add_top_bar(sidebar_hdr)
        sidebar_tv.set_content(self._build_sidebar())
        sidebar_page.set_child(sidebar_tv)
        self.nav_split.set_sidebar(sidebar_page)

        # Content
        content_page = Adw.NavigationPage()
        content_page.set_title("Pachul")
        self.content_tv  = Adw.ToolbarView()
        self.content_hdr = Adw.HeaderBar()
        self.content_hdr.set_show_back_button(False)
        self.content_hdr.set_show_title(False)

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_child(themed_image("open-menu-symbolic", 18))
        menu_btn.add_css_class("image-button")
        menu_btn.add_css_class("flat")
        menu = Gio.Menu()
        menu.append(tr("Sync Databases"),       "app.sync")
        menu.append(tr("Check for Updates"),    "app.check_updates")
        menu.append(tr("Refresh List"),         "app.refresh")
        menu.append_section(None, Gio.Menu())
        menu.append(tr("Manage Repositories…"), "app.manage_repos")
        menu.append(tr("Rate Mirrors…"),        "app.rate_mirrors")
        menu.append_section(None, Gio.Menu())
        menu.append(tr("Find Orphans"),         "app.orphans")
        menu.append(tr("Find Package by File…"), "app.file_search")
        menu.append(tr("Config Files (.pacnew)…"), "app.pacdiff")
        menu.append(tr("Package History…"),     "app.history")
        menu.append(tr("System Info"),          "app.sysinfo")
        menu.append(tr("Cache Cleaner"),        "app.cache")
        menu.append_section(None, Gio.Menu())
        menu.append(tr("Export Package List…"), "app.export_pkgs")
        menu.append(tr("Import Package List…"), "app.import_pkgs")
        menu.append_section(None, Gio.Menu())
        menu.append(tr("View PKGBUILD (AUR)…"),         "app.pkgbuild")
        menu.append(tr("Hold / Unhold Selected"),       "app.hold")
        menu.append(tr("Mark Selected as Explicit"),    "app.mark_explicit")
        menu.append(tr("Mark Selected as Dependency"),  "app.mark_asdeps")
        menu.append_section(None, Gio.Menu())
        menu.append(tr("Preferences"),          "app.preferences")
        menu.append(tr("Keyboard Shortcuts"),   "app.shortcuts")
        menu.append(tr("About Pachul"),         "app.about")
        menu_btn.set_menu_model(menu)
        right_box.append(menu_btn)
        self.content_hdr.pack_end(right_box)
        self.content_tv.add_top_bar(self.content_hdr)

        # Shared selection-mode state: one flag + one selected-name set,
        # kept as its own object since the package list panel is rebuilt
        # (e.g. on language change) while this state should persist.
        self.pkg_sel_state = ListSelectionState()

        self.content_tv.set_content(self._build_list_detail_paned())
        content_page.set_child(self.content_tv)
        self.nav_split.set_content(content_page)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self.nav_split)
        self.set_content(self._toast_overlay)

    # ── List + Detail ────────────────────────────────────────────────────────

    def _build_list_detail_paned(self):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_start_child(self._build_package_list_panel())
        paned.set_resize_start_child(True)
        paned.set_shrink_start_child(False)
        paned.set_end_child(self._build_detail_panel())
        paned.set_resize_end_child(True)
        paned.set_shrink_end_child(False)
        paned.set_position(460)
        return paned

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(8); outer.set_margin_bottom(16)

        # Stat strip
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        stats_box.set_margin_start(10); stats_box.set_margin_end(10)
        stats_box.set_margin_top(4); stats_box.set_margin_bottom(12)
        self.stat_total   = self._stat_card("—", tr("TOTAL"),   "stat-card")
        self.stat_aur     = self._stat_card("—", tr("AUR"),     "stat-card-aur")
        self.stat_updates = self._stat_card("—", tr("UPDATES"), "stat-card-updates")
        for card in (self.stat_total, self.stat_aur, self.stat_updates):
            stats_box.append(card)
        outer.append(stats_box)

        # Browse
        self.nav_listbox = Gtk.ListBox()
        self.nav_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_listbox.add_css_class("navigation-sidebar")
        self.nav_listbox.set_margin_start(5); self.nav_listbox.set_margin_end(5)
        self.nav_listbox.connect("row-activated", self._on_nav_selected)

        self._nav_rows = {}
        browse_items = [
            ("not_installed", "list-add-symbolic",                  tr("New Packages"),   0,    "count-new"),
            ("all",           "view-list-symbolic",                 tr("All Packages"),   None, None),
            ("installed",     "emblem-ok-symbolic",                 tr("Installed"),      0,    None),
            ("updates",       ICON_UPDATE_AVAILABLE,               tr("Updates"),         0,    "count-update"),
        ]
        for key, icon, label, cnt, badge_cls in browse_items:
            row = NavRow(icon, label, cnt, badge_cls)
            self.nav_listbox.append(row)
            self._nav_rows[key] = row
        self.nav_listbox.select_row(self.nav_listbox.get_row_at_index(0))
        outer.append(self.nav_listbox)

        # Repositories
        outer.append(self._separator())
        outer.append(self._sidebar_header(tr("REPOSITORIES")))
        self.repo_listbox = Gtk.ListBox()
        self.repo_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.repo_listbox.add_css_class("navigation-sidebar")
        self.repo_listbox.set_margin_start(5); self.repo_listbox.set_margin_end(5)
        self.repo_listbox.connect("row-activated", self._on_repo_nav_selected)

        self._repo_nav_rows = {}
        self._repo_icon_map = {
            "core":      "drive-harddisk-symbolic",
            "extra":     "folder-symbolic",
            "multilib":  "folder-symbolic",
            "aur":       "application-x-executable-symbolic",
            "community": "folder-open-symbolic",
            "testing":   "folder-visiting-symbolic",
            "flatpak":   "package-x-generic-symbolic",
            "snap":      "package-x-generic-symbolic",
            "chaotic-aur": "folder-remote-symbolic",
        }
        for key in ("core", "extra", "multilib", "aur"):
            row = NavRow(self._repo_icon_map[key], key, 0, "count-badge")
            self.repo_listbox.append(row)
            self._repo_nav_rows[key] = row
        outer.append(self.repo_listbox)

        # Tools
        outer.append(self._separator())
        outer.append(self._sidebar_header(tr("TOOLS")))
        tools_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        tools_box.set_margin_start(5); tools_box.set_margin_end(5); tools_box.set_margin_bottom(4)
        for icon_name, btn_label, cb in [
            (ICON_RATE_MIRRORS,        tr("Rate Mirrors"),  self._on_rate_mirrors),
            ("user-trash-symbolic",    tr("Find Orphans"),  self._on_show_orphans),
            (ICON_CLEAN_CACHE,         tr("Clean Cache"),   self._on_clean_cache),
        ]:
            btn = Gtk.Button()
            btn.add_css_class("flat"); btn.add_css_class("nav-row")
            row_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row_inner.set_margin_top(5); row_inner.set_margin_bottom(5); row_inner.set_margin_start(10)
            ic = make_icon(icon_name, 18)
            ic.set_valign(Gtk.Align.CENTER); ic.add_css_class("dim-label")
            lbl_w = Gtk.Label(label=btn_label)
            lbl_w.set_halign(Gtk.Align.START); lbl_w.set_valign(Gtk.Align.CENTER)
            row_inner.append(ic); row_inner.append(lbl_w)
            btn.set_child(row_inner)
            btn.connect("clicked", cb)
            tools_box.append(btn)
        outer.append(tools_box)

        scroll.set_child(outer)
        return scroll

    def _sidebar_header(self, text):
        lbl = Gtk.Label(label=text)
        lbl.add_css_class("sidebar-section")
        lbl.set_halign(Gtk.Align.CENTER); lbl.set_hexpand(True)
        return lbl

    def _separator(self):
        sep = Gtk.Separator()
        sep.set_margin_top(8); sep.set_margin_start(14); sep.set_margin_end(14)
        return sep

    def _stat_card(self, number, label, css_class="stat-card"):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.add_css_class(css_class); card.set_hexpand(True)
        num = Gtk.Label(label=number)
        num.add_css_class("stat-number"); num.add_css_class("numeric"); num.set_halign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=label)
        lbl.add_css_class("stat-label"); lbl.set_halign(Gtk.Align.CENTER)
        card.append(num); card.append(lbl)
        card._num = num
        return card

    # ── Package list panel ────────────────────────────────────────────────────

    def _build_package_list_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_margin_top(8); search_box.set_margin_bottom(8)
        search_box.set_margin_start(10); search_box.set_margin_end(10)
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text(tr("Search packages, e.g. firefox, vlc, git…"))
        self.search_entry.set_hexpand(True)
        self.search_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.PRIMARY, "system-search-symbolic")
        self.search_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, "edit-clear-symbolic")
        self.search_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, False)
        self.search_entry.connect("changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        self.search_entry.connect("icon-press", self._on_search_icon_press)
        search_box.append(self.search_entry)
        panel.append(search_box)
        panel.append(Gtk.Separator())

        self.pkg_scroll = Gtk.ScrolledWindow()
        pkg_scroll = self.pkg_scroll
        pkg_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        pkg_scroll.set_vexpand(True)
        self.pkg_listview, self.pkg_store, self.pkg_selection, self.pkg_sel_state = \
            make_package_listview(self._on_pkg_activated, self._update_batch_action_bar,
                                   sel_state=self.pkg_sel_state)
        pkg_scroll.set_child(self.pkg_listview)

        spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        spinner_box.set_halign(Gtk.Align.CENTER); spinner_box.set_valign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        sp_lbl = Gtk.Label(label=tr("Loading packages…"))
        sp_lbl.add_css_class("dim-label")
        spinner_box.append(self.spinner); spinner_box.append(sp_lbl)

        # Built to match the DetailPanel's empty-state sizing exactly (36px
        # icon, title-4) rather than Adw.StatusPage's much larger defaults,
        # so the two side-by-side empty states look consistent.
        self.empty_updates_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.empty_updates_page.set_valign(Gtk.Align.CENTER)
        self.empty_updates_page.set_halign(Gtk.Align.CENTER)
        self.empty_updates_page.set_vexpand(True)
        self.empty_updates_page.set_hexpand(True)
        _eu_icon = themed_image("emblem-ok-symbolic", 36)
        _eu_icon.add_css_class("dim-label")
        _eu_icon.set_halign(Gtk.Align.CENTER)
        self.empty_updates_page.append(_eu_icon)
        self._empty_updates_title = Gtk.Label(label=tr("System is up to date"))
        self._empty_updates_title.add_css_class("title-4")
        self._empty_updates_title.set_halign(Gtk.Align.CENTER)
        self._empty_updates_title.set_justify(Gtk.Justification.CENTER)
        self.empty_updates_page.append(self._empty_updates_title)
        self._empty_updates_desc = Gtk.Label(label=tr("No pending updates found."))
        self._empty_updates_desc.add_css_class("dim-label")
        self._empty_updates_desc.set_halign(Gtk.Align.CENTER)
        self._empty_updates_desc.set_justify(Gtk.Justification.CENTER)
        self._empty_updates_desc.set_wrap(True)
        self._empty_updates_desc.set_max_width_chars(40)
        self.empty_updates_page.append(self._empty_updates_desc)

        self.empty_generic_page = Adw.StatusPage()
        self.empty_generic_page.set_paintable(themed_paintable("system-search-symbolic", 72))
        self.empty_generic_page.set_title(tr("No Packages Found"))
        self.empty_generic_page.set_description(tr("Try a different filter or search term."))

        self.list_stack = Gtk.Stack()
        self.list_stack.set_vexpand(True)
        self.list_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.list_stack.add_named(spinner_box,             "loading")
        self.list_stack.add_named(pkg_scroll,              "list")
        self.list_stack.add_named(self.empty_updates_page, "empty_updates")
        self.list_stack.add_named(self.empty_generic_page, "empty_generic")
        self.list_stack.set_visible_child_name("loading")
        panel.append(self.list_stack)

        # A plain Box instead of Gtk.ActionBar, deliberately: ActionBar (like
        # GtkCenterBox) centers its middle widget by reserving symmetric
        # space matching whichever side — start or end — is wider. The
        # Install/Uninstall pair and the Upgrade-All/Check-for-Updates pair
        # are mutually exclusive here and have quite different label
        # lengths (especially once translated), so that symmetric
        # reservation kept swinging the bar's minimum width up and down as
        # the sidebar filter changed — forcing the package-list column to
        # either widen past where the divider was set, or clip its
        # content, depending on how the paned's shrink setting was
        # configured. A plain Box with only the count label set to expand
        # sidesteps that: the label gets whatever space is left over and
        # centers within it, without dictating extra minimum width.
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_bar.add_css_class("toolbar")   # same style class GtkActionBar applies itself
        action_bar.set_margin_start(6); action_bar.set_margin_end(6)
        start_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        end_box   = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Select all button
        self.btn_select_all = Gtk.Button()
        set_button_icon(self.btn_select_all, "edit-select-all-symbolic")
        self.btn_select_all.set_tooltip_text(tr("Select all visible packages"))
        self.btn_select_all.connect("clicked", self._on_select_all)
        self.btn_select_all.add_css_class("flat")
        self.btn_select_all.set_visible(True)
        start_box.append(self.btn_select_all)

        # Deselect all button
        self.btn_deselect_all = Gtk.Button()
        set_button_icon(self.btn_deselect_all, "edit-clear-all-symbolic")
        self.btn_deselect_all.set_tooltip_text(tr("Deselect all packages"))
        self.btn_deselect_all.connect("clicked", self._on_deselect_all)
        self.btn_deselect_all.add_css_class("flat")
        self.btn_deselect_all.set_visible(False)
        start_box.append(self.btn_deselect_all)

        self.btn_install = self._action_btn(
            None, tr("Install"),
            "suggested-action", "install-btn", callback=self._on_install)
        self.btn_install.set_sensitive(False)
        start_box.append(self.btn_install)

        self.pkg_count_label = Gtk.Label(label="")
        self.pkg_count_label.add_css_class("caption"); self.pkg_count_label.add_css_class("dim-label")
        self.pkg_count_label.set_hexpand(True)
        self.pkg_count_label.set_halign(Gtk.Align.CENTER)
        self.pkg_count_label.set_ellipsize(Pango.EllipsizeMode.END)

        self.btn_remove = self._action_btn(
            None, tr("Uninstall"),
            "destructive-action", "remove-btn", callback=self._on_remove)
        self.btn_remove.set_sensitive(False)
        end_box.append(self.btn_remove)

        self.btn_upgrade_all = self._action_btn(
            None, tr("Upgrade All"),
            "suggested-action", callback=self._on_upgrade)
        self.btn_upgrade_all.set_sensitive(False); self.btn_upgrade_all.set_visible(False)
        start_box.append(self.btn_upgrade_all)

        self.btn_check_updates = self._action_btn(
            None, tr("Check for Updates"), callback=self._on_check_updates)
        self.btn_check_updates.set_visible(False)
        end_box.append(self.btn_check_updates)

        action_bar.append(start_box)
        action_bar.append(self.pkg_count_label)
        action_bar.append(end_box)

        panel.append(action_bar)
        return panel

    @staticmethod
    def _set_btn_label(btn, text):
        # Buttons built by _action_btn wrap an icon + label in a Box; find the
        # Gtk.Label child and update its text.
        child = btn.get_child().get_first_child()
        while child:
            if isinstance(child, Gtk.Label):
                child.set_label(text)
                return
            child = child.get_next_sibling()

    def _action_btn(self, icon, label, *css_classes, callback=None):
        btn = Gtk.Button()
        for cls in css_classes:
            btn.add_css_class(cls)
        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        inner.set_margin_start(4); inner.set_margin_end(4)
        if icon:
            ic = themed_image(icon, 18)
            inner.append(ic)
        inner.append(Gtk.Label(label=label))
        btn.set_child(inner)
        if callback:
            btn.connect("clicked", callback)
        return btn

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _build_detail_panel(self):
        self.detail_panel = DetailPanel(
            self._action_btn, self._on_install, self._on_remove,
            self._on_reinstall, self._on_downgrade)
        self.detail_panel.dep_callback = self._lookup_dep_in_list
        return self.detail_panel.stack

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_packages(self):
        self.list_stack.set_visible_child_name("loading")
        self.spinner.start()
        threading.Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        pkgs = get_packages()
        if self._alive:
            GLib.idle_add(self._on_packages_loaded, pkgs)

    def _on_packages_loaded(self, packages):
        self._all_packages = packages
        self.spinner.stop()
        # Carry over the known update markers so a reload doesn't wipe them.
        self._reapply_update_markers()
        self._update_sidebar_counts()
        self._apply_filter()
        # Re-verify updates: on first load when the setting allows it, and on
        # every reload once we've checked before (e.g. after a package op, so
        # an updated package leaves the Updates list).
        if self._updates is not None or get_setting("check_updates_on_start"):
            threading.Thread(target=self._bg_check_updates, daemon=True).start()
        return False

    def _bg_check_updates(self):
        updates = check_updates()
        if self._alive:
            GLib.idle_add(self._on_updates_loaded, updates)

    def _notify_updates(self, n):
        app = self.get_application()
        if app is None:
            return
        notif = Gio.Notification.new(tr("Updates Available"))
        notif.set_body(
            tr("{n} package update can be installed.").format(n=n) if n == 1
            else tr("{n} package updates can be installed.").format(n=n))
        notif.set_priority(Gio.NotificationPriority.NORMAL)
        # An absolute file path, not a bare icon name — the notification
        # daemon (a separate KDE/Qt process under Plasma) resolves a name
        # against the active icon theme itself, which can silently fail
        # the same way GTK's own lookup did (see icons.py's docstring).
        icon_path = os.path.join(APP_DIR, "io.github.wergosam.pachul.svg")
        if not os.path.isfile(icon_path):
            icon_path = "/usr/share/icons/hicolor/scalable/apps/io.github.wergosam.pachul.svg"
        if os.path.isfile(icon_path):
            notif.set_icon(Gio.FileIcon.new(Gio.File.new_for_path(icon_path)))
        app.send_notification("pachul-updates", notif)

    def _on_updates_loaded(self, updates):
        prev_n = len(self._updates) if self._updates else 0
        self._updates = updates
        n = len(updates)
        self.stat_updates._num.set_label(str(n))
        self._nav_rows["updates"].set_count(n)
        # Desktop notification when the update count first rises.
        if n > 0 and n != prev_n and get_setting("notify_updates"):
            self._notify_updates(n)
        self._empty_updates_desc.set_label(
            tr("No pending updates found.") if n == 0
            else tr("{n} update(s) available.").format(n=n))
        self._update_action_bar_mode()
        self._reapply_update_markers()
        self._apply_filter()
        return False

    def _reapply_update_markers(self):
        """Sync the 'update' status on _all_packages with the current
        self._updates set. Marks pending updates and clears stale ones, so a
        fresh package reload (e.g. after installing/updating) reflects reality.

        Matching uses source_id when a package has one — Flatpak/Snap
        entries carry their app-id/package name there (what the actual
        update commands and check_updates() both key off), which can
        differ from the friendly display name in `name`. Plain pacman/AUR
        packages never set source_id, so they fall back to `name` as before.
        """
        update_map = {u["name"]: u["new"] for u in (self._updates or [])}
        for pkg in self._all_packages:
            key = pkg.get("source_id") or pkg["name"]
            if key in update_map:
                pkg["status"] = "update"
                pkg["new_version"] = update_map[key]
            elif pkg.get("status") == "update":
                pkg["status"] = "installed"
                pkg.pop("new_version", None)

    def _update_sidebar_counts(self):
        total         = len(self._all_packages)
        foreign       = sum(1 for p in self._all_packages if p.get("foreign", False))
        installed     = sum(1 for p in self._all_packages if p["status"] in ("installed", "update"))
        not_installed = total - installed
        self.stat_total._num.set_label(str(total))
        self.stat_aur._num.set_label(str(foreign))
        self._nav_rows["installed"].set_count(installed)
        self._nav_rows["not_installed"].set_count(not_installed)

        seen_repos = set(
            p.get("repo", "").lower() for p in self._all_packages
            if p.get("repo", "") not in ("local", "")
        )
        for repo_key in sorted(seen_repos):
            if repo_key not in self._repo_nav_rows:
                icon = self._repo_icon_map.get(repo_key, "folder-symbolic")
                new_row = NavRow(icon, repo_key, 0, "count-badge")
                self.repo_listbox.append(new_row)
                self._repo_nav_rows[repo_key] = new_row
        for repo_key, nav_row in self._repo_nav_rows.items():
            count = sum(1 for p in self._all_packages if p.get("repo", "").lower() == repo_key)
            nav_row.set_count(count)
            nav_row.set_visible(count > 0 or repo_key in ("core", "extra", "multilib", "aur"))

    # ── Filtering ─────────────────────────────────────────────────────────────

    @staticmethod
    def _pkg_matches_filter(pkg, filt):
        """True if pkg should be shown under sidebar filter `filt`.

        `filt` is either one of the special keys (installed/not_installed/
        aur/updates) or a literal repo name. Repo names are matched generically —
        not against a hardcoded shortlist — so any repo discovered at
        runtime (chaotic-aur, testing, community, flatpak, snap, …) is
        filterable as soon as it gets a sidebar row, with no extra wiring
        needed here per repo.
        """
        if filt == "installed":
            return pkg["status"] in ("installed", "update")
        if filt == "not_installed":
            return pkg["status"] not in ("installed", "update")
        if filt == "aur":
            return pkg.get("foreign", False)
        if filt == "updates":
            return pkg.get("status") == "update"
        if filt in (None, "all"):
            return True
        return pkg.get("repo", "").lower() == filt

    @staticmethod
    def _pkg_matches_search(pkg, query):
        """True if pkg matches the free-text search query (empty query always matches)."""
        if not query:
            return True
        q = query.lower()
        return q in pkg["name"].lower() or q in pkg.get("description", "").lower()

    def _apply_filter(self):
        """Filter (sidebar category + search text) in a background thread,
        render in batches to avoid UI freeze."""
        filt  = self._current_filter
        query = self._search_query
        pkgs_snapshot = list(self._all_packages)

        def do_filter():
            filtered = [p for p in pkgs_snapshot
                        if self._pkg_matches_filter(p, filt)
                        and self._pkg_matches_search(p, query)]
            if self._alive:
                GLib.idle_add(self._render_filter_results, filtered, filt, query)

        threading.Thread(target=do_filter, daemon=True).start()

    @staticmethod
    def _make_item(p):
        return PackageItem(
            p["name"], p["version"], p.get("repo", "local"), p["status"],
            p.get("description", ""), p.get("foreign", False), p.get("source_id"))

    def _fill_pkg_store(self, filtered):
        # One splice replaces the whole list; the ListView renders only the
        # visible rows, so there's no need to chunk widget creation any more.
        items = [self._make_item(p) for p in filtered]
        self.pkg_store.splice(0, self.pkg_store.get_n_items(), items)

    def _render_filter_results(self, filtered, filt, query):
        if not self._alive or self._current_filter != filt or self._search_query != query:
            return False
        self._fill_pkg_store(filtered)
        total = len(self._all_packages)
        shown = len(filtered)
        self._list_count_label_text = (
            f"{shown} of {total} packages" if shown != total else f"{total} packages")
        # A checkbox selection persists across filter/search changes, so
        # its "N selected" text takes priority over the plain list count —
        # _update_batch_action_bar() is what owns the label in that case.
        if not self.pkg_sel_state.selected:
            self.pkg_count_label.set_label(self._list_count_label_text)
        if shown == 0:
            self.list_stack.set_visible_child_name(
                "empty_updates" if filt == "updates" and not query and self._updates is not None
                else "empty_generic")
        else:
            self.list_stack.set_visible_child_name("list")
        return False

    # ── Search ────────────────────────────────────────────────────────────────

    SEARCH_DEBOUNCE_MS = 280

    def _cancel_search_timer(self):
        if self._search_timer is not None:
            GLib.source_remove(self._search_timer)
            self._search_timer = None

    def _on_search_changed(self, entry):
        q = entry.get_text().strip()
        self.search_entry.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, bool(q))
        self._cancel_search_timer()
        self._search_query = q
        # Instant local re-filter on every keystroke — cheap, in-memory only.
        self._apply_filter()
        if not q:
            return
        # Defer the expensive, subprocess-spawning remote lookup (repos +
        # AUR) until typing pauses, so new/not-yet-known packages can still
        # surface without a query on every keystroke.
        self._search_timer = GLib.timeout_add(
            self.SEARCH_DEBOUNCE_MS, self._run_remote_search, q)

    def _on_search_activate(self, *_):
        q = self.search_entry.get_text().strip()
        self._cancel_search_timer()
        self._search_query = q
        self._apply_filter()
        if q:
            self._run_remote_search(q)

    def _on_search_icon_press(self, entry, icon_pos):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")   # fires _on_search_changed, which clears the filter

    def _run_remote_search(self, q):
        self._search_timer = None

        def worker():
            remote = search_packages_cmd(q)
            if self._alive:
                GLib.idle_add(self._merge_remote_search, remote, q)

        threading.Thread(target=worker, daemon=True).start()
        return False   # one-shot: do not repeat the timeout

    def _merge_remote_search(self, remote_results, query):
        # Ignore stale results if the query changed while we were waiting.
        if self._search_query != query:
            return False
        existing = {p["name"] for p in self._all_packages}
        found_new = False
        for r in remote_results:
            if r["name"] not in existing:
                self._all_packages.append(r)
                existing.add(r["name"])
                found_new = True
        if found_new:
            self._update_sidebar_counts()
            self._apply_filter()
        return False

    # ── Nav ───────────────────────────────────────────────────────────────────

    def _grab_search_focus(self):
        # Run-once idle callback: grab_focus() returns True, so passing it
        # straight to GLib.idle_add would re-run it on every idle cycle —
        # repeatedly re-selecting the entry's text so each typed character
        # replaces the previous one. Returning False removes the idle source.
        self.search_entry.grab_focus()
        self.search_entry.set_position(-1)   # cursor to end, clears the selection
        return False

    def _on_nav_selected(self, listbox, row):
        self.repo_listbox.unselect_all()
        keys = list(self._nav_rows.keys())
        idx  = row.get_index()
        if idx >= len(keys):
            return
        key = keys[idx]
        if key == "orphans":
            self._on_show_orphans()
            return
        self._current_filter = key
        self._update_action_bar_mode()
        self._apply_filter()

    def _on_repo_nav_selected(self, listbox, row):
        self.nav_listbox.unselect_all()
        keys = list(self._repo_nav_rows.keys())
        idx  = row.get_index()
        if idx < len(keys):
            self._current_filter = keys[idx]
        self._update_action_bar_mode()
        self._apply_filter()

    def _update_action_bar_mode(self):
        is_updates = (self._current_filter == "updates")
        # There's no separate selection "mode" any more — checkboxes are
        # always available. The moment something is checked, the action bar
        # switches to the batch Install/Remove buttons no matter which
        # sidebar filter is active; with nothing checked it falls back to
        # the Updates-specific buttons (or the single-package ones, handled
        # in _update_batch_action_bar).
        has_selection = len(self.pkg_sel_state.selected) > 0
        show_batch_buttons = has_selection or not is_updates
        self.btn_install.set_visible(show_batch_buttons)
        self.btn_remove.set_visible(show_batch_buttons)
        self.btn_upgrade_all.set_visible(is_updates and not has_selection)
        self.btn_check_updates.set_visible(is_updates and not has_selection)
        if is_updates and not has_selection:
            n = len(self._updates) if self._updates else 0
            self.btn_upgrade_all.set_sensitive(n > 0)

        self.btn_deselect_all.set_visible(has_selection)

    # ── Package detail ────────────────────────────────────────────────────────

    def _on_pkg_activated(self, pkg):
        if pkg is None:
            return
        self._selected_pkg = pkg
        installed = pkg.pkg_status in ("installed", "update")
        # An "update" package is installed but upgradable — Install stays
        # active and runs `pacman -S`, which upgrades that single package.
        can_install = pkg.pkg_status != "installed"
        install_label = tr("Update") if pkg.pkg_status == "update" else tr("Install")
        self._set_btn_label(self.detail_panel.btn_install, install_label)
        self.detail_panel.btn_install.set_sensitive(can_install)
        self.detail_panel.btn_remove.set_sensitive(installed)
        self.detail_panel.btn_reinstall.set_sensitive(installed)
        self.detail_panel.btn_downgrade.set_sensitive(installed)
        # A row click always opens that package's detail view — even with
        # a checkbox selection active elsewhere, so a person can still peek
        # at a package before deciding whether to check it too. But the
        # bottom action bar (Install/Remove) must keep reflecting the
        # actual checked set in that case, not silently switch to acting
        # on whatever was last peeked at.
        if not self.pkg_sel_state.selected:
            self._set_btn_label(self.btn_install, install_label)
            self.btn_install.set_sensitive(can_install)
            self.btn_remove.set_sensitive(installed)
        self._show_detail(self.detail_panel, pkg)

    def _set_status_pill(self, panel, status, foreign):
        for cls in ("status-installed", "status-available", "status-update", "status-foreign"):
            panel.status.remove_css_class(cls)
        if status == "update":
            panel.status.set_label(tr("UPDATE AVAILABLE"))
            panel.status.add_css_class("status-update")
        elif status == "installed":
            if foreign:
                panel.status.set_label(tr("INSTALLED (AUR)"))
                panel.status.add_css_class("status-foreign")
            else:
                panel.status.set_label(tr("INSTALLED"))
                panel.status.add_css_class("status-installed")
        else:
            panel.status.set_label(tr("AVAILABLE"))
            panel.status.add_css_class("status-available")

    def _show_detail(self, panel, pkg):
        """Fill `panel`'s hero with `pkg`, then load its info/files in a thread."""
        panel.name.set_label(pkg.pkg_name)
        panel.desc.set_label(pkg.pkg_description or tr("No description available."))
        _tex = get_icon_texture(pkg_icon(pkg.pkg_name), 58)
        if _tex is not None:
            panel.icon.set_from_paintable(_tex)
        else:
            panel.icon.set_from_icon_name(pkg_icon(pkg.pkg_name))

        repo_str = "aur" if pkg.pkg_foreign else (pkg.pkg_repo or "local").lower()
        panel.repo_badge.set_label(repo_str.upper())
        for cls in REPO_BADGE_CLASS.values():
            panel.repo_badge.remove_css_class(cls)
        panel.repo_badge.add_css_class(REPO_BADGE_CLASS.get(repo_str, "badge-local"))
        panel.ver_badge.set_label(pkg.pkg_version)
        self._set_status_pill(panel, pkg.pkg_status, pkg.pkg_foreign)

        panel.stack.set_visible_child_name("detail")
        for row in panel.info_rows.values():
            if isinstance(row, Adw.ActionRow):
                row.set_subtitle("…")
        for exp_row, _ in panel.dep_rows.values():
            exp_row.set_subtitle("…")
        panel.raw_text.set_label(tr("Loading…"))
        panel.set_files_loading()

        def worker():
            if pkg.pkg_repo in ("flatpak", "snap"):
                source_label = tr("Flatpak") if pkg.pkg_repo == "flatpak" \
                    else tr("Snap package")
                info = (
                    f"Name           : {pkg.pkg_name}\n"
                    f"Version        : {pkg.pkg_version}\n"
                    f"Description    : {pkg.pkg_description or '—'}\n"
                    f"Install Reason : {source_label}\n"
                )
                files = []
            else:
                info  = get_package_info(pkg.pkg_name)
                files = get_package_files(pkg.pkg_name)
            if self._alive:
                GLib.idle_add(self._populate_detail, panel, info, files)
        threading.Thread(target=worker, daemon=True).start()

    def _populate_detail(self, panel, raw, files):
        panel.raw_text.set_label(raw)
        parsed = self._parse_pkginfo(raw)
        for key in DetailPanel.INFO_KEYS:
            val = parsed.get(key, "—") or "—"
            if val in ("None", ""):
                val = "—"
            if key in panel.dep_rows:
                exp_row, flow = panel.dep_rows[key]
                self._populate_dep_flow(panel, flow, exp_row, val)
            elif key in panel.info_rows:
                self._set_info_subtitle(panel.info_rows[key], key, val)
        panel.arch_badge.set_label(parsed.get("Architecture", "x86_64"))
        panel.set_files(files)
        return False


    def _set_info_subtitle(self, row, key, val):
        """Set an ActionRow subtitle, rendering URL fields as a clickable link."""
        esc = GLib.markup_escape_text(val)
        if key == "URL" and val.startswith(("http://", "https://")):
            row.set_subtitle(f'<a href="{esc}">{esc}</a>')
        else:
            row.set_subtitle(esc)

    def _parse_pkginfo(self, raw):
        """Parse pacman -Qi / -Si output handling multi-line values correctly."""
        parsed = {}
        current_key = None
        for line in raw.splitlines():
            if line and not line[0].isspace() and ":" in line:
                k, _, v = line.partition(":")
                current_key = k.strip()
                val = v.strip()
                parsed[current_key] = val
            elif current_key and line.startswith(" ") and line.strip():
                # continuation — append to current key
                parsed[current_key] = parsed[current_key] + " " + line.strip()
        return parsed

    def _populate_dep_flow(self, panel, flow, exp_row, val):
        while flow.get_first_child():
            flow.remove(flow.get_first_child())
        if val == "—":
            exp_row.set_subtitle("—")
            exp_row.set_expanded(False)
            return
        import re
        # Each dep token may look like: "libfoo>=1.0" or "libfoo: for something"
        # Split on whitespace first, then strip version constraints and inline descriptions
        raw_tokens = val.split()
        dep_names = []
        for token in raw_tokens:
            # Skip pure description words (tokens after a "name:" token)
            # A dep token starts with a letter/number and contains the package name
            if not token or token[0] in (":", "(", ")"):
                continue
            # Strip inline description separator "name:" — take only up to the colon
            name_part = token.split(":")[0]
            # Strip version constraints
            clean = re.split(r"[><=!]", name_part)[0].strip()
            if clean and re.match(r"^[a-zA-Z0-9_@.+-]+$", clean):
                dep_names.append(clean)
        # Deduplicate while preserving order
        seen = set()
        dep_names = [d for d in dep_names if not (d in seen or seen.add(d))]
        exp_row.set_subtitle(
            tr("{n} package").format(n=len(dep_names)) if len(dep_names) == 1
            else tr("{n} packages").format(n=len(dep_names)))
        # Cap the chip count — fields like "Required By" can list thousands of
        # packages, and one Gtk.Button each would be slow to build.
        CHIP_CAP = 80
        for dep in dep_names[:CHIP_CAP]:
            btn = Gtk.Button(label=dep)
            btn.add_css_class("dep-chip")
            btn.set_tooltip_text(tr("Look up {dep}").format(dep=dep))
            btn.connect("clicked", lambda b, name=dep: panel.dep_callback(name))
            flow.append(btn)
        if len(dep_names) > CHIP_CAP:
            more = Gtk.Label(label=tr("+{n} more").format(n=len(dep_names) - CHIP_CAP))
            more.add_css_class("dim-label"); more.add_css_class("caption")
            flow.append(more)

    def _highlight_in_store(self, store, selection, listview, pkg_name):
        """Select (but do not activate) the row for pkg_name; scroll it into view."""
        for i in range(store.get_n_items()):
            if store.get_item(i).pkg_name == pkg_name:
                selection.set_selected(i)
                listview.scroll_to(i, Gtk.ListScrollFlags.FOCUS, None)
                return True
        return False

    def _lookup_dep_in_list(self, pkg_name):
        """Highlight a dependency package in the package list, broadening the
        view (and fetching it remotely if needed) so it's visible even if
        it isn't installed or doesn't match the current filter/search."""
        # Try the current view first
        if self._highlight_in_store(self.pkg_store, self.pkg_selection,
                                    self.pkg_listview, pkg_name):
            return

        # Not visible under the current filter/search — broaden to "All
        # Packages" with no search text, then try again.
        self._current_filter = "all"
        self._search_query = ""
        self.search_entry.set_text("")
        self.nav_listbox.select_row(self._nav_rows["all"])

        def after_filter():
            if self._highlight_in_store(self.pkg_store, self.pkg_selection,
                                        self.pkg_listview, pkg_name):
                return False
            # Still not found — not installed and not yet in our repo/AUR
            # cache. Look it up remotely and prepend it once found.
            for pkg in self._all_packages:
                if pkg["name"] == pkg_name:
                    self.pkg_store.insert(0, self._make_item(pkg))
                    self.pkg_selection.set_selected(0)
                    self.pkg_listview.scroll_to(0, Gtk.ListScrollFlags.FOCUS, None)
                    return False

            def worker():
                results = search_packages_cmd(pkg_name)
                if self._alive:
                    GLib.idle_add(self._prepend_dep_result, pkg_name, results)

            threading.Thread(target=worker, daemon=True).start()
            return False

        self._apply_filter_then(after_filter)

    def _apply_filter_then(self, callback):
        """Apply the current filter + search text; run callback once rendered."""
        filt  = self._current_filter
        query = self._search_query
        pkgs_snapshot = list(self._all_packages)

        def do_filter():
            filtered = [p for p in pkgs_snapshot
                        if self._pkg_matches_filter(p, filt)
                        and self._pkg_matches_search(p, query)]
            if self._alive:
                GLib.idle_add(self._render_filter_results_then, filtered, filt, query, callback)

        threading.Thread(target=do_filter, daemon=True).start()

    def _render_filter_results_then(self, filtered, filt, query, callback):
        """Same as _render_filter_results but fires `callback` once rendered."""
        if not self._alive or self._current_filter != filt or self._search_query != query:
            return False
        self._fill_pkg_store(filtered)
        total = len(self._all_packages)
        shown = len(filtered)
        self._list_count_label_text = (
            f"{shown} of {total} packages" if shown != total else f"{total} packages")
        if not self.pkg_sel_state.selected:
            self.pkg_count_label.set_label(self._list_count_label_text)
        if shown == 0:
            self.list_stack.set_visible_child_name(
                "empty_updates" if filt == "updates" and not query and self._updates is not None
                else "empty_generic")
        else:
            self.list_stack.set_visible_child_name("list")
        if callback:
            GLib.idle_add(callback)
        return False

    def _prepend_dep_result(self, pkg_name, results):
        for r in results:
            if r["name"] == pkg_name:
                if r["name"] not in {p["name"] for p in self._all_packages}:
                    self._all_packages.append(r)
                self.pkg_store.insert(0, self._make_item(r))
                self.pkg_selection.set_selected(0)
                self.pkg_listview.scroll_to(0, Gtk.ListScrollFlags.FOCUS, None)
                return
        return False

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toast(self, text, timeout=4):
        toast = Adw.Toast()
        toast.set_title(text)
        toast.set_timeout(timeout)
        try:
            self._toast_overlay.add_toast(toast)
        except AttributeError:
            pass

    def _run_terminal(self, cmd, title, on_success=None):
        def _on_done(code):
            if code == 0:
                invalidate_cache()
            self._toast(f"✓ {title} completed" if code == 0
                        else f"✗ {title} failed (exit {code})")
            self._load_packages()
        run_terminal_dialog(self, cmd, title, on_success=on_success, on_done_extra=_on_done)

    def _on_refresh(self, *_):
        self._all_packages = []
        self._updates = None
        self._search_query = ""
        self.search_entry.set_text("")
        self.detail_panel.stack.set_visible_child_name("empty")
        self._selected_pkg = None
        self.pkg_sel_state.selected.clear()
        self._update_action_bar_mode()
        self.btn_install.set_sensitive(False)
        self.btn_remove.set_sensitive(False)
        self._load_packages()

    def _on_sync_db(self, *_):
        def _do_sync():
            invalidate_syncdb_cache()
            self._run_terminal("sudo -S pacman -Sy --noconfirm", tr("Sync Databases"))
        show_sync_db_dialog(self, _do_sync)

    def _on_upgrade(self, *_):
        if get_setting("show_news_before_upgrade"):
            show_news_dialog(self, self._do_upgrade)
        else:
            self._do_upgrade()

    def _do_upgrade(self):
        def _after():
            self._updates = []
            self.stat_updates._num.set_label("0")
            self._nav_rows["updates"].set_count(0)
        # Use the AUR helper if present so repo *and* AUR packages are upgraded.
        # Note: pacman's -Syu already covers every repo listed in
        # /etc/pacman.conf uniformly (core, extra, multilib, chaotic-aur,
        # ...) — there's no per-repo command needed for those.
        helper = self._get_aur_helper()
        cmd = f"{helper} -Syu --noconfirm" if helper else "sudo -S pacman -Syu --noconfirm"
        if get_setting("snapshot_before_upgrade"):
            snap_cmd = build_snapshot_cmd()
            if snap_cmd:
                cmd = f"{snap_cmd} && {cmd}"
        # Flatpak and Snap are entirely separate ecosystems that pacman/AUR
        # helpers never touch, so they need their own commands chained on —
        # only when the person has actually opted into showing them
        # (flatpak_enabled/snap_enabled), matching how the rest of the app
        # treats these two optional sources.
        if get_setting("flatpak_enabled") and flatpak_available():
            cmd = f"{cmd} && flatpak update -y"
        if get_setting("snap_enabled") and snap_available():
            cmd = f"{cmd} && sudo -S snap refresh"
        self._run_terminal(cmd, tr("System Upgrade"), on_success=_after)

    def _on_clean_cache(self, *_):
        show_clean_cache_dialog(self, self._run_terminal)

    def _on_check_updates(self, *_):
        helper = self._get_aur_helper()
        aur_section = (
            "echo; echo '== AUR =='; "
            f"_aur_out=$({helper} -Qua 2>/dev/null); "
            "if [ -n \"$_aur_out\" ]; then echo \"$_aur_out\"; "
            "else echo '(No AUR updates found.)'; fi; "
        ) if helper else ""
        flatpak_section = (
            "echo; echo '== Flatpak =='; "
            "flatpak update --appstream 2>/dev/null; "
            "_fp_out=$(flatpak remote-ls --updates --all "
            "--columns=application,version 2>/dev/null); "
            "if [ -n \"$_fp_out\" ]; then echo \"$_fp_out\"; "
            "else echo '(No Flatpak updates found.)'; fi; "
        ) if (get_setting("flatpak_enabled") and flatpak_available()) else ""
        snap_section = (
            "echo; echo '== Snap =='; "
            "_snap_out=$(snap refresh --list 2>/dev/null | tail -n +2); "
            "if [ -n \"$_snap_out\" ]; then echo \"$_snap_out\"; "
            "else echo '(No Snap updates found.)'; fi; "
        ) if (get_setting("snap_enabled") and snap_available()) else ""
        self._run_terminal(
            "echo '== Official Repositories =='; "
            "if command -v checkupdates >/dev/null 2>&1; then "
            "_repo_out=$(checkupdates 2>/dev/null); "
            "else "
            "_repo_out=$(pacman -Qu 2>/dev/null); "
            "echo '(Note: pacman-contrib/checkupdates not found -- checked against the "
            "last-synced local database instead of a live one. Install pacman-contrib, "
            "or run Sync Databases first, for a fully up-to-date check.)'; "
            "fi; "
            "if [ -n \"$_repo_out\" ]; then echo \"$_repo_out\"; "
            "else echo '(No repo updates found.)'; fi; "
            f"{aur_section}"
            f"{flatpak_section}"
            f"{snap_section}"
            "echo; echo 'Done.'",
            tr("Check for Updates"))

    def _on_manage_repos(self, *_):
        show_repo_manager(self, self._run_terminal)

    def _on_rate_mirrors(self, *_):
        show_mirror_rater(self, self._run_terminal)

    def _on_show_orphans(self, *_):
        show_orphan_finder(self, self._run_terminal)

    def _on_show_file_search(self, *_):
        show_file_search_dialog(self, self._run_terminal)

    def _on_show_sysinfo(self, *_):
        show_sysinfo_dialog(self)

    def _on_show_history(self, *_):
        show_history_dialog(self)

    def _on_show_pacdiff(self, *_):
        show_pacdiff_dialog(self, self._run_terminal)

    def _on_view_pkgbuild(self, *_):
        pkg = self._selected_pkg
        if not pkg:
            self._toast(tr("Select a package first"))
            return
        if not pkg.pkg_foreign:
            self._toast(tr("PKGBUILD is only available for AUR packages"))
            return
        show_pkgbuild_dialog(self, pkg.pkg_name, self._on_install)

    def _on_toggle_hold(self, *_):
        pkg = self._selected_pkg
        if not pkg:
            self._toast(tr("Select a package first"))
            return
        if pkg.pkg_repo in ("flatpak", "snap"):
            self._toast(tr("Hold isn't available for Flatpak/Snap packages"))
            return
        currently = pkg.pkg_name in get_ignored_packages()

        def _do_toggle():
            tmp = set_package_ignored(pkg.pkg_name, not currently)
            if tmp is None:
                self._toast(tr("Could not read /etc/pacman.conf"))
                return
            verb = tr("Unhold") if currently else tr("Hold")
            self._run_terminal(
                f"sudo -S install -m644 {shlex.quote(tmp)} /etc/pacman.conf",
                f"{verb} {pkg.pkg_name}")

        show_hold_dialog(self, pkg.pkg_name, currently, _do_toggle)

    def _on_preferences(self, *_):
        show_preferences(self, self._on_settings_changed, app_dir=APP_DIR)

    def _on_settings_changed(self):
        new_lang = get_language()
        if new_lang != self._current_lang:
            self._current_lang = new_lang
            self._rebuild_for_language_change()
            return
        # Any other setting (AUR helper, include-AUR, Flatpak/Snap toggles,
        # ...) can affect what shows up in the package list and/or the
        # update set — just reload everything. Cheap, and keeps this
        # generic instead of tracking exactly which setting changed.
        if self._alive:
            self._load_packages()
            threading.Thread(target=self._bg_check_updates, daemon=True).start()

    def _rebuild_for_language_change(self):
        """Rebuild the whole window so already-built chrome (sidebar, menu,
        headerbar, tooltips, empty-state pages, ...) picks up the new
        language immediately. Dialogs and the package-row/detail content
        already do this on their own next open/refresh, since they call
        tr() fresh every time they're built — it's specifically the
        long-lived widgets built once in _build_ui() that otherwise
        wouldn't update without restarting the app.

        Best-effort: restores which sidebar view (all/installed/updates/
        repo) was active, and the search text if any was entered.
        The exact selected package and open detail view are not restored
        (the list reloads asynchronously and re-matching a selection into
        that isn't worth the added complexity) — a minor, deliberate
        tradeoff for not needing a full restart.
        """
        filt  = self._current_filter
        query = self._search_query

        self._build_ui()
        self._load_packages()

        row = self._nav_rows.get(filt)
        if row is not None:
            self.repo_listbox.unselect_all()
            self.nav_listbox.select_row(row)
        else:
            row = self._repo_nav_rows.get(filt)
            if row is not None:
                self.nav_listbox.unselect_all()
                self.repo_listbox.select_row(row)
        self._current_filter = filt
        self._update_action_bar_mode()
        if query:
            self.search_entry.set_text(query)  # fires _on_search_changed
        # No explicit _apply_filter() call here: _load_packages() (just
        # above) finishes asynchronously and its own completion handler
        # (_on_packages_loaded) already calls _apply_filter() once loading
        # is done.

    def _on_show_shortcuts(self, *_):
        show_shortcuts_dialog(self)

    def _on_focus_search(self, *_):
        GLib.idle_add(self._grab_search_focus)

    def _on_downgrade(self, *_):
        if not self._selected_pkg:
            self._toast(tr("Select a package first"))
            return
        show_downgrade_dialog(self, self._selected_pkg.pkg_name, self._run_terminal)

    def _on_mark_explicit(self, *_):
        pkg = self._selected_pkg
        if not pkg:
            self._toast(tr("Select a package first"))
            return
        if pkg.pkg_repo in ("flatpak", "snap"):
            self._toast(tr("Not applicable to Flatpak/Snap packages"))
            return
        self._run_terminal(
            f"sudo -S pacman -D --asexplicit {shlex.quote(pkg.pkg_name)}",
            tr("Mark {name} as explicit").format(name=pkg.pkg_name), on_success=self._refresh_selected_pkg)

    def _on_mark_asdeps(self, *_):
        pkg = self._selected_pkg
        if not pkg:
            self._toast(tr("Select a package first"))
            return
        if pkg.pkg_repo in ("flatpak", "snap"):
            self._toast(tr("Not applicable to Flatpak/Snap packages"))
            return

        def _do_mark():
            self._run_terminal(
                f"sudo -S pacman -D --asdeps {shlex.quote(pkg.pkg_name)}",
                tr("Mark {name} as dependency").format(name=pkg.pkg_name), on_success=self._refresh_selected_pkg)

        show_mark_asdeps_dialog(self, pkg.pkg_name, _do_mark)

    def _on_export_pkgs(self, *_):
        show_export_pkgs_intro(self, self._open_export_file_picker)

    def _open_export_file_picker(self):
        dialog = Gtk.FileDialog()
        dialog.set_title(tr("Export Package List"))
        dialog.set_initial_name(tr("pachul-packages.txt"))
        dialog.save(self, None, self._export_save_done)

    def _export_save_done(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return   # user cancelled
        path = gfile.get_path()
        pkgs = get_explicit_packages()
        try:
            with open(path, "w") as f:
                f.write("\n".join(pkgs) + "\n")
            self._toast(tr("Exported {n} packages").format(n=len(pkgs)))
        except OSError as e:
            self._toast(tr("Export failed: {err}").format(err=e))

    def _on_import_pkgs(self, *_):
        helper = self._get_aur_helper()
        show_import_pkgs_intro(self, helper, self._open_import_file_picker)

    def _open_import_file_picker(self):
        dialog = Gtk.FileDialog()
        dialog.set_title(tr("Import Package List"))
        dialog.open(self, None, self._import_open_done)

    def _import_open_done(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return   # user cancelled
        try:
            with open(gfile.get_path()) as f:
                names = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        except OSError as e:
            self._toast(tr("Could not read file: {err}").format(err=e))
            return
        if not names:
            self._toast(tr("No packages found in file"))
            return
        helper = self._get_aur_helper()
        show_import_pkgs_dialog(self, names, helper, self._run_terminal)

    # ── Multi-select / batch actions ─────────────────────────────────────────

    def _rebind_all_rows(self):
        """Detach/reattach the package ListView's model to force every
        visible row to rebind (e.g. after Select All / Deselect All changes
        many rows' checkboxes at once — a single row's own checkbox click
        updates itself directly and doesn't need this), preserving scroll
        position."""
        lv, scroll = self.pkg_listview, self.pkg_scroll
        model = lv.get_model()
        if model is None:
            return
        vadj = scroll.get_vadjustment()
        saved_pos = vadj.get_value() if vadj is not None else None
        lv.set_model(None)
        lv.set_model(model)
        if saved_pos:
            def _restore():
                vadj = scroll.get_vadjustment()
                if vadj is not None:
                    vadj.set_value(saved_pos)
                return False
            # Restore after GTK has finished laying out the reattached
            # model — doing it in the same frame gets overwritten.
            GLib.idle_add(_restore)

    def _iter_known_packages(self):
        """Yield every PackageItem currently loaded in the package list."""
        for i in range(self.pkg_store.get_n_items()):
            item = self.pkg_store.get_item(i)
            if item is not None:
                yield item

    def _update_batch_action_bar(self):
        """Recompute the action bar + detail panel for the current checkbox
        selection.

        Serves as the `on_selection_change` callback fired every time a
        checkbox is toggled (by a single row, or in bulk by Select/Deselect
        All) — there's no separate "selection mode" any more, so this also
        handles falling back to the normal single-package view the moment
        the selection becomes empty again.
        """
        state = self.pkg_sel_state
        n = len(state.selected)

        if n == 0:
            self.pkg_count_label.set_label(getattr(self, "_list_count_label_text", ""))
            if self._selected_pkg is not None:
                self._on_pkg_activated(self._selected_pkg)
            else:
                self._set_btn_label(self.btn_install, tr("Install"))
                self._set_btn_label(self.btn_remove, tr("Uninstall"))
                self.btn_install.set_sensitive(False)
                self.btn_remove.set_sensitive(False)
                self.detail_panel.stack.set_visible_child_name("empty")
            self._update_action_bar_mode()
            return

        seen = set()
        to_install, to_remove = [], []
        selected_names = []
        for item in self._iter_known_packages():
            if item.pkg_name in state.selected and item.pkg_name not in seen:
                seen.add(item.pkg_name)
                selected_names.append(item.pkg_name)
                if item.pkg_status in ("installed", "update"):
                    to_remove.append(item)
                else:
                    to_install.append(item)
        self._batch_install_items = to_install
        self._batch_remove_items = to_remove
        count_text = tr("{n} selected").format(n=n)
        install_label = tr("Install ({n})").format(n=len(to_install))
        remove_label = tr("Remove ({n})").format(n=len(to_remove))

        self.pkg_count_label.set_label(count_text)
        self._set_btn_label(self.btn_install, install_label)
        self._set_btn_label(self.btn_remove, remove_label)
        self.btn_install.set_sensitive(len(to_install) > 0)
        self.btn_remove.set_sensitive(len(to_remove) > 0)

        # Show selected packages in the detail panel
        self.detail_panel.show_batch(selected_names)
        self._update_action_bar_mode()

    def _pkg_is_foreign(self, name):
        for item in self._iter_known_packages():
            if item.pkg_name == name:
                return item.pkg_foreign
        return False

    def _exit_selection_mode(self):
        """Clear the current checkbox selection (e.g. after a batch
        install/remove completes) and fall back to the normal view."""
        if self.pkg_sel_state.selected:
            self.pkg_sel_state.selected.clear()
            self._rebind_all_rows()
        self._update_batch_action_bar()

    def _on_select_all(self, *_):
        """Select all packages currently visible in the package list."""
        all_names = [item.pkg_name for item in self._iter_known_packages()]
        if not all_names:
            return
        state = self.pkg_sel_state
        state.selected.clear()
        state.selected.update(all_names)
        self._update_batch_action_bar()
        # Force refresh of visible rows to update checkboxes — a bulk
        # change like this doesn't go through any single row's own click
        # handler, so nothing else would repaint them.
        self._rebind_all_rows()

    def _on_deselect_all(self, *_):
        """Deselect all packages."""
        self.pkg_sel_state.selected.clear()
        self._update_batch_action_bar()
        self._rebind_all_rows()

    def _flatpak_uninstall_cmd(self, app_id):
        """Uninstall a Flatpak ref, trying the --user scope first and
        falling back to --system (needs sudo) if it's not found there.
        Flatpaks are commonly installed system-wide — that's Flatpak's own
        default scope, and what tools like Pamac or Discover typically
        use — so a fixed --user-only uninstall would silently fail on
        those, same root cause as the earlier Upgrade-All issue."""
        q = shlex.quote(app_id)
        return (f"{{ flatpak uninstall -y --user {q} 2>/dev/null "
                f"|| sudo -S flatpak uninstall -y --system {q}; }}")

    def _install_cmd_for(self, pkg):
        """Build the right install command for a single package, based on
        which source it came from."""
        if pkg.pkg_repo == "flatpak":
            app_id = pkg.pkg_source_id or pkg.pkg_name
            return f"flatpak install -y --user flathub {shlex.quote(app_id)}"
        if pkg.pkg_repo == "snap":
            name = pkg.pkg_source_id or pkg.pkg_name
            return f"sudo -S snap install {shlex.quote(name)}"
        name = shlex.quote(pkg.pkg_name)
        if pkg.pkg_foreign:
            helper = self._get_aur_helper()
            return f"{helper} -S --noconfirm {name}" if helper \
                   else f"sudo -S pacman -S --noconfirm {name}"
        return f"sudo -S pacman -S --noconfirm {name}"

    def _remove_cmd_for(self, pkg):
        """Build the right remove command for a single package, based on
        which source it came from."""
        if pkg.pkg_repo == "flatpak":
            app_id = pkg.pkg_source_id or pkg.pkg_name
            return self._flatpak_uninstall_cmd(app_id)
        if pkg.pkg_repo == "snap":
            name = pkg.pkg_source_id or pkg.pkg_name
            return f"sudo -S snap remove {shlex.quote(name)}"
        return f"sudo -S pacman -R --noconfirm {shlex.quote(pkg.pkg_name)}"

    def _on_batch_install(self):
        items = list(getattr(self, "_batch_install_items", []))
        if not items:
            return
        pac_items = [i for i in items if i.pkg_repo not in ("flatpak", "snap")]
        fp_items  = [i for i in items if i.pkg_repo == "flatpak"]
        sn_items  = [i for i in items if i.pkg_repo == "snap"]

        cmds = []
        if pac_items:
            helper = self._get_aur_helper()
            names = [i.pkg_name for i in pac_items]
            if not helper:
                foreign = [n for n in names if self._pkg_is_foreign(n)]
                if foreign:
                    names = [n for n in names if n not in foreign]
                    self._toast(tr("No AUR helper found — skipped {n} AUR package(s).")
                               .format(n=len(foreign)))
            if names:
                quoted = " ".join(shlex.quote(n) for n in names)
                cmds.append(f"{helper} -S --noconfirm {quoted}" if helper
                            else f"sudo -S pacman -S --noconfirm {quoted}")
        if fp_items:
            ids = " ".join(shlex.quote(i.pkg_source_id or i.pkg_name) for i in fp_items)
            cmds.append(f"flatpak install -y --user flathub {ids}")
        if sn_items:
            names = " ".join(shlex.quote(i.pkg_source_id or i.pkg_name) for i in sn_items)
            cmds.append(f"sudo -S snap install {names}")

        if not cmds:
            return
        cmd = " && ".join(cmds)
        self._run_terminal(cmd, tr("Install {n} packages").format(n=len(items)),
                           on_success=self._exit_selection_mode)

    def _on_batch_remove(self):
        items = list(getattr(self, "_batch_remove_items", []))
        if not items:
            return

        def do_remove():
            pac_items = [i for i in items if i.pkg_repo not in ("flatpak", "snap")]
            fp_items  = [i for i in items if i.pkg_repo == "flatpak"]
            sn_items  = [i for i in items if i.pkg_repo == "snap"]

            cmds = []
            if pac_items:
                quoted = " ".join(shlex.quote(i.pkg_name) for i in pac_items)
                cmds.append(f"sudo -S pacman -R --noconfirm {quoted}")
            if fp_items:
                fp_cmds = [self._flatpak_uninstall_cmd(i.pkg_source_id or i.pkg_name)
                          for i in fp_items]
                cmds.append(" && ".join(fp_cmds))
            if sn_items:
                names = " ".join(shlex.quote(i.pkg_source_id or i.pkg_name) for i in sn_items)
                cmds.append(f"sudo -S snap remove {names}")
            if not cmds:
                return

            self._run_terminal(
                " && ".join(cmds),
                tr("Remove {n} packages").format(n=len(items)),
                on_success=self._exit_selection_mode)

        if not get_setting("confirm_remove"):
            do_remove()
            return

        d = Adw.AlertDialog()
        d.set_heading(tr("Remove {n} packages?").format(n=len(items)))
        d.set_body(tr("This will remove the {n} selected packages from your system.")
                   .format(n=len(items)))
        d.add_response("cancel", tr("Cancel")); d.add_response("remove", tr("Remove"))
        d.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel"); d.set_close_response("cancel")
        d.connect("response", lambda dlg, resp: resp == "remove" and do_remove())
        d.present(self)

    def _on_install(self, *_):
        if self.pkg_sel_state.selected:
            self._on_batch_install()
            return
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg
        cmd = self._install_cmd_for(pkg)
        self._run_terminal(cmd, tr("Install {name}").format(name=pkg.pkg_name),
                           on_success=self._refresh_selected_pkg)

    def _on_remove(self, *_):
        if self.pkg_sel_state.selected:
            self._on_batch_remove()
            return
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg

        def do_remove():
            self._run_terminal(
                self._remove_cmd_for(pkg),
                tr("Remove {name}").format(name=pkg.pkg_name),
                on_success=self._refresh_selected_pkg)

        if not get_setting("confirm_remove"):
            do_remove()
            return

        d = Adw.AlertDialog()
        d.set_heading(tr("Remove {name}?").format(name=pkg.pkg_name))
        d.set_body(tr("This will remove {name} ({version}) from your system.").format(
            name=pkg.pkg_name, version=pkg.pkg_version))
        d.add_response("cancel", tr("Cancel")); d.add_response("remove", tr("Remove"))
        d.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel"); d.set_close_response("cancel")
        d.connect("response", lambda dlg, resp: resp == "remove" and do_remove())
        d.present(self)

    def _on_reinstall(self, *_):
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg
        cmd = self._install_cmd_for(pkg)
        self._run_terminal(cmd, tr("Reinstall {name}").format(name=pkg.pkg_name),
                           on_success=self._refresh_selected_pkg)

    def _refresh_selected_pkg(self):
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg
        if pkg.pkg_repo == "flatpak":
            app_id = pkg.pkg_source_id or pkg.pkg_name
            _, code = run_command(f"flatpak info {shlex.quote(app_id)} 2>/dev/null")
            pkg.pkg_status = "installed" if code == 0 else "available"
        elif pkg.pkg_repo == "snap":
            name = pkg.pkg_source_id or pkg.pkg_name
            _, code = run_command(f"snap list {shlex.quote(name)} 2>/dev/null")
            pkg.pkg_status = "installed" if code == 0 else "available"
        else:
            out, code = run_command(f"pacman -Qi {shlex.quote(pkg.pkg_name)} 2>/dev/null")
            pkg.pkg_status = "installed" if (code == 0 and out) else "available"
        installed = pkg.pkg_status == "installed"
        self.btn_install.set_sensitive(not installed)
        self.btn_remove.set_sensitive(installed)
        panel = self.detail_panel
        panel.btn_install.set_sensitive(not installed)
        self._set_btn_label(panel.btn_install, tr("Install"))
        panel.btn_remove.set_sensitive(installed)
        panel.btn_reinstall.set_sensitive(installed)
        panel.btn_downgrade.set_sensitive(installed)
        self._set_status_pill(panel, pkg.pkg_status, pkg.pkg_foreign)
        self._set_btn_label(self.btn_install, tr("Install"))
        # If the package was a pending update and is now installed, drop it
        # from the updates set so it leaves the Updates list right away.
        # Flatpak/Snap entries key off pkg_source_id (their app-id/package
        # name), which is what check_updates() actually reports for them —
        # pkg_name there is only the friendly display name.
        match_key = pkg.pkg_source_id or pkg.pkg_name
        if installed and self._updates and any(
                u["name"] == match_key for u in self._updates):
            self._updates = [u for u in self._updates
                             if u["name"] != match_key]
            n = len(self._updates)
            self.stat_updates._num.set_label(str(n))
            self._nav_rows["updates"].set_count(n)
            for p in self._all_packages:
                if (p.get("source_id") or p["name"]) == match_key:
                    p["status"] = "installed"
                    p.pop("new_version", None)
            self._apply_filter()
        if installed:
            def worker():
                if pkg.pkg_repo in ("flatpak", "snap"):
                    # No pacman-style metadata exists for these — show what
                    # we actually have instead of running a meaningless
                    # pacman -Qi/-Fl query against a non-pacman name.
                    source_label = tr("Flatpak") if pkg.pkg_repo == "flatpak" \
                        else tr("Snap package")
                    info = (
                        f"Name           : {pkg.pkg_name}\n"
                        f"Version        : {pkg.pkg_version}\n"
                        f"Description    : {pkg.pkg_description or '—'}\n"
                        f"Install Reason : {source_label}\n"
                    )
                    files = []
                else:
                    info  = get_package_info(pkg.pkg_name)
                    files = get_package_files(pkg.pkg_name)
                if self._alive:
                    GLib.idle_add(self._populate_both_panels, info, files)
            threading.Thread(target=worker, daemon=True).start()

        if self.pkg_sel_state.selected:
            self._update_batch_action_bar()

    def _populate_both_panels(self, info, files):
        self._populate_detail(self.detail_panel, info, files)
        return False

    def _get_aur_helper(self):
        if self._aur_helper_cache is None:
            for h in ("paru", "yay", "pikaur", "trizen"):
                _, c = run_command(f"which {h} 2>/dev/null")
                if c == 0:
                    self._aur_helper_cache = h
                    break
        return self._aur_helper_cache
