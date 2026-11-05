"""
Pachul — localpkg.py
Manual installation of a local package file (e.g. a downloaded .tar.gz).

No GTK in here on purpose, so the detection logic can be tested on its own.

Recognised kinds
----------------
"pacman_pkg"  A *built* Arch package: the archive has a ``.PKGINFO`` file at
              its root (``*.pkg.tar.zst`` / ``.xz`` / ``.gz`` ...). Installed
              with ``pacman -U``.
"pkgbuild"    A *source* tarball with a ``PKGBUILD`` (an AUR snapshot, i.e.
              ``<name>.tar.gz`` from aur.archlinux.org). It is unpacked into a
              private build directory, built with ``makepkg`` as the normal
              user and the result is installed with ``pacman -U``.
"deb" / "rpm" Plain ``.deb`` / ``.rpm`` files on Debian/Ubuntu, Fedora and
              openSUSE (installed through the distro's own tool, so
              dependencies are resolved).
"flatpak_bundle" A ``.flatpak`` single-file bundle, installed with
              ``flatpak install --bundle`` (any distro that has Flatpak).
"flatpak_ref" A ``.flatpakref`` file; Flatpak downloads the app from the
              remote named inside it.
"unknown"     Anything else — nothing is ever installed blindly.

Nothing is extracted during analysis; ``tar -t`` / ``tar -xO`` only *read*.
"""

import os
import shlex
import shutil
import subprocess

import distro

KIND_PACMAN_PKG = "pacman_pkg"
KIND_PKGBUILD   = "pkgbuild"
KIND_DEB        = "deb"
KIND_RPM        = "rpm"
KIND_FLATPAK_BUNDLE = "flatpak_bundle"
KIND_FLATPAK_REF    = "flatpak_ref"
KIND_UNKNOWN    = "unknown"

# Upper bound for text read out of an archive (PKGBUILD / .PKGINFO). Real
# files are a few KiB; this just keeps a hostile archive from flooding the UI.
_MAX_TEXT_BYTES = 256 * 1024

# Patterns offered in the file chooser ("Package files"); "All files" is
# always added as a second filter by the caller.
FILE_PATTERNS = (
    "*.tar.gz", "*.tgz", "*.tar.zst", "*.tar.xz", "*.tar.bz2",
    "*.pkg.tar.*", "*.deb", "*.rpm", "*.flatpak", "*.flatpakref",
)


