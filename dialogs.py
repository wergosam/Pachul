"""
Pachul — dialogs.py
All modal tool dialogs:
  - TerminalDialog  : PTY-backed command runner. Privileged commands use
                      pkexec, so authentication happens in the desktop's
                      own native Polkit dialog (GNOME/KDE), not in a
                      password field built by Pachul itself — Pachul never
                      sees the password. The dialog's input row is now a
                      generic "send text to the running command" field for
                      the rare interactive [y/n]-style prompt, not for
                      passwords.
  - RepoManagerDialog : edit the repositories listed in /etc/pacman.conf
  - MirrorRaterDialog : front end for the rate-mirrors tool
  - OrphanFinderDialog: find and remove orphaned packages
  - SysInfoDialog     : overview of system information
"""

import os
import pty
import re as _re
import shlex
import signal
import select
import fcntl
import termios
import struct
import tempfile
import threading
import urllib.parse
from datetime import datetime
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gdk

import distro
import pkgmanager
import localpkg
from backend import (run_command, get_orphans, get_system_info,
                     get_pacman_history,
                     get_downgrade_candidates, build_downgrade_cmd, is_foreign_package,
                     get_pkgbuild, get_pacnew_files, get_file_diff, get_setting, save_settings,
                     files_db_available, search_file_owner, get_package_cache_size,
                     get_tool_updates, paru_installed, get_paru_bootstrap_cmd,
                     get_ignored_packages, build_hold_cmd_bulk, APP_VERSION,
                     aur_helper_install_cmd, pachuli_installed, local_pachuli_path,
                     get_pachuli_install_cmd, pachuli_update_available,
                     local_pachuli_version, installed_pachuli_version)
from i18n import tr, get_language, set_language
from icons import themed_image, themed_paintable


# ─── Kleine Widget-Bausteine ──────────────────────────────────────────────────

_AUTO = Gtk.PolicyType.AUTOMATIC
_NEVER = Gtk.PolicyType.NEVER


def _linear_box(orientation, gap, classes):
    box = Gtk.Box()
    box.set_orientation(orientation)
    box.set_spacing(gap)
    for name in classes:
        box.add_css_class(name)
    return box


def _vbox(gap=0, *classes):
    """Vertikale Gtk.Box mit Abstand und optionalen CSS-Klassen."""
    return _linear_box(Gtk.Orientation.VERTICAL, gap, classes)


def _hbox(gap=0, *classes):
    """Horizontale Gtk.Box mit Abstand und optionalen CSS-Klassen."""
    return _linear_box(Gtk.Orientation.HORIZONTAL, gap, classes)


def _pad(widget, start=None, end=None, top=None, bottom=None):
    """Setzt nur die angegebenen Aussenabstände."""
    for value, setter in ((start, widget.set_margin_start),
                          (end, widget.set_margin_end),
                          (top, widget.set_margin_top),
                          (bottom, widget.set_margin_bottom)):
        if value is not None:
            setter(value)
    return widget


def _btn(label, *classes):
    """Gtk.Button mit Beschriftung und CSS-Klassen."""
    button = Gtk.Button(label=label)
    for name in classes:
        button.add_css_class(name)
    return button


def _scrolled(h_policy, v_policy, *classes):
    """Gtk.ScrolledWindow mit Richtlinien und optionalen CSS-Klassen."""
    sw = Gtk.ScrolledWindow()
    sw.set_policy(h_policy, v_policy)
    for name in classes:
        sw.add_css_class(name)
    return sw


def _modal_window(parent, title, width, height):
    """Verschieb- und skalierbares modales Adw.Window über `parent`."""
    win = Adw.Window()
    win.set_title(title)
    win.set_default_size(width, height)
    win.set_resizable(True)
    win.set_transient_for(parent)
    win.set_modal(True)
    return win


def _status_page(icon_name, title, description):
    """Adw.StatusPage mit grossem Symbol, Titel und Beschreibung."""
    page = Adw.StatusPage()
    page.set_paintable(themed_paintable(icon_name, 72))
    page.set_title(title)
    page.set_description(description)
    return page


def _unlink_quietly(path):
    """Datei löschen; Fehler (z. B. schon weg) werden ignoriert."""
    try:
        os.unlink(path)
    except OSError:
        pass


def _centered(widget):
    """Widget vertikal zentrieren (für Suffix-Widgets in Zeilen)."""
    widget.set_valign(Gtk.Align.CENTER)
    return widget


def _option_row(title, subtitle=None):
    """Adw.ActionRow mit Titel und optionalem Untertitel."""
    row = Adw.ActionRow(title=title)
    if subtitle:
        row.set_subtitle(subtitle)
    return row


def _switch_row(title, subtitle, active=True):
    """Zeile mit Schalter; gibt (row, switch) zurück."""
    switch = _centered(Gtk.Switch())
    switch.set_active(active)
    row = _option_row(title, subtitle)
    row.add_suffix(switch)
    row.set_activatable_widget(switch)
    return row, switch


def _toolbar_with_header():
    """Adw.ToolbarView samt HeaderBar (ohne Fenster-Buttons am rechten Rand)."""
    view = Adw.ToolbarView()
    bar = Adw.HeaderBar()
    bar.set_show_end_title_buttons(False)
    return view, bar


def _scroll_page(content):
    """Vertikal scrollbarer Rahmen um den Dialoginhalt (ohne Horizontal-Scroll)."""
    sw = _scrolled(_NEVER, _AUTO)
    sw.set_vexpand(True)
    sw.set_child(content)
    return sw


def _close_quietly(fd):
    """Dateideskriptor schliessen und einen bereits geschlossenen ignorieren."""
    try:
        os.close(fd)
    except OSError:
        pass


def _decode_pty_bytes(buf):
    """PTY-Bytes zu Text machen. Gibt (text, rest) zurück: ein abgeschnittenes
    UTF-8-Zeichen am Ende bleibt als `rest` für den nächsten Durchlauf stehen;
    ist gar nichts decodierbar, wird latin-1 verwendet."""
    try:
        return buf.decode("utf-8"), b""
    except UnicodeDecodeError:
        pass
    for end in range(len(buf), 0, -1):
        try:
            return buf[:end].decode("utf-8"), buf[end:]
        except UnicodeDecodeError:
            continue
    return buf.decode("latin-1"), b""


# ─── Terminal dialog ──────────────────────────────────────────────────────────

# Recognized pacman/GPG signature-failure patterns. `_GPG_KEY_ID_RE` catches
# the (rarer) case where pacman's output names a concrete key ID — e.g.
# ":: Import PGP key 6D42BDD116E0068F, ..." or "unknown public key <ID>".
# `_GPG_TRUST_RE` / `_GPG_GENERIC_RE` catch the far more common case seen
# with --noconfirm (the key gets auto-imported but stays untrusted):
#   error: <pkg>: signature from "Name <email>" is unknown trust
#   :: File ... is corrupted (invalid or corrupted package (PGP signature)).
# That case has no bare key ID to target, so the fix is a keyring refresh
# (the ArchWiki-recommended remedy: sync + reinstall archlinux-keyring).
_GPG_KEY_ID_RE = _re.compile(
    r'(?:unknown public key|Import PGP key|key ")\s*([0-9A-Fa-f]{8,40})',
    _re.IGNORECASE)
_GPG_TRUST_RE = _re.compile(r'signature from ".*?" is unknown trust', _re.IGNORECASE)
_GPG_GENERIC_RE = _re.compile(
    r'corrupted package \(PGP signature\)|PGP signatures? could not be verified',
    _re.IGNORECASE)

# Stale pacman database lock ("db.lck"). Pacman refuses to run at all while
# this file exists — usually a leftover from a crashed/killed previous run,
# a power loss, or a second package manager instance. Matches both English
# and German pacman wording, since this app is mostly used with a German
# system locale.
_DB_LOCK_RE = _re.compile(
    r'unable to lock database'
    r'|Datenbank (?:nicht sperren|konnte nicht gesperrt werden)',
    _re.IGNORECASE)


_FAILURE_LINE = _re.compile(r"^\s*(error|fehler|fatal|schwerwiegend)\b\s*:", _re.IGNORECASE)


def _failure_hint(full_text):
    """Short explanation appended below the "Failed" footer of a finished
    command: which output lines most likely caused the non-zero exit code,
    and — for multi-step runs (system update + AUR + firmware + Flatpak …) —
    the reminder that the other steps may well have succeeded."""
    lines = []
    for line in full_text.splitlines():
        if _FAILURE_LINE.match(line):
            line = line.strip()
            if line not in lines:
                lines.append(line)
    multi_step = "\n=== " in full_text
    if not lines and not multi_step:
        return ""
    out = ""
    if multi_step:
        out += tr("Note: this run had several steps. Steps above may have "
                  "completed successfully even though the whole run is "
                  "marked as failed.\n")
    if lines:
        out += tr("Probable cause (last error lines):\n")
        for line in lines[-3:]:
            out += "  " + (line if len(line) <= 160 else line[:157] + "…") + "\n"
    return out


def _detect_gpg_issue(text):
    """Return a hex key ID, "" (generic — no ID found), or None (no GPG issue)."""
    if not distro.is_arch():
        return pkgmanager.detect_gpg_issue(text)
    m = _GPG_KEY_ID_RE.search(text)
    if m:
        return m.group(1).upper()
    if _GPG_TRUST_RE.search(text) or _GPG_GENERIC_RE.search(text):
        return ""
    return None


def _detect_lock_issue(text):
    if not distro.is_arch():
        return pkgmanager.detect_lock_issue(text)
    return bool(_DB_LOCK_RE.search(text))


# Matches both of pacman's per-file mismatch line formats — "backup file:"
# (older pacman versions, and always used for files in a package's backup=()
# array) and plain "warning:" (newer versions, and always used for regular,
# non-backup files):
#   warning: accountsservice: /var/lib/AccountsService/icons (Permissions mismatch)
#   backup file: pacman-mirrorlist: /etc/pacman.d/mirrorlist (Modification time mismatch)
_QKK_WARN_RE = _re.compile(r'^(?:warning|backup file):\s*(.+)$')
# The per-package summary line pacman -Qkk prints after that package's
# warnings, e.g. "accountsservice: 286 total files, 1 altered file". In
# real-world testing this count DOES include backup/config-file mismatches
# (contrary to what an old upstream bug report — FS#57680 — suggested it
# shouldn't), so this alone can't be used to tell "genuinely broken" apart
# from "you edited a config file, which is normal" — see
# _is_config_backup_path() below for that.
_QKK_SUMMARY_RE = _re.compile(r'^([^\s:]+):\s*\d+\s*total files,\s*(\d+)\s*altered files?\s*$')


def _is_config_backup_path(detail_line):
    """True if a pacman -Qkk detail line ("/etc/foo.conf (Size mismatch)")
    is for a file under /etc/ — by long-standing Arch packaging convention,
    the only place a package's backup=() (config) files ever live. Pacman
    deliberately never overwrites a locally-modified config file on
    reinstall (it writes a .pacnew alongside instead), so these will keep
    showing up as "altered" forever no matter how many times the owning
    package gets reinstalled — that's not corruption, it's the file doing
    exactly what it's supposed to do."""
    return detail_line.startswith("/etc/")


_DETAIL_LINE_RE = _re.compile(r'^(.*) \(([^)]+)\)$')
_DIR_METADATA_ONLY_REASONS = ("Permissions mismatch", "UID mismatch", "GID mismatch")


def _is_unfixable_dir_metadata(detail_line):
    """True if this is a Permissions/UID/GID mismatch on a directory.
    Confirmed directly against a real upgrade log: pacman prints
    "Verzeichnis-Berechtigungen unterscheiden sich" for a directory during
    a genuine reinstall and leaves it exactly as it was — it never
    chmods/chowns a directory that already exists, whether or not it's
    package-owned. A content-based reason (anything other than pure
    permissions/ownership) is left alone even on a directory, since that
    would mean something more than metadata changed."""
    m = _DETAIL_LINE_RE.match(detail_line)
    if not m:
        return False
    path, reason = m.group(1), m.group(2)
    if reason not in _DIR_METADATA_ONLY_REASONS:
        return False
    try:
        return os.path.isdir(path)
    except OSError:
        return False


def _is_unfixable_by_reinstall(detail_line):
    """Union of every "reinstalling this package will never clear this
    particular warning" case recognized so far."""
    return (_is_config_backup_path(detail_line)
            or _is_unfixable_dir_metadata(detail_line))


def _parse_qkk_details(raw_text):
    """Group pacman -Qkk's per-file warning lines by the package whose
    summary line they precede, keeping only packages pacman itself counted
    as having >0 altered files. Returns {pkg_name: [detail_line, ...]},
    where each detail_line is e.g. "/var/lib/AccountsService/icons
    (Permissions mismatch)" — used to show *why* a package keeps showing
    up (often a cache file a pacman hook regenerates on every install,
    which no amount of reinstalling will ever "fix") instead of just its
    bare name.
    """
    details = {}
    buf = []
    for line in raw_text.splitlines():
        line = line.rstrip()
        m_warn = _QKK_WARN_RE.match(line)
        if m_warn:
            buf.append(m_warn.group(1))
            continue
        m_sum = _QKK_SUMMARY_RE.match(line)
        if m_sum:
            pkg, n_altered = m_sum.group(1), int(m_sum.group(2))
            if n_altered > 0:
                # Keep the package even if buf is empty (e.g. its warning
                # lines used some format this parser doesn't recognize
                # yet) — better an entry with no detail text than silently
                # dropping a package pacman itself flagged as altered.
                prefix = pkg + ":"
                details[pkg] = [
                    (d[len(prefix):].strip() if d.startswith(prefix) else d)
                    for d in buf
                ]
            buf = []
            continue
        if line and not line.startswith(("warning:", "backup file:")):
            buf = []  # unrelated pacman output — don't misattribute stale entries
    return details


def run_terminal_dialog(parent, cmd, title, on_success=None, on_done_extra=None,
                         target_window=None, on_success_with_window=None):
    """
    Show a modal, PTY-backed terminal window that executes *cmd*.
    on_success() is invoked on the main thread when the command ends with 0.
    If on_success_with_window is given, it's called instead as
    on_success_with_window(dialog) — same trigger, but also handed this
    dialog's own window so the caller can keep reusing it (e.g. via
    target_window on a follow-up call) instead of opening a new one.

    If the command fails with a recognizable GPG/signature error, offers an
    inline one-click fix (import the missing key, or refresh the keyring)
    followed by an automatic retry of *cmd* in a fresh dialog.

    If target_window is given (an already-presented Adw.Window), its
    content is replaced with this freshly-built terminal UI and the
    command runs there instead of opening a brand new window on top of
    it — used so a short multi-step flow (scan → pick packages → repair)
    stays in one window instead of stacking a new one at every step.
    """
    # A real top-level Adw.Window instead of Adw.Dialog: Adw.Dialog is
    # deliberately a fixed-size "sheet" centered over the parent — it can't
    # be dragged or resized by the user. Adw.Window is a genuine window, so
    # the window manager gives it normal move/resize behaviour (drag the
    # header bar to move, drag an edge/corner to resize).
    if target_window is not None:
        dialog = target_window
        dialog.set_title(title)
    else:
        dialog = Adw.Window()
        dialog.set_title(title)
        dialog.set_default_size(780, 780)
        dialog.set_resizable(True)
        dialog.set_transient_for(parent)
        dialog.set_modal(True)

    tv = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)

    spinner = Gtk.Spinner(width_request=16, height_request=16)
    spinner.start()
    heading = Gtk.Label(label=title, css_classes=["heading"])
    title_box = _hbox(8)
    for part in (spinner, heading):
        title_box.append(part)
    hdr.set_title_widget(title_box)

    close_btn = _btn(tr("Close"), "suggested-action")
    close_btn.set_sensitive(False)
    hdr.pack_end(close_btn)

    cancel_btn = _btn(tr("Cancel"), "destructive-action", "flat")
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    gpg_banner = Adw.Banner()
    gpg_banner.set_revealed(False)
    tv.add_top_bar(gpg_banner)

    outer = _pad(_vbox(8), start=12, end=12, top=8, bottom=12)

    # Real progress bars, parsed live from pacman's own "[####----] NN%"
    # lines. Two stacked bars:
    #   - progress_bar:         the package currently being downloaded or
    #                            installed right now (e.g. "firefox 68%").
    #   - overall_progress_bar: how far through the whole transaction we
    #                           are, from pacman's own "(i/n) installing
    #                           pkg [...] NN%" counter — only shown once a
    #                           line with that counter has actually been
    #                           seen, since plain download lines don't
    #                           carry an (i/n) prefix and some tools never
    #                           emit one at all.
    # Both hidden until their first matching line arrives; hidden again
    # once the command ends.
    progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    progress_box.set_visible(False)
    progress_label = Gtk.Label(label="")
    progress_label.add_css_class("caption")
    progress_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    progress_label.set_xalign(0.0)
    progress_box.append(progress_label)
    progress_bar = Gtk.ProgressBar()
    progress_bar.set_hexpand(True)
    progress_bar.set_show_text(True)
    progress_box.append(progress_bar)

    overall_progress_label = Gtk.Label(label="")
    overall_progress_label.add_css_class("caption")
    overall_progress_label.add_css_class("dim-label")
    overall_progress_label.set_xalign(0.0)
    overall_progress_label.set_margin_top(4)
    overall_progress_label.set_visible(False)
    progress_box.append(overall_progress_label)
    overall_progress_bar = Gtk.ProgressBar()
    overall_progress_bar.set_hexpand(True)
    overall_progress_bar.set_show_text(True)
    overall_progress_bar.set_visible(False)
    progress_box.append(overall_progress_bar)
    outer.append(progress_box)

    # Overall-progress state for the whole transaction, not just whichever
    # single package Bar 1 currently shows. A pacman transaction is really
    # two back-to-back phases across the same package list — download,
    # then install — and only the install phase carries pacman's own
    # authoritative "(i/n)" counter; download lines never have one. Track
    # each phase's own fraction (download via counting distinct package
    # items against the transaction total, install via the (i/n) counter)
    # and blend them 50/50 into one continuous bar, rather than switching
    # trackers mid-transaction and having it visibly jump backwards from
    # "100%" (end of downloads) to e.g. "33%" (install just starting).
    _dl_total = [0]
    _dl_seen = set()

    scroll = _scrolled(_AUTO, _AUTO, "card")
    scroll.set_hexpand(True)
    scroll.set_vexpand(True)

    term_buf = Gtk.TextBuffer()
    term_view = Gtk.TextView(buffer=term_buf, editable=False,
                             cursor_visible=False, monospace=True,
                             wrap_mode=Gtk.WrapMode.CHAR)
    term_view.add_css_class("terminal-view")

    # Dunkles Systemtheme: .terminal-view-dark schaltet in styles.py auf
    # dunklen Hintergrund/hellen Text um, das helle Theme bleibt
    # unverändert. Läuft synchron mit dem System, falls das Theme
    # gewechselt wird, während der Dialog offen ist.
    _style_mgr = Adw.StyleManager.get_default()
    def _sync_terminal_theme(*_a):
        if _style_mgr.get_dark():
            term_view.add_css_class("terminal-view-dark")
        else:
            term_view.remove_css_class("terminal-view-dark")
    _sync_terminal_theme()
    _style_mgr.connect("notify::dark", _sync_terminal_theme)
    outer.append(scroll)
    scroll.set_child(term_view)

    # Eingabezeile (Passwort bzw. stdin des laufenden Befehls)
    input_frame = Gtk.Frame(margin_top=2, css_classes=["card"])
    input_box = _pad(_hbox(8), start=10, end=10, top=8, bottom=8)

    # This row is mainly for the rare leftover interactive prompt pkexec
    # itself doesn't cover (e.g. a [Y/n] confirmation some tool still
    # asks for) — but in practice it does still sometimes receive an
    # actual password: an AUR helper (yay/paru) calls its own internal
    # `sudo` for its privileged steps, which is a separate mechanism from
    # pkexec that Pachul can't fold into the native Polkit dialog (see
    # PKEXEC_MIGRATION.md). So this stays masked by default, with a
    # reveal toggle to check what was typed — same idea as the eye icon
    # on the native Polkit dialog itself.
    pw_icon = themed_image("utilities-terminal-symbolic", 18)
    input_box.append(pw_icon)
    pw_icon.add_css_class("dim-label")

    pw_entry = Gtk.Entry(hexpand=True, visibility=False,
                         input_purpose=Gtk.InputPurpose.PASSWORD)
    pw_entry.set_placeholder_text(tr("Input for the running command (rarely needed) — press Enter to send"))
    pw_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
    pw_entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, True)
    pw_entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, tr("Show input"))

    def _toggle_pw_visibility(entry, icon_pos):
        if icon_pos != Gtk.EntryIconPosition.SECONDARY:
            return
        now_visible = not entry.get_visibility()
        entry.set_visibility(now_visible)
        entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY,
            "view-conceal-symbolic" if now_visible else "view-reveal-symbolic")
        entry.set_icon_tooltip_text(
            Gtk.EntryIconPosition.SECONDARY,
            tr("Hide input") if now_visible else tr("Show input"))

    pw_entry.connect("icon-press", _toggle_pw_visibility)
    input_box.append(pw_entry)

    send_btn = Gtk.Button(label=tr("Send"))
    send_btn.add_css_class("suggested-action")
    input_box.append(send_btn)

    outer.append(input_frame)
    input_frame.set_child(input_box)
    tv.set_content(outer)
    dialog.set_content(tv)

    # Now that this is a real window, guard against the window manager's
    # own close controls (taskbar "×", Alt+F4, etc.) closing it while a
    # command is still running — that would kill pacman/apt/dnf mid-
    # transaction without the clean SIGTERM the Cancel button sends.
    # Our own Close button already stays disabled until the command
    # finishes; this just closes the same gap for WM-level close requests.
    def _on_close_request(*_):
        if _running[0]:
            cancel_btn.grab_focus()
            return True   # block the close
        return False      # allow it
    dialog.connect("close-request", _on_close_request)

    dialog.present()
    # tippen kann, ohne vorher hineinklicken zu müssen. Direkt nach
    # present() ist das Fenster meist noch nicht vollständig gemappt,
    # daher via idle_add einmalig verzögert ausführen.
    #
    # WICHTIG: grab_focus() liefert selbst True/False zurück (Erfolg/
    # Misserfolg). Würde man es direkt als idle-Callback übergeben,
    # interpretiert GLib ein „True“ als „bitte erneut aufrufen“ — die
    # Funktion würde dann in einer Endlosschleife bei jedem Idle-Zyklus
    # erneut den Fokus grabben, auch während der Nutzer tippt (Symptom:
    # nur das zuletzt getippte Zeichen bleibt markiert, der Rest geht
    # verloren). Daher hier explizit in einen Wrapper packen, der immer
    # False zurückgibt, damit der Callback nur genau einmal läuft.
    def _focus_pw_once():
        pw_entry.grab_focus()
        return False
    GLib.idle_add(_focus_pw_once)

    # ── Internal state ────────────────────────────────────────────────────────
    _running = [True]
    _proc = [None]
    _master_fd = [None]

    _ANSI = _re.compile("|".join((
        # OSC-Sequenzen (Fenstertitel, Hyperlinks und neuere systemd/pam_systemd-
        # Sitzungsmarker wie "OSC 3008", die sudo/pkexec ausgeben können). Muss
        # vor dem allgemeinen ESC-Fallback stehen, sonst wird nur "ESC ]" entfernt
        # und die Nutzlast bliebe als Klartext sichtbar.
        r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)',
        r'\x1b\[[0-9;?]*[ -/]*[@-~]',    # CSI-Sequenzen (Farben, Cursor)
        r'\x1b[()][AB012]',              # Zeichensatz-Umschaltung
        r'\x1b[^[]',                     # sonstige zweibyte-ESC-Folgen
        r'\x08',                         # Backspace
    )))

    # Matches pacman's own progress-bar lines, e.g.:
    #   firefox-125.0-1-x86_64.pkg.tar.zst  65.2 MiB  15.3 MiB/s 00:03 [###----] 68%
    #   (3/12) installing firefox                        [######------------] 71%
    # The leading "(i/n)" counter is optional. It's NOT a reliable signal
    # for "this is an install line, not a download line" on its own —
    # some pacman versions/configs print one on download lines too — so
    # phase classification below uses the .pkg.tar.* filename instead
    # (see _PKG_FILE_RE), and this is only used for its actual i/n values
    # once a line has already been classified as an install line.
    # The bracket contents are left generic ([^\]]*) since the fill character
    # varies with pacman's Color/ILoveCandy settings.
    _PROGRESS_RE = _re.compile(
        r'^\s*(?:\((\d+)/(\d+)\)\s*)?(\S.*?)\s+\[[^\]]*\]\s*(\d{1,3})%\s*$'
    )
    # A package archive filename — always ends this way regardless of
    # pacman's UI locale, unlike matching on translated verbs like
    # "installing"/"installiere". Used to tell download lines apart from
    # install lines no matter what (i/n)-prefix behavior this pacman
    # version/config happens to have.
    _PKG_FILE_RE = _re.compile(r'\.pkg\.tar\.\w+$')
    # pacman's transaction-summary line, printed once right before any
    # progress bars start, e.g. "Pakete (26) audit-4.2.1-1  cups-pdf-3.0.3-1"
    # (German) or "Packages (26) audit-4.2.1-1 cups-pdf-3.0.3-1" (English) —
    # gives an upfront estimate of the transaction total. Treated as a
    # floor rather than gospel below, since e.g. newly-pulled-in optional
    # dependencies can grow the real count past this initial number.
    _TOTAL_PKGS_RE = _re.compile(r'^(?:Pakete|Packages)\s*\((\d+)\)')

    def _update_progress(line):
        m_total = _TOTAL_PKGS_RE.match(line.strip())
        if m_total:
            _dl_total[0] = int(m_total.group(1))
            return
        m = _PROGRESS_RE.match(line)
        if not m:
            return
        idx_str, total_str, desc, pct_str = m.groups()
        desc, pct = desc.strip(), max(0, min(100, int(pct_str)))

        # Bar 1: the package currently being downloaded/installed.
        progress_bar.set_fraction(pct / 100.0)
        progress_bar.set_text(f"{pct}%")
        item = desc.split()[0] if desc.split() else desc
        progress_label.set_label(item)
        progress_label.set_tooltip_text(desc)
        if not progress_box.get_visible():
            progress_box.set_visible(True)

        # Bar 2: overall progress across the whole transaction, blended
        # 50/50 from the two phases so it's one continuous 0-100% climb
        # instead of two separate 0-100% cycles (download, then install)
        # that would otherwise make it visibly jump backwards partway
        # through. A line only counts as "install phase" if its item
        # ISN'T a .pkg.tar.* filename — download lines get counted by
        # distinct package items seen instead, even if this particular
        # pacman happens to also print an (i/n) prefix on them.
        is_install_line = (idx_str is not None) and not _PKG_FILE_RE.search(item)
        if is_install_line:
            idx, total = int(idx_str), int(total_str)
            install_frac = (idx - 1 + pct / 100.0) / total if total else 0.0
            overall_frac = 0.5 + 0.5 * install_frac
            label_txt = f"{idx}/{total}"
        else:
            if pct >= 100:
                _dl_seen.add(item)
            completed = len(_dl_seen)
            # Never let the denominator be smaller than what we've
            # actually observed — if more packages turn up than the
            # transaction-summary line originally promised (e.g. newly
            # pulled-in optional deps), grow the total to match instead
            # of letting the fraction hit 100% before everything's
            # actually done.
            pending = 0 if item in _dl_seen else 1
            total = max(_dl_total[0], completed + pending)
            _dl_total[0] = total
            dl_num = completed if item in _dl_seen else completed + pct / 100.0
            dl_frac = dl_num / total if total else 0.0
            overall_frac = 0.5 * dl_frac
            idx = min(completed + pending, total)
            label_txt = f"{idx}/{total}"
        if total > 0:
            overall_progress_bar.set_fraction(max(0.0, min(1.0, overall_frac)))
            overall_progress_bar.set_text(label_txt)
            overall_progress_label.set_label(tr("Overall progress"))
            if not overall_progress_bar.get_visible():
                overall_progress_bar.set_visible(True)
                overall_progress_label.set_visible(True)

    def append_output(raw_text):
        # Normalize real newlines first, but keep lone '\r' (carriage return
        # without '\n') intact — pacman uses it to redraw the current line
        # in place (progress bars). Naively turning every '\r' into '\n'
        # would spam the buffer with hundreds of near-duplicate lines.
        text = raw_text.replace('\r\n', '\n')
        segments = text.split('\r')
        changed = False
        for i, seg in enumerate(segments):
            if i > 0:
                # A lone '\r' occurred here: erase back to the start of the
                # buffer's current (last, still being written) line so the
                # next segment overwrites it — same as a real terminal.
                end_iter = term_buf.get_end_iter()
                success, line_start = term_buf.get_iter_at_line(end_iter.get_line())
                if success:
                    term_buf.delete(line_start, end_iter)
                    changed = True
            cleaned = _ANSI.sub('', seg)
            if not cleaned:
                continue
            end_iter = term_buf.get_end_iter()
            term_buf.insert(end_iter, cleaned)
            changed = True
            if '\n' in cleaned:
                # This insert just terminated a line (e.g. the final 100%
                # frame of a download, followed by '\n') — check it too,
                # not just the new (currently empty) trailing line.
                n = term_buf.get_end_iter().get_line()
                if n > 0:
                    success1, completed_start = term_buf.get_iter_at_line(n - 1)
                    success2, completed_end = term_buf.get_iter_at_line(n)
                    if success1 and success2:
                        _update_progress(term_buf.get_text(completed_start, completed_end, False))
            # Whatever now sits on the buffer's last (possibly still-open)
            # line is the freshest redraw of it — read it from the buffer
            # itself (not just this chunk) so a chunk boundary landing
            # mid-line never breaks the match.
            last_line_num = term_buf.get_end_iter().get_line()
            success_last, last_start = term_buf.get_iter_at_line(last_line_num)
            if success_last:
                last_line = term_buf.get_text(last_start, term_buf.get_end_iter(), False)
                _update_progress(last_line)
        if not changed:
            return False
        term_view.scroll_mark_onscreen(term_buf.get_insert())
        vadj = scroll.get_vadjustment()
        GLib.idle_add(lambda: vadj.set_value(vadj.get_upper()))
        return False

    def send_input(*_):
        typed = pw_entry.get_text()
        pw_entry.set_text("")
        fd = _master_fd[0]
        if fd is None:
            return
        try:
            os.write(fd, f"{typed}\n".encode())
        except OSError:
            return
        append_output(tr("(input sent)\n"))

    for emitter, signal_name in ((pw_entry, "activate"), (send_btn, "clicked")):
        emitter.connect(signal_name, send_input)

    def close_window(*_):
        close_btn.grab_focus()
        dialog.close()
    close_btn.connect("clicked", close_window)

    def do_cancel(*_):
        child = _proc[0]
        if child is not None:
            try:
                os.killpg(os.getpgid(child.pid), signal.SIGTERM)
            except Exception:
                try:
                    child.terminate()
                except Exception:
                    pass
        cancel_btn.set_sensitive(False)
        append_output(tr("\n— Cancelled —\n"))
        cancel_btn.grab_focus()
    cancel_btn.connect("clicked", do_cancel)

    def on_done(code):
        _running[0] = False
        progress_box.set_visible(False)
        spinner.stop()
        close_btn.set_sensitive(True)
        cancel_btn.set_visible(False)
        close_btn.grab_focus()
        overall_progress_bar.set_visible(False)
        overall_progress_label.set_visible(False)
        # fwupdmgr's own exit-code convention (documented in its man page):
        # 0 = did something successfully, 1 = genuine failure, 2 = ran fine
        # but had nothing to do (e.g. "get-updates"/"update" with no
        # pending firmware). That "2" is not an error — without this, every
        # firmware check/update with nothing pending shows as failed here
        # even though it completed exactly as expected.
        if code == 2 and "fwupdmgr" in cmd:
            code = 0
        sep = "\n" + "─" * 56 + "\n"
        if code == 0:
            append_output(sep + tr("✓  Completed successfully\n"))
        else:
            append_output(sep + tr("✗  Failed  (exit code {code})\n").format(code=code))
        pw_entry.set_sensitive(False)
        send_btn.set_sensitive(False)
        if code != 0:
            full_text = term_buf.get_text(term_buf.get_start_iter(), term_buf.get_end_iter(), False)
            _hint = _failure_hint(full_text)
            if _hint:
                append_output(_hint)
            gpg_issue = _detect_gpg_issue(full_text)
            if gpg_issue is not None:
                key_id = gpg_issue

                def _do_gpg_fix(*_):
                    gpg_banner.set_revealed(False)
                    if distro.is_arch():
                        if key_id:
                            fix = "pkexec /usr/bin/bash -c " + shlex.quote(
                                f"pacman-key --recv-keys {key_id} && "
                                f"pacman-key --lsign-key {key_id}")
                        else:
                            fix = "pkexec /usr/bin/pacman -Sy --needed --noconfirm archlinux-keyring"
                    else:
                        fix = pkgmanager.gpg_fix_cmd(key_id or None)
                    if not fix:
                        return
                    dialog.close()
                    # If both the fix and the original (failed) command are
                    # our own pkexec calls, merge them into one
                    # authentication for the retry — otherwise (e.g. cmd
                    # goes through an AUR helper's own internal sudo)
                    # chain them as before; that helper case already needs
                    # its own separate prompt regardless.
                    retry_cmd = (pkgmanager.combine_pkexec(fix, cmd)
                                 if fix.startswith("pkexec ") and cmd.startswith("pkexec ")
                                 else f"{fix} && {cmd}")
                    run_terminal_dialog(parent, retry_cmd, title,
                                        on_success=on_success, on_done_extra=on_done_extra)

                if key_id:
                    gpg_banner.set_title(tr("Unknown GPG key {id} detected").format(id=key_id))
                    gpg_banner.set_button_label(tr("Import & Retry"))
                else:
                    gpg_banner.set_title(tr("Signature check failed — the keyring may be outdated"))
                    gpg_banner.set_button_label(tr("Update Keyring & Retry"))
                gpg_banner.connect("button-clicked", _do_gpg_fix)
                gpg_banner.set_revealed(True)
            elif _detect_lock_issue(full_text):
                def _do_lock_fix(*_):
                    gpg_banner.set_revealed(False)
                    if distro.is_arch():
                        # Safety check baked into the fix itself: only remove
                        # db.lck if something is actually still holding it —
                        # otherwise we'd risk corrupting a genuinely in-progress
                        # operation. `fuser` checks the *file itself*, so it also
                        # catches the most common real-world cause of this
                        # repeating right after every single transaction:
                        # PackageKit's packagekitd (used by KDE Discover / some
                        # Plasma widgets) waking up and briefly re-locking the
                        # same pacman db right after pacman finishes. A plain
                        # `pgrep pacman` would miss that entirely, since the
                        # process holding the lock isn't named "pacman" at all.
                        # Falls back to a wider process-name check if `fuser`
                        # (psmisc) isn't installed.
                        #
                        # IMPORTANT: build the inner script as one plain string,
                        # then quote it EXACTLY ONCE with shlex.quote() for
                        # embedding into the outer command. Manually wrapping it
                        # in '...' *and* separately shlex.quote()-ing the message
                        # inside (as an earlier version of this code did) nests
                        # two independently-generated single-quoted spans — since
                        # shells can't nest ' inside ', that closes the script
                        # early and leaves an unterminated `if` behind, causing
                        # exactly the "unexpected end of file" error seen before.
                        lock_msg = tr("Something is still holding the database lock — not removing it.")
                        inner_script = (
                            "if command -v fuser >/dev/null 2>&1; then "
                            "  fuser -s /var/lib/pacman/db.lck 2>/dev/null; held=$?; "
                            "else "
                            "  (pgrep -x pacman || pgrep -x pacman-key || pgrep -x packagekitd "
                            "   || pgrep -x pamac-daemon) >/dev/null; held=$?; "
                            "fi; "
                            f"if [ \"$held\" = 0 ]; then echo {shlex.quote(lock_msg)} >&2; exit 1; "
                            "else rm -f /var/lib/pacman/db.lck; fi"
                        )
                        fix = "pkexec /usr/bin/bash -c " + shlex.quote(inner_script)
                    else:
                        fix = pkgmanager.lock_fix_cmd()
                    if not fix:
                        return
                    dialog.close()
                    retry_cmd = (pkgmanager.combine_pkexec(fix, cmd)
                                 if fix.startswith("pkexec ") and cmd.startswith("pkexec ")
                                 else f"{fix} && {cmd}")
                    run_terminal_dialog(parent, retry_cmd, title,
                                        on_success=on_success, on_done_extra=on_done_extra)

                lock_title = tr("Pacman database is locked (stale db.lck)") if distro.is_arch() \
                    else tr("Package manager is locked (stale lock file)")
                gpg_banner.set_title(lock_title)
                gpg_banner.set_button_label(tr("Remove Lock & Retry"))
                gpg_banner.connect("button-clicked", _do_lock_fix)
                gpg_banner.set_revealed(True)
        if code == 0 and on_success:
            on_success()
        if code == 0 and on_success_with_window:
            on_success_with_window(dialog)
        if on_done_extra:
            on_done_extra(code)
        return False

    # ── PTY-Arbeitsthread ─────────────────────────────────────────────────────
    def worker():
        _master_fd[0], slave_fd = pty.openpty()
        master_fd = _master_fd[0]

        try:
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ,
                        struct.pack('HHHH', 40, 120, 0, 0))
        except Exception:
            pass

        plain_title = title.replace("'", "")
        shell_script = "; ".join((
            f"printf '\\033[1m>>> {plain_title}\\033[0m\\n'",
            "echo",
            f"{cmd}",
            "_ec=$?",
            "exit $_ec",
        ))

        child_env = dict(os.environ, TERM="xterm-256color")
        # SUDO_ASKPASS spielt seit pkexec (Polkit über D-Bus statt Askpass-
        # Helfer) keine Rolle mehr; wird vorsichtshalber entfernt, falls
        # irgendwo doch noch über einfaches sudo gestartet wird.
        child_env.pop('SUDO_ASKPASS', None)

        try:
            import subprocess
            proc = subprocess.Popen(
                ["sh", "-c", shell_script],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                close_fds=True, preexec_fn=os.setsid, env=child_env,
            )
            _proc[0] = proc
            os.close(slave_fd)

            leftover = b""
            while True:
                try:
                    ready = select.select([master_fd], [], [], 0.05)[0]
                except (ValueError, OSError):
                    break

                if ready:
                    try:
                        data = os.read(master_fd, 8192)
                    except OSError:
                        break
                    if not data:
                        break
                    shown, leftover = _decode_pty_bytes(leftover + data)
                    GLib.idle_add(append_output, shown)
                elif proc.poll() is not None:
                    # Prozess ist fertig: noch im Puffer liegende Ausgabe holen.
                    try:
                        while select.select([master_fd], [], [], 0.05)[0]:
                            data = os.read(master_fd, 8192)
                            if not data:
                                break
                            GLib.idle_add(append_output,
                                          data.decode('utf-8', errors='replace'))
                    except OSError:
                        pass
                    break

            proc.wait()
            code = proc.returncode

        except Exception as exc:
            GLib.idle_add(append_output,
                          tr("\nInternal error: {err}\n").format(err=exc))
            code = 1

        finally:
            _close_quietly(master_fd)
            _master_fd[0] = None

        GLib.idle_add(on_done, code)

    threading.Thread(target=worker, daemon=True, name="pachul-terminal").start()


