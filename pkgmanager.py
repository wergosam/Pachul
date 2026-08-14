"""
Pachul — pkgmanager.py
Package-manager command builders and output parsers for the non-Arch
distro families: Debian/Ubuntu (apt), Fedora (dnf), openSUSE (zypper).

pacman/AUR itself is left completely untouched in backend.py — that code
path is exactly as it always was. This module only ever gets consulted
when distro.get_family() says we're NOT on Arch, so nothing here can
affect an existing Arch install even in principle.

Design rules this module follows throughout:
  - Every "*_cmd()" function returns a ready-to-run shell command string
    (already shlex-quoted), or None if the operation has no sane
    equivalent on the current family.
  - Every "parse_*()" / "get_*()" function returns the SAME plain dict/
    list shapes backend.py already uses for pacman (e.g. package dicts
    with name/version/repo/description/status/foreign, or update dicts
    with name/old/new/aur) — so window.py and dialogs.py never need to
    know or care which distro they're actually talking to.
  - Anything that can't be determined reliably degrades to an empty
    result rather than raising — exactly the resilience style the rest
    of Pachul already follows for AUR/Flatpak/Snap.

Honesty note for whoever maintains this next: the apt/dnf/zypper output
parsing below is written carefully against each tool's documented/
standard output format, but — unlike the pacman code this project has
years of real-world mileage on — it has not been exercised against a
live Debian, Fedora, or openSUSE installation. Test on real machines and
adjust the parsing in this file if a particular tool version's output
differs from what's assumed here.
"""

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from distro import get_family
import pkgmanager_native as native


# ─── Local, dependency-free command runner ────────────────────────────────────
# Deliberately not importing backend.run_command here: backend.py imports
# THIS module, so importing back would be circular. A tiny duplicate is a
# fair trade for keeping the two modules independent.

_C_ENV = {**os.environ, "LC_ALL": "C", "LANG": "C"}


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, env=_C_ENV)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception as e:
        return str(e), 1


def _fmt_size(num_bytes):
    """Format a byte count base-1024, e.g. 1536 -> '1.5 KiB'. Mirrors
    backend._human_size exactly, duplicated here for the same
    no-circular-import reason as _run above."""
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "None"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PiB"


def _parse_colon_fields(raw):
    """Parse 'Key: value' blocks (dpkg -s / apt-cache show / rpm -qi),
    folding wrapped continuation lines (indented, or a lone '.') into the
    previous key's value."""
    fields = {}
    current = None
    for line in raw.splitlines():
        if line and not line[0].isspace() and ":" in line:
            k, _, v = line.partition(":")
            current = k.strip()
            fields[current] = v.strip()
        elif current and line.startswith((" ", "\t")) and line.strip() not in ("", "."):
            fields[current] = (fields[current] + " " + line.strip().lstrip(". ")).strip()
    return fields


def _dir_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _dir_size(entry.path)
                except OSError:
                    pass
    except OSError:
        pass
    return total


# ─── Install / remove / upgrade / refresh ─────────────────────────────────────

def get_downgrade_candidates(pkg_name):
    """Older versions of pkg_name that could be installed instead of the
    current one — the non-Arch analogue of backend.get_cached_versions().

    Returns [{"version","source","kind"}, ...], newest-looking first.
    kind == "file": `source` is a real cached package file on disk (closest
    equivalent to pacman's package cache).
    kind == "repo": `source` is just the version string again — the
    package manager itself can still resolve that build directly, no
    local file needed (apt-cache madison / dnf's build history / a repo
    that still carries multiple versions).

    Honesty note: real repos usually only keep the *current* build of a
    package, so on a lot of systems this will legitimately come back
    empty or short — that's not a bug, it mirrors what's actually
    available to install."""
    fam = get_family()
    q = shlex.quote(pkg_name)
    candidates = []
    seen = set()

    if fam == "debian":
        cache_dir = Path("/var/cache/apt/archives")
        if cache_dir.is_dir():
            for f in cache_dir.glob(f"{pkg_name}_*.deb"):
                out, code = _run(f"dpkg-deb -f {shlex.quote(str(f))} Version 2>/dev/null")
                version = out.strip()
                if code == 0 and version and version not in seen:
                    seen.add(version)
                    candidates.append({"version": version, "source": str(f), "kind": "file"})
        # apt-cache madison lists every build of pkg_name still resolvable
        # across all configured suites/repos (e.g. -updates, -security,
        # backports) — the closest apt equivalent to browsing a package's
        # version history.
        out, code = _run(f"apt-cache madison {q} 2>/dev/null", timeout=15)
        if out and code == 0:
            for line in out.splitlines():
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2 and parts[1] and parts[1] not in seen:
                    seen.add(parts[1])
                    candidates.append({"version": parts[1], "source": parts[1], "kind": "repo"})
        return candidates

    if fam == "fedora":
        out, code = _run(f"dnf -q --showduplicates list {q} 2>/dev/null", timeout=30)
        if out and code == 0:
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3 and "." in parts[0] and parts[0] != "Available" \
                        and parts[0] != "Installed":
                    version = parts[1]
                    if version not in seen:
                        seen.add(version)
                        candidates.append({"version": version, "source": version, "kind": "repo"})
        # dnf's own download cache — populated automatically unless the
        # system has keepcache=false, same spirit as pacman's package cache.
        cache_root = Path("/var/cache/dnf")
        if cache_root.is_dir():
            for f in cache_root.rglob(f"{pkg_name}-*.rpm"):
                out2, code2 = _run(
                    f"rpm -qp --qf '%{{VERSION}}-%{{RELEASE}}' {shlex.quote(str(f))} 2>/dev/null")
                version = out2.strip()
                if code2 == 0 and version and version not in seen:
                    seen.add(version)
                    candidates.append({"version": version, "source": str(f), "kind": "file"})
        return candidates

    if fam == "suse":
        out, code = _run(
            f"zypper --non-interactive search -s --match-exact {q} 2>/dev/null", timeout=30)
        if out and code == 0:
            for line in out.splitlines():
                if "|" not in line or set(line.strip()) <= {"-", "+"}:
                    continue
                cols = [c.strip() for c in line.split("|")]
                if len(cols) < 5 or cols[2].lower() == "name":
                    continue
                version = cols[4]
                if version and version not in seen:
                    seen.add(version)
                    candidates.append({"version": version, "source": version, "kind": "repo"})
        cache_root = Path("/var/cache/zypp/packages")
        if cache_root.is_dir():
            for f in cache_root.rglob(f"{pkg_name}-*.rpm"):
                out2, code2 = _run(
                    f"rpm -qp --qf '%{{VERSION}}-%{{RELEASE}}' {shlex.quote(str(f))} 2>/dev/null")
                version = out2.strip()
                if code2 == 0 and version and version not in seen:
                    seen.add(version)
                    candidates.append({"version": version, "source": str(f), "kind": "file"})
        return candidates

    return []


def downgrade_cmd(pkg_name, candidate):
    """Ready-to-run install command for one entry from
    get_downgrade_candidates()."""
    fam = get_family()
    kind = candidate.get("kind")
    source = candidate.get("source", "")
    version = candidate.get("version", "")

    if fam == "debian":
        spec = source if kind == "file" else f"{pkg_name}={version}"
        return f"sudo -S apt-get install -y --allow-downgrades {shlex.quote(spec)}"

    if fam == "fedora":
        spec = source if kind == "file" else f"{pkg_name}-{version}"
        return f"sudo -S dnf downgrade -y {shlex.quote(spec)}"

    if fam == "suse":
        spec = source if kind == "file" else f"{pkg_name}={version}"
        return f"sudo -S zypper --non-interactive install --oldpackage {shlex.quote(spec)}"

    return None


