Release 2.3.0

New features
- Repair System dialogs for all four distro families (pacman, apt/dpkg,
  dnf/rpm, zypper/rpm): maintenance, read-only diagnostics, force-remove
- Check Certificates: CA trust store refresh, domain expiry check,
  expired local certificates
- Services & Security: failed systemd services, firewall (UFW, firewalld),
  fail2ban/AppArmor status, SSH root login check
- Find Broken Symlinks: scan only, or scan and remove safe ones
- Clean Cache: new "System Cleanup" section (journal, thumbnails, trash)
- Startup health check (optional): read-only checks after launch,
  results list with one-click access to the matching tool
- "More Update Sources" dialog: ~29 additional tools (rustup, cargo, pip,
  npm, fwupd, ...) chained into the system update
- pachuli integrated as preferred AUR helper (pkexec via -g)
- Update list shows installed -> new version; version numbers for
  non-installed AUR packages (AUR metadata dump with daily cache)
- Version picker: install one of the last 5 versions of a package
- Hold dialog links to the ignored-packages overview

Improvements
- Uniform button font size, smaller header menu labels
- Icons now follow the real foreground colour and update live on
  light/dark switch
- Detail panel hidden until a package is selected
- New translations (DE/FR/IT) for all added strings

Fixes
- Icons nearly invisible on light background (English UI)
- Crash on "&" in titles of Adw rows (markup not escaped)
- "Deselect all" left Uninstall button active; selection counter
  mismatch for Flatpak/Snap
- "Hold selection" ignored the ticked checkbox
- pacman -Qkk parsing broke on localized output (now LC_ALL=C)
- fwupdmgr exit code 2 no longer reported as an error
- pacman installs now use -Sy (stale local database)
- pachuli -S no longer performs a full system upgrade
- False positives in startup check (pacman -Dk, openssl -checkend)
