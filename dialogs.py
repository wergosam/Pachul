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

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango

from backend import (run_command, get_orphans, get_system_info,
                     get_pacman_history, get_cached_versions,
                     get_pkgbuild, get_pacnew_files, get_file_diff, get_setting, save_settings,
                     files_db_available, search_file_owner, get_package_cache_size)
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
    m = _GPG_KEY_ID_RE.search(text)
    if m:
        return m.group(1).upper()
    if _GPG_TRUST_RE.search(text) or _GPG_GENERIC_RE.search(text):
        return ""
    return None


def run_terminal_dialog(parent, cmd, title, on_success=None, on_done_extra=None):
    """
    Open a PTY-backed terminal dialog that runs *cmd*.
    Calls on_success() (on the main thread) if the command exits with code 0.

    If the command fails with a recognizable GPG/signature error, offers an
    inline one-click fix (import the missing key, or refresh the keyring)
    followed by an automatic retry of *cmd* in a fresh dialog.
    """
    dialog = Adw.Dialog()
    dialog.set_title(title)
    dialog.set_content_width(720)
    dialog.set_content_height(520)
    dialog.set_follows_content_size(False)

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

    cmd_lbl = Gtk.Label(label=f"$ {cmd}")
    cmd_lbl.add_css_class("caption")
    cmd_lbl.add_css_class("dim-label")
    cmd_lbl.set_halign(Gtk.Align.START)
    cmd_lbl.set_ellipsize(Pango.EllipsizeMode.END)
    cmd_lbl.set_margin_start(14); cmd_lbl.set_margin_end(14)
    cmd_lbl.set_margin_top(6);    cmd_lbl.set_margin_bottom(4)
    tv.add_top_bar(cmd_lbl)

    gpg_banner = Adw.Banner()
    gpg_banner.set_revealed(False)
    tv.add_top_bar(gpg_banner)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    outer.set_margin_top(8);    outer.set_margin_bottom(12)
    outer.set_margin_start(12); outer.set_margin_end(12)

    # Real progress bar, parsed live from pacman's own "[####----] NN%" lines
    # (download progress and "(i/n) installing pkg [...] NN%" alike). Hidden
    # until the first such line arrives; hidden again once the command ends.
    progress_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    progress_box.set_visible(False)
    progress_label = Gtk.Label(label="")
    progress_label.add_css_class("caption")
    progress_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    progress_label.set_width_chars(18)
    progress_label.set_xalign(0.0)
    progress_box.append(progress_label)
    progress_bar = Gtk.ProgressBar()
    progress_bar.set_hexpand(True)
    progress_bar.set_show_text(True)
    progress_box.append(progress_bar)
    outer.append(progress_box)

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

    toggle_vis_btn = Gtk.ToggleButton()
    toggle_vis_btn.set_child(themed_image("view-reveal-symbolic", 18))
    toggle_vis_btn.add_css_class("image-button")
    toggle_vis_btn.add_css_class("flat")
    toggle_vis_btn.set_tooltip_text(tr("Show/hide input"))
    toggle_vis_btn.connect("toggled", lambda b, *_: pw_entry.set_visibility(b.get_active()))
    input_box.append(toggle_vis_btn)

    input_frame.set_child(input_box)
    outer.append(input_frame)

    tv.set_content(outer)
    dialog.set_child(tv)
    dialog.present(parent)

    # Fokus direkt ins Passwort-/Eingabefeld setzen, damit man sofort
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
    # The bracket contents are left generic ([^\]]*) since the fill character
    # varies with pacman's Color/ILoveCandy settings.
    _PROGRESS_RE = _re.compile(r'^\s*(\S.*?)\s+\[[^\]]*\]\s*(\d{1,3})%\s*$')

    def _update_progress(line):
        m = _PROGRESS_RE.match(line)
        if not m:
            return
        desc, pct = m.group(1).strip(), max(0, min(100, int(m.group(2))))
        progress_bar.set_fraction(pct / 100.0)
        progress_bar.set_text(f"{pct}%")
        item = desc.split()[0] if desc.split() else desc
        progress_label.set_label(item)
        progress_label.set_tooltip_text(desc)
        if not progress_box.get_visible():
            progress_box.set_visible(True)

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
                    if key_id:
                        fix = (f"sudo -S pacman-key --recv-keys {key_id} && "
                               f"sudo -S pacman-key --lsign-key {key_id}")
                    else:
                        fix = "sudo -S pacman -Sy --needed --noconfirm archlinux-keyring"
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
            elif _DB_LOCK_RE.search(full_text):
                def _do_lock_fix(*_):
                    gpg_banner.set_revealed(False)
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
                    dialog.close()
                    run_terminal_dialog(parent, f"{fix} && {cmd}", title,
                                        on_success=on_success, on_done_extra=on_done_extra)

                gpg_banner.set_title(tr("Pacman database is locked (stale db.lck)"))
                gpg_banner.set_button_label(tr("Remove Lock & Retry"))
                gpg_banner.connect("button-clicked", _do_lock_fix)
                gpg_banner.set_revealed(True)
        if code == 0 and on_success:
            on_success()
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
    dialog = Adw.Dialog()
    dialog.set_title(tr("Manage Repositories"))
    # Was 640×500 — far too cramped for comfortably editing pacman.conf.
    # Adw.Dialog doesn't support free resizing by dragging an edge, so the
    # practical fix is simply to open it noticeably bigger by default and
    # let the editor area expand to fill whatever room it has.
    dialog.set_content_width(920)
    dialog.set_content_height(800)

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
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Mirror rater dialog ──────────────────────────────────────────────────────

