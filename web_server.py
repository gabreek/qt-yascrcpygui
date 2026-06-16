import uvicorn
from fastapi import FastAPI, Query, Body, HTTPException, Security, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from utils import adb_handler, scrcpy_handler
from utils.constants import *
from app_config import AppConfig
import os
import json
import shlex
import sys
import base64
import logging
import secrets
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Security Setup ---
AUTH_TOKEN = secrets.token_urlsafe(32)
security = HTTPBearer()
_sessions: Dict[str, bool] = {}

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing API token")
    return credentials.credentials

def _check_credentials(username: str, password: str) -> bool:
    app_config = AppConfig(None)
    correct_username = app_config.get(CONF_WEB_USERNAME, "")
    encoded_pass = app_config.get(CONF_WEB_PASSWORD, "")
    correct_password = ""
    if encoded_pass:
        try:
            correct_password = base64.b64decode(encoded_pass.encode()).decode()
        except Exception:
            pass
    return bool(correct_username and username == correct_username and password == correct_password)

app = FastAPI()
web_thread = None
_config_cache: Dict[str, AppConfig] = {}

# --- Path resolution for PyInstaller ---
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Not running in a bundle
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Mount the icon cache directory as a static path
try:
    app_config_for_path = AppConfig(None)
    icon_cache_dir = app_config_for_path.get_icon_cache_dir()
    if os.path.exists(icon_cache_dir):
        app.mount("/icons", StaticFiles(directory=icon_cache_dir), name="icons")
except Exception as e:
    logger.warning("Could not mount icon cache directory: %s", e)

# Mount the gui directory for placeholder images
try:
    gui_assets_dir = get_resource_path('gui')
    if os.path.exists(gui_assets_dir):
        app.mount("/gui_assets", StaticFiles(directory=gui_assets_dir), name="gui_assets")
except Exception as e:
    logger.warning("Could not mount GUI assets directory: %s", e)

class LaunchRequest(BaseModel):
    device_id: str
    pkg_name: str
    app_name: str
    never_turn_screen_off: bool = False

class WinlatorLaunchRequest(BaseModel):
    device_id: str
    shortcut_path: str
    app_name: str
    pkg_name: str
    never_turn_screen_off: bool = False

class ConfigRequest(BaseModel):
    device_id: str
    pkg_name: str
    config_data: Dict[str, Any]

class TextInputRequest(BaseModel):
    device_id: str
    text: str

class KeyEventRequest(BaseModel):
    device_id: str
    key_command: str

class AdbConnectRequest(BaseModel):
    address: str

class PinRequest(BaseModel):
    device_id: str
    pkg_name: str
    pinned: bool


KEY_COMMAND_MAP = {
    "HOME": "KEYCODE_HOME",
    "BACK": "KEYCODE_BACK",
    "APP_SWITCH": "KEYCODE_APP_SWITCH",
    "VOLUME_UP": "KEYCODE_VOLUME_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN",
    "POWER": "KEYCODE_POWER",
}

def get_config_for_device(device_id: str):
    """Initializes AppConfig and loads the configuration for a specific device, using a cache."""
    configuration_id = device_id
    if ':' in device_id:  # It's a Wi-Fi device
        serial_no = adb_handler.get_serial_from_wifi_device(device_id)
        if serial_no:
            configuration_id = serial_no
    
    if configuration_id not in _config_cache:
        app_config = AppConfig(None)
        app_config.load_config_for_device(configuration_id)
        _config_cache[configuration_id] = app_config
    
    app_config = _config_cache[configuration_id]
    app_config.connection_id = device_id  # Ensure connection_id is set for subsequent operations
    return app_config

@app.post("/api/adb/connect", summary="Connect to a device via ADB over WiFi", dependencies=[Depends(verify_token)])
async def adb_connect(request: AdbConnectRequest):
    """Connects to an ADB device over WiFi."""
    try:
        result = adb_handler.connect_wifi(request.address)
        if "connected" in result or "already connected" in result:
            return {"status": "success", "message": result}
        else:
            raise HTTPException(status_code=400, detail=result or "Failed to connect.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in adb_connect")
        # We don't have a device_id here yet, so we use a generic AppConfig(None) for translation
        tmp_config = AppConfig(None)
        raise HTTPException(status_code=500, detail=tmp_config.tr('api', 'error_adb_connect'))

