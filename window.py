"""
Pachul — window.py
Main application window: sidebar, search page, package list, detail panel,
filtering, and all action handlers.
"""

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
    build_snapshot_cmd,
)
from models import (
    PackageItem, NavRow, REPO_BADGE_CLASS, pkg_icon, make_package_listview,
    make_icon, set_button_icon, ListSelectionState,
)

# Fallback chains for icon names that are missing in some icon themes
# (notably KDE Breeze), which otherwise show up as a red/pink broken icon.
ICON_UPDATE_AVAILABLE = [
    "software-update-available-symbolic", "software-update-available",
    "system-software-update-symbolic", "view-refresh-symbolic",
]
ICON_SELECTION_MODE = [
    "selection-mode-symbolic", "edit-select-all-symbolic",
    "object-select-symbolic", "list-add-symbolic",
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
from i18n import tr
from dialogs import (
    run_terminal_dialog,
    show_repo_manager,
    show_mirror_rater,
    show_orphan_finder,
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

        empty = Adw.StatusPage()
        empty.set_icon_name("package-x-generic-symbolic")
        empty.set_title(tr("Select a Package"))
        empty.set_description(tr("Choose a package to view its details, files, and dependencies."))
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
        self.icon.set_pixel_size(52); self.icon.set_valign(Gtk.Align.CENTER)
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
            icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
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
        self._current_filter   = "installed"
        self._updates          = None
        self._aur_helper_cache = None
        self._search_timer     = None   # GLib source id for debounced search
        self._alive            = True   # set False on close to stop background workers
        self.connect("close-request", self._on_close_request)
        self._build_ui()
        self._load_packages()

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
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        app_icon  = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
        app_icon.set_pixel_size(18)
        title_lbl = Gtk.Label(label="Pachul")
        title_lbl.add_css_class("heading")
        title_box.append(app_icon)
        title_box.append(title_lbl)
        sidebar_hdr.set_title_widget(title_box)
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
        self.btn_upgrade = Gtk.Button()
        set_button_icon(self.btn_upgrade, ICON_UPDATE_AVAILABLE)
        self.btn_upgrade.set_tooltip_text(tr("System upgrade (pacman -Syu)"))
        self.btn_upgrade.connect("clicked", self._on_upgrade)
        self.btn_upgrade.add_css_class("suggested-action")
        right_box.append(self.btn_upgrade)

        self.btn_selection_mode = Gtk.ToggleButton()
        set_button_icon(self.btn_selection_mode, ICON_SELECTION_MODE)
        self.btn_selection_mode.set_tooltip_text(tr("Select multiple packages"))
        self.btn_selection_mode.add_css_class("flat")
        self.btn_selection_mode.connect("toggled", self._on_toggle_selection_mode)
        right_box.append(self.btn_selection_mode)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
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

        self.update_banner = Adw.Banner()
        self.update_banner.set_button_label(tr("Upgrade Now"))
        self.update_banner.connect("button-clicked", self._on_upgrade)
        self.update_banner.set_revealed(False)
        self.content_tv.add_top_bar(self.update_banner)

        # Main stack: search page | list+detail paned
        # Shared selection-mode state: one flag + one selected-name set used
        # by BOTH the main package list and the search-results list, so
        # toggling batch-select and picking packages behaves identically
        # everywhere and survives switching between views.
        self.pkg_sel_state = ListSelectionState()

        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.NONE)  # instant — no freeze
        self.main_stack.add_named(self._build_search_page(),      "search")
        self.main_stack.add_named(self._build_list_detail_paned(), "list")
        self.main_stack.set_visible_child_name("search")

        self.content_tv.set_content(self.main_stack)
        content_page.set_child(self.content_tv)
        self.nav_split.set_content(content_page)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self.nav_split)
        self.set_content(self._toast_overlay)

    # ── Search page ───────────────────────────────────────────────────────────

    def _build_search_page(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Hero
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        hero.set_halign(Gtk.Align.FILL)
        hero.set_margin_top(48); hero.set_margin_bottom(24)
        hero.set_margin_start(60); hero.set_margin_end(60)

        headline = Gtk.Label(label=tr("Search Packages"))
        headline.add_css_class("title-1")
        headline.set_halign(Gtk.Align.CENTER)
        hero.append(headline)

        sub = Gtk.Label(label=tr("Search official repos and AUR"))
        sub.add_css_class("body"); sub.add_css_class("dim-label")
        sub.set_halign(Gtk.Align.CENTER)
        hero.append(sub)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        search_row.set_halign(Gtk.Align.CENTER)
        search_row.set_size_request(520, -1)
        search_row.add_css_class("linked")

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text(tr("Search packages, e.g. firefox, vlc, git…"))
        self.search_entry.set_hexpand(True)
        self.search_entry.add_css_class("search-page-entry")
        self.search_entry.connect("changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        search_row.append(self.search_entry)

        search_btn = Gtk.Button()
        search_btn.set_icon_name("system-search-symbolic")
        search_btn.add_css_class("suggested-action")
        search_btn.connect("clicked", lambda *_: self._on_search_activate())
        search_row.append(search_btn)
        hero.append(search_row)
        root.append(hero)

        root.append(Gtk.Separator())

        # Results stack
        self._search_results_stack = Gtk.Stack()
        self._search_results_stack.set_vexpand(True)
        self._search_results_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self._search_results_stack.set_transition_duration(0)

        idle_page = Adw.StatusPage()
        idle_page.set_icon_name("system-search-symbolic")
        idle_page.set_title(tr("Find Packages"))
        idle_page.set_description(tr("Type above to search the official repositories and AUR."))
        self._search_results_stack.add_named(idle_page, "idle")

        spin_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        spin_box.set_halign(Gtk.Align.CENTER); spin_box.set_valign(Gtk.Align.CENTER)
        self._search_spinner = Gtk.Spinner()
        self._search_spinner.set_size_request(36, 36)
        spin_lbl = Gtk.Label(label=tr("Searching…"))
        spin_lbl.add_css_class("dim-label")
        spin_box.append(self._search_spinner)
        spin_box.append(spin_lbl)
        self._search_results_stack.add_named(spin_box, "searching")

        no_results = Adw.StatusPage()
        no_results.set_icon_name("system-search-symbolic")
        no_results.set_title(tr("No Results"))
        no_results.set_description(tr("Try different keywords or check your spelling."))
        self._search_results_stack.add_named(no_results, "empty")

        # Results paned — its own DetailPanel (self.search_panel), built below
        self._search_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._search_paned.set_position(380)
        self._search_paned.set_shrink_start_child(False)
        self._search_paned.set_shrink_end_child(False)

        results_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search_scroll = Gtk.ScrolledWindow()
        results_scroll = self.search_scroll
        results_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        results_scroll.set_vexpand(True)
        self.search_listview, self.search_store, self.search_selection, _ = \
            make_package_listview(self._on_search_activated,
                                   self._update_batch_action_bar,
                                   sel_state=self.pkg_sel_state)
        # Keep keyboard focus in the search entry as results stream in, so
        # search-as-you-type can't be interrupted by the list grabbing focus.
        self.search_listview.set_can_focus(False)
        results_scroll.set_child(self.search_listview)
        results_panel.append(results_scroll)

        results_action = Gtk.ActionBar()
        # Select all / deselect all button (toggles)
        self.search_btn_select_all = Gtk.Button()
        set_button_icon(self.search_btn_select_all, "edit-select-all-symbolic")
        self.search_btn_select_all.set_tooltip_text(tr("Select all visible packages"))
        self.search_btn_select_all.connect("clicked", self._on_select_all)
        self.search_btn_select_all.add_css_class("flat")
        self.search_btn_select_all.set_visible(False)
        results_action.pack_start(self.search_btn_select_all)

        # Deselect all button
        self.search_btn_deselect_all = Gtk.Button()
        set_button_icon(self.search_btn_deselect_all, "edit-clear-all-symbolic")
        self.search_btn_deselect_all.set_tooltip_text(tr("Deselect all packages"))
        self.search_btn_deselect_all.connect("clicked", self._on_deselect_all)
        self.search_btn_deselect_all.add_css_class("flat")
        self.search_btn_deselect_all.set_visible(False)
        results_action.pack_start(self.search_btn_deselect_all)

        self._search_btn_install = self._action_btn(
            "package-x-generic-symbolic", tr("Install"),
            "suggested-action", "install-btn", callback=self._on_install)
        self._search_btn_install.set_sensitive(False)
        results_action.pack_start(self._search_btn_install)
        self._search_count_lbl = Gtk.Label(label="")
        self._search_count_lbl.add_css_class("caption")
        self._search_count_lbl.add_css_class("dim-label")
        results_action.set_center_widget(self._search_count_lbl)
        self._search_btn_remove = self._action_btn(
            "user-trash-symbolic", tr("Uninstall"),
            "destructive-action", "remove-btn", callback=self._on_remove)
        self._search_btn_remove.set_sensitive(False)
        results_action.pack_end(self._search_btn_remove)
        results_panel.append(results_action)

        self._search_paned.set_start_child(results_panel)
        self._search_paned.set_end_child(self._build_search_detail_panel())
        self._search_results_stack.add_named(self._search_paned, "results")

        root.append(self._search_results_stack)
        return root

    # ── List+detail paned (Installed / AUR / Updates / Repos) ─────────────────

    def _build_list_detail_paned(self):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(380)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_start_child(self._build_package_list_panel())
        paned.set_end_child(self._build_detail_panel())
        return paned


    # ── Search detail panel (independent copy for search paned) ──────────────

    def _build_search_detail_panel(self):
        self.search_panel = DetailPanel(
            self._action_btn, self._on_install, self._on_remove,
            self._on_reinstall, self._on_downgrade)
        self.search_panel.dep_callback = self._search_dep
        return self.search_panel.stack

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
        outer.append(self._sidebar_header(tr("BROWSE")))
        self.nav_listbox = Gtk.ListBox()
        self.nav_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_listbox.add_css_class("navigation-sidebar")
        self.nav_listbox.set_margin_start(5); self.nav_listbox.set_margin_end(5)
        self.nav_listbox.connect("row-activated", self._on_nav_selected)

        self._nav_rows = {}
        browse_items = [
            ("search",    "system-search-symbolic",             tr("Search"),        None, None),
            ("installed", "emblem-ok-symbolic",                 tr("Installed"),     None, None),
            ("foreign",   "application-x-executable-symbolic", tr("AUR / Foreign"), None, "count-foreign"),
            ("updates",   ICON_UPDATE_AVAILABLE,               tr("Updates"),        None, "count-update"),
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
            (ICON_UPDATE_AVAILABLE,    tr("Check Updates"), self._on_check_updates),
            (ICON_RATE_MIRRORS,        tr("Rate Mirrors"),  self._on_rate_mirrors),
            ("user-trash-symbolic",    tr("Find Orphans"),  self._on_show_orphans),
            (ICON_CLEAN_CACHE,         tr("Clean Cache"),   self._on_clean_cache),
        ]:
            btn = Gtk.Button()
            btn.add_css_class("flat"); btn.add_css_class("nav-row")
            row_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row_inner.set_margin_top(5); row_inner.set_margin_bottom(5); row_inner.set_margin_start(10)
            ic = make_icon(icon_name, 16)
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

        self.empty_updates_page = Adw.StatusPage()
        self.empty_updates_page.set_icon_name("emblem-ok-symbolic")
        self.empty_updates_page.set_title(tr("System is up to date"))
        self.empty_updates_page.set_description(tr("No pending updates found."))

        self.empty_generic_page = Adw.StatusPage()
        self.empty_generic_page.set_icon_name("system-search-symbolic")
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

        action_bar = Gtk.ActionBar()
        # Select all button
        self.btn_select_all = Gtk.Button()
        set_button_icon(self.btn_select_all, "edit-select-all-symbolic")
        self.btn_select_all.set_tooltip_text(tr("Select all visible packages"))
        self.btn_select_all.connect("clicked", self._on_select_all)
        self.btn_select_all.add_css_class("flat")
        self.btn_select_all.set_visible(False)
        action_bar.pack_start(self.btn_select_all)

        # Deselect all button
        self.btn_deselect_all = Gtk.Button()
        set_button_icon(self.btn_deselect_all, "edit-clear-all-symbolic")
        self.btn_deselect_all.set_tooltip_text(tr("Deselect all packages"))
        self.btn_deselect_all.connect("clicked", self._on_deselect_all)
        self.btn_deselect_all.add_css_class("flat")
        self.btn_deselect_all.set_visible(False)
        action_bar.pack_start(self.btn_deselect_all)

        self.btn_install = self._action_btn(
            "package-x-generic-symbolic", tr("Install"),
            "suggested-action", "install-btn", callback=self._on_install)
        self.btn_install.set_sensitive(False)
        action_bar.pack_start(self.btn_install)

        self.pkg_count_label = Gtk.Label(label="")
        self.pkg_count_label.add_css_class("caption"); self.pkg_count_label.add_css_class("dim-label")
        action_bar.set_center_widget(self.pkg_count_label)

        self.btn_remove = self._action_btn(
            "user-trash-symbolic", tr("Uninstall"),
            "destructive-action", "remove-btn", callback=self._on_remove)
        self.btn_remove.set_sensitive(False)
        action_bar.pack_end(self.btn_remove)

        self.btn_upgrade_all = self._action_btn(
            "software-update-available-symbolic", tr("Upgrade All"),
            "suggested-action", callback=self._on_upgrade)
        self.btn_upgrade_all.set_sensitive(False); self.btn_upgrade_all.set_visible(False)
        action_bar.pack_start(self.btn_upgrade_all)

        self.btn_check_updates = self._action_btn(
            "view-refresh-symbolic", tr("Check for Updates"), callback=self._on_check_updates)
        self.btn_check_updates.set_visible(False)
        action_bar.pack_end(self.btn_check_updates)

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
        ic = Gtk.Image.new_from_icon_name(icon); ic.set_pixel_size(16)
        inner.append(ic); inner.append(Gtk.Label(label=label))
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
        # Only render the list if we're on a list page — skip if on Search
        if self.main_stack.get_visible_child_name() != "search":
            self._apply_filter()
        else:
            self.list_stack.set_visible_child_name("list")
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
        app.send_notification("pachul-updates", notif)

    def _on_updates_loaded(self, updates):
        prev_n = len(self._updates) if self._updates else 0
        self._updates = updates
        n = len(updates)
        self.stat_updates._num.set_label(str(n))
        self._nav_rows["updates"].set_count(n)
        if n > 0:
            self.update_banner.set_title(
                tr("{n} update available").format(n=n) if n == 1
                else tr("{n} updates available").format(n=n))
            self.update_banner.set_revealed(True)
            # Desktop notification when the update count first rises.
            if n != prev_n and get_setting("notify_updates"):
                self._notify_updates(n)
        else:
            self.update_banner.set_revealed(False)
        self.empty_updates_page.set_description(
            tr("No pending updates found.") if n == 0
            else tr("{n} update(s) available.").format(n=n))
        self._update_action_bar_mode()
        self._reapply_update_markers()
        if self.main_stack.get_visible_child_name() != "search":
            self._apply_filter()
        return False

    def _reapply_update_markers(self):
        """Sync the 'update' status on _all_packages with the current
        self._updates set. Marks pending updates and clears stale ones, so a
        fresh package reload (e.g. after installing/updating) reflects reality."""
        update_map = {u["name"]: u["new"] for u in (self._updates or [])}
        for pkg in self._all_packages:
            if pkg["name"] in update_map:
                pkg["status"] = "update"
                pkg["new_version"] = update_map[pkg["name"]]
            elif pkg.get("status") == "update":
                pkg["status"] = "installed"
                pkg.pop("new_version", None)

    def _update_sidebar_counts(self):
        total     = len(self._all_packages)
        foreign   = sum(1 for p in self._all_packages if p.get("foreign", False))
        installed = sum(1 for p in self._all_packages if p["status"] == "installed")
        self.stat_total._num.set_label(str(total))
        self.stat_aur._num.set_label(str(foreign))
        self._nav_rows["installed"].set_count(installed)
        self._nav_rows["foreign"].set_count(foreign)

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

    def _apply_filter(self):
        """Filter in a background thread, render in batches to avoid UI freeze."""
        filt = self._current_filter
        pkgs_snapshot = list(self._all_packages)

        def do_filter():
            filtered = []
            for pkg in pkgs_snapshot:
                if filt == "installed" and pkg["status"] not in ("installed", "update"):
                    continue
                if filt == "foreign" and not pkg.get("foreign", False):
                    continue
                if filt == "updates" and pkg.get("status") != "update":
                    continue
                if filt in ("core", "extra", "multilib", "community")                         and pkg.get("repo", "").lower() != filt:
                    continue
                if filt == "aur" and not pkg.get("foreign", False):
                    continue
                filtered.append(pkg)
            if self._alive:
                GLib.idle_add(self._render_filter_results, filtered, filt)

        threading.Thread(target=do_filter, daemon=True).start()

    @staticmethod
    def _make_item(p):
        return PackageItem(
            p["name"], p["version"], p.get("repo", "local"), p["status"],
            p.get("description", ""), p.get("foreign", False))

    def _fill_pkg_store(self, filtered):
        # One splice replaces the whole list; the ListView renders only the
        # visible rows, so there's no need to chunk widget creation any more.
        items = [self._make_item(p) for p in filtered]
        self.pkg_store.splice(0, self.pkg_store.get_n_items(), items)

    def _render_filter_results(self, filtered, filt):
        if not self._alive or self._current_filter != filt:
            return False
        self._fill_pkg_store(filtered)
        total = len(self._all_packages)
        shown = len(filtered)
        self.pkg_count_label.set_label(
            f"{shown} of {total} packages" if shown != total else f"{total} packages")
        if shown == 0:
            self.list_stack.set_visible_child_name(
                "empty_updates" if filt == "updates" and self._updates is not None
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
        self._cancel_search_timer()
        if not q:
            self._search_spinner.stop()
            self._search_results_stack.set_visible_child_name("idle")
            return
        # Show the searching state immediately, but defer the actual
        # (subprocess-spawning) search until typing pauses.
        self._search_results_stack.set_visible_child_name("searching")
        self._search_spinner.start()
        self._search_timer = GLib.timeout_add(
            self.SEARCH_DEBOUNCE_MS, self._run_search, q)

    def _on_search_activate(self, *_):
        q = self.search_entry.get_text().strip()
        self._cancel_search_timer()
        if not q:
            self._search_results_stack.set_visible_child_name("idle")
            return
        self._search_results_stack.set_visible_child_name("searching")
        self._search_spinner.start()
        self._run_search(q)

    def _run_search(self, q):
        self._search_timer = None

        def worker(query):
            ql = query.lower()
            local = [p for p in self._all_packages
                     if ql in p["name"].lower() or ql in p.get("description", "").lower()]
            if self._alive:
                GLib.idle_add(self._show_search_results, local, query)
            remote = search_packages_cmd(query)
            if self._alive:
                GLib.idle_add(self._merge_and_show_search, remote, query)

        threading.Thread(target=worker, args=(q,), daemon=True).start()
        return False   # one-shot: do not repeat the timeout

    def _show_search_results(self, results, query):
        if self.search_entry.get_text().strip().lower() != query.lower():
            return False
        self._populate_search_list(results)
        return False

    def _merge_and_show_search(self, remote_results, query):
        if self.search_entry.get_text().strip().lower() != query.lower():
            return False
        existing = {p["name"] for p in self._all_packages}
        for r in remote_results:
            if r["name"] not in existing:
                self._all_packages.append(r)
                existing.add(r["name"])
        ql = query.lower()
        merged = [p for p in self._all_packages
                  if ql in p["name"].lower() or ql in p.get("description", "").lower()]
        self._populate_search_list(merged)
        return False

    def _populate_search_list(self, results):
        self._search_spinner.stop()
        if not results:
            self.search_store.remove_all()
            if self._search_results_stack.get_visible_child_name() != "empty":
                self._search_results_stack.set_visible_child_name("empty")
            return
        items = [self._make_item(p) for p in results]
        self.search_store.splice(0, self.search_store.get_n_items(), items)
        n = len(results)
        self._search_count_lbl.set_label(
            tr("{n} result").format(n=n) if n == 1 else tr("{n} results").format(n=n))
        # Only switch to results page if not already there — avoids any redraw flash
        if self._search_results_stack.get_visible_child_name() != "results":
            self._search_results_stack.set_visible_child_name("results")

    def _on_search_activated(self, pkg):
        if pkg is None:
            return
        self._selected_pkg = pkg
        installed = pkg.pkg_status in ("installed", "update")
        # An "update" package is installed but upgradable — Install stays
        # active and runs `pacman -S`, which upgrades that single package.
        can_install = pkg.pkg_status != "installed"
        install_label = tr("Update") if pkg.pkg_status == "update" else tr("Install")
        self._set_btn_label(self._search_btn_install, install_label)
        self._set_btn_label(self.search_panel.btn_install, install_label)
        self._search_btn_install.set_sensitive(can_install)
        self._search_btn_remove.set_sensitive(installed)
        self.search_panel.btn_install.set_sensitive(can_install)
        self.search_panel.btn_remove.set_sensitive(installed)
        self.search_panel.btn_reinstall.set_sensitive(installed)
        self.search_panel.btn_downgrade.set_sensitive(installed)
        self._show_detail(self.search_panel, pkg)

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
        if key == "search":
            self.main_stack.set_visible_child_name("search")
            self._current_filter = "search"
            GLib.idle_add(self._grab_search_focus)
            return
        if key == "orphans":
            self._on_show_orphans()
            return
        self._current_filter = key
        self.main_stack.set_visible_child_name("list")
        self._update_action_bar_mode()
        self._apply_filter()

    def _on_repo_nav_selected(self, listbox, row):
        self.nav_listbox.unselect_all()
        keys = list(self._repo_nav_rows.keys())
        idx  = row.get_index()
        if idx < len(keys):
            self._current_filter = keys[idx]
        self.main_stack.set_visible_child_name("list")
        self._update_action_bar_mode()
        self._apply_filter()

    def _update_action_bar_mode(self):
        is_updates = (self._current_filter == "updates")
        # Selection mode now persists across views (Installed/Updates/repos/
        # search) — while it's active, always show the batch Install/Remove
        # buttons instead of the Updates-specific ones, so a person can act
        # on their pick no matter which sidebar filter they're looking at.
        selecting = self.pkg_sel_state.active
        show_batch_buttons = selecting or not is_updates
        self.btn_install.set_visible(show_batch_buttons)
        self.btn_remove.set_visible(show_batch_buttons)
        self.btn_upgrade_all.set_visible(is_updates and not selecting)
        self.btn_check_updates.set_visible(is_updates and not selecting)
        if is_updates and not selecting:
            n = len(self._updates) if self._updates else 0
            self.btn_upgrade_all.set_sensitive(n > 0)

        # Select/deselect buttons visibility
        has_selection = len(self.pkg_sel_state.selected) > 0
        self.btn_select_all.set_visible(selecting)
        self.search_btn_select_all.set_visible(selecting)
        self.btn_deselect_all.set_visible(selecting and has_selection)
        self.search_btn_deselect_all.set_visible(selecting and has_selection)

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
        self._set_btn_label(self.btn_install, install_label)
        self._set_btn_label(self.detail_panel.btn_install, install_label)
        self.btn_install.set_sensitive(can_install)
        self.btn_remove.set_sensitive(installed)
        self.detail_panel.btn_install.set_sensitive(can_install)
        self.detail_panel.btn_remove.set_sensitive(installed)
        self.detail_panel.btn_reinstall.set_sensitive(installed)
        self.detail_panel.btn_downgrade.set_sensitive(installed)
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
        """Highlight dependency in the middle panel only; leave the right panel unchanged."""
        # Try current list first
        if self._highlight_in_store(self.pkg_store, self.pkg_selection,
                                    self.pkg_listview, pkg_name):
            return

        # Switch to "installed" filter to make it visible, then highlight
        self._current_filter = "installed"
        self.nav_listbox.select_row(self._nav_rows["installed"])

        def after_filter():
            self._highlight_in_store(self.pkg_store, self.pkg_selection,
                                     self.pkg_listview, pkg_name)
            return False

        self._apply_filter_then(after_filter)

    def _apply_filter_then(self, callback):
        """Apply filter and run callback once rendering is done."""
        filt = self._current_filter
        pkgs_snapshot = list(self._all_packages)

        def do_filter():
            filtered = []
            for pkg in pkgs_snapshot:
                if filt == "installed" and pkg["status"] not in ("installed", "update"):
                    continue
                if filt == "foreign" and not pkg.get("foreign", False):
                    continue
                if filt == "updates" and pkg.get("status") != "update":
                    continue
                if filt in ("core", "extra", "multilib", "community")                         and pkg.get("repo", "").lower() != filt:
                    continue
                if filt == "aur" and not pkg.get("foreign", False):
                    continue
                filtered.append(pkg)
            if self._alive:
                GLib.idle_add(self._render_filter_results_then, filtered, filt, callback)

        threading.Thread(target=do_filter, daemon=True).start()

    def _render_filter_results_then(self, filtered, filt, callback):
        """Same as _render_filter_results but fires `callback` once rendered."""
        if not self._alive or self._current_filter != filt:
            return False
        self._fill_pkg_store(filtered)
        total = len(self._all_packages)
        shown = len(filtered)
        self.pkg_count_label.set_label(
            f"{shown} of {total} packages" if shown != total else f"{total} packages")
        if shown == 0:
            self.list_stack.set_visible_child_name(
                "empty_updates" if filt == "updates" and self._updates is not None
                else "empty_generic")
        else:
            self.list_stack.set_visible_child_name("list")
        if callback:
            GLib.idle_add(callback)
        return False

    def _search_dep(self, pkg_name):
        """Highlight dependency in the search results list only — no entry change, no flicker."""
        # If already in the current results list, just highlight it
        if self._highlight_in_store(self.search_store, self.search_selection,
                                    self.search_listview, pkg_name):
            return

        # Not visible — find it in _all_packages and insert it at the top of the list
        for pkg in self._all_packages:
            if pkg["name"] == pkg_name:
                self.search_store.insert(0, self._make_item(pkg))
                self.search_selection.set_selected(0)
                self.search_listview.scroll_to(0, Gtk.ListScrollFlags.FOCUS, None)
                return

        # Not in cache at all — fetch in background and prepend when ready
        def worker():
            results = search_packages_cmd(pkg_name)
            if self._alive:
                GLib.idle_add(self._prepend_dep_result, pkg_name, results)

        threading.Thread(target=worker, daemon=True).start()

    def _prepend_dep_result(self, pkg_name, results):
        for r in results:
            if r["name"] == pkg_name:
                if r["name"] not in {p["name"] for p in self._all_packages}:
                    self._all_packages.append(r)
                self.search_store.insert(0, self._make_item(r))
                self.search_selection.set_selected(0)
                self.search_listview.scroll_to(0, Gtk.ListScrollFlags.FOCUS, None)
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
        self.search_entry.set_text("")
        self._search_results_stack.set_visible_child_name("idle")
        self.detail_panel.stack.set_visible_child_name("empty")
        self._selected_pkg = None
        self.pkg_sel_state.selected.clear()
        if self.btn_selection_mode.get_active():
            self.btn_selection_mode.set_active(False)  # fires _on_toggle_selection_mode
        self.btn_install.set_sensitive(False)
        self.btn_remove.set_sensitive(False)
        self.update_banner.set_revealed(False)
        self._load_packages()

    def _on_sync_db(self, *_):
        invalidate_syncdb_cache()
        self._run_terminal("sudo -S pacman -Sy --noconfirm", tr("Sync Databases"))

    def _on_upgrade(self, *_):
        if get_setting("show_news_before_upgrade"):
            show_news_dialog(self, self._do_upgrade)
        else:
            self._do_upgrade()

    def _do_upgrade(self):
        def _after():
            self.update_banner.set_revealed(False)
            self._updates = []
            self.stat_updates._num.set_label("0")
            self._nav_rows["updates"].set_count(0)
        # Use the AUR helper if present so repo *and* AUR packages are upgraded.
        helper = self._get_aur_helper()
        cmd = f"{helper} -Syu --noconfirm" if helper else "sudo -S pacman -Syu --noconfirm"
        if get_setting("snapshot_before_upgrade"):
            snap_cmd = build_snapshot_cmd()
            if snap_cmd:
                cmd = f"{snap_cmd} && {cmd}"
        self._run_terminal(cmd, tr("System Upgrade"), on_success=_after)

    def _on_clean_cache(self, *_):
        self._run_terminal(
            "sudo -S -v && { paccache -rk2 2>/dev/null || sudo pacman -Sc --noconfirm; }",
            tr("Clean Cache"))

    def _on_check_updates(self, *_):
        helper = self._get_aur_helper()
        aur = (f"; echo; echo '== AUR =='; {helper} -Qua 2>/dev/null") if helper else ""
        self._run_terminal(
            f"{{ checkupdates 2>/dev/null || pacman -Qu 2>/dev/null; }}{aur}"
            "; echo; echo 'Done.'",
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
        currently = pkg.pkg_name in get_ignored_packages()
        tmp = set_package_ignored(pkg.pkg_name, not currently)
        if tmp is None:
            self._toast(tr("Could not read /etc/pacman.conf"))
            return
        verb = tr("Unhold") if currently else tr("Hold")
        self._run_terminal(
            f"sudo -S install -m644 {shlex.quote(tmp)} /etc/pacman.conf",
            f"{verb} {pkg.pkg_name}")

    def _on_preferences(self, *_):
        show_preferences(self, self._on_settings_changed)

    def _on_settings_changed(self):
        # AUR-helper / include-AUR changes can affect the update set — re-check.
        if self._alive:
            threading.Thread(target=self._bg_check_updates, daemon=True).start()

    def _on_show_shortcuts(self, *_):
        show_shortcuts_dialog(self)

    def _on_focus_search(self, *_):
        self.main_stack.set_visible_child_name("search")
        self._current_filter = "search"
        self.nav_listbox.unselect_all()
        self.repo_listbox.unselect_all()
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
        self._run_terminal(
            f"sudo -S pacman -D --asexplicit {shlex.quote(pkg.pkg_name)}",
            tr("Mark {name} as explicit").format(name=pkg.pkg_name), on_success=self._refresh_selected_pkg)

    def _on_mark_asdeps(self, *_):
        pkg = self._selected_pkg
        if not pkg:
            self._toast(tr("Select a package first"))
            return
        self._run_terminal(
            f"sudo -S pacman -D --asdeps {shlex.quote(pkg.pkg_name)}",
            tr("Mark {name} as dependency").format(name=pkg.pkg_name), on_success=self._refresh_selected_pkg)

    def _on_export_pkgs(self, *_):
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
        quoted = " ".join(shlex.quote(n) for n in names)
        helper = self._get_aur_helper()
        if helper:
            cmd = f"{helper} -S --needed --noconfirm {quoted}"
        else:
            cmd = f"sudo -S pacman -S --needed --noconfirm {quoted}"
        self._run_terminal(cmd, tr("Install {n} packages").format(n=len(names)))

    # ── Multi-select / batch actions ─────────────────────────────────────────

    def _on_toggle_selection_mode(self, btn):
        active = btn.get_active()
        state = self.pkg_sel_state
        if active:
            # Remember the normal count-label text so we can restore it
            # exactly when selection mode ends.
            self._pre_selection_count_label = self.pkg_count_label.get_label()
            self._pre_selection_search_count_label = self._search_count_lbl.get_label()
        state.active = active
        if not active:
            state.selected.clear()
            # Restore the empty (or last selected) detail view
            self.detail_panel.stack.set_visible_child_name("empty")
            self.search_panel.stack.set_visible_child_name("empty")
        # Force every currently-realized row in BOTH lists to rebind so
        # checkboxes appear/disappear immediately — not just after a data
        # reload from switching sidebar filters. Signalling the store
        # (items_changed / splice-with-same-objects) turned out to NOT be
        # reliably picked up by GtkListView for rows that are already bound
        # and on screen. Detaching and reattaching the ListView's model is
        # the one approach that unconditionally forces GTK to tear down and
        # rebuild every visible row against the current sel_state — but it
        # also resets scroll position, so we save/restore it around it.
        for lv, scroll in ((self.pkg_listview, self.pkg_scroll),
                            (self.search_listview, self.search_scroll)):
            model = lv.get_model()
            if model is None:
                continue
            vadj = scroll.get_vadjustment()
            saved_pos = vadj.get_value() if vadj is not None else None
            lv.set_model(None)
            lv.set_model(model)
            if saved_pos:
                def _restore(scroll=scroll, saved_pos=saved_pos):
                    vadj = scroll.get_vadjustment()
                    if vadj is not None:
                        vadj.set_value(saved_pos)
                    return False
                # Restore after GTK has finished laying out the reattached
                # model — doing it in the same frame gets overwritten.
                GLib.idle_add(_restore)
        if active:
            self._update_batch_action_bar()
            self._update_action_bar_mode()
        else:
            self.pkg_count_label.set_label(getattr(self, "_pre_selection_count_label", ""))
            if self._selected_pkg is not None:
                self._on_pkg_activated(self._selected_pkg)
            else:
                self._set_btn_label(self.btn_install, tr("Install"))
                self._set_btn_label(self.btn_remove, tr("Uninstall"))
                self.btn_install.set_sensitive(False)
                self.btn_remove.set_sensitive(False)

            self._search_count_lbl.set_label(
                getattr(self, "_pre_selection_search_count_label", ""))
            search_sel = self.search_selection.get_selected_item()
            if search_sel is not None:
                self._on_search_activated(search_sel)
            else:
                self._set_btn_label(self._search_btn_install, tr("Install"))
                self._set_btn_label(self._search_btn_remove, tr("Uninstall"))
                self._search_btn_install.set_sensitive(False)
                self._search_btn_remove.set_sensitive(False)
            self._update_action_bar_mode()

    def _iter_known_packages(self):
        """Yield every PackageItem currently loaded in either list (main +
        search), so batch actions work no matter which view a package was
        selected from — selection is shared and survives switching views."""
        for store in (self.pkg_store, self.search_store):
            for i in range(store.get_n_items()):
                item = store.get_item(i)
                if item is not None:
                    yield item

    def _update_batch_action_bar(self):
        """Recompute install/remove buckets + labels for the current
        selection, across BOTH the main list and search results, and update
        both action bars in sync.

        Also serves as the `on_selection_change` callback fired by either
        ListView every time a checkbox is toggled.
        """
        state = self.pkg_sel_state
        if not state.active:
            return
        seen = set()
        to_install, to_remove = [], []
        selected_names = []
        for item in self._iter_known_packages():
            if item.pkg_name in state.selected and item.pkg_name not in seen:
                seen.add(item.pkg_name)
                selected_names.append(item.pkg_name)
                if item.pkg_status in ("installed", "update"):
                    to_remove.append(item.pkg_name)
                else:
                    to_install.append(item.pkg_name)
        self._batch_install_names = to_install
        self._batch_remove_names = to_remove
        n = len(state.selected)
        count_text = tr("{n} selected").format(n=n) if n else tr("Select packages…")
        install_label = tr("Install ({n})").format(n=len(to_install))
        remove_label = tr("Remove ({n})").format(n=len(to_remove))

        self.pkg_count_label.set_label(count_text)
        self._set_btn_label(self.btn_install, install_label)
        self._set_btn_label(self.btn_remove, remove_label)
        self.btn_install.set_sensitive(len(to_install) > 0)
        self.btn_remove.set_sensitive(len(to_remove) > 0)

        self._search_count_lbl.set_label(count_text)
        self._set_btn_label(self._search_btn_install, install_label)
        self._set_btn_label(self._search_btn_remove, remove_label)
        self._search_btn_install.set_sensitive(len(to_install) > 0)
        self._search_btn_remove.set_sensitive(len(to_remove) > 0)

        # Show selected packages in the detail panels
        self.detail_panel.show_batch(selected_names)
        self.search_panel.show_batch(selected_names)

        # Update select/deselect button visibility
        has_selection = n > 0
        self.btn_deselect_all.set_visible(has_selection)
        self.search_btn_deselect_all.set_visible(has_selection)

    def _pkg_is_foreign(self, name):
        for item in self._iter_known_packages():
            if item.pkg_name == name:
                return item.pkg_foreign
        return False

    def _exit_selection_mode(self):
        if self.pkg_sel_state.active:
            self.btn_selection_mode.set_active(False)  # fires _on_toggle_selection_mode

    # ---- NEUE METHODE: Suchliste synchronisieren ----
    def _sync_search_store_with_all_packages(self):
        """Update all PackageItems in the search store to reflect current _all_packages data."""
        if self.search_store.get_n_items() == 0:
            return
        all_by_name = {p["name"]: p for p in self._all_packages}
        to_replace = []
        for i in range(self.search_store.get_n_items()):
            item = self.search_store.get_item(i)
            if item is None:
                continue
            pkg_data = all_by_name.get(item.pkg_name)
            if pkg_data:
                new_item = self._make_item(pkg_data)
                to_replace.append((i, new_item))
        for i, new_item in to_replace:
            self.search_store.splice(i, 1, [new_item])

    # ---- NEUE METHODE: Alle auswählen ----
    def _on_select_all(self, *_):
        """Select all packages currently visible in the active list (main or search)."""
        state = self.pkg_sel_state
        if not state.active:
            return

        # Determine which store is currently active
        if self.main_stack.get_visible_child_name() == "search":
            store = self.search_store
        else:
            store = self.pkg_store

        # Collect all package names from the store
        all_names = []
        for i in range(store.get_n_items()):
            item = store.get_item(i)
            if item is not None:
                all_names.append(item.pkg_name)

        if not all_names:
            return

        # Replace the selected set with all names
        state.selected.clear()
        state.selected.update(all_names)

        # Update the batch action bar and detail panels
        self._update_batch_action_bar()

        # Force refresh of visible rows to update checkboxes
        for lv, scroll in ((self.pkg_listview, self.pkg_scroll),
                            (self.search_listview, self.search_scroll)):
            model = lv.get_model()
            if model is None:
                continue
            vadj = scroll.get_vadjustment()
            saved_pos = vadj.get_value() if vadj is not None else None
            lv.set_model(None)
            lv.set_model(model)
            if saved_pos:
                def _restore(scroll=scroll, saved_pos=saved_pos):
                    vadj = scroll.get_vadjustment()
                    if vadj is not None:
                        vadj.set_value(saved_pos)
                    return False
                GLib.idle_add(_restore)

        # Update action bar mode to show deselect button
        self._update_action_bar_mode()

    # ---- NEUE METHODE: Alle abwählen ----
    def _on_deselect_all(self, *_):
        """Deselect all packages."""
        state = self.pkg_sel_state
        if not state.active:
            return

        state.selected.clear()
        self._update_batch_action_bar()
        self._update_action_bar_mode()

        # Force refresh of visible rows to update checkboxes
        for lv, scroll in ((self.pkg_listview, self.pkg_scroll),
                            (self.search_listview, self.search_scroll)):
            model = lv.get_model()
            if model is None:
                continue
            vadj = scroll.get_vadjustment()
            saved_pos = vadj.get_value() if vadj is not None else None
            lv.set_model(None)
            lv.set_model(model)
            if saved_pos:
                def _restore(scroll=scroll, saved_pos=saved_pos):
                    vadj = scroll.get_vadjustment()
                    if vadj is not None:
                        vadj.set_value(saved_pos)
                    return False
                GLib.idle_add(_restore)

    def _on_batch_install(self):
        names = list(getattr(self, "_batch_install_names", []))
        if not names:
            return
        helper = self._get_aur_helper()
        if not helper:
            # Plain pacman can't install AUR packages — drop them and warn,
            # instead of silently failing the whole transaction.
            foreign = [n for n in names if self._pkg_is_foreign(n)]
            if foreign:
                names = [n for n in names if n not in foreign]
                self._toast(tr("No AUR helper found — skipped {n} AUR package(s).")
                           .format(n=len(foreign)))
            if not names:
                return
        quoted = " ".join(shlex.quote(n) for n in names)
        cmd = f"{helper} -S --noconfirm {quoted}" if helper \
              else f"sudo -S pacman -S --noconfirm {quoted}"
        self._run_terminal(cmd, tr("Install {n} packages").format(n=len(names)),
                           on_success=lambda: (self._sync_search_store_with_all_packages(),
                                               self._exit_selection_mode()))

    def _on_batch_remove(self):
        names = list(getattr(self, "_batch_remove_names", []))
        if not names:
            return

        def do_remove():
            quoted = " ".join(shlex.quote(n) for n in names)
            self._run_terminal(
                f"sudo -S pacman -R --noconfirm {quoted}",
                tr("Remove {n} packages").format(n=len(names)),
                on_success=lambda: (self._sync_search_store_with_all_packages(),
                                    self._exit_selection_mode()))

        if not get_setting("confirm_remove"):
            do_remove()
            return

        d = Adw.AlertDialog()
        d.set_heading(tr("Remove {n} packages?").format(n=len(names)))
        d.set_body(tr("This will remove the {n} selected packages from your system.")
                   .format(n=len(names)))
        d.add_response("cancel", tr("Cancel")); d.add_response("remove", tr("Remove"))
        d.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("cancel"); d.set_close_response("cancel")
        d.connect("response", lambda dlg, resp: resp == "remove" and do_remove())
        d.present(self)

    def _on_install(self, *_):
        if self.pkg_sel_state.active:
            self._on_batch_install()
            return
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg
        name = shlex.quote(pkg.pkg_name)
        if pkg.pkg_foreign:
            helper = self._get_aur_helper()
            cmd = f"{helper} -S --noconfirm {name}" if helper \
                  else f"sudo -S pacman -S --noconfirm {name}"
        else:
            cmd = f"sudo -S pacman -S --noconfirm {name}"
        self._run_terminal(cmd, tr("Install {name}").format(name=pkg.pkg_name),
                           on_success=self._refresh_selected_pkg)

    def _on_remove(self, *_):
        if self.pkg_sel_state.active:
            self._on_batch_remove()
            return
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg

        def do_remove():
            self._run_terminal(
                f"sudo -S pacman -R --noconfirm {shlex.quote(pkg.pkg_name)}",
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
        name = shlex.quote(pkg.pkg_name)
        if pkg.pkg_foreign:
            helper = self._get_aur_helper()
            cmd = f"{helper} -S --noconfirm {name}" if helper \
                  else f"sudo -S pacman -S --noconfirm {name}"
        else:
            cmd = f"sudo -S pacman -S --noconfirm {name}"
        self._run_terminal(cmd, tr("Reinstall {name}").format(name=pkg.pkg_name),
                           on_success=self._refresh_selected_pkg)

    def _refresh_selected_pkg(self):
        if not self._selected_pkg:
            return
        pkg = self._selected_pkg
        out, code = run_command(f"pacman -Qi {shlex.quote(pkg.pkg_name)} 2>/dev/null")
        pkg.pkg_status = "installed" if (code == 0 and out) else "available"
        installed = pkg.pkg_status == "installed"
        self.btn_install.set_sensitive(not installed)
        self.btn_remove.set_sensitive(installed)
        self._search_btn_install.set_sensitive(not installed)
        self._search_btn_remove.set_sensitive(installed)
        for panel in (self.detail_panel, self.search_panel):
            panel.btn_install.set_sensitive(not installed)
            self._set_btn_label(panel.btn_install, tr("Install"))
            panel.btn_remove.set_sensitive(installed)
            panel.btn_reinstall.set_sensitive(installed)
            panel.btn_downgrade.set_sensitive(installed)
            self._set_status_pill(panel, pkg.pkg_status, pkg.pkg_foreign)
        self._set_btn_label(self.btn_install, tr("Install"))
        self._set_btn_label(self._search_btn_install, tr("Install"))
        # If the package was a pending update and is now installed, drop it
        # from the updates set so it leaves the Updates list right away.
        if installed and self._updates and any(
                u["name"] == pkg.pkg_name for u in self._updates):
            self._updates = [u for u in self._updates
                             if u["name"] != pkg.pkg_name]
            n = len(self._updates)
            self.stat_updates._num.set_label(str(n))
            self._nav_rows["updates"].set_count(n)
            if n == 0:
                self.update_banner.set_revealed(False)
            for p in self._all_packages:
                if p["name"] == pkg.pkg_name:
                    p["status"] = "installed"
                    p.pop("new_version", None)
            if self.main_stack.get_visible_child_name() != "search":
                self._apply_filter()
        if installed:
            def worker():
                info  = get_package_info(pkg.pkg_name)
                files = get_package_files(pkg.pkg_name)
                if self._alive:
                    GLib.idle_add(self._populate_both_panels, info, files)
            threading.Thread(target=worker, daemon=True).start()

        # Suchliste mit aktuellen Daten synchronisieren
        self._sync_search_store_with_all_packages()
        # Batch-Leiste aktualisieren, falls im Batch-Modus
        if self.pkg_sel_state.active:
            self._update_batch_action_bar()

    def _populate_both_panels(self, info, files):
        self._populate_detail(self.detail_panel, info, files)
        self._populate_detail(self.search_panel, info, files)
        return False

    def _get_aur_helper(self):
        if self._aur_helper_cache is None:
            for h in ("paru", "yay", "pikaur", "trizen"):
                _, c = run_command(f"which {h} 2>/dev/null")
                if c == 0:
                    self._aur_helper_cache = h
                    break
        return self._aur_helper_cache
