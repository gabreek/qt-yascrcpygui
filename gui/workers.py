# FILE: gui/workers.py
# PURPOSE: Centraliza todas as classes QRunnable e QObject workers para o aplicativo.

from PySide6.QtCore import QObject, Signal, QRunnable
from PySide6.QtGui import QPixmap
from utils import scrcpy_handler, icon_scraper, adb_handler
import re
import os
import time
import shlex
import subprocess
from PIL import Image
import sys

# --- Base Worker (for QRunnable) ---
class BaseRunnableWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)

class BaseRunnableWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = BaseRunnableWorkerSignals()

    def run(self):
        raise NotImplementedError("Subclasses must implement the 'run' method.")

# --- App Workers ---
class AppListWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(tuple)

class AppListWorker(QRunnable):
    def __init__(self, device_id):
        super().__init__()
        self.device_id = device_id
        self.signals = AppListWorkerSignals()

    def run(self):
        try:
            user_apps, system_apps = scrcpy_handler.list_installed_apps(self.device_id)
            self.signals.result.emit((user_apps, system_apps))
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class IconWorkerSignals(QObject):
    finished = Signal(str, QPixmap)
    error = Signal(str, str)

class IconWorker(QRunnable):
    def __init__(self, pkg_name, app_name, cache_dir, app_config):
        super().__init__()
        self.pkg_name = pkg_name
        self.app_name = app_name
        self.cache_dir = cache_dir
        self.app_config = app_config
        self.signals = IconWorkerSignals()

    def run(self):
        try:
            icon_path = icon_scraper.get_icon(self.app_name, self.pkg_name, self.cache_dir, self.app_config)
            if icon_path:
                self.signals.finished.emit(self.pkg_name, QPixmap(icon_path))
        except Exception as e:
            self.signals.error.emit(self.pkg_name, str(e))

class ScrcpyLaunchWorker(QObject):
    scrcpy_process_started = Signal(object)
    finished = Signal()
    error = Signal(str)
    display_id_found = Signal(str, str, str)

    def __init__(self, config_values, window_title, device_id, icon_path, session_type):
        super().__init__()
        self.config_values = config_values
        self.window_title = window_title
        self.device_id = device_id
        self.icon_path = icon_path
        self.session_type = session_type

    def run(self):
        try:
            process = scrcpy_handler.launch_scrcpy(
                config_values=self.config_values, window_title=self.window_title,
                device_id=self.device_id, icon_path=self.icon_path, session_type=self.session_type,
                capture_output=(self.session_type == 'winlator')
            )

            self.scrcpy_process_started.emit(process)

            if self.session_type == 'winlator':
                display_id = None
                for line in process.stdout:
                    print(line, end='')
                    match = re.search(r'\[server\] INFO: New display: .*\(id=(\d+)\)', line)
                    if match:
                        display_id = match.group(1)
                        print(f"DEBUG: ScrcpyLaunchWorker extracted display_id: {display_id}")
                        break

                if display_id:
                    self.display_id_found.emit(display_id, self.config_values.get('shortcut_path'), self.config_values.get('package_name'))
                else:
                    process.terminate()
                    raise RuntimeError("Could not find display ID in Scrcpy output.")

        except Exception as e:
            self.error.emit(f"Failed to launch Scrcpy: {e}")
        finally:
            self.finished.emit()

# --- Scrcpy Tab Workers ---
class DeviceInfoWorker(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(dict)

    def __init__(self, device_id):
        super().__init__()
        self.device_id = device_id

    def run(self):
        try:
            info = adb_handler.get_device_info(self.device_id)
            self.result.emit(info)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

class EncoderListWorker(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            video_encoders, audio_encoders = scrcpy_handler.list_encoders()
            self.result.emit((video_encoders, audio_encoders))
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

# --- Winlator Tab Workers ---
class GameListWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            games = adb_handler.list_winlator_shortcuts_with_names()
            self.finished.emit(games)
        except Exception as e:
            self.error.emit(str(e))

class IconExtractorWorker(QObject):
    icon_extracted = Signal(str, bool, QPixmap)
    finished = Signal()

    def __init__(self, extraction_queue, app_config, temp_dir, placeholder_icon):
        super().__init__()
        self.extraction_queue = extraction_queue
        self.app_config = app_config
        self.temp_dir = temp_dir
        self.placeholder_icon = placeholder_icon

    def run(self):
        while True:
            task = self.extraction_queue.get()
            if task is None:
                self.extraction_queue.task_done()
                break

            path, item_widget, save_path = task
            success = False
            pixmap = None
            local_exe_path = None

            try:
                remote_exe_path = adb_handler.get_game_executable_info(path)
                if remote_exe_path:
                    local_exe_path = os.path.join(self.temp_dir, f"{os.path.basename(remote_exe_path)}_{int(time.time()*1000)}")
                    adb_handler.pull_file(remote_exe_path, local_exe_path)
                    if os.path.exists(local_exe_path):
                        extractor_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'utils', 'isolated_extractor.py')
                        python_executable = os.path.join(os.path.dirname(sys.executable), 'python3')
                        cmd = [python_executable, extractor_script_path, local_exe_path, save_path]
                        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
                        if process.returncode == 0 and os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                            img = Image.open(save_path).resize((48, 48), Image.LANCZOS)
                            pixmap = QPixmap.fromImage(img.toqimage())
                            success = True
            except Exception as e:
                print(f"Error in IconExtractorWorker for {item_widget.item_name}: {e}")
            finally:
                if local_exe_path and os.path.exists(local_exe_path):
                    os.remove(local_exe_path)
                self.app_config.save_app_metadata(path, {'exe_icon_fetch_failed': not success})
                self.icon_extracted.emit(path, success, pixmap if pixmap else self.placeholder_icon)
                self.extraction_queue.task_done()
        self.finished.emit()

class QueueJoinWorker(QRunnable):
    finished = Signal()

    def __init__(self, queue_instance):
        super().__init__()
        self.queue_instance = queue_instance
        self.signals = BaseRunnableWorkerSignals()

    def run(self):
        self.queue_instance.join()
        self.signals.finished.emit()

class WinlatorLaunchWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, shortcut_path, display_id, package_name, device_id):
        super().__init__()
        self.shortcut_path = shortcut_path
        self.display_id = display_id
        self.package_name = package_name
        self.device_id = device_id

    def run(self):
        try:
            adb_handler.start_winlator_app(
                shortcut_path=self.shortcut_path,
                display_id=self.display_id,
                package_name=self.package_name,
                device_id=self.device_id
            )
        except Exception as e:
            self.error.emit(f"Failed to launch Winlator app: {e}")
        finally:
            self.finished.emit()

# --- Main Window Workers ---
class DeviceCheckWorker(QObject):
    finished = Signal()
    result = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            device_id = adb_handler.get_connected_device_id()
            self.result.emit(device_id)
        except Exception as e:
            print(f"Error checking device connection: {e}")
            self.result.emit(None)
        finally:
            self.finished.emit()