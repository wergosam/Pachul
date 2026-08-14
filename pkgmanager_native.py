"""
Pachul — pkgmanager_native.py
Optional native-binding fast paths for pkgmanager.py: python3-apt on
Debian/Ubuntu, python3-dnf on Fedora. These are pure accelerators — every
function here is consulted only if the binding actually imports, and every
call site in pkgmanager.py keeps its existing CLI-based implementation as
the fallback if the binding is missing OR any call here raises. Native
code failing here can only ever cost the CLI-level speed back, never break
anything that already worked.

Confidence levels differ a lot between the two halves of this file:

  APT — built AND load-tested against a live Ubuntu 24.04 install (this
  sandbox has python3-apt installed). Benchmarked against the CLI path:
  building the full ~97,000-package "available packages" list took ~19s
  via `apt-cache dumpavail` + text parsing, vs ~3s via apt.Cache() here —
  roughly 6x faster. Single-package info (dpkg -s + apt-cache show +
  apt-mark showauto, up to 3 subprocesses) collapses to one Cache()
  lookup. The one deliberate exception: Version.origins is NOT touched
  during the bulk build — it benchmarked at ~18s for the full cache by
  itself (vs ~1s for every other field combined), because resolving each
  version's origin walks package-file references one at a time. Fine as
  a per-package cost (single_lookup path below), ruinous multiplied
  across ~97k packages, so the bulk path leaves "repo" blank, same as
  the CLI dumpavail fallback already does.

  DNF — two separate native paths, since Fedora's package-manager Python
  bindings forked along with the dnf4→dnf5 transition:

  - dnf5 (`import libdnf5`) is tried FIRST, since Fedora 41+ ships dnf5 as
    the default `dnf` command, and its C++ library (libdnf5) is what the
    Python bindings actually talk to there — the classic `dnf` module
    isn't installed on a dnf5-only system at all.
  - dnf4 (`import dnf`, the classic yum-era module) is tried second, for
    older Fedora/RHEL/CentOS systems still on dnf4.

  NEITHER half was verified against a real system — no Fedora machine was
  available to test against here, and libdnf5's Python bindings in
  particular are SWIG-generated from a still-evolving C++ API, so exact
  method names (base setup/repo-loading calls especially) are written
  from documented examples rather than confirmed working code. Every
  dnf5_*/dnf_* entry point is wrapped so ANY exception makes the caller
  fall back — first to the other binding, then to the CLI path in
  pkgmanager.py, which already works against dnf5 systems today (dnf5's
  CLI stays close to dnf4's for the commands this app uses). So a wrong
  assumption here costs at worst "no speedup", never a crash — but this
  really does need checking on real dnf4 AND dnf5 Fedora installs before
  anyone should trust the native path is what's actually running.
"""

import os
import threading
from pathlib import Path

try:
    import apt
    _APT_OK = True
except Exception:
    _APT_OK = False

try:
    import libdnf5
    _DNF5_OK = True
except Exception:
    _DNF5_OK = False

try:
    import dnf
    _DNF_OK = True
except Exception:
    _DNF_OK = False


def apt_available():
    return _APT_OK


def dnf5_available():
    return _DNF5_OK


def dnf_available():
    """True if EITHER Fedora binding is usable — dnf5 is preferred and
    tried first wherever both are present, but callers that just need a
    yes/no ("is there a native Fedora path at all?") can use this."""
    return _DNF5_OK or _DNF_OK


def _fmt_size(num_bytes):
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "None"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PiB"


# ─── APT (Debian/Ubuntu) ───────────────────────────────────────────────────────
# A single apt.Cache() is expensive to open (~2-4s) but cheap to query
# afterwards, so it's kept as a lazily-created singleton and reused across
# calls — reopening it per call would make single-package lookups (e.g.
# clicking a package in the list) noticeably SLOWER than the plain `dpkg -s`
# CLI path this is meant to speed up, not just the bulk operations.
# invalidate_apt_cache() is called from pkgmanager.py right alongside the
# existing pacman-cache invalidation, after anything that could have
# changed installed/available packages.

