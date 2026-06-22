#!/usr/bin/env python3
# FILE: main.py
# PURPOSE: Ponto de entrada principal do aplicativo.
#          Verifica as dependências, inicializa a configuração e a janela principal.

import sys
import json
import multiprocessing
from PySide6.QtWidgets import QApplication
from utils.dependencies import check_dependencies
from app_config import AppConfig
from gui.main_window import MainWindow
from gui import themes
import web_server

def dump_theme_colors(app):
    from PySide6.QtGui import QPalette
    p = app.palette()
    roles = [
        ('Window', QPalette.ColorRole.Window),
        ('WindowText', QPalette.ColorRole.WindowText),
        ('Base', QPalette.ColorRole.Base),
        ('AlternateBase', QPalette.ColorRole.AlternateBase),
        ('Button', QPalette.ColorRole.Button),
        ('ButtonText', QPalette.ColorRole.ButtonText),
        ('Text', QPalette.ColorRole.Text),
        ('BrightText', QPalette.ColorRole.BrightText),
        ('Highlight', QPalette.ColorRole.Highlight),
        ('HighlightedText', QPalette.ColorRole.HighlightedText),
        ('Mid', QPalette.ColorRole.Mid),
        ('Midlight', QPalette.ColorRole.Midlight),
        ('Dark', QPalette.ColorRole.Dark),
        ('Shadow', QPalette.ColorRole.Shadow),
        ('Light', QPalette.ColorRole.Light),
        ('Link', QPalette.ColorRole.Link),
        ('LinkVisited', QPalette.ColorRole.LinkVisited),
        ('ToolTipBase', QPalette.ColorRole.ToolTipBase),
        ('ToolTipText', QPalette.ColorRole.ToolTipText),
    ]
    colors = {}
    for name, role in roles:
        c = p.color(role)
        colors[name] = {
            'hex': c.name(),
            'r': c.red(),
            'g': c.green(),
            'b': c.blue(),
            'h': c.hue(),
            's': c.saturation(),
            'v': c.value(),
        }
    window = p.color(QPalette.ColorRole.Window)
    is_dark = window.value() < 128
    derived = {
        'is_dark_theme': is_dark,
        'border_color': window.darker(140).name() if not is_dark else window.lighter(170).name(),
    }
    print("=== THEME COLORS DUMP ===")
    print(json.dumps({'palette': colors, 'derived': derived}, indent=2))
    print("=========================")

def main():
    """
    Função principal que inicia a aplicação.
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--theme', action='store_true', help='Dump current theme colors and exit')
    args, remaining = parser.parse_known_args()

    if args.theme:
        app = QApplication(remaining)
        dump_theme_colors(app)
        sys.exit(0)

    # Set process name to "yaScrcpy" instead of "main.py"
    try:
        import ctypes
        libc = ctypes.CDLL(ctypes.util.find_library('c'))
        PR_SET_NAME = 15
        libc.prctl(PR_SET_NAME, b"yaScrcpy", 0, 0, 0)
    except Exception:
        pass
    QApplication.setApplicationName("yaScrcpy")
    QApplication.setApplicationDisplayName("yaScrcpy")
    app = QApplication(remaining)

    if not check_dependencies():
        return



    app_config = AppConfig(None)
    
    # Apply the initial theme
    themes.apply_theme(app, app_config.get('theme', 'System'))

    main_window = MainWindow(app, app_config)

    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
