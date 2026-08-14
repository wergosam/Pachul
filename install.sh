#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  Pachul Installer
#  A powerful Pacman/AUR front end using GTK4 and libadwaita
#  https://github.com/wergosam/Pachul
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}${BOLD}[·]${RESET} $*"; }
success() { echo -e "${GREEN}${BOLD}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}${BOLD}[!]${RESET} $*"; }
error()   { echo -e "${RED}${BOLD}[✗]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Paths ─────────────────────────────────────────────────────────────────────
APP_NAME="pachul"
INSTALL_DIR="/usr/local/bin"
DATA_DIR="/usr/local/share/${APP_NAME}"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
ICON_ID="io.github.wergosam.pachul"
DESKTOP_FILE="${DESKTOP_DIR}/${ICON_ID}.desktop"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Application Python modules (relative to SRC_DIR)
PY_MODULES=(app.py backend.py dialogs.py distro.py i18n.py icons.py models.py
            pkgmanager.py pkgmanager_native.py styles.py window.py notifier.py tray.py)

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "
Pachul — Pacman/AUR Front End — Installer v1.0.0
"

# ── Root check ────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    warn "Not running as root — re-launching with sudo…"
    exec sudo bash "$0" "$@"
fi

# ── Distro / package-manager detection ───────────────────────────────────────
# Pachul now also supports Debian/Ubuntu (apt), Fedora (dnf) and openSUSE
# (zypper) — see distro.py/pkgmanager.py. This installer only needs to know
# which package manager to use for its OWN dependency install below; it
# mirrors distro.py's own detection logic (os-release ID/ID_LIKE, falling
# back to whichever binary is on PATH) so both stay in sync.
detect_family() {
    if [[ -r /etc/os-release ]]; then
        . /etc/os-release
        local ids="${ID:-} ${ID_LIKE:-}"
        case " ${ids} " in
            *" arch "*|*" archlinux "*|*" manjaro "*|*" endeavouros "*) echo arch; return ;;
            *" debian "*|*" ubuntu "*) echo debian; return ;;
            *" fedora "*|*" rhel "*|*" centos "*) echo fedora; return ;;
            *" suse "*|*" opensuse "*|*" sles "*) echo suse; return ;;
        esac
    fi
    if command -v pacman &>/dev/null; then echo arch
    elif command -v apt-get &>/dev/null; then echo debian
    elif command -v dnf &>/dev/null; then echo fedora
    elif command -v zypper &>/dev/null; then echo suse
    else echo unknown
    fi
}

DISTRO_FAMILY="$(detect_family)"
info "Detected package manager family: ${DISTRO_FAMILY}"

if [[ "$DISTRO_FAMILY" == "unknown" ]]; then
    die "Pachul requires Arch (pacman), Debian/Ubuntu (apt), Fedora (dnf) or openSUSE (zypper) — none found."
fi

# ── Source file check ─────────────────────────────────────────────────────────
info "Checking source files…"
MISSING_FILES=()
for f in "${PY_MODULES[@]}"; do
    [[ -f "${SRC_DIR}/${f}" ]] || MISSING_FILES+=("$f")
done
[[ -f "${SRC_DIR}/${ICON_ID}.svg" ]] || MISSING_FILES+=("${ICON_ID}.svg")

if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    die "Missing files in ${SRC_DIR}:\n$(printf '   • %s\n' "${MISSING_FILES[@]}")"
fi
success "All source files present."

# ─────────────────────────────────────────────────────────────────────────────
#  1. Dependencies
# ─────────────────────────────────────────────────────────────────────────────
info "Checking dependencies…"

# Package names differ per distro. Arch and Fedora are verified against
# real systems; Debian/Ubuntu and openSUSE names are best-effort (same
# "written carefully, not live-tested" caveat as the rest of the
# multi-distro work — see DISTRO_SUPPORT_CHANGES.md) and worth double-
# checking on a real system if dependency install fails there.
case "$DISTRO_FAMILY" in
    arch)
        REQUIRED_PKGS=(python gtk4 libadwaita python-gobject pacman-contrib libnotify)
        is_installed() { pacman -Qi "$1" &>/dev/null; }
        install_pkgs() { pacman -Sy --noconfirm --needed "$@"; }
        ;;
    fedora)
        REQUIRED_PKGS=(python3 gtk4 libadwaita python3-gobject libnotify)
        is_installed() { rpm -q "$1" &>/dev/null; }
        install_pkgs() { dnf install -y "$@"; }
        ;;
    debian)
        REQUIRED_PKGS=(python3 gir1.2-gtk-4.0 gir1.2-adw-1 python3-gi libnotify-bin)
        is_installed() { dpkg -s "$1" &>/dev/null; }
        install_pkgs() { apt-get update && apt-get install -y "$@"; }
        ;;
    suse)
        REQUIRED_PKGS=(python3 typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-gobject libnotify-tools)
        is_installed() { rpm -q "$1" &>/dev/null; }
        install_pkgs() { zypper --non-interactive install "$@"; }
        ;;
esac

MISSING_PKGS=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    is_installed "$pkg" || MISSING_PKGS+=("$pkg")
done

