#!/usr/bin/env python3
# FILE: utils/dependencies.py
# PURPOSE: Verifica a existência das dependências externas do aplicativo.

import shutil
from PySide6.QtWidgets import QMessageBox
from app_config import AppConfig

def check_dependencies():
    app_config = AppConfig(None)

    if not shutil.which("adb"):
        QMessageBox.critical(
            None,
            app_config.tr('common', 'error'),
            app_config.tr('common', 'adb_missing')
        )
        return False
    if not shutil.which("scrcpy"):
        QMessageBox.critical(
            None,
            app_config.tr('common', 'error'),
            app_config.tr('common', 'scrcpy_missing')
        )
        return False
    return True
