# FILE: utils/adb_handler.py
# PURPOSE: Centraliza todos os comandos que interagem com o Android Debug Bridge (adb).

import subprocess
import shlex
import re
import os
import time

def _get_startupinfo():
    """Returns a startupinfo object for subprocesses on Windows to suppress console window."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None

def _run_adb_command(command, device_id=None, print_command=False, ignore_errors=False, timeout=5):
    """Helper para executar um comando adb, retornando a saída decodificada."""
    base_cmd = ['adb']
    if device_id:
        base_cmd.extend(['-s', device_id])

    full_cmd = base_cmd + command

    if print_command:
        print('Executing ADB Command:', shlex.join(full_cmd))

    startupinfo = _get_startupinfo()

    try:
        result = subprocess.check_output(full_cmd, text=True, stderr=subprocess.PIPE, startupinfo=startupinfo, timeout=timeout)
        return result.strip()
    except FileNotFoundError:
        if not ignore_errors:
            print(f"Error: ADB command '{full_cmd[0]}' not found. Please ensure ADB is in your system's PATH.")
        return ""
    except subprocess.CalledProcessError:
        return ""
    except subprocess.TimeoutExpired:
        print(f"Warning: ADB command '{shlex.join(full_cmd)}' timed out after {timeout} seconds.")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred while executing ADB command '{shlex.join(full_cmd)}': {e}")
        return ""

def get_device_info(device_id=None):
    """Obtém o nome do modelo e o nível da bateria do dispositivo."""
    if not device_id: return None
    name = _run_adb_command(['shell', 'getprop', 'ro.product.vendor.marketname'], device_id)
    if not name:
        return None

    battery_output = _run_adb_command(['shell', 'dumpsys', 'battery'], device_id, ignore_errors=True)
    level_match = re.search(r'level: (\d+)', battery_output)
    battery_level = level_match.group(1) if level_match else "?"

    return {"commercial_name": name, "battery": battery_level}

def list_winlator_shortcuts_with_names(device_id=None):
    """Retorna uma lista de tuplas (nome, caminho) para os atalhos do Winlator."""
    paths_to_search = [
        '/storage/emulated/0/Download/Winlator/Frontend/',
        '/storage/emulated/0/winlator/Shortcuts/'
    ]
    all_shortcuts = []
    for search_path in paths_to_search:
        command = ['shell', 'find', search_path, '-type', 'f', '-name', '*.desktop']
        output = _run_adb_command(command, device_id, ignore_errors=True)
        if output:
            all_shortcuts.extend(output.splitlines())

    games_with_names = []
    # Use a set to avoid duplicates if a shortcut exists in both locations
    for path in sorted(list(set(all_shortcuts))):
        if path:
            basename = os.path.basename(path)
            name = basename.rsplit('.desktop', 1)[0]
            games_with_names.append((name, path))
    return games_with_names

def get_package_name_from_shortcut(shortcut_path, device_id=None):
    """Lê o arquivo .desktop para extrair o nome do pacote da linha 'Exec='."""
    content = _run_adb_command(['shell', 'cat', shlex.quote(shortcut_path)], device_id)
    if not content:
        return "unknown"

    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith('exec='):
            match = re.search(r'/0/([^/]+)/files/', line)
            if match:
                return match.group(1)
    return "unknown"

def get_game_executable_info(shortcut_path, device_id=None):
    """Lê o arquivo .desktop para encontrar o caminho do .exe no /sdcard."""
    content = _run_adb_command(['shell', 'cat', shlex.quote(shortcut_path)], device_id)
    if not content:
        return None

    game_dir_part = None
    exe_name = None
    exec_path = None

    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith('path='):
            match = re.search(r'dosdevices/d:([^"\\]+)', line, re.IGNORECASE)
            if match:
                game_dir_part = match.group(1).strip()
        elif line.lower().startswith('startupwmclass='):
            exe_name = line.split('=', 1)[1].strip()
        elif line.lower().startswith('exec='):
            # Capture anything inside wine "..."
            match = re.search(r'wine\s+"([^"]+)"', line, re.IGNORECASE)
            if match:
                exec_path = match.group(1).strip()

    # Prioritize Path and StartupWMClass
    if game_dir_part and exe_name:
        full_path_on_sdcard = f"/storage/emulated/0/Download{game_dir_part}/{exe_name}"
        return full_path_on_sdcard.replace('\\', '/')
    elif exec_path:
        # Handle the /home/xuser/.wine/dosdevices/d: case
        if exec_path.lower().startswith('/home/xuser/.wine/dosdevices/d:'):
            full_path_on_sdcard = exec_path.replace('/home/xuser/.wine/dosdevices/d:', '/storage/emulated/0/Download')
            return full_path_on_sdcard.replace('\\', '/')
        # Handle other potential paths if necessary, or return as is if it's a direct path
        # For now, assume it's a direct path if not the specific wine path
        return exec_path.replace('\\', '/')

    return None

def pull_file(remote_path, local_path, device_id=None, timeout=30):
    """Baixa um arquivo do dispositivo para o computador local de forma síncrona."""
    cmd = ['adb']
    if device_id:
        cmd.extend(['-s', device_id])
    cmd.extend(['pull', remote_path, local_path])

    try:
        startupinfo = _get_startupinfo()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', startupinfo=startupinfo)
        stdout, stderr = process.communicate(timeout=timeout) # Add timeout here
        if process.returncode != 0:
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"Warning: ADB pull command '{shlex.join(cmd)}' timed out after {timeout} seconds. Terminating process.")
        process.kill()
        return False
    except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
        print(f"An error occurred during ADB pull command '{shlex.join(cmd)}': {e}")
        return False

def start_winlator_app(shortcut_path, display_id, package_name, device_id=None, windowing_mode=1):
    """Inicia um aplicativo Winlator em um display virtual específico."""
    quoted_path = shlex.quote(shortcut_path)
    activity_name = ".XServerDisplayActivity"
    component = f"{package_name}/{activity_name}"
    remote_command_str = (
        f"am start --display {display_id} "
        f"-n {component} "
        f"--es shortcut_path {quoted_path} "
        f"--activity-clear-task --activity-clear-top --activity-no-history --windowingMode {windowing_mode}"
    )
    command = ['shell', remote_command_str]
    _run_adb_command(command, device_id, print_command=True)

def _get_launcher_activity(package_name, device_id=None):
    """Resolves the main launcher activity for a given package."""
    command = [
        'shell', 'cmd', 'package', 'resolve-activity', '--brief',
        '-a', 'android.intent.action.MAIN',
        '-c', 'android.intent.category.LAUNCHER',
        package_name
    ]
    output = _run_adb_command(command, device_id, ignore_errors=True)
    if output:
        # The output is typically the last line and looks like: com.package/.Activity
        # Or it might have other lines, so we find the one with the package name.
        for line in reversed(output.splitlines()):
            if package_name in line and '/' in line:
                return line.strip()
    return None

def start_app_on_display(package_name, display_id, windowing_mode, device_id=None):
    """Inicia um aplicativo Android em um display virtual específico."""
    component = _get_launcher_activity(package_name, device_id)
    if not component:
        # Error should be handled by the caller
        return

    remote_command_str = (
        f"am start --display {display_id} "
        f"-n {shlex.quote(component)} "
        f"--activity-clear-task --activity-clear-top --activity-no-history --windowingMode {windowing_mode}"
    )
    command = ['shell', remote_command_str]
    _run_adb_command(command, device_id, print_command=True)


def connect_wifi(address):
    """Connects to a device via Wi-Fi."""
    return _run_adb_command(['connect', address], print_command=True, timeout=10)

def disconnect_wifi(address):
    """Disconnects from a Wi-Fi device."""
    return _run_adb_command(['disconnect', address], print_command=True)

def get_device_ip(device_id):
    """Gets the IP address of the device from wlan0 interface."""
    output = _run_adb_command(['shell', 'ip', 'addr', 'show', 'wlan0'], device_id=device_id, ignore_errors=True)
    if output:
        match = re.search(r'inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/', output)
        if match:
            return match.group(1)
    return None

def get_serial_from_wifi_device(device_id):
    """Gets the ro.serialno property from a device connected via Wi-Fi."""
    if not device_id or ':' not in device_id:
        return None
    return _run_adb_command(['shell', 'getprop', 'ro.serialno'], device_id=device_id, ignore_errors=True)

def get_connected_device_id():
    """Retorna o ID do primeiro dispositivo ADB conectado que está online."""
    try:
        output = _run_adb_command(['devices'], ignore_errors=True)
        lines = output.strip().split('\n')
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) == 2:
                    device_id = parts[0].strip()
                    state = parts[1].strip()
                    if device_id and state == 'device': # Only return 'device' state, ignore 'offline', 'unauthorized', etc.
                        return device_id
        return None
    except Exception:
        return None

def get_default_launcher(device_id=None):
    """Obtém o pacote do launcher padrão do Android."""
    command = [
        'shell',
        'cmd', 'package', 'resolve-activity', '--brief',
        '-a', 'android.intent.action.MAIN',
        '-c', 'android.intent.category.HOME'
    ]
    output = _run_adb_command(command, device_id, ignore_errors=True)
    if not output:
        return None

    # A saída pode ter várias linhas, a que nos interessa contém o '/'
    for line in output.splitlines():
        if '/' in line:
            # A linha é algo como: "com.mi.android.globallauncher/.MiuiHomeActivity"
            # Nós só queremos a primeira parte.
            return line.split('/')[0].strip()

    return None # Retorna None se nenhuma linha com o nome do componente for encontrada

def get_device_lock_state(device_id=None):
    """
    Determines the lock state of the device.
    Returns: 'LOCKED_SCREEN_OFF', 'LOCKED_SCREEN_ON', or 'UNLOCKED'.
    """
    # Check if the screen is interactive
    interactive_output = _run_adb_command(['shell', 'dumpsys', 'input_method'], device_id, ignore_errors=True)
    is_interactive = 'mInteractive=true' in interactive_output

    if not is_interactive:
        return 'LOCKED_SCREEN_OFF'

    # If interactive, check the current focused window
    focused_window_output = _run_adb_command(['shell', 'dumpsys', 'window'], device_id, ignore_errors=True)
    if 'mCurrentFocus' in focused_window_output:
        focused_line = [line for line in focused_window_output.splitlines() if 'mCurrentFocus' in line]
        if focused_line and ('Keyguard' in focused_line[0] or 'NotificationShade' in focused_line[0]):
            return 'LOCKED_SCREEN_ON'

    return 'UNLOCKED'

def unlock_device(device_id, pin):
    """
    Attempts to unlock the device by sending power, swipe, and PIN commands.
    """
    lock_state = get_device_lock_state(device_id)

    if lock_state == 'UNLOCKED':
        print("Device is already unlocked.")
        return

    if lock_state == 'LOCKED_SCREEN_OFF':
        # Send POWER keyevent to wake up the screen
        _run_adb_command(['shell', 'input', 'keyevent', '26'], device_id)
        # Add a small delay to allow the screen to turn on
        time.sleep(0.5)

    # Swipe up to dismiss the lock screen
    _run_adb_command(['shell', 'input', 'swipe', '500', '1500', '500', '500'], device_id)
    time.sleep(0.5)

    # Input the PIN
    _run_adb_command(['shell', 'input', 'text', shlex.quote(pin)], device_id)
    time.sleep(0.5)

    # Press Enter to confirm the PIN
    _run_adb_command(['shell', 'input', 'keyevent', '66'], device_id)
