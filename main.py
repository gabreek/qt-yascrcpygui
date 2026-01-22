#!/usr/bin/env python3
# FILE: main.py
# PURPOSE: Ponto de entrada principal do aplicativo.
#          Verifica as dependências, inicializa a configuração e a janela principal.

import sys
import multiprocessing
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal
from utils.dependencies import check_dependencies
from app_config import AppConfig
from gui.main_window import MainWindow
from gui import themes
import web_server

def main():
    """
    Função principal que inicia a aplicação.
    """
    if not check_dependencies():
        return

    app = QApplication(sys.argv)

    app_config = AppConfig(None)
    
    # Apply the initial theme
    themes.apply_theme(app, app_config.get('theme', 'System'))

    main_window = MainWindow(app, app_config)

    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
