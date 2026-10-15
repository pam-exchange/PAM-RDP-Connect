'''
MIT License

Copyright (c) 2024-2026 PAM-Exchange

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import os
import sys
import re
import time
import math
import shutil
import tempfile
import subprocess
import configparser
import ctypes
import getpass

try:
    import msvcrt
    import win32file
    import win32pipe
    import win32gui
    import win32process
    import win32con
    import win32api
    import pywintypes
except ImportError:
    msvcrt = None
    win32file = None
    win32pipe = None
    win32gui = None
    win32process = None
    win32con = None
    win32api = None
    pywintypes = None

def get_app_version():
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        vfile = os.path.join(script_dir, "version")
        if os.path.exists(vfile):
            with open(vfile, "r", encoding="utf-8") as f:
                v = f.read().strip()
                if v:
                    return v
    except Exception:
        pass
    return "2.9.0.0"

gVersion = get_app_version()
gProgramTitle = "PAM RDP Connect"

gSelfPid = os.getpid()
gSelfPidHex = f"{gSelfPid:04x}"

gLockFilename = os.path.join(tempfile.gettempdir(), "pam-rdp.lock")
gLockFd = None
gPipeName = "PAM-RDP-SERVICE"

LOG_ALWAYS = 0
LOG_ERROR = 1
LOG_WARNING = 2
LOG_INFO = 3
LOG_DEBUG = 4
LOG_TRACE = 5

PAM_TYPE_BEYONDTRUST = "BeyondTrustPasswordSafe"
PAM_TYPE_SYMANTEC = "SymantecPAM"
PAM_TYPE_SYMANTEC2 = "SymantecPAMGateway"
PAM_TYPE_SENHASEGURA = "Senhasegura"
PAM_TYPE_CYBERARK = "CyberArk"

PROPERTY_TYPE_SYSTEM = 1
PROPERTY_TYPE_USER = 2

gLogFile = os.path.join(tempfile.gettempdir(), "pam-rdp.log")
gLogLevel = LOG_DEBUG
ErrorMessage = ""


class Settings:
    def __init__(self):
        self.PropertyFilename = ""

        # User properties
        self.CleanupDefined = False
        self.Cleanup = True
        self.ConnectTimeout = 60
        self.PromptTimeout = 15

        self.ScreenModeDefined = False
        self.ScreenMode = "Fullscreen"
        self.WindowWidth = 1024
        self.WindowHeight = 768

        self.UseFontSmoothingDefined = False
        self.UseFontSmoothing = True

        self.AllowWallpaperDefined = False
        self.AllowWallpaper = False

        self.SessionBppDefined = False
        self.SessionBpp = 24

        self.LocalDriveMappingDefined = False
        self.LocalDriveMapping = ""

        self.AcceptSecurityMessagesDefined = False
        self.AcceptSecurityMessages = True

        self.UseSmartSizingDefined = False
        self.UseSmartSizing = False

        self.LogLevel = LOG_DEBUG

        # System properties
        self.PamType = PAM_TYPE_BEYONDTRUST
        self.Heartbeat = True
        self.HeartbeatProgram = r"C:\Program Files\PAM-Exchange\PAM-RDP-Heartbeat\pam-rdp-heartbeat.exe"
        self.Program = r"C:\Windows\system32\mstsc.exe"
        self.MultiUser = False
        self.Port = 4489
        self.CntServer = 0
        self.PamInfo = []


gSettings = Settings()
gLockTimeout = 61000

gFilenameFull = ""
gFilenamePath = ""
gFilenameBase = ""
gFilenameExt = ""
gTemplateDefaultRdpFilename = ""


def log_roll(filename, max_size_mb=5, keep=5):
    if not os.path.exists(filename):
        return
    try:
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        if size_mb >= max_size_mb:
            for i in range(keep - 1, 0, -1):
                fn1 = f"{filename}.{i + 1}"
                fn2 = f"{filename}.{i}"
                if os.path.exists(fn2):
                    try:
                        shutil.move(fn2, fn1)
                    except Exception:
                        pass
            try:
                shutil.move(filename, f"{filename}.1")
            except Exception:
                pass
    except Exception:
        pass


def log_msg(level, line, msg):
    global gLogLevel, gLogFile, gSelfPidHex
    if level <= gLogLevel:
        level_map = {
            LOG_ALWAYS: "ALW",
            LOG_ERROR: "ERR",
            LOG_WARNING: "WRN",
            LOG_INFO: "INF",
            LOG_DEBUG: "DBG",
            LOG_TRACE: "TRC"
        }
        level_txt = level_map.get(level, "DBG")
        time_str = time.strftime("%y/%m/%d %H:%M:%S")
        txt = f"{time_str} [{gSelfPidHex}] {level_txt} {msg} [{line}]\n"
        try:
            with open(gLogFile, "a", encoding="utf-8") as f:
                f.write(txt)
        except Exception:
            pass


def log_trace(line, msg): log_msg(LOG_TRACE, line, msg)
def log_debug(line, msg): log_msg(LOG_DEBUG, line, msg)
def log_info(line, msg): log_msg(LOG_INFO, line, msg)
def log_warning(line, msg): log_msg(LOG_WARNING, line, msg)
def log_error(line, msg): log_msg(LOG_ERROR, line, msg)
def log_always(line, msg): log_msg(LOG_ALWAYS, line, msg)


def msg_box(text, title=gProgramTitle, style=0):
    try:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
            ctypes.windll.user32.MessageBoxW(0, str(text), str(title), style)
        else:
            print(f"[{title}] {text}")
    except Exception:
        print(f"[{title}] {text}")


def end_script():
    semaphore_release()
    log_debug(sys._getframe().f_lineno, "EndScript: exit, finished")
    sys.exit(0)


def semaphore_acquire(timeout_ms):
    global gLockFilename, gLockFd, ErrorMessage
    end_time = (time.time() * 1000) + timeout_ms

    while True:
        try:
            fd = os.open(gLockFilename, os.O_CREAT | os.O_RDWR)
            if msvcrt:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            gLockFd = fd
            log_debug(sys._getframe().f_lineno, f"SemaphoreAcquire: acquired - lockFilename= '{gLockFilename}'")
            return True
        except Exception:
            pass

        log_debug(sys._getframe().f_lineno, f"SemaphoreAcquire: waiting - lockFilename= '{gLockFilename}'")
        time.sleep(1)

        if (time.time() * 1000) > end_time:
            break

    ErrorMessage = "Timeout waiting for semaphore."
    log_error(sys._getframe().f_lineno, f"SemaphoreAcquire: {ErrorMessage}")
    return False


def semaphore_release():
    global gLockFd
    if gLockFd is not None:
        if msvcrt:
            try:
                msvcrt.locking(gLockFd, msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        try:
            os.close(gLockFd)
        except Exception:
            pass
        gLockFd = None
        log_debug(sys._getframe().f_lineno, "SemaphoreRelease: released")


def pipe_message(msg, pipename="", timeout=10000):
    global gPipeName, ErrorMessage
    if not pipename:
        pipename = gPipeName

    pipe_path = rf"\\.\pipe\{pipename}"
    log_debug(sys._getframe().f_lineno, f"PipeMessage: msg= '{msg}', pipename= '{pipename}', timeout= {timeout}")

    if not win32pipe or not win32file:
        ErrorMessage = "Win32 Pipe API unavailable on this platform"
        log_error(sys._getframe().f_lineno, f"PipeMessage: {ErrorMessage}")
        return -1

    try:
        win32pipe.WaitNamedPipe(pipe_path, timeout)
    except Exception as e:
        ErrorMessage = f"WaitNamedPipe failed, lastError= {e}"
        log_error(sys._getframe().f_lineno, f"PipeMessage: {ErrorMessage}")
        return -1

    try:
        handle = win32file.CreateFile(
            pipe_path,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0, None,
            win32file.OPEN_EXISTING,
            0, None
        )
    except Exception as e:
        ErrorMessage = f"CreateFile failed, lastError= {e}"
        log_error(sys._getframe().f_lineno, f"PipeMessage: {ErrorMessage}")
        return -2

    try:
        win32file.WriteFile(handle, msg.encode("ascii"))
        hr, data = win32file.ReadFile(handle, 1024)
        win32file.CloseHandle(handle)

        rsp = data.decode("ascii", errors="replace").strip()
        log_debug(sys._getframe().f_lineno, f"PipeMessage: rsp= -->{rsp}<--")

        if rsp.startswith("OK"):
            return 1
        else:
            ErrorMessage = rsp
            log_error(sys._getframe().f_lineno, f"PipeMessage: rsp= {ErrorMessage}")
            return -4
    except Exception as e:
        ErrorMessage = f"Pipe I/O failed, lastError= {e}"
        log_error(sys._getframe().f_lineno, f"PipeMessage: {ErrorMessage}")
        try:
            win32file.CloseHandle(handle)
        except Exception:
            pass
        return -3


def update_hosts_file(cmd, ip, hostname):
    log_debug(sys._getframe().f_lineno, f"UpdateHostsFile: cmd= '{cmd}', ip= '{ip}', hostname= '{hostname}'")
    msg = f"{cmd} {ip} {hostname}"
    log_debug(sys._getframe().f_lineno, f"UpdateHostsFile: msg= '{msg}'")
    return pipe_message(msg)


def get_long_path_name(path):
    try:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "kernel32"):
            buf = ctypes.create_unicode_buffer(1024)
            res = ctypes.windll.kernel32.GetLongPathNameW(path, buf, 1024)
            if res > 0:
                return buf.value
    except Exception:
        pass
    return path


def delete_file(filename):
    global ErrorMessage
    log_debug(sys._getframe().f_lineno, f"deleteFile: Deleting '{filename}'")
    try:
        if os.path.exists(filename):
            os.remove(filename)
            log_info(sys._getframe().f_lineno, f"deleteFile: Deleted file '{filename}'")
    except Exception as e:
        ErrorMessage = f"Cannot delete file '{filename}'"
        log_error(sys._getframe().f_lineno, f"deleteFile: {ErrorMessage}")
        log_debug(sys._getframe().f_lineno, f"deleteFile: {e}")


def get_clone_filename(server_name):
    clone_filepath = tempfile.gettempdir()
    clone_filepath = get_long_path_name(clone_filepath)
    ts = time.strftime("%Y%m%d%H%M%S")
    clone_filename = os.path.join(clone_filepath, f"PAM-RDP-{server_name}-{ts}.rdp")
    log_debug(sys._getframe().f_lineno, f"getCloneFilename: serverName= '{server_name}', cloneFilename= '{clone_filename}'")
    return clone_filename


def read_properties(filename, p_type=0, settings=None):
    if settings is None:
        settings = Settings()

    if p_type == 0:
        p_type = PROPERTY_TYPE_USER

    log_debug(sys._getframe().f_lineno, f"readProperties: pType= {p_type}, filename= {filename}")

    if not os.path.exists(filename):
        log_always(sys._getframe().f_lineno, f"readProperties: file not found '{filename}' - use defaults")

    settings.PropertyFilename = filename

    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    if os.path.exists(filename):
        try:
            config.read(filename, encoding="utf-8-sig")
        except Exception:
            try:
                config.read(filename)
            except Exception:
                pass

    if p_type == PROPERTY_TYPE_USER:
        def_not_set = "Not Set"

        log_level_str = config.get("main", "LogLevel", fallback="DEBUG").strip().upper()
        level_map = {
            "ERROR": LOG_ERROR,
            "WARNING": LOG_WARNING,
            "INFO": LOG_INFO,
            "DEBUG": LOG_DEBUG,
            "TRACE": LOG_TRACE
        }
        settings.LogLevel = level_map.get(log_level_str, LOG_DEBUG)
        global gLogLevel
        gLogLevel = settings.LogLevel
        log_always(sys._getframe().f_lineno, f"ReadProperties: LogLevel= '{settings.LogLevel}'")

        x = config.get("main", "cleanup", fallback=def_not_set)
        settings.CleanupDefined = (x != def_not_set)
        settings.Cleanup = ("false" not in x.lower())
        log_info(sys._getframe().f_lineno, f"ReadProperties: cleanup = '{settings.Cleanup}' (final)")

        x = config.get("main", "ConnectTimeout", fallback="60")
        try:
            val = int(x)
            if val <= 0 or val >= 900:
                val = 60
        except ValueError:
            val = 60
        settings.ConnectTimeout = val
        log_info(sys._getframe().f_lineno, f"ReadProperties: ConnectTimeout= '{settings.ConnectTimeout}' (final)")

        x = config.get("main", "promptTimeout", fallback="15")
        try:
            val = int(x)
            if val <= 0 or val >= 60:
                val = 15
        except ValueError:
            val = 15
        settings.PromptTimeout = val
        log_info(sys._getframe().f_lineno, f"ReadProperties: PromptTimeout= '{settings.PromptTimeout}' (final)")

        x = config.get("main", "screenMode", fallback=def_not_set)
        settings.ScreenModeDefined = (x != def_not_set)
        if not re.search(r"(Window|Fullscreen|Maximize)", x, re.I):
            x = "Fullscreen"
        settings.ScreenMode = x

        loc_width = 1024
        loc_height = 768

        if settings.ScreenMode == "Fullscreen":
            loc_width = 1024
            loc_height = 768
        elif settings.ScreenMode == "Maximize":
            try:
                if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
                    user32 = ctypes.windll.user32
                    loc_width = user32.GetSystemMetrics(0)
                    loc_height = user32.GetSystemMetrics(1)
            except Exception:
                loc_width, loc_height = 1024, 768
        elif settings.ScreenMode == "Window":
            try:
                loc_width = int(config.get("main", "windowWidth", fallback="1024"))
            except ValueError:
                loc_width = 1024
            try:
                loc_height = int(config.get("main", "windowHeight", fallback="768"))
            except ValueError:
                loc_height = 768

        settings.WindowWidth = loc_width
        settings.WindowHeight = loc_height
        log_info(sys._getframe().f_lineno, f"ReadProperties: ScreenMode= {settings.ScreenMode}, WindowWidth= {settings.WindowWidth}, WindowHeight={settings.WindowHeight} (final)")

        x = config.get("main", "UseFontSmoothing", fallback=def_not_set)
        settings.UseFontSmoothingDefined = (x != def_not_set)
        settings.UseFontSmoothing = ("true" in x.lower())

        x = config.get("main", "wallpaper", fallback=def_not_set)
        settings.AllowWallpaperDefined = (x != def_not_set)
        settings.AllowWallpaper = ("true" in x.lower())

        x = config.get("main", "sessionBpp", fallback=def_not_set)
        settings.SessionBppDefined = (x != def_not_set)
        try:
            val = int(x)
            if val not in (16, 24, 32):
                val = 24
        except ValueError:
            val = 24
        settings.SessionBpp = val

        x = config.get("main", "localDriveMapping", fallback=def_not_set)
        settings.LocalDriveMappingDefined = (x != def_not_set)
        settings.LocalDriveMapping = x

        x = config.get("main", "acceptSecurityMessages", fallback=def_not_set)
        settings.AcceptSecurityMessagesDefined = (x != def_not_set)
        settings.AcceptSecurityMessages = ("true" in x.lower())

        x = config.get("main", "useSmartSizing", fallback=def_not_set)
        settings.UseSmartSizingDefined = (x != def_not_set)
        settings.UseSmartSizing = ("true" in x.lower())

    if p_type == PROPERTY_TYPE_SYSTEM:
        x = config.get("main", "PAMtype", fallback=PAM_TYPE_BEYONDTRUST)
        if not re.search(rf"({PAM_TYPE_BEYONDTRUST}|{PAM_TYPE_SYMANTEC}|{PAM_TYPE_SENHASEGURA}|{PAM_TYPE_CYBERARK})", x, re.I):
            x = PAM_TYPE_BEYONDTRUST
        settings.PamType = x
        log_info(sys._getframe().f_lineno, f"ReadProperties: PamType= '{settings.PamType}' (final)")

        x = config.get("main", "heartbeat", fallback="true")
        settings.Heartbeat = ("true" in x.lower())
        if settings.Heartbeat:
            x = config.get("main", "heartbeatprogram", fallback=r"C:\Program Files\PAM-Exchange\PAM-RDP-Heartbeat\pam-rdp-heartbeat.exe")
            settings.HeartbeatProgram = x

        x = config.get("main", "mstscProgram", fallback=r"C:\Windows\system32\mstsc.exe")
        settings.Program = x

        x = config.get("main", "multiUser", fallback="false")
        settings.MultiUser = ("true" in x.lower())

        def_port = 4489 if settings.PamType == PAM_TYPE_BEYONDTRUST else 3389
        x = config.get(settings.PamType, "Port", fallback=str(def_port))
        try:
            settings.Port = int(x)
        except ValueError:
            settings.Port = def_port

        x = config.get(settings.PamType, "cntServer", fallback="0")
        try:
            settings.CntServer = int(x)
        except ValueError:
            settings.CntServer = 0

        pam_info = []
        for idx in range(1, settings.CntServer + 1):
            sec = f"Server{idx}"
            ip = config.get(sec, "ip", fallback="ERROR")
            dns = config.get(sec, "dns", fallback="ERROR")
            hostname = config.get(sec, "hostname", fallback="ERROR")
            if "ERROR" not in (ip, dns, hostname):
                pam_info.extend([ip, dns, hostname])
                log_debug(sys._getframe().f_lineno, f"ReadProperties: server - index= {idx}, ip= {ip}, dns= {dns}, hostname= {hostname}")
            else:
                log_error(sys._getframe().f_lineno, f"ReadProperties: server - index= {idx}, ip= {ip}, dns= {dns}, hostname= {hostname}")

        settings.PamInfo = pam_info

    return settings


def clone_rdp_file(p_type, rdp_filename, clone_filename, server_name="", ip="", username=""):
    global gSettings, ErrorMessage
    rc = 1

    log_debug(sys._getframe().f_lineno, f"CloneRdpFile: pType= {p_type}, rdpFilename= '{rdp_filename}', cloneFilename= '{clone_filename}', serverName= '{server_name}'")

    content = ""
    try:
        with open(rdp_filename, "rb") as f:
            raw = f.read()
        if raw.startswith(b"\xff\xfe"):
            content = raw.decode("utf-16-le", errors="replace")
        elif raw.startswith(b"\xef\xbb\xbf"):
            content = raw.decode("utf-8-sig", errors="replace")
        else:
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("mbcs", errors="replace")
    except Exception as e:
        ErrorMessage = f"Cannot read file '{rdp_filename}'"
        log_error(sys._getframe().f_lineno, f"CloneRdpFile: {ErrorMessage}, error={e}")
        return -1, ""

    log_trace(sys._getframe().f_lineno, f"CloneRdpFile: Original content\n{content}")

    if gSettings.UseFontSmoothingDefined:
        f_val = "1" if gSettings.UseFontSmoothing else "0"
        if "allow font smoothing" in content:
            content = re.sub(r"(allow font smoothing:i):\d", rf"\1:{f_val}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"allow font smoothing:i:{f_val}\n"

    if gSettings.SessionBppDefined:
        if "session bpp" in content:
            content = re.sub(r"(session bpp:i):\d+", rf"\1:{gSettings.SessionBpp}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"session bpp:i:{gSettings.SessionBpp}\n"

    if gSettings.LocalDriveMappingDefined:
        if "drivestoredirect" in content:
            content = re.sub(r"(drivestoredirect:s):.*", rf"\1:{gSettings.LocalDriveMapping}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"drivestoredirect:s:{gSettings.LocalDriveMapping}\n"

    if gSettings.AllowWallpaperDefined:
        f_val = "0" if gSettings.AllowWallpaper else "1"
        if "disable wallpaper" in content:
            content = re.sub(r"(disable wallpaper:i):\d", rf"\1:{f_val}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"disable wallpaper:i:{f_val}\n"

        if "networkautodetect" in content:
            content = re.sub(r"(networkautodetect:i):\d", r"\1:0", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += "networkautodetect:i:0\n"

        if "connection type" in content:
            content = re.sub(r"(connection type:i):\d", r"\1:4", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += "connection type:i:4\n"

        if "bandwidthautodetect" in content:
            content = re.sub(r"(bandwidthautodetect:i):\d", r"\1:0", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += "bandwidthautodetect:i:0\n"

    if gSettings.AcceptSecurityMessagesDefined:
        f_val = "0" if gSettings.AcceptSecurityMessages else "2"
        if "authentication level" in content:
            content = re.sub(r"(authentication level:i):\d", rf"\1:{f_val}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"authentication level:i:{f_val}\n"

    if gSettings.UseSmartSizingDefined:
        f_val = "1" if gSettings.UseSmartSizing else "0"
        if "smart sizing" in content:
            content = re.sub(r"(smart sizing:i):\d", rf"\1:{f_val}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"smart sizing:i:{f_val}\n"

    ret_ip = ""

    if server_name:
        if p_type == PAM_TYPE_BEYONDTRUST:
            idx = -1
            for i, elm in enumerate(gSettings.PamInfo):
                match_pat = re.escape(elm)
                if re.search(rf"(full address:s):{match_pat}", content):
                    content = re.sub(rf"(full address:s):{match_pat}", rf"\1:{server_name}", content)
                    log_debug(sys._getframe().f_lineno, f"CloneRdpFile: Updated 'full address' to '{server_name}'")
                    idx = i // 3
                    break

            if idx == -1:
                ErrorMessage = f"PAM server entry not found in '{rdp_filename}'"
                log_warning(sys._getframe().f_lineno, f"CloneRdpFile: {ErrorMessage}")
                rc = 2
            else:
                ret_ip = gSettings.PamInfo[3 * idx]
                log_debug(sys._getframe().f_lineno, f"CloneRdpFile: ip= '{ret_ip}'")

        elif p_type in (PAM_TYPE_SENHASEGURA, PAM_TYPE_CYBERARK):
            if gSettings.PamInfo:
                ret_ip = gSettings.PamInfo[0]
            log_debug(sys._getframe().f_lineno, f"CloneRdpFile: ip= '{ret_ip}'")

            if "full address" in content:
                content = re.sub(r"(full address:s):.*", rf"\1:{server_name}", content)
            else:
                if not content.endswith("\n"): content += "\n"
                content += f"full address:s:{server_name}\n"

    if username:
        if "username" in content:
            content = re.sub(r"(username:s):.*", rf"\1:{username}", content)
        else:
            if not content.endswith("\n"): content += "\n"
            content += f"username:s:{username}\n"

    content = content.replace("\r\n", "\n").replace("\n\n", "\n") + "\n"

    try:
        if os.path.exists(clone_filename):
            os.remove(clone_filename)
        with open(clone_filename, "wb") as f:
            f.write(content.encode("utf-8"))
    except Exception as e:
        ErrorMessage = f"Cannot create RDP file '{clone_filename}'"
        log_error(sys._getframe().f_lineno, f"CloneRdpFile: {ErrorMessage}, error= {e}")
        rc = -3

    log_debug(sys._getframe().f_lineno, f"CloneRdpFile: finished, rc= {rc}")
    return rc, ret_ip


def start_program(server_name, command, title, timeout):
    global ErrorMessage
    log_debug(sys._getframe().f_lineno, f"StartProgram: serverName= '{server_name}', command= '{command}', title= '{title}', timeout= {timeout}")

    try:
        proc = subprocess.Popen(command)
        pid = proc.pid
    except Exception as e:
        ErrorMessage = "Program is not found or cannot be started"
        log_error(sys._getframe().f_lineno, f"StartProgram: {ErrorMessage}, lastError= {e}")
        return -1

    log_debug(sys._getframe().f_lineno, f"StartProgram: Run pid= {pid}")

    if win32gui and win32process:
        start_time = time.time()
        found_hwnd = None

        while (time.time() - start_time) < timeout:
            def enum_windows_callback(hwnd, extra):
                nonlocal found_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if win_pid == pid:
                        cls_name = win32gui.GetClassName(hwnd)
                        if "TscShellContainerClass" in cls_name or "mstsc" in cls_name.lower():
                            found_hwnd = hwnd
                            return False
                return True

            try:
                win32gui.EnumWindows(enum_windows_callback, None)
            except Exception:
                pass

            if found_hwnd:
                break
            time.sleep(0.5)

        if not found_hwnd:
            log_debug(sys._getframe().f_lineno, f"StartProgram: Window not found in time for pid= {pid}")
        else:
            try:
                win32gui.SetWindowText(found_hwnd, server_name)
                log_debug(sys._getframe().f_lineno, f"StartProgram: Changed window title to '{server_name}'")
            except Exception as e:
                log_error(sys._getframe().f_lineno, f"StartProgram: Failed to set window title: {e}")

            if gSettings.ScreenMode == "Maximize":
                try:
                    win32gui.ShowWindow(found_hwnd, win32con.SW_MAXIMIZE)
                    log_debug(sys._getframe().f_lineno, "StartProgram: Maximize window")
                except Exception:
                    pass

    log_debug(sys._getframe().f_lineno, "StartProgram: Program started")
    return pid


def regular(rdp_filename):
    global gSettings, ErrorMessage
    log_debug(sys._getframe().f_lineno, f"Regular: RDP filename='{rdp_filename}'")

    command_line = f'"{gSettings.Program}" "{rdp_filename}"'
    log_debug(sys._getframe().f_lineno, f"Regular: commandLine= '{command_line}'")

    try:
        proc = subprocess.Popen(command_line)
        log_debug(sys._getframe().f_lineno, f"Regular: Run pid= {proc.pid}")
    except Exception as e:
        ErrorMessage = "Program is not found or cannot be started"
        log_error(sys._getframe().f_lineno, f"Regular: {ErrorMessage}, error= {e}")
        return -1

    time.sleep(2)
    return 0


def beyond_trust(rdp_filename):
    global gSettings, gLockTimeout, ErrorMessage, gFilenameBase, PAM_TYPE_BEYONDTRUST

    m = re.search(r"(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.I)
    if m:
        server_name = m.group(1).replace(" ", "_")
    else:
        ErrorMessage = f"RDP filename '{rdp_filename}' has incorrect format"
        log_error(sys._getframe().f_lineno, f"BeyondTrust: {ErrorMessage}")
        return -1

    clone_filename = get_clone_filename(server_name)
    log_debug(sys._getframe().f_lineno, f"BeyondTrust: serverName= '{server_name}', cloneFilename= '{clone_filename}'")

    command_line = f'"{gSettings.Program}" "{clone_filename}"'
    if gSettings.ScreenMode == "Fullscreen":
        command_line += " /f"
    else:
        command_line += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"

    log_debug(sys._getframe().f_lineno, f"BeyondTrust: commandLine= '{command_line}'")

    if semaphore_acquire(gLockTimeout):
        rc, ip = clone_rdp_file(PAM_TYPE_BEYONDTRUST, rdp_filename, clone_filename, server_name)
        log_debug(sys._getframe().f_lineno, f"BeyondTrust: rdpFilename= {rdp_filename}, cloneFilename= {clone_filename}, serverName= {server_name}, ip= {ip}")

        update_hosts = (rc == 1)

        if rc < 0:
            log_error(sys._getframe().f_lineno, f"BeyondTrust: CloneRdpFile - {ErrorMessage}")
        else:
            if update_hosts:
                rc = update_hosts_file("add", ip, server_name)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"BeyondTrust: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
            else:
                log_warning(sys._getframe().f_lineno, "No update to hosts file")

            if rc >= 0:
                rc = start_program(server_name, command_line, "ahk_class TscShellContainerClass", gSettings.ConnectTimeout)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"BeyondTrust: StartProgram - {ErrorMessage}")
                else:
                    log_info(sys._getframe().f_lineno, f"BeyondTrust: mstsc session started to '{server_name}'")

                if update_hosts:
                    rc = update_hosts_file("remove", ip, server_name)
                    if rc < 0:
                        log_error(sys._getframe().f_lineno, f"BeyondTrust: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        semaphore_release()

        if gSettings.Cleanup:
            log_debug(sys._getframe().f_lineno, f"BeyondTrust: Deleting '{clone_filename}'")
            delete_file(clone_filename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        log_error(sys._getframe().f_lineno, f"BeyondTrust: {ErrorMessage}")
        rc = -1

    return rc


def symantec1(ip, port, server_name):
    global gSettings, gLockTimeout, ErrorMessage, gTemplateDefaultRdpFilename, PAM_TYPE_SYMANTEC

    if gSettings.MultiUser:
        server_name = f"{server_name}-{getpass.getuser()}"

    command_line = f'"{gSettings.Program}" /v:{server_name}:{port}'
    if gSettings.ScreenMode == "Fullscreen":
        command_line += " /f"
    else:
        command_line += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"

    log_debug(sys._getframe().f_lineno, f"Symantec1: commandLine= '{command_line}'")

    if semaphore_acquire(gLockTimeout):
        docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
        default_rdp_filename = os.path.join(docs_dir, "default.rdp")
        if not os.path.exists(default_rdp_filename) and os.path.exists(gTemplateDefaultRdpFilename):
            shutil.copy(gTemplateDefaultRdpFilename, default_rdp_filename)

        update_hosts = False
        if os.path.exists(default_rdp_filename):
            rc, _ = clone_rdp_file(PAM_TYPE_SYMANTEC, default_rdp_filename, default_rdp_filename)
            update_hosts = (rc == 1)
            if rc < 0:
                log_error(sys._getframe().f_lineno, f"Symantec1: CloneRdpFile - {ErrorMessage}")

        if update_hosts:
            rc = update_hosts_file("add", ip, server_name)
            if rc < 0:
                log_error(sys._getframe().f_lineno, f"Symantec1: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
        else:
            log_warning(sys._getframe().f_lineno, "No update to hosts file")

        if rc >= 0:
            rc = start_program(server_name, command_line, "ahk_class TscShellContainerClass", gSettings.ConnectTimeout)
            if rc < 0:
                log_error(sys._getframe().f_lineno, f"Symantec1: StartProgram - {ErrorMessage}")
            else:
                log_info(sys._getframe().f_lineno, f"Symantec1: mstsc started to {server_name}")

            if update_hosts:
                rc = update_hosts_file("remove", ip, server_name)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"Symantec1: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        semaphore_release()
        gSettings.Cleanup = False
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        log_error(sys._getframe().f_lineno, f"Symantec1: {ErrorMessage}")
        rc = -1

    return rc


def symantec2(rdp_filename):
    global gSettings, gLockTimeout, ErrorMessage, PAM_TYPE_SYMANTEC2

    if "~" in rdp_filename:
        rdp_filename = get_long_path_name(rdp_filename)

    base_name = os.path.splitext(os.path.basename(rdp_filename))[0]
    m = re.search(r"(.*_)?(.*)_PAMGateway", base_name, re.I)
    if m:
        server_name = m.group(2).replace(" ", "_")
        if gSettings.MultiUser:
            server_name = f"{server_name}-{getpass.getuser()}"
        clone_filename = get_clone_filename(server_name)
        log_debug(sys._getframe().f_lineno, f"Symantec2: serverName= '{server_name}', cloneFilename= '{clone_filename}'")
    else:
        ErrorMessage = f"RDP filename '{rdp_filename}' has incorrect format"
        log_error(sys._getframe().f_lineno, f"Symantec2: {ErrorMessage}")
        return -1

    command_line = f'"{gSettings.Program}" "{clone_filename}"'
    if gSettings.ScreenMode == "Fullscreen":
        command_line += " /f"
    else:
        command_line += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"

    log_debug(sys._getframe().f_lineno, f"Symantec2: commandLine= '{command_line}'")

    if semaphore_acquire(gLockTimeout):
        rc, ip = clone_rdp_file(PAM_TYPE_SYMANTEC2, rdp_filename, clone_filename, server_name)
        if rc < 0:
            log_error(sys._getframe().f_lineno, f"Symantec2: CloneRdpFile - {ErrorMessage}")
        else:
            log_debug(sys._getframe().f_lineno, "No update to hosts file required for Symantec2")
            rc = start_program(server_name, command_line, "ahk_class TscShellContainerClass", gSettings.ConnectTimeout)
            if rc < 0:
                log_error(sys._getframe().f_lineno, f"Symantec2: StartProgram - {ErrorMessage}")
            else:
                log_info(sys._getframe().f_lineno, f"Symantec2: mstsc session started to '{server_name}'")

        semaphore_release()

        if gSettings.Cleanup:
            log_debug(sys._getframe().f_lineno, f"Symantec2: Deleting '{clone_filename}'")
            delete_file(clone_filename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        log_error(sys._getframe().f_lineno, f"Symantec2: {ErrorMessage}")
        rc = -1

    return rc


def senhasegura(local_username, remote_username, port, server_name):
    global gSettings, gLockTimeout, ErrorMessage, gTemplateDefaultRdpFilename, PAM_TYPE_SENHASEGURA

    username = f"{local_username}[{remote_username}@{server_name}]"
    log_debug(sys._getframe().f_lineno, f"Senhasegura: username= '{username}'")

    if gSettings.MultiUser:
        server_name = f"{server_name}-{getpass.getuser()}"

    server_name = server_name.replace(" ", "_")
    clone_filename = get_clone_filename(server_name)

    docs_dir = os.path.join(os.path.expanduser("~"), "Documents")
    default_rdp_filename = os.path.join(docs_dir, "default.rdp")
    if not os.path.exists(default_rdp_filename) and os.path.exists(gTemplateDefaultRdpFilename):
        shutil.copy(gTemplateDefaultRdpFilename, default_rdp_filename)

    command_line = f'"{gSettings.Program}" "{clone_filename}"'
    if gSettings.ScreenMode == "Fullscreen":
        command_line += " /f"
    else:
        command_line += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"

    log_debug(sys._getframe().f_lineno, f"Senhasegura: commandLine= '{command_line}'")

    if semaphore_acquire(gLockTimeout):
        rc, ip = clone_rdp_file(PAM_TYPE_SENHASEGURA, default_rdp_filename, clone_filename, server_name, "", username)
        update_hosts = (rc == 1)

        if rc < 0:
            log_error(sys._getframe().f_lineno, f"Senhasegura: CloneRdpFile - {ErrorMessage}")
        else:
            if update_hosts:
                rc = update_hosts_file("add", ip, server_name)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"Senhasegura: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
            else:
                log_warning(sys._getframe().f_lineno, "No update to hosts file")

            if rc >= 0:
                rc = start_program(server_name, command_line, "ahk_class TscShellContainerClass", gSettings.ConnectTimeout)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"Senhasegura: StartProgram - {ErrorMessage}")
                else:
                    log_info(sys._getframe().f_lineno, f"Senhasegura: mstsc session started to '{server_name}'")

                if update_hosts:
                    rc = update_hosts_file("remove", ip, server_name)
                    if rc < 0:
                        log_error(sys._getframe().f_lineno, f"Senhasegura: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        semaphore_release()

        if gSettings.Cleanup:
            log_debug(sys._getframe().f_lineno, f"Senhasegura: Deleting '{clone_filename}'")
            delete_file(clone_filename)
        gSettings.Cleanup = False
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        log_error(sys._getframe().f_lineno, f"Senhasegura: {ErrorMessage}")
        rc = -1

    return rc


def cyber_ark(rdp_filename):
    global gSettings, gLockTimeout, ErrorMessage, PAM_TYPE_CYBERARK

    base_name = os.path.splitext(os.path.basename(rdp_filename))[0]
    m = re.search(r"(.*?), PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", base_name, re.I)
    if m:
        server_name = m.group(1).replace(" ", "_")
        if gSettings.MultiUser:
            server_name = f"{server_name}-{getpass.getuser()}"
        clone_filename = get_clone_filename(server_name)
        log_debug(sys._getframe().f_lineno, f"CyberArk: serverName= '{server_name}', cloneFilename= '{clone_filename}'")
    else:
        ErrorMessage = f"RDP filename '{rdp_filename}' has incorrect format"
        log_error(sys._getframe().f_lineno, f"CyberArk: {ErrorMessage}")
        return -1

    command_line = f'"{gSettings.Program}" "{clone_filename}"'
    if gSettings.ScreenMode == "Fullscreen":
        command_line += " /f"
    else:
        command_line += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"

    log_debug(sys._getframe().f_lineno, f"CyberArk: commandLine= '{command_line}'")

    if semaphore_acquire(gLockTimeout):
        rc, ip = clone_rdp_file(PAM_TYPE_CYBERARK, rdp_filename, clone_filename, server_name)
        update_hosts = (rc == 1)

        if rc < 0:
            log_error(sys._getframe().f_lineno, f"CyberArk: CloneRdpFile - {ErrorMessage}")
        else:
            if update_hosts:
                rc = update_hosts_file("add", ip, server_name)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"CyberArk: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
            else:
                log_warning(sys._getframe().f_lineno, "No update to hosts file")

            if rc >= 0:
                rc = start_program(server_name, command_line, "ahk_class TscShellContainerClass", gSettings.ConnectTimeout)
                if rc < 0:
                    log_error(sys._getframe().f_lineno, f"CyberArk: StartProgram - {ErrorMessage}")
                else:
                    log_info(sys._getframe().f_lineno, f"CyberArk: mstsc session started to '{server_name}'")

                if update_hosts:
                    rc = update_hosts_file("remove", ip, server_name)
                    if rc < 0:
                        log_error(sys._getframe().f_lineno, f"CyberArk: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        semaphore_release()

        if gSettings.Cleanup:
            log_debug(sys._getframe().f_lineno, f"CyberArk: Deleting '{clone_filename}'")
            delete_file(clone_filename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        log_error(sys._getframe().f_lineno, f"CyberArk: {ErrorMessage}")
        rc = -1

    return rc


def main():
    global gLogFile, gLogLevel, gSettings, gLockTimeout
    global gFilenameFull, gFilenamePath, gFilenameBase, gFilenameExt, gTemplateDefaultRdpFilename

    log_roll(gLogFile, 5, 5)

    args = sys.argv[1:]
    log_debug(sys._getframe().f_lineno, f"main: start -------------- ")
    log_debug(sys._getframe().f_lineno, f"main: version= {gVersion}")
    log_debug(sys._getframe().f_lineno, f"main: CommandLine ArgCount: {len(args)}")

    for n, param in enumerate(args, 1):
        log_debug(sys._getframe().f_lineno, f"main: CommandLine Arg[{n}]= '{param}'")

    if len(args) == 1:
        if re.search(r"^(--|-|/)(Ver|Version)$", args[0], re.I):
            msg_box(f"Version {gVersion}", gProgramTitle, 0x40)
            sys.exit(0)
        if re.search(r"^(--|-|/)(Lic|Licens)$", args[0], re.I):
            msg_box(f"License {gVersion}", gProgramTitle, 0x40)
            sys.exit(0)

    script_path = os.path.abspath(sys.argv[0])
    script_dir = os.path.dirname(script_path)
    script_name = os.path.splitext(os.path.basename(script_path))[0]

    gTemplateDefaultRdpFilename = os.path.join(script_dir, "Template-Default.rdp")

    system_prop_filename = os.path.join(script_dir, f"{script_name}.system.properties")
    gSettings = read_properties(system_prop_filename, PROPERTY_TYPE_SYSTEM)

    default_prop_filename = os.path.join(script_dir, f"{script_name}.user.properties")
    user_prop_path = os.path.join(os.environ.get("APPDATA", ""), "PAM-Exchange", "PAM-RDP-Connect")
    user_prop_filename = os.path.join(user_prop_path, f"{script_name}.user.properties")

    if not os.path.exists(user_prop_filename):
        try:
            os.makedirs(user_prop_path, exist_ok=True)
            if os.path.exists(default_prop_filename):
                shutil.copy(default_prop_filename, user_prop_filename)
        except Exception as e:
            log_error(sys._getframe().f_lineno, f"main: Failed copying user properties: {e}")

    gSettings = read_properties(user_prop_filename, PROPERTY_TYPE_USER, gSettings)
    gLockTimeout = 1000 * (1 + gSettings.ConnectTimeout)

    if gSettings.Heartbeat:
        hb_prog = gSettings.HeartbeatProgram
        if os.path.exists(hb_prog):
            log_info(sys._getframe().f_lineno, f"main: Starting heartbeat program '{hb_prog}'")
            try:
                subprocess.Popen([hb_prog])
            except Exception as e:
                log_error(sys._getframe().f_lineno, f"main: Cannot start heartbeat program '{hb_prog}', lastError= {e}")
        else:
            log_error(sys._getframe().f_lineno, f"main: Heartbeat program '{hb_prog}' is not found")

    if len(args) == 1:
        filename = args[0]
        log_debug(sys._getframe().f_lineno, f"main: regular - args[1]= '{filename}'")

        if filename.lower().endswith(".rdp"):
            gFilenameFull = filename
            if "~" in gFilenameFull:
                gFilenameFull = get_long_path_name(gFilenameFull)
                log_debug(sys._getframe().f_lineno, f"main: regular - Long gFilenameFull= '{gFilenameFull}'")

            gFilenamePath = os.path.dirname(gFilenameFull)
            gFilenameBase = os.path.splitext(os.path.basename(gFilenameFull))[0]
            gFilenameExt = os.path.splitext(gFilenameFull)[1]

            if gSettings.PamType == PAM_TYPE_BEYONDTRUST and re.search(r"(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.I):
                log_debug(sys._getframe().f_lineno, "main: regular - Beyondtrust .rdp filename, continue")
            elif gSettings.PamType == PAM_TYPE_SYMANTEC and re.search(r"_PAMGateway", gFilenameBase, re.I):
                gSettings.PamType = PAM_TYPE_SYMANTEC2
                log_debug(sys._getframe().f_lineno, "main: regular - Symantec PAMGateway filename, continue")
            elif gSettings.PamType == PAM_TYPE_CYBERARK and re.search(r"PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.I):
                log_debug(sys._getframe().f_lineno, "main: regular - CyberArk .rdp filename, continue")
            else:
                log_debug(sys._getframe().f_lineno, f"main: call Regular using gFilenameFull= '{gFilenameFull}'")
                rc = regular(gFilenameFull)
                log_debug(sys._getframe().f_lineno, f"main: regular - finished, rc= {rc}")
                end_script()
        else:
            log_debug(sys._getframe().f_lineno, "main: regular - not an .rdp file as argument, continue")

    if gSettings.PamType == PAM_TYPE_BEYONDTRUST:
        if len(args) != 1 or not re.search(r"(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.I):
            msg_box(f"This program requires 1 parameter\n\npam-rdp c:\\.....\\SQL2-d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp", gProgramTitle, 0x10)
            end_script()

        log_debug(sys._getframe().f_lineno, f"main: call BeyondTrust using filename= '{gFilenameFull}'")
        rc = beyond_trust(gFilenameFull)
        if rc < 0:
            log_error(sys._getframe().f_lineno, f"main: BeyondTrust - ErrorMessage= '{ErrorMessage}'")
            msg_box(ErrorMessage, gProgramTitle, 0x10)
        log_debug(sys._getframe().f_lineno, f"main: BeyondTrust - finished, rc= {rc}")

    elif gSettings.PamType == PAM_TYPE_SYMANTEC:
        invalid_args = False
        if len(args) >= 3:
            ip = args[0]
            port = args[1]
            device_name = " ".join(args[2:]).strip().replace(" ", "_")
        else:
            invalid_args = True

        if invalid_args:
            msg_box("This program requires 3 parameters\n\npam-rdp <Local IP> <First Port> <Device Name>", gProgramTitle, 0x10)
            end_script()

        log_debug(sys._getframe().f_lineno, f"main: Call Symantec using ip= '{ip}', port= '{port}', name= '{device_name}'")
        rc = symantec1(ip, port, device_name)
        if rc < 0:
            log_error(sys._getframe().f_lineno, f"main: Symantec - ErrorMessage= '{ErrorMessage}'")
            msg_box(ErrorMessage, gProgramTitle, 0x10)
        log_debug(sys._getframe().f_lineno, f"main: Symantec - finished, rc= {rc}")
        gSettings.Cleanup = False

    elif gSettings.PamType == PAM_TYPE_SYMANTEC2:
        if len(args) != 1 or not re.search(r"(.*_)?(.*)_PAMGateway", gFilenameBase, re.I):
            msg_box("This program requires 1 or 3 parameters\n\n1: pam-rdp <filename.rdp\n\n3: pam-rdp <Local IP> <First Port> <Device Name>", gProgramTitle, 0x10)
            end_script()

        log_debug(sys._getframe().f_lineno, f"main: Call Symantec2 using filename= '{gFilenameFull}'")
        rc = symantec2(gFilenameFull)
        if rc < 0:
            log_error(sys._getframe().f_lineno, f"main: Symantec2 - ErrorMessage= '{ErrorMessage}'")
            msg_box(ErrorMessage, gProgramTitle, 0x10)
        log_debug(sys._getframe().f_lineno, f"main: Symantec2 - finished, rc= {rc}")

    elif gSettings.PamType == PAM_TYPE_SENHASEGURA:
        invalid_args = False
        local_username = ""
        remote_username = ""
        device_name = ""

        if len(args) >= 1:
            username_arg = args[0]
            log_debug(sys._getframe().f_lineno, f"main: Senhasegura - username= '{username_arg}'")

            m = re.match(r"(.*?)\[(.*)@(.*)\]$", username_arg)
            if m:
                local_username = m.group(1)
                remote_username = m.group(2)
                device_name = m.group(3)
            else:
                if len(args) >= 3:
                    local_username = args[0]
                    remote_username = args[1]
                    device_name = " ".join(args[2:])

            if local_username and remote_username and device_name:
                device_name = device_name.strip().replace(" ", "_")
            else:
                invalid_args = True
        else:
            invalid_args = True

        if invalid_args:
            msg_box("Incorrect format for connection to Senhasegura\n\nUse \npam-rdp <localUsername>[remoteUsername@serverName]\n\nor\n\npam-rdp <localUsername> <remoteUsername> <serverName>", gProgramTitle, 0x10)
            end_script()

        log_debug(sys._getframe().f_lineno, f"main: Call Senhasegura using localUsername= '{local_username}', remoteUsername= '{remote_username}', name= '{device_name}', port= {gSettings.Port}")
        rc = senhasegura(local_username, remote_username, gSettings.Port, device_name)
        if rc < 0:
            log_error(sys._getframe().f_lineno, f"main: Senhasegura - ErrorMessage= '{ErrorMessage}'")
            msg_box(ErrorMessage, gProgramTitle, 0x10)
        log_debug(sys._getframe().f_lineno, f"main: Senhasegura - finished, rc= {rc}")
        gSettings.Cleanup = False

    elif gSettings.PamType == PAM_TYPE_CYBERARK:
        if len(args) != 1 or not re.search(r"(.*?), PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.I):
            msg_box("This program requires 1 parameter\n\npam-rdp c:\\.....\\SQL2, PSM Address.d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp", gProgramTitle, 0x10)
            end_script()

        log_debug(sys._getframe().f_lineno, f"main: call CyberArk using gFilenameFull= '{gFilenameFull}'")
        rc = cyber_ark(gFilenameFull)
        if rc < 0:
            log_error(sys._getframe().f_lineno, f"main: CyberArk - ErrorMessage= '{ErrorMessage}'")
            msg_box(ErrorMessage, gProgramTitle, 0x10)
        log_debug(sys._getframe().f_lineno, f"main: CyberArk - finished, rc= {rc}")

    if gSettings.Cleanup:
        log_debug(sys._getframe().f_lineno, f"main: Cleanup - Deleting '{gFilenameFull}'")
        delete_file(gFilenameFull)
    else:
        log_debug(sys._getframe().f_lineno, f"main: Cleanup - No cleanup done '{gFilenameFull}'")

    end_script()


if __name__ == "__main__":
    main()