def mark_explicit_cmd(pkg_name):
    """Mark pkg_name as explicitly/manually installed (pacman's
    `-D --asexplicit` equivalent) — so it's no longer considered an
    orphan candidate once whatever depended on it is removed."""
    fam = get_family()
    q = shlex.quote(pkg_name)
    if fam == "debian":
        return f"sudo -S apt-mark manual {q}"
    if fam == "fedora":
        return f"sudo -S dnf mark install {q}"
    return None  # no simple zypper equivalent


def mark_asdeps_cmd(pkg_name):
    """Mark pkg_name as installed-as-a-dependency (pacman's
    `-D --asdeps` equivalent) — so it becomes an orphan candidate once
    nothing else needs it any more."""
    fam = get_family()
    q = shlex.quote(pkg_name)
    if fam == "debian":
        return f"sudo -S apt-mark auto {q}"
    if fam == "fedora":
        return f"sudo -S dnf mark remove {q}"
    return None  # no simple zypper equivalent


# ─── GPG signature / stale-lock auto-fix (terminal-dialog banner) ────────────
# Mirrors dialogs.py's pacman/archlinux-keyring detection for the other
# families: a regex to recognise the failure in a command's output, and a
# ready-to-run fix command to try before automatically retrying.

_GPG_PATTERNS = {
    "debian": {
        "key_id": re.compile(r'NO_PUBKEY\s+([0-9A-Fa-f]{8,40})', re.IGNORECASE),
        "generic": re.compile(
            r'NO_PUBKEY|is not signed|could not be verified because the public key|'
            r'EXPKEYSIG|The following signatures were invalid', re.IGNORECASE),
    },
    "fedora": {
        "key_id": None,  # dnf/rpm errors don't reliably name a bare key ID the same way
        "generic": re.compile(
            r"GPG check FAILED|Import of key\(s\) didn.t succeed|"
            r"public key .* is not (installed|trusted|available)", re.IGNORECASE),
    },
    "suse": {
        "key_id": None,
        "generic": re.compile(
            r"Signature verification failed|Accepting packages with wrong digests|"
            r"file '.*' is unsigned", re.IGNORECASE),
    },
}

_LOCK_PATTERNS = {
    "debian": re.compile(
        r"Could not get lock|dpkg was interrupted|"
        r"Unable to acquire the dpkg frontend lock", re.IGNORECASE),
    "fedora": re.compile(
        r"Another app is currently holding the (yum|dnf) lock|"
        r"error: (can.t create transaction lock|db5 error)", re.IGNORECASE),
    "suse": re.compile(
        r"System management is locked|waiting for release of lock", re.IGNORECASE),
}


def detect_gpg_issue(text):
    """Return a hex key ID, "" (generic — no ID found), or None (no GPG
    issue detected in `text`)."""
    pats = _GPG_PATTERNS.get(get_family())
    if not pats:
        return None
    if pats["key_id"]:
        m = pats["key_id"].search(text)
        if m:
            return m.group(1).upper()
    if pats["generic"].search(text):
        return ""
    return None


def detect_lock_issue(text):
    pat = _LOCK_PATTERNS.get(get_family())
    return bool(pat and pat.search(text))


def gpg_fix_cmd(key_id=None):
    """Command that imports a missing/untrusted signing key (or does a
    general refresh when no specific key ID was found) so the original
    command can be safely retried afterwards."""
    fam = get_family()

    if fam == "debian":
        if key_id:
            script = (
                f"gpg --no-default-keyring "
                f"--keyring /etc/apt/trusted.gpg.d/pachul-{key_id}.gpg "
                f"--keyserver keyserver.ubuntu.com --recv-keys {key_id}"
            )
        else:
            # No specific key named: refresh whichever base keyring
            # package is present (covers the common "distro keyring is
            # outdated" case — doesn't help for a stale *third-party*
            # repo key, which has no single generic fix).
            script = (
                "(apt-get install -y --reinstall ubuntu-keyring 2>/dev/null || "
                "apt-get install -y --reinstall debian-archive-keyring 2>/dev/null); "
                "apt-get update"
            )
        return "sudo -S bash -c " + shlex.quote(script)

    if fam == "fedora":
        if key_id:
            script = (
                f"gpg --keyserver keyserver.ubuntu.com --recv-keys {key_id} "
                f"--export | rpm --import -"
            )
            return "sudo -S bash -c " + shlex.quote(script)
        return "sudo -S dnf clean all && sudo -S dnf makecache"

    if fam == "suse":
        # zypper's own flag for exactly this situation: import/trust any
        # repo signing keys that would otherwise prompt interactively.
        return "sudo -S zypper --non-interactive --gpg-auto-import-keys refresh"

    return None


def lock_fix_cmd():
    """Remove a stale package-manager lock file — but only if a safety
    check confirms nothing is actually still holding it (mirrors the
    fuser-based check dialogs.py already does for pacman's db.lck)."""
    fam = get_family()
    lock_msg = "Something is still holding the package manager lock — not removing it."
    msg_q = shlex.quote(lock_msg)

    if fam == "debian":
        paths = ("/var/lib/dpkg/lock-frontend /var/lib/dpkg/lock "
                 "/var/lib/apt/lists/lock /var/cache/apt/archives/lock")
        inner = (
            f"if command -v fuser >/dev/null 2>&1 && fuser -s {paths} 2>/dev/null; then "
            f"echo {msg_q} >&2; exit 1; "
            f"else rm -f {paths}; dpkg --configure -a; fi"
        )
        return "sudo -S bash -c " + shlex.quote(inner)

    if fam == "fedora":
        inner = (
            "if pgrep -x dnf >/dev/null 2>&1 || pgrep -x dnf5 >/dev/null 2>&1 "
            "|| pgrep -x packagekitd >/dev/null 2>&1; then "
            f"echo {msg_q} >&2; exit 1; "
            "else rm -f /var/lib/rpm/.rpm.lock; fi"
        )
        return "sudo -S bash -c " + shlex.quote(inner)

    if fam == "suse":
        inner = (
            "if pgrep -x zypper >/dev/null 2>&1 || pgrep -x packagekitd >/dev/null 2>&1; then "
            f"echo {msg_q} >&2; exit 1; "
            "else rm -f /var/run/zypp.pid; fi"
        )
        return "sudo -S bash -c " + shlex.quote(inner)

    return None


# ─── Repository management (Repo Manager / PPA / COPR / OBS) ─────────────────
# The Arch Repo Manager edits /etc/pacman.conf directly — a single file with
# a simple format. apt/dnf/zypper each spread repo config across several
# files or expose their own repo-management subcommands instead, so this is
# a distinct implementation per family rather than one shared code path.

def _debian_sources_files():
    """Every file that can define an apt repo: the classic sources.list,
    plus every *.list (classic one-line) and *.sources (deb822 — the
    default format for Ubuntu 24.04+'s own repos, and increasingly used
    by third-party repos too, e.g. NodeSource's) file under
    sources.list.d/."""
    files = []
    sl = Path("/etc/apt/sources.list")
    if sl.is_file():
        files.append(sl)
    d = Path("/etc/apt/sources.list.d")
    if d.is_dir():
        try:
            files += sorted(f for f in d.iterdir()
                            if f.is_file() and f.suffix in (".list", ".sources"))
        except OSError:
            pass
    return files


def _parse_deb822(text):
    """Yield (fields_dict, start_line, end_line) for each stanza (blocks
    separated by blank lines) in deb822-format text. Line numbers are
    0-indexed into text.splitlines(); end_line is exclusive."""
    lines = text.splitlines()
    stanzas = []
    cur, cur_key, start = {}, None, None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if cur:
                stanzas.append((cur, start, i))
                cur, cur_key, start = {}, None, None
            continue
        if stripped.startswith("#"):
            continue
        if line[:1] not in (" ", "\t") and ":" in line:
            if not cur:
                start = i
            key, _, val = line.partition(":")
            cur_key = key.strip()
            cur[cur_key] = val.strip()
        elif cur_key and line[:1] in (" ", "\t"):
            cur[cur_key] = cur[cur_key] + " " + stripped
    if cur:
        stanzas.append((cur, start, len(lines)))
    return stanzas