_apt_cache = None
_apt_lock = threading.Lock()


def _get_apt_cache():
    global _apt_cache
    if _apt_cache is None:
        with _apt_lock:
            if _apt_cache is None:
                _apt_cache = apt.Cache()
    return _apt_cache


def invalidate_apt_cache():
    global _apt_cache
    with _apt_lock:
        _apt_cache = None


def apt_build_available_packages():
    """{name: {"repo","version","description"}} — native equivalent of
    pkgmanager._build_available_debian()."""
    cache = _get_apt_cache()
    pkgs = {}
    for pkg in cache:
        v = pkg.installed or pkg.candidate
        if v is None:
            continue
        pkgs[pkg.name] = {
            "repo": "", "version": v.version,
            "description": (v.raw_description or v.summary or ""),
        }
    return pkgs


def apt_installed_repos():
    """{pkgname: repo_label} for every currently *installed* package,
    resolved via Version.origins (the "Origin:" field apt itself uses —
    e.g. "Ubuntu", "LP-PPA-something" for a PPA, "Google LLC" for a
    third-party apt source). This is the per-package cost the module
    docstring calls out as fine to pay individually (~18s/97k pkgs
    scales down to a fraction of a second for a typical few-hundred-to-
    low-thousands installed set) — unlike apt_build_available_packages(),
    which deliberately skips origins for the full ~97k-package catalog.
    Used only to populate the sidebar's repo/source categories for
    installed packages; not-yet-installed packages keep repo="" as
    before (resolving origins for all of them would reintroduce the
    full ~18s cost)."""
    cache = _get_apt_cache()
    result = {}
    for pkg in cache:
        if not pkg.is_installed:
            continue
        v = pkg.installed
        if v is None:
            continue
        try:
            origins = v.origins
        except Exception:
            continue
        if not origins:
            continue
        label = (origins[0].origin or origins[0].label or "").strip()
        if label:
            result[pkg.name] = label
    return result


def apt_installed_snapshot():
    """{name: {"name","version","repo","status","description","foreign"}}
    for every installed package — native equivalent of
    pkgmanager.parse_installed(), sourced from one Cache() pass instead of
    parsing `dpkg-query` output."""
    cache = _get_apt_cache()
    result = {}
    for pkg in cache:
        if not pkg.is_installed:
            continue
        v = pkg.installed
        result[pkg.name] = {
            "name": pkg.name, "version": v.version, "repo": "local",
            "status": "installed",
            "description": (v.raw_description or v.summary or ""),
            "foreign": False,
        }
    return result


def apt_installed_fingerprint():
    """(hash, raw_text) — native equivalent of running
    pkgmanager._installed_fingerprint_cmd() and hashing its stdout, built
    from the same Cache() pass instead of a dpkg-query subprocess."""
    cache = _get_apt_cache()
    lines = []
    for pkg in cache:
        if pkg.is_installed:
            lines.append(f"{pkg.name} {pkg.installed.version}")
    raw = "\n".join(sorted(lines))
    import hashlib
    return hashlib.md5(raw.encode()).hexdigest(), raw


def apt_is_installed(pkg_name):
    cache = _get_apt_cache()
    return pkg_name in cache and cache[pkg_name].is_installed


def apt_orphans():
    """Packages installed as a dependency that nothing needs any more —
    native equivalent of `apt-get --simulate autoremove` output-parsing,
    via apt's own is_auto_removable flag directly."""
    cache = _get_apt_cache()
    orphans = []
    for pkg in cache:
        if pkg.is_installed and getattr(pkg, "is_auto_removable", False):
            orphans.append({"name": pkg.name, "version": pkg.installed.version})
    return orphans


def apt_explicit_packages():
    """Native equivalent of `apt-mark showmanual`, via is_auto_installed."""
    cache = _get_apt_cache()
    return [pkg.name for pkg in cache if pkg.is_installed and not pkg.is_auto_installed]


