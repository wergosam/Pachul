#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
#  Pachul installer
#  Graphical Pacman/AUR front end (GTK4 + libadwaita)
#  https://github.com/wergosam/Pachul
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Terminal output helpers ───────────────────────────────────────────────────
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

# _say <colour> <symbol> <text…> — coloured "[symbol] text"; text may use \n etc.
_say() {
    local colour="$1" symbol="$2"
    shift 2
    printf '%s%s[%s]%s %b\n' "$colour" "$BOLD" "$symbol" "$RESET" "$*"
}
info()    { _say "$CYAN"   '·' "$@"; }
success() { _say "$GREEN"  '✓' "$@"; }
warn()    { _say "$YELLOW" '!' "$@"; }
error()   { _say "$RED"    '✗' "$@" >&2; }
die()     { error "$*"; exit 1; }

# ── Names and locations ───────────────────────────────────────────────────────
APP_NAME="pachul"
ICON_ID="io.github.wergosam.pachul"
BW_ICON_ID="io_github_wergosam_pachul_bw"

INSTALL_DIR=/usr/local/bin
DATA_DIR=/usr/local/share/${APP_NAME}
DESKTOP_DIR=/usr/share/applications
ICON_DIR=/usr/share/icons/hicolor/scalable/apps
POLICY_DIR=/usr/share/polkit-1/actions
DESKTOP_FILE="${DESKTOP_DIR}/${ICON_ID}.desktop"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python modules shipped next to this script
PY_MODULES=(
    app.py backend.py dialogs.py distro.py i18n.py icons.py localpkg.py
    models.py pkgmanager.py pkgmanager_native.py styles.py toolshub.py
    window.py notifier.py tray.py
)
# Icons that are copied both to DATA_DIR and to the hicolor theme
ICON_FILES=("${ICON_ID}.svg" "${BW_ICON_ID}.svg")

# ── Welcome ───────────────────────────────────────────────────────────────────
printf '\n%s\n\n' "Pachul — Pacman/AUR Front End — Installer v1.0.0"

# Installing system files needs root; restart through sudo if necessary
[[ $EUID -eq 0 ]] || {
    warn "Not running as root — re-launching with sudo…"
    exec sudo bash "$0" "$@"
}

# ── Which package manager are we on? ─────────────────────────────────────────
# Pachul runs on Arch (pacman), Debian/Ubuntu (apt), Fedora (dnf) and
# openSUSE (zypper), see distro.py / pkgmanager.py. The installer only needs
# the family to pick its own dependency commands. It follows distro.py: first
# the os-release ID / ID_LIKE words, then whichever tool is found on PATH.
detect_family() {
    local words="" family word tool
    local -A id_words=(
        [arch]="arch archlinux manjaro endeavouros"
        [debian]="debian ubuntu"
        [fedora]="fedora rhel centos"
        [suse]="suse opensuse sles"
    )
    local -A path_tools=(
        [arch]=pacman [debian]=apt-get [fedora]=dnf [suse]=zypper
    )

    if [[ -r /etc/os-release ]]; then
        . /etc/os-release
        words=" ${ID:-} ${ID_LIKE:-} "
        for family in arch debian fedora suse; do
            for word in ${id_words[$family]}; do
                if [[ "$words" == *" ${word} "* ]]; then
                    echo "$family"
                    return
                fi
            done
        done
    fi
    for family in arch debian fedora suse; do
        tool="${path_tools[$family]}"
        if command -v "$tool" &>/dev/null; then
            echo "$family"
            return
        fi
    done
    echo unknown
}

DISTRO_FAMILY="$(detect_family)"
info "Detected package manager family: ${DISTRO_FAMILY}"

if [[ "$DISTRO_FAMILY" == "unknown" ]]; then
    die "Pachul requires Arch (pacman), Debian/Ubuntu (apt), Fedora (dnf) or openSUSE (zypper) — none found."
fi

# ── Are all files here? ──────────────────────────────────────────────────────
info "Checking source files…"
absent=()
for rel in "${PY_MODULES[@]}" "${ICON_FILES[@]}"; do
    [[ -f "${SRC_DIR}/${rel}" ]] || absent+=("$rel")
done
if (( ${#absent[@]} > 0 )); then
    die "Missing files in ${SRC_DIR}:\n$(printf '   • %s\n' "${absent[@]}")"
fi
success "All source files present."

# ══ 1. Dependencies ═══════════════════════════════════════════════════════════
info "Checking dependencies…"

# Package names differ between distributions. The Arch and Fedora lists were
# checked on real systems; the Debian/Ubuntu and openSUSE names are
# best-effort (written carefully, not live-tested — see
# DISTRO_SUPPORT_CHANGES.md). If the install fails there, compare them with
# your distribution's package search.
case "$DISTRO_FAMILY" in
    arch)
        REQUIRED_PKGS=(python gtk4 libadwaita python-gobject pacman-contrib libnotify)
        QUERY_CMD=(pacman -Qi)
        INSTALL_CMD=(pacman -Sy --noconfirm --needed)
        ;;
    fedora)
        REQUIRED_PKGS=(python3 gtk4 libadwaita python3-gobject libnotify)
        QUERY_CMD=(rpm -q)
        INSTALL_CMD=(dnf install -y)
        ;;
    debian)
        REQUIRED_PKGS=(python3 gir1.2-gtk-4.0 gir1.2-adw-1 python3-gi libnotify-bin)
        QUERY_CMD=(dpkg -s)
        INSTALL_CMD=(apt-get install -y)
        ;;
    suse)
        REQUIRED_PKGS=(python3 typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-gobject libnotify-tools)
        QUERY_CMD=(rpm -q)
        INSTALL_CMD=(zypper --non-interactive install)
        ;;
