#!/usr/bin/env python3
# FILE: utils/dependencies.py
# PURPOSE: Verifica a existência das dependências externas do aplicativo.

import shutil
import os
import sys
from PySide6.QtWidgets import QMessageBox
from app_config import AppConfig

def find_binary(name):
    """Finds a binary in the system PATH or common locations."""
    path = shutil.which(name)
    if path:
        return path
    
    # Common locations on Linux
    extra_paths = [
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        os.path.expanduser("~/platform-tools"),
        os.path.expanduser("~/.local/bin"),
    ]
    
    for p in extra_paths:
        full_path = os.path.join(p, name)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            # Add to PATH so subsequent subprocess calls find it
            os.environ["PATH"] += os.pathsep + p
            return full_path
            
    return None

def check_dependencies():
    app_config = AppConfig(None)

    if not find_binary("adb"):
        QMessageBox.critical(
            None,
            app_config.tr('common', 'error'),
            app_config.tr('common', 'adb_missing')
        )
        return False
    if not find_binary("scrcpy"):
        QMessageBox.critical(
            None,
            app_config.tr('common', 'error'),
            app_config.tr('common', 'scrcpy_missing')
        )
        return False
    return True
