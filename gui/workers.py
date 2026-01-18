from PySide6.QtCore import QObject, Signal, QRunnable
from PySide6.QtGui import QPixmap
from utils import scrcpy_handler, icon_scraper, adb_handler
import re
import os
import time
from utils.isolated_extractor import extract_icon_in_process
from multiprocessing import Process, Queue
from PIL import Image

# --- Base Worker (for QRunnable) ---
class BaseRunnableWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)

class BaseRunnableWorker(QRunnable):
    def __init__(self):
        super().__init__()
        # Note: No QObject.__init__() here because QRunnable is not a QObject.
        # Signals will be on a separate QObject.

    def run(self):
        raise NotImplementedError("Subclasses must implement the 'run' method.")

# --- App Workers ---
class AppListWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(tuple)

class AppListWorker(QRunnable):
    def __init__(self, connection_id):
        super().__init__()
        self.connection_id = connection_id
        self.signals = AppListWorkerSignals()

    def run(self):
        try:
            user_apps, system_apps = scrcpy_handler.list_installed_apps(self.connection_id)
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

class ScrcpyLaunchWorkerSignals(QObject):
    scrcpy_process_started = Signal(object)
    finished = Signal()
    error = Signal(str)
    display_id_found = Signal(str, str, str)

class ScrcpyLaunchWorker(QRunnable):
    def __init__(self, config_values, window_title, connection_id, icon_path, session_type):
        super().__init__()
        self.signals = ScrcpyLaunchWorkerSignals()
        self.config_values = config_values
        self.window_title = window_title
        self.connection_id = connection_id
        self.icon_path = icon_path
        self.session_type = session_type

    def run(self):
        try:
            process = scrcpy_handler.launch_scrcpy(
                config_values=self.config_values, window_title=self.window_title,
                device_id=self.connection_id, icon_path=self.icon_path, session_type=self.session_type,
                capture_output=(self.session_type in ['winlator', 'app_alt_launch'])
            )

            scrcpy_handler.add_active_scrcpy_session(
                pid=process.pid,
                app_name=self.window_title,
                command_args=process.args,
                icon_path=self.icon_path,
                session_type=self.session_type
            )

            self.signals.scrcpy_process_started.emit(process)

            if self.session_type in ['winlator', 'app_alt_launch']:
                display_id = None
                for line in iter(process.stdout.readline, ''):
                    match = re.search(r'\[server\] INFO: New display: .*\(id=(\d+)\)', line)
                    if match:
                        display_id = match.group(1)
                        break

                if display_id:
                    if self.session_type == 'winlator':
                        shortcut_path = self.config_values.get('shortcut_path')
                        package_name = self.config_values.get('package_name')
                        self.signals.display_id_found.emit(display_id, shortcut_path, package_name)
                    elif self.session_type == 'app_alt_launch':
                        package_name = self.config_values.get('package_name_for_alt_launch')
                        self.signals.display_id_found.emit(display_id, None, package_name)
                else:
                    process.terminate()
                    raise RuntimeError("Could not find display ID in Scrcpy output.")

        except Exception as e:
            self.signals.error.emit(f"Failed to launch Scrcpy: {e}")
        finally:
            self.signals.finished.emit()

# --- Scrcpy Tab Workers ---
class DeviceInfoWorkerSignals(BaseRunnableWorkerSignals):
    result = Signal(dict)

class DeviceInfoWorker(BaseRunnableWorker):
    def __init__(self, connection_id):
        super().__init__()
        self.connection_id = connection_id
        self.signals = DeviceInfoWorkerSignals()

    def run(self):
        try:
            info = adb_handler.get_device_info(self.connection_id)
            if info:
                launcher = adb_handler.get_default_launcher(self.connection_id)
                info['default_launcher'] = launcher
                self.signals.result.emit(info)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class EncoderListWorkerSignals(BaseRunnableWorkerSignals):
    result = Signal(object)

class EncoderListWorker(BaseRunnableWorker):
    def __init__(self):
        super().__init__()
        self.signals = EncoderListWorkerSignals()

    def run(self):
        try:
            video_encoders, audio_encoders = scrcpy_handler.list_encoders()
            self.signals.result.emit((video_encoders, audio_encoders))
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

# --- Winlator Tab Workers ---
class GameListWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)

class GameListWorker(BaseRunnableWorker):
    def __init__(self, connection_id):
        super().__init__()
        self.connection_id = connection_id
        self.signals = GameListWorkerSignals()

    def run(self):
        try:
            shortcuts = adb_handler.list_winlator_shortcuts_with_names(self.connection_id)
            games_with_pkg = []
            for name, path in shortcuts:
                pkg = adb_handler.get_package_name_from_shortcut(path, self.connection_id)
                games_with_pkg.append({'name': name, 'path': path, 'pkg': pkg})
            self.signals.result.emit(games_with_pkg)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class IconExtractorWorkerSignals(QObject):
    icon_extracted = Signal(str, bool, QPixmap)
    finished = Signal()

