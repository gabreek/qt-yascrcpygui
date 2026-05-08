import os
import sys

def get_clean_env():
    """
    Returns a copy of the current environment with PyInstaller-added 
    library paths removed or restored to their original values.
    This is essential when calling system binaries (like adb or scrcpy)
    from a bundled PyInstaller application on Linux/macOS.
    """
    env = os.environ.copy()
    
    # PyInstaller sets LD_LIBRARY_PATH (Linux) or DYLD_LIBRARY_PATH (macOS)
    # to point to the temporary bundle directory. We need to restore the 
    # original values when calling external system tools.
    for var in ['LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH']:
        orig_var = var + '_ORIG'
        if orig_var in env:
            env[var] = env[orig_var]
            # Optionally remove the _ORIG variable to keep it clean
            # env.pop(orig_var)
        else:
            # If there was no original value, just remove the one set by PyInstaller
            if getattr(sys, 'frozen', False):
                env.pop(var, None)
                
    return env
