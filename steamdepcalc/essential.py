import sys
import os
import os.path

def app_path():
    result = ""
    if sys.platform in ["win32", "cygwin", "msys"]:
        result = os.path.join(os.path.expandvars("%AppData%"), "steamdepcalc")
    elif sys.platform == "darwin":
        result = os.path.join(os.path.expandvars("$HOME"), "Library", "Application Support", "steamdepcalc")
    elif sys.platform.startswith("linux"):
        result = os.path.join(os.path.expandvars("$HOME"), ".local", "share", "steamdepcalc")

    os.makedirs(result, exist_ok=True)
    return result

def set_terminal_title(text: str):
    if sys.platform in ["win32", "cygwin", "msys"]:
        os.system(f"title {text}")
    else:
        sys.stdout.write(f"\x1b]2;{text}\x07")