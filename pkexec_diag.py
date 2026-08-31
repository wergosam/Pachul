#!/usr/bin/env python3
"""
Diagnose-Script: bildet Pachuls PTY-Spawn-Mechanismus 1:1 nach (nur die
Prozess-Erzeugung, ohne GTK), um zu prüfen, ob genau DAS der Grund ist,
warum pkexec bei dir übers Eingabefeld statt übers native Popup fragt.

Nutzung:
    python3 pkexec_diag.py            # Test A: exakt wie Pachul (Thread + PTY + setsid)
    python3 pkexec_diag.py --no-setsid   # Test B: wie A, aber OHNE setsid
    python3 pkexec_diag.py --no-thread   # Test C: wie A, aber im Hauptthread statt in einem Thread
    python3 pkexec_diag.py --plain       # Test D: ganz normaler subprocess.run (Referenz/Kontrolle)

Für jeden Fall: schau, ob ein natives Popup erscheint oder ob "Password:"
im Terminal-Output dieses Scripts landet.
"""
import argparse
import os
import pty
import struct
import fcntl
import termios
import select
import subprocess
import sys
import threading


def run_via_pachul_pattern(use_setsid=True):
    """Exact copy of dialogs.py's worker(): pty.openpty() + Popen with
    slave_fd as stdin/stdout/stderr, close_fds=True, preexec_fn=os.setsid,
    full-environment copy — everything Pachul's own terminal dialog does."""
    master_fd, slave_fd = pty.openpty()

    try:
        ws = struct.pack('HHHH', 40, 120, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, ws)
    except Exception:
        pass

    env = dict(os.environ)
    env['TERM'] = 'xterm-256color'
    env.pop('SUDO_ASKPASS', None)

    kwargs = dict(
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        close_fds=True, env=env,
    )
    if use_setsid:
        kwargs['preexec_fn'] = os.setsid

    proc = subprocess.Popen(["sh", "-c", "pkexec true; echo EXIT_CODE=$?"], **kwargs)
    os.close(slave_fd)

    # Read + print everything until the child exits, same select() loop
    # shape as Pachul's own reader.
    while True:
        try:
            rlist, _, _ = select.select([master_fd], [], [], 0.2)
        except (ValueError, OSError):
            break
        if rlist:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            sys.stdout.write(chunk.decode('utf-8', errors='replace'))
            sys.stdout.flush()
        elif proc.poll() is not None:
            break

    proc.wait()
    try:
        os.close(master_fd)
    except OSError:
        pass
    print(f"\n[diag] subprocess exit code: {proc.returncode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-setsid", action="store_true",
                     help="Test B: wie Pachul, aber ohne os.setsid()")
    ap.add_argument("--no-thread", action="store_true",
                     help="Test C: im Hauptthread statt in einem Thread")
    ap.add_argument("--plain", action="store_true",
                     help="Test D: ganz normaler subprocess.run als Kontrolle "
                          "(kein PTY, kein setsid, kein Thread)")
    args = ap.parse_args()

    if args.plain:
        print("[diag] Test D: plain subprocess.run (Kontrollgruppe)")
        r = subprocess.run(["pkexec", "true"])
        print(f"[diag] exit code: {r.returncode}")
        return

    use_setsid = not args.no_setsid
    label = "Test A: Pachul-Muster (Thread + PTY + setsid)"
    if args.no_setsid:
        label = "Test B: PTY + Thread, OHNE setsid"
    if args.no_thread:
        label += " — läuft aber im Hauptthread statt in einem eigenen Thread"

    print(f"[diag] {label}")
    print("[diag] Schau jetzt: erscheint ein natives Popup, oder wird im")
    print("[diag] Terminal direkt nach dem Passwort gefragt?\n")

    if args.no_thread:
        run_via_pachul_pattern(use_setsid=use_setsid)
    else:
        t = threading.Thread(target=run_via_pachul_pattern, args=(use_setsid,), daemon=True)
        t.start()
        t.join()


if __name__ == "__main__":
    main()