def _run_tar(args, timeout=60):
    """Run GNU/bsd tar (auto-detects gz/xz/zst/bz2). Returns (rc, stdout bytes)."""
    try:
        p = subprocess.run(["tar", *args], capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return 1, b""
    return p.returncode, p.stdout


def _list_members(path):
    rc, out = _run_tar(["-tf", path])
    if rc != 0:
        return None
    return [m for m in out.decode("utf-8", "replace").splitlines() if m]


def _unsafe_member(name):
    """Absolute paths or '..' components: never extract such an archive."""
    if name.startswith("/"):
        return True
    return ".." in name.replace("\\", "/").split("/")


def _read_member(path, member):
    rc, out = _run_tar(["-xOf", path, "--", member])
    if rc != 0:
        return ""
    return out[:_MAX_TEXT_BYTES].decode("utf-8", "replace")


def _parse_kv(text, keys):
    """Parse ``key = value`` lines (.PKGINFO / .SRCINFO style); first hit wins."""
    res = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k in keys and k not in res:
            res[k] = v
    return res


def _find_pkgbuild_member(members):
    """Path of the PKGBUILD closest to the archive root ('PKGBUILD' or
    '<dir>/PKGBUILD'), or None."""
    best = None
    for m in members:
        clean = m[2:] if m.startswith("./") else m
        parts = [p for p in clean.split("/") if p]
        if not parts or parts[-1] != "PKGBUILD":
            continue
        if len(parts) > 2:
            continue
        if best is None or len(parts) < best[0]:
            best = (len(parts), "/".join(parts))
    return best[1] if best else None


def analyze(path):
    """Inspect *path* without extracting or installing anything.

    Returns a dict with at least: ``path``, ``kind``, ``size`` and either
    ``error`` (str, set whenever kind == "unknown" or nothing can be done) or
    the details for the install dialog:
      name, version, desc, arch   — what the package says about itself
      pkgbuild_text, build_dir    — only for kind "pkgbuild"
      supported                   — False when this distro can't install it
    """
    info = {
        "path": path, "kind": KIND_UNKNOWN, "size": 0,
        "name": "", "version": "", "desc": "", "arch": "",
        "pkgbuild_text": "", "build_dir": "", "error": "",
        "supported": False, "entries": [],
    }
    try:
        info["size"] = os.path.getsize(path)
    except OSError as e:
        info["error"] = str(e)
        return info

    lower = path.lower()
    fam = distro.get_family()

    # ── Flatpak ──────────────────────────────────────────────────────────
    if lower.endswith(".flatpakref"):
        info["kind"] = KIND_FLATPAK_REF
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read(_MAX_TEXT_BYTES)
        except OSError as e:
            info["error"] = str(e)
            return info
        if not text.lstrip().startswith("[Flatpak Ref]"):
            info["error"] = "The file is not a valid .flatpakref."
            return info
        meta = _parse_kv(text, ("Name", "Branch", "Title", "Url"))
        info["name"]    = meta.get("Name", "")
        info["version"] = meta.get("Branch", "")
        info["desc"]    = meta.get("Title", "")
        info["supported"] = bool(shutil.which("flatpak"))
        if not info["supported"]:
            info["error"] = "Flatpak is not installed."
        return info
    if lower.endswith(".flatpak"):
        info["kind"] = KIND_FLATPAK_BUNDLE
        info["supported"] = bool(shutil.which("flatpak"))
        if not info["supported"]:
            info["error"] = "Flatpak is not installed."
        return info

    # ── plain distro packages ────────────────────────────────────────────
    if lower.endswith(".deb"):
        info["kind"] = KIND_DEB
        info["supported"] = fam == "debian"
        if not info["supported"]:
            info["error"] = "A .deb file can only be installed on Debian/Ubuntu."
        return info
    if lower.endswith(".rpm"):
        info["kind"] = KIND_RPM
        info["supported"] = fam in ("fedora", "suse")
        if not info["supported"]:
            info["error"] = "An .rpm file can only be installed on Fedora/openSUSE."
        return info

    # ── tar archives ─────────────────────────────────────────────────────
    members = _list_members(path)
    if members is None:
        info["error"] = "This file is not a readable archive."
        return info
    info["entries"] = members[:12]

    bad = [m for m in members if _unsafe_member(m)]
    if bad:
        info["error"] = ("The archive contains unsafe paths (absolute or "
                         "'..') and will not be unpacked.")
        return info

    # normalised name ("./x/" -> "x") -> name exactly as tar lists it
    norm = {(m[2:] if m.startswith("./") else m).rstrip("/"): m for m in members}

    if ".PKGINFO" in norm:
        info["kind"] = KIND_PACMAN_PKG
        meta = _parse_kv(_read_member(path, norm[".PKGINFO"]),
                         ("pkgname", "pkgver", "pkgdesc", "arch"))
        info["name"]    = meta.get("pkgname", "")
        info["version"] = meta.get("pkgver", "")
        info["desc"]    = meta.get("pkgdesc", "")
        info["arch"]    = meta.get("arch", "")
        info["supported"] = fam == "arch"
        if not info["supported"]:
            info["error"] = "This is an Arch Linux package; it can only be installed on Arch-based systems."
        return info

    pb = _find_pkgbuild_member(members)
    if pb:
        info["kind"] = KIND_PKGBUILD
        info["build_dir"] = os.path.dirname(pb)          # "" if at the root
        text = _read_member(path, norm[pb])
        info["pkgbuild_text"] = text
        meta = _parse_kv(text, ("pkgname", "pkgver", "pkgdesc"))
        info["name"]    = meta.get("pkgname", "").strip("()\"' ")
        info["version"] = meta.get("pkgver", "").strip("\"' ")
        info["desc"]    = meta.get("pkgdesc", "").strip("\"' ")
        fallback = os.path.basename(path)
        for suffix in (".tar.gz", ".tgz", ".tar.xz", ".tar.zst", ".tar.bz2"):
            if fallback.lower().endswith(suffix):
                fallback = fallback[: -len(suffix)]
                break
        if not info["name"] or info["name"].startswith("$"):
            info["name"] = info["build_dir"] or fallback
        info["supported"] = (fam == "arch"
                             and bool(shutil.which("makepkg"))
                             and bool(shutil.which("pacman")))
        if fam != "arch":
            info["error"] = "A PKGBUILD can only be built on Arch-based systems."
        elif not info["supported"]:
            info["error"] = ("makepkg was not found. Install the "
                             "\"base-devel\" package group first.")
        return info

    info["error"] = ("Not an installable package: the archive contains neither "
                     "a .PKGINFO (built Arch package) nor a PKGBUILD (source "
                     "package). Pachul does not run unknown install scripts.")
    return info


# ─── Command builders ────────────────────────────────────────────────────────

def _build_script(path, build_dir):
    """Shell script (run through ``bash -c``): unpack into a private build
    directory, install missing dependencies via pacman (pkexec), build as the
    normal user, install the result with ``pacman -U`` and clean up."""
    q_path = shlex.quote(path)
    q_sub  = shlex.quote(build_dir)
    return f"""
set -e
BASE="${{XDG_CACHE_HOME:-$HOME/.cache}}/pachul/build"
mkdir -p "$BASE"
WORK="$(mktemp -d "$BASE/local.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
echo "==> Unpacking into $WORK"
tar -xf {q_path} -C "$WORK"
cd "$WORK"/{q_sub}
test -f PKGBUILD || {{ echo "PKGBUILD not found"; exit 1; }}

echo "==> Checking dependencies"
DEPS="$(makepkg --printsrcinfo 2>/dev/null \\
        | sed -n 's/^[[:space:]]*\\(depends\\|makedepends\\|checkdepends\\) = //p' \\
        | sort -u)"
MISSING=""
if [ -n "$DEPS" ]; then
    MISSING="$(printf '%s\\n' "$DEPS" | xargs -r pacman -T || true)"
fi
if [ -n "$MISSING" ]; then
    echo "==> Installing missing dependencies: $MISSING"
    # shellcheck disable=SC2086
    pkexec /usr/bin/pacman -S --needed --asdeps --noconfirm $MISSING
fi

echo "==> Building (makepkg)"
makepkg -cf --noconfirm

PKGS="$(makepkg --packagelist | while read -r f; do [ -f "$f" ] && printf '%s\\n' "$f"; done)"
if [ -z "$PKGS" ]; then
    echo "No built package found"; exit 1
fi
echo "==> Installing"
printf '%s\\n' "$PKGS" | tr '\\n' '\\0' | xargs -0 pkexec /usr/bin/pacman -U --noconfirm
"""


def install_command(info):
    """Return the shell command for the terminal panel, or None if *info*
    can't be installed on this system."""
    if not info.get("supported"):
        return None
    path = info["path"]
    kind = info["kind"]
    q = shlex.quote(path)
    if kind == KIND_PACMAN_PKG:
        return f"pkexec /usr/bin/pacman -U --noconfirm {q}"
    if kind == KIND_PKGBUILD:
        return "bash -c " + shlex.quote(_build_script(path, info["build_dir"]))
    if kind == KIND_FLATPAK_BUNDLE:
        return f"flatpak install --user -y --bundle {q}"
    if kind == KIND_FLATPAK_REF:
        return f"flatpak install --user -y {q}"
    if kind == KIND_DEB:
        return f"pkexec /usr/bin/apt-get install -y {q}"
    if kind == KIND_RPM:
        if distro.get_family() == "suse":
            # No --non-interactive: an unsigned local rpm should be confirmed
            # by the user in the terminal, not silently accepted.
            return f"pkexec /usr/bin/zypper install {q}"
        return f"pkexec /usr/bin/dnf install -y {q}"
    return None
