# FILE: utils/scrcpy_handler.py
# PURPOSE: Centraliza todos os comandos que interagem com o scrcpy.

import subprocess
import shlex
import psutil
import os
import re
import threading

def _get_startupinfo():
    """Returns a startupinfo object for subprocesses on Windows to suppress console window."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None

def _parse_extra_args(extra_args_str):
    """Analisa a string de argumentos extras para separar comandos PRE, POST, variáveis de ambiente e argumentos do scrcpy."""
    prepend_cmds = []
    append_cmds = []
    scrcpy_args = []
    env_vars = {}

    for command in extra_args_str.strip().split(';'):
        command = command.strip()
        if not command:
            continue
        if command.upper().startswith('PRE::'):
            cmd_content = command[5:].strip()
            # Check for environment variable export
            env_match = re.match(r'^export\s+([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$', cmd_content)
            if env_match:
                var_name = env_match.group(1)
                var_value = env_match.group(2)
                env_vars[var_name] = var_value
            else:
                prepend_cmds.append(cmd_content)
        elif command.upper().startswith('POST::'):
            append_cmds.append(command[6:].strip())
        else:
            scrcpy_args.extend(shlex.split(command))

    return {'prepend': prepend_cmds, 'append': append_cmds, 'scrcpy': scrcpy_args, 'env_vars': env_vars}


def _build_command(config_values, extra_scrcpy_args=None, window_title=None, device_id=None):
    """Constrói a lista de argumentos para o comando scrcpy."""
    cmd = ['scrcpy']
    if device_id:
        cmd.extend(['-s', device_id])

    # Sanitize device_id for window title if it's an IP address
    title_device_part = device_id.replace(':', ' ') if device_id else 'Android Device'
    title = window_title or config_values.get('start_app_name') or title_device_part
    if title and title != 'None':
        cmd.append(f"--window-title={title}")

    if config_values.get('turn_screen_off'): cmd.append('--turn-screen-off')
    if config_values.get('fullscreen'): cmd.append('--fullscreen')
    if config_values.get('mipmaps'): cmd.append('--no-mipmaps')
    if config_values.get('stay_awake'): cmd.append('--stay-awake')
    if config_values.get('no_audio'): cmd.append('--no-audio')
    if config_values.get('no_video'): cmd.append('--no-video')

    video_codec_options = []
    if config_values.get('allow_frame_drop') == 'enabled':
        video_codec_options.append('allow-frame-drop=1')
    elif config_values.get('allow_frame_drop') == 'disabled':
        video_codec_options.append('allow-frame-drop=0')

    if config_values.get('low_latency') == 'enabled':
        video_codec_options.append('low-latency:int=1')
    elif config_values.get('low_latency') == 'disabled':
        video_codec_options.append('low-latency:int=0')

    if config_values.get('priority_mode') == 'realtime':
        video_codec_options.append('priority:int=0')
    elif config_values.get('priority_mode') == 'normal':
        video_codec_options.append('priority:int=1')

    if config_values.get('bitrate_mode').lower().strip() == 'cbr':
        video_codec_options.append('bitrate-mode:int=1')
    elif config_values.get('bitrate_mode').lower().strip() == 'vbr':
        video_codec_options.append('bitrate-mode:int=2')

    if video_codec_options:
        cmd.append(f"--video-codec-options={','.join(video_codec_options)}")

    map_args = {
        'mouse_mode': '--mouse',
        'gamepad_mode': '--gamepad',
        'keyboard_mode': '--keyboard',
        'mouse_bind': '--mouse-bind',
        'render_driver': '--render-driver',
        'max_fps': '--max-fps',
        'video_bitrate_slider': '--video-bit-rate',
        'audio_buffer': '--audio-buffer',
        'video_buffer': '--video-buffer',
    }
    for key, arg_name in map_args.items():
        val = config_values.get(key)
        if val and str(val) not in ('Auto', 'None', '0', 'disabled', ''):
            suffix = 'K' if key == 'video_bitrate_slider' else ''
            cmd.append(f"{arg_name}={val}{suffix}")

    # Handle start_app separately to avoid adding it to map_args
    start_app_val = config_values.get('start_app')
    if start_app_val and start_app_val not in ('launcher_shortcut', 'None'):
        cmd.append(f"--start-app={start_app_val}")

    if config_values.get('video_codec') != 'Auto':
        codec_val = config_values.get('video_codec')
        encoder_val = config_values.get('video_encoder')
        if codec_val and encoder_val and encoder_val != 'Auto':
            codec = codec_val.split(' - ')[-1]
            encoder = encoder_val.split()[0]
            cmd.append(f"--video-codec={codec}")
            cmd.append(f"--video-encoder={encoder}")

    if config_values.get('audio_codec') != 'Auto':
        codec_val = config_values.get('audio_codec')
        encoder_val = config_values.get('audio_encoder')
        if codec_val and encoder_val and encoder_val != 'Auto':
            codec = codec_val.split(' - ')[-1]
            encoder = encoder_val.split()[0]
            cmd.append(f"--audio-codec={codec}")
            cmd.append(f"--audio-encoder={encoder}")

    new_display_val = config_values.get('new_display')
    if new_display_val and new_display_val != 'Disabled':
        cmd.append(f"--new-display={new_display_val}")
    else:
        max_size_val = str(config_values.get('max_size', '0'))
        if max_size_val != '0':
            cmd.append(f"--max-size={max_size_val}")

    if extra_scrcpy_args:
        cmd.extend(extra_scrcpy_args)

    return cmd

def _wait_for_scrcpy_and_post_cmds(scrcpy_process, post_cmds, startupinfo):
    """Waits for the scrcpy process to finish and then runs POST commands."""
    scrcpy_process.wait()

    # Clean up the session from the active list once it has ended
    remove_active_scrcpy_session(scrcpy_process.pid)

    for post_cmd_str in post_cmds:
        try:
            post_cmd = shlex.split(post_cmd_str)
            subprocess.run(post_cmd, check=True, startupinfo=startupinfo)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass # Errors are not critical here

def _run_adb_home_command(device_id, startupinfo):
    """Sends a 'HOME' key event via ADB."""
    try:
        home_cmd = ['adb']
        if device_id:
            home_cmd.extend(['-s', device_id])
        home_cmd.extend(['shell', 'input', 'keyevent', 'KEYCODE_HOME'])
        subprocess.run(home_cmd, check=True, startupinfo=startupinfo)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass # Not critical if it fails

def launch_scrcpy(config_values, capture_output=False, window_title=None, device_id=None, icon_path=None, session_type='app'):
    """Inicia o scrcpy com base na configuração fornecida, lidando com comandos PRE e POST."""
    extra_args_str = config_values.get('extraargs', '')
    parsed_args = _parse_extra_args(extra_args_str)

    startupinfo = _get_startupinfo()

    # Special handling for launcher shortcut
    if config_values.get('start_app') == 'launcher_shortcut':
        # Run this in a separate thread to not block scrcpy launch
        threading.Thread(target=_run_adb_home_command, args=(device_id, startupinfo)).start()

    # Executar comandos PRE
    for pre_cmd_str in parsed_args['prepend']:
        try:
            pre_cmd = shlex.split(pre_cmd_str)
            subprocess.run(pre_cmd, check=True, startupinfo=startupinfo)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass # Not critical

    # Construir e executar o comando scrcpy
    cmd = _build_command(config_values, parsed_args['scrcpy'], window_title, device_id)
    
    env = os.environ.copy()
    if icon_path and os.path.exists(icon_path):
        env['SCRCPY_ICON_PATH'] = icon_path

    # Apply environment variables from extraargs
    for var_name, var_value in parsed_args['env_vars'].items():
        env[var_name] = var_value

    if capture_output:
        scrcpy_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, env=env)
    else:
        scrcpy_process = subprocess.Popen(cmd, startupinfo=startupinfo, env=env)

    # Wait for the process and run POST commands in a separate thread
    wait_thread = threading.Thread(
        target=_wait_for_scrcpy_and_post_cmds,
        args=(scrcpy_process, parsed_args['append'], startupinfo)
    )
    wait_thread.daemon = True # Allows main program to exit even if this thread is running
    wait_thread.start()

    return scrcpy_process

def list_installed_apps(device_id=None):
    """Lista os apps, separando entre usuário e sistema, usando o comando scrcpy."""
    cmd = ['scrcpy', '--list-apps']
    if device_id:
        cmd.extend(['-s', device_id])

    try:
        startupinfo = _get_startupinfo()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', startupinfo=startupinfo)

        user_apps = {}
        system_apps = {}
        output_lines = []

        for line in process.stdout:
            output_lines.append(line)
            line = line.strip()
            if not line or line[0] not in ('-', '*'):
                continue

            app_type = line[0]
            content = line[1:].strip()

            match = re.match(r"(.+?)\s{2,}([a-zA-Z0-9_.-]+(?:\.[a-zA-Z0-9_.-]+)*)$", content)
            if match:
                name, pkg = match.groups()
                if app_type == '-':
                    user_apps[name.strip()] = pkg.strip()
                elif app_type == '*':
                    system_apps[name.strip()] = pkg.strip()

        process.wait()

        if process.returncode != 0:
            full_output = "".join(output_lines)
            raise RuntimeError(f"Scrcpy command failed with exit code {process.returncode}: {full_output.strip()}")

        return (user_apps, system_apps)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise RuntimeError(f"Could not list apps via scrcpy: {e}")

def list_encoders(device_id=None):
    cmd = ['scrcpy', '--list-encoders']
    if device_id:
        cmd.extend(['-s', device_id])

    try:
        startupinfo = _get_startupinfo()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', startupinfo=startupinfo)

        output_lines = []
        for line in process.stdout:
            output_lines.append(line)

        output = "".join(output_lines)
        video_encoders = {}
        audio_encoders = {}
        for line in output.splitlines():
            line = line.strip()
            if "(alias for" in line: continue
            vm = re.match(r"--video-codec=(\w+)\s+--video-encoder='?([\w\.-]+)'?\s+\((hw|sw)\)", line)
            if vm:
                codec, encoder, mode = vm.groups()
                video_encoders.setdefault(codec, [])
                if (encoder, mode) not in video_encoders[codec]:
                    video_encoders[codec].append((encoder, mode))
            am = re.match(r"--audio-codec=(\w+)\s+--audio-encoder='?([\w\.-]+)'?\s+\((hw|sw)\)", line)
            if am:
                codec, encoder, mode = am.groups()
                audio_encoders.setdefault(codec, [])
                if (encoder, mode) not in audio_encoders[codec]:
                    audio_encoders[codec].append((encoder, mode))
        return video_encoders, audio_encoders
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise RuntimeError(f"Could not list encoders via scrcpy: {e}")

# Global list to store active scrcpy session information
_active_scrcpy_sessions_data = []

def add_active_scrcpy_session(pid, app_name, command_args, icon_path, session_type):
    """Adds a new active scrcpy session to the global list."""
    session_info = {
        'pid': pid,
        'app_name': app_name,
        'command_args': command_args,
        'icon_path': icon_path,
        'session_type': session_type
    }
    _active_scrcpy_sessions_data.append(session_info)

def remove_active_scrcpy_session(pid):
    """Removes an active scrcpy session from the global list by PID."""
    global _active_scrcpy_sessions_data
    _active_scrcpy_sessions_data = [s for s in _active_scrcpy_sessions_data if s['pid'] != pid]

def get_active_scrcpy_sessions():
    """
    Lists active scrcpy sessions from the globally stored list.
    Verifies if the processes are still running.
    """
    sessions = []
    pids_to_remove = []

    for session_info in _active_scrcpy_sessions_data:
        pid = session_info['pid']
        try:
            proc = psutil.Process(pid)
            # Basic check to ensure it's still a scrcpy-like process
            # This is a sanity check, as we assume it was a scrcpy process when added
            if 'scrcpy' in proc.name().lower() or \
               (proc.cmdline() and 'scrcpy-server' in ' '.join(proc.cmdline()).lower()):
                sessions.append(session_info)
            else:
                pids_to_remove.append(pid) # Process changed its nature or was misidentified
        except psutil.NoSuchProcess:
            pids_to_remove.append(pid) # Process no longer exists

    # Clean up dead processes from the global list
    for pid in pids_to_remove:
        remove_active_scrcpy_session(pid)

    return sessions

def kill_scrcpy_session(pid):
    """
    Terminates a scrcpy process given its PID.
    Returns True if successful, False otherwise.
    """
    try:
        process = psutil.Process(pid)
        process.terminate()  # or process.kill()
        process.wait(timeout=3) # Wait for process to terminate
        remove_active_scrcpy_session(pid) # Remove from global list
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    except psutil.TimeoutExpired:
        # If terminate didn't work, try kill
        try:
            process.kill()
            process.wait(timeout=3)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

def list_displays(device_id=None):

    """Lista os displays disponíveis usando scrcpy."""
    cmd = ['scrcpy', '--list-displays']
    if device_id:
        cmd.extend(['-s', device_id])

    try:
        startupinfo = _get_startupinfo()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', startupinfo=startupinfo)

        output_lines = []
        for line in process.stdout:
            output_lines.append(line)

        output = "".join(output_lines)
        displays = []
        for line in output.splitlines():
            match = re.match(r"--display=(\d+)\s+\(size=(\d+x\d+)\)", line)
            if match:
                display_id, size = match.groups()
                displays.append({'id': int(display_id), 'size': size})
        return displays
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
