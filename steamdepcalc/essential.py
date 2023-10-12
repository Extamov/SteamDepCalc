import sys
from os import makedirs
from os.path import join, expandvars

def app_path():
    result = ""
    if sys.platform in ["win32", "cygwin", "msys"]:
        result = join(expandvars("%AppData%"), "steamdepcalc")
    elif sys.platform == "darwin":
        result = join(expandvars("$HOME"), "Library", "Application Support", "steamdepcalc")
    elif sys.platform.startswith("linux"):
        result = join(expandvars("$HOME"), ".config", "steamdepcalc")

    makedirs(result, exist_ok=True)
    return result