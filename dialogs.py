"""
Pachul — dialogs.py
All modal tool dialogs:
  - TerminalDialog  : PTY-backed command runner with sudo password input
  - RepoManagerDialog : View/edit /etc/pacman.conf repositories
  - MirrorRaterDialog : rate-mirrors front end
  - OrphanFinderDialog: list and remove orphaned packages
  - SysInfoDialog     : system information overview
"""

import os
import pty
import re as _re
import shlex
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
from backend import (run_command, get_orphans, get_system_info,
                     get_pacman_history,
                     get_downgrade_candidates, build_downgrade_cmd,
                     get_pkgbuild, get_pacnew_files, get_file_diff, get_setting, save_settings,
                     files_db_available, search_file_owner, get_package_cache_size,
                     get_tool_updates, paru_installed, get_paru_bootstrap_cmd,
                     get_ignored_packages, build_hold_cmd_bulk)
from i18n import tr, get_language, set_language
from icons import themed_image, themed_paintable


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
    Open a PTY-backed terminal dialog that runs *cmd*.
    Calls on_success() (on the main thread) if the command exits with code 0.
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)

    title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    spinner   = Gtk.Spinner()
    spinner.start()
    spinner.set_size_request(16, 16)
    title_box.append(spinner)
    lbl = Gtk.Label(label=title)
    lbl.add_css_class("heading")
    title_box.append(lbl)
    hdr.set_title_widget(title_box)

    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("suggested-action")
    close_btn.set_sensitive(False)
    hdr.pack_end(close_btn)

    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("destructive-action")
    cancel_btn.add_css_class("flat")
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    gpg_banner = Adw.Banner()
    gpg_banner.set_revealed(False)
    tv.add_top_bar(gpg_banner)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    outer.set_margin_top(8);    outer.set_margin_bottom(12)
    outer.set_margin_start(12); outer.set_margin_end(12)

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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True); scroll.set_hexpand(True)
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.add_css_class("card")

    term_buf  = Gtk.TextBuffer()
    term_view = Gtk.TextView(buffer=term_buf)
    term_view.set_editable(False)
    term_view.set_cursor_visible(False)
    term_view.set_wrap_mode(Gtk.WrapMode.CHAR)
    term_view.add_css_class("terminal-view")
    term_view.set_monospace(True)

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
    scroll.set_child(term_view)
    outer.append(scroll)

    # Password / stdin input row
    input_frame = Gtk.Frame()
    input_frame.add_css_class("card")
    input_frame.set_margin_top(2)

    input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    input_box.set_margin_top(8);    input_box.set_margin_bottom(8)
    input_box.set_margin_start(10); input_box.set_margin_end(10)

    pw_icon = themed_image("dialog-password-symbolic", 18)
    pw_icon.add_css_class("dim-label")
    input_box.append(pw_icon)

    pw_entry = Gtk.Entry()
    pw_entry.set_hexpand(True)
    pw_entry.set_visibility(False)
    pw_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
    pw_entry.set_placeholder_text(tr("Password or input — press Enter to send"))
    input_box.append(pw_entry)

    send_btn = Gtk.Button(label=tr("Send"))
    send_btn.add_css_class("suggested-action")
    input_box.append(send_btn)

    input_frame.set_child(input_box)
    outer.append(input_frame)

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
    _master_fd = [None]
    _proc      = [None]
    _running   = [True]

    _ANSI = _re.compile(
        r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'   # OSC sequences: window title, hyperlinks,
                                                # and newer systemd/pam_systemd session-
                                                # boundary markers (e.g. "OSC 3008") that
                                                # sudo now emits — must come before the
                                                # generic ESC-fallback below, otherwise only
                                                # the ESC ']' gets eaten and the payload
                                                # (e.g. "3008;start=...;type=session") is
                                                # printed as literal text.
        r'|\x1b\[[0-9;?]*[ -/]*[@-~]'
        r'|\x1b[()][AB012]'
        r'|\x1b[^[]'
        r'|\x08'
    )

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
        mark = term_buf.get_insert()
        term_view.scroll_mark_onscreen(mark)
        adj = scroll.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper()))
        return False

    def send_input(*_):
        text = pw_entry.get_text()
        pw_entry.set_text("")
        if _master_fd[0] is not None:
            try:
                os.write(_master_fd[0], (text + "\n").encode())
                append_output(tr("(input sent)\n"))
            except OSError:
                pass

    pw_entry.connect("activate", send_input)
    send_btn.connect("clicked", send_input)

    def on_close_clicked(*_):
        close_btn.grab_focus()
        dialog.close()
    close_btn.connect("clicked", on_close_clicked)

    def do_cancel(*_):
        if _proc[0] is not None:
            try:
                os.killpg(os.getpgid(_proc[0].pid), __import__('signal').SIGTERM)
            except Exception:
                try:
                    _proc[0].terminate()
                except Exception:
                    pass
        cancel_btn.set_sensitive(False)
        cancel_btn.grab_focus()
        append_output(tr("\n— Cancelled —\n"))
    cancel_btn.connect("clicked", do_cancel)

    def on_done(code):
        _running[0] = False
        spinner.stop()
        cancel_btn.set_visible(False)
        close_btn.set_sensitive(True)
        close_btn.grab_focus()
        progress_box.set_visible(False)
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
            gpg_issue = _detect_gpg_issue(full_text)
            if gpg_issue is not None:
                key_id = gpg_issue

                def _do_gpg_fix(*_):
                    gpg_banner.set_revealed(False)
                    if distro.is_arch():
                        if key_id:
                            fix = (f"sudo -S pacman-key --recv-keys {key_id} && "
                                   f"sudo -S pacman-key --lsign-key {key_id}")
                        else:
                            fix = "sudo -S pacman -Sy --needed --noconfirm archlinux-keyring"
                    else:
                        fix = pkgmanager.gpg_fix_cmd(key_id or None)
                    if not fix:
                        return
                    dialog.close()
                    run_terminal_dialog(parent, f"{fix} && {cmd}", title,
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
                        fix = "sudo -S bash -c " + shlex.quote(inner_script)
                    else:
                        fix = pkgmanager.lock_fix_cmd()
                    if not fix:
                        return
                    dialog.close()
                    run_terminal_dialog(parent, f"{fix} && {cmd}", title,
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

    # ── PTY worker ────────────────────────────────────────────────────────────
    def worker():
        master_fd, slave_fd = pty.openpty()
        _master_fd[0] = master_fd

        try:
            ws = struct.pack('HHHH', 40, 120, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, ws)
        except Exception:
            pass

        safe_title = title.replace("'", "")
        wrapped = (
            f"printf '\\033[1m>>> {safe_title}\\033[0m\\n'; "
            f"echo; "
            f"{cmd}; "
            f"_ec=$?; "
            f"exit $_ec"
        )

        env = dict(os.environ)
        env['TERM'] = 'xterm-256color'
        env.pop('SUDO_ASKPASS', None)

        try:
            import subprocess
            proc = subprocess.Popen(
                ["sh", "-c", wrapped],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                close_fds=True, preexec_fn=os.setsid, env=env,
            )
            _proc[0] = proc
            os.close(slave_fd)

            partial = b""
            while True:
                try:
                    rlist, _, _ = select.select([master_fd], [], [], 0.05)
                except (ValueError, OSError):
                    break

                if rlist:
                    try:
                        chunk = os.read(master_fd, 8192)
                    except OSError:
                        break
                    if not chunk:
                        break
                    partial += chunk
                    try:
                        text = partial.decode('utf-8')
                        partial = b""
                    except UnicodeDecodeError:
                        for cut in range(len(partial), 0, -1):
                            try:
                                text = partial[:cut].decode('utf-8')
                                partial = partial[cut:]
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            text = partial.decode('latin-1')
                            partial = b""
                    GLib.idle_add(append_output, text)

                elif proc.poll() is not None:
                    try:
                        while True:
                            r2, _, _ = select.select([master_fd], [], [], 0.05)
                            if not r2:
                                break
                            chunk = os.read(master_fd, 8192)
                            if not chunk:
                                break
                            GLib.idle_add(append_output, chunk.decode('utf-8', errors='replace'))
                    except OSError:
                        pass
                    break

            proc.wait()
            code = proc.returncode

        except Exception as exc:
            GLib.idle_add(append_output, tr("\nInternal error: {err}\n").format(err=exc))
            code = 1

        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
            _master_fd[0] = None

        GLib.idle_add(on_done, code)

    threading.Thread(target=worker, daemon=True).start()


# ─── Sync databases dialog ─────────────────────────────────────────────────────

def show_sync_db_dialog(parent, on_confirm):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Sync Databases"))
    dialog.set_content_width(460)
    dialog.set_content_height(280)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_child(tv)
    dialog.present(parent)


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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)

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
    # non-interactive `sudo -S install ...` call, which the log-style
    # terminal panel handles just fine since it isn't interactive.
    save_btn = Gtk.Button(label=tr("Save"))
    save_btn.add_css_class("suggested-action")
    hdr.pack_end(save_btn)

    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    outer.set_margin_top(12);   outer.set_margin_bottom(16)
    outer.set_margin_start(16); outer.set_margin_end(16)

    repos_group = Adw.PreferencesGroup()
    repos_group.set_title(tr("Active Repositories"))
    repos_group.set_description(tr("Repositories currently enabled in /etc/pacman.conf"))

    out, code = run_command("pacman -Sl 2>/dev/null | awk '{print $1}' | sort -u")
    repos = [r for r in out.splitlines() if r.strip()] if (out and code == 0) else ["core", "extra", "multilib"]

    for repo in repos:
        row = Adw.ActionRow()
        row.set_title(repo)
        icon = themed_image("folder-symbolic", 18)
        icon.add_css_class("dim-label")
        row.add_prefix(icon)
        pkg_out, _ = run_command(f"pacman -Sl {repo} 2>/dev/null | wc -l")
        if pkg_out and pkg_out.strip().isdigit():
            count_lbl = Gtk.Label(label=tr("{n} pkgs").format(n=pkg_out.strip()))
            count_lbl.add_css_class("caption"); count_lbl.add_css_class("dim-label")
            row.add_suffix(count_lbl)
        repos_group.add(row)
    outer.append(repos_group)

    conf_group = Adw.PreferencesGroup()
    conf_group.set_title(tr("pacman.conf"))
    conf_group.set_description(tr("Edit directly below, then click Save. Make sure the syntax stays valid — pacman will refuse to run on a broken config."))
    # Let this group (and the editor inside it) actually grow into the extra
    # room from the larger dialog above, instead of staying pinned to a
    # small fixed height regardless of how big the dialog is.
    conf_group.set_vexpand(True)

    scroll = Gtk.ScrolledWindow()
    scroll.set_min_content_height(420)
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.add_css_class("card")

    conf_out, conf_read_code = run_command("cat /etc/pacman.conf 2>/dev/null")
    readable = bool(conf_out) and conf_read_code == 0
    buf = Gtk.TextBuffer()
    buf.set_text(conf_out if readable else tr("# /etc/pacman.conf not found or not readable"))
    conf_view = Gtk.TextView(buffer=buf)
    conf_view.set_editable(readable)
    conf_view.set_monospace(True)
    conf_view.set_wrap_mode(Gtk.WrapMode.NONE)
    conf_view.add_css_class("terminal-view")
    scroll.set_child(conf_view)
    conf_group.add(scroll)
    outer.append(conf_group)

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
            f"sudo -S install -m644 {shlex.quote(tmp_path)} /etc/pacman.conf",
            tr("Save pacman.conf"))

    save_btn.connect("clicked", _do_save)

    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroller.set_vexpand(True)
    scroller.set_child(outer)
    tv.set_content(scroller)
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real apt/dpkg maintenance commands with sudo — read what each "
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
        "sudo -S apt-get update -y && sudo -S apt-get dist-upgrade -y "
        "&& sudo -S apt-get autoremove -y",
    ))
    steps_group.add(_row(
        tr("Fix Broken Dependencies"),
        tr("Runs 'apt --fix-broken install' to resolve broken or half-installed "
           "dependencies."),
        tr("Run"),
        "sudo -S apt-get install --fix-broken -y",
    ))
    steps_group.add(_row(
        tr("Reconfigure All Packages"),
        tr("Runs 'dpkg --configure -a' to finish any package configuration that was "
           "interrupted."),
        tr("Run"),
        "sudo -S dpkg --configure -a",
    ))
    steps_group.add(_row(
        tr("Fix Missing/Corrupt Package Files"),
        tr("Refreshes the package index, then retries installing anything with "
           "missing or corrupt downloaded files."),
        tr("Run"),
        "sudo -S apt-get update -y && sudo -S apt-get install --fix-missing -y",
    ))
    steps_group.add(_row(
        tr("Clean Package Cache"),
        tr("Removes outdated .deb files from the local cache, then clears it "
           "completely."),
        tr("Run"),
        "sudo -S apt-get autoclean -y && sudo -S apt-get clean -y",
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
            f"sudo -S dpkg --remove --force-remove-reinstreq {shlex.quote(pkg_name)}",
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real dnf/rpm maintenance commands with sudo — read what each "
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
        "sudo -S dnf upgrade --refresh -y && sudo -S dnf autoremove -y",
    ))
    steps_group.add(_row(
        tr("Fix Inconsistent Package Versions"),
        tr("Runs 'dnf distro-sync' to bring installed packages back in line "
           "with what the repos currently offer, after an interrupted or "
           "partial upgrade left some at mismatched versions."),
        tr("Run"),
        "sudo -S dnf distro-sync -y",
    ))
    steps_group.add(_row(
        tr("Rebuild RPM Database"),
        tr("Runs 'rpm --rebuilddb' to rebuild a corrupted local RPM database."),
        tr("Run"),
        "sudo -S rpm --rebuilddb",
    ))
    steps_group.add(_row(
        tr("Clean Package Cache"),
        tr("Runs 'dnf clean all' to clear cached package files and metadata."),
        tr("Run"),
        "sudo -S dnf clean all",
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
            f"sudo -S rpm -e --nodeps {shlex.quote(pkg_name)}",
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real zypper/rpm maintenance commands with sudo — read what "
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
        "sudo -S zypper --non-interactive refresh "
        "&& sudo -S zypper --non-interactive update",
    ))
    steps_group.add(_row(
        tr("Fix Broken Dependencies"),
        tr("Runs 'zypper verify' — openSUSE's own solver run that finds and "
           "proposes fixes for broken or unsatisfied package dependencies."),
        tr("Run"),
        "sudo -S zypper --non-interactive verify",
    ))
    steps_group.add(_row(
        tr("Rebuild RPM Database"),
        tr("Runs 'rpm --rebuilddb' to rebuild a corrupted local RPM database."),
        tr("Run"),
        "sudo -S rpm --rebuilddb",
    ))
    steps_group.add(_row(
        tr("Clean Package Cache"),
        tr("Runs 'zypper clean --all' to clear cached package files and metadata."),
        tr("Run"),
        "sudo -S zypper clean --all",
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
            f"sudo -S rpm -e --nodeps {shlex.quote(pkg_name)}",
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    warn_banner = Adw.Banner()
    warn_banner.set_title(tr(
        "These run real pacman/pacman-key commands with sudo — read what each "
        "one does before running it, especially the last one."))
    warn_banner.set_revealed(True)
    outer.append(warn_banner)

    def _row(title, subtitle, button_label, cmd, suggested=True, on_success=None,
             on_success_with_window=None):
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
            run_terminal_fn(cmd, title, on_success=on_success,
                             on_success_with_window=on_success_with_window)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    steps_group = Adw.PreferencesGroup()
    steps_group.set_title(tr("Standard Maintenance"))

    steps_group.add(_row(
        tr("Force-Refresh & Full Upgrade"),
        tr("Runs 'pacman -Syyu' — forces a fresh download of all repo "
           "databases (ignoring their last-sync timestamps) before "
           "upgrading, useful when a mirror served stale or corrupt data."),
        tr("Run"),
        "sudo -S pacman -Syyu --noconfirm",
    ))
    steps_group.add(_row(
        tr("Check Package Database Consistency"),
        tr("Runs 'pacman -Dk' to check the local package database itself "
           "for internal inconsistencies (separate from checking individual "
           "installed files)."),
        tr("Run"),
        "pacman -Dk",
    ))
    steps_group.add(_row(
        tr("Reinitialize Keyring"),
        tr("Runs 'pacman-key --init' and '--populate archlinux' — a deeper "
           "fix than the automatic keyring banner elsewhere, for when "
           "signature errors persist after that lighter fix."),
        tr("Run"),
        "sudo -S pacman-key --init && sudo -S pacman-key --populate archlinux",
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
                cmd = f"{aur_helper} -S --noconfirm {quoted}"
            else:
                cmd = f"sudo -S pacman -S --noconfirm {quoted}"

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
        tr("Runs 'pacman -Qkk' with sudo (read-only, no changes are made). "
           "If any packages come back altered, you'll be asked right away "
           "which ones to repair."),
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
        # sudo matters just as much: plenty of package-owned files
        # (/etc/shadow, SSL private keys, sudoers, cups/pcp/webmin config,
        # nwfilter templates, ...) are only readable by root. Run as a
        # normal user, pacman can't even open them to hash them and
        # reports "failed to calculate SHA256 checksum" — which looks
        # exactly like corruption in this list but really just means "I
        # wasn't allowed to check." No amount of reinstalling ever clears
        # that specific warning; only checking as root does.
        #
        # Authenticate with a throwaway `sudo -S true` FIRST, completely
        # unredirected, so its "[sudo] password for ...:" prompt lands
        # straight on the visible terminal right away. The actual scan
        # runs as a separate `sudo -S` call afterwards — by then sudo's
        # credential cache is warm, so it proceeds without prompting
        # again, and its own output (not a hidden password prompt) is all
        # that ends up in the redirected file. Without this split, the
        # scan's ">file 2>&1" was also swallowing sudo's own -S prompt
        # (which sudo -S writes to stderr) into the file instead of
        # showing it, leaving the terminal looking stuck with nowhere to
        # type the password until something else eventually flushed it.
        "sudo -S true && { "
        "LC_ALL=C sudo pacman -Qk > " + _QKK_RAW_FILE + " 2>&1; "
        "OUT=$(grep -v '0 altered files' " + _QKK_RAW_FILE + "); "
        "if [ -n \"$OUT\" ]; then printf '%s\\n' \"$OUT\"; "
        "else echo " + shlex.quote(tr("No broken/incomplete packages found.")) + "; fi; }",
        on_success_with_window=_offer_repair_now,
    ))
    outer.append(diag_group)

    danger_group = Adw.PreferencesGroup()
    danger_group.set_title(tr("Last Resort"))
    danger_row = Adw.ActionRow()
    danger_row.set_title(tr("Force-Remove Broken Package"))
    danger_row.set_subtitle(tr(
        "Last resort for a single package pacman refuses to touch normally "
        "— removes it while ignoring dependency checks entirely. Only use "
        "this if the steps above didn't help, and only on the one package "
        "causing the problem."))
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
            f"sudo -S pacman -Rdd --noconfirm {shlex.quote(pkg_name)}",
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    # ── CA certificate bundle ──
    ca_group = Adw.PreferencesGroup()
    ca_group.set_title(tr("CA Certificate Bundle"))
    ca_cmd = pkgmanager.ca_certificates_refresh_cmd()
    ca_row = Adw.ActionRow()
    ca_row.set_title(GLib.markup_escape_text(tr("Reinstall CA Certificates & Rebuild Trust Store")))
    ca_row.set_subtitle(GLib.markup_escape_text(tr(
        "Reinstalls the ca-certificates package and regenerates the "
        "system's trust store. Useful if HTTPS connections fail with "
        "certificate-verification errors that aren't the remote site's "
        "fault.")))
    ca_row.set_subtitle_lines(0)
    if ca_cmd:
        ca_btn = Gtk.Button(label=tr("Run"))
        ca_btn.add_css_class("suggested-action")
        ca_btn.set_valign(Gtk.Align.CENTER)

        def _do_ca_refresh(*_):
            dialog.close()
            run_terminal_fn(ca_cmd, tr("Reinstall CA Certificates & Rebuild Trust Store"))
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
    domain_row.set_subtitle(GLib.markup_escape_text(tr("Comma-separated, e.g. example.com, mail.example.com")))
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
        dialog.close()
        run_terminal_fn(cmd, tr("Domain Certificate Expiry"))
    domain_btn.connect("clicked", _do_domain_check)
    domain_row.add_suffix(domain_btn)
    domain_group.add(domain_row)
    outer.append(domain_group)

    # ── Local certificates ──
    local_group = Adw.PreferencesGroup()
    local_group.set_title(tr("Local Certificates"))
    local_row = Adw.ActionRow()
    local_row.set_title(GLib.markup_escape_text(tr("Show Expired Local Certificates")))
    local_row.set_subtitle(GLib.markup_escape_text(tr(
        "Read-only: scans /etc/ssl/certs for .pem certificates that have "
        "already expired.")))
    local_row.set_subtitle_lines(0)
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
        dialog.close()
        run_terminal_fn(f"bash -c {shlex.quote(script)}", tr("Show Expired Local Certificates"))
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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
    scan_row.set_subtitle(GLib.markup_escape_text(tr(
        "Read-only: lists and classifies broken symlinks without deleting "
        "anything. No sudo needed.")))
    scan_row.set_subtitle_lines(0)
    scan_btn = Gtk.Button(label=tr("Scan"))
    scan_btn.set_valign(Gtk.Align.CENTER)

    def _do_scan(*_):
        dialog.close()
        run_terminal_fn(
            f"DO_DELETE=0 bash -c {shlex.quote(_classify_core)}",
            tr("Scan Only"))
    scan_btn.connect("clicked", _do_scan)
    scan_row.add_suffix(scan_btn)
    action_group.add(scan_row)

    clean_row = Adw.ActionRow()
    clean_row.set_title(GLib.markup_escape_text(tr("Scan & Remove Safe Ones")))
    clean_row.set_subtitle(GLib.markup_escape_text(tr(
        "Same scan, but also deletes the SAFE-category links (license "
        "leftovers only — archiso templates and anything else are still "
        "just listed, never touched). Needs sudo.")))
    clean_row.set_subtitle_lines(0)
    clean_btn2 = Gtk.Button(label=tr("Clean"))
    clean_btn2.add_css_class("suggested-action")
    clean_btn2.set_valign(Gtk.Align.CENTER)

    def _do_clean_symlinks(*_):
        dialog.close()
        run_terminal_fn(
            f"sudo -S env DO_DELETE=1 bash -c {shlex.quote(_classify_core)}",
            tr("Scan & Remove Safe Ones"))
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    ufw_enable_cmd = (
        "sudo -S ufw default deny incoming && sudo -S ufw default allow outgoing && "
        '(systemctl is-active --quiet sshd 2>/dev/null || systemctl is-active --quiet ssh 2>/dev/null) '
        "&& sudo -S ufw limit ssh; "
        "sudo -S ufw --force enable && sudo -S systemctl enable --now ufw && "
        "sudo -S ufw status verbose"
    )
    if ufw_active:
        ufw_group.add(_row(
            tr("Show Firewall Rules"),
            tr("UFW is active. Read-only: shows the current rule set."),
            tr("Show"),
            "sudo -S ufw status verbose",
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
        ufw_install_cmd_by_family = {
            "arch":   "sudo -S pacman -S --noconfirm ufw",
            "debian": "sudo -S apt-get install -y ufw",
            "fedora": "sudo -S dnf install -y ufw",
            "suse":   "sudo -S zypper --non-interactive install ufw",
        }
        install_cmd = ufw_install_cmd_by_family.get(pkgmanager.get_family())
        if install_cmd:
            ufw_group.add(_row(
                tr("Install & Enable Firewall"),
                tr("UFW isn't installed — your system currently has no "
                   "active firewall. Installs it, then enables it with "
                   "default rules (deny incoming, allow outgoing) and "
                   "rate-limited SSH if sshd is running."),
                tr("Install & Enable"),
                f"{install_cmd} && {ufw_enable_cmd}",
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("What this does"))
    info_group.set_description(tr(
        "Creates a compressed archive of your system's identity and boot "
        "configuration (fstab, hostname, bootloader, package-manager "
        "config, …) plus a plain-text list of explicitly-installed "
        "packages, so a fresh install can be brought back to a similar "
        "state. Only the last 5 archives are kept; older ones are removed "
        "automatically. No sudo needed — these files are normally "
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

def show_mirror_rater(parent, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Rate Mirrors"))
    dialog.set_default_size(600, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    _, code = run_command("which rate-mirrors 2>/dev/null")
    has_rate_mirrors = (code == 0)

    if has_rate_mirrors:
        options_group = Adw.PreferencesGroup()
        options_group.set_title(tr("Mirror Options"))
        options_group.set_description(tr(
            "rate-mirrors tests all Arch mirrors and shows you the result — nothing is written to /etc/pacman.d/mirrorlist until you review it and choose to save"
        ))

        country_row = Adw.ActionRow()
        country_row.set_title(tr("Countries"))
        country_row.set_subtitle(tr("Comma-separated country names, or blank for all"))
        country_entry = Gtk.Entry()
        country_entry.set_placeholder_text(tr("e.g. India, Germany, France"))
        country_entry.set_hexpand(True)
        country_entry.set_valign(Gtk.Align.CENTER)
        country_entry.set_width_chars(24)
        country_row.add_suffix(country_entry)
        options_group.add(country_row)

        sort_row = Adw.ActionRow()
        sort_row.set_title(tr("Sort by"))
        sort_row.set_subtitle(tr("How mirrors are ranked"))
        sort_store = Gtk.StringList()
        sort_options = [
            ("score_asc",  tr("Score ↑  (best reliability first)")),
            ("score_desc", tr("Score ↓  (worst reliability first)")),
            ("delay_asc",  tr("Delay ↑  (freshest mirrors first)")),
            ("delay_desc", tr("Delay ↓  (oldest mirrors first)")),
            ("random",     tr("Random   (shuffle before testing)")),
        ]
        for _, label in sort_options:
            sort_store.append(label)
        sort_drop = Gtk.DropDown(model=sort_store)
        sort_drop.set_selected(0)
        sort_drop.set_valign(Gtk.Align.CENTER)
        sort_row.add_suffix(sort_drop)
        options_group.add(sort_row)

        protocol_row = Adw.ActionRow()
        protocol_row.set_title(tr("HTTPS only"))
        protocol_row.set_subtitle(tr("Filter out plain HTTP mirrors"))
        https_switch = Gtk.Switch()
        https_switch.set_active(True)
        https_switch.set_valign(Gtk.Align.CENTER)
        protocol_row.add_suffix(https_switch)
        protocol_row.set_activatable_widget(https_switch)
        options_group.add(protocol_row)

        backup_row = Adw.ActionRow()
        backup_row.set_title(tr("Backup current mirrorlist"))
        backup_row.set_subtitle(tr("Saves existing list to mirrorlist-backup first"))
        backup_switch = Gtk.Switch()
        backup_switch.set_active(True)
        backup_switch.set_valign(Gtk.Align.CENTER)
        backup_row.add_suffix(backup_switch)
        backup_row.set_activatable_widget(backup_switch)
        options_group.add(backup_row)

        delay_row = Adw.ActionRow()
        delay_row.set_title(tr("Max mirror delay (hours)"))
        delay_row.set_subtitle(tr("Skip mirrors that are behind by more than this"))
        delay_spin = Gtk.SpinButton()
        delay_spin.set_range(1, 72); delay_spin.set_increments(1, 6); delay_spin.set_value(6)
        delay_spin.set_valign(Gtk.Align.CENTER)
        delay_row.add_suffix(delay_spin)
        options_group.add(delay_row)

        top_row = Adw.ActionRow()
        top_row.set_title(tr("Number of mirrors to keep"))
        top_row.set_subtitle(tr("0 = keep all ranked mirrors"))
        top_spin = Gtk.SpinButton()
        top_spin.set_range(0, 50); top_spin.set_increments(1, 5); top_spin.set_value(0)
        top_spin.set_valign(Gtk.Align.CENTER)
        top_row.add_suffix(top_spin)
        options_group.add(top_row)

        outer.append(options_group)

        run_btn = Gtk.Button(label=tr("Find Fastest Mirrors"))
        run_btn.add_css_class("suggested-action")
        run_btn.set_halign(Gtk.Align.CENTER)

        def on_run(*_):
            countries_raw = country_entry.get_text().strip()
            sort_idx      = sort_drop.get_selected()
            sort_key      = sort_options[sort_idx][0]
            https_only    = https_switch.get_active()
            backup        = backup_switch.get_active()
            max_delay     = int(delay_spin.get_value()) * 3600
            top_n         = int(top_spin.get_value())

            global_flags = []
            if https_only:
                global_flags.append("--protocol=https")
            if top_n > 0:
                global_flags.append(f"--top-mirrors={top_n}")
            if countries_raw:
                first = countries_raw.split(",")[0].strip()
                global_flags.append(f"--entry-country={shlex.quote(first)}")

            sub_flags = [f"--sort-mirrors-by={sort_key}", f"--max-delay={max_delay}"]
            gf = " ".join(global_flags)
            sf = " ".join(sub_flags)

            # Step 1: only test/rank mirrors and save the ranked list to a
            # plain, user-owned temp file. Nothing under /etc/pacman.d is
            # touched yet, and — since ranking doesn't need root at all —
            # this step doesn't even prompt for a password. The user only
            # sees a password prompt if/when they actually choose to save.
            fd, tmp_path = tempfile.mkstemp(prefix="pachul-mirrorlist-", suffix=".tmp")
            os.close(fd)
            cmd = (
                f'rate-mirrors {gf} --save={shlex.quote(tmp_path)} arch {sf} '
                f'&& echo "{tr("Done — review the result below")}"'
            )

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

            result_dialog = Adw.Window()
            result_dialog.set_title(tr("Mirror Ranking Result"))
            result_dialog.set_default_size(680, 600)
            result_dialog.set_resizable(True)
            result_dialog.set_transient_for(parent)
            result_dialog.set_modal(True)

            rtv = Adw.ToolbarView()
            rhdr = Adw.HeaderBar()
            rhdr.set_show_end_title_buttons(False)

            def _discard(*_):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                result_dialog.close()

            discard_btn = Gtk.Button(label=tr("Discard"))
            discard_btn.add_css_class("flat")
            discard_btn.connect("clicked", _discard)
            rhdr.pack_start(discard_btn)

            def _save(*_):
                result_dialog.close()
                if backup:
                    cmd2 = (
                        "sudo -S -v && "
                        "sudo mv /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist-backup && "
                        f"sudo install -m644 {shlex.quote(tmp_path)} /etc/pacman.d/mirrorlist && "
                        f'echo "{tr("Done — backup saved to /etc/pacman.d/mirrorlist-backup")}"'
                    )
                else:
                    cmd2 = (
                        "sudo -S -v && "
                        f"sudo install -m644 {shlex.quote(tmp_path)} /etc/pacman.d/mirrorlist && "
                        f'echo "{tr("Done — /etc/pacman.d/mirrorlist updated")}"'
                    )

                def _cleanup():
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                run_terminal_fn(cmd2, tr("Save Mirrorlist"), on_success=_cleanup)

            save_btn = Gtk.Button(label=tr("Save as New Mirrorlist"))
            save_btn.add_css_class("suggested-action")
            save_btn.connect("clicked", _save)
            rhdr.pack_end(save_btn)
            rtv.add_top_bar(rhdr)

            router_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            router_outer.set_margin_top(12);   router_outer.set_margin_bottom(16)
            router_outer.set_margin_start(16); router_outer.set_margin_end(16)

            info_lbl = Gtk.Label(
                label=tr("{n} mirrors found — review below, then choose whether to save.").format(n=server_count))
            info_lbl.set_halign(Gtk.Align.START)
            info_lbl.add_css_class("dim-label")
            router_outer.append(info_lbl)

            rscroll = Gtk.ScrolledWindow()
            rscroll.set_vexpand(True)
            rscroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            rscroll.add_css_class("card")
            rbuf = Gtk.TextBuffer()
            rbuf.set_text(content or tr("# No output captured"))
            rview = Gtk.TextView(buffer=rbuf)
            rview.set_editable(False); rview.set_monospace(True)
            rview.set_wrap_mode(Gtk.WrapMode.NONE)
            rview.add_css_class("terminal-view")
            rscroll.set_child(rview)
            router_outer.append(rscroll)

            rtv.set_content(router_outer)
            result_dialog.set_content(rtv)
            result_dialog.present()

        run_btn.connect("clicked", on_run)
        outer.append(run_btn)

        preview_lbl = Gtk.Label()
        preview_lbl.add_css_class("caption"); preview_lbl.add_css_class("dim-label")
        preview_lbl.set_wrap(True); preview_lbl.set_wrap_mode(Pango.WrapMode.CHAR)
        preview_lbl.set_selectable(True); preview_lbl.set_halign(Gtk.Align.CENTER)

        def update_preview(*_):
            countries_raw = country_entry.get_text().strip()
            sort_idx  = sort_drop.get_selected()
            sort_key  = sort_options[sort_idx][0]
            https_only = https_switch.get_active()
            max_delay = int(delay_spin.get_value()) * 3600
            top_n     = int(top_spin.get_value())
            gflags = []
            if https_only: gflags.append("--protocol=https")
            if top_n > 0:  gflags.append(f"--top-mirrors={top_n}")
            if countries_raw:
                first = countries_raw.split(",")[0].strip()
                gflags.append(f"--entry-country={shlex.quote(first)}")
            sflags = [f"--sort-mirrors-by={sort_key}", f"--max-delay={max_delay}"]
            preview_lbl.set_label(
                f"rate-mirrors {' '.join(gflags)} arch {' '.join(sflags)} | sudo tee /etc/pacman.d/mirrorlist"
            )

        country_entry.connect("changed", update_preview)
        sort_drop.connect("notify::selected", update_preview)
        https_switch.connect("notify::active", update_preview)
        delay_spin.connect("value-changed", update_preview)
        top_spin.connect("value-changed", update_preview)
        update_preview()
        outer.append(preview_lbl)

    else:
        status = Adw.StatusPage()
        status.set_paintable(themed_paintable("network-transmit-receive-symbolic", 72))
        status.set_title(tr("rate-mirrors not installed"))
        status.set_description(tr(
            "rate-mirrors uses geo-aware routing to benchmark\n"
            "all Arch mirrors and pick the fastest ones."
        ))
        install_btn = Gtk.Button(label=tr("Install rate-mirrors"))
        install_btn.add_css_class("suggested-action")
        install_btn.set_halign(Gtk.Align.CENTER)
        install_btn.connect("clicked", lambda *_: (
            dialog.close(),
            run_terminal_fn("sudo -S pacman -S --noconfirm rate-mirrors", tr("Install rate-mirrors"))
        ))
        status.set_child(install_btn)
        outer.append(status)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()


# ─── Orphan finder dialog ─────────────────────────────────────────────────────

def show_orphan_finder(parent, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Orphaned Packages"))
    dialog.set_default_size(560, 460)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    outer.set_margin_top(0); outer.set_margin_bottom(0)

    orphans = get_orphans()

    if not orphans:
        status = Adw.StatusPage()
        status.set_paintable(themed_paintable("emblem-ok-symbolic", 72))
        status.set_title(tr("No Orphans Found"))
        status.set_description(tr("Your system has no orphaned packages."))
        status.set_vexpand(True)
        outer.append(status)
    else:
        info_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        info_bar.set_margin_start(16); info_bar.set_margin_end(16)
        info_bar.set_margin_top(12);   info_bar.set_margin_bottom(8)
        info_icon = themed_image("dialog-warning-symbolic", 18)
        info_bar.append(info_icon)
        info_lbl = Gtk.Label(
            label=tr("{n} orphaned package(s) — pulled in automatically as a dependency at some point, but nothing on your system requires them anymore. Safe to remove, or leave them if you might need them again.").format(n=len(orphans))
        )
        info_lbl.add_css_class("caption")
        info_lbl.set_hexpand(True); info_lbl.set_halign(Gtk.Align.START); info_lbl.set_wrap(True)
        info_bar.append(info_lbl)
        outer.append(info_bar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_start(12); scroll.set_margin_end(12)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")

        for o in orphans:
            row = Adw.ActionRow()
            row.set_title(o["name"]); row.set_subtitle(o["version"])
            icon = themed_image("package-x-generic-symbolic", 18)
            icon.add_css_class("dim-label")
            row.add_prefix(icon)
            rm_btn = Gtk.Button(label=tr("Remove"))
            rm_btn.add_css_class("destructive-action"); rm_btn.add_css_class("flat")
            rm_btn.set_valign(Gtk.Align.CENTER)
            name = o["name"]
            rm_btn.connect("clicked", lambda *_, n=name: (
                dialog.close(),
                run_terminal_fn(
                    f"sudo -S pacman -R --noconfirm {shlex.quote(n)}" if distro.is_arch()
                    else pkgmanager.remove_cmd([n]),
                    tr("Remove {name} ").format(name=n))
            ))
            row.add_suffix(rm_btn)
            listbox.append(row)

        scroll.set_child(listbox)
        outer.append(scroll)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(12); btn_box.set_margin_bottom(16)
        names = " ".join(shlex.quote(o["name"]) for o in orphans)
        name_list = [o["name"] for o in orphans]
        remove_all_btn = Gtk.Button(label=tr("Remove All {n} Orphans").format(n=len(orphans)))
        remove_all_btn.add_css_class("destructive-action")
        remove_all_btn.connect("clicked", lambda *_: (
            dialog.close(),
            run_terminal_fn(
                f"sudo -S pacman -Rns --noconfirm {names}" if distro.is_arch()
                else pkgmanager.remove_cmd(name_list, purge=distro.is_debian()),
                tr("Remove All Orphans"))
        ))
        btn_box.append(remove_all_btn)
        outer.append(btn_box)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()


# ─── Clean cache dialog ────────────────────────────────────────────────────────

def show_clean_cache_dialog(parent, run_terminal_fn):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Clean Cache"))
    dialog.set_content_width(520)
    dialog.set_content_height(620)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Cancel"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    _, code = run_command("which paccache 2>/dev/null")
    has_paccache = distro.is_arch() and (code == 0)

    cache_dir_by_family = {
        "debian": "/var/cache/apt/archives",
        "fedora": "/var/cache/dnf",
        "suse":   "/var/cache/zypp/packages",
    }
    cache_path = "/var/cache/pacman/pkg" if distro.is_arch() \
        else cache_dir_by_family.get(distro.get_family(), "N/A")

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
        dialog.close()
        if distro.is_arch():
            cmd = "sudo -S -v && { paccache -rk2 2>/dev/null || sudo pacman -Sc --noconfirm; }"
        else:
            cmd = pkgmanager.clean_cache_cmd() or "true"
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
        row.set_subtitle(GLib.markup_escape_text(subtitle))
        row.set_subtitle_lines(0)
        btn = Gtk.Button(label=button_label)
        if suggested:
            btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)

        def _run(*_):
            dialog.close()
            run_terminal_fn(cmd, cmd_title)
        btn.connect("clicked", _run)
        row.add_suffix(btn)
        return row

    sys_group.add(_sys_row(
        tr("Clean systemd Journal"),
        tr("Shrinks the journal to 500 MB and removes entries older than 4 weeks."),
        tr("Run"),
        "sudo -S journalctl --vacuum-size=500M && sudo -S journalctl --vacuum-time=4weeks",
        tr("Clean systemd Journal"),
    ))
    sys_group.add(_sys_row(
        tr("Remove Old Thumbnail Previews"),
        tr("Deletes cached thumbnail images in ~/.cache/thumbnails older than "
           "30 days. No sudo needed — this only touches your own cache."),
        tr("Run"),
        'bash -c \'if [ -d "$HOME/.cache/thumbnails" ]; then '
        'find "$HOME/.cache/thumbnails" -type f -atime +30 -delete && '
        'echo "' + tr("Done.") + '"; else echo "' +
        tr("No thumbnail cache found.") + '"; fi\'',
        tr("Remove Old Thumbnail Previews"),
    ))
    sys_group.add(_sys_row(
        tr("Empty Trash"),
        tr("Permanently empties your desktop trash/recycle bin (via 'gio "
           "trash --empty'). No sudo needed."),
        tr("Run"),
        'bash -c \'if command -v gio >/dev/null 2>&1; then gio trash --empty && '
        'echo "' + tr("Done.") + '"; else echo "' +
        tr("gio not found — nothing to do.") + '"; fi\'',
        tr("Empty Trash"),
    ))
    outer.append(sys_group)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Import package list dialog ────────────────────────────────────────────────

def show_import_pkgs_intro(parent, helper, on_choose_file):
    """Explanation shown *before* the file picker opens, so the user knows
    what will happen before they even pick a file."""
    dialog = Adw.Dialog()
    dialog.set_title(tr("Import Package List"))
    dialog.set_content_width(480)
    dialog.set_content_height(360)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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
            cmd = f"{helper} -S --needed --noconfirm {quoted}"
        elif distro.is_arch():
            quoted = " ".join(shlex.quote(n) for n in names)
            cmd = f"sudo -S pacman -S --needed --noconfirm {quoted}"
        else:
            cmd = pkgmanager.install_cmd(names)
        run_terminal_fn(cmd, tr("Install {n} packages").format(n=len(names)))

    install_btn.connect("clicked", _do_install)
    outer.append(install_btn)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
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
                        f"sudo -S pacman -S --noconfirm {shlex.quote(n)}" if distro.is_arch()
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
        cmd = "sudo -S pacman -Fy --noconfirm" if distro.is_arch() else pkgmanager.sync_files_db_cmd()
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
    dialog = Adw.Window()
    dialog.set_title(tr("System Information"))
    dialog.set_default_size(560, 680)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    loading_box.set_halign(Gtk.Align.CENTER); loading_box.set_valign(Gtk.Align.CENTER)
    loading_box.set_vexpand(True)
    loading_spinner = Gtk.Spinner()
    loading_spinner.start(); loading_spinner.set_size_request(32, 32)
    loading_spinner.set_halign(Gtk.Align.CENTER)
    loading_box.append(loading_spinner)
    loading_lbl = Gtk.Label(label=tr("Gathering system info…"))
    loading_lbl.add_css_class("dim-label")
    loading_box.append(loading_lbl)
    outer.append(loading_box)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()

    def populate(info):
        outer.remove(loading_box)

        sys_group = Adw.PreferencesGroup()
        sys_group.set_title(tr("System"))
        for key in ("OS", "Desktop", "Kernel", "Architecture"):
            if key in info:
                row = Adw.ActionRow(); row.set_title(tr(key))
                val_lbl = Gtk.Label(label=info[key])
                val_lbl.add_css_class("caption"); val_lbl.add_css_class("dim-label")
                val_lbl.set_selectable(True)
                row.add_suffix(val_lbl)
                sys_group.add(row)
        outer.append(sys_group)

        hw_group = Adw.PreferencesGroup()
        hw_group.set_title(tr("Hardware"))
        for key in ("Processor", "RAM", "Disk (/)", "Disk Type"):
            if key in info:
                row = Adw.ActionRow(); row.set_title(tr(key))
                val_lbl = Gtk.Label(label=info[key])
                val_lbl.add_css_class("caption"); val_lbl.add_css_class("dim-label")
                val_lbl.set_selectable(True)
                row.add_suffix(val_lbl)
                hw_group.add(row)
        outer.append(hw_group)

        pkg_group = Adw.PreferencesGroup()
        pkg_group.set_title(tr("Packages"))
        for key in ("Pacman", "Package Manager", "AUR Helper", "Installed Packages", "Foreign (AUR) Packages", "Package Cache Size"):
            if key in info:
                row = Adw.ActionRow(); row.set_title(tr(key))
                val_lbl = Gtk.Label(label=info[key])
                val_lbl.add_css_class("caption"); val_lbl.add_css_class("dim-label")
                val_lbl.set_selectable(True)
                row.add_suffix(val_lbl)
                pkg_group.add(row)
        outer.append(pkg_group)

        repo_counts = info.get("Repo Counts") or {}
        if repo_counts:
            repo_group = Adw.PreferencesGroup()
            repo_group.set_title(tr("Installed by Repository"))
            repo_group.set_description(tr("How many installed packages come from each source"))
            # Official/enabled sync repos first (alphabetically), AUR/foreign
            # last, since it isn't really a "repository" pacman knows about.
            ordered = sorted(k for k in repo_counts if k != "aur / foreign")
            if "aur / foreign" in repo_counts:
                ordered.append("aur / foreign")
            for repo in ordered:
                row = Adw.ActionRow()
                row.set_title(tr("AUR / Foreign") if repo == "aur / foreign" else repo)
                count_lbl = Gtk.Label(label=tr("{n} pkgs").format(n=repo_counts[repo]))
                count_lbl.add_css_class("caption"); count_lbl.add_css_class("dim-label")
                row.add_suffix(count_lbl)
                repo_group.add(row)
            outer.append(repo_group)
        return False

    def worker():
        info = get_system_info()
        GLib.idle_add(populate, info)

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
    version = "2.2.5"

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
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    # Everything below lives in a ScrolledWindow. Adw.Dialog is capped to
    # the parent window's size, so on a small/default-size main window the
    # dialog's natural (unscrolled) height used to get clipped top and
    # bottom with no way to reach the rest. Inside a scroller it simply
    # scrolls instead.
    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

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
    dialog.set_default_size(640, 600)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
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

def show_downgrade_dialog(parent, pkg_name, run_terminal_fn):
    dialog = Adw.Window()
    dialog.set_title(tr("Downgrade {pkg}").format(pkg=pkg_name))
    dialog.set_default_size(560, 420)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    candidates = get_downgrade_candidates(pkg_name)

    if not candidates:
        status = Adw.StatusPage()
        status.set_paintable(themed_paintable("package-x-generic-symbolic", 72))
        status.set_title(tr("No Older Versions Found"))
        if distro.is_arch():
            desc = tr("No package files for {pkg} were found in /var/cache/pacman/pkg."
                      "\nOlder versions are only available while they remain in the cache."
                      ).format(pkg=pkg_name)
        else:
            desc = tr("No older build of {pkg} is available — either nothing is cached "
                      "locally, or the configured repositories only carry the current "
                      "version.").format(pkg=pkg_name)
        status.set_description(desc)
        status.set_vexpand(True)
        outer.append(status)
    else:
        if distro.is_arch():
            info_text = tr("{n} cached version(s) — pick one to install with pacman -U").format(n=len(candidates))
        else:
            info_text = tr("{n} version(s) available — some may need to be downloaded").format(n=len(candidates))
        info_bar = Gtk.Label(label=info_text)
        info_bar.add_css_class("caption"); info_bar.set_wrap(True)
        info_bar.set_halign(Gtk.Align.START)
        info_bar.set_margin_start(16); info_bar.set_margin_end(16)
        info_bar.set_margin_top(12);   info_bar.set_margin_bottom(8)
        outer.append(info_bar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_start(12); scroll.set_margin_end(12); scroll.set_margin_bottom(12)
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")

        for cand in candidates:
            row = Adw.ActionRow()
            row.set_title(cand["version"])
            if cand["kind"] == "file":
                row.set_subtitle(cand["source"])
            else:
                row.set_subtitle(tr("Available from repository"))
            row.set_subtitle_selectable(True)
            btn = Gtk.Button(label=tr("Install"))
            btn.add_css_class("suggested-action"); btn.add_css_class("flat")
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_, c=cand: (
                dialog.close(),
                run_terminal_fn(build_downgrade_cmd(pkg_name, c),
                                tr("Downgrade {pkg} to {ver}").format(pkg=pkg_name, ver=c["version"]))
            ))
            row.add_suffix(btn)
            listbox.append(row)

        scroll.set_child(listbox)
        outer.append(scroll)

    tv.set_content(outer)
    dialog.set_content(tv)
    dialog.present()


# ─── Hold / unhold package dialog ──────────────────────────────────────────────

def show_hold_dialog(parent, pkg_name, currently_held, on_confirm):
    """currently_held=True means the click will *unhold* it; False means the
    click will add it to IgnorePkg (hold it)."""
    dialog = Adw.Dialog()
    if currently_held:
        dialog.set_title(tr("Unhold {pkg}").format(pkg=pkg_name))
    else:
        dialog.set_title(tr("Hold {pkg}").format(pkg=pkg_name))
    dialog.set_content_width(460)
    dialog.set_content_height(280)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Mark as dependency dialog ─────────────────────────────────────────────────

def show_mark_asdeps_dialog(parent, pkg_name, on_confirm):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Mark {name} as dependency").format(name=pkg_name))
    dialog.set_content_width(460)
    dialog.set_content_height(300)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(16);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

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

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
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

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)

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
    dialog.set_default_size(720, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
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

        info = Gtk.Label(label=(
            tr("{n} file(s) left behind by package updates. Review the diff, then keep the new version or discard it.").format(n=len(files))))
        info.add_css_class("caption"); info.set_wrap(True); info.set_halign(Gtk.Align.START)
        info.set_margin_start(16); info.set_margin_end(16)
        info.set_margin_top(12);   info.set_margin_bottom(8)
        outer.append(info)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
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
            apply_btn.connect("clicked", lambda *_, n=new, o=orig: (
                dialog.close(),
                run_terminal_fn(f"sudo -S mv {shlex.quote(n)} {shlex.quote(o)}",
                                tr("Apply {name}").format(name=n))))
            discard_btn = Gtk.Button(label=tr("Discard"))
            discard_btn.add_css_class("destructive-action"); discard_btn.add_css_class("flat")
            discard_btn.connect("clicked", lambda *_, n=new: (
                dialog.close(),
                run_terminal_fn(f"sudo -S rm {shlex.quote(n)}", tr("Remove {name} ").format(name=n))))
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
    dialog.set_default_size(520, 560)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)

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

        if not names:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 64))
            status.set_title(tr("No Ignored Packages"))
            status.set_description(tr(
                "Held/ignored packages (skipped by system upgrades) show up here."))
            outer.append(status)
            return

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_start(12); scroll.set_margin_end(12)
        scroll.set_margin_top(12);   scroll.set_margin_bottom(12)
        group = Adw.PreferencesGroup()
        group.set_description(tr(
            "These packages are skipped by system upgrades until you unignore them."))
        for name in names:
            row = Adw.ActionRow()
            row.set_title(name)
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
    dialog.set_default_size(760, 620)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)

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

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_start(12); scroll.set_margin_end(12)
        scroll.set_margin_top(12);   scroll.set_margin_bottom(12)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

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
    dlg.set_default_size(780, 780)
    dlg.set_resizable(True)
    dlg.set_transient_for(parent)
    dlg.set_modal(True)
    page = Adw.PreferencesPage()
    page.set_title(tr("General"))
    page.set_icon_name("preferences-system-symbolic")

    # AUR
    aur_group = Adw.PreferencesGroup()
    aur_group.set_title("AUR")

    helper_opts = ["auto", "yay", "paru", "pikaur", "none"]
    helper_row = Adw.ComboRow()
    helper_row.set_title(tr("AUR Helper"))
    helper_row.set_subtitle(tr("Used for AUR installs, updates and PKGBUILDs"))
    helper_row.set_model(Gtk.StringList.new(
        [tr("Auto-detect"), "yay", "paru", "pikaur", tr("None (pacman only)")]))
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
    from backend import flatpak_available, snap_available
    extra_group = Adw.PreferencesGroup()
    extra_group.set_title(tr("Additional Package Sources"))
    extra_group.set_description(tr(
        "Show installed Flatpak/Snap apps alongside pacman packages, and include them when searching. "
        "Flatpak installs use --user (no password needed); Snap always needs one, since snapd requires root."))

    fp_row = Adw.SwitchRow()
    fp_row.set_title("Flatpak")
    fp_row.set_active(s.get("flatpak_enabled", False))
    if not flatpak_available():
        fp_row.set_subtitle(tr("flatpak isn't installed"))
        fp_row.set_sensitive(False)
    fp_row.connect("notify::active", lambda r, _: (
        save_settings({"flatpak_enabled": r.get_active()}), on_changed()))
    extra_group.add(fp_row)

    sn_row = Adw.SwitchRow()
    sn_row.set_title("Snap")
    sn_row.set_active(s.get("snap_enabled", False))
    if not snap_available():
        sn_row.set_subtitle(tr("snap isn't installed"))
        sn_row.set_sensitive(False)
    sn_row.connect("notify::active", lambda r, _: (
        save_settings({"snap_enabled": r.get_active()}), on_changed()))
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
        ("Ctrl+,",        tr("Preferences")),
        ("Ctrl+A",        tr("Select all packages (batch mode)")),
        ("Ctrl+Shift+A",  tr("Deselect all packages (batch mode)")),
        ("F1 / Ctrl+?",   tr("Help")),
        ("Ctrl+Q",        tr("Quit")),
    ]


def _help_function_groups(parent):
    """(group_title, [(name, description), …]) pairs describing every menu
    function — grouped to match the app menu's own sections. `parent` is
    the main window, used to skip rows for features that don't apply on
    the current distro/setup (same conditions the menu itself uses)."""
    hold_supported = getattr(parent, "_hold_supported", False)
    mark_supported = getattr(parent, "_mark_reason_supported", False)

    groups = []

    groups.append((tr("Browsing & Search"), [
        (tr("New Packages / All Packages / Installed / Updates"),
         tr("Sidebar filters for the package list — what's newly available, "
            "everything, only what's installed, or only what has an update "
            "pending.")),
        (tr("Search"),
         tr("Type in the search bar (or press Ctrl+F) to filter the current "
            "list by name or description.")),
        (tr("Package details"),
         tr("Click any package to see its description, version, size, "
            "dependencies and files on the right, with Install/Remove/"
            "Update actions.")),
    ]))

    groups.append((tr("Updating"), [
        (tr("Sync Databases"),
         tr("Refresh the local package index from the repositories, "
            "without installing anything yet.")),
        (tr("Check for Updates"),
         tr("Sync, then rebuild the Updates list — same as pressing Ctrl+U.")),
        (tr("Refresh List"),
         tr("Reload the current view from what's already known locally, "
            "without contacting the repositories.")),
        (tr("Upgrade All"),
         tr("Install every pending update in one go — shown as a button "
            "whenever the Updates list isn't empty.")),
        (tr("Batch mode"),
         tr("Select several packages at once (checkboxes in the list) to "
            "install or remove them together; Ctrl+A / Ctrl+Shift+A select "
            "or deselect everything currently visible.")),
    ]))

    repo_rows = [
        (tr("Manage Repositories…"),
         tr("View and edit which package repositories are enabled.")),
    ]
    if distro.is_arch():
        repo_rows.append((tr("Rate Mirrors…"),
            tr("Benchmark configured mirrors and switch to the fastest "
               "ones. Arch-only — Fedora and openSUSE already pick the "
               "fastest mirror automatically.")))
    groups.append((tr("Repositories"), repo_rows))

    groups.append((tr("Tools"), [
        (tr("Find Orphans"),
         tr("List packages that were pulled in as dependencies but are no "
            "longer needed by anything, so you can clean them up.")),
        (tr("Find Package by File…"),
         tr("Look up which installed package owns a given file path.")),
        (tr("Config File Conflicts…"),
         tr("Review and merge configuration files a package update left "
            "behind instead of overwriting your local changes.")),
        (tr("More Update Sources…"),
         tr("Check for updates outside the system package manager — "
            "rustup, npm, pip, Flatpak, and similar tools.")),
        *([(tr("Ignored Packages…"),
            tr("Hold specific packages back from updates."))] if hold_supported else []),
        (tr("Package History…"),
         tr("Browse a log of past installs, removals and updates.")),
        (tr("System Info"),
         tr("Overview of the system, hardware and installed packages.")),
        (tr("Cache Cleaner"),
         tr("Free up disk space by clearing old cached package files.")),
    ]))

    groups.append((tr("Package Lists"), [
        (tr("Export Package List…"),
         tr("Save the list of explicitly installed packages to a file — "
            "handy for setting up another machine the same way.")),
        (tr("Import Package List…"),
         tr("Install every package from a previously exported list.")),
    ]))

    if distro.is_arch() or hold_supported or mark_supported:
        adv_rows = []
        if distro.is_arch():
            adv_rows.append((tr("View PKGBUILD (AUR)…"),
                tr("Inspect the build script of an AUR package before "
                   "installing it.")))
        if hold_supported:
            adv_rows.append((tr("Hold / Unhold Selected"),
                tr("Toggle whether the selected packages are excluded from "
                   "updates.")))
        if mark_supported:
            adv_rows.append((tr("Mark Selected as Explicit / as Dependency"),
                tr("Change how a package is tracked, so orphan-cleanup "
                   "treats it correctly.")))
        groups.append((tr("AUR / Advanced"), adv_rows))

    groups.append((tr("General"), [
        (tr("Preferences"),
         tr("App-wide settings: language, theme, and other options.")),
        (tr("About Pachul"),
         tr("Version, license and system info for bug reports.")),
    ]))

    return groups


def show_help_dialog(parent):
    dialog = Adw.Window()
    dialog.set_title(tr("Help"))
    dialog.set_default_size(480, 640)
    dialog.set_resizable(True)
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
    outer.set_margin_top(12);   outer.set_margin_bottom(24)
    outer.set_margin_start(16); outer.set_margin_end(16)

    # ── Functions, grouped exactly like the app menu ──
    for title, rows in _help_function_groups(parent):
        if not rows:
            continue
        group = Adw.PreferencesGroup()
        # set_title/set_title/set_subtitle all parse their text as Pango
        # markup, so a literal "&" (e.g. "Browsing & Search") would
        # otherwise crash ("Failed to set text ... from markup") — escape
        # everything here defensively.
        group.set_title(GLib.markup_escape_text(title))
        for name, desc in rows:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(name))
            row.set_subtitle(GLib.markup_escape_text(desc))
            row.set_subtitle_lines(0)
            row.add_css_class("help-row")
            group.add(row)
        outer.append(group)

    # ── Keyboard shortcuts, all in one place ──
    kb_group = Adw.PreferencesGroup()
    kb_group.set_title(tr("Keyboard Shortcuts"))
    for keys, desc in _shortcuts_list():
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(desc))
        kbd = Gtk.Label(label=keys)
        kbd.add_css_class("dim-label"); kbd.add_css_class("monospace")
        kbd.set_valign(Gtk.Align.CENTER)
        row.add_suffix(kbd)
        kb_group.add(row)
    outer.append(kb_group)

    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_content(tv)
    dialog.present()

