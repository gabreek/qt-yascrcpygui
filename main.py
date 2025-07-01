#!/usr/bin/env python3
# FILE: main.py
# PURPOSE: Ponto de entrada principal do aplicativo.
#          Verifica as dependências, inicializa a configuração e a janela principal.

import sys
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

    print("Before QApplication initialization")
    app = QApplication(sys.argv)
    print("After QApplication initialization")
    
    app_config = AppConfig(None) 
    print("AppConfig initialized")

    print("Before MainWindow initialization")
    main_window = MainWindow(app_config)
    print("After MainWindow initialization")
    
    print("Before main_window.show()")
    main_window.show()
    print("After main_window.show()")

    print("Before app.exec()")
    sys.exit(app.exec())
    print("After app.exec() (this should not print if app exits normally)")

if __name__ == "__main__":
    main()