esac

is_installed() { "${QUERY_CMD[@]}" "$1" &>/dev/null; }

install_pkgs() {
    # apt needs a fresh package index first; stop if that fails
    if [[ "$DISTRO_FAMILY" == "debian" ]]; then
        apt-get update || return 1
    fi
    "${INSTALL_CMD[@]}" "$@"
}

to_install=()
for dep in "${REQUIRED_PKGS[@]}"; do
    is_installed "$dep" || to_install+=("$dep")
done

if (( ${#to_install[@]} == 0 )); then
    success "All dependencies satisfied."
else
    warn "Installing missing packages: ${to_install[*]}"
    if ! install_pkgs "${to_install[@]}"; then
        die "Failed to install dependencies."
    fi
    success "Dependencies installed."
fi

# ══ 2. Application modules ════════════════════════════════════════════════════

# First remove icon files from an earlier installation. `install` itself would
# simply overwrite them, but a later install through the package manager (the
# AUR package built from PKGBUILD) fails with "file already exists, owned by
# no package" if these paths are still around from an install.sh run or from
# an older release with a different icon name (e.g. the unused "_transparent"
# variant). Deleting them up front, wherever they ended up, gives every
# install a clean start.
STALE_ICON_FILES=(
    "io_github_wergosam_pachul_bw.svg"
    "io_github_wergosam_pachul_transparent.svg"
    "io.github.wergosam.pachul.svg"
)
info "Checking for icon files left over from a previous installation…"
removed_any=0
for dir in "$DATA_DIR" "$ICON_DIR"; do
    for name in "${STALE_ICON_FILES[@]}"; do
        leftover="${dir}/${name}"
        # -L as well as -e: a dangling symlink fails -e although the link is
        # still there (same idea as os.path.lexists() in app.py)
        if [[ -e "$leftover" || -L "$leftover" ]]; then
            rm -f "$leftover"
            info "Removed existing ${leftover}"
            removed_any=1
        fi
    done
done
if (( removed_any )); then
    success "Stale icon files removed."
else
    info "No stale icon files found."
fi

info "Installing Pachul modules to ${DATA_DIR}…"
install -d "$DATA_DIR"
for rel in "${PY_MODULES[@]}" "${ICON_FILES[@]}"; do
    install -m 644 "${SRC_DIR}/${rel}" "${DATA_DIR}/${rel}"
done
success "Modules installed."

# ══ 3. Launchers ══════════════════════════════════════════════════════════════

# write_launcher <file> <description> <python file in DATA_DIR>
write_launcher() {
    local file="$1" description="$2" entry="$3"
    cat > "$file" <<EOF
#!/usr/bin/env bash
# ${description} — generated by install.sh
export PYTHONPATH="${DATA_DIR}:\${PYTHONPATH:-}"
exec python3 "${DATA_DIR}/${entry}" "\$@"
EOF
    chmod 755 "$file"
}

info "Creating launcher at ${INSTALL_DIR}/${APP_NAME}…"
write_launcher "${INSTALL_DIR}/${APP_NAME}" "Pachul launcher" "app.py"
success "Launcher created."

# Tray launcher: persistent update-status icon, see tray.py
info "Creating tray launcher at ${INSTALL_DIR}/${APP_NAME}-tray…"
write_launcher "${INSTALL_DIR}/${APP_NAME}-tray" "Pachul tray launcher" "tray.py"
success "Tray launcher created."

# optional_install <source> <target> <mode> <start msg> <success msg> <skip msg>
# Copies a file that may be absent from a source checkout; absence is no error.
optional_install() {
    local source_file="$1" target="$2" mode="$3"
    if [[ -f "$source_file" ]]; then
        info "$4"
        install -D -m "$mode" "$source_file" "$target"
        success "$5"
    else
        info "$6"
    fi
}

# pachuli, the companion AUR helper: placed next to the launcher, so it is on
# PATH at once and Pachul prefers it over yay/paru. Optional, a checkout
# without pachuli.py (Pachul used with yay or paru) just skips it.
optional_install "${SRC_DIR}/pachuli.py" "${INSTALL_DIR}/pachuli" 755 \
    "Installing pachuli AUR helper to ${INSTALL_DIR}/pachuli…" \
    "pachuli installed — already on PATH via ${INSTALL_DIR}." \
    "No pachuli.py found next to install.sh — skipping (optional; Pachul falls back to yay/paru if installed)."

# The tray icon needs an AppIndicator library; only warn if it is missing
tray_lib_present=1
tray_hints=()
case "$DISTRO_FAMILY" in
    arch)
        pacman -Qi libayatana-appindicator &>/dev/null \
            || pacman -Qi libappindicator-gtk3 &>/dev/null \
            || tray_lib_present=0
        tray_hints=("libayatana-appindicator not found — the tray icon needs it to show up."
                    "Install with: sudo pacman -S libayatana-appindicator")
        ;;
    fedora)
        rpm -q libappindicator-gtk3 &>/dev/null || tray_lib_present=0
        tray_hints=("libappindicator-gtk3 not found — the tray icon needs it to show up."
                    "Install with: sudo dnf install libappindicator-gtk3")
        ;;
    debian)
        dpkg -s gir1.2-ayatanaappindicator3-0.1 &>/dev/null || tray_lib_present=0
        tray_hints=("libayatana-appindicator (GObject introspection bindings) not found — the tray icon needs it."
                    "Install with: sudo apt-get install gir1.2-ayatanaappindicator3-0.1")
        ;;
    suse)
        rpm -q typelib-1_0-AyatanaAppIndicator3-0_1 &>/dev/null || tray_lib_present=0
        tray_hints=("AyatanaAppIndicator3 typelib not found — the tray icon needs it to show up."
                    "Install with: sudo zypper install typelib-1_0-AyatanaAppIndicator3-0_1")
        ;;