def show_mirror_rater(parent, run_terminal_fn):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Rate Mirrors"))
    dialog.set_content_width(600)
    dialog.set_content_height(560)

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

            result_dialog = Adw.Dialog()
            result_dialog.set_title(tr("Mirror Ranking Result"))
            result_dialog.set_content_width(680)
            result_dialog.set_content_height(600)

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
            result_dialog.set_child(rtv)
            result_dialog.present(parent)

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
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Orphan finder dialog ─────────────────────────────────────────────────────

def show_orphan_finder(parent, run_terminal_fn):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Orphaned Packages"))
    dialog.set_content_width(560)
    dialog.set_content_height(460)

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
                run_terminal_fn(f"sudo -S pacman -R --noconfirm {shlex.quote(n)}", tr("Remove {name} ").format(name=n))
            ))
            row.add_suffix(rm_btn)
            listbox.append(row)

        scroll.set_child(listbox)
        outer.append(scroll)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(12); btn_box.set_margin_bottom(16)
        names = " ".join(shlex.quote(o["name"]) for o in orphans)
        remove_all_btn = Gtk.Button(label=tr("Remove All {n} Orphans").format(n=len(orphans)))
        remove_all_btn.add_css_class("destructive-action")
        remove_all_btn.connect("clicked", lambda *_: (
            dialog.close(),
            run_terminal_fn(f"sudo -S pacman -Rns --noconfirm {names}", tr("Remove All Orphans"))
        ))
        btn_box.append(remove_all_btn)
        outer.append(btn_box)

    tv.set_content(outer)
    dialog.set_child(tv)
    dialog.present(parent)


# ─── Clean cache dialog ────────────────────────────────────────────────────────

