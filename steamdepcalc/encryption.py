from subprocess import check_output, CalledProcessError
import sys
import hashlib
from Cryptodome.Cipher import AES

def _read_cmd(cmd):
    try:
        return str(check_output(cmd), "utf-8")
    except CalledProcessError:
        return None

def _read_reg(path, key_name):
    try:
        import winreg
        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        return winreg.QueryValueEx(reg_key, key_name)[0]
    except OSError:
        return None

def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None

def _get_special_id():
    ids = ["d0_N0t_chAnge_thiS--|3CV2EWzq|--"]

    if sys.platform in ["win32", "cygwin", "msys"]:
        ids += [_read_cmd("wmic csproduct get uuid").split("\n")[1].strip(), _read_reg(r"SOFTWARE\Microsoft\Cryptography", "MachineGuid"), _read_reg(r"SYSTEM\CurrentControlSet\Control\IDConfigDB\Hardware Profiles\0001", "HwProfileGuid")]

    if sys.platform == "darwin":
        ids += [_read_cmd("ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'")]

    if sys.platform.startswith("linux"):
        ids += [_read_file("/etc/machine-id")]

    combined_id = "||<->||".join([x for x in ids if x is not None])

    return hashlib.sha256(combined_id.encode("utf-8")).digest()

def system_encrypt(data: bytes):
    special_id = _get_special_id()
    cipher = AES.new(special_id, AES.MODE_CTR)
    return cipher.nonce + cipher.encrypt(data)

def system_decrypt(data: bytes):
    special_id = _get_special_id()
    return AES.new(special_id, AES.MODE_CTR, nonce=data[:8]).decrypt(data[8:])