def list_repos():
    """Every configured repo, normalized to
    [{"id","label","url","enabled", ...format-specific extra keys}, ...].
    `id` is opaque to callers — pass the whole dict back to
    set_repo_enabled_cmd()."""
    fam = get_family()

    if fam == "debian":
        repos = []
        for f in _debian_sources_files():
            try:
                text = f.read_text(errors="replace")
            except Exception:
                continue
            if f.suffix == ".sources":
                for fields, start, end in _parse_deb822(text):
                    uris = fields.get("URIs", "")
                    suites = fields.get("Suites", "")
                    enabled = fields.get("Enabled", "yes").strip().lower() != "no"
                    label = f"{uris} {suites}".strip() or f.name
                    repos.append({
                        "id": f"{f}:{start}", "label": label, "url": uris,
                        "enabled": enabled, "file": str(f), "kind": "deb822",
                        "start": start, "end": end,
                    })
            else:
                for i, line in enumerate(text.splitlines()):
                    stripped = line.strip()
                    is_comment = stripped.startswith("#")
                    body = stripped.lstrip("#").strip()
                    if body.startswith("deb ") or body.startswith("deb-src "):
                        parts = body.split()
                        url = parts[1] if len(parts) > 1 else ""
                        suite = parts[2] if len(parts) > 2 else ""
                        repos.append({
                            "id": f"{f}:{i}", "label": f"{url} {suite}".strip(),
                            "url": url, "enabled": not is_comment,
                            "file": str(f), "kind": "oneline", "line": i,
                        })
        return repos

    if fam == "fedora":
        out, code = _run("dnf -q repolist --all 2>/dev/null", timeout=20)
        repos = []
        lines = out.splitlines() if out else []
        if code == 0 and len(lines) >= 2:
            header = lines[0]
            # Column positions vary with repo-id width, so slice by the
            # header's own column starts rather than assume fixed offsets
            # or split() (repo names routinely contain spaces).
            name_pos = header.lower().find("repo name")
            status_pos = header.lower().find("status")
            for line in lines[1:]:
                if not line.strip():
                    continue
                if name_pos > 0:
                    repoid = line[:name_pos].strip()
                    name = line[name_pos:status_pos].strip() if status_pos > name_pos else ""
                    status = line[status_pos:].strip() if status_pos > 0 else ""
                else:
                    parts = line.split()
                    repoid, name, status = (parts[0], "", "") if parts else ("", "", "")
                if not repoid:
                    continue
                repos.append({"id": repoid, "label": name or repoid, "url": "",
                              "enabled": status.lower() != "disabled", "kind": "dnf"})
        return repos

    if fam == "suse":
        out, code = _run("zypper --non-interactive repos 2>/dev/null", timeout=20)
        repos = []
        if out and code == 0:
            for line in out.splitlines():
                if "|" not in line or set(line.strip()) <= {"-", "+"}:
                    continue
                cols = [c.strip() for c in line.split("|")]
                if len(cols) < 4 or cols[1].lower() == "alias":
                    continue
                alias, name, enabled_str = cols[1], cols[2], cols[3]
                repos.append({"id": alias, "label": name or alias, "url": "",
                              "enabled": enabled_str.lower().startswith("y"), "kind": "zypper"})
        return repos

    return []


def set_repo_enabled_cmd(repo, enabled):
    """`repo`: one dict as returned by list_repos(). Returns a ready-to-run
    command that flips its enabled state, or None if that's not possible
    for this entry."""
    fam = get_family()

    if fam == "debian":
        path = Path(repo["file"])
        try:
            lines = path.read_text(errors="replace").splitlines()
        except Exception:
            return None
        if repo["kind"] == "oneline":
            i = repo.get("line", -1)
            if not (0 <= i < len(lines)):
                return None
            stripped = lines[i].strip()
            lines[i] = stripped.lstrip("#").strip() if enabled else (
                stripped if stripped.startswith("#") else "# " + stripped)
        else:  # deb822 — toggle/insert the stanza's own Enabled: field
            start, end = repo.get("start"), repo.get("end")
            if start is None or end is None:
                return None
            stanza = [ln for ln in lines[start:end] if not ln.strip().startswith("Enabled:")]
            stanza.insert(1 if stanza else 0, f"Enabled: {'yes' if enabled else 'no'}")
            lines = lines[:start] + stanza + lines[end:]
        new_text = "\n".join(lines) + "\n"
        try:
            fd, tmp_path = tempfile.mkstemp(prefix="pachul-repo-", suffix=path.suffix)
            with os.fdopen(fd, "w") as f:
                f.write(new_text)
        except OSError:
            return None
        return f"sudo -S install -m644 {shlex.quote(tmp_path)} {shlex.quote(str(path))}"

    if fam == "fedora":
        flag = "--set-enabled" if enabled else "--set-disabled"
        return f"sudo -S dnf config-manager {flag} {shlex.quote(repo['id'])}"

    if fam == "suse":
        flag = "-e" if enabled else "-d"
        return f"sudo -S zypper modifyrepo {flag} {shlex.quote(repo['id'])}"

    return None


def third_party_kind_label():
    """Short label for this distro's third-party-repo system, e.g. for an
    "Add {label}" button."""
    return {"debian": "PPA", "fedora": "COPR", "suse": "OBS Repository"}.get(get_family(), "")


def third_party_helper_available():
    """Whether the tool needed to add a third-party repo is present."""
    fam = get_family()
    if fam == "debian":
        return shutil.which("add-apt-repository") is not None
    if fam == "fedora":
        _, code = _run("dnf -q copr --help 2>/dev/null", timeout=10)
        return code == 0
    if fam == "suse":
        return shutil.which("zypper") is not None
    return False


def third_party_helper_install_cmd():
    """Installs whatever's needed for add_third_party_cmd() to work."""
    fam = get_family()
    if fam == "debian":
        return "sudo -S apt-get install -y software-properties-common"
    if fam == "fedora":
        return "sudo -S dnf install -y dnf-plugins-core"
    return None


def add_third_party_cmd(identifier):
    """identifier: "user/ppa-name" (Debian/Ubuntu PPA), "user/project"
    (Fedora COPR), or "project/repo" (openSUSE OBS), exactly as the person
    would type it on each service's own website."""
    fam = get_family()
    identifier = identifier.strip()
    if not identifier:
        return None
    if fam == "debian":
        ppa = identifier if identifier.startswith("ppa:") else f"ppa:{identifier}"
        return f"sudo -S add-apt-repository -y {shlex.quote(ppa)}"
    if fam == "fedora":
        return f"sudo -S dnf copr enable -y {shlex.quote(identifier)}"
    if fam == "suse":
        alias = re.sub(r"[^A-Za-z0-9_.-]", "-", identifier)
        return _combine_sudo(
            f"sudo -S zypper --non-interactive addrepo "
            f"obs://{shlex.quote(identifier)} {shlex.quote(alias)}",
            f"sudo -S zypper --non-interactive --gpg-auto-import-keys refresh {shlex.quote(alias)}")
    return None


def remove_third_party_cmd(identifier):
    """Reverses add_third_party_cmd() for the same identifier (Debian/
    Fedora), or removes a repo by its zypper alias (openSUSE — pass the
    alias you gave it when adding, e.g. via list_repos())."""
    fam = get_family()
    identifier = identifier.strip()
    if not identifier:
        return None
    if fam == "debian":
        ppa = identifier if identifier.startswith("ppa:") else f"ppa:{identifier}"
        return f"sudo -S add-apt-repository --remove -y {shlex.quote(ppa)}"
    if fam == "fedora":
        return f"sudo -S dnf copr remove -y {shlex.quote(identifier)}"
    if fam == "suse":
        alias = re.sub(r"[^A-Za-z0-9_.-]", "-", identifier)
        return f"sudo -S zypper --non-interactive removerepo {shlex.quote(alias)}"
    return None