def show_clean_cache_dialog(parent, run_terminal_fn):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Clean Cache"))
    dialog.set_content_width(480)
    dialog.set_content_height(340)

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
    has_paccache = (code == 0)

    info_group = Adw.PreferencesGroup()
    info_group.set_title(tr("What this does"))
    if has_paccache:
        info_group.set_description(tr(
            "Removes old cached package versions from /var/cache/pacman/pkg "
            "using paccache, keeping the 2 most recent versions of each "
            "package so you can still downgrade later if needed. "
            "Currently installed packages are never touched."
        ))
    else:
        info_group.set_description(tr(
            "paccache isn't installed, so this falls back to pacman's "
            "built-in cleanup (pacman -Sc), which removes cached versions "
            "of packages that are no longer installed, plus superseded old "
            "versions of packages you still have. "
            "Currently installed packages are never touched."
        ))
    outer.append(info_group)

    size_group = Adw.PreferencesGroup()
    size_row = Adw.ActionRow()
    size_row.set_title(tr("Current Cache Size"))
    size_row.set_subtitle("/var/cache/pacman/pkg")
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
        run_terminal_fn(
            "sudo -S -v && { paccache -rk2 2>/dev/null || sudo pacman -Sc --noconfirm; }",
            tr("Clean Cache"))

    clean_btn.connect("clicked", _do_clean)
    outer.append(clean_btn)

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
    dialog = Adw.Dialog()
    dialog.set_title(tr("Import Package List"))
    dialog.set_content_width(520)
    dialog.set_content_height(480)

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
        quoted = " ".join(shlex.quote(n) for n in names)
        if helper:
            cmd = f"{helper} -S --needed --noconfirm {quoted}"
        else:
            cmd = f"sudo -S pacman -S --needed --noconfirm {quoted}"
        run_terminal_fn(cmd, tr("Install {n} packages").format(n=len(names)))

    install_btn.connect("clicked", _do_install)
    outer.append(install_btn)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(outer)
    tv.set_content(scroll)
    dialog.set_child(tv)
    dialog.present(parent)


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
    dialog = Adw.Dialog()
    dialog.set_title(tr("Find Package by File"))
    dialog.set_content_width(600)
    dialog.set_content_height(560)

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
    dialog.set_child(tv)
    dialog.present(parent)

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

            _, installed_code = run_command(f"pacman -Qi {shlex.quote(pkg_name)} 2>/dev/null")
            if installed_code == 0:
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
                    run_terminal_fn(f"sudo -S pacman -S --noconfirm {shlex.quote(n)}",
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
        run_terminal_fn("sudo -S pacman -Fy --noconfirm", tr("Sync File Database"))
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
    dialog = Adw.Dialog()
    dialog.set_title(tr("System Information"))
    dialog.set_content_width(560)
    dialog.set_content_height(680)

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
    dialog.set_child(tv)
    dialog.present(parent)

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
        for key in ("Pacman", "AUR Helper", "Installed Packages", "Foreign (AUR) Packages", "Package Cache Size"):
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


# ─── Package history (pacman log) ─────────────────────────────────────────────

_HISTORY_ICONS = {
    "installed":   ("package-x-generic-symbolic",        "status-installed"),
    "removed":     ("user-trash-symbolic",               "status-foreign"),
    "upgraded":    ("software-update-available-symbolic", "status-update"),
    "downgraded":  ("go-down-symbolic",                  "status-update"),
    "reinstalled": ("view-refresh-symbolic",             None),
}


def show_history_dialog(parent):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Package History"))
    dialog.set_content_width(640)
    dialog.set_content_height(600)

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
    dialog.set_child(tv)
    dialog.present(parent)

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
    dialog = Adw.Dialog()
    dialog.set_title(tr("Downgrade {pkg}").format(pkg=pkg_name))
    dialog.set_content_width(560)
    dialog.set_content_height(420)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    versions = get_cached_versions(pkg_name)

    if not versions:
        status = Adw.StatusPage()
        status.set_paintable(themed_paintable("package-x-generic-symbolic", 72))
        status.set_title(tr("No Cached Versions"))
        status.set_description(
            tr("No package files for {pkg} were found in /var/cache/pacman/pkg.\nOlder versions are only available while they remain in the cache.").format(pkg=pkg_name))
        status.set_vexpand(True)
        outer.append(status)
    else:
        info_bar = Gtk.Label(
            label=tr("{n} cached version(s) — pick one to install with pacman -U").format(n=len(versions)))
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

        for version, filepath in versions:
            row = Adw.ActionRow()
            row.set_title(version)
            row.set_subtitle(filepath)
            row.set_subtitle_selectable(True)
            btn = Gtk.Button(label=tr("Install"))
            btn.add_css_class("suggested-action"); btn.add_css_class("flat")
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_, fp=filepath, v=version: (
                dialog.close(),
                run_terminal_fn(f"sudo -S pacman -U --noconfirm {shlex.quote(fp)}",
                                tr("Downgrade {pkg} to {ver}").format(pkg=pkg_name, ver=v))
            ))
            row.add_suffix(btn)
            listbox.append(row)

        scroll.set_child(listbox)
        outer.append(scroll)

    tv.set_content(outer)
    dialog.set_child(tv)
    dialog.present(parent)


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
    if currently_held:
        info_group.set_title(tr("Allow {pkg} to Update Again").format(pkg=pkg_name))
        info_group.set_description(tr(
            "Removes {pkg} from IgnorePkg in /etc/pacman.conf. It will be "
            "included in system upgrades again from now on."
        ).format(pkg=pkg_name))
        action_label = tr("Unhold {pkg}").format(pkg=pkg_name)
    else:
        info_group.set_title(tr("Pin {pkg} to Its Current Version").format(pkg=pkg_name))
        info_group.set_description(tr(
            "Adds {pkg} to IgnorePkg in /etc/pacman.conf. Held packages are "
            "skipped by system upgrades — useful if a specific version needs "
            "to stay put for compatibility — and won't update again until "
            "you unhold them."
        ).format(pkg=pkg_name))
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

    dialog = Adw.Dialog()
    dialog.set_title(tr("PKGBUILD — {pkg}").format(pkg=pkg_name))
    dialog.set_content_width(760)
    dialog.set_content_height(600)

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
    dialog.set_child(tv)
    dialog.present(parent)

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
    dialog = Adw.Dialog()
    dialog.set_title(tr("Config Files (.pacnew / .pacsave)"))
    dialog.set_content_width(720)
    dialog.set_content_height(560)

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
    loading.append(Gtk.Label(label=tr("Scanning for .pacnew/.pacsave files…")))
    outer.append(loading)

    tv.set_content(outer)
    dialog.set_child(tv)
    dialog.present(parent)

    def render(files):
        outer.remove(loading)
        if not files:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 72))
            status.set_title(tr("Nothing to Merge"))
            status.set_description(tr("No .pacnew or .pacsave files were found."))
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