class IconExtractorWorker(BaseRunnableWorker):
    def __init__(self, extraction_queue, app_config, temp_dir, placeholder_icon, connection_id):
        super().__init__()
        self.signals = IconExtractorWorkerSignals()
        self.extraction_queue = extraction_queue
        self.app_config = app_config
        self.temp_dir = temp_dir
        self.placeholder_icon = placeholder_icon
        self.connection_id = connection_id

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
                remote_exe_path = adb_handler.get_game_executable_info(path, self.connection_id)
                if remote_exe_path:
                    local_exe_path = os.path.join(self.temp_dir, f"{os.path.basename(remote_exe_path)}_{int(time.time()*1000)}")
                    adb_handler.pull_file(remote_exe_path, local_exe_path, self.connection_id)
                    if os.path.exists(local_exe_path):
                        result_queue = Queue()
                        process = Process(target=extract_icon_in_process, args=(local_exe_path, save_path, result_queue))
                        process.start()
                        process.join()

                        if not result_queue.empty():
                            result_success, result_data = result_queue.get()
                            if result_success:
                                img = Image.open(save_path).resize((48, 48), Image.LANCZOS)
                                pixmap = QPixmap.fromImage(img.toqimage())
                                success = True
            except Exception:
                pass
            finally:
                if local_exe_path and os.path.exists(local_exe_path):
                    os.remove(local_exe_path)
                self.app_config.save_app_metadata(path, {'exe_icon_fetch_failed': not success})
                self.signals.icon_extracted.emit(path, success, pixmap if pixmap else self.placeholder_icon)
                self.extraction_queue.task_done()
        self.signals.finished.emit()

class WinlatorLaunchWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)

class WinlatorLaunchWorker(BaseRunnableWorker):
    def __init__(self, shortcut_path, display_id, package_name, connection_id, windowing_mode):
        super().__init__()
        self.signals = WinlatorLaunchWorkerSignals()
        self.shortcut_path = shortcut_path
        self.display_id = display_id
        self.package_name = package_name
        self.connection_id = connection_id
        self.windowing_mode = windowing_mode

    def run(self):
        try:
            adb_handler.start_winlator_app(
                shortcut_path=self.shortcut_path,
                display_id=self.display_id,
                package_name=self.package_name,
                device_id=self.connection_id,
                windowing_mode=self.windowing_mode
            )
        except Exception as e:
            self.signals.error.emit(f"Failed to launch Winlator app: {e}")
        finally:
            self.signals.finished.emit()

class AppLaunchWorker(BaseRunnableWorker):
    def __init__(self, package_name, display_id, windowing_mode, connection_id):
        super().__init__()
        self.signals = BaseRunnableWorkerSignals()
        self.package_name = package_name
        self.display_id = display_id
        self.windowing_mode = windowing_mode
        self.connection_id = connection_id

    def run(self):
        try:
            adb_handler.start_app_on_display(
                package_name=self.package_name,
                display_id=self.display_id,
                windowing_mode=self.windowing_mode,
                device_id=self.connection_id
            )
        except Exception as e:
            self.signals.error.emit(f"Failed to launch app: {e}")
        finally:
            self.signals.finished.emit()


# --- Main Window Workers ---
class DeviceCheckWorkerSignals(QObject):
    finished = Signal()
    result = Signal(str)

class DeviceCheckWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = DeviceCheckWorkerSignals()

    def run(self):
        try:
            device_id = adb_handler.get_connected_device_id()
            self.signals.result.emit(device_id)
        except Exception:
            self.signals.result.emit(None)
        finally:
            self.signals.finished.emit()


class DeviceConfigLoaderWorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(dict)


class DeviceConfigLoaderWorker(QRunnable):
    def __init__(self, device_id, app_config):
        super().__init__()
        self.device_id = device_id
        self.app_config = app_config
        self.signals = DeviceConfigLoaderWorkerSignals()

    def run(self):
        try:
            connection_id = self.device_id
            configuration_id = self.device_id

            if ':' in connection_id:
                serial_no = adb_handler.get_serial_from_wifi_device(connection_id)
                if serial_no:
                    configuration_id = serial_no

            self.app_config.load_config_for_device(configuration_id)
            
            self.app_config.connection_id = connection_id
            
            device_info = adb_handler.get_device_info(connection_id)
            
            output = {
                "device_id": connection_id,
                "device_info": device_info,
            }
            self.signals.result.emit(output)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()
