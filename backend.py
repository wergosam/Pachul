"""
Pachul — backend.py
Data layer for the whole app: package queries, AUR search, update checks,
orphan detection, system information and the demo-mode sample data.

Cache layout (below ~/.cache/pachul/)
-------------------------------------
  installed.json   output of pacman -Q / -Qm; stale as soon as pacman -Q differs
  syncdb.json      the repository index (pacman -Sl); refreshed every 6 hours
  packages.json    the merged package list, so the next start can show it at once
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import concurrent.futures
from pathlib import Path
from gi.repository import GLib

import distro
import pkgmanager


# ─── Cache paths ──────────────────────────────────────────────────────────────

CACHE_DIR      = Path.home() / ".cache" / "pachul"
INSTALLED_CACHE = CACHE_DIR.joinpath("installed.json")
SYNCDB_CACHE = CACHE_DIR.joinpath("syncdb.json")
PKG_CACHE = CACHE_DIR.joinpath("packages.json")
FLATPAK_REMOTE_CACHE = CACHE_DIR / "flatpak_remote.json"
AUR_NAMES_CACHE = CACHE_DIR / "aur_names.json"
AUR_META_CACHE = CACHE_DIR / "aur_meta.json"   # name -> [version, description]
SNAP_CATALOG_CACHE = CACHE_DIR / "snap_catalog.json"
APP_VERSION    = "2.3.1"   # shown in the About dialog — bump on every release
CACHE_VERSION  = 4   # bump when the cached package schema changes, to force a rebuild
SYNCDB_TTL     = 6 * 3600   # 6 hours
FLATPAK_REMOTE_TTL = 6 * 3600   # same cadence as pacman's syncdb
# packages.gz changes constantly in aggregate (packages come and go every
# day), but any single refresh is just as informative a day later, and the
# AUR explicitly asks bulk consumers of this dump not to poll it more often
# than once every 24h.
AUR_NAMES_TTL = 24 * 3600
AUR_META_TTL = 24 * 3600   # same cadence — one ~10 MB download per day at most
SNAP_CATALOG_TTL = 6 * 3600   # same cadence as the Flatpak remote catalog

def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _read_json(path):
    """Load a JSON file; any problem (missing, corrupt) simply yields None."""
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def _write_json(path, data):
    """Write atomically (temp file, then rename); failures are swallowed."""
    try:
        _ensure_cache_dir()
        staging = path.with_suffix(".tmp")
        staging.write_text(json.dumps(data, separators=(",", ":")))
        staging.replace(path)
    except Exception:
        pass

# ─── User settings ────────────────────────────────────────────────────────────

CONFIG_DIR    = Path.home() / ".config" / "pachul"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
_DEFAULT_SETTINGS = {
    "aur_helper":               "auto",   # auto | pachuli | yay | paru | pikaur | none
    "include_aur_updates":      True,
    "confirm_remove":           True,
    "check_updates_on_start":   True,
    "snapshot_before_upgrade":  False,  # off by default — Timeshift rsync mode can be slow
    "notify_updates":           True,
    "bg_check_interval":        "daily",  # hourly | 6h | daily
    "language":                 "en",     # en | de
    "flatpak_enabled":          False,    # off by default — opt-in extra package source
    "snap_enabled":             False,    # off by default — opt-in extra package source
    "auto_update_tool_ids":     [],       # ids of "More Update Sources" tools to run with every normal upgrade
    "startup_healthcheck_enabled": True,  # scan for fixable problems (failed services, no firewall, etc.) on launch
    "color_scheme":             "system", # system | light | dark  (Appearance in the main menu)
    "pkg_sort_key":             "name",   # name | repo | status  (package list sort order)
    "pkg_sort_desc":            False,    # True = descending order
    "makepkg_pkexec_attempts":  0,        # automatic PACMAN_AUTH=pkexec setup attempts (max 3)
}
_settings_cache = None


def load_settings():
    global _settings_cache
    if _settings_cache is None:
        data = _read_json(SETTINGS_FILE) or {}
        _settings_cache = {**_DEFAULT_SETTINGS, **data}
    return _settings_cache


def get_setting(key):
    return load_settings().get(key, _DEFAULT_SETTINGS.get(key))


def save_settings(new_values):
    """Merge new_values into the stored settings and persist them."""
    global _settings_cache, _aur_helper_cache
    _settings_cache = {**_DEFAULT_SETTINGS, **load_settings(), **new_values}
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(_settings_cache, f, indent=2)
        tmp.replace(SETTINGS_FILE)
    except Exception:
        pass
    _aur_helper_cache = "__unset__"   # re-resolve helper in case the preference changed


def _file_age(path):
    """Return seconds since file was last modified, or infinity."""
    try:
        return time.time() - path.stat().st_mtime
    except Exception:
        return float("inf")


# ─── Helpers ──────────────────────────────────────────────────────────────────

# Force a stable C locale for all parsed queries, so pacman field names
# ("Depends On", "Required By", …) and values ("None") stay English regardless
# of the user's system language.
_C_ENV = {**os.environ, "LC_ALL": "C", "LANG": "C"}


def run_command(cmd, timeout=30):
    try:
        done = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout, env=_C_ENV)
    except subprocess.TimeoutExpired:
        return "", 1
    except Exception as exc:
        return str(exc), 1
    return done.stdout.strip(), done.returncode


def run_command_stream(cmd, on_line, on_done, timeout=180):
    """Start a shell command in the background and forward each output line
    to on_line; on_done receives the exit code (both on the GLib main loop)."""
    def pump():
        try:
            child = subprocess.Popen(
                cmd, shell=True, text=True, bufsize=1,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for raw_line in child.stdout:
                GLib.idle_add(on_line, raw_line.rstrip())
            child.wait()
        except Exception as exc:
            GLib.idle_add(on_line, f"Error: {exc}")
            GLib.idle_add(on_done, 1)
            return
        GLib.idle_add(on_done, child.returncode)
    threading.Thread(target=pump, daemon=True).start()


def _is_demo():
    """Demo mode kicks in only when no supported package manager
    (pacman/apt/dnf/zypper) can be found at all."""
    return distro.get_family() is None


_aur_helper_cache = "__unset__"

def _find_aur_helper():
    """Return the AUR helper to use, honouring the user's preference. Cached.
    The AUR only exists on Arch — on Debian/Fedora/openSUSE this always
    returns None immediately, without even trying the `which` lookups.
    pachuli (the user's own AUR helper) is tried first under "auto", ahead
    of yay/paru/pikaur/trizen."""
    if not distro.is_arch():
        return None
    pref = get_setting("aur_helper")
    if pref == "none":
        return None
    global _aur_helper_cache
    if _aur_helper_cache == "__unset__":
        candidates = [pref] if (pref and pref != "auto") else ("pachuli", "yay", "paru", "pikaur", "trizen")
        _aur_helper_cache = None
        for h in candidates:
            _, c = run_command(f"which {h} 2>/dev/null")
            if c == 0:
                _aur_helper_cache = h
                break
    return _aur_helper_cache


def _strip_ansi(text):
    """Strip ANSI/SGR colour escape codes. pachuli (unlike yay/paru) always
    emits colour codes regardless of whether stdout is a real terminal, so
    anything captured from it needs this before display or parsing."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text) if text else text


def aur_helper_upgrade_cmd(helper):
    """Full system upgrade (repo + AUR) via `helper`. pachuli routes its own
    privilege escalation through pkexec (-g), per the user's setup, instead
    of an internal sudo call."""
    if helper == "pachuli":
        return "pachuli -Syu --noconfirm -g"
    return f"{helper} -Syu --noconfirm"


def aur_helper_install_cmd(helper, names, needed=False, noconfirm=True, force_aur=False):
    """Install one or more AUR package names via `helper`. `names` is a
    pre-shlex-quoted string of one or more package names.

    noconfirm=False lets the helper's own interactive prompts through —
    e.g. yay/paru's repo-vs-AUR disambiguation, or pachuli's dependency-
    provides-conflict question — needed wherever a package that might
    also exist in a repo is being installed, since that disambiguation
    doesn't resolve reliably under --noconfirm.

    force_aur=True additionally passes pachuli's -a/--aur-only flag,
    which is the only way to make it build from the AUR even when a
    same-named repo package exists (pachuli's own classification
    otherwise always prefers the repo — see get_pkgbuild()'s note on the
    same asymmetry). yay/paru resolve this themselves interactively
    instead via the disambiguation prompt above, so force_aur has no
    effect for them.

    pachuli always routes its own privilege escalation through pkexec
    (-g), per the user's setup, instead of an internal sudo call; it
    also has no --needed flag (it already applies --needed-equivalent
    logic internally for repo packages, and always (re)builds AUR
    ones), so that flag is simply dropped for it."""
    if helper == "pachuli":
        flags = " -a" if force_aur else ""
        flags += " --noconfirm" if noconfirm else ""
        return f"pachuli -S {names}{flags} -g"
    extra = " --needed" if needed else ""
    extra += " --noconfirm" if noconfirm else ""
    return f"{helper} -S{extra} {names}"


def paru_installed():
    return shutil.which("paru") is not None


def get_paru_bootstrap_cmd():
    """Standard AUR-bootstrap sequence for paru itself. paru isn't in any
    official repo, so — like any other AUR package — it has to be built
    from its own AUR git repo the very first time (base-devel/git provide
    the build toolchain makepkg needs)."""
    build_dir = "/tmp/pachul-paru-build"
    return (
        f"rm -rf {build_dir} && "
        f"pkexec /usr/bin/pacman -S --needed --noconfirm base-devel git && "
        f"git clone https://aur.archlinux.org/paru.git {build_dir} && "
        f"cd {build_dir} && makepkg -si --noconfirm && "
        f"cd - && rm -rf {build_dir}"
    )


def pachuli_installed():
    return shutil.which("pachuli") is not None


def local_pachuli_path(app_dir):
    """Path to a pachuli.py sitting next to Pachul's own source (app_dir —
    e.g. a `python app.py` dev checkout, or install.sh/the PKGBUILD's own
    SRC_DIR before their install step runs), if present. pachuli is the
    user's own separate project, not part of Pachul itself — most
    checkouts simply won't have it, which is fine; this only offers
    something to install when there's actually a file to install."""
    if not app_dir:
        return None
    p = Path(app_dir) / "pachuli.py"
    return str(p) if p.is_file() else None


def local_pachuli_version(local_path):
    """Version der lokalen pachuli.py (siehe local_pachuli_path()), oder
    None, falls keine gefunden/gelesen werden konnte."""
    if not local_path:
        return None
    return _read_version_const(local_path, "VERSION")


def installed_pachuli_version():
    """Version des aktuell auf PATH installierten `pachuli`, oder None,
    falls nicht installiert oder die Version nicht gelesen werden
    konnte."""
    path = shutil.which("pachuli")
    if not path:
        return None
    return _read_version_const(path, "VERSION")


def pachuli_update_available(local_path):
    """True, wenn eine lokale pachuli.py existiert und entweder noch gar
    nicht installiert ist, oder eine neuere Version als die aktuell
    installierte hat. Braucht _read_version_const()/_version_newer()
    weiter unten in dieser Datei (Pachul-Selbst-Installations-Abschnitt) —
    beide sind bewusst generisch gehalten und nicht pachul-spezifisch."""
    local_v = local_pachuli_version(local_path)
    if not local_v:
        return False
    installed_v = installed_pachuli_version()
    if installed_v is None:
        return True
    return _version_newer(local_v, installed_v)


def get_pachuli_install_cmd(src_path):
    """Installs a local pachuli.py as `pachuli` to the same directory as
    the pachul launcher itself (matches install.sh's and the PKGBUILD's
    own pachuli step), so it lands on PATH immediately — no build step,
    since it's a plain Python script with its own shebang, just like
    install.sh's `install -m 755` already does for it."""
    return f"pkexec install -m 755 {shlex.quote(src_path)} /usr/local/bin/pachuli"


MAKEPKG_CONF_PATH = "/etc/makepkg.conf"


def makepkg_pkexec_configured():
    """True if /etc/makepkg.conf already points PACMAN_AUTH at pkexec.

    makepkg (called by pachuli/yay/paru/pikaur alike while building an AUR
    package) installs missing build/runtime dependencies itself, entirely
    outside any of those helpers' own privilege escalation — by default it
    always shells out to plain `sudo` for that one step, regardless of
    whether the helper's *own* upgrade/install call went through pkexec.
    Since pacman 6.1, makepkg.conf's PACMAN_AUTH lets that step use pkexec
    (or another tool) instead; this only checks whether it already does."""
    try:
        content = Path(MAKEPKG_CONF_PATH).read_text()
    except OSError:
        return False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("PACMAN_AUTH=") and "pkexec" in stripped:
            return True
    return False


def makepkg_auth_needs_setup():
    """True only if /etc/makepkg.conf has NO active PACMAN_AUTH line at all
    (i.e. makepkg still uses its default, plain sudo). An active line that
    already names pkexec is done; one naming something else (doas, su, …) is
    the user's own deliberate choice and is never overwritten."""
    try:
        content = Path(MAKEPKG_CONF_PATH).read_text()
    except OSError:
        return False
    for line in content.splitlines():
        if line.strip().startswith("PACMAN_AUTH="):
            return False
    return True


def get_makepkg_pkexec_cmd():
    """Pkexec command that points /etc/makepkg.conf's PACMAN_AUTH at
    pkexec, rewriting an existing (possibly commented-out) PACMAN_AUTH
    line in place if one is present, or appending a fresh one otherwise —
    run through `bash -c` since it needs a conditional, not a single
    command. See makepkg_pkexec_configured() for why this setting exists
    at all."""
    script = (
        f"if grep -q '^#\\?PACMAN_AUTH=' {MAKEPKG_CONF_PATH}; then "
        f"sed -i 's|^#\\?PACMAN_AUTH=.*|PACMAN_AUTH=(/usr/bin/pkexec)|' {MAKEPKG_CONF_PATH}; "
        f"else "
        f"echo 'PACMAN_AUTH=(/usr/bin/pkexec)' >> {MAKEPKG_CONF_PATH}; "
        f"fi"
    )
    return f"pkexec /usr/bin/bash -c {shlex.quote(script)}"


def get_aur_rpc_version(pkg_name):
    """Query the AUR RPC API for a package's current version there, if any.
    Best-effort only: returns None on any failure (offline, package not on
    the AUR, API hiccup, …) rather than raising — this is a supplementary
    check and must never disrupt anything else if it doesn't work."""
    if not distro.is_arch():
        return None
    import urllib.request
    import urllib.parse
    try:
        url = "https://aur.archlinux.org/rpc/v5/info?arg[]=" + urllib.parse.quote(pkg_name)
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results") or []
        if results:
            return results[0].get("Version")
    except Exception:
        pass
    return None


def check_aur_ahead_of_repo(pkg_name, installed_version):
    """For a package Pachul knows via a plain repo (not pkg_foreign) —
    e.g. a popular AUR package also mirrored as a prebuilt binary in a
    repo like chaotic-aur — check whether the *true* AUR has the same
    name at a strictly newer version than what's currently installed.
    This is exactly the "arch-update" situation: the repo mirror can lag
    behind the AUR's own rebuild cadence, and pacman/checkupdates alone
    have no way to notice since AUR isn't a sync-db source at all.
    Returns the AUR version string if it's ahead, else None (also None if
    the AUR RPC can't be reached — this never blocks or errors out)."""
    aur_version = get_aur_rpc_version(pkg_name)
    if not aur_version:
        return None
    out, code = run_command(
        f"vercmp {shlex.quote(aur_version)} {shlex.quote(installed_version)}", timeout=5)
    if code != 0:
        return None
    try:
        return aur_version if int(out.strip()) > 0 else None
    except (ValueError, TypeError):
        return None


# ─── Flatpak / Snap: optional extra package sources ───────────────────────────
# Both are entirely opt-in (see flatpak_enabled / snap_enabled settings) — if
# disabled, or if the binary simply isn't installed, every function below is
# a fast no-op that returns nothing, so people who don't use either just never
# pay for it (no extra subprocess calls at all).
#
# Privilege note: flatpak installs/removes are done with `--user` and need no
# elevated privileges — Flatpak's per-user mode is the common, recommended
# setup on Arch/Manjaro (unlike distros that pre-configure a writable
# system-wide installation). Snap fundamentally requires snapd, which always
# needs root for install/remove/refresh, so those go through the same
# `pkexec` terminal flow as pacman actions.

_flatpak_available_cache = None
_snap_available_cache = None


def flatpak_available():
    global _flatpak_available_cache
    if _flatpak_available_cache is None:
        _, code = run_command("which flatpak 2>/dev/null")
        _flatpak_available_cache = (code == 0)
    return _flatpak_available_cache


def invalidate_flatpak_available_cache():
    """Call after installing/removing the flatpak package itself, so the
    next flatpak_available() check re-probes instead of returning the
    stale cached result from earlier in this run."""
    global _flatpak_available_cache
    _flatpak_available_cache = None


def snap_available():
    global _snap_available_cache
    if _snap_available_cache is None:
        _, code = run_command("which snap 2>/dev/null")
        _snap_available_cache = (code == 0)
    return _snap_available_cache


def invalidate_snap_available_cache():
    """Call after installing/removing snapd, so the next snap_available()
    check re-probes instead of returning the stale cached result from
    earlier in this run."""
    global _snap_available_cache
    _snap_available_cache = None


def _load_flatpak_remote_cache():
    """Return the cached flatpak-remote index if it's fresh enough."""
    if _file_age(FLATPAK_REMOTE_CACHE) < FLATPAK_REMOTE_TTL:
        data = _read_json(FLATPAK_REMOTE_CACHE)
        if data:
            return data
    return None


def _build_flatpak_remote_index():
    """Every app/runtime available on ANY configured Flatpak remote (not
    just installed ones) — {app_id: {"name", "version", "description"}}.
    Cached with its own TTL like pacman's syncdb: `flatpak remote-ls`
    has to be run once per configured remote (Flathub alone lists several
    thousand entries), which is far too slow to redo on every package-list
    load. Genuinely offline-safe: if there are no remotes configured, or
    the command fails/times out, this just yields an empty index — same
    empty-result shape either way, nothing for callers to special-case."""
    remotes_out, _ = run_command("flatpak remotes --columns=name 2>/dev/null", timeout=10)
    remotes = [r.strip() for r in (remotes_out or "").splitlines() if r.strip()]
    index = {}
    for remote in remotes:
        # --all: same reasoning as get_flatpak_packages()'s own --all —
        # without it, locale/debug/source extensions are silently missing
        # from here even though flatpak update would still offer them.
        out, code = run_command(
            f"flatpak remote-ls {shlex.quote(remote)} --all "
            "--columns=application,name,version,description 2>/dev/null", timeout=90)
        if not out or code != 0:
            continue
        for line in out.splitlines():
            parts = line.split("\t")
            app_id = parts[0].strip() if parts else ""
            if not app_id or app_id in index:  # first remote wins (usually flathub anyway)
                continue
            name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else app_id
            version = parts[2].strip() if len(parts) > 2 else ""
            desc = parts[3].strip() if len(parts) > 3 else ""
            index[app_id] = {"name": name, "version": version, "description": desc}
    _write_json(FLATPAK_REMOTE_CACHE, index)
    return index


def get_flatpak_packages():
    """Every Flatpak app/runtime worth showing — both installed *and*
    available-but-not-installed, in the same dict shape get_packages()
    uses (mirrors how pacman packages merge installed + syncdb below).
    Runtimes (e.g. "org.gnome.Platform") are included deliberately, not
    just apps — Pamac and other Flatpak-aware tools list them too, and
    they can have their own pending updates that would otherwise be
    invisible in the package list even though they're counted. `--all`
    is required for that: `flatpak list` hides locale and debug
    extensions (e.g. "org.gnome.Platform.Locale") by default, same as
    remote-ls — without it those never show up here even though
    get_flatpak_updates() (which also uses --all) counts them as pending.
    `source_id` carries the Flatpak ref ID (e.g. "org.gimp.GIMP"), which
    is what the actual install/uninstall commands need — pkg_name stays
    the friendly display name."""
    if not (get_setting("flatpak_enabled") and flatpak_available()):
        return []
    out, code = run_command(
        "flatpak list --all --columns=application,name,version 2>/dev/null", timeout=15)
    items = {}
    if out and code == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            app_id = parts[0].strip() if parts else ""
            if not app_id:
                continue
            name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else app_id
            version = parts[2].strip() if len(parts) > 2 else ""
            items[app_id] = {
                "name": name, "version": version, "repo": "flatpak",
                "status": "installed", "description": "", "foreign": False,
                "source_id": app_id,
            }

    # Layer the (cached) remote catalog on top: fills in everything not
    # already installed as "available", and backfills a description for
    # installed entries (flatpak list itself doesn't provide one).
    remote_index = _load_flatpak_remote_cache()
    if remote_index is None:
        remote_index = _build_flatpak_remote_index()
    for app_id, info in remote_index.items():
        if app_id in items:
            if not items[app_id]["description"]:
                items[app_id]["description"] = info.get("description", "")
        else:
            items[app_id] = {
                "name": info.get("name", app_id), "version": info.get("version", ""),
                "repo": "flatpak", "status": "available",
                "description": info.get("description", ""), "foreign": False,
                "source_id": app_id,
            }
    return list(items.values())


def _load_snap_catalog_cache():
    """Return the cached Snap Store catalog index if it's fresh enough."""
    if _file_age(SNAP_CATALOG_CACHE) < SNAP_CATALOG_TTL:
        data = _read_json(SNAP_CATALOG_CACHE)
        if data:
            return data
    return None


def _build_snap_catalog_index():
    """Every snap available in the Snap Store, browsable by category —
    {name: {"name", "version", "description"}}. Cached like Flatpak's
    remote catalog (_build_flatpak_remote_index()), for the same reason:
    walking every category is too slow to redo on every package-list load.

    Unlike Flatpak (remote-ls) or the AUR (packages.gz), there's no CLI
    command or single bulk dump for "every available snap" — `snap find`
    requires a search term, and the Snap Store's own HTTP API
    (api.snapcraft.io) hard-caps every /v2/snaps/find call at 100 results,
    with no page/offset parameter to go beyond that — this is a documented
    API limitation, not something we're choosing not to use. The one lever
    that's actually available: results are also implicitly split into
    "featured" and non-featured per category, so querying featured=true
    and featured=false separately roughly doubles coverage versus one
    mixed call. That's still bounded (up to ~200/category, not the
    literal full catalog the AUR/Flatpak indexes are), but it's the
    practical ceiling the public API allows — good enough for a "browse
    what's new" list without turning into thousands of uncategorized,
    low-signal entries anyway.

    Best-effort: returns {} on any failure (offline, API changed shape,
    timeout, …) rather than raising — same offline-safety guarantee as
    _build_flatpak_remote_index()/_build_aur_names_index()."""
    import json as _json
    import urllib.request
    import urllib.error
    import urllib.parse
    headers = {"Snap-Device-Series": "16", "User-Agent": "Pachul"}
    try:
        req = urllib.request.Request(
            "https://api.snapcraft.io/v2/snaps/categories", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            cat_data = _json.loads(resp.read().decode("utf-8", errors="replace"))
        categories = [c["name"] for c in cat_data.get("categories", []) if c.get("name")]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return {}

    index = {}
    for cat in categories:
        for featured in ("true", "false"):
            url = ("https://api.snapcraft.io/v2/snaps/find?"
                    + urllib.parse.urlencode({
                        "category": cat, "featured": featured,
                        "fields": "title,summary,version",
                    }))
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = _json.loads(resp.read().decode("utf-8", errors="replace"))
            except (urllib.error.URLError, OSError, ValueError):
                continue  # one bad request shouldn't lose every other one
            for result in data.get("results", []):
                snap = result.get("snap", {})
                name = snap.get("name", "")
                if not name or name in index:
                    continue
                index[name] = {
                    "name": snap.get("title") or name,
                    "version": snap.get("version", ""),
                    "description": snap.get("summary", ""),
                }
    _write_json(SNAP_CATALOG_CACHE, index)
    return index


def get_snap_packages():
    """Every Snap worth showing — both installed *and* available-but-not-
    installed, in the same dict shape get_packages() uses (mirrors
    get_flatpak_packages()'s installed+catalog merge above)."""
    if not (get_setting("snap_enabled") and snap_available()):
        return []
    out, code = run_command("snap list 2>/dev/null", timeout=15)
    items = {}
    if out and code == 0:
        for line in out.splitlines()[1:]:  # first line is the "Name Version Rev ..." header
            parts = line.split()
            if len(parts) < 2:
                continue
            name, version = parts[0], parts[1]
            items[name] = {
                "name": name, "version": version, "repo": "snap",
                "status": "installed", "description": "", "foreign": False,
                "source_id": name,
            }

    catalog = _load_snap_catalog_cache()
    if catalog is None:
        catalog = _build_snap_catalog_index()
    for name, info in catalog.items():
        if name in items:
            if not items[name]["description"]:
                items[name]["description"] = info.get("description", "")
        else:
            items[name] = {
                "name": info.get("name", name), "version": info.get("version", ""),
                "repo": "snap", "status": "available",
                "description": info.get("description", ""), "foreign": False,
                "source_id": name,
            }
    return list(items.values())


def search_flatpak(query):
    """Search flathub (or whatever remotes are configured) for `query`."""
    if not (get_setting("flatpak_enabled") and flatpak_available()):
        return []
    out, code = run_command(
        f"flatpak search {shlex.quote(query)} "
        "--columns=application,name,version,description 2>/dev/null", timeout=20)
    if not out or code != 0:
        return []
    items = []
    for line in out.splitlines():
        parts = line.split("\t")
        app_id = parts[0].strip() if parts else ""
        if not app_id or "no matches found" in line.lower():
            continue
        name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else app_id
        version = parts[2].strip() if len(parts) > 2 else ""
        desc = parts[3].strip() if len(parts) > 3 else ""
        items.append({
            "name": name, "version": version, "repo": "flatpak",
            "description": desc, "status": "available", "foreign": False,
            "source_id": app_id,
        })
    return items


def search_snap(query):
    """Search the Snap Store for `query`."""
    if not (get_setting("snap_enabled") and snap_available()):
        return []
    out, code = run_command(f"snap find {shlex.quote(query)} 2>/dev/null", timeout=20)
    if not out or code != 0:
        return []
    lines = out.splitlines()
    items = []
    for line in lines[1:]:  # first line is the "Name Version Publisher ..." header
        parts = line.split(None, 4)
        if len(parts) < 2:
            continue
        name, version = parts[0], parts[1]
        desc = parts[4].strip() if len(parts) > 4 else ""
        items.append({
            "name": name, "version": version, "repo": "snap",
            "description": desc, "status": "available", "foreign": False,
            "source_id": name,
        })
    return items


# ─── Curated AUR entries (always listed; also the demo-mode catalogue) ───────

_POPULAR_AUR_TABLE = """
yay|12.3.5-1|Yet another yogurt - AUR helper written in Go
paru|2.0.4-1|Feature packed AUR helper
google-chrome|124.0-1|The popular web browser by Google
visual-studio-code-bin|1.89.0-1|Visual Studio Code editor from Microsoft
discord|0.0.57-1|All-in-one voice and text chat for gamers
spotify|1.2.25-1|A proprietary music streaming service
1password|8.10.30-1|Password manager and secure digital wallet
zoom|6.0.2-1|Video conferencing, web conferencing, webinars
slack-desktop|4.38.125-1|Messaging app for teams
telegram-desktop-bin|5.1.6-1|Official Telegram Desktop client
obs-studio-browser|30.1.2-1|Free and open source streaming/recording software
timeshift|24.01.1-1|System restore utility for Linux
ventoy-bin|1.0.99-1|Tool to create bootable USB drives
onlyoffice-bin|8.0.1-1|Free office suite compatible with MS Office
bottles|51.14-1|Run Windows software on Linux using Wine
protonup-qt|2.9.0-1|Install and manage Proton-GE and Luxtorpeda
heroic-games-launcher|2.14.0-1|Open source Epic, GOG and Amazon Games launcher
lutris|0.5.17-1|Open gaming platform for Linux
mangohud|0.7.1-1|Vulkan/OpenGL overlay for monitoring FPS and temps
nerd-fonts-complete|3.2.1-1|Iconic font aggregator and collection
ttf-ms-fonts|0.1-9|Core Microsoft fonts
pamac-aur|11.6.0-1|A Package Manager with AUR support
pikaur|1.28-1|Lightweight AUR package manager
sublime-text-4|4.0.4180-1|Sophisticated text editor for code and prose
jetbrains-toolbox|2.3.2-1|JetBrains IDE manager
postman-bin|11.0.9-1|API development environment
insomnia|9.2.0-1|Open-source API client
dbeaver|24.0.5-1|Universal database tool and SQL client
wine|9.8-1|A compatibility layer for running Windows programs
steam|1.0.0.79-2|Valve's digital software delivery system
"""
POPULAR_AUR_PACKAGES = [
    tuple(cell.strip() for cell in row.split("|"))
    for row in _POPULAR_AUR_TABLE.strip().splitlines()
]


def _aur_stub(name, desc, version=""):
    """Entry for a package that is only known from the AUR catalogue."""
    return {"name": name, "version": version, "repo": "aur",
            "status": "available", "description": desc, "foreign": True}


# ─── Installed-package fingerprint ────────────────────────────────────────────

def _installed_fingerprint():
    """Fast fingerprint of installed packages, used to decide whether the
    cached package list needs rebuilding."""
    if distro.is_arch():
        local_db = Path("/var/lib/pacman/local")
        out, code = run_command("pacman -Q 2>/dev/null")
        if code != 0:
            return None
        # Combine package count + local db mtime for a fast, reliable fingerprint
        try:
            mtime = str(int(local_db.stat().st_mtime))
        except Exception:
            mtime = "0"
        pkg_count = str(out.count("\n"))
        fingerprint = hashlib.md5(f"{mtime}:{pkg_count}".encode()).hexdigest()
        return fingerprint, out

    return pkgmanager.get_installed_fingerprint()


# ─── Sync-DB cache (pacman -Sl) ───────────────────────────────────────────────

def _load_syncdb_cache():
    """The cached repository index while it is within its TTL, else None."""
    if _file_age(SYNCDB_CACHE) >= SYNCDB_TTL:
        return None
    return _read_json(SYNCDB_CACHE) or None

def _parse_db_file(db_path):
    """Read one pacman .db archive into {pkgname: (repo, version, desc)}."""
    import tarfile
    repo = db_path.stem  # file name without ".db" is the repo name
    found = {}
    wanted = ("%NAME%", "%VERSION%", "%DESC%")
    try:
        with tarfile.open(db_path, "r:*") as archive:
            desc_files = {m.name: m for m in archive.getmembers()
                          if m.name.endswith("/desc")}
            for member in desc_files.values():
                handle = archive.extractfile(member)
                if not handle:
                    continue
                rows = handle.read().decode("utf-8", errors="replace").splitlines()
                fields = {}
                for pos, tag in enumerate(rows[:-1]):
                    if tag in wanted:
                        fields[tag] = rows[pos + 1].strip()
                pkg = fields.get("%NAME%")
                if pkg:
                    found[pkg] = (repo,
                                  fields.get("%VERSION%") or "",
                                  fields.get("%DESC%") or "")
    except Exception:
        pass
    return found


def _build_syncdb(installed_set):
    """Build the 'available packages' index — from local pacman .db files
    on Arch (fast, no subprocess needed), or via the matching native tool
    (apt/dnf/zypper) on other distros. Either way the result is cached
    with the same TTL, since apt/dnf/zypper are noticeably slower here
    than pacman's offline tarball parsing."""
    if not distro.is_arch():
        pkgs = pkgmanager.build_available_packages()
        _write_json(SYNCDB_CACHE, pkgs)
        return pkgs

    sync_dir = Path("/var/lib/pacman/sync")
    index = {}

    if sync_dir.exists():
        db_files = list(sync_dir.glob("*.db"))
        workers = min(4, len(db_files) or 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for parsed in pool.map(_parse_db_file, db_files):
                for pkg_name, (repo, version, desc) in parsed.items():
                    index[pkg_name] = {"repo": repo, "version": version,
                                       "description": desc}

    # No usable .db files: ask pacman itself (slower, but always available)
    if not index:
        listing, rc = run_command("pacman -Sl 2>/dev/null", timeout=60)
        if listing and rc == 0:
            for row in listing.splitlines():
                cols = row.strip().split()
                if len(cols) >= 3:
                    index[cols[1]] = {"repo": cols[0], "version": cols[2],
                                      "description": ""}

    _write_json(SYNCDB_CACHE, index)
    return index


# ─── Main package list ────────────────────────────────────────────────────────

def _load_aur_names_cache():
    """Cached AUR package-name list while it is within its TTL, else None."""
    if _file_age(AUR_NAMES_CACHE) >= AUR_NAMES_TTL:
        return None
    return _read_json(AUR_NAMES_CACHE) or None


def load_aur_meta_cache(ignore_ttl=False):
    """Return the cached AUR {name: [version, description]} map, or None.
    With ignore_ttl=True a stale cache is still returned (better a version
    that is a few days old than none at all while a refresh is pending)."""
    if ignore_ttl or _file_age(AUR_META_CACHE) < AUR_META_TTL:
        data = _read_json(AUR_META_CACHE)
        if isinstance(data, dict) and data:
            return data
    return None


def aur_meta_is_fresh():
    return load_aur_meta_cache() is not None


def refresh_aur_meta():
    """Download the AUR's packages-meta-v1.json.gz (every package with its
    current version and description) and cache a compact name -> [version,
    description] map. This is what lets not-yet-installed AUR packages show
    a version number without one RPC request per package.

    The dump is a single JSON array of ~100k+ objects (far too big to
    json.loads in one go on a desktop), so it is decompressed and decoded
    one object at a time from a stream — memory stays proportional to the
    small result map, not to the dump.

    Best-effort: returns None on any failure (offline, AUR unreachable,
    malformed data) and keeps whatever cache already exists."""
    import zlib
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            "https://aur.archlinux.org/packages-meta-v1.json.gz",
            headers={"User-Agent": "Pachul"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            meta = _parse_aur_meta_stream(iter(lambda: resp.read(1 << 16), b""))
    except (urllib.error.URLError, OSError, EOFError, zlib.error, ValueError):
        return None
    if not meta:
        return None
    _write_json(AUR_META_CACHE, meta)
    return meta


def _parse_aur_meta_stream(chunks):
    """Incrementally decode a gzip'd JSON array of AUR package objects
    (an iterable of byte chunks) into {name: [version, description]}."""
    import zlib
    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    jd = json.JSONDecoder()
    meta = {}
    buf = ""
    started = False
    pending = b""   # incomplete multi-byte UTF-8 tail between chunks

    def drain(buf):
        i, n = 0, len(buf)
        while True:
            while i < n and buf[i] in " \t\r\n,":
                i += 1
            if i >= n or buf[i] == "]":
                return buf[i:] if i < n else "", i >= n or buf[i] == "]"
            try:
                obj, end = jd.raw_decode(buf, i)
            except ValueError:
                return buf[i:], False     # object not complete yet
            if isinstance(obj, dict) and obj.get("Name"):
                meta[obj["Name"]] = [obj.get("Version") or "",
                                     obj.get("Description") or ""]
            i = end

    for chunk in chunks:
        raw = pending + dec.decompress(chunk)
        try:
            text = raw.decode("utf-8")
            pending = b""
        except UnicodeDecodeError as e:
            text = raw[:e.start].decode("utf-8", errors="replace")
            pending = raw[e.start:]
        buf += text
        if not started:
            buf = buf.lstrip()
            if not buf:
                continue
            if buf[0] != "[":
                raise ValueError("unexpected AUR meta format")
            buf = buf[1:]
            started = True
        buf, _done = drain(buf)
    tail = dec.flush()
    if tail:
        buf += (pending + tail).decode("utf-8", errors="replace")
        drain(buf)
    return meta


def apply_aur_meta(packages, meta):
    """Fill version (and a blank description) of available-but-not-installed
    AUR entries from `meta`, in place. Installed/update entries keep their
    real local version. Returns how many entries were touched."""
    if not meta:
        return 0
    n = 0
    for p in packages:
        if p.get("repo") == "aur" and p.get("status") == "available":
            m = meta.get(p["name"])
            if m:
                p["version"] = m[0]
                if not p.get("description"):
                    p["description"] = m[1]
                n += 1
    return n


def _build_aur_names_index():
    """Every package name currently in the AUR (tens of thousands), fetched
    from the AUR's own packages.gz dump — a plain, one-name-per-line list
    with no metadata. That's deliberate: it's the lightweight way to get
    the *full* catalog without hammering the RPC API once per package, and
    it's exactly what POPULAR_AUR_PACKAGES's own comment already noted —
    a real version/description for an available-but-not-installed AUR
    package isn't knowable without querying the AUR directly, so this
    leaves both blank for every name here. get_aur_info() already fetches
    the real thing on demand once a specific package's details are
    actually opened — doing that upfront for ~90k packages just to
    populate a browse list isn't remotely worth it.

    Best-effort: returns [] on any failure (offline, AUR unreachable,
    malformed response, …) rather than raising — same offline-safety
    guarantee as _build_flatpak_remote_index()."""
    import gzip
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            "https://aur.archlinux.org/packages.gz",
            headers={"User-Agent": "Pachul"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = gzip.decompress(resp.read())
    except (urllib.error.URLError, OSError, EOFError):
        return []
    names = [
        line.strip() for line in raw.decode("utf-8", errors="replace").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    _write_json(AUR_NAMES_CACHE, names)
    return names


def _merge_into_list(installed_pkgs, syncdb, aur_set):
    """Merge installed packages, the repo index and the AUR names into the
    single list the UI shows."""
    merged = dict(installed_pkgs)

    for pkgname, meta in syncdb.items():
        blurb = meta.get("description", "")
        entry = merged.get(pkgname)
        if entry is None:
            merged[pkgname] = {
                "name": pkgname,
                "version": meta["version"],
                "repo": meta["repo"],
                "status": "available",
                "description": blurb,
                "foreign": False,
            }
            continue
        if meta["repo"] and not entry["foreign"]:
            entry["repo"] = meta["repo"]
        # the repo index fills in a missing description
        if not entry.get("description"):
            entry["description"] = blurb

    # Arch only: curated AUR entries go in first so they keep their nicer
    # descriptions, then the complete AUR catalogue (aur_set, built by
    # _build_aur_names_index()) adds everything else with blank details.
    if distro.is_arch():
        for name, _version, desc in POPULAR_AUR_PACKAGES:
            merged.setdefault(name, _aur_stub(name, desc))
        for name in aur_set:
            merged.setdefault(name, _aur_stub(name, ""))

    return list(merged.values())


def get_packages():
    """
    The full package list, as quickly as possible.

    1. packages.json exists and its installed-fingerprint still matches:
       serve that cache straight away.
    2. Otherwise rebuild (pacman -Q plus the cached or fresh repo index)
       and store the result for the next start.
    """
    if _is_demo():
        return [_aur_stub(name, desc, version)
                for name, version, desc in POPULAR_AUR_PACKAGES]

    # Fast path: compare the installed-package fingerprint
    snapshot = _installed_fingerprint()
    if snapshot is None:
        return []
    fingerprint, raw_Q = snapshot

    cached = _read_json(PKG_CACHE)
    if (cached and cached.get("version") == CACHE_VERSION
            and cached.get("fingerprint") == fingerprint):
        packages = cached["packages"]
    else:
        # ── Slow path: rebuild ────────────────────────────────────────────────
        # Step 1 — installed packages
        installed_pkgs = {}
        for line in raw_Q.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                installed_pkgs[parts[0]] = {
                    "name": parts[0], "version": parts[1],
                    "repo": "local", "status": "installed",
                    "description": "", "foreign": False,
                }

        # Step 2 — mark AUR/foreign (Arch/AUR-only concept; nothing to do
        # on Debian/Fedora/openSUSE, where every installed package always
        # comes from a configured repo)
        if distro.is_arch():
            foreign_out, _ = run_command("pacman -Qm 2>/dev/null")
            for line in (foreign_out or "").splitlines():
                parts = line.strip().split(None, 1)
                if parts and parts[0] in installed_pkgs:
                    installed_pkgs[parts[0]]["foreign"] = True
                    installed_pkgs[parts[0]]["repo"] = "aur"
        elif distro.is_debian():
            # Real repo/origin per installed package (e.g. "Ubuntu" vs a
            # PPA's label), so the sidebar's repo categories aren't empty
            # for installed packages the way they'd be if "local" (the
            # placeholder set above) were left as-is. Purely additive —
            # packages with no resolvable origin just keep "local".
            for pkgname, origin in pkgmanager.installed_repos().items():
                if pkgname in installed_pkgs:
                    installed_pkgs[pkgname]["repo"] = origin.lower()

        # Step 3 — sync DB (use cache if fresh, else rebuild)
        syncdb = _load_syncdb_cache()
        if syncdb is None:
            syncdb = _build_syncdb(set(installed_pkgs))

        # Step 3b — full AUR name catalog (Arch only; own cache/TTL, same
        # idea as syncdb just above)
        aur_names = []
        if distro.is_arch():
            aur_names = _load_aur_names_cache()
            if aur_names is None:
                aur_names = _build_aur_names_index()

        # Step 4 — merge
        packages = _merge_into_list(installed_pkgs, syncdb, set(aur_names))

        # Step 5 — save cache (pacman packages only — Flatpak/Snap are merged
        # in fresh below every time, so they're never stale in this cache)
        _write_json(PKG_CACHE, {"version": CACHE_VERSION, "fingerprint": fingerprint,
                                "packages": packages})

    # Flatpak/Snap are independent, opt-in sources, queried fresh each call
    # rather than folded into the pacman fingerprint cache above, and are
    # no-ops entirely when disabled or not installed. "Fresh" only means the
    # *installed* set (`flatpak list`, `snap list` are both cheap) — Flatpak's
    # available-package catalog is itself cached separately, with its own TTL
    # (see _load_flatpak_remote_cache()), since that one genuinely isn't cheap.
    # Versions for not-yet-installed AUR packages come from a separate daily
    # cache (never stored inside packages.json, which only rebuilds when the
    # installed set changes and would freeze them). A stale map is still
    # used here; the window refreshes it in the background when it's old.
    if distro.is_arch():
        apply_aur_meta(packages, load_aur_meta_cache(ignore_ttl=True))

    return packages + get_flatpak_packages() + get_snap_packages()


def invalidate_cache():
    """Call this after install/remove/upgrade so next load rebuilds."""
    try:
        PKG_CACHE.unlink(missing_ok=True)
    except Exception:
        pass
    if pkgmanager.native.apt_available():
        pkgmanager.native.invalidate_apt_cache()
    if pkgmanager.native.dnf5_available():
        pkgmanager.native.invalidate_dnf5_base()


def invalidate_syncdb_cache():
    """Call this after pacman -Sy so the sync DB is re-fetched."""
    try:
        SYNCDB_CACHE.unlink(missing_ok=True)
    except Exception:
        pass
    if pkgmanager.native.apt_available():
        pkgmanager.native.invalidate_apt_cache()
    if pkgmanager.native.dnf5_available():
        pkgmanager.native.invalidate_dnf5_base()


# ─── Package info / files ─────────────────────────────────────────────────────

def get_package_info(pkg_name):
    if not distro.is_arch():
        text = pkgmanager.get_package_info_text(pkg_name)
        if text:
            return text
        if _is_demo():
            return (f"Name           : {pkg_name}\nVersion        : 1.0.0-1\n"
                    f"Description    : Demo package (no supported package manager found)\n"
                    f"Architecture   : x86_64\nURL            : https://example.com/{pkg_name}\n"
                    f"Licenses       : GPL\nGroups         : None\nProvides       : None\n"
                    f"Depends On     : glibc\nOptional Deps  : None\nConflicts With : None\n"
                    f"Replaces       : None\nInstalled Size : 1.20 MiB\nPackager       : None\n"
                    f"Build Date     : Thu 01 Jan 2026\nInstall Date   : Thu 01 Jan 2026\n"
                    f"Install Reason : Explicitly installed\n")
        return (f"Name           : {pkg_name}\n"
                f"Description    : No detailed information available — this package "
                f"is not installed and was not found in the configured repositories.\n")

    q = shlex.quote(pkg_name)
    out, code = run_command(f"pacman -Qi {q} 2>/dev/null")
    if out and code == 0:
        return out
    out2, code2 = run_command(f"pacman -Si --noconfirm {q} 2>/dev/null")
    if out2 and code2 == 0:
        return out2

    # Not installed and not in the sync DB — for AUR packages, ask a helper.
    helper = _find_aur_helper()
    if helper:
        cmd = f"pachuli -Si {q} -g 2>/dev/null" if helper == "pachuli" else f"{helper} -Si {q} 2>/dev/null"
        out3, code3 = run_command(cmd, timeout=30)
        if out3 and code3 == 0:
            return _strip_ansi(out3)

    if _is_demo():
        return (f"Name           : {pkg_name}\nVersion        : 1.0.0-1\n"
                f"Description    : Demo package (not on Arch Linux)\n"
                f"Architecture   : x86_64\nURL            : https://example.com/{pkg_name}\n"
                f"Licenses       : GPL\nGroups         : None\nProvides       : None\n"
                f"Depends On     : glibc\nOptional Deps  : None\nConflicts With : None\n"
                f"Replaces       : None\nInstalled Size : 1.20 MiB\nPackager       : Arch Linux\n"
                f"Build Date     : Thu 01 Jan 2026\nInstall Date   : Thu 01 Jan 2026\n"
                f"Install Reason : Explicitly installed\nValidated By   : Signature\n")

    # Honest fallback on a real system: don't fabricate version/dates/deps.
    return (f"Name           : {pkg_name}\n"
            f"Description    : No detailed information available — this package "
            f"is not installed and was not found in the sync databases"
            f"{' or AUR' if helper else ''}.\n")


def get_package_files(pkg_name):
    # shown when the real file list cannot be determined
    placeholder = [f"{pkg_name} /usr/bin/{pkg_name}",
                   f"{pkg_name} /usr/share/man/man1/{pkg_name}.1"]
    if not distro.is_arch():
        return pkgmanager.get_package_files(pkg_name) or placeholder
    listing, rc = run_command(f"pacman -Ql {shlex.quote(pkg_name)} 2>/dev/null")
    if listing and rc == 0:
        return listing.splitlines()
    return placeholder


# ─── File → package search (pacman -F) ───────────────────────────────────────

def files_db_available():
    """Whether a synced pacman files database exists for `pacman -F` to use."""
    if not distro.is_arch():
        return pkgmanager.files_db_available()
    out, code = run_command("ls /var/lib/pacman/sync/*.files 2>/dev/null | head -1")
    return bool(out.strip()) and code == 0


def search_file_owner(query):
    """Which package(s) own file paths matching `query` (regex, via `pacman -Fx`).

    Returns [{"pkg": "repo/name", "version": "1.0-1", "files": [...]}].
    Requires the files DB to be synced first (`pkexec /usr/bin/pacman -Fy`) — callers
    should check `files_db_available()` and offer that sync if it's missing.
    """
    query = query.strip()
    if not query:
        return []
    if not distro.is_arch():
        results = pkgmanager.search_file_owner(query)
        if not results and _is_demo():
            needle = query.strip("/").lower()
            lib_name = needle if needle.startswith("lib") else (f"lib{needle}" if needle else "libssl.so.3")
            results = [
                {"pkg": "openssl", "version": "3.3.1-1", "files": [f"usr/lib/{lib_name}"]},
                {"pkg": "systemd", "version": "256.4-1", "files": [f"usr/lib/systemd/{needle or 'systemd'}"]},
            ]
        return results
    out, code = run_command(f"pacman -Fx {shlex.quote(query)} 2>/dev/null", timeout=30)
    results = []
    if out and code == 0:
        current = None
        for line in out.splitlines():
            if line and not line[0].isspace():
                parts = line.split()
                if len(parts) >= 2:
                    current = {"pkg": parts[0], "version": parts[1], "files": []}
                    results.append(current)
            elif current is not None:
                current["files"].append(line.strip())
    if not results and _is_demo():
        needle = query.strip("/").lower()
        lib_name = needle if needle.startswith("lib") else (f"lib{needle}" if needle else "libssl.so.3")
        results = [
            {"pkg": "extra/openssl", "version": "3.3.1-1",
             "files": [f"usr/lib/{lib_name}"]},
            {"pkg": "core/systemd", "version": "256.4-1",
             "files": [f"usr/lib/systemd/{needle or 'systemd'}"]},
        ]
    return results


# ─── Updates / orphans / sysinfo ─────────────────────────────────────────────

def check_updates():
    """Repo updates (checkupdates) plus AUR updates from a helper, if
    present, plus Flatpak/Snap updates when those sources are enabled.
    The four checks are independent of each other, so they run in
    parallel threads rather than one after another — checkupdates and
    {helper} -Qua alone each allow up to a minute, so sequentially this
    could take several minutes in the worst case; in parallel the whole
    check takes about as long as the single slowest one."""
    def _repo_check():
        if not distro.is_arch():
            return pkgmanager.check_updates()
        results = []
        out, code = run_command("checkupdates 2>/dev/null || pacman -Qu 2>/dev/null", timeout=60)
        if out and code == 0:
            for line in out.splitlines():
                if "[ignored]" in line or "(ignored)" in line:
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    results.append({"name": parts[0], "old": parts[1],
                                    "new": parts[3], "aur": False})
        return filter_ignored_updates(results)

    def _aur_check():
        helper = _find_aur_helper()
        if not (helper and get_setting("include_aur_updates")):
            return []
        results = []
        aur_cmd = "pachuli -Qua -g 2>/dev/null" if helper == "pachuli" else f"{helper} -Qua 2>/dev/null"
        aout, acode = run_command(aur_cmd, timeout=90)
        if aout and acode == 0:
            for line in _strip_ansi(aout).splitlines():
                if "[ignored]" in line or "(ignored)" in line:
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    results.append({"name": parts[0], "old": parts[1],
                                    "new": parts[3], "aur": True})
        return filter_ignored_updates(results)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fn) for fn in
                   (_repo_check, _aur_check, get_flatpak_updates, get_snap_updates)]
        groups = [f.result() for f in futures]

    # Merge preserving the original precedence (repo > AUR > Flatpak > Snap)
    # for de-duplication, same as when these ran sequentially one at a time.
    updates = []
    seen = set()
    for group in groups:
        for u in group:
            if u["name"] not in seen:
                updates.append(u)
                seen.add(u["name"])
    return updates


def get_flatpak_updates():
    """Pending Flatpak updates, in the same {name, old, new, aur} shape
    check_updates() uses for repo/AUR entries, so they merge into one list.
    `name` is set to the Flatpak app ID (not the friendly display name) —
    that's what `flatpak update` itself and the matching logic in the UI
    (which keys off each installed package's `source_id`) both expect.
    Empty list if Flatpak support isn't enabled/installed, or refreshing
    the local metadata fails (offline, etc.) — this is purely informational
    and should never block the rest of the update check."""
    if not (get_setting("flatpak_enabled") and flatpak_available()):
        return []
    # Refresh the local appstream/summary cache first — otherwise
    # `remote-ls --updates` can compare against a stale local copy and
    # under-report what's actually available.
    run_command("flatpak update --appstream 2>/dev/null", timeout=30)
    out, code = run_command(
        "flatpak remote-ls --updates --all --columns=application,version 2>/dev/null",
        timeout=20)
    if not out or code != 0:
        return []
    updates = []
    for line in out.splitlines():
        parts = line.split("\t")
        app_id = parts[0].strip() if parts else ""
        if not app_id:
            continue
        new_version = parts[1].strip() if len(parts) > 1 else ""
        updates.append({"name": app_id, "old": "", "new": new_version, "aur": False})
    return updates


def get_snap_updates():
    """Pending Snap updates, in the same {name, old, new, aur} shape
    check_updates() uses. `snap refresh --list` only queries snapd for
    what's pending — it does not install or change anything. Prints
    'All snaps up to date.' (no table) when nothing's pending, which the
    parsing below naturally yields zero rows for."""
    if not (get_setting("snap_enabled") and snap_available()):
        return []
    out, code = run_command("snap refresh --list 2>/dev/null", timeout=30)
    if not out or code != 0:
        return []
    lines = out.splitlines()
    if len(lines) < 2:   # just the "All snaps up to date." line, or empty
        return []
    updates = []
    for line in lines[1:]:   # first line is the "Name Version Rev ..." header
        parts = line.split()
        if len(parts) < 2:
            continue
        updates.append({"name": parts[0], "old": "", "new": parts[1], "aur": False})
    return updates


def get_orphans():
    if distro.is_arch():
        listing, _ = run_command("pacman -Qdt 2>/dev/null")
        orphans = []
        for row in (listing or "").splitlines():
            fields = row.strip().split(None, 1)
            if len(fields) == 2:
                orphans.append({"name": fields[0], "version": fields[1]})
    else:
        orphans = pkgmanager.get_orphans()
    if not orphans and _is_demo():
        orphans = [{"name": n, "version": v} for n, v in _DEMO_ORPHANS]
    return orphans


_DEMO_ORPHANS = (
    ("lib32-libpng12", "1.2.56-2"),
    ("perl-encode-locale", "1.05-7"),
    ("python2", "2.7.18-3"),
)


def _human_size(num_bytes):
    """Format a byte count base-1024, e.g. 1536 → '1.5 KiB'."""
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PiB"


def _dir_size(path):
    """Total size of all files under `path`, in bytes (resilient to errors)."""
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


PKG_CACHE_DIR = "/var/cache/pacman/pkg"


def get_package_cache_size():
    """Human-readable current size of the system package cache."""
    if not distro.is_arch():
        return pkgmanager.get_package_cache_size()
    return _human_size(_dir_size(PKG_CACHE_DIR)) if os.path.isdir(PKG_CACHE_DIR) else "N/A"


def _get_desktop_info():
    """Desktop environment name + version, where detectable. Best-effort:
    covers the common desktops shipped on Arch/Manjaro; falls back to just
    the XDG-reported name (no version) for anything else."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or ""
    desktop = desktop.split(":")[0].strip() if desktop else ""
    if not desktop:
        return "Unknown"

    dl = desktop.lower()
    version_cmd = None
    if "kde" in dl or "plasma" in dl:
        version_cmd = "plasmashell --version 2>/dev/null"
    elif "gnome" in dl:
        version_cmd = "gnome-shell --version 2>/dev/null"
    elif "xfce" in dl:
        version_cmd = "xfce4-session --version 2>/dev/null"
    elif "cinnamon" in dl:
        version_cmd = "cinnamon --version 2>/dev/null"
    elif "mate" in dl:
        version_cmd = "mate-session --version 2>/dev/null"
    elif "budgie" in dl:
        version_cmd = "budgie-desktop --version 2>/dev/null"
    elif "lxqt" in dl:
        version_cmd = "lxqt-session --version 2>/dev/null"

    version = ""
    if version_cmd:
        out, code = run_command(version_cmd)
        if out and code == 0:
            m = re.search(r"(\d+[\w.\-]*)", out)
            if m:
                version = m.group(1)

    return f"{desktop} {version}".strip() if version else desktop


def _get_cpu_info():
    """CPU model name (and thread count), read straight from /proc/cpuinfo —
    works the same on x86_64 and (with the Hardware/model fallback) on ARM.

    IMPORTANT: on x86, the bare "model" field (just a numeric model ID,
    e.g. "85") appears *before* the actual "model name" line in the file.
    A naive first-match-wins check over ("model name", "hardware", "model")
    would therefore latch onto that numeric ID and stop, since "model"
    matches before the real name is even reached. So: always scan for
    "model name" first; only fall back to "Hardware" (common on ARM boards)
    or the bare "model" field if no "model name" line exists at all.
    """
    model_name = ""
    hardware = ""
    bare_model = ""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                low = line.lower()
                if low.startswith("model name") and not model_name:
                    model_name = line.split(":", 1)[1].strip()
                elif low.startswith("hardware") and not hardware:
                    hardware = line.split(":", 1)[1].strip()
                elif low.startswith("model") and not low.startswith("model name") and not bare_model:
                    bare_model = line.split(":", 1)[1].strip()
                if model_name:
                    break
    except Exception:
        pass
    model = model_name or hardware or bare_model
    if not model:
        return "Unknown"
    threads = os.cpu_count()
    return f"{model} ({threads} threads)" if threads else model


def _get_disk_type():
    """Storage type (NVMe SSD / SSD / HDD) for whatever the root filesystem
    actually lives on. Resolves through partitions, LUKS and LVM down to the
    underlying physical block device before checking rotational vs. NVMe."""
    try:
        out, code = run_command("findmnt -n -o SOURCE / 2>/dev/null")
        src = out.strip() if (out and code == 0) else ""
        if not src:
            return "Unknown"

        out2, code2 = run_command(f"lsblk -ndo pkname {shlex.quote(src)} 2>/dev/null")
        parent = out2.strip() if (out2 and code2 == 0) else ""
        if not parent:
            parent = os.path.basename(src)  # already a whole-disk device

        if parent.startswith("nvme"):
            return f"NVMe SSD ({parent})"

        rota_path = f"/sys/block/{parent}/queue/rotational"
        try:
            with open(rota_path) as f:
                rota = f.read().strip()
            kind = "HDD" if rota == "1" else "SSD"
        except Exception:
            kind = "Unknown"
        return f"{kind} ({parent})"
    except Exception:
        return "Unknown"


def _get_installed_aur_helpers():
    """Which AUR helper binaries are actually present on the system —
    independent of which one Pachul is currently configured to use, since
    that's a separate question from what's simply installed."""
    found = []
    for helper in ("pachuli", "yay", "paru", "pikaur", "trizen"):
        _, code = run_command(f"which {helper} 2>/dev/null")
        if code == 0:
            found.append(helper)
    return found


def get_system_info():
    """System overview, derived in-process where possible (no shell pipelines)."""
    info = {}
    uname = os.uname()
    info["Kernel"] = uname.release
    info["Architecture"] = uname.machine

    os_name = "Unknown"
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_name = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass
    info["OS"] = os_name
    info["Desktop"] = _get_desktop_info()

    if distro.is_arch():
        out, code = run_command("pacman -V 2>/dev/null")
        m = re.search(r"Pacman v?([\w.\-]+)", out) if (out and code == 0) else None
        info["Pacman"] = m.group(1) if m else "Unknown"
    else:
        pm = distro.get_package_manager()
        out, code = run_command(f"{pm} --version 2>/dev/null", timeout=10) if pm else ("", 1)
        first_line = out.splitlines()[0] if (out and code == 0) else "Unknown"
        info["Package Manager"] = f"{pm} ({first_line})" if pm else "Unknown"

    if distro.is_arch():
        aur_helpers = _get_installed_aur_helpers()
        info["AUR Helper"] = ", ".join(aur_helpers) if aur_helpers else "None installed"

    info["Processor"] = _get_cpu_info()

    try:
        du = shutil.disk_usage("/")
        pct = round(du.used / du.total * 100) if du.total else 0
        info["Disk (/)"] = f"{_human_size(du.used)} / {_human_size(du.total)} ({pct}% used)"
    except Exception:
        info["Disk (/)"] = "N/A"
    info["Disk Type"] = _get_disk_type()

    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    meminfo[key] = int(rest.split()[0]) * 1024   # kB → bytes
        total = meminfo.get("MemTotal", 0)
        if total:
            used = total - meminfo.get("MemAvailable", 0)
            info["RAM"] = f"{_human_size(used)} / {_human_size(total)}"
        else:
            info["RAM"] = "N/A"
    except Exception:
        info["RAM"] = "N/A"

    if distro.is_arch():
        # Installed count = subdirs of the local pacman DB (no subprocess needed)
        try:
            with os.scandir("/var/lib/pacman/local") as it:
                info["Installed Packages"] = str(sum(1 for e in it if e.is_dir()))
        except OSError:
            out, code = run_command("pacman -Q 2>/dev/null")
            info["Installed Packages"] = str(len(out.splitlines())) if (out and code == 0) else "N/A"

        out, code = run_command("pacman -Qm 2>/dev/null")
        foreign_count = len(out.splitlines()) if (out and code == 0) else 0
        info["Foreign (AUR) Packages"] = str(foreign_count)

        # Per-repository breakdown of installed packages. `pacman -Sl` lists
        # every package in every enabled sync repo and marks the ones that are
        # currently installed with "[installed" (pacman appends the installed
        # version too if it differs) — one pass gives an installed-count per
        # repo without needing a separate cross-reference query.
        repo_counts = {}
        out, code = run_command("pacman -Sl 2>/dev/null")
        if out and code == 0:
            for line in out.splitlines():
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                repo, rest = parts[0], parts[2]
                if "[installed" in rest:
                    repo_counts[repo] = repo_counts.get(repo, 0) + 1
        if foreign_count:
            repo_counts["aur / foreign"] = foreign_count
        info["Repo Counts"] = repo_counts
    else:
        cmd = pkgmanager._installed_fingerprint_cmd()
        out, code = (run_command(cmd) if cmd else ("", 1))
        info["Installed Packages"] = str(len(out.splitlines())) if (out and code == 0) else "N/A"
        info["Repo Counts"] = {}

    info["Package Cache Size"] = get_package_cache_size()

    return info


# ─── Pacman log / history ─────────────────────────────────────────────────────

PACMAN_LOG = Path("/var/log/pacman.log")
_LOG_RE = re.compile(
    r"^\[(.*?)\]\s+\[ALPM\]\s+"
    r"(installed|removed|upgraded|downgraded|reinstalled)\s+(\S+)\s+\((.*?)\)")


def get_pacman_history(limit=500):
    """Parse recent package transactions, newest first. Despite the name
    (kept for compatibility with existing callers), this now covers
    apt/dnf/zypper's own transaction logs too when not on Arch."""
    if not distro.is_arch():
        return pkgmanager.get_package_history(limit)
    try:
        lines = PACMAN_LOG.read_text(errors="replace").splitlines()
    except Exception:
        return []
    entries = []
    for line in lines:
        m = _LOG_RE.match(line)
        if m:
            ts, action, name, ver = m.groups()
            entries.append({"time": ts, "action": action, "name": name, "version": ver})
    entries.reverse()
    return entries[:limit]


# ─── Real program icons (installed packages, Flatpak downloads) ───────────────

def _parse_desktop_icon(path):
    """Read the Icon= value out of a .desktop file's [Desktop Entry]
    section. Returns None if the file can't be read or has no Icon= key."""
    try:
        in_entry = False
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line == "[Desktop Entry]":
                    in_entry = True
                    continue
                if line.startswith("[") and line != "[Desktop Entry]":
                    if in_entry:
                        break
                    continue
                if in_entry and line.startswith("Icon="):
                    return line[len("Icon="):].strip() or None
    except Exception:
        pass
    return None


def build_desktop_icon_map():
    """Scan installed .desktop files once and map package/app identifier ->
    icon value (bare theme name or absolute path, straight from Icon=).

    Two sources, handled differently:
      - Ordinary repo/AUR packages: .desktop files under the system (and
        user) applications dirs, resolved back to their owning package via
        pkgmanager.owning_package_for_file() (one pacman/dpkg/rpm query
        per .desktop file — there are usually only a few dozen to a few
        hundred of these, so this is cheap enough to do synchronously in
        a background thread on every full package reload).
      - Flatpak: exported .desktop files are named exactly after the
        Flatpak application ID (e.g. org.gimp.GIMP.desktop), which is
        also what Pachul stores as pkg_source_id — no ownership lookup
        needed, the filename stem *is* the key.

    Best-effort throughout: any package whose .desktop file is missing,
    unreadable, or has no Icon= key is simply left out of the map, and
    callers fall back to the existing symbolic icon set.
    """
    import glob
    mapping = {}

    system_dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]
    for d in system_dirs:
        for path in glob.glob(os.path.join(d, "*.desktop")):
            icon_val = _parse_desktop_icon(path)
            if not icon_val:
                continue
            pkg = pkgmanager.owning_package_for_file(path)
            if pkg:
                mapping.setdefault(pkg, icon_val)

    flatpak_dirs = [
        "/var/lib/flatpak/exports/share/applications",
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    ]
    for d in flatpak_dirs:
        for path in glob.glob(os.path.join(d, "*.desktop")):
            app_id = os.path.splitext(os.path.basename(path))[0]
            icon_val = _parse_desktop_icon(path)
            if icon_val:
                mapping.setdefault(app_id, icon_val)

    return mapping


def fetch_flatpak_icon(app_id):
    """Best-effort download of a Flatpak app's icon from Flathub's public,
    unauthenticated icon CDN, cached locally so each app is only fetched
    once. Returns True if the icon is available locally afterwards
    (already cached, or freshly downloaded), False if it couldn't be
    fetched (offline, a non-Flathub remote, or no icon published there) —
    callers should keep showing the existing symbolic icon in that case.
    """
    import urllib.request
    from icons import FLATPAK_ICON_CACHE_DIR
    if not app_id:
        return False
    dest = FLATPAK_ICON_CACHE_DIR / f"{app_id}.png"
    if dest.is_file():
        return True
    url = f"https://dl.flathub.org/repo/appstream/x86_64/icons/128x128/{app_id}.png"
    try:
        FLATPAK_ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Pachul"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.rename(dest)
        return True
    except Exception:
        return False


# ─── AUR package metadata (votes / popularity / maintainer) ───────────────────

def get_aur_info(pkg_name):
    """Fetch AUR metadata for pkg_name via the official AUR RPC API
    (https://aur.archlinux.org/rpc/v5/info). Returns a dict with keys like
    NumVotes, Popularity, Maintainer, LastModified, OutOfDate — or None if
    the package isn't on AUR, or the request fails (e.g. offline).

    The RPC doesn't expose comments, so callers should instead link out to
    the package's AUR web page for those.
    """
    import urllib.request
    import urllib.parse
    url = ("https://aur.archlinux.org/rpc/v5/info?arg[]="
           + urllib.parse.quote(pkg_name, safe=""))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Pachul"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    results = data.get("results") or []
    return results[0] if results else None


# ─── Pre-upgrade snapshot (Timeshift / Snapper) ────────────────────────────────

def detect_snapshot_tool():
    """Detect an available system-snapshot tool for the pre-upgrade safety net.

    Returns (tool, extra):
      ("timeshift", None)       — Timeshift is installed
      ("snapper", "<config>")   — Snapper is installed; extra is the first
                                    configured snapshot config (e.g. "root")
      (None, None)              — neither is installed
    Timeshift is preferred when both are present since it snapshots the
    whole system by default, without needing a config name.
    """
    _, code = run_command("which timeshift 2>/dev/null")
    if code == 0:
        return "timeshift", None
    _, code = run_command("which snapper 2>/dev/null")
    if code == 0:
        cfg_out, _ = run_command(
            "snapper list-configs 2>/dev/null | awk 'NR>2{print $1}' | head -1")
        cfg = cfg_out.strip() or "root"
        return "snapper", cfg
    return None, None


def build_snapshot_cmd(comment="Pachul: before system upgrade"):
    """Shell command that creates a pre-upgrade snapshot, or None if no
    supported snapshot tool (Timeshift/Snapper) is installed."""
    tool, info = detect_snapshot_tool()
    if tool == "timeshift":
        return f"pkexec /usr/bin/timeshift --create --comments {shlex.quote(comment)} --scripted"
    if tool == "snapper":
        return f"pkexec /usr/bin/snapper -c {shlex.quote(info)} create --description {shlex.quote(comment)}"
    return None


# ─── Explicit-package export ──────────────────────────────────────────────────

def get_explicit_packages():
    """Names of explicitly-installed packages, repo + AUR (or apt/dnf/
    zypper's equivalent "manually installed" concept elsewhere)."""
    if not distro.is_arch():
        return pkgmanager.get_explicit_packages()
    out, code = run_command("pacman -Qqe 2>/dev/null")
    return out.splitlines() if (out and code == 0) else []


# ─── Downgrade: cached package versions ───────────────────────────────────────

def get_pkgbuild(pkg_name):
    """Fetch the PKGBUILD text for an AUR package (helper first, then the AUR web).
    PKGBUILDs are an Arch/AUR-specific concept; on other distros this is
    unreachable in practice since no package there is ever pkg_foreign."""
    if not distro.is_arch():
        return f"# PKGBUILDs only exist on Arch Linux (AUR) — not applicable here.\n"
    helper = _find_aur_helper()
    if helper:
        cmd = f"pachuli -Sp {shlex.quote(pkg_name)} -g" if helper == "pachuli" else f"{helper} -Gp {shlex.quote(pkg_name)}"
        out, code = run_command(cmd, timeout=30)
        if out and code == 0:
            return _strip_ansi(out)
    import urllib.request
    url = f"https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h={pkg_name}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"# Could not fetch PKGBUILD for {pkg_name}\n# {e}\n"


# ─── .pacnew / .pacsave config files ──────────────────────────────────────────

def get_pacnew_files():
    """Find config-file-conflict markers that need merging/reviewing:
    .pacnew/.pacsave on Arch, .dpkg-dist/.dpkg-old/.ucf-dist on Debian,
    .rpmnew/.rpmsave on Fedora/openSUSE."""
    if not distro.is_arch():
        return pkgmanager.get_config_conflict_files()
    out, _ = run_command(
        "find /etc /usr /boot /opt -xdev "
        "\\( -name '*.pacnew' -o -name '*.pacsave' \\) 2>/dev/null", timeout=30)
    files = []
    for line in out.splitlines():
        line = line.strip()
        if line.endswith(".pacnew") or line.endswith(".pacsave"):
            files.append({
                "new": line,
                "orig": line.rsplit(".", 1)[0],
                "kind": "pacnew" if line.endswith(".pacnew") else "pacsave",
            })
    return files


def get_file_diff(orig, new):
    out, _ = run_command(
        f"diff -u {shlex.quote(orig)} {shlex.quote(new)} 2>/dev/null", timeout=15)
    return out or "(files are identical or could not be read)"


# ─── External tool updaters ───────────────────────────────────────────────────
# Detection + update commands for developer/system tools that live outside
# pacman/Flatpak/Snap and therefore never show up in check_updates(). Every
# entry below only runs each tool's own --version/list/check subcommand for
# detection — nothing here changes the system until the user explicitly
# picks "Update" in the dialog.
#
# Each static spec dict:
#   id           unique id
#   name         display name (English; looked up through i18n.tr() in the UI)
#   binaries     list of candidate executable names, first match wins
#   version_cmd  optional "{bin} --version"-style command (first line kept)
#   check_cmd    optional command whose output is shown as detail/preview
#   update_cmd   command that performs the update; may use "{bin}"
#   note         optional explanatory caption shown under the row

TOOL_SPECS = [
    {
        "id": "firmware", "name": "Firmware (fwupdmgr)",
        "binaries": ["fwupdmgr"],
        "version_cmd": "fwupdmgr --version 2>/dev/null | head -1",
        "check_cmd": "fwupdmgr refresh --force >/dev/null 2>&1; fwupdmgr get-updates 2>&1",
        "update_cmd": "fwupdmgr update -y",
        "note": "Firmware updates for the mainboard, SSDs, and other devices via fwupd.",
    },
    {
        "id": "rustup", "name": "Rust Toolchains (rustup)",
        "binaries": ["rustup"],
        "version_cmd": "rustup --version 2>/dev/null | head -1",
        "check_cmd": "rustup check 2>&1",
        "update_cmd": "rustup update",
        "note": "",
    },
    {
        "id": "pip", "name": "pip (--user packages)",
        "binaries": ["pip", "pip3"],
        "version_cmd": None,
        "check_cmd": "{bin} list --outdated --user --format=freeze 2>/dev/null",
        "update_cmd": ("{bin} list --outdated --user --format=freeze 2>/dev/null "
                        "| grep -v '^-e' | cut -d= -f1 | xargs -r -n1 {bin} install --user -U"),
        "note": "Upgrades every outdated package installed with --user.",
    },
    {
        "id": "pipx", "name": "pipx",
        "binaries": ["pipx"],
        "version_cmd": None,
        "check_cmd": "pipx list --short 2>/dev/null",
        "update_cmd": "pipx upgrade-all",
        "note": "",
    },
    {
        "id": "npm", "name": "npm (global packages)",
        "binaries": ["npm"],
        "version_cmd": None,
        "check_cmd": "npm outdated -g 2>/dev/null",
        "update_cmd": "npm update -g",
        "note": "",
    },
    {
        "id": "claude_code", "name": "Claude Code",
        "binaries": ["claude"],
        "version_cmd": "claude --version 2>/dev/null | head -1",
        "check_cmd": None,
        "update_cmd": "claude update",
        "note": "",
    },
    {
        "id": "lensfun", "name": "Lensfun Camera/Lens Database",
        "binaries": ["lensfun-update-data"],
        "version_cmd": None,
        "check_cmd": None,
        "update_cmd": "lensfun-update-data",
        "note": "Fetches the latest camera/lens calibration data used by darktable, digiKam, and similar apps.",
    },
    {
        "id": "uv", "name": "uv (Python package/tool manager)",
        "binaries": ["uv"],
        "version_cmd": "uv --version 2>/dev/null",
        "check_cmd": None,
        "update_cmd": "uv self update",
        "note": "Only works for the standalone uv installer — a pacman/AUR install is updated there instead.",
    },
    {
        "id": "fnm", "name": "fnm (Fast Node Manager)",
        "binaries": ["fnm"],
        "version_cmd": "fnm --version 2>/dev/null",
        "check_cmd": None,
        "update_cmd": "fnm install --lts",
        "note": "Installs the latest Node.js LTS release via fnm.",
    },
]


def _cargo_update_check():
    """cargo-installed binaries, via the separate cargo-update subcommand
    (cargo install cargo-update). Detected dynamically because whether the
    subcommand itself is installed changes the update command we offer."""
    if not shutil.which("cargo"):
        return None
    out, _ = run_command("cargo install-update -l 2>&1", timeout=20)
    out = out or ""
    if "no such subcommand" in out.lower() or "no such command" in out.lower():
        return {
            "id": "cargo", "name": "Cargo (crates.io binaries)",
            "version": "", "detail": "",
            "update_cmd": "cargo install cargo-update && cargo install-update -a",
            "launch_cmd": None,
            "note": "Installs the 'cargo-update' helper crate first, then upgrades all cargo-installed binaries.",
        }
    return {
        "id": "cargo", "name": "Cargo (crates.io binaries)",
        "version": "", "detail": out.strip(),
        "update_cmd": "cargo install-update -a",
        "launch_cmd": None,
        "note": "",
    }


def _gh_extensions_check():
    """Only offered when gh is installed AND at least one extension is
    present — gh itself is often installed without any extensions."""
    if not shutil.which("gh"):
        return None
    out, code = run_command("gh extension list 2>/dev/null", timeout=15)
    if code != 0 or not (out or "").strip():
        return None
    return {
        "id": "gh_extensions", "name": "GitHub CLI Extensions",
        "version": "", "detail": out.strip(),
        "update_cmd": "gh extension upgrade --all",
        "launch_cmd": None,
        "note": "",
    }


def _ollama_check():
    """Skipped when Ollama is a pacman/AUR package — the regular update
    list (check_updates) already covers that case."""
    if not shutil.which("ollama"):
        return None
    _, code = run_command("pacman -Qq ollama 2>/dev/null", timeout=10)
    if code == 0:
        return None
    version, _ = run_command("ollama --version 2>/dev/null", timeout=10)
    return {
        "id": "ollama", "name": "Ollama",
        "version": (version or "").strip(), "detail": "",
        "update_cmd": "curl -fsSL https://ollama.com/install.sh | sh",
        "launch_cmd": None,
        "note": "Re-runs the official installer script to fetch the latest release.",
    }


def _find_pycharm_binary():
    """Locate a PyCharm CLI launcher script — plain install, Toolbox
    install, or a manual/AUR install under /opt."""
    for name in ("pycharm", "pycharm.sh"):
        found = shutil.which(name)
        if found:
            return found
    toolbox_apps = Path.home() / ".local" / "share" / "JetBrains" / "Toolbox" / "apps"
    try:
        for pattern in ("PyCharm-P/ch-*/*/bin/pycharm.sh", "PyCharm-C/ch-*/*/bin/pycharm.sh"):
            matches = sorted(toolbox_apps.glob(pattern), reverse=True)
            if matches:
                return str(matches[0])
    except Exception:
        pass
    for pattern in ("/opt/pycharm*/bin/pycharm.sh", "/usr/share/pycharm/bin/pycharm.sh"):
        matches = sorted(Path("/").glob(pattern.lstrip("/")), reverse=True)
        if matches:
            return str(matches[0])
    return None


def _pycharm_plugins_dir():
    """XDG data dir holding installed PyCharm plugins
    (~/.local/share/JetBrains/PyCharm<version>/) — picks the most
    recently used version directory if several are present."""
    base = Path.home() / ".local" / "share" / "JetBrains"
    try:
        dirs = [d for d in base.glob("PyCharm*") if d.is_dir()]
    except Exception:
        return None
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


def _extract_plugin_id(plugin_dir):
    """Read the <id> out of a plugin's plugin.xml, packed inside one of
    its lib/*.jar files."""
    lib_dir = plugin_dir / "lib"
    if not lib_dir.is_dir():
        return None
    try:
        jars = list(lib_dir.glob("*.jar"))
    except Exception:
        return None
    for jar_path in jars:
        try:
            with zipfile.ZipFile(jar_path) as zf:
                if "META-INF/plugin.xml" not in zf.namelist():
                    continue
                with zf.open("META-INF/plugin.xml") as f:
                    root = ET.fromstring(f.read())
                    id_el = root.find("id")
                    if id_el is not None and id_el.text:
                        return id_el.text.strip()
        except Exception:
            continue
    return None


def _pycharm_installed_plugin_ids():
    plugins_dir = _pycharm_plugins_dir()
    if not plugins_dir:
        return []
    ids = []
    try:
        for entry in plugins_dir.iterdir():
            if not entry.is_dir():
                continue
            pid = _extract_plugin_id(entry)
            if pid:
                ids.append(pid)
    except Exception:
        pass
    return ids


def _jetbrains_plugins_check():
    """Updates PyCharm plugins from the command line the same way
    topgrade does it: JetBrains IDEs have no dedicated 'update plugins'
    verb, but re-running 'installPlugins <id>' for an already-installed
    plugin always fetches the latest compatible version and overwrites
    the old one — so calling it for every detected plugin ID amounts to
    updating all of them. PyCharm must be closed for this to work (the
    launcher refuses a second instance against the same config).
    Falls back to just launching Toolbox/PyCharm if the CLI launcher or
    the installed plugin IDs can't be determined."""
    binary = _find_pycharm_binary()
    ids = _pycharm_installed_plugin_ids() if binary else []
    if binary and ids:
        quoted_ids = " ".join(shlex.quote(i) for i in ids)
        return {
            "id": "jetbrains_plugins", "name": "JetBrains PyCharm Plugins",
            "version": "", "detail": "\n".join(ids),
            "update_cmd": f"{shlex.quote(binary)} installPlugins {quoted_ids}",
            "launch_cmd": None,
            "note": "Re-installs every detected plugin at its latest compatible version "
                    "(the same trick topgrade uses) — close PyCharm first.",
        }

    try:
        config_dirs = list(Path.home().glob(".config/JetBrains/PyCharm*"))
    except Exception:
        config_dirs = []
    toolbox = shutil.which("jetbrains-toolbox")
    fallback_bin = binary or shutil.which("pycharm") or shutil.which("pycharm.sh")
    if not (config_dirs or toolbox or fallback_bin):
        return None
    return {
        "id": "jetbrains_plugins", "name": "JetBrains PyCharm Plugins",
        "version": "", "detail": "",
        "update_cmd": None,
        "launch_cmd": toolbox or fallback_bin,
        "note": "Couldn't determine the CLI launcher or installed plugin IDs automatically — "
                "this opens Toolbox/PyCharm so you can use Settings \u2192 Plugins \u2192 Update All instead.",
    }


def _nvm_check():
    """nvm installs as a shell function (nvm.sh), not a binary on PATH, so
    detection is by directory rather than shutil.which."""
    script = Path.home() / ".nvm" / "nvm.sh"
    if not script.exists():
        return None
    version, _ = run_command(
        f"bash -lc 'source {shlex.quote(str(script))}; nvm --version' 2>/dev/null", timeout=15)
    return {
        "id": "nvm", "name": "nvm (Node Version Manager)",
        "version": (version or "").strip(), "detail": "",
        "update_cmd": (f"bash -lc 'source {shlex.quote(str(script))}; "
                        "nvm install --lts; nvm alias default lts/*'"),
        "launch_cmd": None,
        "note": "Installs the latest Node.js LTS release and sets it as the default.",
    }


def _pyenv_check():
    if not shutil.which("pyenv"):
        return None
    version, _ = run_command("pyenv --version 2>/dev/null", timeout=10)
    pyenv_root = os.environ.get("PYENV_ROOT", str(Path.home() / ".pyenv"))
    return {
        "id": "pyenv", "name": "pyenv (Python Version Manager)",
        "version": (version or "").strip(), "detail": "",
        "update_cmd": f"pyenv update 2>/dev/null || (cd {shlex.quote(pyenv_root)} && git pull)",
        "launch_cmd": None,
        "note": "Updates pyenv itself — install new Python versions separately with 'pyenv install'.",
    }


def _sdkman_check():
    """SDKMAN's 'sdk' command is a shell function too, sourced from
    sdkman-init.sh rather than being a plain executable."""
    init_script = Path.home() / ".sdkman" / "bin" / "sdkman-init.sh"
    if not init_script.exists():
        return None
    return {
        "id": "sdkman", "name": "SDKMAN (Java/Kotlin/Gradle/Maven)",
        "version": "", "detail": "",
        "update_cmd": f"bash -lc 'source {shlex.quote(str(init_script))}; sdk selfupdate; sdk update'",
        "launch_cmd": None,
        "note": "Updates SDKMAN itself and its candidate index — not each installed SDK version.",
    }


def _conda_check():
    """Prefers mamba over conda when both are present (same base env, mamba
    is just the faster front end)."""
    binary = shutil.which("mamba") or shutil.which("conda")
    if not binary:
        return None
    cmd_name = os.path.basename(binary)
    version, _ = run_command(f"{shlex.quote(binary)} --version 2>/dev/null", timeout=10)
    if cmd_name == "mamba":
        update_cmd = "mamba update --all -y"
        name = "Mamba (base environment)"
    else:
        update_cmd = "conda update -n base -c defaults conda -y && conda update --all -y"
        name = "Conda (base environment)"
    return {
        "id": "conda", "name": name,
        "version": (version or "").strip(), "detail": "",
        "update_cmd": update_cmd,
        "launch_cmd": None,
        "note": "Updates the base environment only — other environments need updating separately.",
    }


def _texlive_check():
    """Skipped when TeX Live is a pacman/AUR package — the regular update
    list (check_updates) already covers that case."""
    if not shutil.which("tlmgr"):
        return None
    _, code = run_command("pacman -Qo $(command -v tlmgr) 2>/dev/null", timeout=10)
    if code == 0:
        return None
    version, _ = run_command("tlmgr --version 2>/dev/null | head -1", timeout=10)
    return {
        "id": "texlive", "name": "TeX Live (tlmgr)",
        "version": (version or "").strip(), "detail": "",
        "update_cmd": "tlmgr update --self --all",
        "launch_cmd": None,
        "note": "",
    }


def _vscode_extensions_check():
    binary = shutil.which("code") or shutil.which("codium")
    if not binary:
        return None
    out, code = run_command(f"{shlex.quote(binary)} --list-extensions 2>/dev/null", timeout=15)
    if code != 0 or not (out or "").strip():
        return None
    cmd_name = os.path.basename(binary)
    return {
        "id": "vscode_ext",
        "name": "VS Code Extensions" if cmd_name == "code" else "VSCodium Extensions",
        "version": "", "detail": out.strip(),
        "update_cmd": f"{cmd_name} --list-extensions | xargs -L 1 {cmd_name} --install-extension --force",
        "launch_cmd": None,
        "note": "Reinstalls every extension at its latest Marketplace version.",
    }


def _clamav_db_check():
    if not shutil.which("freshclam"):
        return None
    version, _ = run_command("freshclam --version 2>/dev/null | head -1", timeout=10)
    return {
        "id": "clamav_db", "name": "ClamAV Virus Definitions",
        "version": (version or "").strip(), "detail": "",
        "update_cmd": "pkexec /usr/bin/freshclam",
        "launch_cmd": None,
        "note": "Downloads the latest ClamAV signature database.",
    }


def _docker_images_check():
    if not shutil.which("docker"):
        return None
    out, code = run_command(
        "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -v '<none>'",
        timeout=15)
    if code != 0 or not (out or "").strip():
        return None
    return {
        "id": "docker_images", "name": "Docker Images",
        "version": "", "detail": out.strip(),
        "update_cmd": ("docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null "
                        "| grep -v '<none>' | xargs -L1 docker pull"),
        "launch_cmd": None,
        "note": "Pulls the latest version of every locally tagged image.",
    }


def _podman_images_check():
    if not shutil.which("podman"):
        return None
    out, code = run_command(
        "podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -v '<none>'",
        timeout=15)
    if code != 0 or not (out or "").strip():
        return None
    return {
        "id": "podman_images", "name": "Podman Images",
        "version": "", "detail": out.strip(),
        "update_cmd": ("podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null "
                        "| grep -v '<none>' | xargs -L1 podman pull"),
        "launch_cmd": None,
        "note": "Pulls the latest version of every locally tagged image.",
    }


def _flatpak_unused_check():
    if not (get_setting("flatpak_enabled") and flatpak_available()):
        return None
    out, code = run_command(
        "flatpak list --columns=application --app=false 2>/dev/null", timeout=15)
    if code != 0 or not (out or "").strip():
        return None
    return {
        "id": "flatpak_unused", "name": "Flatpak: Unused Runtimes",
        "version": "", "detail": "",
        "update_cmd": "flatpak uninstall --unused -y",
        "launch_cmd": None,
        "note": "Removes runtimes and extensions no installed app depends on anymore.",
    }


def _vim_neovim_plugins_check():
    """Detects whichever plugin manager is present and picks the matching
    headless update invocation — lazy.nvim and packer.nvim take priority
    over vim-plug when more than one is found, matching how most users
    who have several actually only use the newest one."""
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))

    if shutil.which("nvim"):
        lazy_dir = data_home / "nvim" / "lazy" / "lazy.nvim"
        packer_dir = data_home / "nvim" / "site" / "pack" / "packer" / "start" / "packer.nvim"
        plug_file = data_home / "nvim" / "site" / "autoload" / "plug.vim"
        if lazy_dir.is_dir():
            return {
                "id": "nvim_plugins", "name": "Neovim Plugins (lazy.nvim)",
                "version": "", "detail": "",
                "update_cmd": 'nvim --headless "+Lazy! sync" +qa',
                "launch_cmd": None, "note": "",
            }
        if packer_dir.is_dir():
            return {
                "id": "nvim_plugins", "name": "Neovim Plugins (packer.nvim)",
                "version": "", "detail": "",
                "update_cmd": ('nvim --headless -c "autocmd User PackerComplete quitall" '
                                '-c "PackerSync"'),
                "launch_cmd": None, "note": "",
            }
        if plug_file.exists():
            return {
                "id": "nvim_plugins", "name": "Neovim Plugins (vim-plug)",
                "version": "", "detail": "",
                "update_cmd": 'nvim --headless "+PlugUpdate" +qa',
                "launch_cmd": None, "note": "",
            }

    if shutil.which("vim"):
        plug_file = Path.home() / ".vim" / "autoload" / "plug.vim"
        if plug_file.exists():
            return {
                "id": "vim_plugins", "name": "Vim Plugins (vim-plug)",
                "version": "", "detail": "",
                "update_cmd": 'vim -Es -c "PlugUpdate" -c "qa"',
                "launch_cmd": None, "note": "",
            }
    return None


def _tmux_tpm_check():
    tpm_script = Path.home() / ".tmux" / "plugins" / "tpm" / "bin" / "update_plugins"
    if not tpm_script.exists():
        return None
    return {
        "id": "tmux_tpm", "name": "tmux Plugins (TPM)",
        "version": "", "detail": "",
        "update_cmd": f"{shlex.quote(str(tpm_script))} all",
        "launch_cmd": None, "note": "",
    }


def _zsh_frameworks_check():
    """Returns a list (0-2 entries) since more than one zsh/fish plugin
    framework can coexist, unlike the other checks here which are 1:1."""
    entries = []

    ohmyzsh_dir = Path(os.environ.get("ZSH", str(Path.home() / ".oh-my-zsh")))
    if ohmyzsh_dir.is_dir() and (ohmyzsh_dir / "tools" / "upgrade.sh").exists():
        entries.append({
            "id": "oh_my_zsh", "name": "Oh My Zsh",
            "version": "", "detail": "",
            "update_cmd": f'env ZSH={shlex.quote(str(ohmyzsh_dir))} sh {shlex.quote(str(ohmyzsh_dir / "tools" / "upgrade.sh"))}',
            "launch_cmd": None, "note": "",
        })

    zinit_dirs = [
        Path.home() / ".local" / "share" / "zinit" / "zinit.git",
        Path.home() / ".zinit" / "bin" / "zinit.zsh",
    ]
    if any(p.exists() for p in zinit_dirs) and shutil.which("zsh"):
        entries.append({
            "id": "zinit", "name": "Zinit (zsh plugin manager)",
            "version": "", "detail": "",
            "update_cmd": 'zsh -ic "zinit self-update; zinit update --all"',
            "launch_cmd": None, "note": "",
        })

    antigen_files = [Path.home() / ".antigen" / "antigen.zsh", Path.home() / ".antigen.zsh"]
    if any(p.exists() for p in antigen_files) and shutil.which("zsh"):
        entries.append({
            "id": "antigen", "name": "Antigen (zsh plugin manager)",
            "version": "", "detail": "",
            "update_cmd": 'zsh -ic "antigen update"',
            "launch_cmd": None, "note": "",
        })

    if shutil.which("sheldon"):
        entries.append({
            "id": "sheldon", "name": "Sheldon (shell plugin manager)",
            "version": "", "detail": "",
            "update_cmd": "sheldon lock --update",
            "launch_cmd": None, "note": "",
        })

    if shutil.which("fish") and shutil.which("fisher"):
        entries.append({
            "id": "fisher", "name": "Fisher (fish plugin manager)",
            "version": "", "detail": "",
            "update_cmd": 'fish -c "fisher update"',
            "launch_cmd": None, "note": "",
        })

    return entries


def _dotfiles_git_repos_check():
    """Auto-discovers common dotfiles/config repos and offers a 'git pull'
    for each — only ones that are an actual git repo AND have a remote
    configured (skipping local-only repos, same as topgrade does)."""
    candidates = [
        Path.home() / ".dotfiles",
        Path.home() / "dotfiles",
        Path.home() / ".config" / "nvim",
        Path.home() / ".vim",
        Path.home() / ".emacs.d",
    ]
    entries = []
    for repo in candidates:
        if not (repo / ".git").exists():
            continue
        _, code = run_command(f"git -C {shlex.quote(str(repo))} remote get-url origin 2>/dev/null", timeout=10)
        if code != 0:
            continue
        entries.append({
            "id": f"git_repo_{repo.name}", "name": f"Git Repo: {repo}",
            "version": "", "detail": "",
            "update_cmd": f"git -C {shlex.quote(str(repo))} pull --ff-only",
            "launch_cmd": None, "note": "",
        })
    return entries


def _getnf_check():
    if not shutil.which("getnf"):
        return None
    return {
        "id": "getnf", "name": "Nerd Fonts (getnf)",
        "version": "", "detail": "",
        "update_cmd": "getnf -U",
        "launch_cmd": None,
        "note": "Updates already-installed Nerd Fonts to their latest release.",
    }


def _tldr_check():
    if not shutil.which("tldr"):
        return None
    return {
        "id": "tldr", "name": "tldr Pages",
        "version": "", "detail": "",
        "update_cmd": "tldr --update",
        "launch_cmd": None, "note": "",
    }


def _nix_check():
    if not (shutil.which("nix-env") or shutil.which("nix")):
        return None
    return {
        "id": "nix", "name": "Nix Packages (nix-env)",
        "version": "", "detail": "",
        "update_cmd": "nix-channel --update && nix-env -u '*'",
        "launch_cmd": None,
        "note": "Classic nix-env profile only \u2014 flake-based setups update differently.",
    }


def _home_manager_check():
    if not shutil.which("home-manager"):
        return None
    return {
        "id": "home_manager", "name": "home-manager",
        "version": "", "detail": "",
        "update_cmd": "home-manager switch",
        "launch_cmd": None, "note": "",
    }


def get_tool_updates():
    """Detect installed external tools (rustup, cargo, pip, pipx, npm, fnm,
    nvm, pyenv, SDKMAN, Conda/Mamba, TeX Live, GitHub CLI extensions,
    Claude Code, VS Code/VSCodium extensions, Lensfun, uv, Ollama, ClamAV
    definitions, Docker/Podman images, Flatpak unused runtimes, JetBrains
    PyCharm plugins, Vim/Neovim/tmux plugin managers, zsh/fish frameworks,
    dotfiles git repos, Nerd Fonts, tldr, Nix/home-manager, firmware via
    fwupd, …) that aren't covered by check_updates(). Returns a list of
    dicts: id, name, version, detail, update_cmd (or None), launch_cmd
    (or None), note. A tool with update_cmd set can be run directly; one
    with only launch_cmd set (JetBrains plugins fallback) has no
    scriptable updater and just gets opened. Purely read-only: only each
    tool's own --version/list/check subcommand runs here, nothing is
    changed."""
    results = []
    for spec in TOOL_SPECS:
        found_bin = next((b for b in spec["binaries"] if shutil.which(b)), None)
        if not found_bin:
            continue
        version = ""
        if spec.get("version_cmd"):
            vout, vcode = run_command(spec["version_cmd"], timeout=10)
            if vcode == 0 and vout:
                version = vout.strip().splitlines()[0]
        detail = ""
        if spec.get("check_cmd"):
            cout, _ = run_command(spec["check_cmd"].format(bin=found_bin), timeout=30)
            detail = (cout or "").strip()
        update_cmd = spec.get("update_cmd")
        if update_cmd:
            update_cmd = update_cmd.format(bin=found_bin)
        # Only npm and pip have a check_cmd output format that's
        # guaranteed to list *only* genuinely outdated items (no
        # "up to date" rows mixed in) — rustup check, cargo install-update
        # -l, gh extension list, pipx list, etc. all show every installed
        # item regardless of status, so counting their lines would
        # overstate how much is actually pending. Left None there rather
        # than showing a misleading number.
        outdated_count = None
        if detail:
            if spec["id"] == "npm":
                # "npm outdated -g" output: one header line, then one row
                # per outdated package (it never lists up-to-date ones).
                outdated_count = max(0, len(detail.splitlines()) - 1)
            elif spec["id"] == "pip":
                # "--format=freeze" output: exactly one line per outdated
                # package, no header.
                outdated_count = len(detail.splitlines())
        results.append({
            "id": spec["id"], "name": spec["name"], "version": version,
            "detail": detail, "update_cmd": update_cmd, "launch_cmd": None,
            "note": spec.get("note", ""), "outdated_count": outdated_count,
        })

    for fn in (_cargo_update_check, _gh_extensions_check, _ollama_check,
               _jetbrains_plugins_check, _nvm_check, _pyenv_check, _sdkman_check,
               _conda_check, _texlive_check, _vscode_extensions_check,
               _clamav_db_check, _docker_images_check, _podman_images_check,
               _flatpak_unused_check, _vim_neovim_plugins_check, _tmux_tpm_check,
               _getnf_check, _tldr_check, _nix_check, _home_manager_check):
        entry = fn()
        if entry:
            results.append(entry)

    for fn in (_zsh_frameworks_check, _dotfiles_git_repos_check):
        results.extend(fn())

    return results


def get_enabled_auto_update_commands():
    """Re-scans get_tool_updates() and returns [(name, update_cmd), ...]
    for every tool the user has opted into auto-running alongside the
    normal system upgrade (via the 'More Update Sources' checkboxes).
    Re-scanning rather than trusting the saved list means a tool that was
    uninstalled since being enabled is silently skipped instead of
    failing the whole upgrade chain. Launch-only entries (no update_cmd,
    e.g. the JetBrains fallback) can't run headlessly and are excluded."""
    enabled_ids = set(get_setting("auto_update_tool_ids") or [])
    if not enabled_ids:
        return []
    commands = []
    for t in get_tool_updates():
        if t["id"] in enabled_ids and t.get("update_cmd"):
            commands.append((t["name"], t["update_cmd"]))
    return commands


# ─── IgnorePkg (hold) ─────────────────────────────────────────────────────────

PACMAN_CONF = Path("/etc/pacman.conf")


def chaotic_aur_configured():
    """Whether chaotic-aur is set up as a repo in /etc/pacman.conf. A
    plain file read rather than a `pacman -Sl`/`pacman -Sy` subprocess
    call, since this is checked at sidebar-build time (window.py's
    _build_sidebar()) — before packages, and thus pacman's sync
    databases, are necessarily loaded at all."""
    if not distro.is_arch():
        return False
    try:
        content = PACMAN_CONF.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(re.search(r"^\[chaotic-aur\]", content, re.MULTILINE))


def _conf_directive_values(lines, key):
    """Alle Werte einer pacman.conf-Direktive (z.B. IgnorePkg) aus ALLEN
    passenden, nicht auskommentierten Zeilen. Inline-Kommentare
    ("IgnorePkg = foo # Grund") werden abgeschnitten. Gibt
    (Zeilenindizes, Menge der Werte) zurück."""
    pat = re.compile(r"^" + re.escape(key) + r"\s*=(.*)$")
    idxs, values = [], set()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#"):
            continue
        m = pat.match(s)
        if not m:
            continue
        idxs.append(i)
        values.update(m.group(1).split("#", 1)[0].split())
    return idxs, values


def get_ignored_packages():
    """Set of packages currently held back from upgrades — via IgnorePkg
    in pacman.conf on Arch, or the matching native hold/lock mechanism
    on apt/openSUSE (dnf has no reliable built-in equivalent)."""
    if not distro.is_arch():
        return pkgmanager.get_held_packages()
    try:
        lines = PACMAN_CONF.read_text(errors="replace").splitlines()
    except Exception:
        return set()
    return _conf_directive_values(lines, "IgnorePkg")[1]


def _pacman_conf_list(key):
    """Werte einer pacman.conf-Direktive über `pacman-conf` (löst auch
    Include-Dateien und mehrere Zeilen korrekt auf). Leere Liste, wenn
    pacman-conf nicht verfügbar ist."""
    if not shutil.which("pacman-conf"):
        return []
    out, code = run_command(f"pacman-conf {shlex.quote(key)} 2>/dev/null", timeout=10)
    if code != 0 or not out:
        return []
    return [x.strip() for x in out.splitlines() if x.strip()]


def _ignore_patterns():
    """(Muster, Gruppen) aus IgnorePkg / IgnoreGroup. Quelle: pacman-conf
    plus direktes Lesen von /etc/pacman.conf als Rückfall. Muster dürfen
    Wildcards enthalten (wie bei pacman selbst)."""
    pats = set(_pacman_conf_list("IgnorePkg"))
    groups = set(_pacman_conf_list("IgnoreGroup"))
    try:
        lines = PACMAN_CONF.read_text(errors="replace").splitlines()
        pats |= _conf_directive_values(lines, "IgnorePkg")[1]
        groups |= _conf_directive_values(lines, "IgnoreGroup")[1]
    except Exception:
        pass
    return pats, groups


def filter_ignored_updates(updates):
    """Entfernt Pakete, die pacman per IgnorePkg / IgnoreGroup von
    Upgrades ausschliesst, aus einer Update-Liste. `checkupdates` und
    `pacman -Qu` listen solche Pakete trotzdem auf (nur mit dem Zusatz
    "[ignored]"), ein AUR-Helper je nach Version ebenfalls — ohne diesen
    Filter würden sie in pachul als Update erscheinen, obwohl ein
    System-Upgrade sie überspringt. Nur für Arch relevant."""
    if not updates or not distro.is_arch():
        return updates
    import fnmatch
    pats, groups = _ignore_patterns()
    for g in groups:
        out, code = run_command(f"pacman -Sgq {shlex.quote(g)} 2>/dev/null", timeout=15)
        if code == 0 and out:
            pats.update(x.strip() for x in out.splitlines() if x.strip())
    if not pats:
        return updates
    return [u for u in updates
            if not any(fnmatch.fnmatchcase(u["name"], p) for p in pats)]


def _write_ignorepkg(lines, idxs, current):
    """Schreibt die IgnorePkg-Werte `current` zurück in `lines`: Die erste
    vorhandene IgnorePkg-Zeile wird aktualisiert, weitere (doppelte)
    IgnorePkg-Zeilen werden entfernt — ihre Werte sind in `current`
    bereits enthalten. Ist `current` leer, werden alle Zeilen entfernt.
    Existiert noch keine Zeile, wird sie unter [options] eingefügt.
    Gibt den Pfad einer Temp-Datei mit dem neuen Inhalt zurück."""
    if idxs:
        if current:
            lines[idxs[0]] = "IgnorePkg = " + " ".join(sorted(current))
            drop = idxs[1:]
        else:
            drop = idxs
        for i in sorted(drop, reverse=True):
            del lines[i]
    elif current:
        new_line = "IgnorePkg = " + " ".join(sorted(current))
        for i, line in enumerate(lines):
            if line.strip() == "[options]":
                lines.insert(i + 1, new_line)
                break
        else:
            lines.append(new_line)

    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="pachul-pacman-conf-", suffix=".conf")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    return tmp