# ─── Sync databases dialog ─────────────────────────────────────────────────────

def show_sync_db_dialog(parent, on_confirm):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Sync Databases"))
    dialog.set_content_width(460)
    dialog.set_content_height(280)

    tv, hdr = _toolbar_with_header()
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("Refresh Package Lists"))
    info_group.set_description(tr(
        "Downloads the latest package lists from your enabled repositories "
        "(pacman -Sy), so Pachul knows about new versions and new packages. "
        "This only refreshes metadata — nothing on your system is "
        "installed, removed, or upgraded."
    ))
    outer.append(info_group)

    sync_btn = Gtk.Button(label=tr("Sync Databases"))
    sync_btn.add_css_class("suggested-action")
    sync_btn.set_halign(Gtk.Align.CENTER)

    def _do_sync(*_):
        dialog.close()
        on_confirm()

    sync_btn.connect("clicked", _do_sync)
    outer.append(sync_btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Shared info box ──────────────────────────────────────────────────────────

def make_info_box(info_id, heading, paragraphs, dismissible=False):
    """Card with an info icon, a bold heading and wrapped paragraphs — used
    to explain a tool before the user acts. All texts go through tr().

    dismissible=True adds a close button; the choice is remembered in the
    settings under "hide_info_<info_id>" and the box is then not built at
    all (returns None, so callers must check). Margins are left to the
    caller, since every dialog lays out its content differently."""
    key = "hide_info_" + info_id
    if dismissible and get_setting(key):
        return None

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.add_css_class("card")

    icon = themed_image("dialog-information-symbolic", 20)
    icon.set_valign(Gtk.Align.START)
    icon.set_margin_top(14); icon.set_margin_start(14)
    box.append(icon)

    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    col.set_hexpand(True)
    col.set_margin_top(12);  col.set_margin_bottom(12)
    col.set_margin_start(0); col.set_margin_end(0 if dismissible else 14)

    head = Gtk.Label(label=tr(heading))
    head.set_wrap(True); head.set_xalign(0); head.set_hexpand(True)
    head.add_css_class("heading")
    col.append(head)
    for text in paragraphs:
        lbl = Gtk.Label(label=tr(text))
        lbl.set_wrap(True); lbl.set_xalign(0); lbl.set_hexpand(True)
        col.append(lbl)
    box.append(col)

    if dismissible:
        close = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close.add_css_class("flat"); close.add_css_class("circular")
        close.set_valign(Gtk.Align.START)
        close.set_margin_top(8); close.set_margin_end(8)
        close.set_tooltip_text(tr("Hide this hint"))

        def _hide(*_):
            save_settings({key: True})
            box.set_visible(False)
        close.connect("clicked", _hide)
        box.append(close)
    return box


# ─── Repository manager dialog ────────────────────────────────────────────────

def show_repo_manager(parent, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Manage Repositories"))
    # Was 640×500 — far too cramped for comfortably editing pacman.conf.
    # Now a real, resizable Adw.Window instead of Adw.Dialog, so the user
    # can also just drag it bigger themselves; this default just starts
    # it out roomy.
    dialog.set_default_size(920, 800)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()

    # NOTE: this used to shell out to "sudo -S ${VISUAL:-${EDITOR:-nano}}
    # /etc/pacman.conf" inside the terminal-dialog's plain-text output panel.
    # That panel is a simple scrolling log view, not a real terminal
    # emulator (it deliberately strips ANSI/escape codes so pacman's output
    # stays readable) — so a full-screen curses editor like nano has nothing
    # to draw with: every screen-clear/cursor-move/redraw sequence it sends
    # gets filtered out, and after the password is sent nothing visible ever
    # happens again, even though nano is technically still running and
    # waiting for input.
    #
    # Fix: edit the file right here as a normal (editable) GTK TextView, then
    # write it out via the same safe pattern already used elsewhere in the
    # app for pacman.conf changes (window.py's hold/unhold flow) — dump the
    # new content to a user-owned temp file, then apply it with a single
    # non-interactive `pkexec install ...` call, authenticated through the
    # desktop's native Polkit dialog rather than anything typed into the
    # log-style terminal panel.
    save_btn = _btn(tr("Save"), "suggested-action")
    close_btn = _btn(tr("Close"), "flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    for header_btn in (save_btn, close_btn):
        hdr.pack_end(header_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(12), start=16, end=16, top=12, bottom=16)

    # Info box: explains what a repository is and what happens when repos
    # are missing or additional ones are added.
    info_box = make_info_box(
        "repo_manager",
        "What is a repository?",
        ["A repository (repo) is a package archive on a server from which pacman fetches programs and updates.",
         "If a repository is missing: its packages can no longer be found or installed, and already installed packages from it receive no further updates (for example, without «multilib» there is no 32-bit software such as Steam or Wine; without «core» or «extra» the system itself can no longer be updated properly).",
         "If additional repositories are added: their packages appear in the search and can be installed. However, this can cause dependency and version conflicts, for example when a repository offers different versions of system libraries, which can block updates or break the system. Only add third-party repositories from sources you trust."])
    outer.append(info_box)

    repos_group = Adw.PreferencesGroup(
        title=tr("Active Repositories"),
        description=tr("Repositories currently enabled in /etc/pacman.conf"))

    listing, listing_code = run_command(
        "pacman -Sl 2>/dev/null | awk '{print $1}' | sort -u")
    if listing and listing_code == 0:
        repos = [name for name in listing.splitlines() if name.strip()]
    else:
        repos = ["core", "extra", "multilib"]

    for repo in repos:
        repo_row = Adw.ActionRow(title=repo)
        folder_icon = themed_image("folder-symbolic", 18)
        folder_icon.add_css_class("dim-label")
        repo_row.add_prefix(folder_icon)
        pkg_count, _ = run_command(f"pacman -Sl {repo} 2>/dev/null | wc -l")
        if pkg_count and pkg_count.strip().isdigit():
            repo_row.add_suffix(Gtk.Label(
                label=tr("{n} pkgs").format(n=pkg_count.strip()),
                css_classes=["caption", "dim-label"]))
        repos_group.add(repo_row)
    outer.append(repos_group)

    conf_group = Adw.PreferencesGroup()
    conf_group.set_title(tr("pacman.conf"))
    conf_group.set_description(tr("Edit directly below, then click Save. Make sure the syntax stays valid — pacman will refuse to run on a broken config."))
    # Let this group (and the editor inside it) actually grow into the extra
    # room from the larger dialog above, instead of staying pinned to a
    # small fixed height regardless of how big the dialog is.
    conf_group.set_vexpand(True)

    scroll = _scrolled(_AUTO, _AUTO, "card")
    scroll.set_min_content_height(420)
    scroll.set_vexpand(True)

    conf_out, conf_read_code = run_command("cat /etc/pacman.conf 2>/dev/null")
    readable = bool(conf_out) and conf_read_code == 0
    buf = Gtk.TextBuffer()
    buf.set_text(conf_out if readable else tr("# /etc/pacman.conf not found or not readable"))
    conf_view = Gtk.TextView(buffer=buf, editable=readable, monospace=True,
                             wrap_mode=Gtk.WrapMode.NONE)
    conf_view.add_css_class("terminal-view")
    scroll.set_child(conf_view)
    outer.append(conf_group)
    conf_group.add(scroll)

    save_btn.set_sensitive(readable)

    def _do_save(*_):
        start, end = buf.get_bounds()
        new_content = buf.get_text(start, end, True)
        fd, tmp_path = tempfile.mkstemp(prefix="pachul-pacman-conf-", suffix=".conf")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(new_content)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            return
        dialog.close()
        run_terminal_fn(
            f"pkexec /usr/bin/install -m644 {shlex.quote(tmp_path)} /etc/pacman.conf",
            tr("Save pacman.conf"))

    save_btn.connect("clicked", _do_save)

    tv.set_content(_scroll_page(outer))
    dialog.set_content(tv)
    dialog.present()


def show_repo_manager_native(parent, run_terminal_fn):
    """Repo Manager for apt/dnf/zypper: list configured repos with an
    enable/disable switch each, plus an "Add {PPA/COPR/OBS}" row. Unlike
    the Arch version above (a single pacman.conf text editor), each
    family here spreads repo config across several files or its own
    dedicated subcommand — so rather than a raw text editor, this reads
    the current state via pkgmanager.list_repos() and drives every change
    through pkgmanager's own command builders."""
    dialog = Adw.Window()
    dialog.set_title(tr("Manage Repositories"))
    dialog.set_default_size(640, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = _btn(tr("Close"), "flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    kind_label = pkgmanager.third_party_kind_label()

    repos_group = Adw.PreferencesGroup()
    repos_group.set_title(tr("Configured Repositories"))
    repos = pkgmanager.list_repos()
    if not repos:
        repos_group.set_description(tr(
            "No repositories could be read — they may be defined somewhere Pachul "
            "doesn't know to look yet, or this list needs root to read on your system."))
    for repo in repos:
        row = Adw.SwitchRow()
        row.set_title(GLib.markup_escape_text(repo["label"]))
        row.set_subtitle(GLib.markup_escape_text(repo.get("file", repo["id"])))
        row.set_active(repo["enabled"])

        def _on_toggle(r, _pspec, repo=repo):
            new_state = r.get_active()
            if new_state == repo["enabled"]:
                return
            cmd = pkgmanager.set_repo_enabled_cmd(repo, new_state)
            if not cmd:
                r.handler_block_by_func(_on_toggle)
                r.set_active(repo["enabled"])
                r.handler_unblock_by_func(_on_toggle)
                return
            verb = tr("Enable") if new_state else tr("Disable")
            run_terminal_fn(cmd, f"{verb} {repo['label']}")
            repo["enabled"] = new_state

        row.connect("notify::active", _on_toggle)
        repos_group.add(row)
    outer.append(repos_group)

    # Third-party repos (PPA / COPR / OBS)
    third_group = Adw.PreferencesGroup()
    third_group.set_title(tr("Add / Remove {kind}").format(kind=kind_label))
    hints = {
        "PPA": tr('Format: user/ppa-name (as shown on the PPA\'s Launchpad page)'),
        "COPR": tr('Format: user/project (as shown on the project\'s Copr page)'),
        "OBS Repository": tr('Format: project/repo (as shown on the project\'s OBS page)'),
    }
    third_group.set_description(hints.get(kind_label, ""))

    if not pkgmanager.third_party_helper_available():
        install_row = Adw.ActionRow()
        install_row.set_title(tr("Required tool isn't installed yet"))
        install_btn = Gtk.Button(label=tr("Install"))
        install_btn.add_css_class("suggested-action")
        install_btn.set_valign(Gtk.Align.CENTER)

        def _do_install_helper(*_):
            cmd = pkgmanager.third_party_helper_install_cmd()
            if cmd:
                dialog.close()
                run_terminal_fn(cmd, tr("Install repository tools"))
        install_btn.connect("clicked", _do_install_helper)
        install_row.add_suffix(install_btn)
        third_group.add(install_row)
    else:
        entry_row = Adw.ActionRow()
        entry_row.set_title(kind_label)
        id_entry = Gtk.Entry()
        id_entry.set_placeholder_text(
            "user/ppa-name" if kind_label == "PPA" else
            "user/project" if kind_label == "COPR" else "project/repo")
        id_entry.set_hexpand(True)
        id_entry.set_valign(Gtk.Align.CENTER)
        id_entry.set_width_chars(24)
        entry_row.add_suffix(id_entry)
        third_group.add(entry_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.set_margin_top(8)
        remove_btn = Gtk.Button(label=tr("Remove"))
        remove_btn.add_css_class("destructive-action")
        add_btn = Gtk.Button(label=tr("Add"))
        add_btn.add_css_class("suggested-action")

        def _do_add(*_):
            identifier = id_entry.get_text().strip()
            cmd = pkgmanager.add_third_party_cmd(identifier)
            if not cmd:
                return
            dialog.close()
            run_terminal_fn(cmd, tr("Add {kind} {id}").format(kind=kind_label, id=identifier))

        def _do_remove(*_):
            identifier = id_entry.get_text().strip()
            cmd = pkgmanager.remove_third_party_cmd(identifier)
            if not cmd:
                return
            dialog.close()
            run_terminal_fn(cmd, tr("Remove {kind} {id}").format(kind=kind_label, id=identifier))

        add_btn.connect("clicked", _do_add)
        remove_btn.connect("clicked", _do_remove)
        btn_row.append(remove_btn)
        btn_row.append(add_btn)

        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrapper.append(btn_row)
        third_group.add(wrapper)

    outer.append(third_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Repair System (apt/dpkg), Debian-only ────────────────────────────────────

def show_apt_repair_dialog(parent, run_terminal_fn):
    """A menu of the standard apt/dpkg troubleshooting commands (update+
    upgrade+autoremove, --fix-broken, dpkg --configure -a, --fix-missing,
    autoclean+clean, listing not-fully-installed packages, and a
    last-resort force-remove for a single package), each just a thin
    wrapper that hands the real command to run_terminal_fn — no new
    parsing/backend logic, this dialog only assembles well-known apt/dpkg
    invocations. Debian-family only; not offered on Arch/Fedora/openSUSE,
    which each have their own equivalents already."""
    dialog = Adw.Window()
    dialog.set_title(tr("Repair System"))
    dialog.set_default_size(600, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real apt/dpkg maintenance commands with root privileges (via pkexec) — read what each "
        "one does before running it, especially the last one."))
    warn_banner.set_revealed(True)
    outer.append(warn_banner)

    def _row(title, subtitle, button_label, cmd, suggested=True):
        row = Adw.ActionRow()
        # set_title/set_subtitle parse their text as Pango markup, so a
        # literal "&" in e.g. "Update & Upgrade" would otherwise crash
        # ("Failed to set text ... from markup") — escape both first.
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(GLib.markup_escape_text(subtitle))
        row.set_subtitle_lines(0)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            dialog.close()
            run_terminal_fn(cmd, title)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    steps_group = Adw.PreferencesGroup()
    steps_group.set_title(tr("Standard Maintenance"))

    steps_group.add(_row(
        tr("Update, Upgrade & Autoremove"),
        tr("Refreshes the package index, upgrades everything, then removes packages "
           "no longer needed by anything else."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote(
            "apt-get update -y && apt-get dist-upgrade -y && apt-get autoremove -y"),
    ))
    steps_group.add(_row(
        tr("Fix Broken Dependencies"),
        tr("Runs 'apt --fix-broken install' to resolve broken or half-installed "
           "dependencies."),
        tr("Run"),
        "pkexec /usr/bin/apt-get install --fix-broken -y",
    ))
    steps_group.add(_row(
        tr("Reconfigure All Packages"),
        tr("Runs 'dpkg --configure -a' to finish any package configuration that was "
           "interrupted."),
        tr("Run"),
        "pkexec /usr/bin/dpkg --configure -a",
    ))
    steps_group.add(_row(
        tr("Fix Missing/Corrupt Package Files"),
        tr("Refreshes the package index, then retries installing anything with "
           "missing or corrupt downloaded files."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote("apt-get update -y && apt-get install --fix-missing -y"),
    ))
    steps_group.add(_row(
        tr("Clean Package Cache"),
        tr("Removes outdated .deb files from the local cache, then clears it "
           "completely."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote("apt-get autoclean -y && apt-get clean -y"),
    ))
    outer.append(steps_group)

    diag_group = Adw.PreferencesGroup()
    diag_group.set_title(tr("Diagnose"))
    diag_group.add(_row(
        tr("Show Broken/Incomplete Packages"),
        tr("Read-only: lists packages dpkg considers not fully installed (e.g. "
           "flagged 'reinstall required')."),
        tr("Show"),
        "dpkg -l | grep -E '^..r' || echo " + shlex.quote(tr("No broken/incomplete packages found.")),
        suggested=False,
    ))
    outer.append(diag_group)

    danger_group = Adw.PreferencesGroup()
    danger_group.set_title(tr("Last Resort"))
    danger_row = Adw.ActionRow()
    danger_row.set_title(tr("Force-Remove Broken Package"))
    danger_row.set_subtitle(tr(
        "Last resort for a single package dpkg refuses to touch normally — "
        "removes it while ignoring the 'reinstall required' flag. Only use this "
        "if the steps above didn't help, and only on the one package causing "
        "the problem."))
    danger_row.set_subtitle_lines(0)

    pkg_entry = Gtk.Entry()
    pkg_entry.set_placeholder_text(tr("Package name"))
    pkg_entry.set_valign(Gtk.Align.CENTER)
    pkg_entry.set_width_chars(18)
    danger_row.add_suffix(pkg_entry)
    force_btn = Gtk.Button(label=tr("Remove"))
    force_btn.add_css_class("destructive-action")
    force_btn.set_valign(Gtk.Align.CENTER)
    force_btn.set_sensitive(False)
    pkg_entry.connect("notify::text",
                       lambda e, *_: force_btn.set_sensitive(bool(e.get_text().strip())))

    def _do_force_remove(*_):
        pkg_name = pkg_entry.get_text().strip()
        if not pkg_name:
            return
        dialog.close()
        run_terminal_fn(
            f"pkexec /usr/bin/dpkg --remove --force-remove-reinstreq {shlex.quote(pkg_name)}",
            tr("Force-Remove Broken Package") + f" ({pkg_name})")
    force_btn.connect("clicked", _do_force_remove)
    danger_row.add_suffix(force_btn)
    danger_group.add(danger_row)
    outer.append(danger_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Repair System (dnf/rpm), Fedora-only ─────────────────────────────────────

def show_dnf_repair_dialog(parent, run_terminal_fn):
    """dnf/rpm equivalent of show_apt_repair_dialog() above — same idea,
    same layout, just the Fedora-side commands: dnf upgrade+autoremove,
    distro-sync (dnf's closest match to apt's --fix-broken — resolves
    installed packages that ended up at inconsistent versions after an
    interrupted/partial upgrade), rpm --rebuilddb, dnf clean all, a
    read-only dnf check for dependency/duplicate problems, and rpm -e
    --nodeps as the last-resort single-package force-remove."""
    dialog = Adw.Window()
    dialog.set_title(tr("Repair System"))
    dialog.set_default_size(600, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real dnf/rpm maintenance commands with root privileges (via pkexec) — read what each "
        "one does before running it, especially the last one."))
    warn_banner.set_revealed(True)
    outer.append(warn_banner)

    def _row(title, subtitle, button_label, cmd, suggested=True):
        row = Adw.ActionRow()
        # set_title/set_subtitle parse their text as Pango markup, so a
        # literal "&" in e.g. "Update & Upgrade" would otherwise crash
        # ("Failed to set text ... from markup") — escape both first.
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(GLib.markup_escape_text(subtitle))
        row.set_subtitle_lines(0)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            dialog.close()
            run_terminal_fn(cmd, title)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    steps_group = Adw.PreferencesGroup()
    steps_group.set_title(tr("Standard Maintenance"))

    steps_group.add(_row(
        tr("Update, Upgrade & Autoremove"),
        tr("Refreshes repo metadata, upgrades everything, then removes packages "
           "no longer needed by anything else."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote("dnf upgrade --refresh -y && dnf autoremove -y"),
    ))
    steps_group.add(_row(
        tr("Fix Inconsistent Package Versions"),
        tr("Runs 'dnf distro-sync' to bring installed packages back in line "
           "with what the repos currently offer, after an interrupted or "
           "partial upgrade left some at mismatched versions."),
        tr("Run"),
        "pkexec /usr/bin/dnf distro-sync -y",
    ))
    steps_group.add(_row(
        tr("Rebuild RPM Database"),
        tr("Runs 'rpm --rebuilddb' to rebuild a corrupted local RPM database."),
        tr("Run"),
        "pkexec /usr/bin/rpm --rebuilddb",
    ))
    steps_group.add(_row(
        tr("Clean Package Cache"),
        tr("Runs 'dnf clean all' to clear cached package files and metadata."),
        tr("Run"),
        "pkexec /usr/bin/dnf clean all",
    ))
    outer.append(steps_group)

    diag_group = Adw.PreferencesGroup()
    diag_group.set_title(tr("Diagnose"))
    diag_group.add(_row(
        tr("Show Broken/Unsatisfied Packages"),
        tr("Read-only: runs 'dnf check' to list dependency, duplicate, or "
           "obsoleted-package problems in what's currently installed."),
        tr("Show"),
        "dnf check || echo " + shlex.quote(tr("No broken/incomplete packages found.")),
        suggested=False,
    ))
    outer.append(diag_group)

    danger_group = Adw.PreferencesGroup()
    danger_group.set_title(tr("Last Resort"))
    danger_row = Adw.ActionRow()
    danger_row.set_title(tr("Force-Remove Broken Package"))
    danger_row.set_subtitle(tr(
        "Last resort for a single package rpm refuses to touch normally — "
        "removes it while ignoring dependency checks entirely. Only use this "
        "if the steps above didn't help, and only on the one package causing "
        "the problem."))
    danger_row.set_subtitle_lines(0)

    pkg_entry = Gtk.Entry()
    pkg_entry.set_placeholder_text(tr("Package name"))
    pkg_entry.set_valign(Gtk.Align.CENTER)
    pkg_entry.set_width_chars(18)
    danger_row.add_suffix(pkg_entry)
    force_btn = Gtk.Button(label=tr("Remove"))
    force_btn.add_css_class("destructive-action")
    force_btn.set_valign(Gtk.Align.CENTER)
    force_btn.set_sensitive(False)
    pkg_entry.connect("notify::text",
                       lambda e, *_: force_btn.set_sensitive(bool(e.get_text().strip())))

    def _do_force_remove(*_):
        pkg_name = pkg_entry.get_text().strip()
        if not pkg_name:
            return
        dialog.close()
        run_terminal_fn(
            f"pkexec /usr/bin/rpm -e --nodeps {shlex.quote(pkg_name)}",
            tr("Force-Remove Broken Package") + f" ({pkg_name})")
    force_btn.connect("clicked", _do_force_remove)
    danger_row.add_suffix(force_btn)
    danger_group.add(danger_row)
    outer.append(danger_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Repair System (zypper/rpm), openSUSE-only ────────────────────────────────

def show_zypper_repair_dialog(parent, run_terminal_fn):
    """zypper/rpm equivalent of show_apt_repair_dialog()/show_dnf_repair_dialog()
    above — same layout, openSUSE-side commands: zypper refresh+update,
    zypper verify (openSUSE's own dependency-repair solver run — the
    closest match to apt's --fix-broken / dnf's distro-sync), rpm
    --rebuilddb (shared with the Fedora dialog, since it's plain rpm),
    zypper clean --all, a read-only verify --dry-run for diagnosis, and
    rpm -e --nodeps as the last-resort single-package force-remove."""
    dialog = Adw.Window()
    dialog.set_title(tr("Repair System"))
    dialog.set_default_size(600, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real zypper/rpm maintenance commands with root privileges (via pkexec) — read what "
        "each one does before running it, especially the last one."))
    warn_banner.set_revealed(True)
    outer.append(warn_banner)

    def _row(title, subtitle, button_label, cmd, suggested=True):
        row = Adw.ActionRow()
        # set_title/set_subtitle parse their text as Pango markup, so a
        # literal "&" in e.g. "Update & Upgrade" would otherwise crash
        # ("Failed to set text ... from markup") — escape both first.
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(GLib.markup_escape_text(subtitle))
        row.set_subtitle_lines(0)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            dialog.close()
            run_terminal_fn(cmd, title)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    steps_group = Adw.PreferencesGroup()
    steps_group.set_title(tr("Standard Maintenance"))

    steps_group.add(_row(
        tr("Update & Upgrade"),
        tr("Refreshes repo metadata, then installs all available updates."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote(
            "zypper --non-interactive refresh && zypper --non-interactive update"),
    ))
    steps_group.add(_row(
        tr("Fix Broken Dependencies"),
        tr("Runs 'zypper verify' — openSUSE's own solver run that finds and "
           "proposes fixes for broken or unsatisfied package dependencies."),
        tr("Run"),
        "pkexec /usr/bin/zypper --non-interactive verify",
    ))
    steps_group.add(_row(
        tr("Rebuild RPM Database"),
        tr("Runs 'rpm --rebuilddb' to rebuild a corrupted local RPM database."),
        tr("Run"),
        "pkexec /usr/bin/rpm --rebuilddb",
    ))
    steps_group.add(_row(
        tr("Clean Package Cache"),
        tr("Runs 'zypper clean --all' to clear cached package files and metadata."),
        tr("Run"),
        "pkexec /usr/bin/zypper clean --all",
    ))
    outer.append(steps_group)

    diag_group = Adw.PreferencesGroup()
    diag_group.set_title(tr("Diagnose"))
    diag_group.add(_row(
        tr("Show Broken/Unsatisfied Packages"),
        tr("Read-only: runs 'zypper verify --dry-run' to list what it would "
           "change without actually changing anything."),
        tr("Show"),
        "zypper --non-interactive verify --dry-run || echo "
        + shlex.quote(tr("No broken/incomplete packages found.")),
        suggested=False,
    ))
    outer.append(diag_group)

    danger_group = Adw.PreferencesGroup()
    danger_group.set_title(tr("Last Resort"))
    danger_row = Adw.ActionRow()
    danger_row.set_title(tr("Force-Remove Broken Package"))
    danger_row.set_subtitle(tr(
        "Last resort for a single package rpm refuses to touch normally — "
        "removes it while ignoring dependency checks entirely. Only use this "
        "if the steps above didn't help, and only on the one package causing "
        "the problem."))
    danger_row.set_subtitle_lines(0)

    pkg_entry = Gtk.Entry()
    pkg_entry.set_placeholder_text(tr("Package name"))
    pkg_entry.set_valign(Gtk.Align.CENTER)
    pkg_entry.set_width_chars(18)
    danger_row.add_suffix(pkg_entry)
    force_btn = Gtk.Button(label=tr("Remove"))
    force_btn.add_css_class("destructive-action")
    force_btn.set_valign(Gtk.Align.CENTER)
    force_btn.set_sensitive(False)
    pkg_entry.connect("notify::text",
                       lambda e, *_: force_btn.set_sensitive(bool(e.get_text().strip())))

    def _do_force_remove(*_):
        pkg_name = pkg_entry.get_text().strip()
        if not pkg_name:
            return
        dialog.close()
        run_terminal_fn(
            f"pkexec /usr/bin/rpm -e --nodeps {shlex.quote(pkg_name)}",
            tr("Force-Remove Broken Package") + f" ({pkg_name})")
    force_btn.connect("clicked", _do_force_remove)
    danger_row.add_suffix(force_btn)
    danger_group.add(danger_row)
    outer.append(danger_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Repair System (pacman), Arch-only ─────────────────────────────────────────

def show_pacman_repair_dialog(parent, run_terminal_fn, aur_helper=None):
    """pacman equivalent of the apt/dnf/zypper repair dialogs above. Arch
    already surfaces its two most common failure modes proactively —
    stale GPG keys and a stuck db.lck — as inline fix banners elsewhere
    (see dialogs.py's GPG/lock-detection code near the top of this file),
    so this dialog covers what those banners don't: a full force-refresh,
    a read-only file-integrity check, a deeper keyring reinit for when the
    lighter banner fix isn't enough, and rpm/dpkg-force-remove's pacman
    equivalent."""
    dialog = Adw.Window()
    dialog.set_title(tr("Repair System"))
    dialog.set_default_size(600, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    def _row(title, subtitle, button_label, cmd, suggested=True, on_success=None,
             on_success_with_window=None):
        row = Adw.ActionRow()
        # set_title parses its text as Pango markup, so a literal "&" in
        # e.g. "Update & Upgrade" would otherwise crash ("Failed to set
        # text ... from markup") — escape it first. set_tooltip_text()
        # below takes plain text, no markup/escaping involved.
        row.set_title(GLib.markup_escape_text(title))
        row.set_tooltip_text(subtitle)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            # Keep the repair dialog open behind the terminal window
            # instead of closing it, so you can run several steps in a
            # row without reopening the menu each time. Explicitly pass
            # parent=dialog (instead of letting it default to the main
            # window) so the terminal window stacks on top of this
            # still-open dialog rather than the main window behind it —
            # see the parent= comment on pachulWindow._run_terminal for
            # why getting this wrong causes a GTK snapshot warning.
            run_terminal_fn(cmd, title, on_success=on_success,
                             on_success_with_window=on_success_with_window,
                             parent=dialog)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    steps_group = Adw.PreferencesGroup()
    steps_group.set_title(tr("Standard Maintenance"))

    steps_group.add(_row(
        tr("Force-Refresh & Full Upgrade"),
        tr("Runs 'pacman -Syyu' with root privileges (via pkexec). Normally pacman only re-downloads "
           "a repo's database if its timestamp changed; this ignores that "
           "and forces a fresh download of ALL repo databases before "
           "upgrading every installed package. Use this when a mirror "
           "served you a stale or corrupted database — typical symptoms "
           "are pacman reporting packages as up to date that you know "
           "aren't, or checksum/signature errors that don't go away with a "
           "normal update. Takes longer than a regular sync since nothing "
           "is skipped, but makes no changes beyond what -Syu itself would "
           "install anyway."),
        tr("Run"),
        "pkexec /usr/bin/pacman -Syyu --noconfirm",
    ))
    steps_group.add(_row(
        tr("Check Package Database Consistency"),
        tr("Runs 'pacman -Dk', a fast, read-only check. It only looks at "
           "pacman's own local database — the dependency graph and package "
           "metadata under /var/lib/pacman — for internal problems like "
           "orphaned or duplicate entries. It does NOT look at the actual "
           "installed files on disk (for that, see 'Search for Packages "
           "With Missing/Modified Files' below); the two checks are "
           "independent and catch different kinds of corruption."),
        tr("Run"),
        "pacman -Dk",
    ))
    steps_group.add(_row(
        tr("Reinitialize Keyring"),
        tr("Runs 'pacman-key --init' followed by 'pacman-key --populate "
           "archlinux' with root privileges (via pkexec). This resets and rebuilds pacman's GPG "
           "trust database from scratch and repopulates it with the "
           "official Arch Linux master keys. Use it when package signature "
           "verification keeps failing even after the lighter, automatic "
           "keyring-fix banner shown elsewhere in the app — that banner "
           "only imports one specific missing key, while this rebuilds the "
           "whole keyring. It talks to a keyserver over the network, so it "
           "can take a little while and will fail if you're offline."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote("pacman-key --init && pacman-key --populate archlinux"),
    ))
    outer.append(steps_group)

    diag_group = Adw.PreferencesGroup()
    diag_group.set_title(tr("Diagnose"))

    _QKK_RAW_FILE = "/tmp/pachul-qkk-raw.txt"

    def _load_qkk_details():
        try:
            with open(_QKK_RAW_FILE) as f:
                raw = f.read()
        except OSError:
            return {}
        return _parse_qkk_details(raw)

    def _offer_repair_now(dialog):
        # Fires once "Search for Packages With Missing/Modified Files" finishes
        # (that command always exits 0 — grep simply finding nothing isn't
        # a failure). The package list comes ONLY from the strict Python
        # parser below now, not from a bash grep/cut over the raw pacman
        # output — that grep matched any line containing the substring
        # "altered file" (including odd pacman lines that don't actually
        # name a package), which could plant garbage entries like a
        # literal "altered files" row. _parse_qkk_details only accepts
        # lines matching pacman's exact "pkg: N total files, M altered
        # files" summary format, so there's no such ambiguity here.
        details = _load_qkk_details()
        names = sorted(details.keys())

        # Split off packages whose ONLY complaint is a locally-modified
        # /etc/ config file or a directory-permission diff — reinstalling
        # can never clear either (pacman won't overwrite a modified
        # config file, and never chmods/chowns a pre-existing directory),
        # so listing them as "repair me" is misleading. Keep them out of
        # the list entirely rather than just unchecking them.
        real_names, config_only = [], []
        for name in names:
            reasons = details.get(name)
            if reasons and all(_is_unfixable_by_reinstall(r) for r in reasons):
                config_only.append(name)
            else:
                real_names.append(name)

        if real_names:
            # target_window=dialog: turn the just-finished search window
            # straight into the picker instead of opening a new one.
            _show_repair_confirm(real_names, details, len(config_only), target_window=dialog)
        elif config_only:
            parent._toast(tr(
                "All {n} package(s) only have config/permission "
                "differences a reinstall can't fix.").format(n=len(config_only)))

    def _show_repair_confirm(names, details=None, config_only_count=0, target_window=None):
        details = details or {}
        if target_window is not None:
            # Reuse the same window the repair terminal was just showing
            # instead of stacking a new one — this is what makes the
            # scan -> pick -> repair -> (leftovers) -> pick -> repair
            # loop stay in a single window end to end.
            confirm = target_window
            confirm.set_title(tr("Repair Broken Packages"))
        else:
            confirm = Adw.Window()
            confirm.set_title(tr("Repair Broken Packages"))
            # Match the main window's current height instead of a fixed guess,
            # so this doesn't look cramped on a maximized/tall window or
            # oversized on a small one. Falls back to the old fixed height if
            # the main window hasn't been allocated a size yet for some reason.
            main_win_height = parent.get_height() or 420
            confirm.set_default_size(760, max(360, main_win_height))
            confirm.set_resizable(True)
            confirm.set_transient_for(parent)
            confirm.set_modal(True)

        ctv  = Adw.ToolbarView()
        chdr = Adw.HeaderBar()
        chdr.set_show_end_title_buttons(False)
        not_now_btn = Gtk.Button(label=tr("Not Now"))
        not_now_btn.add_css_class("flat")
        not_now_btn.connect("clicked", lambda *_: confirm.close())
        chdr.pack_start(not_now_btn)

        select_all_btn = Gtk.Button(label=tr("Select All"))
        select_all_btn.add_css_class("flat")
        select_none_btn = Gtk.Button(label=tr("Select None"))
        select_none_btn.add_css_class("flat")
        chdr.pack_end(select_none_btn)
        chdr.pack_end(select_all_btn)
        ctv.add_top_bar(chdr)

        couter = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        couter.set_margin_top(16);   couter.set_margin_bottom(24)
        couter.set_margin_start(16); couter.set_margin_end(16)

        info_group = Adw.PreferencesGroup()
        info_group.set_title(
            tr("{n} package(s) with missing or altered files found").format(n=len(names)))
        desc = tr(
            "Choose which ones to reinstall from your configured "
            "repositories to restore the original files:")
        if config_only_count:
            desc += " " + tr(
                "({n} more package(s) with only config/permission "
                "differences are hidden — reinstalling never touches "
                "those.)").format(n=config_only_count)
        info_group.set_description(desc)
        couter.append(info_group)

        # Two side-by-side boxed lists instead of one long column — with
        # potentially dozens of broken packages, a single column on a
        # window this wide (760px, sized to match the main window's
        # height) leaves half the width empty and forces a lot of
        # scrolling. Split the (already-sorted, as pacman -Qkk reports
        # them) name list roughly in half: first half left, second half
        # right.
        cols_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        cols_box.set_homogeneous(True)
        left_group = Adw.PreferencesGroup()
        right_group = Adw.PreferencesGroup()
        cols_box.append(left_group)
        cols_box.append(right_group)
        couter.append(cols_box)

        checks = []  # [(Gtk.CheckButton, package_name), ...]

        def _update_repair_btn(*_):
            n = sum(1 for cb, _n in checks if cb.get_active())
            repair_btn.set_sensitive(n > 0)
            repair_btn.set_label(tr("Repair {n} package(s)").format(n=n))

        mid = (len(names) + 1) // 2
        for i, name in enumerate(names):
            row = Adw.ActionRow(title=GLib.markup_escape_text(name))
            reasons = details.get(name)
            # A package can have both a genuine issue AND an unrelated,
            # expected config-file diff at the same time — only surface
            # the genuine one(s) here, since that's what "Repair" can
            # actually address.
            real_reasons = [r for r in reasons if not _is_unfixable_by_reinstall(r)] if reasons else []
            if real_reasons:
                # e.g. "icon-theme.cache (Modification time mismatch)" — lets
                # the user see at a glance whether this is a file a pacman
                # hook just regenerates every time (safe to leave unchecked)
                # or something that looks like genuine corruption.
                shown = real_reasons[:2]
                subtitle = "; ".join(shown)
                if len(real_reasons) > len(shown):
                    subtitle += " " + tr("(+{n} more)").format(n=len(real_reasons) - len(shown))
                row.set_subtitle(GLib.markup_escape_text(subtitle))
                row.set_subtitle_lines(0)
            cb = Gtk.CheckButton()
            cb.set_valign(Gtk.Align.CENTER)
            cb.set_active(True)
            cb.connect("toggled", _update_repair_btn)
            row.add_prefix(cb)
            row.set_activatable_widget(cb)
            checks.append((cb, name))
            (left_group if i < mid else right_group).add(row)

        def _select_all(*_):
            for cb, _n in checks:
                cb.set_active(True)

        def _select_none(*_):
            for cb, _n in checks:
                cb.set_active(False)

        select_all_btn.connect("clicked", _select_all)
        select_none_btn.connect("clicked", _select_none)

        repair_btn = Gtk.Button()
        repair_btn.add_css_class("suggested-action")
        repair_btn.set_halign(Gtk.Align.CENTER)
        _update_repair_btn()

        def _do_repair(*_):
            selected = [name for cb, name in checks if cb.get_active()]
            if not selected:
                return
            # Whatever's left unchecked right now is what the reopened
            # window should show afterwards — a plain "still on the list"
            # follow-up, no re-scan involved.
            remaining = [name for cb, name in checks if not cb.get_active()]
            quoted = " ".join(shlex.quote(n) for n in selected)
            # Same AUR-helper routing as repair_cmd above — otherwise any
            # AUR-installed package in the selection just fails silently.
            if aur_helper:
                cmd = aur_helper_install_cmd(aur_helper, quoted)
            else:
                cmd = f"pkexec /usr/bin/pacman -S --noconfirm {quoted}"

            def _reopen_remaining():
                if remaining:
                    _show_repair_confirm(remaining, details, target_window=confirm)

            # target_window=confirm: run the repair right here instead of
            # popping open yet another window on top of this one.
            run_terminal_fn(cmd, tr("Repair Broken Packages"),
                             on_success=_reopen_remaining if remaining else None,
                             target_window=confirm)
        repair_btn.connect("clicked", _do_repair)
        couter.append(repair_btn)

        cscroll = Gtk.ScrolledWindow()
        cscroll.set_vexpand(True)
        cscroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        cscroll.set_child(couter)
        ctv.set_content(cscroll)
        confirm.set_content(ctv)
        confirm.present()

    diag_group.add(_row(
        tr("Search for Packages With Missing/Modified Files"),
        tr("Runs 'pacman -Qkk' with root privileges (via pkexec) — read-only, "
           "no changes are made. Unlike 'Check Package Database Consistency' "
           "above, this actually hashes every file every installed package "
           "owns and compares it against what the package claims it should "
           "be, so it also catches files that were deleted, changed, or "
           "have the wrong permissions/ownership. On a full system this can "
           "take a couple of minutes. It's normal to see a few 'altered' "
           "hits for config files under /etc you've deliberately edited "
           "yourself — those aren't corruption, and reinstalling can't fix "
           "them since pacman never overwrites a modified config file. If "
           "any packages come back altered, you'll be asked right away "
           "which ones to repair by reinstalling."),
        tr("Run"),
        # stdbuf forces line-buffered output on BOTH streams even though
        # they're going to a file, not a terminal. Without it, libc
        # switches stdout to large block-buffering once it detects a
        # non-tty target while stderr stays unbuffered — the per-package
        # "N total files, M altered files" summary (stdout) and the
        # per-file "warning:" lines (stderr) then land in the file wildly
        # out of order and sometimes mid-line-spliced together, which is
        # exactly the kind of corruption that made this parser miss (or
        # misattribute) a chunk of the packages it should have caught.
        #
        # Root matters just as much: plenty of package-owned files
        # (/etc/shadow, SSL private keys, sudoers, cups/pcp/webmin config,
        # nwfilter templates, ...) are only readable by root. Run as a
        # normal user, pacman can't even open them to hash them and
        # reports "failed to calculate SHA256 checksum" — which looks
        # exactly like corruption in this list but really just means "I
        # wasn't allowed to check." No amount of reinstalling ever clears
        # that specific warning; only checking as root does.
        #
        # No throwaway pre-auth call needed here (that used to warm sudo's
        # credential cache before the real, redirected call, so sudo's own
        # "[sudo] password for ...:" prompt on stderr wouldn't get silently
        # swallowed by ">file 2>&1"). pkexec's authentication happens in a
        # separate native Polkit window, entirely outside this command's
        # own stdout/stderr, so nothing here can accidentally capture it —
        # one plain call is enough. `env LC_ALL=C` (rather than a bare
        # `LC_ALL=C` prefix, which sudo/pkexec don't reliably pass through
        # to the target process) keeps pacman's output in English so the
        # parser below matches reliably regardless of the system locale.
        "pkexec /usr/bin/env LC_ALL=C pacman -Qk > " + _QKK_RAW_FILE + " 2>&1; "
        "OUT=$(grep -v '0 altered files' " + _QKK_RAW_FILE + "); "
        "if [ -n \"$OUT\" ]; then printf '%s\\n' \"$OUT\"; "
        "else echo " + shlex.quote(tr("No broken/incomplete packages found.")) + "; fi",
        on_success_with_window=_offer_repair_now,
    ))
    outer.append(diag_group)

    danger_group = Adw.PreferencesGroup()
    danger_group.set_title(tr("Last Resort"))
    danger_row = Adw.ActionRow()
    danger_row.set_title(tr("Force-Remove Broken Package"))
    danger_row.set_tooltip_text(tr(
        "Runs 'pacman -Rdd' with root privileges (via pkexec) on the single package name you type "
        "in. -Rdd removes it while skipping BOTH dependency checks that "
        "pacman normally does: it won't stop you even if other installed "
        "packages still depend on this one, and it won't try to remove "
        "anything that depends on it either — it only ever touches the one "
        "package you named. This is a genuine last resort for a package "
        "pacman refuses to touch any other way (e.g. it's stuck "
        "half-installed and blocking every other operation); it can leave "
        "dependents broken, so only use it on the one package actually "
        "causing the problem, after the steps above didn't help, and "
        "reinstall it (or whatever needed it) afterwards if you can."))

    pkg_entry = Gtk.Entry()
    pkg_entry.set_placeholder_text(tr("Package name"))
    pkg_entry.set_valign(Gtk.Align.CENTER)
    pkg_entry.set_width_chars(18)
    danger_row.add_suffix(pkg_entry)
    force_btn = Gtk.Button(label=tr("Remove"))
    force_btn.add_css_class("destructive-action")
    force_btn.set_valign(Gtk.Align.CENTER)
    force_btn.set_sensitive(False)
    pkg_entry.connect("notify::text",
                       lambda e, *_: force_btn.set_sensitive(bool(e.get_text().strip())))

    def _do_force_remove(*_):
        pkg_name = pkg_entry.get_text().strip()
        if not pkg_name:
            return
        run_terminal_fn(
            f"pkexec /usr/bin/pacman -Rdd --noconfirm {shlex.quote(pkg_name)}",
            tr("Force-Remove Broken Package") + f" ({pkg_name})",
            parent=dialog)
    force_btn.connect("clicked", _do_force_remove)
    danger_row.add_suffix(force_btn)
    danger_group.add(danger_row)
    outer.append(danger_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Certificate Checker (Modul 2 from the user's manjaro-wartung.sh) ─────────

def show_cert_checker_dialog(parent, run_terminal_fn):
    """Cross-distro TLS/CA certificate health check, adapted from the
    "MODUL 2: TLS/SSL-Zertifikate" section of the user's own
    manjaro-wartung.sh. Three independent pieces, all runnable on any of
    the 4 supported distro families:
      1. Reinstall the CA certificate bundle + rebuild the system trust
         store (distro-specific package/command, see
         pkgmanager.ca_certificates_refresh_cmd()).
      2. Check the TLS certificate expiry of any domains the user types
         in (the original script hard-coded manjaro.org and friends —
         that's obviously not useful for anyone else, so this asks
         instead of assuming).
      3. Read-only scan of /etc/ssl/certs for already-expired local
         certificates.
    Pure openssl/find/date shell logic — nothing here touches the package
    manager except the reinstall step, so unlike the repair dialogs this
    one dialog covers all distros rather than needing four separate ones."""
    dialog = Adw.Window()
    dialog.set_title(tr("Certificate Checker"))
    dialog.set_default_size(600, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    # ── CA certificate bundle ──
    ca_group = Adw.PreferencesGroup()
    ca_group.set_title(tr("CA Certificate Bundle"))
    ca_cmd = pkgmanager.ca_certificates_refresh_cmd()
    ca_row = Adw.ActionRow()
    ca_row.set_title(GLib.markup_escape_text(tr("Reinstall CA Certificates & Rebuild Trust Store")))
    ca_row.set_tooltip_text(tr(
        "Reinstalls the ca-certificates package (the bundle of root "
        "certificates your system trusts by default) and regenerates the "
        "system's trust store from it. Use this when HTTPS connections "
        "fail with certificate-verification errors across multiple, "
        "otherwise-unrelated sites at once — that pattern points at a "
        "damaged or outdated local trust store rather than a problem "
        "with any one remote site. Safe to run any time: it only "
        "reinstalls the package and rebuilds the store, it doesn't "
        "remove or add any certificate you didn't already have."))
    if ca_cmd:
        ca_btn = Gtk.Button(label=tr("Run"))
        ca_btn.add_css_class("suggested-action")
        ca_btn.set_valign(Gtk.Align.CENTER)

        def _do_ca_refresh(*_):
            # Stay open — parent=dialog so the terminal stacks correctly
            # on top of it instead of the main window (see the parent=
            # comment on pachulWindow._run_terminal).
            run_terminal_fn(ca_cmd, tr("Reinstall CA Certificates & Rebuild Trust Store"),
                             parent=dialog)
        ca_btn.connect("clicked", _do_ca_refresh)
        ca_row.add_suffix(ca_btn)
    ca_group.add(ca_row)
    outer.append(ca_group)

    # ── Domain expiry check ──
    domain_group = Adw.PreferencesGroup()
    domain_group.set_title(tr("Domain Certificate Expiry"))
    domain_group.set_description(tr(
        "Checks how many days remain before each domain's TLS "
        "certificate expires — nothing is changed, purely informational."))
    domain_row = Adw.ActionRow()
    domain_row.set_title(GLib.markup_escape_text(tr("Domains")))
    domain_row.set_tooltip_text(tr(
        "Opens a real TLS connection to each domain on port 443 and reads "
        "back the certificate it presents, then reports how many days "
        "remain until it expires (or how many days ago it already did). "
        "Comma-separated, e.g. example.com, mail.example.com — each "
        "domain needs to actually be reachable over the network right "
        "now, since this isn't a local file check like the one below, "
        "it's a live connection."))
    domain_entry = Gtk.Entry()
    domain_entry.set_placeholder_text(tr("Domains to check"))
    domain_entry.set_valign(Gtk.Align.CENTER)
    domain_entry.set_width_chars(24)
    domain_row.add_suffix(domain_entry)
    domain_btn = Gtk.Button(label=tr("Check"))
    domain_btn.add_css_class("suggested-action")
    domain_btn.set_valign(Gtk.Align.CENTER)
    domain_btn.set_sensitive(False)
    domain_entry.connect(
        "notify::text",
        lambda e, *_: domain_btn.set_sensitive(bool(e.get_text().strip())))

    def _do_domain_check(*_):
        domains = domain_entry.get_text().strip()
        if not domains:
            return
        script = (
            'IFS="," read -ra DOMS <<< "$DOMAINS"; '
            'for d in "${DOMS[@]}"; do '
            '  d="$(echo "$d" | xargs)"; '
            '  [ -z "$d" ] && continue; '
            '  echo "== $d =="; '
            '  ENDE=$(echo | timeout 5 openssl s_client -connect "$d:443" -servername "$d" 2>/dev/null '
            '    | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2); '
            '  if [ -z "$ENDE" ]; then '
            '    echo "  ' + tr("Could not retrieve certificate (offline or unreachable?)") + '"; '
            '  else '
            '    ENDE_EPOCH=$(date -d "$ENDE" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$ENDE" +%s 2>/dev/null || echo 0); '
            '    JETZT_EPOCH=$(date +%s); '
            '    TAGE=$(( (ENDE_EPOCH - JETZT_EPOCH) / 86400 )); '
            '    if [ "$TAGE" -lt 0 ]; then '
            '      echo "  ' + tr("EXPIRED {days} days ago").replace("{days}", "$(( -TAGE ))") + '"; '
            '    elif [ "$TAGE" -lt 30 ]; then '
            '      echo "  ' + tr("Expires in {days} days (until {date})").replace("{days}", "$TAGE").replace("{date}", "$ENDE") + '"; '
            '    else '
            '      echo "  ' + tr("Valid, {days} days remaining (until {date})").replace("{days}", "$TAGE").replace("{date}", "$ENDE") + '"; '
            '    fi; '
            '  fi; '
            'done'
        )
        cmd = f"DOMAINS={shlex.quote(domains)} bash -c {shlex.quote(script)}"
        run_terminal_fn(cmd, tr("Domain Certificate Expiry"), parent=dialog)
    domain_btn.connect("clicked", _do_domain_check)
    domain_row.add_suffix(domain_btn)
    domain_group.add(domain_row)
    outer.append(domain_group)

    # ── Local certificates ──
    local_group = Adw.PreferencesGroup()
    local_group.set_title(tr("Local Certificates"))
    local_row = Adw.ActionRow()
    local_row.set_title(GLib.markup_escape_text(tr("Show Expired Local Certificates")))
    local_row.set_tooltip_text(tr(
        "Read-only: scans every .pem file under /etc/ssl/certs and checks "
        "its expiry date, without opening any network connection. This "
        "covers only that one system-wide certificate directory — not "
        "your browser's own certificate store, not a login keychain, and "
        "not certificates presented by remote servers (use the Domain "
        "check above for those). An expired entry here doesn't "
        "necessarily break anything today, since most software only "
        "cares about a certificate's validity at the moment it's "
        "actually used, but it's worth knowing about and cleaning up."))
    local_btn = Gtk.Button(label=tr("Show"))
    local_btn.set_valign(Gtk.Align.CENTER)

    def _do_local_check(*_):
        script = (
            'ABGELAUFEN=0; '
            'while IFS= read -r -d "" CERT; do '
            '  if ! openssl x509 -checkend 0 -noout -in "$CERT" 2>/dev/null; then '
            '    echo "' + tr("EXPIRED: {cert}").replace("{cert}", "$CERT") + '"; '
            '    ABGELAUFEN=$((ABGELAUFEN + 1)); '
            '  fi; '
            'done < <(find /etc/ssl/certs/ -name "*.pem" -print0 2>/dev/null); '
            'if [ "$ABGELAUFEN" -eq 0 ]; then echo "' + tr("All local certificates are valid.") + '"; fi'
        )
        run_terminal_fn(f"bash -c {shlex.quote(script)}", tr("Show Expired Local Certificates"),
                         parent=dialog)
    local_btn.connect("clicked", _do_local_check)
    local_row.add_suffix(local_btn)
    local_group.add(local_row)
    outer.append(local_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Broken Symlink Finder (Modul 5b from the user's manjaro-wartung.sh) ──────

def show_broken_symlinks_dialog(parent, run_terminal_fn):
    """Finds and classifies broken symlinks under /usr and /etc, adapted
    from "MODUL 5: Verwaiste Pakete und Symlinks" in the user's own
    manjaro-wartung.sh (the orphaned-package half of that module already
    exists in Pachul as the Orphan Finder — this covers only the
    symlink half, which didn't). Classification:
      SAFE   — /usr/share/licenses/**  (license-file leftovers, never
               functionally significant)
      SAFE   — /usr/share/archiso/**   (Arch/Manjaro-only: archiso build
               templates, not a runtime concern; harmless empty category
               on other distros where /usr/share/archiso won't exist)
      REVIEW — everything else, listed only, never auto-deleted
    'find -xtype l' itself is pure POSIX/GNU find, so this dialog works
    identically on all 4 supported distro families."""
    dialog = Adw.Window()
    dialog.set_title(tr("Broken Symlinks"))
    dialog.set_default_size(600, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("What this does"))
    info_group.set_description(tr(
        "Searches /usr and /etc for symlinks pointing at files that no "
        "longer exist — usually harmless leftovers from removed packages, "
        "but occasionally a sign something didn't uninstall cleanly."))
    outer.append(info_group)

    # Shared bash core: classify every broken symlink into SAFE (license
    # leftovers, archiso templates) or REVIEW (anything else — listed only,
    # never touched). $DO_DELETE switches between a pure scan and actually
    # removing the SAFE-category links.
    _classify_core = (
        'mapfile -t ALLE < <(find /usr /etc -xtype l -print 2>/dev/null); '
        'if [ ${#ALLE[@]} -eq 0 ]; then echo "' + tr("No broken symlinks found.") + '"; exit 0; fi; '
        'LIZENZ=(); ARCHISO=(); PRUEFEN=(); '
        'for L in "${ALLE[@]}"; do '
        '  case "$L" in '
        '    /usr/share/licenses/*) LIZENZ+=("$L") ;; '
        '    /usr/share/archiso/*)  ARCHISO+=("$L") ;; '
        '    *)                     PRUEFEN+=("$L") ;; '
        '  esac; '
        'done; '
        'echo "' + tr("{n} broken symlinks found.").replace("{n}", "${#ALLE[@]}") + '"; echo; '
        'if [ ${#LIZENZ[@]} -gt 0 ]; then '
        '  echo "' + tr("SAFE — license leftovers ({n}):").replace("{n}", "${#LIZENZ[@]}") + '"; '
        '  printf "  %s\\n" "${LIZENZ[@]}"; '
        '  if [ "$DO_DELETE" = "1" ]; then '
        '    for L in "${LIZENZ[@]}"; do rm -f "$L"; done; '
        '    echo "  -> ' + tr("removed") + '"; '
        '  fi; echo; '
        'fi; '
        'if [ ${#ARCHISO[@]} -gt 0 ]; then '
        '  echo "' + tr("SAFE but skipped — archiso build templates ({n}), expected on "
                          "Arch/Manjaro, not deleted:").replace("{n}", "${#ARCHISO[@]}") + '"; '
        '  printf "  %s\\n" "${ARCHISO[@]}"; echo; '
        'fi; '
        'if [ ${#PRUEFEN[@]} -gt 0 ]; then '
        '  echo "' + tr("REVIEW — not auto-deleted ({n}):").replace("{n}", "${#PRUEFEN[@]}") + '"; '
        '  printf "  %s\\n" "${PRUEFEN[@]}"; echo; '
        '  echo "' + tr("For each: 'pacman/dpkg/rpm/zypper -qf <path>' or equivalent tells you "
                          "which package owns it, if any; a reinstall of that package usually "
                          "fixes the link.") + '"; '
        'fi'
    )

    action_group = Adw.PreferencesGroup()
    action_group.set_title(tr("Scan"))

    scan_row = Adw.ActionRow()
    scan_row.set_title(GLib.markup_escape_text(tr("Scan Only")))
    scan_row.set_tooltip_text(tr(
        "Read-only: searches /usr and /etc for symlinks whose target no "
        "longer exists, then sorts every one it finds into one of three "
        "groups for the report — license-file leftovers (safe), "
        "Arch/Manjaro archiso build templates (safe but distro-specific, "
        "expected to exist there), and everything else (needs manual "
        "review). Nothing is ever deleted by this button, and since it "
        "only reads the filesystem, no elevated privileges are needed."))
    scan_btn = Gtk.Button(label=tr("Scan"))
    scan_btn.set_valign(Gtk.Align.CENTER)

    def _do_scan(*_):
        run_terminal_fn(
            f"DO_DELETE=0 bash -c {shlex.quote(_classify_core)}",
            tr("Scan Only"), parent=dialog)
    scan_btn.connect("clicked", _do_scan)
    scan_row.add_suffix(scan_btn)
    action_group.add(scan_row)

    clean_row = Adw.ActionRow()
    clean_row.set_title(GLib.markup_escape_text(tr("Scan & Remove Safe Ones")))
    clean_row.set_tooltip_text(tr(
        "Runs the same scan as above, but this time actually deletes the "
        "links it classified as safe — license-file leftovers under "
        "/usr/share/licenses only. The archiso-template group and "
        "everything in the review group are still just listed, never "
        "touched, no matter how many times you run this. Needs root "
        "privileges (via pkexec) because /usr/share is owned by root, "
        "so the deletion itself requires elevated permissions even "
        "though scanning doesn't."))
    clean_btn2 = Gtk.Button(label=tr("Clean"))
    clean_btn2.add_css_class("suggested-action")
    clean_btn2.set_valign(Gtk.Align.CENTER)

    def _do_clean_symlinks(*_):
        run_terminal_fn(
            f"pkexec /usr/bin/env DO_DELETE=1 bash -c {shlex.quote(_classify_core)}",
            tr("Scan & Remove Safe Ones"), parent=dialog)
    clean_btn2.connect("clicked", _do_clean_symlinks)
    clean_row.add_suffix(clean_btn2)
    action_group.add(clean_row)
    outer.append(action_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Services & Security Check (Modul 7 from the user's manjaro-wartung.sh) ───

def show_services_security_dialog(parent, run_terminal_fn):
    """Adapted from "MODUL 7: Systemdienste und Sicherheit" in the user's
    own manjaro-wartung.sh. Almost entirely distro-agnostic: systemctl,
    ufw, and sshd_config are the same across all 4 supported families —
    only the shadow.service auto-reset (a known-harmless, Manjaro-specific
    quirk) and the UFW *install* command (package name/manager differ)
    need any distro branching, everything else runs identically.
    Live-checks each row's current state when the dialog opens (cheap,
    local-only calls: systemctl is-active/is-failed, `which ufw`, reading
    sshd_config) so only the buttons that make sense for THIS system are
    shown active — e.g. no shadow.service row at all unless it's actually
    failed right now."""
    dialog = Adw.Window()
    dialog.set_title(tr("Services & Security"))
    dialog.set_default_size(600, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    def _row(title, subtitle, button_label, cmd, suggested=False):
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(GLib.markup_escape_text(subtitle))
        row.set_subtitle_lines(0)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            dialog.close()
            run_terminal_fn(cmd, title)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    # ── Failed systemd services (always shown — cheap, informative) ──
    services_group = Adw.PreferencesGroup()
    services_group.set_title(tr("Services"))
    services_group.add(_row(
        tr("Show Failed Services"),
        tr("Read-only: lists any systemd services currently in a failed "
           "state."),
        tr("Show"),
        'systemctl --failed --no-pager 2>/dev/null',
    ))

    # shadow.service is a known-harmless, occasionally-failing service on
    # Manjaro specifically (password/group integrity check tripping after
    # updates) — only show the row if it's actually failed right now, on
    # any distro (the check itself is universal, even if the failure mode
    # is Manjaro-specific in practice).
    shadow_out, _ = run_command("systemctl is-failed shadow.service 2>/dev/null")
    if (shadow_out or "").strip() == "failed":
        services_group.add(_row(
            tr("Reset shadow.service"),
            tr("shadow.service has failed — this is usually a harmless "
               "password/group integrity check tripping after an update. "
               "Resets it without touching anything else."),
            tr("Reset"),
            "systemctl reset-failed shadow.service",
        ))
    outer.append(services_group)

    # ── Critical security services (read-only status, always shown) ──
    sec_group = Adw.PreferencesGroup()
    sec_group.set_title(tr("Security Services"))
    sec_group.add(_row(
        tr("Check firewalld / fail2ban / apparmor"),
        tr("Read-only: reports whether each of these — if installed — is "
           "currently active."),
        tr("Check"),
        'for D in firewalld fail2ban apparmor; do '
        '  if systemctl is-active --quiet "$D" 2>/dev/null; then '
        '    echo "$D: ' + tr("running").replace('"', '') + '"; '
        '  elif systemctl list-unit-files "${D}.service" >/dev/null 2>&1; then '
        '    echo "$D: ' + tr("installed but NOT active").replace('"', '') + '"; '
        '  else '
        '    echo "$D: ' + tr("not installed").replace('"', '') + '"; '
        '  fi; '
        'done',
    ))
    outer.append(sec_group)

    # ── UFW firewall — the one row with real distro branching (only the
    # install command differs; everything else is identical) ──
    ufw_group = Adw.PreferencesGroup()
    ufw_group.set_title(tr("Firewall (UFW)"))
    _, ufw_installed_code = run_command("which ufw 2>/dev/null")
    ufw_installed = (ufw_installed_code == 0)
    ufw_active = False
    if ufw_installed:
        _, active_code = run_command("systemctl is-active --quiet ufw 2>/dev/null")
        ufw_active = (active_code == 0)

    # openSUSE's ufw package doesn't pull in iptables as a dependency
    # (openSUSE bug 964649) — without it every ufw command fails with
    # "ERROR: Couldn't determine iptables version", including on systems
    # where ufw was already installed before this check was added. Make
    # sure it's present before every enable, not just on a fresh install.
    _suse_iptables_guard = (
        "which iptables >/dev/null 2>&1 || "
        "zypper --non-interactive install iptables; "
    ) if pkgmanager.get_family() == "suse" else ""
    _ufw_enable_inner = (
        _suse_iptables_guard +
        "ufw default deny incoming && ufw default allow outgoing && "
        '(systemctl is-active --quiet sshd 2>/dev/null || systemctl is-active --quiet ssh 2>/dev/null) '
        "&& ufw limit ssh; "
        "ufw --force enable && systemctl enable --now ufw && "
        "ufw status verbose"
    )
    ufw_enable_cmd = "pkexec /usr/bin/bash -c " + shlex.quote(_ufw_enable_inner)
    if ufw_active:
        ufw_group.add(_row(
            tr("Show Firewall Rules"),
            tr("UFW is active. Read-only: shows the current rule set."),
            tr("Show"),
            "pkexec /usr/bin/ufw status verbose",
        ))
    elif ufw_installed:
        ufw_group.add(_row(
            tr("Enable Firewall"),
            tr("UFW is installed but not active — your system currently has "
               "no active firewall. Enables it with default rules (deny "
               "incoming, allow outgoing) and rate-limited SSH if sshd is "
               "running."),
            tr("Enable"),
            ufw_enable_cmd,
            suggested=True,
        ))
    else:
        # Raw (un-prefixed) per-family install commands — combined with
        # the raw enable script below into a single pkexec call, rather
        # than chaining "pkexec install ... && pkexec bash -c 'enable...'"
        # (two separate authentications for what's really one operation
        # from the person's point of view).
        ufw_install_by_family = {
            "arch":   "pacman -S --noconfirm ufw",
            "debian": "apt-get install -y ufw",
            "fedora": "dnf install -y ufw",
            # openSUSE's ufw package, unlike the other 3 families, does
            # NOT pull in iptables as a dependency (openSUSE bug 964649).
            # Without it ufw can't determine the iptables version and
            # every ufw command — including "enable" — fails with
            # "ERROR: Couldn't determine iptables version". Installing
            # it alongside ufw here closes that gap.
            "suse":   "zypper --non-interactive install ufw iptables",
        }
        install_raw = ufw_install_by_family.get(pkgmanager.get_family())
        if install_raw:
            ufw_group.add(_row(
                tr("Install & Enable Firewall"),
                tr("UFW isn't installed — your system currently has no "
                   "active firewall. Installs it, then enables it with "
                   "default rules (deny incoming, allow outgoing) and "
                   "rate-limited SSH if sshd is running."),
                tr("Install & Enable"),
                "pkexec /usr/bin/bash -c " + shlex.quote(install_raw + " && " + _ufw_enable_inner),
                suggested=True,
            ))
    outer.append(ufw_group)

    # ── SSH root login (read-only check, always shown if sshd_config exists) ──
    ssh_group = Adw.PreferencesGroup()
    ssh_group.set_title(tr("SSH"))
    ssh_group.add(_row(
        tr("Check SSH Root Login"),
        tr("Read-only: checks /etc/ssh/sshd_config for PermitRootLogin "
           "yes, which lets root log in directly over SSH."),
        tr("Check"),
        '[ -f /etc/ssh/sshd_config ] && '
        '( grep -qE "^PermitRootLogin\\s+yes" /etc/ssh/sshd_config '
        '  && echo "' + tr("SSH root login is ENABLED — consider disabling it "
                             "(PermitRootLogin no).").replace('"', '') + '" '
        '  || echo "' + tr("SSH root login is disabled or not explicitly "
                             "configured.").replace('"', '') + '" ) '
        '|| echo "' + tr("No /etc/ssh/sshd_config found — SSH server doesn't "
                          "seem to be installed.").replace('"', '') + '"',
    ))
    outer.append(ssh_group)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Configuration Backup (Modul 6 from the user's manjaro-wartung.sh) ────────

def show_config_backup_dialog(parent, run_terminal_fn):
    """Adapted from "MODUL 6: Backup wichtiger Konfigurationen" in the
    user's own manjaro-wartung.sh. Unlike the other adapted modules, this
    one genuinely needs distro branching: which config files matter
    (pacman.conf vs sources.list vs dnf.conf vs zypp.conf, …) and how to
    export the installed-package list (pacman -Qqe vs apt-mark showmanual
    vs dnf repoquery vs rpm -qa) differ per family — see
    pkgmanager.config_backup_sources() / installed_package_list_cmd().
    Everything else (tar, keeping only the last 5 backups) is identical
    across all 4 families."""
    dialog = Adw.Window()
    dialog.set_title(tr("Configuration Backup"))
    dialog.set_default_size(600, 500)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("What this does"))
    info_group.set_description(tr(
        "Creates a compressed archive of your system's identity and boot "
        "configuration (fstab, hostname, bootloader, package-manager "
        "config, …) plus a plain-text list of explicitly-installed "
        "packages, so a fresh install can be brought back to a similar "
        "state. Only the last 5 archives are kept; older ones are removed "
        "automatically. No elevated privileges needed — these files are normally "
        "world-readable."))
    outer.append(info_group)

    dest_group = Adw.PreferencesGroup()
    dest_row = Adw.ActionRow()
    dest_row.set_title(tr("Backup Folder"))
    dest_entry = Gtk.Entry()
    dest_entry.set_text(str(Path.home() / "pachul-backup"))
    dest_entry.set_valign(Gtk.Align.CENTER)
    dest_entry.set_width_chars(28)
    dest_row.add_suffix(dest_entry)
    dest_group.add(dest_row)
    outer.append(dest_group)

    sources = pkgmanager.config_backup_sources()
    included_group = Adw.PreferencesGroup()
    included_group.set_title(tr("Included If Present"))
    included_group.set_description(", ".join(sources))
    outer.append(included_group)

    pkg_cmd, pkg_explicit = pkgmanager.installed_package_list_cmd()
    if pkg_cmd:
        pkg_note_group = Adw.PreferencesGroup()
        pkg_note_group.set_description(
            tr("Also saves the list of explicitly-installed packages.") if pkg_explicit
            else tr("Also saves the full list of installed packages (this "
                     "distro has no simple way to tell explicit installs "
                     "from pulled-in dependencies)."))
        outer.append(pkg_note_group)

    backup_btn = Gtk.Button(label=tr("Create Backup"))
    backup_btn.add_css_class("suggested-action")
    backup_btn.set_halign(Gtk.Align.CENTER)

    def _do_backup(*_):
        dest = dest_entry.get_text().strip() or str(Path.home() / "pachul-backup")
        dialog.close()
        quoted_sources = " ".join(shlex.quote(s) for s in sources)
        pkg_line = ""
        if pkg_cmd:
            pkg_line = (
                f'PAKETLISTE="$ZIEL/pakete-$DATUM.txt"; '
                f'{pkg_cmd} > "$PAKETLISTE" 2>/dev/null; '
                f'echo "' + tr("Package list saved ({n} packages): $PAKETLISTE").replace("{n}", '$(wc -l < "$PAKETLISTE" 2>/dev/null || echo ?)') + '"; '
            )
        script = (
            f'ZIEL={shlex.quote(dest)}; '
            'DATUM=$(date +%Y%m%d-%H%M%S); '
            'mkdir -p "$ZIEL"; '
            'ARCHIV="$ZIEL/pachul-config-$DATUM.tar.gz"; '
            f'QUELLEN=({quoted_sources}); '
            'VORHANDEN=(); '
            'for Q in "${QUELLEN[@]}"; do [ -e "$Q" ] && VORHANDEN+=("$Q"); done; '
            'if [ ${#VORHANDEN[@]} -eq 0 ]; then '
            '  echo "' + tr("Nothing to back up — none of the expected config paths exist.") + '"; '
            'else '
            '  tar -czf "$ARCHIV" "${VORHANDEN[@]}" 2>/dev/null || true; '
            '  echo "' + tr("Backup created ({size}): $ARCHIV").replace("{size}", '$(du -sh "$ARCHIV" 2>/dev/null | cut -f1)') + '"; '
            'fi; '
            + pkg_line +
            'ls -t "$ZIEL"/pachul-config-*.tar.gz 2>/dev/null | tail -n +6 | while read -r ALT; do '
            '  rm -f "$ALT"; echo "' + tr("Removed old backup:") + ' $ALT"; '
            'done'
        )
        run_terminal_fn(f"bash -c {shlex.quote(script)}", tr("Configuration Backup"))
    backup_btn.connect("clicked", _do_backup)
    outer.append(backup_btn)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Mirror rater dialog ──────────────────────────────────────────────────────

def _manjaro_branch():
    """Branch from /etc/pacman-mirrors.conf (stable / testing / unstable);
    falls back to stable. Needed because the branch is part of every
    Manjaro mirror URL."""
    try:
        for line in Path("/etc/pacman-mirrors.conf").read_text(errors="replace").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == "Branch" and val.strip() in ("stable", "testing", "unstable"):
                return val.strip()
    except OSError:
        pass
    return "stable"


def _detect_country_code():
    """Best-effort 2-letter country code of this machine, without any
    network access: first from the system time zone (zone.tab maps every
    zone to a country), then from the locale (de_CH.UTF-8 -> CH).
    Returns "" if nothing usable is found."""
    tz = ""
    try:
        tz = Path("/etc/timezone").read_text().strip()
    except OSError:
        pass
    if not tz:
        try:
            link = os.path.realpath("/etc/localtime")
            if "zoneinfo/" in link:
                tz = link.split("zoneinfo/", 1)[1]
        except OSError:
            pass
    if tz:
        for tab in ("/usr/share/zoneinfo/zone.tab", "/usr/share/zoneinfo/zone1970.tab"):
            try:
                for line in Path(tab).read_text(errors="replace").splitlines():
                    if line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 3 and parts[2].strip() == tz:
                        cc = parts[0].split(",")[0].strip().upper()
                        if len(cc) == 2 and cc.isalpha():
                            return cc
            except OSError:
                continue
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        m = _re.match(r"^[a-z]{2,3}_([A-Z]{2})", os.environ.get(var, ""))
        if m:
            return m.group(1)
    return ""


def show_mirror_rater(parent, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Find Fastest Mirrors"))
    dialog.set_default_size(600, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = _btn(tr("Close"), "flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    _, code = run_command("which rate-mirrors 2>/dev/null")
    has_rate_mirrors = (code == 0)

    # Manjaro has its own repositories and mirror network: its mirrorlist
    # must be built with the "manjaro" subcommand, never the Arch one.
    is_manjaro = distro.is_manjaro()
    mirror_cmd = "manjaro" if is_manjaro else "arch"
    manjaro_branch = _manjaro_branch() if is_manjaro else None

    mirror_paragraphs = ["Mirrors are servers that hold copies of the package archives. pacman downloads packages and updates from the servers listed in /etc/pacman.d/mirrorlist, trying them from top to bottom.",
                         "rate-mirrors measures which servers respond fastest from your location and puts them first. This helps with slow downloads, errors such as 404 or timeouts, or after moving to another country. The result is only shown first — your current list is replaced only when you save.",
                         "Tip: keep «Backup current mirrorlist» switched on (only the most recent backup is kept). After saving, sync the databases so pacman uses the new servers («Sync Databases»)."]
    if is_manjaro:
        mirror_paragraphs.append("On Manjaro this list is normally managed by pacman-mirrors; running pacman-mirrors later can replace your result.")
    # Instead of a big info card: a small info icon + heading. Click it
    # to read the whole explanation.
    hint_text = "\n\n".join(tr(p) for p in mirror_paragraphs)
    hint_icon = _centered(themed_image("dialog-information-symbolic", 16))
    hint_content = _hbox(8)
    hint_content.append(hint_icon)
    hint_content.append(Gtk.Label(label=tr("What are mirrors?")))
    mirror_hint = Gtk.MenuButton(halign=Gtk.Align.START,
                                 direction=Gtk.ArrowType.DOWN,
                                 css_classes=["flat"])
    mirror_hint.set_child(hint_content)
    hint_label = Gtk.Label(label=hint_text, wrap=True, max_width_chars=60,
                           xalign=0)
    _pad(hint_label, start=14, end=14, top=12, bottom=12)
    popover = Gtk.Popover()
    popover.set_child(hint_label)
    mirror_hint.set_popover(popover)
    outer.append(mirror_hint)

    if has_rate_mirrors:
        options_group = Adw.PreferencesGroup(
            title=tr("Mirror Options"),
            description=tr("Choose how mirrors are selected and tested"))

        country_row = _option_row(
            tr("Countries"),
            tr("Only use mirrors from these countries — 2-letter codes separated by commas, e.g. CH, DE, AT. Leave blank for all."))
        country_entry = _centered(Gtk.Entry(
            hexpand=True, width_chars=24,
            placeholder_text=tr("e.g. CH, DE, AT")))
        _detected_cc = _detect_country_code()
        if _detected_cc:
            country_entry.set_text(_detected_cc)
            country_row.set_subtitle(
                country_row.get_subtitle() + "\n" +
                tr("Detected automatically from your system settings"))
        country_row.add_suffix(country_entry)
        options_group.add(country_row)

        sort_row = _option_row(
            tr("Sort by"),
            tr("Order in which mirrors are picked for testing; the final order always comes from the speed test"))
        sort_options = [
            ("score_asc",  tr("Score ↑  (best reliability first)")),
            ("score_desc", tr("Score ↓  (worst reliability first)")),
            ("delay_asc",  tr("Delay ↑  (freshest mirrors first)")),
            ("delay_desc", tr("Delay ↓  (oldest mirrors first)")),
            ("random",     tr("Random   (shuffle before testing)")),
        ]
        sort_drop = _centered(Gtk.DropDown(
            model=Gtk.StringList.new([label for _, label in sort_options])))
        sort_drop.set_selected(0)
        sort_row.add_suffix(sort_drop)
        sort_row.set_visible(not is_manjaro)   # arch subcommand only

        protocol_row, https_switch = _switch_row(
            tr("HTTPS only"),
            tr("Ignore unencrypted HTTP mirrors (recommended)"))
        options_group.add(protocol_row)

        backup_row, backup_switch = _switch_row(
            tr("Backup current mirrorlist"),
            tr("Copies the current list to /etc/pacman.d/mirrorlist-backup before replacing it (an older backup is overwritten)"))
        options_group.add(backup_row)

        delay_row = _option_row(
            tr("Max mirror delay (hours)"),
            tr("Skip mirrors whose last sync is older than this"))
        delay_spin = _centered(Gtk.SpinButton())
        delay_spin.set_range(1, 72)
        delay_spin.set_increments(1, 6)
        delay_spin.set_value(6)
        delay_row.add_suffix(delay_spin)

        advanced_row = Adw.ExpanderRow(title=tr("Advanced options"))
        for nested in (sort_row, delay_row):
            advanced_row.add_row(nested)

        top_row = _option_row(
            tr("Number of mirrors to keep"),
            tr("How many of the fastest mirrors end up in the list (0 = all). 3 is usually enough."))
        top_spin = _centered(Gtk.SpinButton())
        top_spin.set_range(0, 50)
        top_spin.set_increments(1, 5)
        top_spin.set_value(3)
        top_row.add_suffix(top_spin)
        options_group.add(top_row)
        options_group.add(advanced_row)

        # Zeilen schlank halten: der Erklärungstext wandert vom sichtbaren
        # Untertitel in den Tooltip (Maus über die Zeile halten).
        for compact_row in (country_row, sort_row, protocol_row, backup_row,
                            delay_row, top_row):
            explanation = compact_row.get_subtitle()
            if explanation:
                compact_row.set_tooltip_text(explanation)
                compact_row.set_subtitle("")

        outer.append(options_group)

        run_btn = Gtk.Button(label=tr("Find Fastest Mirrors"))
        run_btn.add_css_class("suggested-action")
        run_btn.set_halign(Gtk.Align.CENTER)

        def _parse_countries():
            """-> (codes, ok). Only 2-letter ISO codes are valid for
            rate-mirrors' --include-countries (names like "Germany" are not)."""
            entered = country_entry.get_text().strip().replace(";", ",")
            codes = [part.strip().upper() for part in entered.split(",")
                     if part.strip()]
            ok = not any(len(c) != 2 or not (c.isascii() and c.isalpha())
                         for c in codes)
            return codes, ok

        def _build_flags():
            codes, _ok = _parse_countries()
            top_n = int(top_spin.get_value())
            max_delay = int(delay_spin.get_value()) * 3600
            global_flags = ["--protocol=https"] if https_switch.get_active() else []
            if codes:
                global_flags.append("--include-countries=" + ",".join(codes))
            if top_n > 0:
                global_flags.append(f"--max-mirrors-to-output={top_n}")
            sub_flags = [f"--max-delay={max_delay}"]
            if is_manjaro:
                sub_flags.append(f"--branch={manjaro_branch}")
            else:
                chosen_sort = sort_options[sort_drop.get_selected()][0]
                sub_flags.append(f"--sort-mirrors-by={chosen_sort}")
            return global_flags, sub_flags

        def on_run(*_):
            if not _parse_countries()[1]:
                return
            backup = backup_switch.get_active()
            global_flags, sub_flags = _build_flags()
            gf = " ".join(global_flags)
            sf = " ".join(sub_flags)

            # Step 1: only test/rank mirrors and save the ranked list to a
            # plain, user-owned temp file. Nothing under /etc/pacman.d is
            # touched yet, and — since ranking doesn't need root at all —
            # this step doesn't even prompt for a password. The user only
            # sees a password prompt if/when they actually choose to save.
            tmp_fd, tmp_path = tempfile.mkstemp(prefix="pachul-mirrorlist-", suffix=".tmp")
            os.close(tmp_fd)
            review_msg = tr("Done — review the result below")
            cmd = " ".join((
                "rate-mirrors", gf, f"--save={shlex.quote(tmp_path)}",
                mirror_cmd, sf, f'&& echo "{review_msg}"',
            ))

            def _after_test():
                _show_mirror_result(tmp_path, backup)

            dialog.close()
            run_terminal_fn(cmd, tr("Find Fastest Mirrors"), on_success=_after_test)

        def _show_mirror_result(tmp_path, backup):
            try:
                with open(tmp_path, "r", errors="replace") as f:
                    content = f.read()
            except OSError:
                content = ""
            server_count = sum(1 for ln in content.splitlines() if ln.strip().startswith("Server"))

            result_dialog = _modal_window(parent, tr("Mirror Ranking Result"), 680, 600)
            rtv, rhdr = _toolbar_with_header()

            def _discard(*_):
                _unlink_quietly(tmp_path)
                result_dialog.close()

            discard_btn = _btn(tr("Discard"), "flat")
            discard_btn.connect("clicked", _discard)
            rhdr.pack_start(discard_btn)

            def _save(*_):
                result_dialog.close()
                # A single pkexec call wrapping both steps in one bash -c,
                # rather than the old "sudo -S -v" credential-warming trick
                # (which existed only to stop sudo from re-prompting between
                # two separate `sudo mv` / `sudo install` calls) — pkexec has
                # no local credential cache to warm, so one call sharing one
                # Polkit authentication is the equivalent here.
                quoted_tmp = shlex.quote(tmp_path)
                if backup:
                    script = (
                        "mv /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist-backup && "
                        f"install -m644 {quoted_tmp} /etc/pacman.d/mirrorlist"
                    )
                    ok_msg = tr("Done — backup saved to /etc/pacman.d/mirrorlist-backup")
                    cmd2 = f'pkexec /usr/bin/bash -c {shlex.quote(script)} && echo "{ok_msg}"'
                else:
                    ok_msg = tr("Done — /etc/pacman.d/mirrorlist updated")
                    cmd2 = (f"pkexec /usr/bin/install -m644 {quoted_tmp} "
                            f'/etc/pacman.d/mirrorlist && echo "{ok_msg}"')

                run_terminal_fn(cmd2, tr("Save Mirrorlist"),
                                on_success=lambda: _unlink_quietly(tmp_path))

            save_btn = _btn(tr("Save as New Mirrorlist"), "suggested-action")
            save_btn.connect("clicked", _save)
            rhdr.pack_end(save_btn)
            rtv.add_top_bar(rhdr)

            router_outer = _pad(_vbox(8), start=16, end=16, top=12, bottom=16)

            router_outer.append(Gtk.Label(
                label=tr("{n} mirrors found, fastest first. Review the list, then save it as your new mirrorlist or discard it.").format(n=server_count),
                halign=Gtk.Align.START, css_classes=["dim-label"]))

            rscroll = _scrolled(_AUTO, _AUTO, "card")
            rscroll.set_vexpand(True)
            rbuf = Gtk.TextBuffer()
            rbuf.set_text(content or tr("# No output captured"))
            rview = Gtk.TextView(buffer=rbuf, editable=False, monospace=True,
                                 wrap_mode=Gtk.WrapMode.NONE)
            rview.add_css_class("terminal-view")
            router_outer.append(rscroll)
            rscroll.set_child(rview)

            result_dialog.set_content(rtv)
            rtv.set_content(router_outer)
            result_dialog.present()

        run_btn.connect("clicked", on_run)
        outer.append(run_btn)

        preview_lbl = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.CHAR,
                                selectable=True, halign=Gtk.Align.CENTER,
                                css_classes=["caption", "dim-label"])

        def update_preview(*_):
            _codes, valid = _parse_countries()
            toggle_error = (country_entry.remove_css_class if valid
                            else country_entry.add_css_class)
            toggle_error("error")
            run_btn.set_sensitive(valid)
            glob, sub = _build_flags()
            preview_lbl.set_label("rate-mirrors {} {} {}".format(
                " ".join(glob), mirror_cmd, " ".join(sub)))

        for source, signal_name in (
            (country_entry, "changed"),
            (sort_drop,     "notify::selected"),
            (https_switch,  "notify::active"),
            (delay_spin,    "value-changed"),
            (top_spin,      "value-changed"),
        ):
            source.connect(signal_name, update_preview)
        update_preview()
        outer.append(preview_lbl)

    else:
        status = _status_page(
            "network-transmit-receive-symbolic",
            tr("rate-mirrors not installed"),
            tr("rate-mirrors measures how fast mirrors respond from your location and sorts your mirrorlist accordingly. Testing needs no administrator rights."))
        install_btn = _btn(tr("Install rate-mirrors"), "suggested-action")
        install_btn.set_halign(Gtk.Align.CENTER)

        def _install_rate_mirrors(*_):
            dialog.close()
            run_terminal_fn("pkexec /usr/bin/pacman -S --noconfirm rate-mirrors",
                            tr("Install rate-mirrors"))
        install_btn.connect("clicked", _install_rate_mirrors)
        status.set_child(install_btn)
        outer.append(status)

    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_content(tv)
    dialog.present()


# ─── Orphan finder dialog ─────────────────────────────────────────────────────

def show_orphan_finder(parent, run_terminal_fn):
    dialog = _modal_window(parent, tr("Orphaned Packages"), 560, 460)

    tv, hdr = _toolbar_with_header()
    close_btn = _btn(tr("Close"), "flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = _vbox(0)

    orphans = get_orphans()

    if not orphans:
        status = _status_page("emblem-ok-symbolic", tr("No Orphans Found"),
                              tr("Your system has no orphaned packages."))
        status.set_vexpand(True)
        outer.append(status)
    else:
        info_bar = _pad(_hbox(8), start=16, end=16, top=12, bottom=8)
        info_bar.append(themed_image("dialog-warning-symbolic", 18))
        info_bar.append(Gtk.Label(
            label=tr("{n} orphaned package(s) — pulled in automatically as a dependency at some point, but nothing on your system requires them anymore. Safe to remove, or leave them if you might need them again.").format(n=len(orphans)),
            hexpand=True, halign=Gtk.Align.START, wrap=True,
            css_classes=["caption"]))
        outer.append(info_bar)

        scroll = _pad(_scrolled(_NEVER, _AUTO), start=12, end=12)
        scroll.set_vexpand(True)

        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                              css_classes=["boxed-list"])

        for o in orphans:
            row = Adw.ActionRow(title=o["name"], subtitle=o["version"])
            pkg_icon = themed_image("package-x-generic-symbolic", 18)
            pkg_icon.add_css_class("dim-label")
            row.add_prefix(pkg_icon)
            rm_btn = _centered(_btn(tr("Remove"), "destructive-action", "flat"))
            name = o["name"]

            def _do_remove_one(*_, n=name, r=row):
                # Der Dialog bleibt offen, damit mehrere Waisen nacheinander
                # entfernt werden können. Nur die betroffene Zeile verschwindet,
                # und erst, wenn das Entfernen tatsächlich geklappt hat.
                if distro.is_arch():
                    remove_cmd = f"pkexec /usr/bin/pacman -R --noconfirm {shlex.quote(n)}"
                else:
                    remove_cmd = pkgmanager.remove_cmd([n])
                run_terminal_fn(
                    remove_cmd,
                    tr("Remove {name} ").format(name=n),
                    on_success=lambda: listbox.remove(r),
                    parent=dialog)
            rm_btn.connect("clicked", _do_remove_one)
            row.add_suffix(rm_btn)
            listbox.append(row)

        outer.append(scroll)
        scroll.set_child(listbox)

        btn_box = _pad(_hbox(8), top=12, bottom=16)
        btn_box.set_halign(Gtk.Align.CENTER)
        names = " ".join(shlex.quote(o["name"]) for o in orphans)
        name_list = [o["name"] for o in orphans]
        remove_all_btn = _btn(
            tr("Remove All {n} Orphans").format(n=len(orphans)),
            "destructive-action")

        def _remove_everything(*_):
            dialog.close()
            if distro.is_arch():
                cmd_all = f"pkexec /usr/bin/pacman -Rns --noconfirm {names}"
            else:
                cmd_all = pkgmanager.remove_cmd(name_list, purge=distro.is_debian())
            run_terminal_fn(cmd_all, tr("Remove All Orphans"))
        remove_all_btn.connect("clicked", _remove_everything)
        btn_box.append(remove_all_btn)
        outer.append(btn_box)

    dialog.set_content(tv)
    tv.set_content(outer)
    dialog.present()


# ─── Clean cache dialog ────────────────────────────────────────────────────────

def show_clean_cache_dialog(parent, run_terminal_fn):
    # Adw.Window instead of Adw.Dialog so the window can be exactly as tall
    # as the main window (an Adw.Dialog sheet has a fixed content size).
    dialog = Adw.Window()
    dialog.set_title(tr("Clean Cache"))
    main_win_height = parent.get_height() or 620
    dialog.set_default_size(520, main_win_height)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Cancel"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    _, code = run_command("which paccache 2>/dev/null")
    has_paccache = distro.is_arch() and (code == 0)

    cache_dir_by_family = {
        "debian": "/var/cache/apt/archives",
        "fedora": "/var/cache/dnf",
        "suse":   "/var/cache/zypp/packages",
    }
    cache_path = "/var/cache/pacman/pkg" if distro.is_arch() \
        else cache_dir_by_family.get(distro.get_family(), "N/A")

    cache_hint = make_info_box(
        "cache_cleaner",
        "What is the package cache?",
        ["When you install or update software, the package manager keeps the downloaded package files. This lets you reinstall a package without downloading it again, or go back to an older version.",
         "The cache keeps growing and can take up many gigabytes. Cleaning it is safe for the running system, but older versions are no longer available locally afterwards — so better not clean it right after an update that causes problems, you may still need the old version."],
        dismissible=True)
    if cache_hint is not None:
        outer.append(cache_hint)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("What this does"))
    if has_paccache:
        info_group.set_description(tr(
            "Removes old cached package versions from /var/cache/pacman/pkg "
            "using paccache, keeping the 2 most recent versions of each "
            "package so you can still downgrade later if needed. "
            "Currently installed packages are never touched."
        ))
    elif distro.is_arch():
        info_group.set_description(tr(
            "paccache isn't installed, so this falls back to pacman's "
            "built-in cleanup (pacman -Sc), which removes cached versions "
            "of packages that are no longer installed, plus superseded old "
            "versions of packages you still have. "
            "Currently installed packages are never touched."
        ))
    else:
        info_group.set_description(tr(
            "Removes cached package files from {path}. Currently "
            "installed packages are never touched."
        ).format(path=cache_path))
    outer.append(info_group)

    size_group = Adw.PreferencesGroup()
    size_row = Adw.ActionRow()
    size_row.set_title(tr("Current Cache Size"))
    size_row.set_subtitle(cache_path)
    size_lbl = Gtk.Label(label=get_package_cache_size())
    size_lbl.add_css_class("caption"); size_lbl.add_css_class("dim-label")
    size_row.add_suffix(size_lbl)
    size_group.add(size_row)
    outer.append(size_group)

    clean_btn = Gtk.Button(label=tr("Clean Cache"))
    clean_btn.add_css_class("suggested-action")
    clean_btn.set_halign(Gtk.Align.CENTER)

    def _do_clean(*_):
        if distro.is_arch():
            cmd = "{ paccache -rk2 2>/dev/null || pkexec /usr/bin/pacman -Sc --noconfirm; }"
        else:
            cmd = pkgmanager.clean_cache_cmd() or "true"
        # Not parent=dialog here: this dialog is an Adw.Dialog (a sheet
        # presented over the main window), not a real Gtk.Window, so it
        # can't be passed to set_transient_for() — unlike the Adw.Window
        # dialogs elsewhere in this file. Since it isn't a separate
        # top-level window, there's also no stacking-order warning risk
        # to guard against here; the default parent is fine.
        run_terminal_fn(cmd, tr("Clean Cache"))

    clean_btn.connect("clicked", _do_clean)
    outer.append(clean_btn)

    # ── System Cleanup (from the user's manjaro-wartung.sh "MODUL 4"): the
    # journal/thumbnail/trash part of it, which is genuinely distro-agnostic
    # (journalctl, find, gio are the same everywhere) — unlike the package
    # cache above it, which needed the pacman/apt/dnf/zypper branching. ──
    sys_group = Adw.PreferencesGroup()
    sys_group.set_title(tr("System Cleanup"))
    sys_group.set_description(tr(
        "Not package-related — general disk cleanup for the systemd "
        "journal, old thumbnail previews, and the trash."))

    def _sys_row(title, subtitle, button_label, cmd, cmd_title, suggested=False):
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(title))
        row.set_tooltip_text(subtitle)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            # Same Adw.Dialog caveat as _do_clean above: no parent=dialog
            # here, this isn't a real Gtk.Window.
            run_terminal_fn(cmd, cmd_title)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    sys_group.add(_sys_row(
        tr("Clean systemd Journal"),
        tr("Runs 'journalctl --vacuum-size=500M' followed by "
           "'--vacuum-time=4weeks'. This only vacuums (rotates out and "
           "discards) old log entries — it shrinks the journal down to "
           "500 MB total and additionally removes anything older than 4 "
           "weeks, whichever removes more; it never touches today's live, "
           "currently-being-written log. Needs root privileges (via pkexec) since the journal "
           "under /var/log/journal is root-owned. Worth running if disk "
           "space is tight and 'journalctl --disk-usage' shows the "
           "journal has grown large — otherwise there's no real downside "
           "to leaving it, you just lose the ability to look further "
           "back in the logs."),
        tr("Run"),
        "pkexec /usr/bin/bash -c " + shlex.quote(
            "journalctl --vacuum-size=500M && journalctl --vacuum-time=4weeks"),
        tr("Clean systemd Journal"),
    ))
    sys_group.add(_sys_row(
        tr("Remove Old Thumbnail Previews"),
        tr("Deletes cached preview images under ~/.cache/thumbnails that "
           "haven't been accessed in the last 30 days — the small "
           "generated thumbnails your file manager shows for images, "
           "videos, and documents, not the original files themselves. "
           "Nothing here is unique data: any thumbnail your file manager "
           "still needs gets silently regenerated the next time you "
           "browse to that folder, so this is purely reclaiming disk "
           "space with no real downside beyond a brief re-generation "
           "delay next time. No elevated privileges needed — this only touches your own "
           "user cache, never system files."),
        tr("Run"),
        'bash -c \'if [ -d "$HOME/.cache/thumbnails" ]; then '
        'find "$HOME/.cache/thumbnails" -type f -atime +30 -delete && '
        'echo "' + tr("Done.") + '"; else echo "' +
        tr("No thumbnail cache found.") + '"; fi\'',
        tr("Remove Old Thumbnail Previews"),
    ))
    sys_group.add(_sys_row(
        tr("Empty Trash"),
        tr("Permanently empties your desktop trash/recycle bin via 'gio "
           "trash --empty', following the same XDG trash location "
           "(usually ~/.local/share/Trash) your file manager already "
           "uses — so anything you see in the Trash there is exactly "
           "what this removes. Unlike a normal delete, this step is NOT "
           "recoverable through the trash/recycle-bin UI afterwards; "
           "files not already in the trash are completely unaffected. No "
           "root privileges needed, since it only ever touches your own account's "
           "trash."),
        tr("Run"),
        'bash -c \'if command -v gio >/dev/null 2>&1; then gio trash --empty && '
        'echo "' + tr("Done.") + '"; else echo "' +
        tr("gio not found — nothing to do.") + '"; fi\'',
        tr("Empty Trash"),
    ))
    outer.append(sys_group)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Import package list dialog ────────────────────────────────────────────────

def show_import_pkgs_intro(parent, helper, on_choose_file):
    """Explanation shown *before* the file picker opens, so the user knows
    what will happen before they even pick a file."""
    dialog = Adw.Dialog()
    dialog.set_title(tr("Import Package List"))
    dialog.set_content_width(480)
    dialog.set_content_height(360)

    tv, hdr = _toolbar_with_header()
    cancel_btn = _btn(tr("Cancel"), "flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("Install Programs From a Saved List"))
    if helper:
        info_group.set_description(tr(
            "Reads one package name per line from the file (lines starting "
            "with # are ignored), then installs every listed package via "
            "{helper}, using --needed so anything already installed is "
            "skipped automatically. Nothing else on your system is changed."
        ).format(helper=helper))
    else:
        info_group.set_description(tr(
            "Reads one package name per line from the file (lines starting "
            "with # are ignored), then installs every listed package via "
            "pacman -S --needed, so anything already installed is skipped "
            "automatically. AUR packages in the list can't be installed this "
            "way since no AUR helper is configured — only official-repo "
            "packages will succeed. Nothing else on your system is changed."
        ))
    outer.append(info_group)

    choose_btn = Gtk.Button(label=tr("Choose File…"))
    choose_btn.add_css_class("suggested-action")
    choose_btn.set_halign(Gtk.Align.CENTER)

    def _proceed(*_):
        dialog.close()
        on_choose_file()

    choose_btn.connect("clicked", _proceed)
    outer.append(choose_btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_child(tv)
    dialog.present(parent)


def show_import_pkgs_dialog(parent, names, helper, run_terminal_fn):
    """Preview of what was actually found in the chosen file, shown after
    the file picker — the "why"/"how" was already explained by
    show_import_pkgs_intro() before the file was even picked, so this one
    only needs the concrete result and the final confirmation."""
    dialog = Adw.Window()
    dialog.set_title(tr("Import Package List"))
    dialog.set_default_size(520, 480)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    list_group = Adw.PreferencesGroup()
    list_group.set_title(tr("{n} packages found in file").format(n=len(names)))

    list_scroll = Gtk.ScrolledWindow()
    list_scroll.set_min_content_height(260)
    list_scroll.set_vexpand(True)
    list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    list_scroll.add_css_class("card")

    names_buf = Gtk.TextBuffer()
    names_buf.set_text("\n".join(names))
    names_view = Gtk.TextView(buffer=names_buf)
    names_view.set_editable(False); names_view.set_monospace(True)
    names_view.set_wrap_mode(Gtk.WrapMode.NONE)
    names_view.add_css_class("terminal-view")
    list_scroll.set_child(names_view)

    outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    outer_box.append(list_scroll)
    list_group.add(outer_box)
    outer.append(list_group)

    install_btn = Gtk.Button(label=tr("Install {n} packages").format(n=len(names)))
    install_btn.add_css_class("suggested-action")
    install_btn.set_halign(Gtk.Align.CENTER)

    def _do_install(*_):
        dialog.close()
        if helper:
            quoted = " ".join(shlex.quote(n) for n in names)
            cmd = aur_helper_install_cmd(helper, quoted, needed=True)
        elif distro.is_arch():
            quoted = " ".join(shlex.quote(n) for n in names)
            cmd = f"pkexec /usr/bin/pacman -S --needed --noconfirm {quoted}"
        else:
            cmd = pkgmanager.install_cmd(names)
        run_terminal_fn(cmd, tr("Install {n} packages").format(n=len(names)))

    install_btn.connect("clicked", _do_install)
    outer.append(install_btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Install a local package file (.tar.gz, .pkg.tar.zst, .deb, .rpm) ─────────

def show_install_local_dialog(parent, info, run_terminal_fn):
    """Summary of a manually chosen package file plus the final confirmation.

    *info* comes from localpkg.analyze(); nothing has been unpacked or
    installed at this point. For source tarballs (PKGBUILD) the build script
    is shown first, because building runs arbitrary shell code as the user."""
    dialog = Adw.Window()
    dialog.set_title(tr("Install Local Package"))
    dialog.set_default_size(560, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    kind = info["kind"]
    kind_label = {
        localpkg.KIND_PACMAN_PKG: tr("Built Arch package (installed with pacman -U)"),
        localpkg.KIND_PKGBUILD:   tr("Source package with PKGBUILD (built with makepkg, then installed)"),
        localpkg.KIND_DEB:        tr("Debian package (.deb)"),
        localpkg.KIND_RPM:        tr("RPM package (.rpm)"),
        localpkg.KIND_FLATPAK_BUNDLE: tr("Flatpak bundle (.flatpak)"),
        localpkg.KIND_FLATPAK_REF:    tr("Flatpak reference (.flatpakref) — the app is downloaded from its remote"),
    }.get(kind, tr("Unknown"))

    group = Adw.PreferencesGroup()
    group.set_title(os.path.basename(info["path"]))

    def _row(title, value):
        r = Adw.ActionRow()
        r.set_title(GLib.markup_escape_text(title))
        r.set_subtitle(GLib.markup_escape_text(value))
        r.set_subtitle_selectable(True)
        group.add(r)

    _row(tr("Type"), kind_label)
    if info.get("name"):
        _row(tr("Package"), info["name"])
    if info.get("version"):
        _row(tr("Version"), info["version"])
    if info.get("desc"):
        _row(tr("Description"), info["desc"])
    _row(tr("Size"), f"{info.get('size', 0) / 1024 / 1024:.1f} MiB")
    outer.append(group)

    cmd = localpkg.install_command(info)

    if cmd is None:
        # Unsupported / not a package: say why and stop here.
        err = Adw.StatusPage()
        err.set_icon_name("dialog-warning-symbolic")
        err.set_title(tr("Can't install this file"))
        err.set_description(GLib.markup_escape_text(tr(info.get("error") or "Unknown error")))
        err.set_vexpand(False)
        outer.append(err)
        if info.get("entries"):
            peek = Adw.PreferencesGroup()
            peek.set_title(tr("First entries in the archive"))
            buf = Gtk.TextBuffer()
            buf.set_text("\n".join(info["entries"]))
            view = Gtk.TextView(buffer=buf)
            view.set_editable(False); view.set_monospace(True)
            view.set_wrap_mode(Gtk.WrapMode.NONE)
            view.add_css_class("terminal-view")
            sc = Gtk.ScrolledWindow()
            sc.set_min_content_height(120)
            sc.add_css_class("card")
            sc.set_child(view)
            peek.add(sc)
            outer.append(peek)
    else:
        if kind == localpkg.KIND_PKGBUILD:
            warn = Adw.PreferencesGroup()
            warn.set_title(tr("Review the PKGBUILD before building"))
            warn.set_description(tr(
                "Building runs the shell code from this PKGBUILD as your user. "
                "Only continue if you trust where the file came from. Missing "
                "dependencies are installed from the official repositories "
                "first (administrator password required); AUR-only "
                "dependencies must be installed beforehand."
            ))
            buf = Gtk.TextBuffer()
            buf.set_text(info.get("pkgbuild_text") or "")
            view = Gtk.TextView(buffer=buf)
            view.set_editable(False); view.set_monospace(True)
            view.set_wrap_mode(Gtk.WrapMode.NONE)
            view.add_css_class("terminal-view")
            sc = Gtk.ScrolledWindow()
            sc.set_min_content_height(240)
            sc.set_vexpand(True)
            sc.add_css_class("card")
            sc.set_child(view)
            warn.add(sc)
            outer.append(warn)
        elif kind in (localpkg.KIND_FLATPAK_BUNDLE, localpkg.KIND_FLATPAK_REF):
            note = Gtk.Label(label=tr(
                "Installed for your user account (no administrator password "
                "needed). Required runtimes are fetched from your Flatpak "
                "remotes."))
            note.set_wrap(True)
            note.set_xalign(0)
            note.add_css_class("dim-label")
            outer.append(note)
        else:
            note = Gtk.Label(label=tr(
                "The package is installed as-is. Dependencies are resolved by "
                "your package manager; you will be asked for the administrator "
                "password."))
            note.set_wrap(True)
            note.set_xalign(0)
            note.add_css_class("dim-label")
            outer.append(note)

        label = (tr("Build and Install") if kind == localpkg.KIND_PKGBUILD
                 else tr("Install"))
        btn = Gtk.Button(label=label)
        btn.add_css_class("suggested-action")
        btn.set_halign(Gtk.Align.CENTER)

        title = tr("Install {name}").format(
            name=info.get("name") or os.path.basename(info["path"]))

        def _go(*_):
            dialog.close()
            run_terminal_fn(cmd, title)

        btn.connect("clicked", _go)
        outer.append(btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Export package list dialog ────────────────────────────────────────────────

def show_export_pkgs_intro(parent, on_choose_location):
    """Explanation shown *before* the save-file picker opens, so it's clear
    up front exactly what ends up in the file."""
    dialog = Adw.Dialog()
    dialog.set_title(tr("Export Package List"))
    dialog.set_content_width(480)
    dialog.set_content_height(320)

    tv, hdr = _toolbar_with_header()
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("Save Installed Programs to a List"))
    info_group.set_description(tr(
        "Writes the names of every package you explicitly installed "
        "yourself (one per line) to a plain text file — this deliberately "
        "excludes dependencies that were only pulled in automatically. "
        "Use \"Import Package List\" later, on this or another machine, to "
        "reinstall the same set of programs."
    ))
    outer.append(info_group)

    choose_btn = Gtk.Button(label=tr("Choose Location…"))
    choose_btn.add_css_class("suggested-action")
    choose_btn.set_halign(Gtk.Align.CENTER)

    def _proceed(*_):
        dialog.close()
        on_choose_location()

    choose_btn.connect("clicked", _proceed)
    outer.append(choose_btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── File search dialog (pacman -F) ──────────────────────────────────────────

def show_file_search_dialog(parent, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Find Package by File"))
    dialog.set_default_size(600, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    sync_banner = Adw.Banner()
    sync_banner.set_title(tr("File database not synced yet — sync it to search"))
    sync_banner.set_button_label(tr("Sync Now"))
    sync_banner.set_revealed(not files_db_available())
    outer.append(sync_banner)

    search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    search_box.set_margin_start(12); search_box.set_margin_end(12)
    search_box.set_margin_top(10);   search_box.set_margin_bottom(6)
    entry = Gtk.SearchEntry()
    entry.set_placeholder_text(tr("e.g. libssl.so.3 or usr/bin/htop"))
    entry.set_hexpand(True)
    search_box.append(entry)
    search_btn = Gtk.Button(label=tr("Search"))
    search_btn.add_css_class("suggested-action")
    search_box.append(search_btn)
    outer.append(search_box)

    hint = Gtk.Label(label=tr("Find out which package installs a given file or command."))
    hint.add_css_class("caption"); hint.add_css_class("dim-label")
    hint.set_margin_start(12); hint.set_margin_bottom(8)
    hint.set_halign(Gtk.Align.START)
    outer.append(hint)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    scroll.set_margin_start(12); scroll.set_margin_end(12); scroll.set_margin_bottom(12)
    listbox = Gtk.ListBox()
    listbox.set_selection_mode(Gtk.SelectionMode.NONE)
    listbox.add_css_class("boxed-list")
    scroll.set_child(listbox)
    outer.append(scroll)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    def render(results):
        while listbox.get_first_child():
            listbox.remove(listbox.get_first_child())
        if not results:
            empty = Adw.ActionRow()
            empty.set_title(tr("No Package Found"))
            empty.set_subtitle(tr("No package provides a matching file."))
            listbox.append(empty)
            return
        for r in results:
            pkg_full = r["pkg"]
            pkg_name = pkg_full.split("/")[-1]
            repo = pkg_full.split("/")[0] if "/" in pkg_full else ""

            row = Adw.ExpanderRow()
            row.set_title(pkg_name)
            row.set_subtitle(f"{repo}  ·  {r['version']}" if repo else r["version"])
            icon = themed_image("package-x-generic-symbolic", 18)
            icon.add_css_class("dim-label")
            row.add_prefix(icon)

            if distro.is_arch():
                _, installed_code = run_command(f"pacman -Qi {shlex.quote(pkg_name)} 2>/dev/null")
                pkg_installed = installed_code == 0
            else:
                pkg_installed = pkgmanager.is_installed(pkg_name)
            if pkg_installed:
                badge = Gtk.Label(label=tr("INSTALLED"))
                badge.add_css_class("caption"); badge.add_css_class("status-installed")
                badge.add_css_class("row-status-pill")
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)
            else:
                inst_btn = Gtk.Button(label=tr("Install"))
                inst_btn.add_css_class("suggested-action"); inst_btn.add_css_class("flat")
                inst_btn.set_valign(Gtk.Align.CENTER)
                name = pkg_name
                inst_btn.connect("clicked", lambda *_, n=name: (
                    dialog.close(),
                    run_terminal_fn(
                        f"pkexec /usr/bin/pacman -S --noconfirm {shlex.quote(n)}" if distro.is_arch()
                        else pkgmanager.install_cmd([n]),
                        tr("Install {name}").format(name=n))
                ))
                row.add_suffix(inst_btn)

            shown_files = r["files"][:20]
            for f in shown_files:
                frow = Adw.ActionRow()
                frow.set_title(f if f.startswith("/") else f"/{f}")
                row.add_row(frow)
            extra = len(r["files"]) - len(shown_files)
            if extra > 0:
                more = Adw.ActionRow()
                more.set_title(tr("… and {n} more files").format(n=extra))
                row.add_row(more)

            listbox.append(row)

    def do_sync(*_):
        sync_banner.set_revealed(False)
        cmd = "pkexec /usr/bin/pacman -Fy --noconfirm" if distro.is_arch() else pkgmanager.sync_files_db_cmd()
        if cmd:
            run_terminal_fn(cmd, tr("Sync File Database"))
    sync_banner.connect("button-clicked", do_sync)

    def do_search(*_):
        query = entry.get_text().strip()
        if not query:
            return
        if not files_db_available():
            sync_banner.set_revealed(True)
            return
        while listbox.get_first_child():
            listbox.remove(listbox.get_first_child())
        searching = Adw.ActionRow()
        searching.set_title(tr("Searching…"))
        listbox.append(searching)

        def worker():
            results = search_file_owner(query)
            GLib.idle_add(render, results)

        threading.Thread(target=worker, daemon=True).start()

    search_btn.connect("clicked", do_search)
    entry.connect("activate", do_search)

def show_sysinfo_dialog(parent):
    dialog = _modal_window(parent, tr("System Information"), 560, 680)

    tv, hdr = _toolbar_with_header()
    close_btn = _btn(tr("Close"), "flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    loading_spinner = Gtk.Spinner(width_request=32, height_request=32,
                                  halign=Gtk.Align.CENTER)
    loading_spinner.start()
    loading_lbl = Gtk.Label(label=tr("Gathering system info…"),
                            css_classes=["dim-label"])
    loading_box = _vbox(12)
    loading_box.set_halign(Gtk.Align.CENTER)
    loading_box.set_valign(Gtk.Align.CENTER)
    loading_box.set_vexpand(True)
    for part in (loading_spinner, loading_lbl):
        loading_box.append(part)
    outer.append(loading_box)

    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_content(tv)
    dialog.present()

    def value_group(title, keys, info):
        """PreferencesGroup mit einer Zeile pro vorhandenem Schlüssel aus `info`."""
        group = Adw.PreferencesGroup(title=title)
        for key in keys:
            if key not in info:
                continue
            entry_row = Adw.ActionRow(title=tr(key))
            entry_row.add_suffix(Gtk.Label(
                label=info[key], selectable=True,
                css_classes=["caption", "dim-label"]))
            group.add(entry_row)
        return group

    def populate(info):
        outer.remove(loading_box)

        outer.append(value_group(
            tr("System"), ("OS", "Desktop", "Kernel", "Architecture"), info))
        outer.append(value_group(
            tr("Hardware"), ("Processor", "RAM", "Disk (/)", "Disk Type"), info))
        outer.append(value_group(
            tr("Packages"),
            ("Pacman", "Package Manager", "AUR Helper", "Installed Packages",
             "Foreign (AUR) Packages", "Package Cache Size"),
            info))

        repo_counts = info.get("Repo Counts") or {}
        if repo_counts:
            repo_group = Adw.PreferencesGroup(
                title=tr("Installed by Repository"),
                description=tr("How many installed packages come from each source"))
            # Offizielle bzw. aktivierte Sync-Repos zuerst (alphabetisch), AUR
            # bzw. Fremdpakete zuletzt, denn das ist für pacman kein echtes Repo.
            ordered = sorted(k for k in repo_counts if k != "aur / foreign")
            if "aur / foreign" in repo_counts:
                ordered.append("aur / foreign")
            for repo in ordered:
                shown_name = tr("AUR / Foreign") if repo == "aur / foreign" else repo
                repo_row = Adw.ActionRow(title=shown_name)
                repo_row.add_suffix(Gtk.Label(
                    label=tr("{n} pkgs").format(n=repo_counts[repo]),
                    css_classes=["caption", "dim-label"]))
                repo_group.add(repo_row)
            outer.append(repo_group)
        return False

    def worker():
        GLib.idle_add(populate, get_system_info())

    threading.Thread(target=worker, daemon=True).start()


# ─── About dialog (single page — see show_about_dialog docstring) ────────────

def show_about_dialog(parent, app_icon_name="io.github.wergosam.pachul"):
    """Custom, single-page replacement for Adw.AboutDialog.

    Adw.AboutDialog is a rigid GNOME-standard widget: as soon as you set
    debug_info / a stock license_type / multiple credit categories, it
    grows extra navigation buttons at the bottom that push those onto
    separate "Legal"/"Troubleshooting"/"Credits" pages — by design, and
    not something the public API lets you flatten. Since the whole point
    here is "everything visible at a glance, no clicking around", this
    builds a plain Adw.Window instead: one scrollable page, no
    sub-navigation, just grouped rows — and, unlike Adw.Dialog, a real
    window the user can freely move and resize."""
    import platform
    try:
        distro_name = distro.get_distro_name()
        pkg_mgr = distro.get_package_manager() or "?"
    except Exception:
        distro_name, pkg_mgr = "?", "?"
    gtk_ver = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
    adw_ver = f"{Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}"
    py_ver = platform.python_version()
    version = APP_VERSION

    dialog = Adw.Window()
    dialog.set_title(tr("About Pachul"))
    # Wider than before so the identity block and description can sit
    # side by side instead of stacking into one tall column. Height is
    # taken from the main window's own startup default size (set via
    # set_default_size() in window.py), not its current/resized size —
    # get_default_size() always returns that original value, so this
    # dialog stays exactly as tall as the program window was at launch
    # even if the user has since resized the main window.
    _, start_height = parent.get_default_size() if parent is not None else (600, 560)
    if start_height <= 0:
        start_height = 560
    dialog.set_default_size(600, start_height)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    # Everything below lives in a ScrolledWindow. Adw.Dialog is capped to
    # the parent window's size, so on a small/default-size main window the
    # dialog's natural (unscrolled) height used to get clipped top and
    # bottom with no way to reach the rest. Inside a scroller it simply
    # scrolls instead.
    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    outer.set_margin_top(8);    outer.set_margin_bottom(24)
    outer.set_margin_start(24); outer.set_margin_end(24)

    # ── Identity block (icon/name/version/links) on the left, purpose
    # description on the right — side by side to keep the dialog short ──
    top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)

    left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    left_col.set_halign(Gtk.Align.CENTER)
    left_col.set_valign(Gtk.Align.START)
    left_col.set_size_request(180, -1)
    icon_img = Gtk.Image.new_from_icon_name(app_icon_name)
    icon_img.set_pixel_size(80)
    left_col.append(icon_img)
    name_lbl = Gtk.Label(label="Pachul")
    name_lbl.add_css_class("title-1")
    left_col.append(name_lbl)
    ver_lbl = Gtk.Label(label=tr("Version {v}").format(v=version))
    ver_lbl.add_css_class("dim-label")
    left_col.append(ver_lbl)
    top_box.append(left_col)

    # ── Kurzfassung des Zwecks — direkt sichtbar, kein Klick nötig ──
    right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    right_col.set_valign(Gtk.Align.CENTER)
    right_col.set_hexpand(True)
    desc_lbl = Gtk.Label(label=tr(
        "Pachul is a graphical package manager for Arch, Debian/Ubuntu, "
        "Fedora and openSUSE. Search, install, update and remove packages, "
        "review config file conflicts, keep external tools (rustup, npm, "
        "pip, Flatpak, …) up to date, and more — all from one native "
        "GTK4/libadwaita app."))
    desc_lbl.set_wrap(True)
    desc_lbl.set_justify(Gtk.Justification.LEFT)
    desc_lbl.set_halign(Gtk.Align.START)
    desc_lbl.set_xalign(0)
    right_col.append(desc_lbl)
    top_box.append(right_col)
    outer.append(top_box)

    # ── Alle Detailinformationen als flache Liste, keine Unterseiten ──
    info_group = Adw.PreferencesGroup()
    info_rows = [
        (tr("Developer"), "Juerg Rechsteiner"),
        (tr("License"), "GPL-2.0-or-later"),
        (tr("Distro"), distro_name),
        (tr("Package Manager"), pkg_mgr),
        ("GTK", gtk_ver),
        ("libadwaita", adw_ver),
        ("Python", py_ver),
    ]
    for title, value in info_rows:
        row = Adw.ActionRow()
        row.set_title(title)
        val_lbl = Gtk.Label(label=value)
        val_lbl.add_css_class("caption"); val_lbl.add_css_class("dim-label")
        val_lbl.set_selectable(True)
        row.add_suffix(val_lbl)
        info_group.add(row)
    outer.append(info_group)

    # ── Links & Aktionen — direkt als Buttons, keine "Legal"/"Troubleshooting"-Seite.
    # Angehängt an die linke Spalte (unter Icon/Name/Version), damit der
    # Dialog insgesamt weniger hoch wird. ──
    links_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    links_box.set_margin_top(6)

    def open_uri(uri):
        Gtk.UriLauncher.new(uri).launch(parent, None, None)

    website_btn = Gtk.Button(label=tr("Website"))
    website_btn.connect("clicked", lambda *_: open_uri("https://github.com/wergosam/Pachul"))
    links_box.append(website_btn)

    issue_btn = Gtk.Button(label=tr("Report an Issue"))
    issue_btn.connect("clicked", lambda *_: open_uri("https://github.com/wergosam/Pachul/issues"))
    links_box.append(issue_btn)

    def copy_debug_info(*_):
        text = (f"Pachul {version}\n"
                f"Distro: {distro_name} (pkg manager: {pkg_mgr})\n"
                f"GTK: {gtk_ver}  ·  libadwaita: {adw_ver}\n"
                f"Python: {py_ver}\n")
        display = Gdk.Display.get_default()
        if display:
            display.get_clipboard().set(text)
        copy_btn.set_label(tr("Copied!"))
        GLib.timeout_add(1500, lambda: copy_btn.set_label(tr("Copy Debug Info")) or False)

    copy_btn = Gtk.Button(label=tr("Copy Debug Info"))
    copy_btn.connect("clicked", copy_debug_info)
    links_box.append(copy_btn)
    left_col.append(links_box)

    copyright_lbl = Gtk.Label(label="© 2024–2026 Juerg Rechsteiner")
    copyright_lbl.add_css_class("caption"); copyright_lbl.add_css_class("dim-label")
    copyright_lbl.set_halign(Gtk.Align.CENTER)
    outer.append(copyright_lbl)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()




_HISTORY_ICONS = {
    "installed":   ("package-x-generic-symbolic",        "status-installed"),
    "removed":     ("user-trash-symbolic",               "status-foreign"),
    "upgraded":    ("software-update-available-symbolic", "status-update"),
    "downgraded":  ("go-down-symbolic",                  "status-update"),
    "reinstalled": ("view-refresh-symbolic",             None),
}


def show_history_dialog(parent):
    dialog = Adw.Window()
    dialog.set_title(tr("Package History"))
    dialog.set_default_size(640, max(600, (parent.get_height() if parent is not None else 0) or 780))  # as tall as the main window
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    desc_lbl = Gtk.Label(label=tr(
        "Install, upgrade and removal events read from /var/log/pacman.log, newest first — for reference only, nothing here changes your system."))
    desc_lbl.set_wrap(True)
    desc_lbl.set_halign(Gtk.Align.START)
    desc_lbl.set_xalign(0)
    desc_lbl.add_css_class("caption"); desc_lbl.add_css_class("dim-label")
    desc_lbl.set_margin_start(12); desc_lbl.set_margin_end(12)
    desc_lbl.set_margin_top(10)
    outer.append(desc_lbl)

    search = Gtk.SearchEntry()
    search.set_placeholder_text(tr("Filter by package name…"))
    search.set_margin_start(12); search.set_margin_end(12)
    search.set_margin_top(8);    search.set_margin_bottom(6)
    outer.append(search)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    scroll.set_margin_start(12); scroll.set_margin_end(12); scroll.set_margin_bottom(12)
    listbox = Gtk.ListBox()
    listbox.set_selection_mode(Gtk.SelectionMode.NONE)
    listbox.add_css_class("boxed-list")
    scroll.set_child(listbox)
    outer.append(scroll)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    def render(entries):
        while listbox.get_first_child():
            listbox.remove(listbox.get_first_child())
        q = search.get_text().strip().lower()
        shown = 0
        for e in entries:
            if q and q not in e["name"].lower():
                continue
            row = Adw.ActionRow()
            row.set_title(e["name"])
            row.set_subtitle(f"{e['action']} · {e['version']} · {e['time']}")
            row.set_subtitle_selectable(True)
            icon_name, css = _HISTORY_ICONS.get(e["action"], ("package-x-generic-symbolic", None))
            icon = themed_image(icon_name, 18)
            icon.add_css_class("dim-label")
            row.add_prefix(icon)
            badge = Gtk.Label(label=e["action"].upper())
            badge.add_css_class("row-status-pill")
            if css:
                badge.add_css_class(css)
            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)
            listbox.append(row)
            shown += 1
        if shown == 0:
            empty = Adw.ActionRow()
            empty.set_title(tr("No matching entries"))
            listbox.append(empty)

    def worker():
        entries = get_pacman_history()
        def show():
            render(entries)
            search.connect("search-changed", lambda *_: render(entries))
            return False
        GLib.idle_add(show)

    threading.Thread(target=worker, daemon=True).start()


# ─── Downgrade from cache ─────────────────────────────────────────────────────

def show_downgrade_dialog(parent, pkg_name, run_terminal_fn, limit=None, title=None):
    """limit: zeigt nur die neuesten `limit` Versionen (None = alle).
    title: optionaler Fenstertitel (Standard: "Downgrade {pkg}")."""
    dialog = Adw.Window()
    dialog.set_title(title or tr("Downgrade {pkg}").format(pkg=pkg_name))
    dialog.set_default_size(560, 420)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    # Kandidaten im Hintergrund laden (Arch: Abfrage des Arch Linux Archive
    # = Netzwerkzugriff) — bis dahin ein Spinner.
    loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    loading.set_halign(Gtk.Align.CENTER); loading.set_valign(Gtk.Align.CENTER)
    loading.set_vexpand(True)
    sp = Gtk.Spinner(); sp.start(); sp.set_size_request(32, 32)
    loading.append(sp)
    loading.append(Gtk.Label(label=tr("Looking for available versions…")))
    outer.append(loading)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    def populate(candidates, foreign=False):
        for child in list(outer):
            outer.remove(child)
        if foreign:
            # AUR-Pakete: es gibt kein Versionsarchiv wie bei den offiziellen
            # Repositories — kurzer Hinweis, wie es hier stattdessen läuft.
            aur_note = make_info_box(
                "downgrade_aur", "AUR package: versions work differently", [
                    "The AUR has no version archive like the official repositories. "
                    "Pachul can only offer versions that are still on your disk: the "
                    "pacman cache and the build folders of your AUR helper "
                    "(yay, paru, pikaur, pachuli).",
                    "An older version is therefore only available if you built or "
                    "installed it earlier. After cleaning the helper's cache it is gone; "
                    "then you would have to check out an older PKGBUILD and build it yourself.",
                ])
            aur_note.set_margin_start(12); aur_note.set_margin_end(12)
            aur_note.set_margin_top(12)
            outer.append(aur_note)
        if limit:
            candidates = candidates[:limit]

        # Nur die installierte Version gefunden = keine Alternative.
        others = [c for c in candidates if not c.get("installed")]

        if not candidates:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("package-x-generic-symbolic", 72))
            status.set_title(tr("No Older Versions Found"))
            if distro.is_arch():
                desc = tr("No package files for {pkg} were found in /var/cache/pacman/pkg "
                          "or in the Arch Linux Archive.\nThe archive needs an internet "
                          "connection and only holds packages from the official repositories."
                          ).format(pkg=pkg_name)
            else:
                desc = tr("No older build of {pkg} is available — either nothing is cached "
                          "locally, or the configured repositories only carry the current "
                          "version.").format(pkg=pkg_name)
            status.set_description(desc)
            status.set_vexpand(True)
            outer.append(status)
            return

        if distro.is_arch():
            info_text = tr("{n} version(s) — pick one to install with pacman -U. "
                           "Versions not in the local cache are downloaded from the "
                           "Arch Linux Archive.").format(n=len(candidates))
        else:
            info_text = tr("{n} version(s) available — some may need to be downloaded").format(n=len(candidates))
        if not others:
            if distro.is_arch():
                info_text = tr("No other version of {pkg} was found — not in the local "
                               "cache, the AUR helper build caches or the Arch Linux "
                               "Archive (which only holds packages from the official "
                               "repositories, and needs an internet connection)."
                               ).format(pkg=pkg_name)
            else:
                info_text = tr("No other version of {pkg} is available.").format(pkg=pkg_name)
        outer.append(_pad(
            Gtk.Label(label=info_text, wrap=True, halign=Gtk.Align.START,
                      css_classes=["caption"]),
            start=16, end=16, top=12, bottom=8))

        scroll = _pad(_scrolled(_NEVER, _AUTO), start=12, end=12, bottom=12)
        scroll.set_vexpand(True)
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                              css_classes=["boxed-list"])

        for cand in candidates:
            kind = cand["kind"]
            if kind == "installed":
                detail = tr("Currently installed")
            elif kind == "file":
                detail = cand["source"]
            elif kind == "url":
                detail = tr("Download from Arch Linux Archive")
            else:
                detail = tr("Available from repository")
            cand_row = Adw.ActionRow(title=cand["version"], subtitle=detail)
            cand_row.set_subtitle_selectable(True)
            if cand.get("installed"):
                cand_row.add_suffix(Gtk.Label(
                    label=tr("INSTALLED"), valign=Gtk.Align.CENTER,
                    css_classes=["row-status-pill", "status-installed"]))
            pick_btn = _centered(_btn(tr("Install"), "suggested-action", "flat"))
            pick_btn.set_sensitive(not cand.get("installed"))

            def _downgrade_to(*_, c=cand):
                dialog.close()
                run_terminal_fn(
                    build_downgrade_cmd(pkg_name, c),
                    tr("Downgrade {pkg} to {ver}").format(pkg=pkg_name, ver=c["version"]))
            pick_btn.connect("clicked", _downgrade_to)
            cand_row.add_suffix(pick_btn)
            listbox.append(cand_row)

        outer.append(scroll)
        scroll.set_child(listbox)

    def worker():
        try:
            cands = get_downgrade_candidates(pkg_name)
        except Exception:
            cands = []
        try:
            foreign = is_foreign_package(pkg_name)
        except Exception:
            foreign = False
        GLib.idle_add(populate, cands, foreign)

    threading.Thread(target=worker, daemon=True).start()


# ─── Hold / unhold package dialog ──────────────────────────────────────────────

def show_hold_dialog(parent, pkg_name, currently_held, on_confirm, on_show_ignored=None):
    """currently_held=True means the click will *unhold* it; False means the
    click will add it to IgnorePkg (hold it)."""
    dialog = Adw.Dialog()
    if currently_held:
        dialog.set_title(tr("Unhold {pkg}").format(pkg=pkg_name))
    else:
        dialog.set_title(tr("Hold {pkg}").format(pkg=pkg_name))
    dialog.set_content_width(460)
    dialog.set_content_height(280)

    tv, hdr = _toolbar_with_header()
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    mechanism = tr("IgnorePkg in /etc/pacman.conf") if distro.is_arch() \
        else tr("apt-mark hold") if distro.is_debian() \
        else tr("a zypper package lock") if distro.is_suse() \
        else tr("the system's hold mechanism")
    if currently_held:
        info_group.set_title(tr("Allow {pkg} to Update Again").format(pkg=pkg_name))
        info_group.set_description(tr(
            "Removes {pkg} from {mechanism}. It will be "
            "included in system upgrades again from now on."
        ).format(pkg=pkg_name, mechanism=mechanism))
        action_label = tr("Unhold {pkg}").format(pkg=pkg_name)
    else:
        info_group.set_title(tr("Pin {pkg} to Its Current Version").format(pkg=pkg_name))
        info_group.set_description(tr(
            "Adds {pkg} to {mechanism}. Held packages are "
            "skipped by system upgrades — useful if a specific version needs "
            "to stay put for compatibility — and won't update again until "
            "you unhold them."
        ).format(pkg=pkg_name, mechanism=mechanism))
        action_label = tr("Hold {pkg}").format(pkg=pkg_name)
    outer.append(info_group)

    action_btn = Gtk.Button(label=action_label)
    action_btn.add_css_class("suggested-action")
    action_btn.set_halign(Gtk.Align.CENTER)

    def _do_action(*_):
        dialog.close()
        on_confirm()

    action_btn.connect("clicked", _do_action)
    outer.append(action_btn)

    # Shortcut to the overview of everything that is held — the two belong
    # together (this dialog changes one package, that one lists and undoes
    # them all). Only offered when there is something to look at.
    if on_show_ignored is not None:
        n_ignored = len(get_ignored_packages())
        if n_ignored:
            link_btn = Gtk.Button(
                label=tr("Show Ignored Packages ({n})…").format(n=n_ignored))
            link_btn.add_css_class("flat")
            link_btn.set_halign(Gtk.Align.CENTER)

            def _show_ignored(*_):
                dialog.close()
                on_show_ignored()

            link_btn.connect("clicked", _show_ignored)
            outer.append(link_btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Mark as dependency dialog ─────────────────────────────────────────────────

def show_mark_asdeps_dialog(parent, pkg_name, on_confirm):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Mark {name} as dependency").format(name=pkg_name))
    dialog.set_content_width(460)
    dialog.set_content_height(300)

    tv, hdr = _toolbar_with_header()
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = _pad(_vbox(16), start=16, end=16, top=16, bottom=24)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("What this does"))
    info_group.set_description(tr(
        "Only changes {pkg}'s install-reason metadata to \"installed as a "
        "dependency\" — the package itself is not touched or removed right "
        "now. The effect: once nothing else on your system depends on {pkg} "
        "anymore, it will show up as an orphan and can be cleaned up later "
        "via \"Find Orphans\"."
    ).format(pkg=pkg_name))
    outer.append(info_group)

    mark_btn = Gtk.Button(label=tr("Mark as Dependency"))
    mark_btn.add_css_class("suggested-action")
    mark_btn.set_halign(Gtk.Align.CENTER)

    def _do_mark(*_):
        dialog.close()
        on_confirm()

    mark_btn.connect("clicked", _do_mark)
    outer.append(mark_btn)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)
    tv.set_content(scroll)
    scroll.set_child(outer)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── PKGBUILD viewer (AUR) ────────────────────────────────────────────────────

def show_pkgbuild_dialog(parent, pkg_name, on_install):
    from backend import get_aur_info

    dialog = Adw.Window()
    dialog.set_title(tr("PKGBUILD — {pkg}").format(pkg=pkg_name))
    dialog.set_default_size(760, 600)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)

    aur_url = f"https://aur.archlinux.org/packages/{urllib.parse.quote(pkg_name, safe='')}"
    link_btn = Gtk.LinkButton(uri=aur_url)
    link_btn.set_child(themed_image("adw-external-link-symbolic", 18))
    link_btn.set_tooltip_text(tr("View on AUR (votes, comments, discussion)"))
    link_btn.add_css_class("flat")
    hdr.pack_start(link_btn)

    install_btn = Gtk.Button(label=tr("Install"))
    install_btn.add_css_class("suggested-action")
    install_btn.connect("clicked", lambda *_: (dialog.close(), on_install()))
    hdr.pack_end(install_btn)
    tv.add_top_bar(hdr)

    ood_banner = Adw.Banner()
    ood_banner.set_title(tr("This AUR package is flagged out-of-date by its maintainer"))
    ood_banner.set_revealed(False)
    tv.add_top_bar(ood_banner)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    desc_lbl = Gtk.Label(label=tr(
        "A PKGBUILD is the build script an AUR package uses to compile and install itself. AUR packages aren't reviewed by Arch, so it's worth skimming this before installing."))
    desc_lbl.set_wrap(True)
    desc_lbl.set_halign(Gtk.Align.START)
    desc_lbl.set_xalign(0)
    desc_lbl.add_css_class("caption"); desc_lbl.add_css_class("dim-label")
    desc_lbl.set_margin_start(16); desc_lbl.set_margin_end(16)
    desc_lbl.set_margin_top(10)
    outer.append(desc_lbl)

    # AUR metadata strip (votes / popularity / maintainer / last updated) —
    # placeholders until the async RPC call resolves.
    meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
    meta_box.set_margin_start(16); meta_box.set_margin_end(16)
    meta_box.set_margin_top(10);   meta_box.set_margin_bottom(6)

    def _stat(icon_name):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = themed_image(icon_name, 18)
        icon.add_css_class("dim-label")
        box.append(icon)
        lbl = Gtk.Label(label="—")
        lbl.add_css_class("caption")
        box.append(lbl)
        return box, lbl

    votes_box, votes_lbl = _stat("starred-symbolic")
    pop_box,   pop_lbl   = _stat("emblem-favorite-symbolic")
    maint_box, maint_lbl = _stat("avatar-default-symbolic")
    upd_box,   upd_lbl   = _stat("document-open-recent-symbolic")
    for b in (votes_box, pop_box, maint_box, upd_box):
        meta_box.append(b)
    outer.append(meta_box)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    label = Gtk.Label(label=tr("Loading PKGBUILD…"))
    label.set_selectable(True); label.set_wrap(True)
    label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    label.add_css_class("monospace"); label.add_css_class("caption")
    label.set_xalign(0); label.set_yalign(0)
    label.set_margin_start(12); label.set_margin_end(12)
    label.set_margin_top(8);    label.set_margin_bottom(8)
    scroll.set_child(label)
    outer.append(scroll)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    def render_meta(info):
        if info is None:
            maint_lbl.set_label(tr("AUR info unavailable"))
            votes_box.set_visible(False)
            pop_box.set_visible(False)
            upd_box.set_visible(False)
            return
        votes_lbl.set_label(str(info.get("NumVotes", "—")))
        pop_lbl.set_label(f"{info.get('Popularity', 0):.2f}")
        maint = info.get("Maintainer") or tr("Orphaned")
        maint_lbl.set_label(maint)
        last_mod = info.get("LastModified")
        if last_mod:
            upd_lbl.set_label(datetime.fromtimestamp(last_mod).strftime("%Y-%m-%d"))
        else:
            upd_lbl.set_label("—")
        ood_banner.set_revealed(bool(info.get("OutOfDate")))

    def worker():
        text = get_pkgbuild(pkg_name)
        GLib.idle_add(label.set_label, text)
        info = get_aur_info(pkg_name)
        GLib.idle_add(render_meta, info)

    threading.Thread(target=worker, daemon=True).start()


# ─── .pacnew / .pacsave manager ───────────────────────────────────────────────

def show_pacdiff_dialog(parent, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Config Files (.pacnew / .pacsave)") if distro.is_arch()
                      else tr("Config File Conflicts"))
    dialog.set_default_size(720, max(560, (parent.get_height() if parent is not None else 0) or 780))  # as tall as the main window
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    loading.set_halign(Gtk.Align.CENTER); loading.set_valign(Gtk.Align.CENTER)
    loading.set_vexpand(True)
    sp = Gtk.Spinner(); sp.start(); sp.set_size_request(32, 32)
    loading.append(sp)
    loading.append(Gtk.Label(label=tr("Scanning for .pacnew/.pacsave files…") if distro.is_arch()
                                    else tr("Scanning for config file conflicts…")))
    outer.append(loading)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    def render(files):
        outer.remove(loading)
        if not files:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 72))
            status.set_title(tr("Nothing to Merge"))
            status.set_description(tr("No .pacnew or .pacsave files were found.") if distro.is_arch()
                                    else tr("No config file conflicts were found."))
            status.set_vexpand(True)
            outer.append(status)
            return

        if distro.is_arch():
            pd_hint = make_info_box(
                "pacdiff",
                "What are .pacnew and .pacsave files?",
                ["If you changed a configuration file yourself and the package ships a new version of it, pacman does not overwrite your file. It saves the new default next to it as «.pacnew». If you remove a package whose configuration file you changed, your file is kept as «.pacsave».",
                 "«Use New (overwrite)» replaces your file with the new one — your own settings in it are lost. «Discard» only deletes the .pacnew file and keeps your version, which may then lack new options or contain outdated ones. Check the diff first."])
            pd_hint.set_margin_start(16); pd_hint.set_margin_end(16)
            pd_hint.set_margin_top(12)
            outer.append(pd_hint)

        info = Gtk.Label(label=(
            tr("{n} file(s) left behind by package updates. Review the diff, then keep the new version or discard it.").format(n=len(files))))
        info.add_css_class("caption"); info.set_wrap(True); info.set_halign(Gtk.Align.START)
        info.set_margin_start(16); info.set_margin_end(16)
        info.set_margin_top(12);   info.set_margin_bottom(8)
        outer.append(info)

        scroll = _scrolled(_NEVER, _AUTO)
        scroll.set_vexpand(True)
        scroll.set_margin_start(12); scroll.set_margin_end(12); scroll.set_margin_bottom(12)
        group = Adw.PreferencesGroup()

        for fdict in files:
            new, orig, kind = fdict["new"], fdict["orig"], fdict["kind"]
            exp = Adw.ExpanderRow()
            exp.set_title(orig)
            exp.set_subtitle(f"{kind} · {new}")

            diff_scroll = Gtk.ScrolledWindow()
            diff_scroll.set_min_content_height(160); diff_scroll.set_max_content_height(300)
            diff_lbl = Gtk.Label(label=tr("Loading diff…"))
            diff_lbl.set_selectable(True); diff_lbl.set_wrap(True)
            diff_lbl.set_wrap_mode(Pango.WrapMode.CHAR)
            diff_lbl.add_css_class("monospace"); diff_lbl.add_css_class("caption")
            diff_lbl.set_xalign(0); diff_lbl.set_yalign(0)
            diff_lbl.set_margin_start(12); diff_lbl.set_margin_end(12)
            diff_lbl.set_margin_top(6);    diff_lbl.set_margin_bottom(6)
            diff_scroll.set_child(diff_lbl)
            diff_row = Gtk.ListBoxRow(); diff_row.set_activatable(False)
            diff_row.set_child(diff_scroll)
            exp.add_row(diff_row)

            btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            btn_row.set_halign(Gtk.Align.END)
            btn_row.set_margin_start(12); btn_row.set_margin_end(12)
            btn_row.set_margin_top(6);    btn_row.set_margin_bottom(8)
            apply_btn = Gtk.Button(label=tr("Use New (overwrite)"))
            apply_btn.add_css_class("suggested-action")

            def _do_apply(*_, n=new, o=orig, e=exp):
                # Keep the dialog open so several files can be reviewed
                # and resolved one after another; just drop this file's
                # row once the move actually succeeds.
                run_terminal_fn(f"pkexec /usr/bin/mv {shlex.quote(n)} {shlex.quote(o)}",
                                 tr("Apply {name}").format(name=n),
                                 on_success=lambda e=e: group.remove(e),
                                 parent=dialog)
            apply_btn.connect("clicked", _do_apply)

            discard_btn = Gtk.Button(label=tr("Discard"))
            discard_btn.add_css_class("destructive-action"); discard_btn.add_css_class("flat")

            def _do_discard(*_, n=new, e=exp):
                run_terminal_fn(f"pkexec /usr/bin/rm {shlex.quote(n)}", tr("Remove {name} ").format(name=n),
                                 on_success=lambda e=e: group.remove(e),
                                 parent=dialog)
            discard_btn.connect("clicked", _do_discard)
            btn_row.append(discard_btn)
            btn_row.append(apply_btn)
            wrap_row = Gtk.ListBoxRow(); wrap_row.set_activatable(False)
            wrap_row.set_child(btn_row)
            exp.add_row(wrap_row)

            group.add(exp)

            def load_diff(lbl=diff_lbl, o=orig, n=new):
                text = get_file_diff(o, n)
                GLib.idle_add(lbl.set_label, text)
            threading.Thread(target=load_diff, daemon=True).start()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(group)
        scroll.set_child(box)
        outer.append(scroll)

    def worker():
        files = get_pacnew_files()
        GLib.idle_add(render, files)

    threading.Thread(target=worker, daemon=True).start()


# ─── External tool updaters ───────────────────────────────────────────────────

# Full catalog of every "More Update Sources" tool, shown in a help
# expander regardless of what's actually detected — so the person can see
# what Pachul is *able* to update, not just what it already found. Name
# strings match the ones used by the live rows so tr() resolves the same
# translation; most descriptions reuse an existing note string, a few are
# new and only used here.
_TOOL_HELP_ENTRIES = [
    ("Config Files (.pacnew / .pacsave)" if distro.is_arch() else "Config File Conflicts",
     "Review and merge configuration files left behind by package updates."),
    ("Firmware (fwupdmgr)",
     "Firmware updates for the mainboard, SSDs, and other devices via fwupd."),
    ("Rust Toolchains (rustup)", "Updates installed Rust toolchains."),
    ("Cargo (crates.io binaries)", "Updates binaries installed via cargo install."),
    ("pip (--user packages)", "Upgrades every outdated package installed with --user."),
    ("pipx", "Upgrades every pipx-installed application."),
    ("npm (global packages)", "Updates globally installed npm packages."),
    ("fnm (Fast Node Manager)", "Installs the latest Node.js LTS release via fnm."),
    ("nvm (Node Version Manager)",
     "Installs the latest Node.js LTS release and sets it as the default."),
    ("pyenv (Python Version Manager)",
     "Updates pyenv itself \u2014 install new Python versions separately with 'pyenv install'."),
    ("SDKMAN (Java/Kotlin/Gradle/Maven)",
     "Updates SDKMAN itself and its candidate index \u2014 not each installed SDK version."),
    ("Conda/Mamba (base environment)",
     "Updates the base environment only \u2014 other environments need updating separately."),
    ("TeX Live (tlmgr)", "Updates TeX Live packages."),
    ("GitHub CLI Extensions", "Updates all installed gh extensions."),
    ("Claude Code", "Updates the Claude Code CLI."),
    ("VS Code/VSCodium Extensions",
     "Reinstalls every extension at its latest Marketplace version."),
    ("Lensfun Camera/Lens Database",
     "Fetches the latest camera/lens calibration data used by darktable, digiKam, and similar apps."),
    ("uv (Python package/tool manager)",
     "Only works for the standalone uv installer \u2014 a pacman/AUR install is updated there instead."),
    ("Ollama", "Re-runs the official installer script to fetch the latest release."),
    ("ClamAV Virus Definitions", "Downloads the latest ClamAV signature database."),
    ("Docker/Podman Images", "Pulls the latest version of every locally tagged image."),
    ("Flatpak: Unused Runtimes",
     "Removes runtimes and extensions no installed app depends on anymore."),
    ("JetBrains PyCharm Plugins",
     "Updates installed plugins via the command line (installPlugins) \u2014 falls back to opening Toolbox/PyCharm."),
    ("Vim/Neovim Plugins", "Updates plugins managed by lazy.nvim, packer.nvim, or vim-plug."),
    ("tmux Plugins (TPM)", "Updates everything managed through the tmux Plugin Manager."),
    ("Zsh/Fish Frameworks", "Oh My Zsh, Zinit, Antigen, Sheldon, Fisher."),
    ("Dotfiles Git Repos", "Runs 'git pull' on detected config repos with a remote configured."),
    ("Nerd Fonts (getnf)", "Updates already-installed Nerd Fonts to their latest release."),
    ("tldr Pages", "Updates the local tldr page cache."),
    ("Nix / home-manager",
     "Updates Nix packages (nix-env) or applies your home-manager configuration."),
]


def show_ignored_packages_dialog(parent, run_terminal_fn):
    """Overview of every package currently held via IgnorePkg in
    /etc/pacman.conf — a single place to see and undo holds, instead of
    having to remember which packages were pinned and visit each one's
    detail panel individually."""
    dialog = Adw.Window()
    dialog.set_title(tr("Ignored Packages"))
    dialog.set_default_size(520, max(560, (parent.get_height() if parent is not None else 0) or 780))  # as tall as the main window
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)

    unignore_all_btn = Gtk.Button(label=tr("Unignore All"))
    unignore_all_btn.add_css_class("destructive-action")
    hdr.pack_end(unignore_all_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    def run_unignore(names):
        cmd = build_hold_cmd_bulk(names, False)
        if not cmd:
            return
        dialog.close()
        run_terminal_fn(cmd, tr("Unignore {n} packages").format(n=len(names)))

    def render():
        for child in list(outer):
            outer.remove(child)
        names = sorted(get_ignored_packages())
        unignore_all_btn.set_visible(bool(names))

        ig_paragraphs = ["Ignored (held) packages are skipped by system upgrades and stay at their current version until you unignore them.",
                         "Be careful: if a package stays old while the libraries it depends on are upgraded, it may stop working or block other updates. Hold packages only temporarily, for example until a known bug is fixed."]
        if distro.is_arch():
            ig_paragraphs.append("Arch does not officially support partial upgrades, so every ignored package is a small risk for the whole system.")
        ig_hint = make_info_box("ignored_packages", "What does “ignored” mean?", ig_paragraphs)
        ig_hint.set_margin_start(12); ig_hint.set_margin_end(12)
        ig_hint.set_margin_top(12)
        outer.append(ig_hint)

        if not names:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 64))
            status.set_title(tr("No Ignored Packages"))
            status.set_description(tr(
                "Held/ignored packages (skipped by system upgrades) show up here."))
            outer.append(status)
            return

        scroll = _pad(_scrolled(_NEVER, _AUTO), start=12, end=12, top=12, bottom=12)
        scroll.set_vexpand(True)
        group = Adw.PreferencesGroup()
        group.set_description(tr(
            "These packages are skipped by system upgrades until you unignore them."))
        for name in names:
            row = Adw.ActionRow()
            row.set_title(name)
            ver_btn = Gtk.Button(label=tr("Choose Version…"))
            ver_btn.set_valign(Gtk.Align.CENTER)
            ver_btn.set_tooltip_text(tr(
                "Install one of the last 5 versions. The package stays ignored."))
            ver_btn.connect(
                "clicked",
                lambda *_, n=name: show_downgrade_dialog(
                    dialog, n, run_terminal_fn, limit=5,
                    title=tr("Choose Version of {pkg}").format(pkg=n)))
            row.add_suffix(ver_btn)
            btn = Gtk.Button(label=tr("Unignore"))
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_, n=name: run_unignore([n]))
            row.add_suffix(btn)
            group.add(row)
        scroll.set_child(group)
        outer.append(scroll)

    unignore_all_btn.connect(
        "clicked", lambda *_: run_unignore(sorted(get_ignored_packages())))
    render()


def show_tool_updates_dialog(parent, run_terminal_fn):
    """Scan for developer/system tools that pacman/Flatpak/Snap don't cover
    (rustup, cargo, pip/pipx, npm, gh extensions, Claude Code, Lensfun, uv,
    Ollama, JetBrains PyCharm plugins, fwupd firmware, …) and let the user
    both run a one-off update now and opt individual tools into running
    automatically alongside every normal system upgrade."""
    dialog = Adw.Window()
    dialog.set_title(tr("More Update Sources"))
    # Same height as the main program window.
    _main_h = (parent.get_height() if parent is not None else 0) or 780
    dialog.set_default_size(760, max(620, _main_h))
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)

    update_btn = Gtk.Button(label=tr("Update Selected"))
    update_btn.add_css_class("suggested-action")
    update_btn.set_sensitive(False)
    hdr.pack_end(update_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    loading.set_halign(Gtk.Align.CENTER); loading.set_valign(Gtk.Align.CENTER)
    loading.set_vexpand(True)
    sp = Gtk.Spinner(); sp.start(); sp.set_size_request(32, 32)
    loading.append(sp)
    loading.append(Gtk.Label(label=tr("Scanning for update sources…")))
    outer.append(loading)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()

    checks = {}   # id -> (Gtk.CheckButton, update_cmd, display name)

    def _installed_badge():
        badge = Gtk.Label(label=tr("INSTALLED"))
        badge.add_css_class("row-status-pill")
        badge.add_css_class("status-installed")
        badge.set_valign(Gtk.Align.CENTER)
        return badge

    def _outdated_count_badge(n):
        # Reuses the same amber "update" pill style already used for
        # individual packages elsewhere in the app.
        badge = Gtk.Label(label=tr("{n} outdated").format(n=n))
        badge.add_css_class("row-status-pill")
        badge.add_css_class("status-update")
        badge.set_valign(Gtk.Align.CENTER)
        return badge

    def _refresh_update_btn(*_):
        update_btn.set_sensitive(any(cb.get_active() for cb, _cmd, _n in checks.values()))

    def _on_auto_toggled(cb, tool_id):
        current = set(get_setting("auto_update_tool_ids") or [])
        if cb.get_active():
            current.add(tool_id)
        else:
            current.discard(tool_id)
        save_settings({"auto_update_tool_ids": sorted(current)})
        _refresh_update_btn()

    def _on_update_clicked(*_):
        picked = [(name, cmd) for cb, cmd, name in checks.values()
                  if cb.get_active() and cmd]
        if not picked:
            return
        dialog.close()
        steps = " ; ".join(
            f'echo; echo "=== {name} ==="; echo; {cmd}' for name, cmd in picked)
        run_terminal_fn(steps, tr("Update Selected Tools"))
    update_btn.connect("clicked", _on_update_clicked)

    def _launch_and_close(cmd):
        dialog.close()
        try:
            subprocess_start(cmd)
        except Exception:
            pass

    def render(tools):
        outer.remove(loading)

        scroll = _pad(_scrolled(_NEVER, _AUTO), start=12, end=12, top=12, bottom=12)
        scroll.set_vexpand(True)
        box = _vbox(12)

        # Config files (.pacnew/.pacsave on Arch; .rpmnew/.dpkg-dist etc.
        # elsewhere) always gets its own entry point — it has its own
        # diff-review dialog rather than a plain update_cmd.
        cfg_group = Adw.PreferencesGroup()
        cfg_group.set_title(tr("Configuration"))
        cfg_row = Adw.ActionRow()
        cfg_row.set_title(tr("Config Files (.pacnew / .pacsave)") if distro.is_arch()
                           else tr("Config File Conflicts"))
        cfg_row.set_subtitle(tr("Review and merge configuration files left behind by package updates."))
        cfg_btn = Gtk.Button(label=tr("Review…"))
        cfg_btn.set_valign(Gtk.Align.CENTER)
        cfg_btn.connect("clicked", lambda *_: (dialog.close(), show_pacdiff_dialog(parent, run_terminal_fn)))
        cfg_row.add_suffix(cfg_btn)
        cfg_group.add(cfg_row)
        box.append(cfg_group)

        # Static help text — visible even when nothing is detected, so the
        # person can see what Pachul is *able* to update once installed.
        help_group = Adw.PreferencesGroup()
        help_row = Adw.ExpanderRow()
        help_row.set_title(tr("What can be updated here?"))
        help_row.set_subtitle(tr(
            "Full list of supported sources \u2014 shown once installed and detected."))
        for name, desc in _TOOL_HELP_ENTRIES:
            info_row = Adw.ActionRow()
            info_row.set_title(tr(name))
            info_row.set_subtitle(tr(desc))
            help_row.add_row(info_row)
        help_group.add(help_row)
        box.append(help_group)

        if tools:
            enabled_ids = set(get_setting("auto_update_tool_ids") or [])

            tools_group = Adw.PreferencesGroup()
            tools_group.set_title(tr("Detected Tools"))
            tools_group.set_description(tr(
                "Checked tools run automatically with every normal system upgrade from now on. "
                "\u201cUpdate Selected\u201d above also runs whatever is checked right now, once."))

            for t in tools:
                name = tr(t["name"])
                outdated_count = t.get("outdated_count")
                subtitle_parts = [p for p in (t.get("version") or "",
                                               tr(t["note"]) if t.get("note") else "") if p]
                if t.get("update_cmd"):
                    row = Adw.ExpanderRow() if t.get("detail") else Adw.ActionRow()
                    row.set_title(name)
                    if subtitle_parts:
                        row.set_subtitle(" \u2014 ".join(subtitle_parts))
                    cb = Gtk.CheckButton()
                    cb.set_valign(Gtk.Align.CENTER)
                    cb.set_active(t["id"] in enabled_ids)
                    cb.connect("toggled", _refresh_update_btn)
                    cb.connect("toggled", _on_auto_toggled, t["id"])
                    row.add_prefix(cb)
                    if outdated_count is not None:
                        row.add_suffix(_outdated_count_badge(outdated_count))
                    row.add_suffix(_installed_badge())
                    checks[t["id"]] = (cb, t["update_cmd"], name)

                    if t.get("detail"):
                        detail_lbl = Gtk.Label(label=t["detail"])
                        detail_lbl.set_selectable(True); detail_lbl.set_wrap(True)
                        detail_lbl.set_wrap_mode(Pango.WrapMode.CHAR)
                        detail_lbl.add_css_class("monospace"); detail_lbl.add_css_class("caption")
                        detail_lbl.set_xalign(0); detail_lbl.set_yalign(0)
                        detail_lbl.set_margin_start(12); detail_lbl.set_margin_end(12)
                        detail_lbl.set_margin_top(6);    detail_lbl.set_margin_bottom(6)
                        detail_row = Gtk.ListBoxRow(); detail_row.set_activatable(False)
                        detail_row.set_child(detail_lbl)
                        row.add_row(detail_row)
                    tools_group.add(row)
                elif t.get("launch_cmd"):
                    # No scriptable updater (e.g. JetBrains fallback) — offer
                    # to launch the tool; can't be part of the auto-run list.
                    row = Adw.ActionRow()
                    row.set_title(name)
                    if subtitle_parts:
                        row.set_subtitle(" \u2014 ".join(subtitle_parts))
                    row.add_suffix(_installed_badge())
                    open_btn = Gtk.Button(label=tr("Open"))
                    open_btn.set_valign(Gtk.Align.CENTER)
                    open_btn.connect("clicked", lambda *_, c=t["launch_cmd"]: _launch_and_close(c))
                    row.add_suffix(open_btn)
                    tools_group.add(row)

            box.append(tools_group)
        else:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 64))
            status.set_title(tr("No Additional Tools Found"))
            status.set_description(tr(
                "None of the supported external tools (rustup, cargo, pip/pipx, npm, "
                "gh extensions, Claude Code, Lensfun, uv, Ollama, JetBrains) were detected."))
            box.append(status)

        scroll.set_child(box)
        outer.append(scroll)

    def worker():
        tools = get_tool_updates()
        GLib.idle_add(render, tools)

    threading.Thread(target=worker, daemon=True).start()


def subprocess_start(cmd):
    """Launch a GUI tool detached from Pachul (no PTY/terminal needed)."""
    import subprocess
    subprocess.Popen(
        cmd, shell=True, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)


# ─── Preferences ──────────────────────────────────────────────────────────────

def show_preferences(parent, on_changed, app_dir=None, run_terminal_fn=None):
    from backend import (load_settings, save_settings, is_update_timer_enabled,
                         enable_update_timer, disable_update_timer, detect_snapshot_tool,
                         is_autostart_enabled, set_autostart_enabled, start_tray, stop_tray)
    s = load_settings()

    dlg = Adw.PreferencesWindow()
    dlg.set_title(tr("Preferences "))
    # Adw.PreferencesWindow (unlike Adw.PreferencesDialog) is a real,
    # freely resizable/movable top-level window — same reasoning as
    # show_repo_manager above. Default a bit more generously sized than
    # the implicit ~640×576 default.
    dlg.set_default_size(640, 780)
    dlg.set_resizable(True)
    dlg.set_transient_for(parent)
    dlg.set_modal(True)
    page = Adw.PreferencesPage()
    page.set_title(tr("General"))
    page.set_icon_name("preferences-system-symbolic")

    # AUR
    aur_group = Adw.PreferencesGroup()
    aur_group.set_title("AUR")

    helper_opts = ["auto", "pachuli", "yay", "paru", "pikaur", "none"]
    helper_row = Adw.ComboRow()
    helper_row.set_title(tr("AUR Helper"))
    helper_row.set_subtitle(tr("Used for AUR installs, updates and PKGBUILDs"))
    helper_row.set_model(Gtk.StringList.new(
        [tr("Auto-detect"), "pachuli", "yay", "paru", "pikaur", tr("None (pacman only)")]))
    cur = s.get("aur_helper", "auto")
    helper_row.set_selected(helper_opts.index(cur) if cur in helper_opts else 0)
    helper_row.connect("notify::selected", lambda r, _: (
        save_settings({"aur_helper": helper_opts[r.get_selected()]}), on_changed()))
    aur_group.add(helper_row)

    if not paru_installed():
        paru_row = Adw.ActionRow()
        paru_row.set_title(tr("paru not installed"))
        paru_row.set_subtitle(tr(
            "paru handles some AUR-vs-repo ambiguities (e.g. a package that "
            "exists both in a plain repo and on the AUR) more reliably than "
            "other helpers. Builds it from the AUR the same way any AUR "
            "package is built (needs base-devel and git)."))
        paru_btn = Gtk.Button(label=tr("Install paru"))
        paru_btn.add_css_class("suggested-action")
        paru_btn.set_valign(Gtk.Align.CENTER)

        def _on_install_paru(btn):
            if not run_terminal_fn:
                return
            btn.set_sensitive(False)
            # Parent the terminal dialog to this (still-open, modal)
            # Preferences window instead of the main window, so it stacks
            # correctly above it right from the first frame.
            run_terminal_fn(get_paru_bootstrap_cmd(), tr("Install paru"), parent=dlg)
        paru_btn.connect("clicked", _on_install_paru)
        paru_row.add_suffix(paru_btn)
        aur_group.add(paru_row)

    local_pachuli = local_pachuli_path(app_dir)
    if local_pachuli and pachuli_update_available(local_pachuli):
        pachuli_missing = not pachuli_installed()
        pachuli_row = Adw.ActionRow()
        if pachuli_missing:
            pachuli_row.set_title(tr("pachuli found but not installed"))
            pachuli_row.set_subtitle(tr(
                "A pachuli.py was found next to Pachul's own files but isn't "
                "on your PATH yet, so it can't be used as the AUR helper. "
                "Installs it as-is to /usr/local/bin — same place as the "
                "pachul launcher itself — no build step, just the one-time "
                "authentication any system-wide install needs."))
            pachuli_btn = Gtk.Button(label=tr("Install pachuli"))
        else:
            pachuli_row.set_title(tr("Newer pachuli available"))
            pachuli_row.set_subtitle(tr(
                "A newer pachuli.py ({new}) was found next to Pachul's own "
                "files than the one currently installed ({old}). Updating "
                "replaces /usr/local/bin/pachuli with this version — no "
                "build step, just the one-time authentication any "
                "system-wide install needs."
            ).format(new=local_pachuli_version(local_pachuli),
                     old=installed_pachuli_version()))
            pachuli_btn = Gtk.Button(label=tr("Update pachuli"))
        pachuli_btn.add_css_class("suggested-action")
        pachuli_btn.set_valign(Gtk.Align.CENTER)

        def _on_install_pachuli(btn):
            if not run_terminal_fn:
                return
            btn.set_sensitive(False)
            run_terminal_fn(get_pachuli_install_cmd(local_pachuli),
                             pachuli_btn.get_label(), parent=dlg)
        pachuli_btn.connect("clicked", _on_install_pachuli)
        pachuli_row.add_suffix(pachuli_btn)
        aur_group.add(pachuli_row)

    inc_row = Adw.SwitchRow()
    inc_row.set_title(tr("Include AUR in update checks"))
    inc_row.set_active(s.get("include_aur_updates", True))
    inc_row.connect("notify::active", lambda r, _: (
        save_settings({"include_aur_updates": r.get_active()}), on_changed()))
    aur_group.add(inc_row)
    if distro.is_arch():
        page.add(aur_group)

    # python3-apt (Debian only) — the native binding pkgmanager_native.py
    # uses for faster package info/listing/updates/repo detection. Without
    # it, Pachul still works fine via the plain apt/dpkg CLI, just a bit
    # slower, and the sidebar's repo categories stay empty for installed
    # packages (see pkgmanager.installed_repos()'s docstring).
    if distro.is_debian() and not pkgmanager.native.apt_available():
        apt_group = Adw.PreferencesGroup()
        apt_group.set_title(tr("Performance"))
        apt_row = Adw.ActionRow()
        apt_row.set_title(tr("python3-apt not installed"))
        apt_row.set_subtitle(tr(
            "Speeds up package info, listing and update checks, and lets "
            "the sidebar show repo categories for installed packages. "
            "Pachul works without it, just a bit slower. Restart Pachul "
            "after installing for it to take effect."))
        apt_btn = Gtk.Button(label=tr("Install python3-apt"))
        apt_btn.add_css_class("suggested-action")
        apt_btn.set_valign(Gtk.Align.CENTER)

        def _on_install_python3_apt(btn):
            if not run_terminal_fn:
                return
            btn.set_sensitive(False)
            run_terminal_fn(pkgmanager.python3_apt_install_cmd(),
                             tr("Install python3-apt"), parent=dlg)
        apt_btn.connect("clicked", _on_install_python3_apt)
        apt_row.add_suffix(apt_btn)
        apt_group.add(apt_row)
        page.add(apt_group)

    if distro.is_fedora() and not pkgmanager.native.dnf_available():
        dnf_group = Adw.PreferencesGroup()
        dnf_group.set_title(tr("Performance"))
        dnf_row = Adw.ActionRow()
        dnf_row.set_title(tr("python3-libdnf5 not installed"))
        dnf_row.set_subtitle(tr(
            "Speeds up package info, listing and update checks. "
            "Pachul works without it, just a bit slower. Restart Pachul "
            "after installing for it to take effect."))
        dnf_btn = Gtk.Button(label=tr("Install python3-libdnf5"))
        dnf_btn.add_css_class("suggested-action")
        dnf_btn.set_valign(Gtk.Align.CENTER)

        def _on_install_python3_libdnf5(btn):
            if not run_terminal_fn:
                return
            btn.set_sensitive(False)
            run_terminal_fn(pkgmanager.dnf_native_install_cmd(),
                             tr("Install python3-libdnf5"), parent=dlg)
        dnf_btn.connect("clicked", _on_install_python3_libdnf5)
        dnf_row.add_suffix(dnf_btn)
        dnf_group.add(dnf_row)
        page.add(dnf_group)

    # Additional package sources
    from backend import (flatpak_available, snap_available,
                          invalidate_flatpak_available_cache,
                          invalidate_snap_available_cache)
    extra_group = Adw.PreferencesGroup()
    extra_group.set_title(tr("Additional Package Sources"))
    extra_group.set_description(tr(
        "Show installed Flatpak/Snap apps alongside pacman packages, and include them when searching. "
        "Flatpak installs use --user (no password needed); Snap always needs one, since snapd requires root."))

    def _resolve_flatpak_install():
        return pkgmanager.flatpak_install_cmd(), tr("flatpak isn't installed")

    def _resolve_snap_install():
        if distro.is_arch():
            # snapd isn't in the official Arch repos (AUR-only), so this
            # goes through pachuli specifically — same -S/-g invocation as
            # every other AUR install in this app (see
            # aur_helper_install_cmd()'s pachuli branch) — rather than
            # whatever helper is currently configured in the AUR section
            # above, since pachuli is wanted here regardless.
            local_pachuli = local_pachuli_path(app_dir)
            if not (pachuli_installed() or local_pachuli):
                return None, tr(
                    "snap isn't installed (AUR-only on Arch — install pachuli above first)")
            cmd = aur_helper_install_cmd("pachuli", shlex.quote("snapd"), noconfirm=True)
            if not pachuli_installed():
                # pachuli isn't on PATH yet, but a local pachuli.py sits
                # next to Pachul's own files (see the AUR section above) —
                # bootstrap it first, then use it for snapd itself.
                cmd = f"{get_pachuli_install_cmd(local_pachuli)} && {cmd}"
            return cmd, tr("snap isn't installed (AUR-only on Arch — installs snapd via pachuli)")
        return pkgmanager.snap_install_cmd(), tr("snap isn't installed")

    def _pkgsource_row(title, setting_key, available_fn, invalidate_fn, resolve_install,
                        uninstall_cmd_fn, uninstall_heading, uninstall_body,
                        install_title, uninstall_title):
        """SwitchRow for an optional package source (Flatpak/Snap) with a
        single button that installs it when absent and uninstalls it when
        present, refreshing itself live once the terminal command
        succeeds — availability here is just a cheap `which` check cached
        in backend.py, so no restart or dialog reopen is needed."""
        row = Adw.SwitchRow()
        row.set_title(title)
        row.set_active(s.get(setting_key, False))
        row.connect("notify::active", lambda r, _: (
            save_settings({setting_key: r.get_active()}), on_changed()))

        btn = Gtk.Button()
        btn.set_valign(Gtk.Align.CENTER)
        row.add_suffix(btn)

        def _refresh():
            avail = available_fn()
            # Only disable the row's own switch when the package is absent
            # — NOT row.set_sensitive(), which would also grey out (and
            # make unclickable) the Install/Uninstall button added as a
            # suffix below, since GTK propagates a container's
            # insensitivity down to its children regardless of their own
            # sensitive property.
            switch_widget = row.get_activatable_widget()
            if switch_widget is not None:
                switch_widget.set_sensitive(avail)
            else:
                row.set_sensitive(avail)
            btn.remove_css_class("suggested-action")
            btn.remove_css_class("destructive-action")
            if avail:
                row.set_subtitle("")
                btn.set_label(tr("Uninstall"))
                btn.add_css_class("destructive-action")
                btn.set_sensitive(bool(uninstall_cmd_fn() and run_terminal_fn))
            else:
                cmd, subtitle = resolve_install()
                row.set_subtitle(subtitle)
                btn.set_label(tr("Install"))
                btn.add_css_class("suggested-action")
                btn.set_sensitive(bool(cmd and run_terminal_fn))

        def _after_success():
            invalidate_fn()
            _refresh()

        def _on_click(_btn):
            if not run_terminal_fn:
                return
            if available_fn():
                cmd = uninstall_cmd_fn()
                if not cmd:
                    return
                d = Adw.AlertDialog()
                d.set_heading(uninstall_heading)
                d.set_body(uninstall_body)
                d.add_response("cancel", tr("Cancel"))
                d.add_response("uninstall", tr("Uninstall"))
                d.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
                d.set_default_response("cancel")
                d.set_close_response("cancel")

                def _on_response(_d, r):
                    if r == "uninstall":
                        btn.set_sensitive(False)
                        run_terminal_fn(cmd, uninstall_title, parent=dlg,
                                         on_success=_after_success)
                d.connect("response", _on_response)
                d.present(dlg)
            else:
                cmd, _subtitle = resolve_install()
                if not cmd:
                    return
                btn.set_sensitive(False)
                run_terminal_fn(cmd, install_title, parent=dlg, on_success=_after_success)

        btn.connect("clicked", _on_click)
        _refresh()
        return row

    fp_row = _pkgsource_row(
        "Flatpak", "flatpak_enabled", flatpak_available, invalidate_flatpak_available_cache,
        _resolve_flatpak_install, pkgmanager.flatpak_uninstall_cmd,
        tr("Uninstall Flatpak?"),
        tr("Removes the flatpak package. Any Flatpak apps installed through "
           "it will stop working until it's reinstalled."),
        tr("Install Flatpak"), tr("Uninstall Flatpak"))
    extra_group.add(fp_row)

    sn_row = _pkgsource_row(
        "Snap", "snap_enabled", snap_available, invalidate_snap_available_cache,
        _resolve_snap_install, pkgmanager.snap_uninstall_cmd,
        tr("Uninstall Snap?"),
        tr("Removes snapd. Any Snap apps installed through it will stop "
           "working until it's reinstalled."),
        tr("Install Snap"), tr("Uninstall Snap"))
    extra_group.add(sn_row)
    page.add(extra_group)

    # Behaviour
    beh = Adw.PreferencesGroup()
    beh.set_title(tr("Behaviour"))

    def _switch(title, subtitle, key):
        row = Adw.SwitchRow()
        row.set_title(title)
        if subtitle:
            row.set_subtitle(subtitle)
        row.set_active(s.get(key, True))
        row.connect("notify::active", lambda r, _: save_settings({key: r.get_active()}))
        beh.add(row)

    _switch(tr("Confirm before removing packages"), None, "confirm_remove")
    _switch(tr("Check for updates on startup"), None, "check_updates_on_start")
    _switch(tr("Notify when updates are available"), None, "notify_updates")
    _switch(
        tr("Check for fixable system problems on startup"),
        tr("Scans for things like failed services, no active firewall, "
           "expired certificates or a broken package database, and lets "
           "you jump straight to the matching built-in tool. Read-only, "
           "no password needed."),
        "startup_healthcheck_enabled")

    snap_tool, snap_info = detect_snapshot_tool()
    snap_row = Adw.SwitchRow()
    snap_row.set_title(tr("Create snapshot before system upgrades"))
    if snap_tool == "timeshift":
        snap_row.set_subtitle(tr("Safety net via Timeshift — restore point before every upgrade"))
    elif snap_tool == "snapper":
        snap_row.set_subtitle(
            tr("Safety net via Snapper (config: {config})").format(config=snap_info))
    else:
        snap_row.set_subtitle(tr("No Timeshift or Snapper installation found"))
        snap_row.set_sensitive(False)
    snap_row.set_active(bool(snap_tool) and s.get("snapshot_before_upgrade", False))
    snap_row.connect("notify::active", lambda r, _: save_settings(
        {"snapshot_before_upgrade": r.get_active()}))
    beh.add(snap_row)
    page.add(beh)

    # Appearance (light / dark / follow system)
    look_group = Adw.PreferencesGroup()
    look_group.set_title(tr("Appearance"))
    look_group.set_description(tr("Changes apply immediately"))

    # Two switches cover all three states: "Follow System" on = system,
    # otherwise the "Dark Mode" switch decides between dark and light.
    style_mgr = Adw.StyleManager.get_default()
    cur_scheme = s.get("color_scheme", "system")
    _busy = [False]   # guards against the switches re-triggering each other

    follow_row = Adw.SwitchRow()
    follow_row.set_title(tr("Follow System"))
    dark_row = Adw.SwitchRow()
    dark_row.set_title(tr("Dark Mode"))

    follow_row.set_active(cur_scheme not in ("light", "dark"))
    dark_row.set_active(cur_scheme == "dark" if cur_scheme in ("light", "dark")
                        else style_mgr.get_dark())
    dark_row.set_sensitive(not follow_row.get_active())

    def _apply_scheme(value):
        # The app owns the action: it applies the scheme and saves it.
        app = parent.get_application()
        if app is not None:
            app.activate_action("color_scheme", GLib.Variant.new_string(value))

    def _on_follow_toggled(row, _p):
        if _busy[0]:
            return
        _busy[0] = True
        try:
            if row.get_active():
                _apply_scheme("system")
            else:
                # Keep what is on screen right now, but fixed from here on.
                _apply_scheme("dark" if style_mgr.get_dark() else "light")
            dark_row.set_sensitive(not row.get_active())
            dark_row.set_active(style_mgr.get_dark())
        finally:
            _busy[0] = False

    def _on_dark_toggled(row, _p):
        if _busy[0]:
            return
        _apply_scheme("dark" if row.get_active() else "light")

    follow_row.connect("notify::active", _on_follow_toggled)
    dark_row.connect("notify::active", _on_dark_toggled)
    look_group.add(follow_row)
    look_group.add(dark_row)
    page.add(look_group)

    # Language
    lang_group = Adw.PreferencesGroup()
    lang_group.set_title(tr("Language"))
    lang_group.set_description(tr("Changes apply immediately"))

    lang_opts = ["en", "de", "fr", "it"]
    lang_row = Adw.ComboRow()
    lang_row.set_title(tr("Language"))
    lang_row.set_model(Gtk.StringList.new([tr("English"), tr("German"), tr("French"), tr("Italian")]))
    cur_lang = get_language()
    lang_row.set_selected(lang_opts.index(cur_lang) if cur_lang in lang_opts else 0)
    lang_row.connect("notify::selected", lambda r, _: (
        set_language(lang_opts[r.get_selected()]), on_changed()))
    lang_group.add(lang_row)
    page.add(lang_group)

    # Tray icon autostart (per-user autostart entry — no root needed)
    tray_group = Adw.PreferencesGroup()
    tray_group.set_title(tr("Tray Icon"))
    tray_group.set_description(tr(
        "A persistent icon showing the pending update count"))

    autostart_row = Adw.SwitchRow()
    autostart_row.set_title(tr("Start automatically at login"))
    autostart_row.set_active(is_autostart_enabled())

    def _on_autostart_toggle(row, _):
        active = row.get_active()
        set_autostart_enabled(active, app_dir=app_dir)
        # Take effect right away instead of only at the next login.
        if active:
            start_tray(app_dir=app_dir)
        else:
            stop_tray()

    autostart_row.connect("notify::active", _on_autostart_toggle)
    tray_group.add(autostart_row)
    page.add(tray_group)

    # Background service (systemd --user timer)
    svc = Adw.PreferencesGroup()
    svc.set_title(tr("Background Service"))
    svc.set_description(tr("Check for updates and notify even when Pachul is closed, "
                        "via a systemd user timer"))

    interval_opts = ["hourly", "6h", "daily"]
    interval_row = Adw.ComboRow()
    interval_row.set_title(tr("Check interval"))
    interval_row.set_model(Gtk.StringList.new([tr("Hourly"), tr("Every 6 hours"), tr("Daily")]))
    cur_int = s.get("bg_check_interval", "daily")
    interval_row.set_selected(interval_opts.index(cur_int) if cur_int in interval_opts else 2)

    bg_row = Adw.SwitchRow()
    bg_row.set_title(tr("Run background update checks"))
    bg_row.set_active(is_update_timer_enabled())

    def _apply_timer():
        if bg_row.get_active():
            enable_update_timer(interval_opts[interval_row.get_selected()])
        else:
            disable_update_timer()

    bg_row.connect("notify::active", lambda r, _: _apply_timer())

    def _on_interval(r, _):
        save_settings({"bg_check_interval": interval_opts[r.get_selected()]})
        if bg_row.get_active():        # re-arm with the new interval
            enable_update_timer(interval_opts[r.get_selected()])

    interval_row.connect("notify::selected", _on_interval)
    svc.add(bg_row)
    svc.add(interval_row)
    page.add(svc)

    dlg.add(page)

    # AdwPreferencesPage centres its content in a 600px clamp, which left
    # much wider side margins than in the other dialogs. Let the content
    # use the full width instead (margins then come from the group itself).
    def _widen(w):
        c = w.get_first_child()
        while c is not None:
            if isinstance(c, Adw.Clamp):
                c.set_maximum_size(10000)
                c.set_tightening_threshold(10000)
                c.set_margin_start(4); c.set_margin_end(4)
            _widen(c)
            c = c.get_next_sibling()
    try:
        _widen(dlg)
    except Exception:
        pass
    dlg.present()


# ─── Help (functions overview + keyboard shortcuts) ───────────────────────────

def _shortcuts_list():
    """Built fresh on every call (not at module import) so it always
    reflects the currently active language, even if the user switches
    language in Preferences without restarting Pachul."""
    return [
        ("Ctrl+F",        tr("Focus search")),
        ("F5",            tr("Sync databases")),
        ("Ctrl+R",        tr("Refresh package list")),
        ("Ctrl+U",        tr("Check for updates")),
        ("Ctrl+T",        tr("Open tools")),
        ("Ctrl+D",        tr("Show/hide package details")),
        ("Ctrl+Shift+D",  tr("Toggle light/dark")),
        ("Ctrl+,",        tr("Preferences")),
        ("Ctrl+A",        tr("Select all packages (batch mode)")),
        ("Ctrl+Shift+A",  tr("Deselect all packages (batch mode)")),
        ("F1 / Ctrl+?",   tr("Help")),
        ("Ctrl+Q",        tr("Quit")),
    ]


def _help_function_groups(parent):
    """(group_title, [(name, description), …]) pairs for the Help window.

    Mirrors what the user actually sees: the main window and its sidebar,
    the Packages and Tools hubs (toolshub.py — same group names, same
    titles, same distro conditions), the Preferences and the terminal
    commands. The descriptions go further than the one-line hub texts and
    also cover what the per-dialog tooltips and info boxes say, so the
    help is never thinner than the UI it explains. `parent` is the main
    window, used to skip rows for features that don't apply on the current
    distro/setup (same conditions the hubs themselves use)."""
    hold_supported = getattr(parent, "_hold_supported", False)
    mark_supported = getattr(parent, "_mark_reason_supported", False)

    groups = []
    _rows = []
    _rows.append((tr("Window layout"),
         tr(
            "The window has three parts: the sidebar on the left (filters "
            "and counters), the package list in the middle (with the search"
            " bar) and the details of the selected package on the right. "
            "The header bar at the top gives access to Packages, Tools, "
            "Preferences, Help and About Pachul.")))
    _rows.append((tr("Header bar buttons"),
         tr(
            "Packages: sync, check for updates and actions for the selected"
            " packages. Tools (Ctrl+T): a searchable overview of all "
            "maintenance, repair and system tools — type a word and press "
            "Enter to open the first match. Preferences (Ctrl+,): all "
            "settings. Help (F1): this window. About Pachul: version, "
            "license and system info for bug reports.")))
    _rows.append((tr("Sidebar counters"),
         tr(
            "The three cards at the top of the sidebar show the total "
            "number of packages, how many of them come from the AUR, and "
            "how many updates are pending.")))
    _rows.append((tr("Status badges"),
         tr(
            "INSTALLED marks a package that is already on your system, "
            "UPDATE marks an installed package for which a newer version is"
            " available. Next to the name, small badges show the version, "
            "the repository it comes from and its architecture.")))
    _rows.append((tr("Administrator rights"),
         tr(
            "Actions that change the system (installing, removing, "
            "repairing …) ask for your password through pkexec and show "
            "their progress in a terminal window. Read-only checks and "
            "scans run without elevated rights; each tool's description "
            "says which is which.")))
    _rows.append((tr("Tooltips and info boxes"),
         tr(
            "Many rows in the tools carry a tooltip with the exact command "
            "that is run and what it affects — hold the mouse over a row to"
            " read it before pressing its button. Info boxes explain a "
            "topic once; those with a close button stay hidden after you "
            "dismiss them.")))
    groups.append((tr("Getting Started"), _rows))

    _rows = []
    _rows.append((tr("All Packages / Updates"),
         tr(
            "At the top of the sidebar: All Packages lists everything the "
            "package manager knows about; Updates lists only installed "
            "packages with a newer version available, with a count badge.")))
    _rows.append((tr("NEW section"),
         tr(
            "Everything that is not installed yet — either all at once (All"
            " New Packages) or per source such as core, extra, multilib, "
            "aur, Flatpak or Snap. A good place to discover software.")))
    _rows.append((tr("INSTALLED PACKAGES section"),
         tr(
            "Everything that is already on your system — all of it (All "
            "Installed Packages) or per origin. Every repository appears in"
            " both sections, each with its own package counter.")))
    _rows.append((tr("Search"),
         tr(
            "Type in the search bar (or press Ctrl+F) to filter the list "
            "that is currently shown by name or description. Pick All "
            "Packages in the sidebar first if you want to search "
            "everything.")))
    _rows.append((tr("Package details"),
         tr(
            "Click a package to see its description and actions on the "
            "right. The Info tab shows version, size, license, dependencies"
            " and more; the Files tab lists every file the installed "
            "package placed on your system, with a filter field and a file "
            "counter.")))
    _rows.append((tr("Dependencies"),
         tr(
            "Dependency entries in the Info tab are buttons: click one to "
            "look that package up. Long lists can be expanded.")))
    groups.append((tr("Browsing & Search"), _rows))

    _rows = []
    _rows.append((tr("Install"),
         tr(
            "Installs the selected package from its source — repository, "
            "AUR, Flatpak or Snap. A terminal window shows the progress, "
            "and your password is asked via pkexec when needed.")))
    _rows.append((tr("Uninstall"),
         tr(
            "Removes the selected package. If “Confirm before removing "
            "packages” is switched on in Preferences, you are asked first.")))
    _rows.append((tr("Reinstall"),
         tr(
            "Installs the same version of an installed package again — "
            "useful when some of its files are damaged or missing.")))
    _rows.append((tr("Downgrade"),
         tr(
            "Shows older versions of the package — those still in the "
            "package cache first, others from the repository if available —"
            " and installs the one you pick. Afterwards use Ignore Updates,"
            " or the next upgrade will install the newer version again.")))
    _rows.append((tr("Ignore Updates"),
         tr(
            "Pins a package at its current version so system upgrades skip "
            "it until you release it again (Arch: IgnorePkg in "
            "/etc/pacman.conf, Debian: apt-mark hold, openSUSE: package "
            "lock). Use it only temporarily — a package that falls behind "
            "its libraries can break or block other updates. All held "
            "packages are listed under Tools → Ignored Packages.")))
    _rows.append((tr("Batch mode"),
         tr(
            "Tick the checkboxes in the package list to select several "
            "packages. The right side then lists the selection, and the "
            "bottom bar offers Install, Uninstall and Ignore Updates for "
            "all of them at once. Ctrl+A selects everything currently "
            "visible, Ctrl+Shift+A clears the selection.")))
    _rows.append((tr("Bottom action bar"),
         tr(
            "Left: buttons to select or deselect all visible packages, then"
            " Install. Right: Uninstall and Ignore Updates. Upgrade All "
            "appears whenever updates are pending, and Check for Updates is"
            " available in the Updates view.")))
    groups.append((tr("Installing & Removing"), _rows))

    _rows = []
    _rows.append((tr("Sync Databases"),
         tr(
            "Downloads the latest package lists from the repositories "
            "without installing anything (F5). A confirmation dialog "
            "explains what happens first.")))
    _rows.append((tr("Check for Updates"),
         tr(
            "Syncs, then rebuilds the Updates list (Ctrl+U, or the button "
            "in the Updates view). AUR packages are included if enabled in "
            "Preferences.")))
    _rows.append((tr("Refresh List"),
         tr(
            "Reloads the view from what is already known locally, without "
            "contacting the repositories (Ctrl+R).")))
    _rows.append((tr("Upgrade All"),
         tr(
            "Installs every pending update in one go. If Timeshift or "
            "Snapper is found and enabled in Preferences, a restore point "
            "is created first. Flatpak and Snap updates are included when "
            "those sources are enabled.")))
    _rows.append((tr("Updates outside the package manager"),
         tr(
            "Developer and system tools that normal upgrades don't cover "
            "(rustup, npm, pip, firmware …) are handled under Tools → More "
            "Update Sources.")))
    _rows.append((tr("Notifications and background checks"),
         tr(
            "Preferences can check for updates on startup and notify you "
            "when some are available. With the tray icon and the background"
            " service, checks also run periodically while Pachul is closed.")))
    groups.append((tr("Updating"), _rows))

    _rows = []
    _rows.append((tr("Install Local Package…"),
         tr(
            "Installs a downloaded file: a built package (.pkg.tar.*, "
            "installed with pacman -U), a .tar.gz with a PKGBUILD (built "
            "with makepkg first), .deb, .rpm, .flatpak or .flatpakref. "
            "Pachul recognises the type, shows what it found and asks "
            "before installing. Only formats your distribution can handle "
            "work.")))
    _rows.append((tr("Manage Repositories…"),
         tr(
            "Arch: shows the active repositories and lets you edit "
            "pacman.conf (for example to enable multilib) — a wrong entry "
            "can stop updates from working, so change it with care. Other "
            "distributions: enable, disable or add software sources without"
            " editing files by hand.")))
    if distro.is_arch():
        _rows.append((tr("Find Fastest Mirrors…"),
         tr(
            "Tests the configured mirrors, ranks them by speed and lets you"
            " apply the fastest ones to make downloads quicker. Arch only —"
            " Fedora and openSUSE already pick the fastest mirror "
            "automatically. An info box in the dialog explains what mirrors"
            " are.")))
    _rows.append((tr("More Update Sources…"),
         tr(
            "Checks tools that normal upgrades don't cover: rustup, cargo, "
            "pip/pipx, npm, fnm/nvm, firmware (fwupd), Docker/Podman "
            "images, editor plugins and more. Update them once with “Update"
            " Selected”, or tick a tool to have it run automatically with "
            "every normal system upgrade. The “What can be updated here?” "
            "list shows everything supported, even if it isn't installed.")))
    _rows.append((tr("Import Package List…"),
         tr(
            "Installs packages from a list file you exported earlier. After"
            " you pick the file, the packages found in it are shown before "
            "anything is installed.")))
    _rows.append((tr("Export Package List…"),
         tr(
            "Saves the names of your explicitly installed programs to a "
            "text file — handy for setting up another machine the same way "
            "(use Import Package List there). You choose the target "
            "location first.")))
    groups.append((tr("Software & Sources"), _rows))

    _rows = []
    _rows.append((tr("Find Orphans"),
         tr(
            "Lists packages that were installed as dependencies and are no "
            "longer needed by anything, so you can remove them and free "
            "space. Check the list first: a program you use directly can "
            "show up here if it was marked as a dependency — use Mark "
            "Selected as Explicit to protect it.")))
    _rows.append((tr("Cache Cleaner"),
         tr(
            "Frees disk space used by downloaded package files. On Arch it "
            "keeps the 2 newest versions of each package (paccache), so a "
            "downgrade stays possible; installed packages are never "
            "touched. The dialog also offers general cleanup: shrink the "
            "systemd journal (500 MB / 4 weeks), delete thumbnails older "
            "than 30 days and empty the trash — emptying the trash cannot "
            "be undone.")))
    if distro.is_arch():
        _rows.append((tr("Config Files (.pacnew)…"),
         tr(
            "After an update, a package can leave a new default "
            "configuration file (.pacnew) or a backup (.pacsave) next to "
            "yours instead of overwriting your changes. This tool shows the"
            " differences and helps you merge or discard them.")))
    if not distro.is_arch():
        _rows.append((tr("Config File Conflicts…"),
         tr(
            "After an update, a package can leave a new default "
            "configuration file (such as .rpmnew or .dpkg-dist) next to "
            "yours instead of overwriting your changes. This tool shows the"
            " differences and helps you merge or discard them.")))
    if hold_supported:
        _rows.append((tr("Ignored Packages…"),
         tr(
            "Overview of all packages currently held back from upgrades, "
            "with an Unignore button for each (and Unignore All). An info "
            "box explains why holding packages for long is risky.")))
    _rows.append((tr("Package History…"),
         tr(
            "A log of past installs, upgrades and removals with dates — "
            "useful to find out what changed before something stopped "
            "working.")))
    _rows.append((tr("Find Package by File…"),
         tr(
            "Finds out which package a file belongs to: enter a file name "
            "or path. If the file database hasn't been synced yet, you are "
            "offered to do that first.")))
    groups.append((tr("Maintenance"), _rows))

    _rows = []
    if distro.is_arch():
        _rows.append((tr("Repair System (pacman)…"),
         tr(
            "Standard Maintenance: Force-Refresh & Full Upgrade (pacman "
            "-Syyu), a read-only database consistency check, and "
            "Reinitialize Keyring (helps with signature errors). Diagnose: "
            "search for packages with missing or modified files and "
            "reinstall the ones you pick. Last Resort: force-remove a "
            "broken package while ignoring dependencies — only when nothing"
            " else works.")))
    if distro.is_debian():
        _rows.append((tr("Repair System (apt/dpkg)…"),
         tr(
            "Standard Maintenance: update, upgrade & autoremove, fix broken"
            " dependencies, reconfigure all packages, fix missing or "
            "corrupt package files and clean the package cache. Diagnose "
            "lists broken or incomplete packages; Last Resort offers a "
            "forced removal.")))
    if distro.is_fedora():
        _rows.append((tr("Repair System (dnf/rpm)…"),
         tr(
            "Standard Maintenance: update, upgrade & autoremove, fix "
            "inconsistent package versions, rebuild the RPM database and "
            "clean the package cache. Diagnose shows broken or unsatisfied "
            "packages; Last Resort offers a forced removal.")))
    if distro.is_suse():
        _rows.append((tr("Repair System (zypper/rpm)…"),
         tr(
            "Standard Maintenance: update & upgrade, fix broken "
            "dependencies, rebuild the RPM database and clean the package "
            "cache. Diagnose shows broken or unsatisfied packages; Last "
            "Resort offers a forced removal.")))
    _rows.append((tr("Check Certificates…"),
         tr(
            "Domain check: connects live to the domains you enter (port "
            "443) and reports the days left until the certificate expires. "
            "Local check: read-only scan of the .pem files in "
            "/etc/ssl/certs. There is also a one-click reinstall of the CA "
            "certificate bundle for when HTTPS errors hit many unrelated "
            "sites at once.")))
    _rows.append((tr("Find Broken Symlinks…"),
         tr(
            "Scans /usr and /etc for symbolic links whose target no longer "
            "exists and sorts them into license leftovers (safe), archiso "
            "templates (expected) and everything else (review by hand). "
            "Scanning is read-only; the clean-up button deletes only the "
            "safe license leftovers and needs administrator rights.")))
    groups.append((tr("Repair"), _rows))

    _rows = []
    _rows.append((tr("System Info"),
         tr(
            "Operating system, kernel, hardware and package statistics in "
            "one place — a good thing to include in a bug report.")))
    _rows.append((tr("Services & Security…"),
         tr(
            "Shows failed systemd services (with a one-click reset for the "
            "usually harmless shadow.service), whether firewalld, fail2ban "
            "and apparmor are active, the UFW firewall (show rules, install"
            " and enable) and a check of the SSH root-login setting. Most "
            "checks are read-only.")))
    _rows.append((tr("Configuration Backup…"),
         tr(
            "Creates a compressed archive of important system configuration"
            " (fstab, hostname, bootloader, package-manager config …) plus "
            "a list of installed packages in the folder you choose "
            "(default: ~/pachul-backup). Only the last 5 archives are kept."
            " No administrator rights needed.")))
    groups.append((tr("System"), _rows))

    _rows = []
    if distro.is_arch():
        _rows.append((tr("View PKGBUILD (AUR)…"),
         tr(
            "Shows the build script of an AUR package before you install "
            "it, so you can see what it will do — always worth a look for "
            "unfamiliar packages. A link button in the viewer opens the "
            "package's AUR page (votes, comments, discussion).")))
    if hold_supported:
        _rows.append((tr("Hold / Unhold Selected"),
         tr(
            "Same as Ignore Updates, but from the Packages menu: toggles "
            "whether the selected packages are excluded from upgrades. A "
            "dialog explains the effect and asks for confirmation.")))
    if mark_supported:
        _rows.append((tr("Mark Selected as Explicit / as Dependency"),
         tr(
            "Changes how a package is tracked. Explicit means installed on "
            "purpose, so it is never offered for removal as an orphan; "
            "Dependency means installed for other packages, so it shows up "
            "in Find Orphans once nothing needs it any more. Only this "
            "label changes — nothing is installed or removed.")))
    groups.append((tr("Selected Packages"), _rows))

    _rows = []
    if distro.is_arch():
        _rows.append((tr("AUR Helper"),
         tr(
            "Chooses the program used for AUR installs, updates and "
            "PKGBUILDs: auto-detect, pachuli (Pachul's own minimal helper),"
            " yay, paru, pikaur or none (pacman only). A missing helper can"
            " be installed right from the Preferences. “Include AUR in "
            "update checks” also looks for newer AUR versions — switch it "
            "off if checks are slow or you don't use the AUR.")))
    if distro.is_debian() or distro.is_fedora():
        _rows.append((tr("Python bindings (apt / dnf)"),
         tr(
            "If python3-apt (Debian/Ubuntu) or python3-libdnf5 (Fedora) is "
            "missing, Preferences offers to install it. It speeds up "
            "package info, listing and update checks; Pachul works without "
            "it, just more slowly. Restart Pachul afterwards.")))
    _rows.append((tr("Additional Package Sources"),
         tr(
            "Switch Flatpak and Snap support on or off, and install or "
            "uninstall flatpak/snapd itself. When enabled, their apps "
            "appear in the sidebar and are included in searches and "
            "upgrades. Flatpak installs run without a password; Snap always"
            " needs one.")))
    _rows.append((tr("Confirmations and notifications"),
         tr(
            "“Confirm before removing packages” asks before anything is "
            "uninstalled. “Check for updates on startup” and “Notify when "
            "updates are available” control the automatic update check and "
            "its desktop notification.")))
    _rows.append((tr("Startup health check"),
         tr(
            "Scans at startup for fixable problems such as failed services "
            "or no active firewall. If something is found, a summary dialog"
            " lets you open the matching tool — nothing is changed "
            "automatically. Turn it off under Preferences → Behaviour.")))
    _rows.append((tr("Snapshot before upgrades"),
         tr(
            "If Timeshift or Snapper is installed, a restore point can be "
            "created before every system upgrade as a safety net.")))
    _rows.append((tr("Appearance"),
         tr(
            "“Follow System” uses the desktop's light or dark setting; "
            "“Dark Mode” switches manually (Ctrl+Shift+D toggles). Changes "
            "apply immediately.")))
    _rows.append((tr("Language"),
         tr(
            "Switches between English, German, French and Italian. The "
            "interface is rebuilt right away, no restart needed.")))
    _rows.append((tr("Tray icon and background service"),
         tr(
            "Start the tray icon automatically at login to see pending "
            "updates at a glance. The background service checks for updates"
            " through a systemd user timer (hourly, every 6 hours or "
            "daily), even when Pachul is closed.")))
    groups.append((tr("Preferences Explained"), _rows))

    groups.append((tr("Terminal Commands"), [
        (tr("pachul"),
         tr("Launches the main window — same as clicking the app icon.")),
        (tr("pachul-tray"),
         tr("Launches the standalone tray icon showing pending updates "
            "(requires libayatana-appindicator).")),
        (tr("pachul-uninstall"),
         tr("Removes a stray install.sh-based installation that's blocking "
            "an AUR package install/upgrade with a \"conflicting files\" "
            "error. Run as: sudo pachul-uninstall")),
        (tr("pachuli"),
         tr("Pachul's own minimal AUR helper, with a pacman/yay-style "
            "command-line syntax (an operation letter -S/-R/-Q/-Y plus "
            "stackable modifiers, e.g. -Ss, -Syu, -Rns). The commands "
            "below cover every combination it supports; running "
            "pachuli --help in a terminal prints the same reference.")),
        (tr("pachuli <suchbegriff ...>"),
         tr("Bare mode (like \"yay <term>\"): searches like -Ss and then "
            "asks which numbered results to install directly, e.g. "
            "\"1 3\", \"1-3\", \"^4\" or \"all\".")),
        (tr("pachuli -Ss <suchbegriff>"),
         tr("Searches both the AUR and the repositories for the given "
            "term and lists the matches.")),
        (tr("pachuli -S <paket ...>"),
         tr("Installs the given package(s), building AUR packages with "
            "makepkg as needed.")),
        (tr("pachuli -Su [paket ...]"),
         tr("Checks for and installs updates without refreshing the "
            "repository database first — repo packages are upgraded from "
            "the local cache only.")),
        (tr("pachuli -Syu"),
         tr("Like -Su, but also refreshes the repository database first "
            "(only if it looks outdated).")),
        (tr("pachuli -Syyu"),
         tr("Like -Syu, but forces a repository database refresh even if "
            "it looks up to date.")),
        (tr("pachuli -Si <paket ...>"),
         tr("Shows sync/AUR details for package(s) that aren't installed "
            "yet.")),
        (tr("pachuli -Sp <paket ...>"),
         tr("Fetches and prints a package's PKGBUILD without building or "
            "installing it.")),
        (tr("pachuli -Sc"),
         tr("Clears cached package files that are no longer the "
            "currently installed version.")),
        (tr("pachuli -Scc"),
         tr("Clears the entire package cache, including files for "
            "currently installed versions.")),
        (tr("pachuli -R <paket ...>"),
         tr("Removes the given package(s), keeping their configuration "
            "files.")),
        (tr("pachuli -Rns <paket ...>"),
         tr("Removes the given package(s) together with their "
            "configuration files.")),
        (tr("pachuli -Qu"),
         tr("Lists available updates as \"name old -> new\", the same "
            "way \"yay -Qu\" does.")),
        (tr("pachuli -Qu -q"),
         tr("Like -Qu, but prints only the bare count — handy for status "
            "lines or scripts.")),
        (tr("pachuli -Qi [paket ...]"),
         tr("Shows detailed info for installed packages, all of them if "
            "none are named, like \"pacman -Qi\".")),
        (tr("pachuli -Qii [paket ...]"),
         tr("Like -Qi, but also lists backup configuration files and "
            "whether they were modified.")),
        (tr("pachuli -Yc"),
         tr("Finds and removes orphaned dependencies — packages pulled "
            "in as dependencies that nothing needs anymore, like "
            "\"yay -Yc\".")),
        (tr("pachuli --help"),
         tr("Prints the full built-in command reference, including all "
            "modifiers and options.")),
        (tr("pachuli --version"),
         tr("Prints the installed pachuli version.")),
    ]))

    groups.append((tr("General"), [
        (tr("Help"),
         tr(
             "Opens this window (F1). Type in the search field at the top to"
             " find a topic quickly.")),
        (tr("About Pachul"),
         tr("Version, license and system info for bug reports.")),
    ]))

    return groups


def show_startup_healthcheck_dialog(parent, findings, activate_fn, rescan_fn=None):
    """Summary shown once, shortly after startup, when
    backend.startup_health_checks() found something — a short list of
    findings, each with a button that opens the existing repair/
    diagnostic dialog that can fix it (Services & Security, one of the
    four package-manager Repair dialogs, the Certificate Checker, or
    Broken Symlinks). This dialog itself never runs any fix — it's
    purely a router to tools that already exist elsewhere in the app.
    `activate_fn` is called with the finding's "action" string (a
    pachulWindow._on_show_* method name) when its button is clicked.
    Deliberately stays open after that click (only its own Close button
    or the window's own close button dismiss it) so several findings can
    be opened one after another without having to wait for the next
    startup — each click just relabels that row's button to "Opened" as
    a lightweight confirmation.

    The list can be refreshed in place, so a fix applied via one of those
    tools doesn't require restarting the app to see it drop off: a
    header-bar button lets the user re-run the checks manually, and the
    caller can also push a fresh scan in on its own (e.g. after a repair
    command finishes) by calling the returned `render` function with a
    new findings list — see pachulWindow._on_done /
    _healthcheck_render in window.py. `rescan_fn`, if given, is called
    as rescan_fn(on_done) when the user clicks that button; it must run
    backend.startup_health_checks() (in a background thread) and then
    call on_done(new_findings).

    Returns (dialog, render) — render(findings) rebuilds the list in
    place; callers should stop calling it once the dialog has closed."""
    dialog = Adw.Window()
    dialog.set_title(tr("Startup Check"))
    dialog.set_default_size(560, 480)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    refresh_btn = Gtk.Button()
    refresh_btn.set_child(themed_image("view-refresh-symbolic", 16))
    refresh_btn.set_tooltip_text(tr("Check again"))
    refresh_btn.set_visible(rescan_fn is not None)
    hdr.pack_end(refresh_btn)
    tv.add_top_bar(hdr)

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    content.set_margin_top(16);   content.set_margin_bottom(24)
    content.set_margin_start(16); content.set_margin_end(16)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    scroll.set_child(content)
    tv.set_content(scroll)
    dialog.set_content(tv)

    closed = [False]
    dialog.connect("close-request", lambda *_: closed.__setitem__(0, True) or False)

    def render(items):
        if closed[0]:
            return
        for child in list(content):
            content.remove(child)

        if not items:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 64))
            status.set_title(tr("Nothing Left to Fix"))
            status.set_description(tr(
                "A re-check no longer finds any of the earlier issues."))
            content.append(status)
            content.set_valign(Gtk.Align.CENTER)
            content.set_vexpand(True)
            return
        content.set_valign(Gtk.Align.FILL)
        content.set_vexpand(False)

        info = Adw.PreferencesGroup()
        info.set_description(tr(
            "{n} thing(s) found that a built-in tool can help with. Nothing "
            "has been changed — pick one to open the matching tool."
        ).format(n=len(items)) if len(items) != 1 else tr(
            "1 thing found that a built-in tool can help with. Nothing has "
            "been changed — open it below to fix it."))
        content.append(info)

        group = Adw.PreferencesGroup()
        group.set_title(tr("Findings"))
        for f in items:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(f["title"]))
            if f.get("detail"):
                row.set_subtitle(GLib.markup_escape_text(f["detail"]))
                row.set_subtitle_lines(0)
            btn = Gtk.Button(label=tr("Open"))
            btn.add_css_class("suggested-action")
            btn.set_valign(Gtk.Align.CENTER)

            def _open(_btn, action=f["action"], button=btn):
                activate_fn(action)
                # Stays open (see docstring) — just gives a small
                # confirmation that this row's tool was launched, so
                # re-clicking the same row by mistake is obvious rather
                # than silently reopening it.
                button.set_label(tr("Opened"))
                button.remove_css_class("suggested-action")
            btn.connect("clicked", _open)
            row.add_suffix(btn)
            group.add(row)
        content.append(group)

        hint = Gtk.Label(label=tr(
            "You can turn this check off anytime in Preferences → Behaviour."))
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        hint.set_xalign(0)
        content.append(hint)

    def _on_refresh_clicked(*_):
        if rescan_fn is None:
            return
        refresh_btn.set_sensitive(False)

        def _done(new_findings):
            refresh_btn.set_sensitive(True)
            render(new_findings)
        rescan_fn(_done)
    refresh_btn.connect("clicked", _on_refresh_clicked)

    render(findings)
    dialog.present()
    return dialog, render


def show_help_dialog(parent):
    dialog = Adw.Window()
    dialog.set_title(tr("Help"))
    # As tall as, and almost as wide as, the main window's startup size
    # (1240x780, see set_default_size() in window.py) rather than a small
    # fixed guess — falls back to that same startup size if the main
    # window hasn't been allocated a size yet for some reason.
    main_win_width  = parent.get_width()  or 1240
    main_win_height = parent.get_height() or 780
    dialog.set_default_size(max(480, main_win_width - 100), max(640, main_win_height))
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv, hdr = _toolbar_with_header()
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_end(close_btn)
    tv.add_top_bar(hdr)

    # Search field: the help is long now, so let people jump to a topic.
    search = Gtk.SearchEntry()
    search.set_placeholder_text(tr("Search help…"))
    search.set_hexpand(True)
    search_box = Gtk.Box()
    search_box.set_margin_start(12); search_box.set_margin_end(12)
    search_box.set_margin_top(6);    search_box.set_margin_bottom(6)
    search_box.append(search)
    tv.add_top_bar(search_box)

    scroll = _scrolled(_NEVER, _AUTO)
    scroll.set_vexpand(True)

    outer = _pad(_vbox(16), start=16, end=16, top=12, bottom=24)

    # (group_widget, [(row, haystack), …]) — kept for live filtering
    help_groups = []

    # ── Functions, grouped like the Packages / Tools hubs ──
    for title, rows in _help_function_groups(parent):
        if not rows:
            continue
        group = Adw.PreferencesGroup()
        # set_title/set_title/set_subtitle all parse their text as Pango
        # markup, so a literal "&" (e.g. "Browsing & Search") would
        # otherwise crash ("Failed to set text ... from markup") — escape
        # everything here defensively.
        group.set_title(GLib.markup_escape_text(title))
        entries = []
        for name, desc in rows:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(name))
            row.set_subtitle(GLib.markup_escape_text(desc))
            row.set_subtitle_lines(0)
            row.add_css_class("help-row")
            group.add(row)
            entries.append((row, f"{name} {desc} {title}".casefold()))
        help_groups.append((group, entries))
        outer.append(group)

    # ── Keyboard shortcuts, all in one place ──
    kb_group = Adw.PreferencesGroup()
    kb_title = tr("Keyboard Shortcuts")
    kb_group.set_title(kb_title)
    kb_entries = []
    for keys, desc in _shortcuts_list():
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(desc))
        kbd = Gtk.Label(label=keys)
        kbd.add_css_class("dim-label"); kbd.add_css_class("monospace")
        kbd.set_valign(Gtk.Align.CENTER)
        row.add_suffix(kbd)
        kb_group.add(row)
        kb_entries.append((row, f"{desc} {keys} {kb_title}".casefold()))
    help_groups.append((kb_group, kb_entries))
    outer.append(kb_group)

    empty = Adw.StatusPage()
    empty.set_icon_name("system-search-symbolic")
    empty.set_title(tr("No matching help topics"))
    empty.set_description(tr("Try a different search term."))
    empty.set_visible(False)
    outer.append(empty)

    def _filter(*_):
        q = search.get_text().strip().casefold()
        any_visible = False
        for group, entries in help_groups:
            shown = 0
            for row, hay in entries:
                vis = (not q) or all(w in hay for w in q.split())
                row.set_visible(vis)
                shown += vis
            group.set_visible(shown > 0)
            any_visible = any_visible or shown > 0
        empty.set_visible(not any_visible)

    search.connect("search-changed", _filter)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()
