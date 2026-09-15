#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  Pachul Uninstaller
#  Removes exactly what install.sh puts in place — its counterpart.
#
#  Main use case: install.sh and the AUR package (built from PKGBUILD, via
#  yay/paru/pikaur/pachuli) both write the same system paths (app modules,
#  desktop entry, hicolor icons…). If install.sh was used at some point,
#  those paths exist on disk but aren't owned by any pacman package —
#  pacman then refuses to install/upgrade the AUR package with a
#  "failed to commit transaction (conflicting files)" error. Run this
#  script first to clear the install.sh copy out of the way, then install
#  normally via your AUR helper.
#  https://github.com/wergosam/Pachul
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}${BOLD}[·]${RESET} $*"; }
success() { echo -e "${GREEN}${BOLD}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}${BOLD}[!]${RESET} $*"; }

# ── Paths (must mirror install.sh exactly) ──────────────────────────────────
APP_NAME="pachul"
INSTALL_DIR="/usr/local/bin"
DATA_DIR="/usr/local/share/${APP_NAME}"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
POLICY_DIR="/usr/share/polkit-1/actions"
ICON_ID="io.github.wergosam.pachul"
BW_ICON_ID="io_github_wergosam_pachul_bw"
DESKTOP_FILE="${DESKTOP_DIR}/${ICON_ID}.desktop"

echo -e "
Pachul — Uninstaller (removes an install.sh-based installation)
"

# ── Root check (same pattern as install.sh) ─────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    warn "Not running as root — re-launching with sudo…"
    exec sudo bash "$0" "$@"
fi

REMOVED_ANY=0
remove() {
    # $1: path, $2: human-readable label for the info line
    if [[ -e "$1" || -L "$1" ]]; then
        rm -rf "$1"
        info "Removed $2: $1"
        REMOVED_ANY=1
    fi
}

remove "${INSTALL_DIR}/${APP_NAME}"      "launcher"
remove "${INSTALL_DIR}/${APP_NAME}-tray" "tray launcher"
remove "${INSTALL_DIR}/pachuli"          "pachuli AUR helper"
remove "$DATA_DIR"                       "application modules"
remove "$DESKTOP_FILE"                   "desktop entry"
remove "${ICON_DIR}/${ICON_ID}.svg"      "app icon"
remove "${ICON_DIR}/${BW_ICON_ID}.svg"   "tray icon"
# A much older release used this filename here instead — see install.sh's
# own stale-icon cleanup step for the same reasoning; harmless if absent.
remove "${ICON_DIR}/io_github_wergosam_pachul_transparent.svg" "legacy icon (older release)"
remove "${POLICY_DIR}/${ICON_ID}.policy" "Polkit policy"

update-desktop-database "$DESKTOP_DIR" &>/dev/null || true
gtk-update-icon-cache -f -t /usr/share/icons/hicolor &>/dev/null || true

echo
if [[ $REMOVED_ANY -eq 1 ]]; then
    success "install.sh's copy of Pachul has been removed."
else
    info "Nothing found to remove — install.sh may never have been used here, or it's already gone."
fi
echo
echo -e "You can now install Pachul via your AUR helper, e.g.: ${BOLD}yay -S pachul${RESET}"
echo
warn "Note: the per-user background-update timer and tray autostart entry"
warn "(if enabled via Preferences) live under your own \$HOME and aren't touched by"
warn "this script — turn them off from Preferences first if you'd like, or just"
warn "leave them; they'll simply do nothing until Pachul is reinstalled."

# ─────────────────────────────────────────────────────────────────────────────
#  Optional: pacman/AUR-helper cache cleanup
# ─────────────────────────────────────────────────────────────────────────────
# Unrelated to the conflicting-files fix above (pacman's package cache and
# an AUR helper's own build-dir cache are plain, unregistered directories —
# they can't cause that error either way) — offered here purely as a
# convenient extra since a cleanup script is already running. Opt-in only,
# since it clears real disk cache, not just Pachul's own files.
# Prefers pachuli (matching Pachul's own default AUR-helper preference —
# see aur_helper_install_cmd() in backend.py); falls back to yay, which
# supports the same -Sc/-Scc flags, if pachuli isn't on PATH.
CACHE_TOOL=""
if command -v pachuli &>/dev/null; then
    CACHE_TOOL="pachuli"
elif command -v yay &>/dev/null; then
    CACHE_TOOL="yay"
fi

if [[ -n "$CACHE_TOOL" ]]; then
    echo
    read -rp "$(echo -e "${CYAN}${BOLD}[?]${RESET} Also clean the pacman/AUR package cache now via '${CACHE_TOOL} -Sc'? [y/N] ")" REPLY || REPLY="n"
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        # Both tools' own escalation (pkexec for pachuli, an internal sudo
        # call for yay) and their build-cache paths need to run as the
        # actual invoking user, not root — this script may itself be
        # running as root by now (see the sudo re-exec above), so hand
        # off via sudo -u back to $SUDO_USER when we have one, instead of
        # quietly operating on root's own cache/home.
        if [[ -n "${SUDO_USER:-}" ]]; then
            sudo -u "$SUDO_USER" "$CACHE_TOOL" -Sc || true
        else
            "$CACHE_TOOL" -Sc || true
        fi
    else
        info "Skipped cache cleanup."
    fi
else
    info "Neither pachuli nor yay found on PATH — skipping optional cache cleanup."
fi