def set_package_ignored(pkg_name, ignore):
    """Compute a pacman.conf with pkg_name added to / removed from IgnorePkg and
    write it to a temp file. Returns the temp path, or None if no change is needed.

    The editing happens here in Python (safe); the caller just needs to copy the
    temp file over /etc/pacman.conf with root privileges.
    """
    return set_packages_ignored([pkg_name], ignore)


def set_packages_ignored(pkg_names, ignore):
    """Batch version of set_package_ignored: adds/removes several package
    names to/from IgnorePkg in a single pass, returning one temp file to
    install. Returns None if none of the requested names actually needed
    a change (all already in the requested state). Berücksichtigt alle
    IgnorePkg-Zeilen der Datei (auch von Hand ergänzte)."""
    try:
        lines = PACMAN_CONF.read_text().splitlines()
    except Exception:
        return None

    idxs, current = _conf_directive_values(lines, "IgnorePkg")

    names = set(pkg_names)
    if ignore:
        changed = bool(names - current)
        current |= names
    else:
        changed = bool(names & current)
        current -= names
    if not changed:
        return None

    return _write_ignorepkg(lines, idxs, current)


def build_hold_cmd(pkg_name, hold):
    """Ready-to-run shell command that holds/unholds a single package from
    upgrades, regardless of distro — the terminal-dialog callers in
    window.py just run whatever this returns, without needing to know
    whether that means editing pacman.conf or calling apt-mark/zypper
    directly. Returns None if holding isn't supported/needed here (e.g.
    already in the requested state, or no equivalent exists at all — dnf
    has no reliable built-in hold mechanism)."""
    if not distro.is_arch():
        return pkgmanager.hold_cmd(pkg_name, hold)
    tmp = set_package_ignored(pkg_name, hold)
    if tmp is None:
        return None
    return f"pkexec /usr/bin/install -m644 {shlex.quote(tmp)} /etc/pacman.conf"