def list_copr_projects():
    """Currently-enabled COPR projects (Fedora only)."""
    if get_family() != "fedora":
        return []
    out, code = _run("dnf -q copr list 2>/dev/null", timeout=15)
    if code != 0 or not out:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.lower().startswith("list of")]


def _combine_sudo(*cmds):
    """Join several `sudo -S ...`-prefixed commands into ONE `sudo -S
    bash -c '...'` invocation, so Pachul's terminal dialog only has to
    prompt for the password once.

    Why this matters: chaining separate commands as `sudo -S cmd1 &&
    sudo -S cmd2` makes sudo prompt for the password a SECOND time
    partway through — but nothing in the terminal view visually flags
    that a new prompt appeared, so it's easy to miss. When that happens
    the second command just sits there waiting for input that never
    comes: the whole chain looks like it silently did nothing (e.g. a
    single-package update never actually reinstalls the package, so it
    never disappears from the Updates list), rather than failing with a
    visible error.

    Any cmd not prefixed with "sudo -S " (e.g. a plain flatpak command
    that doesn't need root) is passed through unchanged inside the
    wrapped shell. `None`/empty entries are dropped."""
    parts = []
    for c in cmds:
        if not c:
            continue
        parts.append(c[len("sudo -S "):] if c.startswith("sudo -S ") else c)
    if not parts:
        return None
    if len(parts) == 1 and not (cmds[0] or "").startswith("sudo -S "):
        # Nothing actually needed root — don't wrap a plain command in sudo.
        return parts[0]
    inner = " && ".join(parts)
    return "sudo -S bash -c " + shlex.quote(inner)


def install_cmd(names, needed=True):
    """`names`: list[str] of package names to install/upgrade to latest."""
    quoted = " ".join(shlex.quote(n) for n in names)
    fam = get_family()
    if fam == "debian":
        return f"sudo -S apt-get install -y {quoted}"
    if fam == "fedora":
        return f"sudo -S dnf install -y {quoted}"
    if fam == "suse":
        return f"sudo -S zypper --non-interactive install {quoted}"
    return None


def install_cmd_synced(names, needed=True):
    """Same as install_cmd(), but refreshes repo metadata first (same
    reasoning as sync_db_cmd()'s callers), combined into a single sudo
    prompt via _combine_sudo() instead of two chained `sudo -S` calls."""
    return _combine_sudo(sync_db_cmd(), install_cmd(names, needed=needed))


def remove_cmd(names, purge=False):
    quoted = " ".join(shlex.quote(n) for n in names)
    fam = get_family()
    if fam == "debian":
        verb = "purge" if purge else "remove"
        return f"sudo -S apt-get {verb} -y {quoted}"
    if fam == "fedora":
        return f"sudo -S dnf remove -y {quoted}"
    if fam == "suse":
        return f"sudo -S zypper --non-interactive remove {quoted}"
    return None


def autoremove_cmd():
    """Remove every currently-unneeded dependency in one go, where the
    native tool supports that directly (apt/dnf do; zypper doesn't have a
    single-shot equivalent — use remove_cmd() with get_orphans() names
    instead on openSUSE)."""
    fam = get_family()
    if fam == "debian":
        return "sudo -S apt-get autoremove -y"
    if fam == "fedora":
        return "sudo -S dnf autoremove -y"
    return None


def sync_db_cmd():
    """Refresh repo metadata only, no upgrade."""
    fam = get_family()
    if fam == "debian":
        return "sudo -S apt-get update"
    if fam == "fedora":
        return "sudo -S dnf makecache"
    if fam == "suse":
        return "sudo -S zypper --non-interactive refresh"
    return None


def upgrade_all_cmd():
    fam = get_family()
    if fam == "debian":
        return _combine_sudo("sudo -S apt-get update", "sudo -S apt-get upgrade -y")
    if fam == "fedora":
        return "sudo -S dnf upgrade -y"
    if fam == "suse":
        return _combine_sudo("sudo -S zypper --non-interactive refresh",
                              "sudo -S zypper --non-interactive update")
    return None


def clean_cache_cmd():
    fam = get_family()
    if fam == "debian":
        return "sudo -S apt-get clean"
    if fam == "fedora":
        return "sudo -S dnf clean packages"
    if fam == "suse":
        return "sudo -S zypper clean"
    return None


CACHE_DIR_BY_FAMILY = {
    "debian": "/var/cache/apt/archives",
    "fedora": "/var/cache/dnf",
    "suse":   "/var/cache/zypp/packages",
}


def get_package_cache_size():
    fam = get_family()
    path = CACHE_DIR_BY_FAMILY.get(fam)
    if not path or not os.path.isdir(path):
        return "N/A"
    return _fmt_size(_dir_size(path))


# ─── Hold / unhold (pacman's IgnorePkg equivalent) ────────────────────────────
# Unlike pacman (a config-file edit), apt and zypper both hold packages via
# a direct, built-in command — no file to edit/copy. dnf has no built-in
# equivalent (the versionlock plugin isn't installed by default), so
# holding is simply unavailable there.

def hold_cmd(pkg_name, hold):
    fam = get_family()
    q = shlex.quote(pkg_name)
    if fam == "debian":
        return f"sudo -S apt-mark {'hold' if hold else 'unhold'} {q}"
    if fam == "suse":
        return f"sudo -S zypper --non-interactive {'addlock' if hold else 'removelock'} {q}"
    return None  # fedora: no reliable built-in equivalent without extra plugins


def hold_cmd_bulk(pkg_names, hold):
    fam = get_family()
    quoted = " ".join(shlex.quote(n) for n in pkg_names)
    if fam == "debian":
        return f"sudo -S apt-mark {'hold' if hold else 'unhold'} {quoted}"
    if fam == "suse":
        verb = "addlock" if hold else "removelock"
        return _combine_sudo(*(f"sudo -S zypper --non-interactive {verb} {shlex.quote(n)}"
                                for n in pkg_names))
    return None


def get_held_packages():
    """Packages currently held/locked from upgrades — pacman's IgnorePkg
    equivalent for apt/zypper."""
    fam = get_family()
    if fam == "debian":
        out, code = _run("apt-mark showhold 2>/dev/null")
        return set(out.splitlines()) if (out and code == 0) else set()
    if fam == "suse":
        out, code = _run("zypper --non-interactive locks 2>/dev/null")
        names = set()
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("|")]
            # Typical row: "1 | name | Type | package | Match Type | glob"
            if len(parts) >= 2 and parts[0].isdigit():
                names.add(parts[1])
        return names if code == 0 else set()
    return set()


# ─── Search ────────────────────────────────────────────────────────────────────

def search_cmd(query):
    fam = get_family()
    q = shlex.quote(query)
    if fam == "debian":
        return f"apt-cache search {q}"
    if fam == "fedora":
        return f"dnf -q search {q} 2>/dev/null"
    if fam == "suse":
        return f"zypper --non-interactive search --details {q} 2>/dev/null"
    return None


