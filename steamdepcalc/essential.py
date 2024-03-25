import sys
from os import makedirs, system
from os.path import join, expandvars

def app_path():
    result = ""
    if sys.platform in ["win32", "cygwin", "msys"]:
        result = join(expandvars("%AppData%"), "steamdepcalc")
    elif sys.platform == "darwin":
        result = join(expandvars("$HOME"), "Library", "Application Support", "steamdepcalc")
    elif sys.platform.startswith("linux"):
        result = join(expandvars("$HOME"), ".local", "share", "steamdepcalc")

    makedirs(result, exist_ok=True)
    return result

def set_terminal_title(text: str):
    if sys.platform in ["win32", "cygwin", "msys"]:
        system(f"title {text}")
    else:
        sys.stdout.write(f"\x1b]2;{text}\x07")