def build_hold_cmd_bulk(pkg_names, hold):
    """Same as build_hold_cmd(), for several packages in one shot."""
    if not distro.is_arch():
        return pkgmanager.hold_cmd_bulk(pkg_names, hold)
    tmp = set_packages_ignored(pkg_names, hold)
    if tmp is None:
        return None
    return f"pkexec /usr/bin/install -m644 {shlex.quote(tmp)} /etc/pacman.conf"


ARCH_ARCHIVE_URL = "https://archive.archlinux.org/packages"


def get_arch_archive_versions(pkg_name, timeout=15):
    """Alle im Arch Linux Archive abgelegten Versionen von pkg_name als
    [{"version","source","kind":"url","date"}, ...], neueste zuerst.
    Leere Liste bei Netzwerkfehler oder wenn das Paket dort nicht
    existiert (z.B. AUR-Pakete). Blockiert bis zum Timeout — nicht im
    GTK-Hauptthread aufrufen."""
    import urllib.request
    from datetime import datetime
    if not pkg_name:
        return []
    dir_url = f"{ARCH_ARCHIVE_URL}/{pkg_name[0]}/{pkg_name}/"
    try:
        req = urllib.request.Request(dir_url, headers={"User-Agent": "Pachul"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    # Zeile: <a href="NAME-VER-REL-ARCH.pkg.tar.zst">…</a>   03-Oct-2024 12:34  size
    row_re = re.compile(
        r'<a href="(?P<file>[^"/]+\.pkg\.tar\.(?:zst|xz))"[^>]*>[^<]*</a>'
        r'\s+(?P<date>\d{2}-\w{3}-\d{4} \d{2}:\d{2})')
    found = {}
    for m in row_re.finditer(html):
        fname = m.group("file")
        stem = re.sub(r"\.pkg\.tar\.\w+$", "", fname)
        parts = stem.rsplit("-", 3)       # name-ver-rel-arch
        if len(parts) != 4 or parts[0] != pkg_name:
            continue
        try:
            ts = datetime.strptime(m.group("date"), "%d-%b-%Y %H:%M")
        except ValueError:
            ts = datetime.min
        version = f"{parts[1]}-{parts[2]}"
        if version not in found or ts > found[version][0]:
            found[version] = (ts, fname)
    out = [{"version": v, "source": f"{dir_url}{fname}", "kind": "url", "date": ts}
           for v, (ts, fname) in found.items()]
    out.sort(key=lambda c: c["date"], reverse=True)
    return out


def _installed_version_arch(pkg_name):
    out, code = run_command(f"pacman -Q {shlex.quote(pkg_name)} 2>/dev/null", timeout=5)
    if code == 0 and out.strip():
        parts = out.strip().split()
        if len(parts) >= 2:
            return parts[1]
    return None


def is_foreign_package(pkg_name):
    """True, wenn das installierte Paket nicht aus einem Sync-Repository
    stammt (auf Arch: AUR bzw. selbst gebaut, `pacman -Qm`). Auf anderen
    Distros immer False."""
    if not distro.is_arch():
        return False
    out, code = run_command("pacman -Qqm 2>/dev/null", timeout=10)
    return code == 0 and pkg_name in out.split()


def get_downgrade_candidates(pkg_name):
    """Andere Versionen von pkg_name, die statt der aktuellen installiert
    werden können, als [{"version","source","kind"}, ...] — "kind" ist
    "file" (echte Datei im Cache), "url" (Arch Linux Archive, pacman lädt
    sie selbst) oder "repo" (der Paketmanager löst genau diesen Build selbst
    auf). Die installierte Version ist mit "installed": True markiert.
    Reihenfolge: neueste zuerst. Auf Arch wird zusätzlich zum lokalen
    Paketcache das Arch Linux Archive abgefragt (Netzwerkzugriff; nicht im
    GTK-Hauptthread aufrufen). Andere Distros: pkgmanager.get_downgrade_candidates()."""
    if not distro.is_arch():
        return pkgmanager.get_downgrade_candidates(pkg_name)
    cached = {v: fp for v, fp in get_cached_versions(pkg_name)}
    for v, fp in get_aur_built_versions(pkg_name):
        cached.setdefault(v, fp)
    installed = _installed_version_arch(pkg_name)
    result, seen = [], set()
    for c in get_arch_archive_versions(pkg_name):
        v = c["version"]
        if v in cached:                    # lokale Datei bevorzugen (kein Download)
            c = {"version": v, "source": cached[v], "kind": "file"}
        c["installed"] = (v == installed)
        result.append(c)
        seen.add(v)
    # Nur im Cache vorhandene Versionen (z.B. AUR-Pakete oder offline)
    for v, fp in cached.items():
        if v not in seen:
            result.append({"version": v, "source": fp, "kind": "file",
                           "installed": (v == installed)})
    # Die installierte Version immer anzeigen — auch wenn sie weder im
    # Archiv noch im Cache liegt (typisch für AUR-Pakete).
    if installed and installed not in seen and installed not in cached:
        result.insert(0, {"version": installed, "source": "", "kind": "installed",
                          "installed": True})
    return result


def build_downgrade_cmd(pkg_name, candidate):
    """Ready-to-run install command for one entry from
    get_downgrade_candidates()."""
    if not distro.is_arch():
        return pkgmanager.downgrade_cmd(pkg_name, candidate)
    return f"pkexec /usr/bin/pacman -U --noconfirm {shlex.quote(candidate['source'])}"


def get_aur_built_versions(pkg_name):
    """[(version, filepath), …] bereits gebauter Pakete aus den Build-Caches
    der AUR-Helfer (yay, paru, pikaur, pachuli) — AUR-Pakete landen nicht
    im pacman-Cache. Neueste zuerst (nach Änderungszeit)."""
    home = Path.home()
    roots = [home / ".cache" / "yay" / pkg_name,
             home / ".cache" / "paru" / "clone" / pkg_name,
             home / ".cache" / "pikaur" / "pkg",
             home / ".cache" / "pachuli" / "builds"]
    pkgdest = os.environ.get("PKGDEST")
    if pkgdest:
        roots.append(Path(pkgdest))
    results = {}
    for root in roots:
        try:
            if not root.is_dir():
                continue
            for f in root.rglob(f"{pkg_name}-*.pkg.tar.*"):
                if f.name.endswith(".sig"):
                    continue
                stem = re.sub(r"\.pkg\.tar\.\w+$", "", f.name)
                parts = stem.rsplit("-", 3)
                if len(parts) == 4 and parts[0] == pkg_name:
                    results.setdefault(f"{parts[1]}-{parts[2]}", str(f))
        except Exception:
            continue
    return sorted(results.items(),
                  key=lambda vf: os.path.getmtime(vf[1]) if os.path.exists(vf[1]) else 0,
                  reverse=True)


def get_cached_versions(pkg_name):
    """Return [(version, filepath), …] of cached .pkg files for pkg_name, newest first."""
    cache_dir = Path("/var/cache/pacman/pkg")
    results = []
    try:
        for f in cache_dir.glob(f"{pkg_name}-*.pkg.tar.*"):
            if f.name.endswith(".sig"):
                continue
            base = re.sub(r"\.pkg\.tar\.\w+$", "", f.name)
            parts = base.rsplit("-", 3)   # name-ver-rel-arch (name may contain '-')
            if len(parts) == 4 and parts[0] == pkg_name:
                results.append((f"{parts[1]}-{parts[2]}", str(f)))
    except Exception:
        pass
    results.sort(
        key=lambda vf: os.path.getmtime(vf[1]) if os.path.exists(vf[1]) else 0,
        reverse=True)
    return results


# ─── Search ───────────────────────────────────────────────────────────────────

def search_packages_cmd(query):
    def parse_pacman_ss(out):
        """pacman -Ss: a 'repo/name version ...' line, then the description."""
        found = []
        text_lines = out.splitlines()
        total = len(text_lines)
        idx = 0
        while idx < total:
            header = text_lines[idx].strip()
            tokens = header.split() if "/" in header else []
            if not tokens:
                idx += 1
                continue
            qualified = tokens[0]
            ver = tokens[1] if len(tokens) > 1 else "unknown"
            if "/" in qualified:
                repo_name, pkg = qualified.split("/", 1)
            else:
                repo_name, pkg = "", qualified
            blurb = text_lines[idx + 1].strip() if idx + 1 < total else ""
            found.append({"name": pkg, "version": ver, "repo": repo_name,
                          "description": blurb, "status": "available",
                          "foreign": repo_name.lower() == "aur"})
            idx += 2
        return found

    def parse_pachuli_ss(out):
        """Parse pachuli's numbered -Ss output (always ANSI-coloured): per
        result a 'N repo/name version [...]' line, optionally followed by an
        indented description. Returns the same shape as parse_pacman_ss."""
        found = []
        text_lines = _strip_ansi(out).splitlines()
        row_re = re.compile(r"^\d+\s+(\S+)/(\S+)\s+(\S+)")
        idx = 0
        while idx < len(text_lines):
            hit = row_re.match(text_lines[idx].strip())
            if not hit:
                idx += 1
                continue
            repo_name, pkg, ver = hit.groups()
            nxt = text_lines[idx + 1] if idx + 1 < len(text_lines) else None
            has_desc = nxt is not None and nxt.startswith(" ")
            blurb = nxt.strip() if has_desc else ""
            found.append({"name": pkg, "version": ver, "repo": repo_name,
                          "description": blurb, "status": "available",
                          "foreign": repo_name.lower() == "aur"})
            idx += 2 if has_desc else 1
        return found

    packages = []
    seen = set()

    def collect(items):
        """Append results whose name has not been seen yet."""
        for item in items:
            if item["name"] in seen:
                continue
            seen.add(item["name"])
            packages.append(item)

    if not distro.is_arch():
        search_cmd = pkgmanager.search_cmd(query)
        if search_cmd:
            out, code = run_command(search_cmd, timeout=30)
            if out and code == 0:
                collect(pkgmanager.parse_search(out))
        collect(search_flatpak(query))
        collect(search_snap(query))
        return packages

    quoted = shlex.quote(query)
    out, code = run_command(f"pacman -Ss {quoted} 2>/dev/null")
    if out and code == 0:
        collect(parse_pacman_ss(out))

    helper = _find_aur_helper()
    if helper:
        if helper == "pachuli":
            # -a skips pachuli's own repo search, -q drops status lines
            aur_out, aur_code = run_command(f"pachuli -Ss {quoted} -a -q -g 2>/dev/null", timeout=30)
            aur_found = parse_pachuli_ss(aur_out) if (aur_out and aur_code == 0) else []
        else:
            aur_out, aur_code = run_command(f"{helper} -Ss --aur {quoted} 2>/dev/null", timeout=30)
            aur_found = parse_pacman_ss(aur_out) if (aur_out and aur_code == 0) else []
        official = ("core", "extra", "multilib", "community")
        for item in aur_found:
            if item["name"] in seen:
                continue
            item["foreign"] = True
            if item["repo"].lower() not in official:
                item["repo"] = "aur"
        collect(aur_found)

    collect(search_flatpak(query))
    collect(search_snap(query))

    return packages


# ─── Self-installation & tray autostart ────────────────────────────────────
# Mirrors install.sh's own paths exactly, so the in-app installer and the
# standalone script are just two front-ends to the same result — running
# one after the other is always a safe no-op.

INSTALL_DESKTOP_DIR  = "/usr/share/applications"
INSTALL_ICON_ID      = "io.github.wergosam.pachul"
INSTALL_DESKTOP_FILE = f"{INSTALL_DESKTOP_DIR}/{INSTALL_ICON_ID}.desktop"

# Per-user autostart entry for the tray icon. Deliberately NOT the
# system-wide /etc/xdg/autostart install.sh used to write — a file here
# needs no root to create, remove, or toggle, and per the XDG autostart
# spec a user's own ~/.config/autostart always takes precedence anyway.
AUTOSTART_DIR  = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / f"{INSTALL_ICON_ID}-tray.desktop"


def is_pachul_installed():
    """Whether Pachul is installed system-wide — via install.sh
    (launcher in /usr/local/bin) or the AUR package (launcher in
    /usr/bin). Checked through PATH rather than a single hardcoded
    directory, since the two installation methods disagree on where the
    launcher lives; a hardcoded /usr/local/bin check would silently
    treat a perfectly good AUR install as "not installed"."""
    return shutil.which("pachul") is not None and os.path.isfile(INSTALL_DESKTOP_FILE)


# Wo die installierten Python-Module landen, je nach Installationsart —
# install.sh's DATA_DIR bzw. der PKGBUILD's $pkgdir/usr/share/$pkgname.
INSTALLED_PACHUL_DIRS = ("/usr/local/share/pachul", "/usr/share/pachul")


def _read_version_const(path, const_name):
    """Liest eine `NAME = "x.y.z"`-Konstante direkt aus einer Python-Datei,
    ohne sie auszuführen — das funktioniert auch dann noch zuverlässig,
    wenn die betreffende Datei selbst kaputt/veraltet ist (genau der
    Fall, den ein Versions-Check abfangen soll), und ohne für eine
    GUI-App wie Pachul extra einen Prozess zu starten, nur um an die
    Versionsnummer zu kommen."""
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(rf'^{re.escape(const_name)}\s*=\s*["\']([\d.]+)', content, re.MULTILINE)
    return m.group(1) if m else None


def _parse_version(v):
    """Parst einen Punkt-getrennten Versions-String wie '2.1.0' in ein
    Tupel aus Ints für den Vergleich. Nicht-numerische Anteile (z.B. ein
    '-dev'-Suffix) werden ignoriert; ein leerer/ungültiger String ergibt
    (0,), sodass er gegenüber jeder echten Version als "älter" gilt."""
    if not v:
        return (0,)
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) or (0,)


def _version_newer(a, b):
    """True, wenn Version a > Version b (beide als 'x.y.z'-Strings, z.B.
    aus _read_version_const())."""
    return _parse_version(a) > _parse_version(b or "")


def installed_pachul_version():
    """Version der aktuell systemweit installierten Pachul-Kopie, oder
    None, falls keine gefunden wird. Liest APP_VERSION direkt aus der
    installierten backend.py statt die App zu starten."""
    for d in INSTALLED_PACHUL_DIRS:
        v = _read_version_const(os.path.join(d, "backend.py"), "APP_VERSION")
        if v:
            return v
    return None


def pachul_update_available(app_dir):
    """True, wenn Pachul systemweit installiert ist, die gerade laufende
    Kopie (app_dir — z.B. ein frisch gezogener/entpackter Checkout) aber
    eine neuere APP_VERSION mitbringt als die installierte. False bei
    einer ganz frischen (noch nie installierten) Kopie — dafür ist
    is_pachul_installed()/_maybe_offer_install()'s bestehender
    "Install"-Zweig zuständig — und auch dann, wenn die installierte
    Version aus irgendeinem Grund nicht gelesen werden konnte (im
    Zweifel lieber nichts anfassen)."""
    if not is_pachul_installed():
        return False
    installed_v = installed_pachul_version()
    if installed_v is None:
        return False
    return _version_newer(APP_VERSION, installed_v)


def find_install_script(app_dir):
    """install.sh sits next to app.py only in a source checkout — an
    already-installed copy under /usr/local/share/pachul never ships it,
    so this naturally returns None once there's nothing left to install."""
    path = os.path.join(app_dir, "install.sh")
    return path if os.path.isfile(path) else None


def build_install_command(app_dir):
    """pkexec command that runs install.sh non-interactively, through the
    exact same terminal/pkexec flow every other privileged action in the
    app already uses — there's only one installation code path to maintain."""
    script = find_install_script(app_dir)
    if not script:
        return None
    return f"pkexec /usr/bin/bash {shlex.quote(script)}"


def is_autostart_enabled():
    return AUTOSTART_FILE.is_file()


def _resolve_icon_path(app_dir=None):
    """Absolute path to the tray's black-and-white icon — never a bare
    icon-theme name. Both install.sh and the AUR PKGBUILD install the
    icon to the same system-wide hicolor path, so that's checked first
    (works regardless of a dev checkout still being around); a source
    checkout next to app_dir is the fallback for a not-yet-installed run.
    Used for the autostart .desktop's Icon= key: AppIndicator/Ayatana
    auto-populates the tray's SNI "DesktopEntry" property from this file,
    and Plasma's system tray resolves ITS OWN icon from that file's
    Icon= key by name — via Plasma's own icon cache, independent of
    whatever tray.py sets via set_icon_full(). A bare name there raced
    against Plasma's cache and fell back to the generic
    "applications-other" icon a few seconds in; an absolute path bypasses
    that lookup entirely, the same fix already applied to tray.py's own
    icon and to backend.py's own _pachul_icon_path() for notify-send.
    """
    bw_name = "io_github_wergosam_pachul_bw"
    system_path = f"/usr/share/icons/hicolor/scalable/apps/{bw_name}.svg"
    if os.path.isfile(system_path):
        return system_path
    if app_dir:
        checkout_path = os.path.join(app_dir, f"{bw_name}.svg")
        if os.path.isfile(checkout_path):
            return checkout_path
    return bw_name  # last-resort fallback to the old by-name behaviour


def set_autostart_enabled(enabled, app_dir=None):
    """Create or remove the per-user tray-icon autostart entry. Never
    touches anything outside the user's own config directory, so this
    never needs a password."""
    try:
        if enabled:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            if is_pachul_installed():
                exec_cmd = "pachul-tray"
            elif app_dir:
                exec_cmd = (f"{shlex.quote(sys.executable or 'python3')} "
                            f"{shlex.quote(os.path.join(app_dir, 'tray.py'))}")
            else:
                exec_cmd = "pachul-tray"
            icon_path = _resolve_icon_path(app_dir)
            AUTOSTART_FILE.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Pachul Update Tray\n"
                "Comment=Persistent tray icon showing pending Pacman/AUR updates\n"
                f"Exec={exec_cmd}\n"
                f"Icon={icon_path}\n"
                "Terminal=false\n"
                "NoDisplay=true\n"
                "X-GNOME-Autostart-enabled=true\n")
        else:
            AUTOSTART_FILE.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def is_tray_running():
    """Whether a pachul-tray process is currently running for this user."""
    _, code = run_command("pgrep -f 'tray[.]py' >/dev/null 2>&1")
    return code == 0