# ─── Preferences ──────────────────────────────────────────────────────────────

def show_preferences(parent, on_changed):
    from backend import (load_settings, save_settings, is_update_timer_enabled,
                         enable_update_timer, disable_update_timer, detect_snapshot_tool)
    s = load_settings()

    dlg = Adw.PreferencesDialog()
    dlg.set_title(tr("Preferences "))
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

    inc_row = Adw.SwitchRow()
    inc_row.set_title(tr("Include AUR in update checks"))
    inc_row.set_active(s.get("include_aur_updates", True))
    inc_row.connect("notify::active", lambda r, _: (
        save_settings({"include_aur_updates": r.get_active()}), on_changed()))
    aur_group.add(inc_row)
    page.add(aur_group)

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
    _switch(tr("Show Arch news before upgrades"),
            tr("Warns about manual interventions before a system upgrade"),
            "show_news_before_upgrade")

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
    dlg.present(parent)


# ─── Arch news (pre-upgrade) ──────────────────────────────────────────────────

def show_news_dialog(parent, on_proceed):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Arch Linux News"))
    dialog.set_content_width(640)
    dialog.set_content_height(520)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    cancel_btn = Gtk.Button(label=tr("Cancel"))
    cancel_btn.add_css_class("flat")
    cancel_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(cancel_btn)
    proceed_btn = Gtk.Button(label=tr("Upgrade Now"))
    proceed_btn.add_css_class("suggested-action")
    proceed_btn.connect("clicked", lambda *_: (dialog.close(), on_proceed()))
    hdr.pack_end(proceed_btn)
    tv.add_top_bar(hdr)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    loading.set_halign(Gtk.Align.CENTER); loading.set_valign(Gtk.Align.CENTER)
    loading.set_vexpand(True)
    sp = Gtk.Spinner(); sp.start(); sp.set_size_request(32, 32)
    loading.append(sp)
    loading.append(Gtk.Label(label=tr("Fetching latest news…")))
    outer.append(loading)

    tv.set_content(outer)
    dialog.set_child(tv)
    dialog.present(parent)

    def render(items):
        outer.remove(loading)
        if items is None:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("network-offline-symbolic", 72))
            status.set_title(tr("Could Not Fetch News"))
            status.set_description(tr("You appear to be offline. You can still proceed with the upgrade."))
            status.set_vexpand(True)
            outer.append(status)
            return
        if not items:
            status = Adw.StatusPage()
            status.set_paintable(themed_paintable("emblem-ok-symbolic", 72))
            status.set_title(tr("No Recent News"))
            status.set_vexpand(True)
            outer.append(status)
            return

        hint = Gtk.Label(label=tr("Review recent announcements before upgrading:"))
        hint.add_css_class("caption"); hint.set_halign(Gtk.Align.START)
        hint.set_margin_start(16); hint.set_margin_end(16)
        hint.set_margin_top(12);   hint.set_margin_bottom(8)
        outer.append(hint)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_margin_start(12); scroll.set_margin_end(12); scroll.set_margin_bottom(12)
        group = Adw.PreferencesGroup()
        for it in items:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(it["title"]))
            row.set_subtitle(it["date"])
            if it["link"]:
                link = Gtk.LinkButton.new_with_label(it["link"], tr("Open"))
                link.set_valign(Gtk.Align.CENTER)
                row.add_suffix(link)
            group.add(row)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL); box.append(group)
        scroll.set_child(box)
        outer.append(scroll)

    def worker():
        from backend import get_arch_news
        items = get_arch_news()
        GLib.idle_add(render, items)

    threading.Thread(target=worker, daemon=True).start()


