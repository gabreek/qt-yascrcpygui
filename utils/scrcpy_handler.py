# FILE: utils/scrcpy_handler.py
# PURPOSE: Centraliza todos os comandos que interagem com o scrcpy.

import subprocess
import shlex
import psutil
import os
import re
import threading
import time # Added for delays in output parsing
import utils.adb_handler # Explicit import for clarity

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


def _build_command(config_values, extra_scrcpy_args=None, window_title=None, device_id=None, force_no_start_app=False):
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
    if config_values.get('allow_frame_drop') == 'Enabled':
        video_codec_options.append('allow-frame-drop=1')
    elif config_values.get('allow_frame_drop') == 'Disabled':
        video_codec_options.append('allow-frame-drop=0')

    if config_values.get('low_latency') == 'Enabled':
        video_codec_options.append('low-latency:int=1')
    elif config_values.get('low_latency') == 'Disabled':
        video_codec_options.append('low-latency:int=0')

    if config_values.get('priority_mode') == 'Realtime':
        video_codec_options.append('priority:int=0')
    elif config_values.get('priority_mode') == 'Normal':
        video_codec_options.append('priority:int=1')

    bitrate_mode_val = config_values.get('bitrate_mode', '').lower().strip()
    if bitrate_mode_val in ['constant', 'cbr']:
        video_codec_options.append('bitrate-mode:int=1')
    elif bitrate_mode_val in ['variable', 'vbr']:
        video_codec_options.append('bitrate-mode:int=2')

    if config_values.get('color_range') == 'Full':
        video_codec_options.append('color-range:int=1')
    elif config_values.get('color_range') == 'Limited':
        video_codec_options.append('color-range:int=2')

    iframe_interval = config_values.get('iframe_interval')
    if iframe_interval is not None and int(iframe_interval) > 0:
        video_codec_options.append(f'iframe-interval={int(iframe_interval)}')

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
        'audio_bitrate_slider': '--audio-bit-rate',
        'audio_buffer': '--audio-buffer',
        'video_buffer': '--video-buffer',
    }
    for key, arg_name in map_args.items():
        val = config_values.get(key)
        if val and str(val) not in ('Auto', 'None', '0', 'disabled', ''):
            suffix = 'K' if key == 'video_bitrate_slider' else ''
            cmd.append(f"{arg_name}={val}{suffix}")

    # Handle start_app separately to avoid adding it to map_args
    # If force_no_start_app is True, then we explicitly do NOT add --start-app
    start_app_val = config_values.get('start_app')
    if not force_no_start_app and start_app_val and start_app_val not in ('launcher_shortcut', 'None'):
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

def _parse_scrcpy_output_for_display_id(scrcpy_process, timeout=20):
    """
    Reads scrcpy output to find the virtual display ID.
    Returns the display ID as a string, or None if not found within the timeout.
    """
    start_time = time.monotonic()
    display_id_pattern = re.compile(r"\[server\] INFO: New display: .*\(id=(\d+)\)")

    for line in iter(scrcpy_process.stdout.readline, ''):
        if not line:
            if scrcpy_process.poll() is not None:
                break
            time.sleep(0.1)
            continue

        print(f"Scrcpy stdout (alt launch): {line.strip()}")

        match = display_id_pattern.search(line)
        if match:
            return match.group(1)

        if time.monotonic() - start_time > timeout:
            print("Timeout while waiting for display ID from scrcpy for alternate launch.")
            break

    return None