def start_tray(app_dir=None):
    """Launch the tray icon right now, detached from this process — used
    so enabling autostart in Preferences shows the icon immediately
    instead of only at the next login. No-op if already running.

    Prefers a tray.py right next to app_dir (i.e. whatever code is
    actually running right now) over the installed `pachul-tray` command:
    otherwise, on a machine where install.sh was run at some point in the
    past, this would always launch that old installed copy even while
    actively testing a newer source checkout — silently running stale
    code with no indication that's what happened.
    """
    if is_tray_running():
        return True
    if app_dir and os.path.isfile(os.path.join(app_dir, "tray.py")):
        exec_args = [sys.executable or "python3", os.path.join(app_dir, "tray.py")]
    elif is_pachul_installed():
        exec_args = ["pachul-tray"]
    else:
        exec_args = ["pachul-tray"]
    try:
        subprocess.Popen(
            exec_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:

        return False


def stop_tray():
    """Quit the running tray icon right now — the counterpart to
    start_tray(), used when autostart is turned off in Preferences."""
    run_command("pkill -f 'tray[.]py' 2>/dev/null")
    return True


def notify_tray_recheck():
    """Ask any running pachul-tray process to immediately re-check for
    updates via SIGUSR1, instead of leaving its tray label/tooltip showing
    a stale count until its own periodic timer next fires. Called right
    after a successful upgrade in the main window — a no-op (silently)
    if no tray process is currently running."""
    run_command("pkill -SIGUSR1 -f 'tray[.]py' 2>/dev/null")


# ─── Background update-check (systemd --user timer) ───────────────────────────

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
TIMER_UNIT       = "pachul-update-check"
_TIMER_INTERVALS = {"hourly": "1h", "6h": "6h", "daily": "1d"}


def _notifier_path():
    return str(Path(__file__).resolve().parent / "notifier.py")


def is_update_timer_enabled():
    out, code = run_command(f"systemctl --user is-enabled {TIMER_UNIT}.timer 2>/dev/null")
    return code == 0 and out.strip() == "enabled"


def enable_update_timer(interval="daily"):
    """Write & enable the systemd --user timer that runs the notifier periodically."""
    on_active = _TIMER_INTERVALS.get(interval, "1d")
    python = sys.executable or "python3"
    notifier = _notifier_path()
    service = (
        "[Unit]\n"
        "Description=Pachul background update check\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={python} {notifier}\n")
    timer = (
        "[Unit]\n"
        "Description=Pachul periodic update check\n\n"
        "[Timer]\n"
        "OnBootSec=5min\n"
        f"OnUnitActiveSec={on_active}\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n")
    try:
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        (SYSTEMD_USER_DIR / f"{TIMER_UNIT}.service").write_text(service)
        (SYSTEMD_USER_DIR / f"{TIMER_UNIT}.timer").write_text(timer)
    except Exception:
        return False
    run_command("systemctl --user daemon-reload")
    _, code = run_command(f"systemctl --user enable --now {TIMER_UNIT}.timer")
    return code == 0


def disable_update_timer():
    run_command(f"systemctl --user disable --now {TIMER_UNIT}.timer")
    return True


def _pachul_icon_path():
    """Absolute path to Pachul's tray/notification icon file (the
    black-and-white variant), checked directly rather than resolved by
    name through an icon theme — works both in a source checkout (icon
    sits right next to this file) and once installed system-wide
    (install.sh's ICON_DIR). Falls back to the bare name only if the file
    genuinely can't be found anywhere. Only used by
    send_update_notification(), which is only ever called from the tray
    (tray.py) — the main window's own notification code
    (window.py's _notify_updates()) points at the main app icon
    directly."""
    name = "io_github_wergosam_pachul_bw"
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{name}.svg")
    if os.path.isfile(local):
        return local
    system_path = f"/usr/share/icons/hicolor/scalable/apps/{name}.svg"
    if os.path.isfile(system_path):
        return system_path
    return name  # last-resort fallback to the old by-name behaviour


def send_update_notification(n, extra=0):
    """Send a desktop notification about n available package updates,
    plus (optionally) how many enabled "More Update Sources" tools are
    ready to run alongside the next system upgrade.

    Returns the notification's id (via notify-send's -p/--print-id) so a
    caller that keeps running (the tray icon) can later withdraw it with
    withdraw_notification() once the pending count drops back to 0 —
    otherwise a stale "N updates available" entry can keep sitting in
    the desktop's notification history/center long after the updates
    were actually installed. Returns None if the id couldn't be
    determined (e.g. notify-send is missing, or too old to support -p),
    in which case there's simply nothing to withdraw later."""
    if run_command("which notify-send 2>/dev/null")[1] != 0:
        return None
    from i18n import tr   # local import: avoids a circular import with i18n.py
    title = tr("Updates Available")
    parts = []
    if n > 0:
        line = tr("{n} package update can be installed.") if n == 1 \
            else tr("{n} package updates can be installed.")
        parts.append(line.format(n=n))
    if extra > 0:
        line = tr("1 additional update source is ready to run.") if extra == 1 \
            else tr("{n} additional update sources are ready to run.")
        parts.append(line.format(n=extra))
    body = " ".join(parts)
    icon = _pachul_icon_path()
    out, code = run_command(
        f"notify-send --app-name=Pachul --icon={shlex.quote(icon)} -p "
        f"{shlex.quote('Pachul: ' + title)} {shlex.quote(body)}")
    if code == 0 and out.strip().isdigit():
        return int(out.strip())
    return None


def withdraw_notification(notif_id):
    """Close a previously-sent desktop notification by the id
    send_update_notification() returned, via the freedesktop.org
    Notifications D-Bus interface — notify-send itself has no way to
    withdraw a notification after the fact, only the D-Bus interface
    underneath it does. A no-op if notif_id is None (nothing was ever
    sent, or the id couldn't be determined) or if the notification was
    already dismissed/expired on its own; CloseNotification on an
    already-gone id is harmless."""
    if notif_id is None:
        return
    run_command(
        "gdbus call --session --dest org.freedesktop.Notifications "
        "--object-path /org/freedesktop/Notifications "
        "--method org.freedesktop.Notifications.CloseNotification "
        f"{int(notif_id)}")


def startup_health_checks():
    """A handful of fast, strictly read-only, no-root checks for common
    fixable problems, run once in the background shortly after the main
    window opens (see pachulWindow._bg_startup_health_check). Every check
    here uses only commands the repair/diagnostic dialogs already treat
    as safe (systemctl --failed, pacman -Dk, dpkg -l, dnf check, the
    Broken Symlinks scan, the Certificate Checker's local scan) — this
    function does not add any new kind of system probing, it just runs a
    curated subset of the existing ones automatically and reports what
    it found. Nothing here ever needs a password: findings only point at
    which already-existing dialog can fix the problem, they don't fix it
    themselves. Returns a list of dicts, each
    {"title": str, "detail": str, "action": <attribute name of a
    pachulWindow._on_show_* method>}, or an empty list if nothing was
    found (including if a check itself failed or timed out — a check
    that can't complete is skipped silently rather than reported as a
    problem). Includes a best-effort heuristic check for openSUSE
    ('zypper verify --dry-run --no-refresh'): unlike pacman -Dk/dnf
    check/dpkg -l, zypper's dry-run output isn't a clean "found a
    problem" signal on every version/locale, so this only looks for the
    literal "Nothing to do" (no issue) vs. any other non-empty output
    (possible issue) and labels the finding as a heuristic — it can
    occasionally be wrong in either direction, which the other, more
    reliable checks in this function are not."""
    from i18n import tr   # local import: avoids a circular import with i18n.py
    findings = []

    def _add(title, detail, action):
        findings.append({"title": title, "detail": detail, "action": action})

    # ── Failed systemd services (all distros) ──
    out, _ = run_command("systemctl --failed --no-legend --plain --no-pager 2>/dev/null", timeout=6)
    failed = [l for l in out.splitlines() if l.strip()]
    if failed:
        names = [l.split()[0] for l in failed if l.split()]
        _add(
            tr("{n} systemd service(s) failed").format(n=len(failed)),
            ", ".join(names[:5]) + ("…" if len(names) > 5 else ""),
            "_on_show_services_security",
        )

    # ── SSH root login enabled (all distros) ──
    out, _ = run_command(
        '[ -r /etc/ssh/sshd_config ] && '
        'grep -qE "^PermitRootLogin\\s+yes" /etc/ssh/sshd_config && echo yes',
        timeout=4)
    if out.strip() == "yes":
        _add(
            tr("SSH allows direct root login"),
            tr("PermitRootLogin yes is set in /etc/ssh/sshd_config."),
            "_on_show_services_security",
        )

    # ── No active firewall (all distros) ──
    _, ufw_active_code = run_command("systemctl is-active --quiet ufw 2>/dev/null", timeout=4)
    _, firewalld_active_code = run_command("systemctl is-active --quiet firewalld 2>/dev/null", timeout=4)
    if ufw_active_code != 0 and firewalld_active_code != 0:
        _add(
            tr("No active firewall detected"),
            tr("Neither UFW nor firewalld is currently active."),
            "_on_show_services_security",
        )

    # ── Package database / consistency (distro-specific) ──
    fam = pkgmanager.get_family()
    if fam == "arch":
        if os.path.exists("/var/lib/pacman/db.lck"):
            _add(
                tr("Pacman database is locked (stale db.lck)"),
                tr("A leftover db.lck is blocking every pacman operation."),
                "_on_show_pacman_repair",
            )
        # pacman -Dk prints "No database errors have been found!" on
        # success — NOT empty output — so a plain "is there any output"
        # check always misfires. Only non-empty output that doesn't
        # match that success message is an actual finding.
        out, _ = run_command("pacman -Dk 2>/dev/null", timeout=8)
        stripped = out.strip()
        if stripped and "no database errors" not in stripped.lower():
            _add(
                tr("Pacman database consistency issues found"),
                stripped.splitlines()[0],
                "_on_show_pacman_repair",
            )
    elif fam == "debian":
        out, _ = run_command("dpkg -l 2>/dev/null | grep -E '^..r'", timeout=8)
        broken = [l for l in out.splitlines() if l.strip()]
        if broken:
            _add(
                tr("{n} broken/incomplete package(s) (dpkg)").format(n=len(broken)),
                broken[0].strip(),
                "_on_show_apt_repair",
            )
    elif fam == "fedora":
        out, code = run_command("dnf check 2>/dev/null", timeout=15)
        if code != 0 and out.strip():
            _add(
                tr("dnf check reports package problems"),
                out.strip().splitlines()[0],
                "_on_show_dnf_repair",
            )
    elif fam == "suse":
        # Heuristic, unlike the three checks above: --no-refresh keeps
        # this from hitting the network/repos (faster, safer for an
        # automatic background check, but can miss fixes only a fresh
        # repo refresh would reveal), and "Nothing to do" is the only
        # normal-case output this reliably recognizes across zypper
        # versions/locales — anything else non-empty is reported as a
        # *possible* issue, not a confirmed one. Locked/permission
        # errors (e.g. another zypper already running) are treated as a
        # failed check and skipped silently, same as every other check
        # here.
        out, code = run_command(
            "zypper --non-interactive --no-refresh verify --dry-run 2>&1", timeout=15)
        low = out.lower()
        _skip_markers = ("system management is locked", "unable to lock",
                          "permission denied", "no repositories")
        if out.strip() and "nothing to do" not in low \
                and not any(m in low for m in _skip_markers):
            _add(
                tr("zypper verify suggests possible package problems (heuristic — please double-check)"),
                out.strip().splitlines()[0],
                "_on_show_zypper_repair",
            )

    # ── Expired local certificates (all distros) ──
    # `openssl x509 -checkend` always prints its own verdict text
    # ("Certificate will (not) expire") to stdout regardless of -noout
    # or the exit code, so that stdout has to be silenced too (not just
    # stderr) or every single certificate checked — not just the
    # expired ones — ends up as a line in $CERT's output.
    out, _ = run_command(
        'while IFS= read -r -d "" CERT; do '
        '  openssl x509 -checkend 0 -noout -in "$CERT" >/dev/null 2>&1 || echo "$CERT"; '
        'done < <(find /etc/ssl/certs/ -name "*.pem" -print0 2>/dev/null)',
        timeout=10)
    expired = [l for l in out.splitlines() if l.strip()]
    if expired:
        _add(
            tr("{n} expired local certificate(s)").format(n=len(expired)),
            expired[0].strip(),
            "_on_show_cert_checker",
        )

    # ── Broken symlinks under /usr/share/licenses only (all distros).
    # The Broken Symlinks dialog only ever auto-deletes this one
    # category (its "Scan & Remove Safe Ones" button) — everything else
    # it finds goes in a "REVIEW — not auto-deleted" bucket that needs
    # manually identifying and reinstalling the owning package, so it
    # can never actually disappear just by opening that tool. Reporting
    # those here would point at a "fix" that doesn't exist, which is
    # exactly what caused it to keep reappearing after every re-check —
    # so only the truly one-click-fixable category is checked.
    out, _ = run_command(
        'find /usr/share/licenses -xtype l -print 2>/dev/null', timeout=8)
    orphaned = [l for l in out.splitlines() if l.strip()]
    if orphaned:
        _add(
            tr("{n} orphaned license symlink(s) (safe to remove)").format(n=len(orphaned)),
            orphaned[0].strip(),
            "_on_show_broken_symlinks",
        )

    return findings


def run_update_notification_check():
    """Entry point for the systemd timer: check for updates and notify if
    any — package updates, or enabled "More Update Sources" tools that
    are still actually detected right now (re-checked fresh each time, so
    an uninstalled tool never shows up here even if it was once enabled)."""
    if not get_setting("notify_updates"):
        return 0
    n = len(check_updates())
    extra = len(get_enabled_auto_update_commands())
    if n > 0 or extra > 0:
        send_update_notification(n, extra)
    return n