# ─── Keyboard shortcuts ───────────────────────────────────────────────────────

_SHORTCUTS = [
    ("Ctrl+F",      tr("Focus search")),
    ("F5",          tr("Sync databases")),
    ("Ctrl+R",      tr("Refresh package list")),
    ("Ctrl+U",      tr("Check for updates")),
    ("Ctrl+,",      tr("Preferences  ")),
    ("Ctrl+A",      tr("Select all packages (batch mode)")),
    ("Ctrl+Shift+A", tr("Deselect all packages (batch mode)")),
    ("Ctrl+Q",      tr("Quit")),
]


def show_shortcuts_dialog(parent):
    dialog = Adw.Dialog()
    dialog.set_title(tr("Keyboard Shortcuts "))
    dialog.set_content_width(420)

    tv  = Adw.ToolbarView()
    hdr = Adw.HeaderBar()
    hdr.set_show_end_title_buttons(False)
    close_btn = Gtk.Button(label=tr("Close"))
    close_btn.add_css_class("flat")
    close_btn.connect("clicked", lambda *_: dialog.close())
    hdr.pack_start(close_btn)
    tv.add_top_bar(hdr)

    group = Adw.PreferencesGroup()
    group.set_margin_top(12); group.set_margin_bottom(16)
    group.set_margin_start(12); group.set_margin_end(12)
    for keys, desc in _SHORTCUTS:
        row = Adw.ActionRow()
        row.set_title(desc)
        kbd = Gtk.Label(label=keys)
        kbd.add_css_class("dim-label"); kbd.add_css_class("monospace")
        kbd.set_valign(Gtk.Align.CENTER)
        row.add_suffix(kbd)
        group.add(row)

    tv.set_content(group)
    dialog.set_child(tv)
    dialog.present(parent)