def parse_search(out):
    """Parse this family's search_cmd() output into
    [{"name","version","repo","description","status","foreign"}, ...].
    Version/repo are left blank where the tool's search output doesn't
    include them (apt-cache search / dnf search) — the same "fill in on
    click" convention already used for the AUR-discoverability list."""
    fam = get_family()
    results = []

    if fam == "debian":
        # "pkgname - one-line description"
        for line in out.splitlines():
            name, sep, desc = line.partition(" - ")
            name = name.strip()
            if not (name and sep):
                continue
            results.append({"name": name, "version": "", "repo": "",
                            "description": desc.strip(), "status": "available",
                            "foreign": False})
        return results

    if fam == "fedora":
        # "pkgname.arch : one-line summary" (plus header lines to skip)
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith(("=", "Last metadata")):
                continue
            m = re.match(r"^(\S+)\.\S+\s*:\s*(.*)$", line)
            if not m:
                continue
            results.append({"name": m.group(1), "version": "", "repo": "",
                            "description": m.group(2).strip(), "status": "available",
                            "foreign": False})
        return results

    if fam == "suse":
        # Table: "S | Name | Type | Version | Arch | Repository"
        for line in out.splitlines():
            if "|" not in line or set(line.strip()) <= {"-", "+"}:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 4 or cols[1].lower() == "name":
                continue
            name, version, repo = cols[1], cols[3] if len(cols) > 3 else "", \
                cols[-1] if len(cols) > 4 else ""
            if not name:
                continue
            results.append({"name": name, "version": version, "repo": repo,
                            "description": "", "status": "available",
                            "foreign": False})
        return results

    return results


# ─── Package info (normalised to pacman -Qi/-Si's "Key : Value" shape) ────────
# window.py's `_parse_pkginfo` already parses generic "Key : Value" text —
# building the SAME field names here means the existing UI needs no
# changes at all to display info for apt/dnf/zypper packages.

_RPM_LIST_FLAGS = {
    "requires":  "--requires",
    "provides":  "--provides",
    "conflicts": "--conflicts",
    "obsoletes": "--obsoletes",
}


def _rpm_list(q, flag):
    out, code = _run(f"rpm -q {flag} {q} 2>/dev/null")
    if code != 0 or not out:
        return "None"
    items = [ln.strip() for ln in out.splitlines()
             if ln.strip() and not ln.startswith("rpmlib(") and not ln.startswith("(none)")]
    return ", ".join(items) if items else "None"


def is_installed(pkg_name):
    """Cheap installed/not-installed check, used where the caller just
    needs a yes/no rather than full package info."""
    fam = get_family()
    q = shlex.quote(pkg_name)
    if fam == "debian":
        if native.apt_available():
            try:
                return native.apt_is_installed(pkg_name)
            except Exception:
                pass
        out, code = _run(f"dpkg-query -W -f='${{Status}}' {q} 2>/dev/null")
        return code == 0 and "installed" in out
    if fam in ("fedora", "suse"):
        if fam == "fedora":
            if native.dnf5_available():
                try:
                    return native.dnf5_is_installed(pkg_name)
                except Exception:
                    pass
            if native.dnf_available():
                try:
                    return native.dnf_is_installed(pkg_name)
                except Exception:
                    pass
        _, code = _run(f"rpm -q {q} 2>/dev/null")
        return code == 0
    return False


def get_package_info_text(pkg_name):
    """Returns pacman-style 'Key : Value' info text for pkg_name, or None
    if the package can't be found installed or in any configured repo."""
    fam = get_family()
    q = shlex.quote(pkg_name)

    if fam == "debian":
        if native.apt_available():
            try:
                text = native.apt_package_info_text(pkg_name)
                if text:
                    return text
            except Exception:
                pass  # fall through to the CLI path below
        out, code = _run(f"dpkg -s {q} 2>/dev/null")
        installed = bool(out) and code == 0
        if not installed:
            out, code = _run(f"apt-cache show {q} 2>/dev/null")
        if not (out and code == 0):
            return None
        f = _parse_colon_fields(out)
        if not f:
            return None

        install_date = "None"
        reason = "None"
        if installed:
            reason = "Explicitly installed"
            auto_out, auto_code = _run(f"apt-mark showauto {q} 2>/dev/null")
            if auto_code == 0 and pkg_name in auto_out.splitlines():
                reason = "Installed as a dependency for another package"
            try:
                mtime = Path(f"/var/lib/dpkg/info/{pkg_name}.list").stat().st_mtime
                import datetime
                install_date = datetime.datetime.fromtimestamp(mtime).strftime("%a %d %b %Y %H:%M:%S")
            except Exception:
                pass

        size_kb = f.get("Installed-Size", "")
        size_h = _fmt_size(float(size_kb) * 1024) if size_kb.strip().isdigit() else "None"
        optional = ", ".join(x for x in (f.get("Recommends", ""), f.get("Suggests", "")) if x) or "None"

        return (
            f"Name           : {f.get('Package', pkg_name)}\n"
            f"Version        : {f.get('Version', '')}\n"
            f"Description    : {f.get('Description', '') or '—'}\n"
            f"Architecture   : {f.get('Architecture', '')}\n"
            f"URL            : {f.get('Homepage', 'None')}\n"
            f"Licenses       : None\n"
            f"Groups         : {f.get('Section', 'None')}\n"
            f"Depends On     : {f.get('Depends', 'None')}\n"
            f"Optional Deps  : {optional}\n"
            f"Required By    : None\n"
            f"Conflicts With : {f.get('Conflicts', 'None')}\n"
            f"Provides       : {f.get('Provides', 'None')}\n"
            f"Replaces       : {f.get('Replaces', 'None')}\n"
            f"Installed Size : {size_h}\n"
            f"Packager       : {f.get('Maintainer', 'None')}\n"
            f"Build Date     : None\n"
            f"Install Date   : {install_date}\n"
            f"Install Reason : {reason}\n"
        )

    if fam in ("fedora", "suse"):
        out, code = _run(f"rpm -qi {q} 2>/dev/null")
        installed = bool(out) and code == 0 and "is not installed" not in out
        if not installed:
            if fam == "fedora":
                out, code = _run(f"dnf -q info {q} 2>/dev/null")
            else:
                out, code = _run(f"zypper --non-interactive info {q} 2>/dev/null")
            if not (out and code == 0):
                return None
        f = _parse_colon_fields(out)
        if not f:
            return None

        version = f.get("Version", "")
        release = f.get("Release", "")
        full_version = f"{version}-{release}" if release else version
        size = f.get("Size", "")
        size_h = _fmt_size(size) if size.strip().isdigit() else "None"

        reason = "None"
        if installed:
            reason = "Explicitly installed"
            if fam == "fedora":
                native_reason = None
                if native.dnf5_available():
                    try:
                        native_reason = native.dnf5_package_reason(pkg_name)
                    except Exception:
                        native_reason = None
                if native_reason is not None:
                    if native_reason == "dependency":
                        reason = "Installed as a dependency for another package"
                else:
                    r_out, r_code = _run(
                        f"dnf -q repoquery --installed --qf '%{{reason}}' {q} 2>/dev/null")
                    if r_code == 0 and r_out.strip() == "dependency":
                        reason = "Installed as a dependency for another package"

        return (
            f"Name           : {f.get('Name', pkg_name)}\n"
            f"Version        : {full_version}\n"
            f"Description    : {f.get('Description', '') or '—'}\n"
            f"Architecture   : {f.get('Architecture', '')}\n"
            f"URL            : {f.get('URL', 'None')}\n"
            f"Licenses       : {f.get('License', 'None')}\n"
            f"Groups         : {f.get('Group', 'None')}\n"
            f"Depends On     : {_rpm_list(q, '--requires') if installed else 'None'}\n"
            f"Optional Deps  : None\n"
            f"Required By    : None\n"
            f"Conflicts With : {_rpm_list(q, '--conflicts') if installed else 'None'}\n"
            f"Provides       : {_rpm_list(q, '--provides') if installed else 'None'}\n"
            f"Replaces       : {_rpm_list(q, '--obsoletes') if installed else 'None'}\n"
            f"Installed Size : {size_h}\n"
            f"Packager       : {f.get('Packager', f.get('Vendor', 'None'))}\n"
            f"Build Date     : {f.get('Build Date', 'None')}\n"
            f"Install Date   : {f.get('Install Date', 'None') if installed else 'None'}\n"
            f"Install Reason : {reason}\n"
        )

    return None


