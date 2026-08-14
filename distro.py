"""
Pachul — distro.py
Linux distribution / package-manager-family detection.

Pachul was originally an Arch-only tool built entirely around pacman/AUR.
This module is the single place that answers "which package manager am I
running on?" — everything else (backend.py, pkgmanager.py) asks *this*
module rather than re-detecting things itself, so there's exactly one
place to fix if a new distro needs adding later.

Detected families: "arch", "debian", "fedora", "suse".
Downstream/derivative distros resolve to the right family automatically
via /etc/os-release's ID_LIKE field, e.g.:
  Manjaro, EndeavourOS, CachyOS, Garuda      -> arch
  Ubuntu, Linux Mint, Pop!_OS, elementary OS -> debian
  Nobara, RHEL, CentOS Stream, Rocky, Alma   -> fedora
  openSUSE Leap, openSUSE Tumbleweed         -> suse

For "arch" specifically, /etc/pacman.conf's presence is checked FIRST,
ahead of ID_LIKE — small/personal Arch derivatives (e.g. Xray_OS) often
skip setting ID_LIKE=arch, so relying on ID_LIKE alone silently missed
them even though they're fully pacman-based.
"""

import shutil
from pathlib import Path

OS_RELEASE = Path("/etc/os-release")

# id / id_like tokens (lowercased) that map to each family. Checked in
# this order; first match wins.
_FAMILY_HINTS = {
    "arch":   ("arch", "archlinux", "manjaro", "endeavouros"),
    "debian": ("debian", "ubuntu"),
    "fedora": ("fedora", "rhel", "centos"),
    "suse":   ("suse", "opensuse", "sles"),
}

# The primary CLI binary used to identify/drive each family, in the
# fallback path (used when /etc/os-release is missing or unrecognised —
# e.g. a minimal container image).
_PM_BINARY = {
    "arch":   "pacman",
    "debian": "apt-get",
    "fedora": "dnf",
    "suse":   "zypper",
}

_cache = {}


def _read_os_release():
    data = {}
    try:
        for line in OS_RELEASE.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            data[key.strip()] = val.strip().strip('"').strip("'")
    except Exception:
        pass
    return data


def _family_from_pacman_conf():
    """/etc/pacman.conf existing is the single most reliable "this is an
    Arch-based system" signal there is — pacman cannot run without it.
    Checked before the ID_LIKE text-matching below and before the PATH-
    dependent binary lookup, because small/personal Arch derivatives
    (e.g. Xray_OS) often don't bother setting ID_LIKE=arch in their
    /etc/os-release the way the bigger, more established ones (Manjaro,
    EndeavourOS, CachyOS, Garuda) do — which otherwise left them
    undetected as "arch" here even though they're 100% pacman-based.
    A plain filesystem check also sidesteps the (rarer, but real) case
    where a GUI app launched from a desktop icon/tray gets a trimmed
    PATH that doesn't include pacman for shutil.which() to find."""
    return "arch" if Path("/etc/pacman.conf").exists() else None


def _family_from_os_release():
    data = _read_os_release()
    ids = [data.get("ID", "")] + data.get("ID_LIKE", "").split()
    ids = [i.lower() for i in ids if i]
    for family, hints in _FAMILY_HINTS.items():
        if any(i in hints for i in ids):
            return family
    return None


def _family_from_binaries():
    """Fallback for when /etc/os-release is missing or its ID/ID_LIKE
    isn't one we recognise: just see which package-manager binary is
    actually on PATH. dnf5 (Fedora 41+) still ships a `dnf` binary/alias,
    so no special-casing is needed there."""
    for family, binary in _PM_BINARY.items():
        if shutil.which(binary):
            return family
    return None


def get_family():
    """Return 'arch' | 'debian' | 'fedora' | 'suse' | None.
    None means no supported package manager was found at all (Pachul
    then falls back to its existing demo-data mode)."""
    if "family" not in _cache:
        _cache["family"] = (_family_from_pacman_conf()
                             or _family_from_os_release()
                             or _family_from_binaries())
    return _cache["family"]


def get_package_manager():
    """Primary CLI binary name for the detected family, or None."""
    return _PM_BINARY.get(get_family())


def is_arch():
    return get_family() == "arch"


def is_debian():
    return get_family() == "debian"


def is_fedora():
    return get_family() == "fedora"


def is_suse():
    return get_family() == "suse"


def is_rpm_based():
    """Fedora and openSUSE both use rpm/dnf-style low-level tooling
    (rpm -qi/-ql/--requires/... all work identically on both), so a lot
    of package-info code can treat them as one group."""
    return get_family() in ("fedora", "suse")


def get_distro_name():
    """Human-readable distro name for display (e.g. system-info page)."""
    data = _read_os_release()
    return data.get("PRETTY_NAME") or data.get("NAME") or "Unknown Linux"


def reset_cache():
    """Forces re-detection on the next call. Mainly useful for tests."""
    _cache.clear()