esac
if (( ! tray_lib_present )); then
    for hint in "${tray_hints[@]}"; do
        warn "$hint"
    done
fi

# Tray autostart is not configured here: Pachul keeps its own per-user
# autostart entry (~/.config/autostart), switchable under Preferences →
# Tray Icon. That avoids another sudo prompt and any clash with a system-wide
# entry.
info "Tray icon autostart: enable it from Pachul's Preferences → Tray Icon."

# ══ 4. Menu entry ═════════════════════════════════════════════════════════════
info "Creating desktop entry…"
install -d "$DESKTOP_DIR"
printf '%s\n' \
    "[Desktop Entry]" \
    "Type=Application" \
    "Name=Pachul" \
    "GenericName=Package Manager" \
    "Comment=A powerful Pacman/AUR front end" \
    "Exec=${INSTALL_DIR}/${APP_NAME}" \
    "Icon=${ICON_ID}" \
    "Categories=System;PackageManager;" \
    "Keywords=pacman;aur;packages;arch;" \
    "Terminal=false" \
    "StartupWMClass=pachul" \
    > "$DESKTOP_FILE"
success "Desktop entry created."

# ══ 5. Icons ══════════════════════════════════════════════════════════════════
info "Installing icon…"
install -d "$ICON_DIR"
for rel in "${ICON_FILES[@]}"; do
    install -m 644 "${SRC_DIR}/${rel}" "${ICON_DIR}/${rel}"
done
gtk-update-icon-cache -f -t /usr/share/icons/hicolor &>/dev/null || true
success "Icon installed."

# Polkit policy: gives the native pkexec dialog a readable "Authentication
# required to manage packages with Pachul" text instead of Polkit's generic
# fallback that prints the raw command line (details and trade-offs in
# PKEXEC_MIGRATION.md). Optional — pkexec works without it, so a checkout
# lacking the file is fine.
optional_install "${SRC_DIR}/${ICON_ID}.policy" "${POLICY_DIR}/${ICON_ID}.policy" 644 \
    "Installing Polkit policy (nicer authentication dialog text)…" \
    "Polkit policy installed — no polkitd restart needed." \
    "No ${ICON_ID}.policy found next to install.sh — skipping (optional, app works fine without it)."

# ══ 6. Refresh the desktop database ═══════════════════════════════════════════
update-desktop-database "$DESKTOP_DIR" &>/dev/null || true

# ══ Summary ═══════════════════════════════════════════════════════════════════
printf '\n%b\n\n' "${GREEN}${BOLD}  Pachul installed successfully!${RESET}"
printf '%b\n' "  Installed modules  : ${BOLD}${DATA_DIR}/${RESET}"
printf '                       %s\n' "${PY_MODULES[@]}"
printf '\n%b\n' "  Run from terminal  : ${BOLD}pachul${RESET}"
printf '%b\n\n' "  Or launch from     : ${BOLD}Applications → System → Pachul${RESET}"
printf '%b\n' "  Tray update icon   : enable at login via Preferences → Tray Icon"
printf '%b\n\n' "  Run it right away  : ${BOLD}${APP_NAME}-tray &${RESET}"
if [[ -f "${INSTALL_DIR}/pachuli" ]]; then
    printf '%b\n\n' "  AUR helper         : ${BOLD}pachuli${RESET} (installed to ${INSTALL_DIR}, used automatically by Pachul)"
fi