# ─── Package files / file-owner search ────────────────────────────────────────

def get_package_files(pkg_name):
    """Returns ["pkgname /path", ...] lines, same shape as pacman -Ql."""
    fam = get_family()
    q = shlex.quote(pkg_name)
    if fam == "debian":
        out, code = _run(f"dpkg -L {q} 2>/dev/null")
    elif fam in ("fedora", "suse"):
        out, code = _run(f"rpm -ql {q} 2>/dev/null")
    else:
        return None
    if not (out and code == 0):
        return None
    return [f"{pkg_name} {line}" for line in out.splitlines() if line.strip()]


def sync_files_db_cmd():
    """Command for the "file search isn't ready yet" banner's Sync Now
    button. Only really needed on Debian, where file-owner search depends
    on the optional apt-file tool and its own separately-updated cache;
    dnf/zypper need no such separate step (files_db_available() already
    reports True for them, so this never actually gets called there)."""
    if get_family() == "debian":
        return _combine_sudo("sudo -S apt-get install -y apt-file", "sudo -S apt-file update")
    return None


def files_db_available():
    """Whether file->package search is ready to use. Unlike pacman -Fx
    (which needs an explicit `pacman -Fy` sync first), dnf/zypper query
    their existing metadata directly with no separate sync step; apt
    needs the optional apt-file tool installed."""
    fam = get_family()
    if fam == "debian":
        return shutil.which("apt-file") is not None
    if fam in ("fedora", "suse"):
        return True
    return False


_DNF_PROVIDES_FIELD_KEYS = {"Repo", "Matched from", "Filename", "Provide"}


def _parse_dnf_provides(out):
    results = []
    current = None
    for raw_line in out.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("Last metadata"):
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        if key in _DNF_PROVIDES_FIELD_KEYS:
            if key == "Filename" and current is not None:
                current["files"].append(rest)
            continue
        # New package header, e.g. "vim-enhanced-2:9.1.16-1.fc41.x86_64 : summary"
        # rpartition on " : " so an epoch's own colon isn't mistaken for it.
        spec = line.rpartition(" : ")[0].strip() or line.strip()
        if not spec:
            continue
        current = {"pkg": spec, "version": "", "files": []}
        results.append(current)
    return results


def search_file_owner(query):
    """Which package(s) own file paths matching `query`. Returns the same
    [{"pkg","version","files":[...]}] shape backend.py's pacman -Fx
    parsing already produces."""
    fam = get_family()
    q = shlex.quote(query)

    if fam == "debian":
        out, code = _run(f"apt-file search {q} 2>/dev/null", timeout=30)
        if not (out and code == 0):
            return []
        by_pkg = {}
        for line in out.splitlines():
            pkg, sep, path = line.partition(":")
            pkg, path = pkg.strip(), path.strip()
            if not (pkg and sep):
                continue
            by_pkg.setdefault(pkg, {"pkg": pkg, "version": "", "files": []})
            by_pkg[pkg]["files"].append(path)
        return list(by_pkg.values())

    if fam == "fedora":
        out, code = _run(f"dnf -q provides {q} 2>/dev/null", timeout=30)
        return _parse_dnf_provides(out) if (out and code == 0) else []

    if fam == "suse":
        out, code = _run(f"zypper --non-interactive wp {q} 2>/dev/null", timeout=30)
        if not (out and code == 0):
            return []
        results = []
        for line in out.splitlines():
            if "|" not in line or set(line.strip()) <= {"-", "+"}:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 2 or cols[0].lower() in ("s", ""):
                continue
            name = cols[1] if len(cols) > 1 else ""
            if name and name.lower() != "name":
                results.append({"pkg": name, "version": "", "files": [query]})
        return results

    return []


# ─── Installed-package listing ─────────────────────────────────────────────────

def _installed_fingerprint_cmd():
    """Command whose full stdout gets hashed by backend.py as a cheap
    'has anything changed since last time?' fingerprint — same role as
    pacman -Q for the Arch path."""
    fam = get_family()
    if fam == "debian":
        return "dpkg-query -W -f='${Package} ${Version}\\n' 2>/dev/null"
    if fam in ("fedora", "suse"):
        return "rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}\\n' 2>/dev/null"
    return None


def get_installed_fingerprint():
    """(fingerprint, raw_text) — python3-apt fast path on Debian when it's
    available (see pkgmanager_native.py), else the CLI-based fingerprint
    via _installed_fingerprint_cmd(). Either way `raw_text` is "name
    version" lines, so backend.get_packages()'s own parsing of it doesn't
    need to know or care which path was used."""
    if get_family() == "debian" and native.apt_available():
        try:
            return native.apt_installed_fingerprint()
        except Exception:
            pass  # fall through to the CLI path below
    cmd = _installed_fingerprint_cmd()
    if not cmd:
        return None
    out, code = _run(cmd)
    if code != 0 or not out:
        return None
    import hashlib
    return hashlib.md5(out.encode()).hexdigest(), out


def parse_installed(raw_out):
    """Parse _installed_fingerprint_cmd()'s output into the same
    {name: {"name","version","repo","status","description","foreign"}}
    shape backend.py builds from `pacman -Q`."""
    installed = {}
    for line in raw_out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            installed[parts[0]] = {
                "name": parts[0], "version": parts[1],
                "repo": "local", "status": "installed",
                "description": "", "foreign": False,
            }
    return installed


# ─── Available-package listing (pacman sync-db equivalent) ───────────────────
# These subprocess calls are slower than pacman's offline .db-tarball
# parsing, so backend.py caches the result the same way it already
# caches the pacman sync db (same TTL, same cache file).

def _build_available_debian():
    """List every package apt knows about — via python3-apt directly when
    available (fast: ~3s for a full Ubuntu package set in testing), else
    `apt-cache dumpavail` (slower: ~10-20s in the same testing, but works
    with just the `apt` CLI, no extra package needed).

    Earlier revision of the CLI fallback path parsed
    /var/lib/apt/lists/*_Packages directly (mirroring how pacman's own
    .db tarballs get parsed, with no subprocess needed) — but modern apt
    compresses those list files on-disk (lz4 by default on current
    Ubuntu/Debian, sometimes gzip or zstd instead) rather than keeping
    them as plain text, and the compression scheme in use isn't something
    Pachul should have to guess at. `apt-cache dumpavail` asks apt itself
    to decompress and dump everything, however it's stored."""
    if native.apt_available():
        try:
            return native.apt_build_available_packages()
        except Exception:
            pass  # fall through to the CLI path below

    pkgs = {}
    out, code = _run("apt-cache dumpavail 2>/dev/null", timeout=60)
    if out and code == 0:
        for block in out.split("\n\n"):
            if not block.strip():
                continue
            fields = _parse_colon_fields(block)
            name = fields.get("Package")
            if name and name not in pkgs:
                pkgs[name] = {"repo": "", "version": fields.get("Version", ""),
                              "description": fields.get("Description", "")}
    return pkgs


def _build_available_fedora():
    if native.dnf5_available():
        try:
            return native.dnf5_build_available_packages()
        except Exception:
            pass  # fall through — see pkgmanager_native.py's module
                  # docstring: neither dnf5 nor dnf4 native path here has
                  # been verified against a real system, so either one
                  # can legitimately fail and should just degrade quietly.
    if native.dnf_available():
        try:
            return native.dnf_build_available_packages()
        except Exception:
            pass
    out, code = _run(
        "dnf -q repoquery --available "
        "--qf '%{name}|%{version}-%{release}|%{reponame}|%{summary}' 2>/dev/null",
        timeout=90)
    pkgs = {}
    if out and code == 0:
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                name, version, repo, desc = parts
                if name not in pkgs:
                    pkgs[name] = {"repo": repo, "version": version, "description": desc}
    return pkgs