def apt_check_updates():
    """Native equivalent of parsing `apt list --upgradable`, via apt's own
    is_upgradable flag — also sidesteps that command's dependence on
    whatever locale/column-width apt happens to print in."""
    cache = _get_apt_cache()
    updates = []
    for pkg in cache:
        if pkg.is_installed and pkg.is_upgradable and pkg.candidate:
            updates.append({
                "name": pkg.name, "old": pkg.installed.version,
                "new": pkg.candidate.version, "aur": False,
            })
    return updates


def _apt_dep_names(version, dep_type):
    try:
        names = set()
        for dep in version.get_dependencies(dep_type):
            for bd in dep.or_dependencies:
                names.add(bd.name)
        return names
    except Exception:
        return set()


def apt_package_info_text(pkg_name):
    """Same pacman-style 'Key : Value' text as
    pkgmanager.get_package_info_text()'s Debian branch, sourced from one
    Cache() lookup instead of up to 3 subprocesses (dpkg -s / apt-cache
    show / apt-mark showauto)."""
    cache = _get_apt_cache()
    if pkg_name not in cache:
        return None
    pkg = cache[pkg_name]
    v = pkg.installed or pkg.candidate
    if v is None:
        return None

    installed = pkg.is_installed
    depends = ", ".join(sorted(_apt_dep_names(v, "Depends"))) or "None"
    optional = ", ".join(sorted(_apt_dep_names(v, "Recommends") | _apt_dep_names(v, "Suggests"))) or "None"
    conflicts = ", ".join(sorted(_apt_dep_names(v, "Conflicts"))) or "None"
    provides = ", ".join(v.provides) or "None"

    reason, install_date = "None", "None"
    if installed:
        reason = ("Installed as a dependency for another package"
                  if pkg.is_auto_installed else "Explicitly installed")
        try:
            import datetime
            mtime = Path(f"/var/lib/dpkg/info/{pkg_name}.list").stat().st_mtime
            install_date = datetime.datetime.fromtimestamp(mtime).strftime("%a %d %b %Y %H:%M:%S")
        except Exception:
            pass

    # .origins is cheap for one package (unlike iterating the whole cache
    # with it — see the module docstring), so it's fine to use here.
    try:
        origins = v.origins
        section = v.section or "None"
    except Exception:
        origins, section = [], "None"

    # installed_size is already in bytes (unlike dpkg -s's Installed-Size,
    # which is in KiB) — confirmed by comparing both on the same package
    # during testing, so no unit conversion here.
    size_h = _fmt_size(v.installed_size) if (installed and v.installed_size) else "None"
    maintainer = v.record.get("Maintainer", "None") if hasattr(v, "record") else "None"

    return (
        f"Name           : {pkg.name}\n"
        f"Version        : {v.version}\n"
        f"Description    : {(v.raw_description or v.summary or '—')}\n"
        f"Architecture   : {v.architecture}\n"
        f"URL            : {v.homepage or 'None'}\n"
        f"Licenses       : None\n"
        f"Groups         : {section}\n"
        f"Depends On     : {depends}\n"
        f"Optional Deps  : {optional}\n"
        f"Required By    : None\n"
        f"Conflicts With : {conflicts}\n"
        f"Provides       : {provides}\n"
        f"Replaces       : None\n"
        f"Installed Size : {size_h}\n"
        f"Packager       : {maintainer}\n"
        f"Build Date     : None\n"
        f"Install Date   : {install_date}\n"
        f"Install Reason : {reason}\n"
    )


# ─── DNF5 (Fedora 41+, the current default) — UNVERIFIED, see module docstring ──
# libdnf5's Python bindings are SWIG-generated from its C++ API. A Base
# needs its repos loaded before any query works, which is the expensive
# part (network/disk I/O reading repo metadata) — so, same reasoning as
# the apt.Cache() singleton above, one Base is built lazily and reused
# rather than reloaded on every call.

_dnf5_base = None
_dnf5_lock = threading.Lock()