if [[ ${#MISSING_PKGS[@]} -gt 0 ]]; then
    warn "Installing missing packages: ${MISSING_PKGS[*]}"
    install_pkgs "${MISSING_PKGS[@]}" || die "Failed to install dependencies."
    success "Dependencies installed."
else
    success "All dependencies satisfied."
fi

# ─────────────────────────────────────────────────────────────────────────────
#  2. Install application modules
# ─────────────────────────────────────────────────────────────────────────────
info "Installing Pachul modules to ${DATA_DIR}…"

install -d "$DATA_DIR"
for f in "${PY_MODULES[@]}"; do
    install -m 644 "${SRC_DIR}/${f}" "${DATA_DIR}/${f}"
done
success "Modules installed."

# ─────────────────────────────────────────────────────────────────────────────
#  3. Launcher wrapper
# ─────────────────────────────────────────────────────────────────────────────
info "Creating launcher at ${INSTALL_DIR}/${APP_NAME}…"

cat > "${INSTALL_DIR}/${APP_NAME}" <<EOF
#!/usr/bin/env bash
# Pachul launcher — generated by install.sh
export PYTHONPATH="${DATA_DIR}:\${PYTHONPATH:-}"
exec python3 "${DATA_DIR}/app.py" "\$@"
EOF
chmod 755 "${INSTALL_DIR}/${APP_NAME}"
success "Launcher created."

# ─────────────────────────────────────────────────────────────────────────────
#  3b. Tray launcher (persistent update-status icon, see tray.py)
# ─────────────────────────────────────────────────────────────────────────────
info "Creating tray launcher at ${INSTALL_DIR}/${APP_NAME}-tray…"

cat > "${INSTALL_DIR}/${APP_NAME}-tray" <<EOF
#!/usr/bin/env bash
# Pachul tray launcher — generated by install.sh
export PYTHONPATH="${DATA_DIR}:\${PYTHONPATH:-}"
exec python3 "${DATA_DIR}/tray.py" "\$@"
EOF
chmod 755 "${INSTALL_DIR}/${APP_NAME}-tray"
success "Tray launcher created."

case "$DISTRO_FAMILY" in
    arch)
        if ! pacman -Qi libayatana-appindicator &>/dev/null && ! pacman -Qi libappindicator-gtk3 &>/dev/null; then
            warn "libayatana-appindicator not found — the tray icon needs it to show up."
            warn "Install with: sudo pacman -S libayatana-appindicator"
        fi
        ;;
    fedora)
        if ! rpm -q libappindicator-gtk3 &>/dev/null; then
            warn "libappindicator-gtk3 not found — the tray icon needs it to show up."
            warn "Install with: sudo dnf install libappindicator-gtk3"
        fi
        ;;
    debian)
        if ! dpkg -s gir1.2-ayatanaappindicator3-0.1 &>/dev/null; then
            warn "libayatana-appindicator (GObject introspection bindings) not found — the tray icon needs it."
            warn "Install with: sudo apt-get install gir1.2-ayatanaappindicator3-0.1"
        fi
        ;;
    suse)
        if ! rpm -q typelib-1_0-AyatanaAppIndicator3-0_1 &>/dev/null; then
            warn "AyatanaAppIndicator3 typelib not found — the tray icon needs it to show up."
            warn "Install with: sudo zypper install typelib-1_0-AyatanaAppIndicator3-0_1"
        fi
        ;;
esac

# Autostart for the tray icon is no longer set up here — Pachul manages its
# own per-user autostart entry (~/.config/autostart), toggleable from
# Preferences → Tray Icon, so it works without another sudo prompt and
# never conflicts with a system-wide entry.
info "Tray icon autostart: enable it from Pachul's Preferences → Tray Icon."

# ─────────────────────────────────────────────────────────────────────────────
#  4. Desktop entry
# ─────────────────────────────────────────────────────────────────────────────
info "Creating desktop entry…"

install -d "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Pachul
GenericName=Package Manager
Comment=A powerful Pacman/AUR front end
Exec=${INSTALL_DIR}/${APP_NAME}
Icon=${ICON_ID}
Categories=System;PackageManager;
Keywords=pacman;aur;packages;arch;
Terminal=false
StartupWMClass=pachul
EOF
success "Desktop entry created."

# ─────────────────────────────────────────────────────────────────────────────
#  5. Icon
# ─────────────────────────────────────────────────────────────────────────────
info "Installing icon…"

install -d "$ICON_DIR"
install -m 644 "${SRC_DIR}/${ICON_ID}.svg" "${ICON_DIR}/${ICON_ID}.svg"
gtk-update-icon-cache -f -t /usr/share/icons/hicolor &>/dev/null || true
success "Icon installed."

# ─────────────────────────────────────────────────────────────────────────────
#  6. Update desktop database
# ─────────────────────────────────────────────────────────────────────────────
update-desktop-database "$DESKTOP_DIR" &>/dev/null || true

# ─────────────────────────────────────────────────────────────────────────────
#  Done
# ─────────────────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}${BOLD}  Pachul installed successfully!${RESET}"
echo
echo -e "  Installed modules  : ${BOLD}${DATA_DIR}/${RESET}"
printf  "                       %s\n" "${PY_MODULES[@]}"
echo
echo -e "  Run from terminal  : ${BOLD}pachul${RESET}"
echo -e "  Or launch from     : ${BOLD}Applications → System → Pachul${RESET}"
echo
echo -e "  Tray update icon   : enable at login via Preferences → Tray Icon"
echo -e "  Run it right away  : ${BOLD}${APP_NAME}-tray &${RESET}"
echo
