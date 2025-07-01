#!/usr/bin/env python3
# FILE: main.py
# PURPOSE: Ponto de entrada principal do aplicativo.
#          Verifica as dependências, inicializa a configuração e a janela principal.

import sys
import multiprocessing
from PySide6.QtWidgets import QApplication
from utils.dependencies import check_dependencies
from utils import adb_handler
from app_config import AppConfig
from gui.main_window import MainWindow



def main():
    """
    Função principal que inicia a aplicação.
    """
    if not check_dependencies():
        return

    app = QApplication(sys.argv)
    print("QApplication initialization")

    app_config = AppConfig(None)
    print("AppConfig initialized")

    main_window = MainWindow(app_config)
    print("MainWindow initialization")

    main_window.show()
    print("Main_window.show()")

    print("app.exec()")
    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
