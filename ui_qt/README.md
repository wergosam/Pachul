# Pachul – Qt-Look-Prototyp

Design-System im Adwaita-Look auf Basis von Qt6 (Fusion + eigene Palette),
unabhängig vom Desktop. Noch **keine** Paketverwaltung – nur das Aussehen.

## Starten

    # Arch/Manjaro:  sudo pacman -S pyside6      (oder: pip install PySide6)
    python3 -m ui_qt.demo                    # folgt dem System (hell/dunkel)
    python3 -m ui_qt.demo --mode dark
    python3 -m ui_qt.demo --accent system    # Plasma-Akzentfarbe statt Adwaita-Blau

Der Sonne/Mond-Knopf in der Kopfleiste schaltet Hell/Dunkel um; im Hauptmenü (Hamburger) unter „Erscheinungsbild“ gibt es zusätzlich „Wie das System“ und den Akzent
(live). Dialoge: „Werkzeuge“, „Einstellungen“, Terminal (über Werkzeuge →
„Lokales Paket installieren“).

## Aufbau

| Datei | Inhalt |
|---|---|
| `qt.py` | Ein Import-Punkt für PySide6 (bevorzugt) oder PyQt6 |
| `theme.py` | Farb-Tokens (hell/dunkel), QPalette, QSS, Live-Umschaltung, Akzent |
| `widgets.py` | Group/Row/SwitchRow/ComboRow/ExpanderRow, Card, Pill, NavRow, StatCard, Banner, Toast, HeaderBar, StatusPage, Dialog … |
| `icons_qt.py`, `icon_data.py` | die eingebetteten SVG-Icons, farbig und HiDPI-scharf |
| `demo.py` | Hauptfenster mit Fake-Daten (Delegate-basierte Paketliste) |

Regel: Aussehen kommt aus `theme.T` zur Zeichenzeit, nicht aus Stylesheets –
QSS gibt es nur für Standard-Widgets (Buttons, Eingabefelder, Scrollbars, Menüs).