def _alternate_launch_background_task(scrcpy_process, device_id, config_values, windowing_mode, session_type, startupinfo, original_post_cmds):
    """
    Background task to monitor scrcpy output for display ID and then launch the app via ADB.
    This also handles the remaining scrcpy process lifecycle.
    """
    display_id = None
    try:
        display_id = _parse_scrcpy_output_for_display_id(scrcpy_process)
        if display_id is None:
            print("Error: Could not find virtual display ID from scrcpy output for alternate launch. App will not be launched.")
            scrcpy_process.terminate()
            return

        if session_type in ['app', 'app_alt_launch']:
            target_app_id = config_values.get('start_app') or config_values.get('package_name_for_alt_launch')
            if target_app_id:
                utils.adb_handler.start_app_on_display(target_app_id, display_id, windowing_mode, device_id)
                print(f"Launched app '{target_app_id}' on display {display_id} via ADB.")
            else:
                print("Error: No application package name provided for alternate launch.")
        
        elif session_type == 'winlator':
            shortcut_path = config_values.get('shortcut_path')
            package_name = config_values.get('package_name_for_alt_launch')
            if shortcut_path and package_name:
                utils.adb_handler.start_winlator_app(shortcut_path, display_id, package_name, device_id, windowing_mode)
                print(f"Launched Winlator app '{shortcut_path}' on display {display_id} via ADB.")
            else:
                print("Error: Missing shortcut_path or package_name for Winlator alternate launch.")

    except Exception as e:
        print(f"Error in alternate launch background task: {e}")
    finally:
        # Continue consuming stdout to prevent blocking the pipe for the scrcpy process
        if scrcpy_process.stdout:
            try:
                for line in scrcpy_process.stdout:
                    # Log this output for debugging, it's not normal Scrcpy output
                    print(f"Scrcpy stdout (remainder): {line.strip()}")
            except (IOError, ValueError): # Occurs if stream is closed unexpectedly
                pass
        
    # Wait for scrcpy process to finish (and run POST commands if any)
    _wait_for_scrcpy_and_post_cmds(scrcpy_process, original_post_cmds, startupinfo)


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

def launch_scrcpy(config_values, capture_output=False, window_title=None, device_id=None, icon_path=None, session_type='app', perform_alternate_app_launch=False):
    """
    Inicia o scrcpy com base na configuração fornecida, lidando com comandos PRE e POST.
    Se `perform_alternate_app_launch` for True, Scrcpy será iniciado sem --start-app,
    e o aplicativo será lançado posteriormente via ADB após a detecção do display virtual.
    """
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

    # Determine if --start-app should be suppressed for alternate launch
    force_no_start_app = perform_alternate_app_launch
    
    # Construir e executar o comando scrcpy
    cmd = _build_command(config_values, parsed_args['scrcpy'], window_title, device_id, force_no_start_app=force_no_start_app)
    
    env = os.environ.copy()
    if icon_path and os.path.exists(icon_path):
        env['SCRCPY_ICON_PATH'] = icon_path

    # Apply environment variables from extraargs
    for var_name, var_value in parsed_args['env_vars'].items():
        env[var_name] = var_value

    # Always capture output if alternate app launch is requested or explicitly asked for
    actual_capture_output = capture_output or perform_alternate_app_launch

    if actual_capture_output:
        scrcpy_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, env=env)
    else:
        scrcpy_process = subprocess.Popen(cmd, startupinfo=startupinfo, env=env)

    # If alternate app launch is requested, start a background task to handle it
    if perform_alternate_app_launch:
        windowing_mode_str = config_values.get('windowing_mode', 'Fullscreen')
        windowing_mode_int = 1 if windowing_mode_str == 'Fullscreen' else 2 # Default to Fullscreen for windowingMode

        alt_launch_thread = threading.Thread(
            target=_alternate_launch_background_task,
            args=(scrcpy_process, device_id, config_values, windowing_mode_int, session_type, startupinfo, parsed_args['append'])
        )
        alt_launch_thread.daemon = True
        alt_launch_thread.start()
    else:
        # Normal POST command waiting
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

            match = re.match(r"(.+?)\s{2,}([a-zA-Z0-9_.-]+(?:\\.[a-zA-Z0-9_.-]+)*)$", content)
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
            vm = re.match(r"--video-codec=(\w+)\s+--video-encoder='?([\w.-]+)'?\s+\((\w+)\)(?:\s+\[\w+\])?", line)
            if vm:
                codec, encoder, mode = vm.groups()
                video_encoders.setdefault(codec, [])
                if (encoder, mode) not in video_encoders[codec]:
                    video_encoders[codec].append((encoder, mode))
            am = re.match(r"--audio-codec=(\w+)\s+--audio-encoder='?([\w.-]+)'?\s+\((\w+)\)", line)
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