@app.post("/api/app/pin", summary="Pin or unpin an application", dependencies=[Depends(verify_token)])
async def pin_app(request: PinRequest):
    """Pins or unpins an application for the current device."""
    try:
        app_config = get_config_for_device(request.device_id)
        app_config.save_app_metadata(request.pkg_name, {'pinned': request.pinned})
        msg_key = 'app_pinned' if request.pinned else 'app_unpinned'
        return {"status": "success", "message": app_config.tr('api', msg_key, pkg=request.pkg_name)}
    except Exception as e:
        logger.exception("Error in pin_app")
        app_config = get_config_for_device(request.device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_pin'))

@app.post("/api/input/text", dependencies=[Depends(verify_token)])
async def text_input(request: TextInputRequest):
    """Types the given text on the device."""
    try:
        adb_handler._run_adb_command(['shell', 'input', 'text', shlex.quote(request.text)], request.device_id)
        app_config = get_config_for_device(request.device_id)
        return {"status": "success", "message": app_config.tr('api', 'text_input_sent')}
    except Exception as e:
        logger.exception("Error in text_input")
        app_config = get_config_for_device(request.device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_text_input'))

@app.post("/api/input/keyevent", dependencies=[Depends(verify_token)])
async def key_event(request: KeyEventRequest):
    """Sends a key event to the device."""
    try:
        keycode = KEY_COMMAND_MAP.get(request.key_command.upper())
        if not keycode:
            raise HTTPException(status_code=400, detail="Invalid key command.")

        adb_handler._run_adb_command(['shell', 'input', 'keyevent', keycode], request.device_id)
        app_config = get_config_for_device(request.device_id)
        return {"status": "success", "message": app_config.tr('api', 'key_event_sent', key=request.key_command)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in key_event")
        app_config = get_config_for_device(request.device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_key_event'))

@app.get("/api/folders", summary="List custom session folders with ordering", dependencies=[Depends(verify_token)])
async def list_folders(device_id: str):
    """Returns custom session folders (pinned sections) and their display order."""
    try:
        app_config = get_config_for_device(device_id)
        custom_sessions = app_config.get_custom_sessions()
        order = app_config.get_custom_sessions_order()
        existing = [k for k in order if k in custom_sessions and k != 'all']
        remaining = sorted([k for k in custom_sessions if k != 'all' and k not in order], key=lambda x: x.lower())
        return {"folders": existing + remaining}
    except Exception:
        return {"folders": []}

@app.get("/api/config", dependencies=[Depends(verify_token)])
async def get_config(device_id: str, profile_key: str, b64: bool = False):
    """Retrieves the configuration for a specific app on a device."""
    try:
        decoded_key = profile_key
        if b64:
            decoded_key = base64.b64decode(profile_key).decode('utf-8')

        app_config = get_config_for_device(device_id)
        
        # Use the AppConfig's internal profile loading mechanism, which is known to work
        app_config.load_profile(decoded_key)

        # Get all keys dynamically from AppConfig
        config_keys = AppConfig.all_known_keys()
        
        config_to_use = {}
        for key in config_keys:
            # By calling get() for each key, we get the final value after the
            # profile (global + specific) has been loaded internally by AppConfig.
            value = app_config.get(key)
            if value is not None:
                config_to_use[key] = value
            
        return config_to_use
    except Exception as e:
        logger.exception("Error in get_config")
        app_config = get_config_for_device(device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_get_config'))


@app.post("/api/config", dependencies=[Depends(verify_token)])
async def set_config(request: ConfigRequest):
    """Saves the configuration for a specific app on a device."""
    try:
        configuration_id = request.device_id
        if ':' in request.device_id:
            serial_no = adb_handler.get_serial_from_wifi_device(request.device_id)
            if serial_no:
                configuration_id = serial_no
        
        # Invalidate cache
        if configuration_id in _config_cache:
            del _config_cache[configuration_id]

        app_config = get_config_for_device(request.device_id)
        app_config.save_app_scrcpy_config(request.pkg_name, request.config_data)
        if web_thread:
            web_thread.config_needs_reload.emit()
        return {"status": "success", "message": app_config.tr('api', 'config_saved')}
    except Exception as e:
        logger.exception("Error in set_config")
        app_config = get_config_for_device(request.device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_set_config'))

@app.get("/api/devices", dependencies=[Depends(verify_token)])
async def list_devices():
    """Returns a list of all connected ADB devices with their info."""
    try:
        output = adb_handler._run_adb_command(['devices'], ignore_errors=True)
        lines = output.strip().split('\n')
        devices = []
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split('\t')
                if len(parts) == 2:
                    device_id = parts[0].strip()
                    state = parts[1].strip()
                    if device_id and state == 'device':
                        device_info = adb_handler.get_device_info(device_id)
                        devices.append({
                            "id": device_id,
                            "name": device_info.get("commercial_name", "Unknown") if device_info else "Unknown",
                            "battery": device_info.get("battery", "?") if device_info else "?"
                        })
        return devices
    except Exception as e:
        logger.exception("Error in list_devices")
        tmp_config = AppConfig(None)
        raise HTTPException(status_code=500, detail=tmp_config.tr('api', 'error_list_devices'))


@app.get("/api/devices/{device_id}/info", summary="Get detailed device information", dependencies=[Depends(verify_token)])
async def get_device_details(device_id: str):
    try:
        info = adb_handler.get_device_info(device_id)
        if not info:
            raise HTTPException(status_code=404, detail="Device not found or info not available.")

        launcher = adb_handler.get_default_launcher(device_id)
        info['default_launcher'] = launcher
        return info
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in get_device_details")
        app_config = get_config_for_device(device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_device_details'))


@app.get("/api/profiles", summary="List profiles with existing configurations for a device", dependencies=[Depends(verify_token)])
async def list_profiles(device_id: str):
    """
    Lists app and Winlator profiles that have a saved configuration and are currently installed on the device.
    """
    try:
        app_config = get_config_for_device(device_id)

        # Get installed apps
        user_apps, system_apps = scrcpy_handler.list_installed_apps(device_id)
        installed_apps_packages = set(user_apps.values()) | set(system_apps.values())

        # Get winlator shortcuts
        shortcuts = adb_handler.list_winlator_shortcuts_with_names(device_id)
        winlator_shortcuts_on_device = {path for name, path in shortcuts}

        # Filter app configs
        app_configs_from_settings = app_config.get_app_config_keys()
        filtered_app_configs = []
        for key, name in app_configs_from_settings:
            if key in installed_apps_packages:
                filtered_app_configs.append({"key": key, "name": name})

        # Filter winlator configs
        winlator_configs_from_settings = app_config.get_winlator_config_keys()
        filtered_winlator_configs = []
        for key, name in winlator_configs_from_settings:
            if key in winlator_shortcuts_on_device:
                filtered_winlator_configs.append({"key": key, "name": name})

        return {
            "apps": sorted(filtered_app_configs, key=lambda x: x['name'].lower()),
            "winlator": sorted(filtered_winlator_configs, key=lambda x: x['name'].lower())
        }
    except Exception as e:
        logger.exception("Error in list_profiles")
        # Gracefully fail if device disconnects or other ADB errors occur during fetch
        return {"apps": [], "winlator": []}


@app.get("/api/apps", dependencies=[Depends(verify_token)])
async def list_apps(device_id: str, include_system_apps: bool = False):
    """Lists installed applications for a given device."""
    try:
        app_config = get_config_for_device(device_id)
        user_apps, system_apps = scrcpy_handler.list_installed_apps(device_id)

        all_apps = []
        app_list = user_apps.items()
        if include_system_apps:
            app_list = list(user_apps.items()) + list(system_apps.items())

        for name, pkg in app_list:
            metadata = app_config.get_app_metadata(pkg)
            is_pinned = metadata.get('pinned', False)
            all_apps.append({"name": name, "pkg_name": pkg, "icon": f"{pkg}.png", "pinned": is_pinned})

        all_apps.sort(key=lambda x: x['name'].lower())
        return all_apps
    except Exception as e:
        logger.exception("Error in list_apps")
        app_config = get_config_for_device(device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_list_apps'))


@app.get("/api/winlator/apps", summary="List Winlator shortcuts/games", dependencies=[Depends(verify_token)])
async def list_winlator_apps(device_id: str):
    """Lists Winlator shortcuts found on the device."""
    try:
        shortcuts = adb_handler.list_winlator_shortcuts_with_names(device_id)
        if not shortcuts:
            return []

        games = []
        for name, path in shortcuts:
            pkg = adb_handler.get_package_name_from_shortcut(path, device_id)
            icon_filename = f"{os.path.basename(path)}.png"
            games.append({"name": name, "path": path, "pkg": pkg, "icon": icon_filename})

        return sorted(games, key=lambda x: x['name'].lower())
    except Exception as e:
        logger.exception("Error in list_winlator_apps")
        app_config = get_config_for_device(device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_list_winlator'))


@app.post("/api/launch", summary="Launch a standard Android application", dependencies=[Depends(verify_token)])
async def launch_app(request: LaunchRequest):
    """Launches an application on a device and tracks the session."""
    try:
        app_config = get_config_for_device(request.device_id)
        config_to_use = app_config.get_global_values_no_profile()
        app_specific_config = app_config.get_app_metadata(request.pkg_name).get('config', {})
        if app_specific_config:
            config_to_use.update(app_specific_config)

        config_to_use['start_app'] = request.pkg_name
        perform_alt_launch = config_to_use.get(ALTERNATE_LAUNCH_METHOD, False)

        if request.never_turn_screen_off:
            config_to_use['turn_screen_off'] = False

        icon_cache_dir = app_config.get_icon_cache_dir()
        icon_path = os.path.join(icon_cache_dir, f"{request.pkg_name}.png")

        process = scrcpy_handler.launch_scrcpy(
            config_values=config_to_use,
            window_title=request.app_name,
            device_id=request.device_id,
            icon_path=icon_path,
            session_type='app',
            perform_alternate_app_launch=perform_alt_launch
        )
        
        scrcpy_handler.add_active_scrcpy_session(
            pid=process.pid,
            app_name=request.app_name,
            command_args=process.args,
            icon_path=icon_path,
            session_type='app'
        )
        return {"status": "success", "message": app_config.tr('api', 'launch_sent', name=request.app_name), "pid": process.pid}
    except Exception as e:
        logger.exception("Error in launch_app")
        app_config = get_config_for_device(request.device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_launch'))

@app.post("/api/winlator/launch", summary="Launch a Winlator application", dependencies=[Depends(verify_token)])
async def launch_winlator_app(request: WinlatorLaunchRequest):
    """Launches a Winlator app on a device and tracks the session."""
    try:
        app_config = get_config_for_device(request.device_id)
        config_to_use = app_config.get_global_values_no_profile()
        
        # Winlator apps might have specific configs stored by shortcut path
        app_specific_config = app_config.get_app_metadata(request.shortcut_path).get('config', {})
        if app_specific_config:
            config_to_use.update(app_specific_config)
            
        # This is for the alternate launch logic inside scrcpy_handler
        config_to_use['package_name_for_alt_launch'] = request.pkg_name
        config_to_use['shortcut_path'] = request.shortcut_path
        
        if request.never_turn_screen_off:
            config_to_use['turn_screen_off'] = False
        
        icon_cache_dir = app_config.get_icon_cache_dir()
        icon_path = os.path.join(icon_cache_dir, f"{os.path.basename(request.shortcut_path)}.png")

        process = scrcpy_handler.launch_scrcpy(
            config_values=config_to_use,
            window_title=request.app_name,
            device_id=request.device_id,
            icon_path=icon_path,
            session_type='winlator',
            perform_alternate_app_launch=True # Necessary for display ID detection and app start
        )
        
        scrcpy_handler.add_active_scrcpy_session(
            pid=process.pid,
            app_name=request.app_name,
            command_args=process.args,
            icon_path=icon_path,
            session_type='winlator'
        )
        return {"status": "success", "message": app_config.tr('api', 'launch_sent', name=request.app_name), "pid": process.pid}
    except Exception as e:
        logger.exception("Error in launch_winlator_app")
        app_config = get_config_for_device(request.device_id)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_launch_winlator'))

@app.get("/api/scrcpy/encoders", summary="List available scrcpy encoders", dependencies=[Depends(verify_token)])
async def list_encoders(device_id: str = None):
    try:
        if not device_id:
            return {"video_encoders": {}, "audio_encoders": {}}

        app_config = get_config_for_device(device_id)

        # Use cache if available, similar to the desktop app
        cached_data = app_config.get_encoder_cache()
        if cached_data and cached_data.get('video'):
            return {
                "video_encoders": cached_data.get('video', {}),
                "audio_encoders": cached_data.get('audio', {})
            }
        
        # Fallback to live fetch and save to cache
        video_encoders, audio_encoders = scrcpy_handler.list_encoders()
        app_config.save_encoder_cache(video_encoders, audio_encoders)
        return {"video_encoders": video_encoders, "audio_encoders": audio_encoders}

    except Exception as e:
        logger.exception("Error in list_encoders")
        return {"video_encoders": {}, "audio_encoders": {}}

@app.get("/api/scrcpy/sessions", summary="List active scrcpy sessions", dependencies=[Depends(verify_token)])
async def get_active_sessions():
    """Returns a list of active (running) scrcpy sessions."""
    try:
        sessions = scrcpy_handler.get_active_scrcpy_sessions()
        for s in sessions:
            if s.get('icon_path'):
                s['icon_url'] = f"/icons/{os.path.basename(s['icon_path'])}"
            else:
                s['icon_url'] = None
        return sessions
    except Exception as e:
        logger.exception("Error in get_active_sessions")
        raise HTTPException(status_code=500, detail="Internal error while listing scrcpy sessions.")

@app.delete("/api/scrcpy/sessions/{pid}", summary="Kill a scrcpy session by PID", dependencies=[Depends(verify_token)])
async def kill_session(pid: int, device_id: str = None):
    """Terminates a scrcpy session by its Process ID (PID)."""
    try:
        app_config = get_config_for_device(device_id) if device_id else AppConfig(None)
        if scrcpy_handler.kill_scrcpy_session(pid):
            return {"status": "success", "message": app_config.tr('api', 'session_killed', pid=pid)}
        else:
            raise HTTPException(status_code=404, detail=app_config.tr('api', 'session_not_found', pid=pid))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in kill_session")
        app_config = get_config_for_device(device_id) if device_id else AppConfig(None)
        raise HTTPException(status_code=500, detail=app_config.tr('api', 'error_kill_session'))

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>yaScrcpy - Login</title>
  <link rel="manifest" href="/static/manifest.json">
  <meta name="theme-color" content="#1e1e1e">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="yaScrcpy">
  <link rel="apple-touch-icon" href="/static/icon.png">
  <style id="theme-vars">:root { --bg: #1e1e1e; --text: #d4d4d4; --primary: #007acc; --primary-hover: #005a9e; --panel: #2a2a2a; --border: #444; --input-bg: #1e1e1e; --input-border: #555; --muted: #9ca3af; --danger: #ef4444; --danger-hover: #dc2626; }</style>
  <!--THEME_CSS-->
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: var(--bg); color: var(--text); }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 32px; width: 320px; }
    h1 { text-align: center; margin-bottom: 24px; font-size: 20px; }
    label { display: block; margin-bottom: 4px; font-size: 13px; color: var(--muted); }
    input { width: 100%; padding: 10px; margin-bottom: 16px; border: 1px solid var(--input-border); border-radius: 6px; background: var(--input-bg); color: var(--text); font-size: 14px; }
    button { width: 100%; padding: 10px; border: none; border-radius: 6px; background: var(--primary); color: #fff; font-size: 14px; cursor: pointer; }
    button:hover { background: var(--primary-hover); }
    .error { color: var(--danger); font-size: 13px; text-align: center; margin-top: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>yaScrcpy Web</h1>
    <form method="post" action="/login">
      <label for="username">Username</label>
      <input type="text" id="username" name="username" autocomplete="username" required>
      <label for="password">Password</label>
      <input type="password" id="password" name="password" autocomplete="current-password" required>
      <button type="submit">Sign In</button>
    </form>
  </div>
  <script>
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js');
    }
  </script>
</body>
</html>"""

_THEME_COLORS_FILE = os.path.expanduser("~/.config/yaScrcpy/current_theme.json")

def _get_web_theme_css():
    """Returns a :root CSS block with the app's current theme colors."""
    # Default dark fallback
    colors = {
        'bg': '#1e1e1e', 'text': '#d4d4d4', 'primary': '#007acc',
        'primary_hover': '#005a9e', 'panel': '#2a2a2a', 'border': '#444',
        'input_bg': '#1e1e1e', 'input_border': '#555', 'muted': '#9ca3af',
        'danger': '#ef4444', 'danger_hover': '#dc2626',
    }

    # Read colors saved by themes.py at theme-change time (works for ALL themes, including System)
    try:
        with open(_THEME_COLORS_FILE) as f:
            saved = json.load(f)
            colors.update(saved)
    except Exception:
        pass

    return f"""<style id="theme-vars">:root {{
  --bg: {colors['bg']};
  --text: {colors['text']};
  --primary: {colors['primary']};
  --primary-hover: {colors['primary_hover']};
  --panel: {colors['panel']};
  --border: {colors['border']};
  --input-bg: {colors['input_bg']};
  --input-border: {colors['input_border']};
  --muted: {colors['muted']};
  --danger: {colors['danger']};
  --danger-hover: {colors['danger_hover']};
}}</style>"""

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return _LOGIN_PAGE.replace('<!--THEME_CSS-->', _get_web_theme_css())

@app.post("/login")
async def do_login(request: Request):
    form = await request.form()
    username = form.get('username', '')
    password = form.get('password', '')
    if _check_credentials(username, password):
        session_id = str(uuid.uuid4())
        _sessions[session_id] = True
        resp = RedirectResponse(url='/', status_code=303)
        resp.set_cookie(key='session', value=session_id, max_age=86400*30, path='/', httponly=True, samesite='lax')
        return resp
    return HTMLResponse(content=_LOGIN_PAGE.replace('<!--THEME_CSS-->', _get_web_theme_css()).replace('</form>', '</form><p class="error">Invalid credentials</p>'), status_code=401)

# Serve index.html with the injected API token and theme.
# If not authenticated, serve the login page inline (no redirect — keeps PWA standalone).
@app.get("/", response_class=HTMLResponse, summary="Serve the web interface with auth token")
async def serve_index(request: Request):
    session_id = request.cookies.get('session')
    if not session_id or session_id not in _sessions:
        return HTMLResponse(content=_LOGIN_PAGE)
    index_path = get_resource_path('web/index.html')
    with open(index_path, 'r') as f:
        content = f.read()
    # Inject theme colors (replaces placeholder)
    content = content.replace('<!--THEME_CSS-->', _get_web_theme_css())
    # Inject the API token
    content = content.replace('{{API_TOKEN}}', AUTH_TOKEN)
    return content

# Serve service worker at root scope (no auth — browser fetches it without credentials)
@app.get("/sw.js", response_class=HTMLResponse)
async def serve_sw():
    sw_path = get_resource_path('web/sw.js')
    with open(sw_path, 'r') as f:
        return f.read()

# Mount the static web assets (excluding index.html)
web_dir = get_resource_path('web')
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="web_static")
else:
    logger.error("CRITICAL: Web directory '%s' not found.", web_dir)


def _ensure_ssl_cert():
    """Generate a self-signed cert for HTTPS if it doesn't exist. Returns (certfile, keyfile) or (None, None)."""
    cert_dir = os.path.expanduser("~/.config/yaScrcpy")
    cert_path = os.path.join(cert_dir, "server.crt")
    key_path = os.path.join(cert_dir, "server.key")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path
    os.makedirs(cert_dir, exist_ok=True)
    try:
        import subprocess
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_path, "-out", cert_path,
            "-days", "3650", "-nodes",
            "-subj", "/CN=yaScrcpy"
        ], check=True, capture_output=True)
        os.chmod(key_path, 0o600)
        logger.info("Self-signed SSL certificate generated at %s", cert_path)
        return cert_path, key_path
    except Exception as e:
        logger.warning("Could not generate SSL certificate (install openssl or use HTTP): %s", e)
        return None, None

def set_thread_instance(thread):
    """This function is called by the QThread to set the global thread instance."""
    global web_thread
    web_thread = thread

if __name__ == "__main__":
    app_config = AppConfig(None)
    port = int(app_config.get(CONF_WEB_PORT, 8000))
    certfile, keyfile = _ensure_ssl_cert()
    if certfile and keyfile:
        logger.info("Starting HTTPS on port %d", port)
        uvicorn.run(app, host="0.0.0.0", port=port, access_log=False, ssl_certfile=certfile, ssl_keyfile=keyfile)
    else:
        logger.info("Starting HTTP on port %d", port)
        uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)