def _build_available_suse():
    out, code = _run("zypper --non-interactive packages 2>/dev/null", timeout=90)
    pkgs = {}
    if out and code == 0:
        for line in out.splitlines():
            if "|" not in line or set(line.strip()) <= {"-", "+"}:
                continue
            cols = [c.strip() for c in line.split("|")]
            # Typical columns: S | Repository | Name | Version | Arch
            if len(cols) < 4 or cols[2].lower() == "name":
                continue
            name, version, repo = cols[2], cols[3], cols[1]
            if name and name not in pkgs:
                pkgs[name] = {"repo": repo, "version": version, "description": ""}
    return pkgs


def build_available_packages():
    """Returns {name: {"repo","version","description"}}, the same shape
    backend._build_syncdb() returns for pacman."""
    fam = get_family()
    if fam == "debian":
        return _build_available_debian()
    if fam == "fedora":
        return _build_available_fedora()
    if fam == "suse":
        return _build_available_suse()
    return {}


def python3_apt_install_cmd():
    """Installs python3-apt, the native binding used throughout this file
    (see pkgmanager_native.py) for faster package info/listing/updates on
    Debian-family distros. A plain apt install — python3-apt ships as a
    regular Debian/Ubuntu package, no PPA or build step needed, unlike
    Arch's paru (which has no official-repo equivalent and must be built
    from the AUR)."""
    return "sudo -S apt-get install -y python3-apt"


def dnf_native_install_cmd():
    """Installs python3-libdnf5, the native binding used throughout this
    file (see pkgmanager_native.py, dnf5_available()) for faster package
    info/listing/updates on Fedora. dnf5 has been Fedora's default package
    manager since Fedora 41, so this targets its binding rather than the
    older python3-dnf (classic dnf4's binding) — see native.dnf_available(),
    which still accepts either as a fallback if dnf5's isn't present."""
    return "sudo -S dnf install -y python3-libdnf5"


def config_backup_sources():
    """List of config paths worth backing up, per distro family — only
    entries that actually exist on this system are used by the caller
    (see show_config_backup_dialog()), so it's fine for this list to be
    a superset. Deliberately narrow: system identity/boot config, not a
    general-purpose /etc backup."""
    common = ["/etc/fstab", "/etc/hosts", "/etc/hostname", "/etc/default/grub"]
    fam = get_family()
    if fam == "arch":
        return common + [
            "/etc/pacman.conf", "/etc/pacman.d/mirrorlist",
            "/etc/mkinitcpio.conf", "/etc/locale.conf", "/etc/locale.gen",
            "/etc/vconsole.conf", "/boot/grub/grub.cfg",
        ]
    if fam == "debian":
        return common + [
            "/etc/apt/sources.list", "/etc/apt/sources.list.d",
            "/etc/default/locale", "/etc/default/keyboard",
            "/etc/netplan", "/etc/network/interfaces",
            "/boot/grub/grub.cfg",
        ]
    if fam == "fedora":
        return common + [
            "/etc/dnf/dnf.conf", "/etc/yum.repos.d",
            "/etc/locale.conf", "/etc/vconsole.conf",
            "/boot/grub2/grub.cfg",
        ]
    if fam == "suse":
        return common + [
            "/etc/zypp/zypp.conf", "/etc/zypp/repos.d",
            "/etc/locale.conf", "/etc/vconsole.conf",
            "/boot/grub2/grub.cfg",
        ]
    return common


def installed_package_list_cmd():
    """(shell_cmd, is_explicit_only) — a command that prints one package
    name per line, for the config-backup's package-list export. Where
    the package manager can tell explicitly-installed apart from
    pulled-in-as-dependency (Arch, Debian, Fedora), this uses that —
    matching what the backup is actually for (being able to reinstall
    just what you chose, not every transitive dependency too). openSUSE
    has no equally simple built-in for that distinction, so it falls
    back to every installed package via rpm."""
    fam = get_family()
    if fam == "arch":
        return ("pacman -Qqe", True)
    if fam == "debian":
        return ("apt-mark showmanual", True)
    if fam == "fedora":
        return ("dnf repoquery --userinstalled --qf '%{name}' 2>/dev/null", True)
    if fam == "suse":
        return ("rpm -qa --qf '%{NAME}\\n' | sort", False)
    return (None, False)


def ca_certificates_refresh_cmd():
    """(install_cmd, refresh_note) — reinstalls the CA certificate bundle
    and regenerates the system trust store, per distro family. Package
    name and trust-store command genuinely differ per family (verified
    against each distro's own docs):
      - Arch: ca-certificates(-mozilla/-utils); trust store is rebuilt via
        'trust extract-compat' (the pacman package hook runs the same
        thing automatically on every upgrade, so this is only needed if
        that hook was skipped/failed).
      - Debian/Ubuntu/Mint: ca-certificates; 'update-ca-certificates'.
      - Fedora: ca-certificates; 'update-ca-trust extract'.
      - openSUSE: ca-certificates; 'update-ca-certificates' (yes, same
        command name as Debian's, but a different implementation — see
        openSUSE/ca-certificates upstream).
    """
    fam = get_family()
    if fam == "arch":
        return ("sudo -S pacman -S --needed --noconfirm "
                "ca-certificates ca-certificates-mozilla ca-certificates-utils "
                "&& sudo -S trust extract-compat")
    if fam == "debian":
        return "sudo -S apt-get install -y --reinstall ca-certificates && sudo -S update-ca-certificates"
    if fam == "fedora":
        return "sudo -S dnf reinstall -y ca-certificates && sudo -S update-ca-trust extract"
    if fam == "suse":
        return "sudo -S zypper --non-interactive install --force ca-certificates && sudo -S update-ca-certificates"
    return None


def installed_repos():
    """{pkgname: repo_label} for currently installed packages — Debian
    only for now (via python3-apt origins, see
    pkgmanager_native.apt_installed_repos()). Used to populate the
    sidebar's per-repo categories for installed packages, since
    build_available_packages()'s bulk apt path leaves "repo" blank for
    performance reasons. Returns {} without python3-apt (an
    apt-cache-policy-per-package CLI fallback would mean one subprocess
    per installed package — too slow to be worth it for what's a
    nice-to-have sidebar grouping) or on Fedora/openSUSE, where
    build_available_packages() already fills in a real repo name for
    every package, installed or not."""
    if get_family() != "debian":
        return {}
    if native.apt_available():
        try:
            return native.apt_installed_repos()
        except Exception:
            pass
    return {}


def check_updates_preview_cmd():
    """Raw shell snippet that lists pending updates directly in a
    terminal — used for the "Check for Updates" preview dialog, which
    just runs a command and shows the person its output (unlike
    check_updates() above, which parses everything into structured data
    for the main package list)."""
    fam = get_family()
    if fam == "debian":
        return "apt list --upgradable 2>/dev/null | tail -n +2"
    if fam == "fedora":
        return "dnf -q list --upgrades 2>/dev/null"
    if fam == "suse":
        return "zypper --non-interactive list-updates 2>/dev/null"
    return None


# ─── Updates ────────────────────────────────────────────────────────────────────

