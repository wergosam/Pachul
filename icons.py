"""
Pachul — icons.py
Inline SVG icon set for the whole app.

WHY THIS EXISTS: relying on icon *names* looked up through the system/GTK
icon theme means Pachul's appearance depends on whatever theme happens to
be active. On this machine that surfaced as:

    Gtk-WARNING **: Failed to load icon .../Breeze KDE-Story-Light/apps/22/
    utilities-terminal-symbolic.svg: Datei oder Verzeichnis nicht gefunden

The active theme's own icon index claimed to have that icon, pointing at a
file that doesn't actually exist (a broken/incomplete third-party theme).
Because GTK resolves the icon *name* against the currently active theme
first and only falls through to another theme (e.g. the hicolor fallback
theme, or another entry in a Gio.ThemedIcon fallback list) when the name
is entirely *absent* from that theme's index — not when the name exists
but its file is missing/broken — simply registering extra fallback icon
files doesn't reliably fix this specific failure mode: the active theme
already "claims" the name, so GTK never gets to our fallback for it.

The only fix that's actually guaranteed regardless of any of that is to
stop resolving these icons by name through the icon theme at all. Every
icon Pachul uses is defined here as raw SVG markup and rendered directly
to a texture ourselves — the system/KDE icon theme is never consulted for
any of these, so a broken or incomplete theme simply can't affect Pachul,
no matter what's wrong with it.

All shapes use "currentColor" for fill/stroke; since we render outside of
GTK's own symbolic-icon recolor pipeline, we substitute this ourselves
with a color matched to the current light/dark style (see _icon_color()),
so icons still look correct in both.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Adw, Gdk, GdkPixbuf, GLib, Gio

from functools import lru_cache

# ─── Icon definitions ─────────────────────────────────────────────────────────

ICON_SVGS = {
    "dialog-password-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="3" y="6" width="10" height="7" rx="1" fill="currentColor"/>
        <rect x="5" y="3" width="6" height="4" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="8" cy="9" r="1.5" fill="currentColor"/>
        <line x1="8" y1="9" x2="8" y2="11" stroke="currentColor" stroke-width="1.5"/>
    </svg>""",

    "utilities-terminal-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="1.5" y="2.5" width="13" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.3"/>
        <path d="M4 6.2 L6.6 8 L4 9.8" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="7.6" y1="9.8" x2="11.2" y2="9.8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </svg>""",

    "package-x-generic-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M8 1.2 L14 4.3 V11.7 L8 14.8 L2 11.7 V4.3 Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
        <path d="M2 4.3 L8 7.4 L14 4.3 M8 7.4 V14.8" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
    </svg>""",

    "folder-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2 4.2 C2 3.5 2.5 3 3.2 3 H6.3 L7.6 4.4 H12.8 C13.5 4.4 14 4.9 14 5.6 V11.4 C14 12.1 13.5 12.6 12.8 12.6 H3.2 C2.5 12.6 2 12.1 2 11.4 Z" fill="currentColor"/>
    </svg>""",

    "folder-open-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2 4.6 C2 3.9 2.5 3.4 3.2 3.4 H6.2 L7.5 4.7 H12.4 C13 4.7 13.5 5.2 13.4 5.8 L13 5.8 H4.6 C4 5.8 3.5 6.2 3.3 6.8 L1.8 11.2 C1.6 11.7 2 12.2 2.5 12.2 H11.6 C12.1 12.2 12.6 11.8 12.8 11.3 L14.1 7.4 C14.3 6.9 13.9 6.4 13.4 6.4" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
    </svg>""",

    "folder-visiting-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2 4.2 C2 3.5 2.5 3 3.2 3 H6.3 L7.6 4.4 H12.8 C13.5 4.4 14 4.9 14 5.6 V11.4 C14 12.1 13.5 12.6 12.8 12.6 H3.2 C2.5 12.6 2 12.1 2 11.4 Z" fill="currentColor" opacity="0.55"/>
        <path d="M5.5 9.5 L8 7 L10.5 9.5 M8 7 V12" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "folder-download-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2 4.2 C2 3.5 2.5 3 3.2 3 H6.3 L7.6 4.4 H12.8 C13.5 4.4 14 4.9 14 5.6 V11.4 C14 12.1 13.5 12.6 12.8 12.6 H3.2 C2.5 12.6 2 12.1 2 11.4 Z" fill="currentColor" opacity="0.55"/>
        <path d="M8 6 V10.5 M5.8 8.5 L8 10.7 L10.2 8.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "user-trash-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M3.5 4.5 H12.5 M6 4.5 V3 C6 2.6 6.3 2.3 6.7 2.3 H9.3 C9.7 2.3 10 2.6 10 3 V4.5 M4.3 4.5 L4.9 12.6 C4.95 13.2 5.4 13.7 6 13.7 H10 C10.6 13.7 11.05 13.2 11.1 12.6 L11.7 4.5" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="6.7" y1="6.8" x2="6.9" y2="11.4" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
        <line x1="9.3" y1="6.8" x2="9.1" y2="11.4" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
    </svg>""",

    "system-search-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="6.8" cy="6.8" r="4" fill="none" stroke="currentColor" stroke-width="1.3"/>
        <line x1="9.7" y1="9.7" x2="13.3" y2="13.3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
    </svg>""",

    "view-refresh-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M3 6.5 C3.6 4.3 5.6 2.7 8 2.7 C10.9 2.7 13.3 5.1 13.3 8 C13.3 10.9 10.9 13.3 8 13.3 C5.6 13.3 3.6 11.7 3 9.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <path d="M3 3.3 V6.7 H6.4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "system-software-update-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M3 6 C3.6 3.8 5.6 2.2 8 2.2 C10.9 2.2 13.2 4.5 13.2 7.3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <path d="M13.2 2.2 V6 H9.4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M13 10 C12.4 12.2 10.4 13.8 8 13.8 C5.1 13.8 2.8 11.5 2.8 8.7" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <path d="M2.8 13.8 V10 H6.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "software-update-available-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M8 4.8 V9.2 M5.9 7.2 L8 9.3 L10.1 7.2" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="5.5" y1="11.4" x2="10.5" y2="11.4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>""",

    "preferences-system-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="2.3" fill="none" stroke="currentColor" stroke-width="1.3"/>
        <path d="M8 1.8 V3.3 M8 12.7 V14.2 M14.2 8 H12.7 M3.3 8 H1.8 M12.3 3.7 L11.2 4.8 M4.8 11.2 L3.7 12.3 M12.3 12.3 L11.2 11.2 M4.8 4.8 L3.7 3.7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </svg>""",

    "preferences-system-details-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="6.5" cy="6.5" r="2" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M6.5 1.6 V2.7 M6.5 10.3 V11.4 M11.4 6.5 H10.3 M2.7 6.5 H1.6 M9.7 3.3 L8.9 4.1 M4.1 8.9 L3.3 9.7 M9.7 9.7 L8.9 8.9 M4.1 4.1 L3.3 3.3" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
        <circle cx="11.5" cy="11.5" r="2.7" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <line x1="11.5" y1="10.1" x2="11.5" y2="10.4" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
        <line x1="11.5" y1="11.9" x2="11.5" y2="12.9" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
    </svg>""",

    "preferences-system-network-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="5.5" r="2.2" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4 14 C4 11.2 5.8 9.6 8 9.6 C10.2 9.6 12 11.2 12 14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <path d="M1.6 8 C1.6 8 2.6 6.5 2.6 5.5 C2.6 4.5 1.6 3 1.6 3 M14.4 8 C14.4 8 13.4 6.5 13.4 5.5 C13.4 4.5 14.4 3 14.4 3" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
    </svg>""",

    "network-wireless-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2.3 6.3 C5.6 3 10.4 3 13.7 6.3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <path d="M4.6 8.6 C6.5 6.7 9.5 6.7 11.4 8.6" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <path d="M6.7 10.9 C7.4 10.2 8.6 10.2 9.3 10.9" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <circle cx="8" cy="13" r="1" fill="currentColor"/>
    </svg>""",

    "network-offline-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2.3 6.3 C5.6 3 10.4 3 13.7 6.3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.4"/>
        <path d="M4.6 8.6 C6.5 6.7 9.5 6.7 11.4 8.6" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.4"/>
        <circle cx="8" cy="13" r="1" fill="currentColor" opacity="0.4"/>
        <line x1="2" y1="2" x2="14" y2="14" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
    </svg>""",

    "network-wired-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="5.5" y="2" width="5" height="4.5" rx="0.6" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <line x1="6.3" y1="6.5" x2="6.3" y2="8" stroke="currentColor" stroke-width="1.1"/>
        <line x1="7.3" y1="6.5" x2="7.3" y2="9" stroke="currentColor" stroke-width="1.1"/>
        <line x1="8.7" y1="6.5" x2="8.7" y2="9" stroke="currentColor" stroke-width="1.1"/>
        <line x1="9.7" y1="6.5" x2="9.7" y2="8" stroke="currentColor" stroke-width="1.1"/>
        <path d="M4.5 14 V11.5 C4.5 10.9 5 10.4 5.6 10.4 H10.4 C11 10.4 11.5 10.9 11.5 11.5 V14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>""",

    "network-server-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="2" y="2.3" width="12" height="4.2" rx="0.7" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <rect x="2" y="9.5" width="12" height="4.2" rx="0.7" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="4.2" cy="4.4" r="0.6" fill="currentColor"/>
        <circle cx="4.2" cy="11.6" r="0.6" fill="currentColor"/>
    </svg>""",

    "network-transmit-receive-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M5 2.5 V9 M2.8 4.5 L5 2.3 L7.2 4.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M11 13.5 V7 M8.8 11.5 L11 13.7 L13.2 11.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "network-workgroup-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="3.3" r="1.6" fill="none" stroke="currentColor" stroke-width="1.1"/>
        <circle cx="3.3" cy="11.7" r="1.6" fill="none" stroke="currentColor" stroke-width="1.1"/>
        <circle cx="12.7" cy="11.7" r="1.6" fill="none" stroke="currentColor" stroke-width="1.1"/>
        <path d="M8 4.9 V7 M8 7 L4.4 10.4 M8 7 L11.6 10.4" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
    </svg>""",

    "drive-harddisk-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="1.5" y="4.5" width="13" height="7" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="11.2" cy="8" r="1" fill="currentColor"/>
        <line x1="3" y1="8" x2="8.5" y2="8" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
    </svg>""",

    "video-display-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="1.5" y="2.5" width="13" height="8.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <line x1="5.5" y1="13.5" x2="10.5" y2="13.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="8" y1="11" x2="8" y2="13.5" stroke="currentColor" stroke-width="1.2"/>
    </svg>""",

    "audio-card-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="1.5" y="4" width="13" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="5" cy="8" r="1.3" fill="none" stroke="currentColor" stroke-width="1"/>
        <line x1="9" y1="6.2" x2="12.5" y2="6.2" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
        <line x1="9" y1="8" x2="12.5" y2="8" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
        <line x1="9" y1="9.8" x2="12.5" y2="9.8" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
    </svg>""",

    "audio-speakers-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M2 6 H4.3 L7.5 3.2 V12.8 L4.3 10 H2 Z" fill="currentColor"/>
        <path d="M9.5 5.7 C10.6 6.6 10.6 9.4 9.5 10.3" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <path d="M11.2 4 C13.2 5.8 13.2 10.2 11.2 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>""",

    "applications-multimedia-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M6.6 5.3 L11 8 L6.6 10.7 Z" fill="currentColor"/>
    </svg>""",

    "applications-graphics-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="1.5" y="2.5" width="13" height="11" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="5.3" cy="6" r="1.2" fill="currentColor"/>
        <path d="M2 11.5 L6 8 L9 10.5 L11.5 8 L14.2 10.8" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>""",

    "applications-engineering-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="3.1" fill="none" stroke="currentColor" stroke-width="1.3"/>
        <g stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
            <line x1="8" y1="2.2" x2="8" y2="3.6"/>
            <line x1="8" y1="12.4" x2="8" y2="13.8"/>
            <line x1="2.2" y1="8" x2="3.6" y2="8"/>
            <line x1="12.4" y1="8" x2="13.8" y2="8"/>
            <line x1="4.1" y1="4.1" x2="5.1" y2="5.1"/>
            <line x1="10.9" y1="10.9" x2="11.9" y2="11.9"/>
            <line x1="11.9" y1="4.1" x2="10.9" y2="5.1"/>
            <line x1="5.1" y1="10.9" x2="4.1" y2="11.9"/>
        </g>
    </svg>""",

    "text-editor-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M3 13 L3.5 10.6 L10.3 3.8 C10.7 3.4 11.4 3.4 11.8 3.8 L12.2 4.2 C12.6 4.6 12.6 5.3 12.2 5.7 L5.4 12.5 Z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
        <line x1="9.2" y1="4.9" x2="11.1" y2="6.8" stroke="currentColor" stroke-width="1.1"/>
    </svg>""",

    "text-x-script-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M4 1.6 H9.2 L12.5 4.9 V14.4 H4 Z" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/>
        <path d="M9.2 1.6 V4.9 H12.5" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/>
        <path d="M6.2 9 L4.9 10.5 L6.2 12" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M9.5 9 L10.8 10.5 L9.5 12" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "web-browser-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <ellipse cx="8" cy="8" rx="2.6" ry="6.3" fill="none" stroke="currentColor" stroke-width="1.1"/>
        <line x1="1.9" y1="8" x2="14.1" y2="8" stroke="currentColor" stroke-width="1.1"/>
        <path d="M2.7 5 H13.3 M2.7 11 H13.3" fill="none" stroke="currentColor" stroke-width="1"/>
    </svg>""",

    "avatar-default-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="5.3" r="2.6" fill="currentColor"/>
        <path d="M2.5 14 C2.5 10.8 4.9 9 8 9 C11.1 9 13.5 10.8 13.5 14" fill="currentColor"/>
    </svg>""",

    "dialog-information-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="8" cy="5.2" r="0.9" fill="currentColor"/>
        <line x1="8" y1="7.3" x2="8" y2="11.3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </svg>""",

    "dialog-warning-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M8 1.8 L14.5 13.2 H1.5 Z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
        <line x1="8" y1="6" x2="8" y2="9.6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <circle cx="8" cy="11.3" r="0.9" fill="currentColor"/>
    </svg>""",

    "document-open-recent-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M4 1.6 H9.2 L12.5 4.9 V14.4 H4 Z" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/>
        <path d="M9.2 1.6 V4.9 H12.5" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/>
        <circle cx="8" cy="10" r="2.6" fill="none" stroke="currentColor" stroke-width="1"/>
        <path d="M8 8.6 V10 L9 10.8" fill="none" stroke="currentColor" stroke-width="0.9" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "document-revert-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M9.5 3 C12 3.5 13.8 5.7 13.8 8.3 C13.8 11.3 11.3 13.8 8.3 13.8 C5.3 13.8 2.8 11.3 2.8 8.3 C2.8 6.2 4 4.4 5.7 3.5" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <path d="M9.7 1.3 L9.7 4.7 L6.3 3.9 Z" fill="currentColor"/>
    </svg>""",

    "edit-clear-all-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="4" y="6.3" width="8.5" height="5.2" rx="0.7" fill="none" stroke="currentColor" stroke-width="1.2" transform="rotate(-20 8 9)"/>
        <line x1="2.3" y1="4" x2="13.7" y2="4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>""",

    "edit-select-all-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="2" y="2" width="12" height="12" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2.4 1.6"/>
    </svg>""",

    "selection-mode-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="2.2" y="2.2" width="6" height="6" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <rect x="9.5" y="2.2" width="4.3" height="4.3" rx="0.8" fill="currentColor" opacity="0.35"/>
        <path d="M4 5.4 L5 6.4 L6.8 4" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/>
        <rect x="2.2" y="9.5" width="4.3" height="4.3" rx="0.8" fill="currentColor" opacity="0.35"/>
        <rect x="9.5" y="9.5" width="4.3" height="4.3" rx="0.8" fill="currentColor" opacity="0.35"/>
    </svg>""",

    "object-select-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="2" y="2" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4.7 8.2 L7 10.5 L11.3 5.8" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "list-add-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <line x1="8" y1="2.5" x2="8" y2="13.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        <line x1="2.5" y1="8" x2="13.5" y2="8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
    </svg>""",

    "go-down-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M4 6 L8 10.5 L12 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "view-reveal-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M1.5 8 C3.3 5 5.5 3.6 8 3.6 C10.5 3.6 12.7 5 14.5 8 C12.7 11 10.5 12.4 8 12.4 C5.5 12.4 3.3 11 1.5 8 Z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
        <circle cx="8" cy="8" r="2" fill="currentColor"/>
    </svg>""",

    "starred-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M8 1.8 L9.9 5.8 L14.2 6.4 L11.1 9.4 L11.9 13.7 L8 11.6 L4.1 13.7 L4.9 9.4 L1.8 6.4 L6.1 5.8 Z" fill="currentColor"/>
    </svg>""",

    "emblem-favorite-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M8 13.5 C8 13.5 2 9.8 2 5.8 C2 3.9 3.4 2.6 5.1 2.6 C6.3 2.6 7.4 3.3 8 4.3 C8.6 3.3 9.7 2.6 10.9 2.6 C12.6 2.6 14 3.9 14 5.8 C14 9.8 8 13.5 8 13.5 Z" fill="currentColor"/>
    </svg>""",

    "emblem-ok-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <circle cx="8" cy="8" r="6.3" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4.9 8.2 L7 10.4 L11.1 5.9" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "adw-external-link-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <path d="M6.5 2.5 H3.3 C2.6 2.5 2 3.1 2 3.8 V12.2 C2 12.9 2.6 13.5 3.3 13.5 H11.7 C12.4 13.5 13 12.9 13 12.2 V9" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M9 2.5 H13.5 V7 M13.3 2.7 L7.3 8.7" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "open-menu-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <line x1="2.5" y1="4.5" x2="13.5" y2="4.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <line x1="2.5" y1="8" x2="13.5" y2="8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        <line x1="2.5" y1="11.5" x2="13.5" y2="11.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
    </svg>""",

    "utilities-system-monitor-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="1.5" y="2.5" width="13" height="9" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M3.3 9.3 L5.5 5.8 L7.3 8 L9.2 4.3 L11 7.3 L12.7 5.5" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="5.5" y1="14" x2="10.5" y2="14" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        <line x1="8" y1="11.5" x2="8" y2="14" stroke="currentColor" stroke-width="1.2"/>
    </svg>""",

    "application-x-executable-symbolic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
        <rect x="2" y="3" width="12" height="10" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.2"/>
        <path d="M4.3 6 L6.5 8 L4.3 10" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="7.5" y1="10" x2="10.5" y2="10" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
    </svg>""",
}


# ─── Rendering ────────────────────────────────────────────────────────────────

def _icon_color():
    """Approximates Adwaita's default foreground color for the current
    light/dark style. Doesn't track live theme switches automatically —
    icons created before a light/dark toggle keep their old color until
    recreated, which is a minor cosmetic tradeoff for not depending on the
    system icon theme at all."""
    try:
        dark = Adw.StyleManager.get_default().get_dark()
    except Exception:
        dark = False
    return "#eeeeec" if dark else "#2e3436"


@lru_cache(maxsize=512)
def _texture_for(name, size, color):
    svg = ICON_SVGS.get(name)
    if svg is None:
        return None
    data = svg.replace("currentColor", color).encode("utf-8")
    try:
        loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
        loader.set_size(size, size)
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
        if pixbuf is None:
            return None
        return Gdk.Texture.new_for_pixbuf(pixbuf)
    except GLib.Error:
        return None


def get_icon_texture(name, size=18):
    """Gdk.Texture for one of our inline icons, or None if `name` isn't in
    ICON_SVGS (caller should fall back to the system icon theme in that
    case — this should be rare, since every icon Pachul actually uses is
    meant to be covered here)."""
    return _texture_for(name, size, _icon_color())


def themed_image(icon_names, size=18):
    """Drop-in replacement for building a Gtk.Image from an icon name (or a
    list of fallback names, kept for compatibility with existing call
    sites) — renders our own inline SVG instead of looking the name up in
    the system icon theme. Falls back to the old system-theme lookup only
    if none of the given names are in our inline set."""
    if isinstance(icon_names, str):
        icon_names = [icon_names]
    for name in icon_names:
        tex = get_icon_texture(name, size)
        if tex is not None:
            img = Gtk.Image.new_from_paintable(tex)
            img.set_pixel_size(size)
            return img
    gicon = Gio.ThemedIcon.new_from_names(list(icon_names))
    img = Gtk.Image.new_from_gicon(gicon)
    img.set_pixel_size(size)
    return img


def themed_paintable(icon_name, size=36):
    """For widgets that take a Gdk.Paintable directly (e.g.
    Adw.StatusPage.set_paintable()) rather than a Gtk.Image."""
    tex = get_icon_texture(icon_name, size)
    if tex is not None:
        return tex
    display = Gdk.Display.get_default()
    theme = Gtk.IconTheme.get_for_display(display) if display else None
    if theme is None:
        return None
    return theme.lookup_icon(icon_name, None, size, 1, Gtk.TextDirection.NONE, 0)
