# FILE: utils/scrcpy_handler.py
# PURPOSE: Centraliza todos os comandos que interagem com o scrcpy.

import subprocess
import shlex
import psutil
import os
import json
import re

def _get_startupinfo():
    """Returns a startupinfo object for subprocesses on Windows to suppress console window."""
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None

def _build_command(config_values, window_title=None, device_id=None):
    """Constrói a lista de argumentos para o comando scrcpy."""
    cmd = ['scrcpy']
    if device_id:
        cmd.extend(['-s', device_id])

    title = window_title or config_values.get('start_app_name') or 'Android Device'
    if title and title != 'None':
        cmd.append(f"--window-title={title}")

    if config_values.get('turn_screen_off'): cmd.append('--turn-screen-off')
    if config_values.get('fullscreen'): cmd.append('--fullscreen')
    if config_values.get('mipmaps'): cmd.append('--no-mipmaps')
    if config_values.get('stay_awake'): cmd.append('--stay-awake')
    if config_values.get('no_audio'): cmd.append('--no-audio')
    if config_values.get('no_video'): cmd.append('--no-video')

    map_args = {
        'start_app': '--start-app',
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
        max_size_val = config_values.get('max_size')
        if max_size_val and max_size_val != '0':
            cmd.append(f"--max-size={max_size_val}")

    extra = config_values.get('extraargs', '').strip()
    if extra:
        cmd.extend(shlex.split(extra))

    return cmd

def launch_scrcpy(config_values, capture_output=False, window_title=None, device_id=None, icon_path=None, session_type='app'):
    """Inicia o scrcpy com base na configuração fornecida."""
    cmd = _build_command(config_values, window_title, device_id)
    print('Executing Scrcpy Command:', ' '.join(cmd))

    env = os.environ.copy()
    if icon_path and os.path.exists(icon_path):
        env['SCRCPY_ICON_PATH'] = icon_path

    startupinfo = _get_startupinfo()

    if capture_output:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo, env=env)
    else:
        process = subprocess.Popen(cmd, startupinfo=startupinfo, env=env)

    return process

def list_installed_apps(device_id=None):
    """Lista os apps, separando entre usuário e sistema, usando o comando scrcpy."""
    cmd = ['scrcpy', '--list-apps']
    if device_id:
        cmd.extend(['-s', device_id])

    try:
        startupinfo = _get_startupinfo()

        print(f"Executing: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', startupinfo=startupinfo)

        user_apps = {}
        system_apps = {}
        output_lines = []

        for line in process.stdout:
            print(line, end='')
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

        total_apps = len(user_apps) + len(system_apps)
        print(f"Found {total_apps} apps ({len(user_apps)} user, {len(system_apps)} system).")

        return (user_apps, system_apps)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise RuntimeError(f"Could not list apps via scrcpy: {e}")

def list_encoders(device_id=None):
    cmd = ['scrcpy', '--list-encoders']
    if device_id:
        cmd.extend(['-s', device_id])

    try:
        startupinfo = _get_startupinfo()

        print(f"Executing: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', startupinfo=startupinfo)

        output_lines = []
        for line in process.stdout:
            print(line, end='')
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

def list_displays(device_id=None):
    """Lista os displays disponíveis usando scrcpy."""
    cmd = ['scrcpy', '--list-displays']
    if device_id:
        cmd.extend(['-s', device_id])

    try:
        startupinfo = _get_startupinfo()

        print(f"Executing: {' '.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', startupinfo=startupinfo)

        output_lines = []
        for line in process.stdout:
            print(line, end='')
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