def check_updates():
    """Pending updates as [{"name","old","new","aur":False}, ...]."""
    fam = get_family()

    if fam == "debian":
        if native.apt_available():
            try:
                return native.apt_check_updates()
            except Exception:
                pass
        out, code = _run("apt list --upgradable 2>/dev/null", timeout=60)
        updates = []
        if out and code == 0:
            pat = re.compile(r"^(\S+)/\S+\s+(\S+)\s+\S+\s+\[upgradable from:\s*(\S+)\]")
            for line in out.splitlines():
                m = pat.match(line.strip())
                if m:
                    name, new, old = m.group(1), m.group(2), m.group(3)
                    updates.append({"name": name, "old": old, "new": new, "aur": False})
        return updates

    if fam == "fedora":
        if native.dnf5_available():
            try:
                return native.dnf5_check_updates()
            except Exception:
                pass
        if native.dnf_available():
            try:
                return native.dnf_check_updates()
            except Exception:
                pass
        out, code = _run("dnf -q list --upgrades 2>/dev/null", timeout=60)
        updates = []
        if code in (0, 100) and out:
            installed_out, _ = _run(_installed_fingerprint_cmd() or "", timeout=30)
            installed = parse_installed(installed_out) if installed_out else {}
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 2 or "." not in parts[0]:
                    continue
                name = parts[0].rsplit(".", 1)[0]
                new = parts[1]
                old = installed.get(name, {}).get("version", "")
                updates.append({"name": name, "old": old, "new": new, "aur": False})
        return updates

    if fam == "suse":
        out, code = _run("zypper --non-interactive list-updates 2>/dev/null", timeout=60)
        updates = []
        if out and code == 0:
            for line in out.splitlines():
                if "|" not in line or set(line.strip()) <= {"-", "+"}:
                    continue
                cols = [c.strip() for c in line.split("|")]
                # Typical columns: S | Repository | Name | Current | Available | Arch
                if len(cols) < 5 or cols[2].lower() == "name":
                    continue
                name, old, new = cols[2], cols[3], cols[4]
                updates.append({"name": name, "old": old, "new": new, "aur": False})
        return updates

    return []


# ─── Orphans (packages installed as a dependency, now unneeded) ──────────────

def get_orphans():
    fam = get_family()

    if fam == "debian":
        if native.apt_available():
            try:
                return native.apt_orphans()
            except Exception:
                pass
        out, code = _run("apt-get --simulate autoremove 2>/dev/null", timeout=30)
        orphans = []
        if out and code == 0:
            for line in out.splitlines():
                if line.startswith("Remv "):
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[1]
                        ver_m = re.search(r"\[([^\]]+)\]", line)
                        orphans.append({"name": name, "version": ver_m.group(1) if ver_m else ""})
        return orphans

    if fam == "fedora":
        out, code = _run(
            "dnf -q repoquery --unneeded --qf '%{name} %{version}-%{release}' 2>/dev/null",
            timeout=30)
        orphans = []
        if out and code == 0:
            for line in out.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    orphans.append({"name": parts[0], "version": parts[1]})
        return orphans

    if fam == "suse":
        # Not all zypper versions support --orphaned; fails silently to []
        # on the ones that don't, same "just no orphans shown" degradation
        # the app already applies everywhere else.
        out, code = _run("zypper --non-interactive packages --orphaned 2>/dev/null", timeout=30)
        orphans = []
        if out and code == 0:
            for line in out.splitlines():
                if "|" not in line or set(line.strip()) <= {"-", "+"}:
                    continue
                cols = [c.strip() for c in line.split("|")]
                if len(cols) < 4 or cols[2].lower() == "name":
                    continue
                orphans.append({"name": cols[2], "version": cols[3]})
        return orphans

    return []


# ─── Explicit / "manually installed" package export ───────────────────────────

def get_explicit_packages():
    fam = get_family()
    if fam == "debian":
        if native.apt_available():
            try:
                return native.apt_explicit_packages()
            except Exception:
                pass
        out, code = _run("apt-mark showmanual 2>/dev/null", timeout=15)
        return out.splitlines() if (out and code == 0) else []
    if fam == "fedora":
        out, code = _run("dnf -q repoquery --userinstalled --qf '%{name}' 2>/dev/null", timeout=30)
        return out.splitlines() if (out and code == 0) else []
    if fam == "suse":
        # No direct zypper equivalent to "explicitly installed" tracking;
        # every installed package is returned rather than silently
        # under-reporting what the person actually asked for.
        out, code = _run("rpm -qa --qf '%{NAME}\\n' 2>/dev/null", timeout=15)
        return out.splitlines() if (out and code == 0) else []
    return []


# ─── Config-file conflicts (.pacnew/.pacsave equivalent) ──────────────────────
# Debian: dpkg renames the *old* file to .dpkg-old and drops the new one
#         in as .dpkg-dist when a locally-modified conffile would
#         otherwise be overwritten (or ucf-managed files use .ucf-dist).
# RPM (Fedora/openSUSE): rpm keeps the new file as .rpmnew, or backs up
#         the modified original as .rpmsave.

def get_config_conflict_files():
    """Same shape as backend.get_pacnew_files(): [{"new","orig","kind"}].
    `new` is always the file dialogs.py's pacdiff UI would `mv` over `orig`
    to apply, or `rm` to discard — for a *_dist/*_new file that means the
    newly-shipped default; for a *_old/*_save backup file it means the
    previous, locally-modified version pacman/dpkg/rpm set aside instead
    of overwriting outright. This mirrors exactly how pacman's own
    .pacnew/.pacsave pair already works in the existing UI code."""
    fam = get_family()
    if fam == "debian":
        patterns = "-name '*.dpkg-dist' -o -name '*.dpkg-old' -o -name '*.ucf-dist'"
        suffix_kind = {".dpkg-dist": "new", ".dpkg-old": "old", ".ucf-dist": "new"}
    elif fam in ("fedora", "suse"):
        patterns = "-name '*.rpmnew' -o -name '*.rpmsave'"
        suffix_kind = {".rpmnew": "new", ".rpmsave": "old"}
    else:
        return []

    out, _ = _run(f"find /etc /usr /boot /opt -xdev \\( {patterns} \\) 2>/dev/null", timeout=30)
    files = []
    for line in out.splitlines():
        line = line.strip()
        for suffix, kind in suffix_kind.items():
            if line.endswith(suffix):
                files.append({
                    "new": line,
                    "orig": line[: -len(suffix)],
                    "kind": kind,
                })
                break
    return files


# ─── Package transaction history ──────────────────────────────────────────────

def get_package_history(limit=500):
    """Best-effort recent install/remove/upgrade history, in the same
    shape as backend.get_pacman_history(): [{"time","action","name","version"}]."""
    fam = get_family()
    entries = []

    if fam == "debian":
        log = Path("/var/log/dpkg.log")
        try:
            lines = log.read_text(errors="replace").splitlines()
        except Exception:
            return []
        # "2026-01-15 10:22:31 status installed vim:amd64 2.2-1"
        # "2026-01-15 10:22:30 install vim:amd64 <none> 2.2-1"
        pat = re.compile(
            r"^(\S+ \S+) (install|upgrade|remove|purge) (\S+):\S+ \S+ (\S+)")
        for line in lines:
            m = pat.match(line)
            if m:
                ts, action, name, ver = m.groups()
                entries.append({"time": ts, "action": action, "name": name, "version": ver})
        entries.reverse()
        return entries[:limit]

    if fam == "fedora":
        out, code = _run("dnf -q history list 2>/dev/null", timeout=15)
        if not (out and code == 0):
            return []
        for line in out.splitlines():
            parts = line.split("|")
            if len(parts) >= 3 and parts[0].strip().isdigit():
                entries.append({"time": parts[2].strip(), "action": parts[1].strip(),
                                "name": "", "version": ""})
        return entries[:limit]

    if fam == "suse":
        log = Path("/var/log/zypp/history")
        try:
            lines = log.read_text(errors="replace").splitlines()
        except Exception:
            return []
        # "2026-01-15 10:22:31|install|vim|9.1-1|x86_64|..."
        for line in lines:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                entries.append({"time": parts[0].strip(), "action": parts[1].strip(),
                                "name": parts[2].strip(), "version": parts[3].strip()})
        entries.reverse()
        return entries[:limit]

    return []