def _get_dnf5_base():
    global _dnf5_base
    if _dnf5_base is None:
        with _dnf5_lock:
            if _dnf5_base is None:
                base = libdnf5.base.Base()
                base.load_config_from_file()
                base.setup()
                repo_sack = base.get_repo_sack()
                repo_sack.create_repos_from_system_configuration()
                repo_sack.update_and_load_repos(repo_sack.get_repos())
                _dnf5_base = base
    return _dnf5_base


def invalidate_dnf5_base():
    global _dnf5_base
    with _dnf5_lock:
        _dnf5_base = None


def _dnf5_evr(pkg):
    """version-release, matching the "version-release" shape the rest of
    Pachul already expects (e.g. from `dnf repoquery`'s %{version}-%{release})."""
    return f"{pkg.get_version()}-{pkg.get_release()}"


def dnf5_build_available_packages():
    base = _get_dnf5_base()
    query = libdnf5.rpm.PackageQuery(base)
    query.filter_available()
    pkgs = {}
    for pkg in query:
        name = pkg.get_name()
        if name not in pkgs:
            pkgs[name] = {
                "repo": pkg.get_repo_id() or "",
                "version": _dnf5_evr(pkg),
                "description": pkg.get_summary() or "",
            }
    return pkgs


def dnf5_is_installed(pkg_name):
    base = _get_dnf5_base()
    query = libdnf5.rpm.PackageQuery(base)
    query.filter_installed()
    query.filter_name([pkg_name])
    return bool(list(query))


def dnf5_check_updates():
    base = _get_dnf5_base()
    installed_q = libdnf5.rpm.PackageQuery(base)
    installed_q.filter_installed()
    installed = {p.get_name(): p for p in installed_q}

    upgrades_q = libdnf5.rpm.PackageQuery(base)
    upgrades_q.filter_upgrades()
    updates = []
    for pkg in upgrades_q:
        old = installed.get(pkg.get_name())
        updates.append({
            "name": pkg.get_name(),
            "old": _dnf5_evr(old) if old else "",
            "new": _dnf5_evr(pkg), "aur": False,
        })
    return updates


def dnf5_package_reason(pkg_name):
    """"user" (explicitly installed) or "dependency", or None if unknown/
    not installed — libdnf5 tracks this per-package via its own
    TransactionItemReason, the dnf5 equivalent of dnf4's yumdb reason."""
    base = _get_dnf5_base()
    query = libdnf5.rpm.PackageQuery(base)
    query.filter_installed()
    query.filter_name([pkg_name])
    pkgs = list(query)
    if not pkgs:
        return None
    reason = pkgs[0].get_reason()
    reason_name = str(reason).rsplit("_", 1)[-1].lower()
    return "user" if reason_name == "user" else "dependency"


# ─── DNF4 (classic, dnf/yum-era) — UNVERIFIED, see module docstring ───────────

def dnf_build_available_packages():
    base = dnf.Base()
    base.read_all_repos()
    base.fill_sack(load_system_repo=True)
    pkgs = {}
    for pkg in base.sack.query().available():
        if pkg.name not in pkgs:
            pkgs[pkg.name] = {
                "repo": pkg.reponame or "", "version": f"{pkg.version}-{pkg.release}",
                "description": pkg.summary or "",
            }
    return pkgs


def dnf_is_installed(pkg_name):
    base = dnf.Base()
    base.fill_sack(load_system_repo=True, load_available_repos=False)
    return bool(list(base.sack.query().installed().filter(name=pkg_name)))


def dnf_check_updates():
    base = dnf.Base()
    base.read_all_repos()
    base.fill_sack()
    updates = []
    installed = {p.name: p for p in base.sack.query().installed()}
    for pkg in base.sack.query().upgrades():
        old = installed.get(pkg.name)
        updates.append({
            "name": pkg.name,
            "old": f"{old.version}-{old.release}" if old else "",
            "new": f"{pkg.version}-{pkg.release}", "aur": False,
        })
    return updates
