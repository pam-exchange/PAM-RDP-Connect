'''
MIT License

Copyright (c) 2024-2025 PAM-Exchange

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

import sys
import os
import re
import time
import math
import logging
import shutil
import subprocess
import configparser
import tempfile
import datetime
import ctypes

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import win32file
    import win32pipe
    import win32gui
    import win32process
    import win32con
    import win32api
except ImportError:
    pass

# Information about the script
gScriptName = "pam-rdp"
gVersion = "2.9.0"
gProgramTitle = "PAM RDP Connect"

gSelfPid = os.getpid()
gSelfPidHex = f"{gSelfPid:04x}"

gTempDir = tempfile.gettempdir()
gLockFilename = os.path.join(gTempDir, f"{gScriptName}.lock")
gLockFileObj = None
gPipeName = "PAM-RDP-SERVICE"

# Constants for Logging
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

gLogFile = os.path.join(gTempDir, f"{gScriptName}.log")
gLogLevel = LOG_DEBUG
ErrorMessage = ""


def log_roll(filename, max_size_mb=5, keep=5):
    if max_size_mb < 1:
        max_size_mb = 1
    try:
        size_mb = os.path.getsize(filename) / (1024 * 1024)
    except Exception:
        size_mb = 0

    if size_mb >= max_size_mb:
        while keep > 1:
            fn1 = f"{filename}.{keep}"
            fn2 = f"{filename}.{keep - 1}"
            if os.path.exists(fn2):
                try:
                    shutil.move(fn2, fn1)
                except Exception:
                    pass
            keep -= 1
        if os.path.exists(filename):
            try:
                shutil.move(filename, fn2)
            except Exception:
                pass


log_roll(gLogFile, 5, 5)


def log_msg(level, line, msg):
    global gLogLevel, gSelfPidHex, gLogFile
    if level <= gLogLevel:
        level_txt = {
            LOG_ALWAYS: "ALW",
            LOG_ERROR: "ERR",
            LOG_WARNING: "WRN",
            LOG_INFO: "INF",
            LOG_DEBUG: "DBG",
            LOG_TRACE: "TRC"
        }.get(level, "DBG")

        time_str = datetime.datetime.now().strftime("%y/%m/%d %H:%M:%S")
        txt = f"{time_str} [{gSelfPidHex}] {level_txt} {msg} [{line}]\n"
        try:
            with open(gLogFile, "a", encoding="utf-8") as h:
                h.write(txt)
        except Exception:
            pass


def logTrace(line, msg):
    log_msg(LOG_TRACE, line, msg)


def logDebug(line, msg):
    log_msg(LOG_DEBUG, line, msg)


def logInfo(line, msg):
    log_msg(LOG_INFO, line, msg)


def logWarning(line, msg):
    log_msg(LOG_WARNING, line, msg)


def logError(line, msg):
    log_msg(LOG_ERROR, line, msg)


def logAlways(line, msg):
    log_msg(LOG_ALWAYS, line, msg)


def show_msg_box(text, title=gProgramTitle, timeout=None):
    try:
        MB_OK = 0x00000000
        MB_ICONINFORMATION = 0x00000040
        MB_ICONERROR = 0x00000010

        style = MB_OK
        if "IconX" in str(timeout) or "Error" in title or ErrorMessage:
            style |= MB_ICONERROR
        else:
            style |= MB_ICONINFORMATION

        timeout_sec = 0
        if timeout:
            m = re.search(r"T(\d+)", str(timeout))
            if m:
                timeout_sec = int(m.group(1))

        if timeout_sec > 0 and hasattr(ctypes, "windll"):
            # MessageBoxTimeoutW(hwnd, text, title, type, language_id, timeout_ms)
            ctypes.windll.user32.MessageBoxTimeoutW(
                0, text, title, style, 0, timeout_sec * 1000
            )
        elif 'win32gui' in sys.modules:
            win32gui.MessageBox(0, text, title, style)
        else:
            print(f"[{title}] {text}")
    except Exception:
        print(f"[{title}] {text}")


class Settings:
    def __init__(self):
        self.PropertyFilename = ""
        # User settings
        self.LogLevel = LOG_DEBUG
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

        # System settings
        self.pamType = PAM_TYPE_BEYONDTRUST
        self.Heartbeat = True
        self.HeartbeatProgram = r"C:\Program Files\PAM-Exchange\PAM-RDP-Heartbeat\pam-rdp-heartbeat.exe"
        self.Program = r"C:\Windows\system32\mstsc.exe"
        self.MultiUser = False
        self.Port = 4489
        self.CntServer = 0
        self.PamInfo = []


def ini_read(filename, section, option, default_val):
    config = configparser.ConfigParser(strict=False)
    try:
        config.read(filename, encoding='utf-8')
        if config.has_section(section) and config.has_option(section, option):
            val = config.get(section, option)
            return val
    except Exception:
        pass
    return default_val


def read_properties(filename, p_type=PROPERTY_TYPE_USER, settings=None):
    global gLogLevel
    if settings is None:
        settings = Settings()

    logDebug(sys._getframe().f_back.f_lineno if sys._getframe().f_back else 0,
             f"readProperties: pType= {p_type}, filename= {filename}")

    if p_type == 0:
        p_type = PROPERTY_TYPE_USER

    if not os.path.exists(filename):
        logAlways(sys._getframe().f_back.f_lineno if sys._getframe().f_back else 0,
                  f"readProperties: file not found '{filename}' - use defaults")

    settings.PropertyFilename = filename

    if p_type == PROPERTY_TYPE_USER:
        def_not_set = "Not Set"
        def_screen_mode = "Fullscreen"
        def_window_width = 1024
        def_window_height = 768
        def_use_font_smoothing = "true"
        def_session_bpp = 24
        def_local_drive_mapping = ""
        def_allow_wallpaper = "false"
        def_accept_security_messages = "true"
        def_use_smart_sizing = "false"
        def_cleanup = "true"
        def_log_level = "DEBUG"
        def_connect_timeout = 60
        def_prompt_timeout = 15

        x = ini_read(filename, "main", "LogLevel", def_log_level).upper()
        if x == "ERROR":
            settings.LogLevel = LOG_ERROR
        elif x == "WARNING":
            settings.LogLevel = LOG_WARNING
        elif x == "INFO":
            settings.LogLevel = LOG_INFO
        elif x == "DEBUG":
            settings.LogLevel = LOG_DEBUG
        elif x == "TRACE":
            settings.LogLevel = LOG_TRACE
        else:
            settings.LogLevel = LOG_DEBUG
        gLogLevel = settings.LogLevel
        logAlways(0, f"ReadProperties: LogLevel= '{settings.LogLevel}'")

        x = ini_read(filename, "main", "cleanup", def_not_set)
        settings.CleanupDefined = (x != def_not_set)
        settings.Cleanup = "false" not in x.lower()

        x = ini_read(filename, "main", "ConnectTimeout", str(def_connect_timeout))
        try:
            val_int = int(x)
            if val_int <= 0 or val_int >= 900:
                val_int = def_connect_timeout
        except ValueError:
            val_int = def_connect_timeout
        settings.ConnectTimeout = val_int

        x = ini_read(filename, "main", "promptTimeout", str(def_prompt_timeout))
        try:
            val_int = int(x)
            if val_int <= 0 or val_int >= 60:
                val_int = def_prompt_timeout
        except ValueError:
            val_int = def_prompt_timeout
        settings.PromptTimeout = val_int

        x = ini_read(filename, "main", "screenMode", def_not_set)
        settings.ScreenModeDefined = (x != def_not_set)
        if not re.search(r"(Window|Fullscreen|Maximize)", x, re.IGNORECASE):
            x = "Fullscreen"
        settings.ScreenMode = x

        if settings.ScreenMode.lower() == "fullscreen":
            loc_width = def_window_width
            loc_height = def_window_height
        elif settings.ScreenMode.lower() == "maximize":
            settings.ScreenMode = "Maximize"
            loc_width = win32api.GetSystemMetrics(0) if 'win32api' in sys.modules else 1024
            loc_height = win32api.GetSystemMetrics(1) if 'win32api' in sys.modules else 768
        elif settings.ScreenMode.lower() == "window":
            settings.ScreenMode = "Window"
            lw = ini_read(filename, "main", "windowWidth", str(def_window_width))
            try:
                loc_width = int(lw)
                if loc_width <= 0:
                    loc_width = def_window_width
            except ValueError:
                loc_width = def_window_width

            lh = ini_read(filename, "main", "windowHeight", str(def_window_height))
            try:
                loc_height = int(lh)
                if loc_height <= 0:
                    loc_height = def_window_height
            except ValueError:
                loc_height = def_window_height
        else:
            settings.ScreenMode = "Fullscreen"
            loc_width = def_window_width
            loc_height = def_window_height

        settings.WindowWidth = int(loc_width)
        settings.WindowHeight = int(loc_height)

        x = ini_read(filename, "main", "UseFontSmoothing", def_not_set)
        settings.UseFontSmoothingDefined = (x != def_not_set)
        settings.UseFontSmoothing = "true" in x.lower()

        x = ini_read(filename, "main", "wallpaper", def_not_set)
        settings.AllowWallpaperDefined = (x != def_not_set)
        settings.AllowWallpaper = "true" in x.lower()

        x = ini_read(filename, "main", "sessionBpp", def_not_set)
        settings.SessionBppDefined = (x != def_not_set)
        try:
            val_bpp = int(x)
            if val_bpp not in [16, 24, 32]:
                val_bpp = def_session_bpp
        except ValueError:
            val_bpp = def_session_bpp
        settings.SessionBpp = val_bpp

        x = ini_read(filename, "main", "localDriveMapping", def_not_set)
        settings.LocalDriveMappingDefined = (x != def_not_set)
        settings.LocalDriveMapping = x

        x = ini_read(filename, "main", "acceptSecurityMessages", def_not_set)
        settings.AcceptSecurityMessagesDefined = (x != def_not_set)
        settings.AcceptSecurityMessages = "true" in x.lower()

        x = ini_read(filename, "main", "useSmartSizing", def_not_set)
        settings.UseSmartSizingDefined = (x != def_not_set)
        settings.UseSmartSizing = "true" in x.lower()

    if p_type == PROPERTY_TYPE_SYSTEM:
        def_pam_type = PAM_TYPE_BEYONDTRUST
        def_heartbeat = "true"
        def_heartbeat_program = r"C:\Program Files\PAM-Exchange\PAM-RDP-Heartbeat\pam-rdp-heartbeat.exe"
        def_program = r"C:\Windows\system32\mstsc.exe"
        def_multi_user = "false"

        x = ini_read(filename, "main", "PAMtype", def_pam_type)
        match = f"({PAM_TYPE_BEYONDTRUST}|{PAM_TYPE_SYMANTEC}|{PAM_TYPE_SENHASEGURA}|{PAM_TYPE_CYBERARK})"
        if not re.search(match, x, re.IGNORECASE):
            x = PAM_TYPE_BEYONDTRUST
            logWarning(0, "ReadProperties: PamType not OK, using default")
        settings.pamType = x

        x = ini_read(filename, "main", "heartbeat", def_heartbeat)
        settings.Heartbeat = "true" in x.lower()

        if settings.Heartbeat:
            x = ini_read(filename, "main", "heartbeatprogram", def_heartbeat_program)
            settings.HeartbeatProgram = x

        x = ini_read(filename, "main", "mstscProgram", def_program)
        settings.Program = x

        x = ini_read(filename, "main", "multiUser", def_multi_user)
        settings.MultiUser = "true" in x.lower()

        def_port = 4489 if settings.pamType == PAM_TYPE_BEYONDTRUST else 3389
        x = ini_read(filename, settings.pamType, "Port", str(def_port))
        try:
            settings.Port = int(x)
        except ValueError:
            settings.Port = def_port

        def_cnt_server = "0"
        x = ini_read(filename, settings.pamType, "cntServer", def_cnt_server)
        try:
            settings.CntServer = int(x)
        except ValueError:
            settings.CntServer = 0

        pam_info = []
        err = "ERROR"
        for i in range(1, settings.CntServer + 1):
            sec = f"Server{i}"
            x_val = ini_read(filename, sec, "ip", err)
            y_val = ini_read(filename, sec, "dns", err)
            z_val = ini_read(filename, sec, "hostname", err)
            if err not in (x_val, y_val, z_val):
                pam_info.append(x_val)
                pam_info.append(y_val)
                pam_info.append(z_val)
                logDebug(0, f"ReadProperties: server - index= {i}, ip= {x_val}, dns= {y_val}, hostname= {z_val}")
            else:
                logError(0, f"ReadProperties: server - index= {i}, ip= {x_val}, dns= {y_val}, hostname= {z_val}")
        settings.PamInfo = pam_info

    return settings


def SemaphoreAcquire(timeout_ms):
    global gLockFilename, gLockFileObj, ErrorMessage

    end_time = time.time() + (timeout_ms / 1000.0)

    while True:
        try:
            f = open(gLockFilename, "a+b")
            if msvcrt:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            gLockFileObj = f
            logDebug(sys._getframe().f_back.f_lineno if sys._getframe().f_back else 0,
                     f"SemaphoreAcquire: acquired - lockFilename= '{gLockFilename}'")
            return 1
        except Exception as e:
            if 'f' in locals() and f:
                try:
                    f.close()
                except Exception:
                    pass
            logDebug(sys._getframe().f_back.f_lineno if sys._getframe().f_back else 0,
                     f"SemaphoreAcquire: waiting - lockFilename= '{gLockFilename}', err= {e}")

        time.sleep(1)
        if time.time() > end_time:
            break

    ErrorMessage = "Timeout waiting for semaphore."
    logError(0, f"SemaphoreAcquire: {ErrorMessage}")
    return 0


def SemaphoreRelease():
    global gLockFileObj
    if gLockFileObj:
        try:
            if msvcrt:
                msvcrt.locking(gLockFileObj.fileno(), msvcrt.LK_UNLCK, 1)
            gLockFileObj.close()
            logDebug(0, "SemaphoreRelease: released")
        except Exception:
            pass
        gLockFileObj = None


def PipeMessage(msg, pipename="", timeout=10000):
    global gPipeName, ErrorMessage

    rc = 0
    ErrorMessage = ""
    if not pipename:
        pipename = gPipeName

    full_pipe_path = fr"\\.\pipe\{pipename}"
    logDebug(0, f"PipeMessage: msg= '{msg}', pipename= '{pipename}', timeout= {timeout}")

    try:
        win32pipe.WaitNamedPipe(full_pipe_path, timeout)
        handle = win32file.CreateFile(
            full_pipe_path,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        if not handle or handle == win32file.INVALID_HANDLE_VALUE:
            ErrorMessage = "CreateFile failed"
            logError(0, f"PipeMessage: {ErrorMessage}")
            return -2

        msg_bytes = msg.encode('ascii')
        win32file.WriteFile(handle, msg_bytes)

        hr, resp_bytes = win32file.ReadFile(handle, 1024)
        rsp = resp_bytes.decode('ascii', errors='ignore')
        logDebug(0, f"PipeMessage: rsp= -->{rsp}<--")

        if rsp.startswith("OK"):
            rc = 1
        else:
            ErrorMessage = rsp
            logError(0, f"PipeMessage: rsp= {ErrorMessage}")
            rc = -4

        win32file.CloseHandle(handle)
    except Exception as e:
        ErrorMessage = f"PipeMessage exception: {str(e)}"
        logError(0, f"PipeMessage: {ErrorMessage}")
        rc = -1

    return rc


def UpdateHostsFile(cmd, ip, hostname):
    logDebug(0, f"UpdateHostsFile: cmd= '{cmd}', ip= '{ip}', hostname= '{hostname}'")
    msg = f"{cmd} {ip} {hostname}"
    logDebug(0, f"UpdateHostsFile: msg= '{msg}'")
    rc = PipeMessage(msg)
    return rc


def get_long_path_name(path):
    if 'win32api' in sys.modules:
        try:
            return win32api.GetLongPathName(path)
        except Exception:
            pass
    return os.path.abspath(path)


def deleteFile(filename):
    global ErrorMessage
    logDebug(0, f"deleteFile: Deleting '{filename}'")
    try:
        if os.path.exists(filename):
            os.remove(filename)
        logInfo(0, f"deleteFile: Deleted file '{filename}'")
    except Exception as e:
        ErrorMessage = f"Cannot delete file '{filename}'"
        logError(0, f"deleteFile: {ErrorMessage}")
        logDebug(0, f"deleteFile: {e}")


def getCloneFilename(serverName):
    clone_filepath = gTempDir
    logDebug(0, f"getCloneFilename: cloneFilepath= '{clone_filepath}'")
    if "~" in clone_filepath:
        clone_filepath = get_long_path_name(clone_filepath)
        logDebug(0, f"getCloneFilename: Long cloneFilepath= '{clone_filepath}'")

    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    clone_filename = os.path.join(clone_filepath, f"PAM-RDP-{serverName}-{ts}.rdp")
    logDebug(0, f"getCloneFilename: serverName= '{serverName}', cloneFilename= '{clone_filename}'")
    return clone_filename


def CloneRdpFile(p_type, rdp_filename, clone_filename, server_name="", ip_out_list=None, username=""):
    global gSettings, ErrorMessage
    rc = 1

    logDebug(0, f"CloneRdpFile: pType= {p_type}, rdpFilename= '{rdp_filename}', cloneFilename= '{clone_filename}', serverName= '{server_name}'")

    try:
        with open(rdp_filename, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        ErrorMessage = f"Cannot read file '{rdp_filename}'"
        logError(0, f"CloneRdpFile: {ErrorMessage}, error={e}")
        return -1

    logTrace(0, f"CloneRdpFile: Original content\n{content}")

    # font smoothing
    if gSettings.UseFontSmoothingDefined:
        f_val = "1" if gSettings.UseFontSmoothing else "0"
        if re.search(r"allow font smoothing", content, re.IGNORECASE):
            logDebug(0, f"CloneRdpFile: Updating 'allow font smoothing' to '{f_val}'")
            content = re.sub(r"(allow font smoothing:i):\d", rf"\1:{f_val}", content, flags=re.IGNORECASE)
        else:
            logDebug(0, f"CloneRdpFile: Adding 'allow font smoothing' with '{f_val}'")
            if not content.endswith("\n"):
                content += "\n"
            content += f"allow font smoothing:i:{f_val}\n"

    # session bpp
    if gSettings.SessionBppDefined:
        if re.search(r"session bpp", content, re.IGNORECASE):
            logDebug(0, f"CloneRdpFile: Updating 'session bpp' to '{gSettings.SessionBpp}'")
            content = re.sub(r"(session bpp:i):\d+", rf"\1:{gSettings.SessionBpp}", content, flags=re.IGNORECASE)
        else:
            logDebug(0, f"CloneRdpFile: Adding 'session bpp' with '{gSettings.SessionBpp}'")
            if not content.endswith("\n"):
                content += "\n"
            content += f"session bpp:i:{gSettings.SessionBpp}\n"

    # drive mapping
    if gSettings.LocalDriveMappingDefined:
        if re.search(r"drivestoredirect", content, re.IGNORECASE):
            logDebug(0, f"CloneRdpFile: Updating 'drivestoredirect' to '{gSettings.LocalDriveMapping}'")
            content = re.sub(r"(drivestoredirect:s):.*", rf"\1:{gSettings.LocalDriveMapping}", content, flags=re.IGNORECASE)
        else:
            logDebug(0, f"CloneRdpFile: Adding 'drivestoredirect' with '{gSettings.LocalDriveMapping}'")
            if not content.endswith("\n"):
                content += "\n"
            content += f"drivestoredirect:s:{gSettings.LocalDriveMapping}\n"

    # wallpaper
    if gSettings.AllowWallpaperDefined:
        f_val = "1" if gSettings.AllowWallpaper else "0"
        if re.search(r"disable wallpaper", content, re.IGNORECASE):
            logDebug(0, f"CloneRdpFile: Updating 'disable wallpaper' to '{f_val}'")
            content = re.sub(r"(disable wallpaper:i):\d", rf"\1:{f_val}", content, flags=re.IGNORECASE)
        else:
            logDebug(0, f"CloneRdpFile: Adding 'disable wallpaper' with '{f_val}'")
            if not content.endswith("\n"):
                content += "\n"
            content += f"disable wallpaper:i:{f_val}\n"

        if re.search(r"networkautodetect", content, re.IGNORECASE):
            content = re.sub(r"(networkautodetect:i):\d", r"\1:0", content, flags=re.IGNORECASE)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += "networkautodetect:i:0\n"

        if re.search(r"connection type", content, re.IGNORECASE):
            content = re.sub(r"(connection type:i):\d", r"\1:4", content, flags=re.IGNORECASE)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += "connection type:i:4\n"

        if re.search(r"bandwidthautodetect", content, re.IGNORECASE):
            content = re.sub(r"(bandwidthautodetect:i):\d", r"\1:0", content, flags=re.IGNORECASE)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += "bandwidthautodetect:i:0\n"

    # accept security messages
    if gSettings.AcceptSecurityMessagesDefined:
        f_val = "0" if gSettings.AcceptSecurityMessages else "2"
        if re.search(r"authentication level", content, re.IGNORECASE):
            content = re.sub(r"(authentication level:i):\d", rf"\1:{f_val}", content, flags=re.IGNORECASE)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += f"authentication level:i:{f_val}\n"

    # smart sizing
    if gSettings.UseSmartSizingDefined:
        f_val = "1" if gSettings.UseSmartSizing else "0"
        if re.search(r"smart sizing", content, re.IGNORECASE):
            content = re.sub(r"(smart sizing:i):\d", rf"\1:{f_val}", content, flags=re.IGNORECASE)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += f"smart sizing:i:{f_val}\n"

    ip = ""
    if len(server_name) > 0:
        if p_type == PAM_TYPE_BEYONDTRUST:
            idx = -1
            for i, elm in enumerate(gSettings.PamInfo):
                match = elm.replace(".", r"\.")
                pattern = r"(full address:s):" + match + r"(:\d+)?"
                content, found_cnt = re.subn(pattern, rf"\1:{server_name}", content, flags=re.IGNORECASE)
                if found_cnt > 0:
                    logDebug(0, f"CloneRdpFile: Updated 'full address' to '{server_name}'")
                    idx = math.floor(i / 3)
                    logDebug(0, f"CloneRdpFile: found i={i}, idx={idx}, elm={elm}")
                    break
            if idx == -1:
                ErrorMessage = f"PAM server entry not found in '{rdp_filename}'"
                logWarning(0, f"CloneRdpFile: {ErrorMessage}")
                rc = 2
            else:
                ip = gSettings.PamInfo[3 * idx]
                logDebug(0, f"CloneRdpFile: ip= '{ip}'")

        if p_type in (PAM_TYPE_SENHASEGURA, PAM_TYPE_CYBERARK):
            if len(gSettings.PamInfo) > 0:
                ip = gSettings.PamInfo[0]
            logDebug(0, f"CloneRdpFile: ip= '{ip}'")

            if re.search(r"full address", content, re.IGNORECASE):
                content = re.sub(r"(full address:s):.*", rf"\1:{server_name}", content, flags=re.IGNORECASE)
            else:
                if not content.endswith("\n"):
                    content += "\n"
                content += f"full address:s:{server_name}\n"

    if ip_out_list is not None and isinstance(ip_out_list, list):
        ip_out_list.append(ip)

    if len(username) > 0:
        if re.search(r"username", content, re.IGNORECASE):
            content = re.sub(r"(username:s):.*", rf"\1:{username}", content, flags=re.IGNORECASE)
        else:
            if not content.endswith("\n"):
                content += "\n"
            content += f"username:s:{username}\n"

    content = content.replace("\r\n", "\n").replace("\n\n", "\n")
    if not content.endswith("\n"):
        content += "\n"

    logTrace(0, f"CloneRdpFile: Updated content\n{content}")

    try:
        if os.path.exists(clone_filename):
            os.remove(clone_filename)
        with open(clone_filename, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
    except Exception as e:
        ErrorMessage = f"Cannot create RDP file '{clone_filename}'"
        logError(0, f"CloneRdpFile: {ErrorMessage}, lastError= {e}")
        rc = -3

    logDebug(0, f"CloneRdpFile: finished, rc= {rc}")
    return rc


def StartProgram(serverName, command, title, timeout):
    global ErrorMessage, gSettings

    logDebug(0, f"StartProgram: serverName= '{serverName}', command= '{command}', title= '{title}', timeout= {timeout}")

    use_class = False
    class_name = ""
    m = re.match(r"^ahk_class\s+(.*)$", title, re.IGNORECASE)
    if m:
        use_class = True
        class_name = m.group(1)
        logDebug(0, f"StartProgram: className= {class_name}")

    try:
        proc = subprocess.Popen(command)
        pid = proc.pid
    except Exception as e:
        ErrorMessage = "Program is not found or cannot be started"
        logError(0, f"StartProgram: {ErrorMessage}, lastError= {e}")
        return -1

    logDebug(0, f"StartProgram: Run pid= {pid}")

    # Wait for process window
    start_time = time.time()
    found_hwnd = None

    while time.time() - start_time < timeout:
        time.sleep(0.5)

        def enum_windows_callback(hwnd, extra):
            nonlocal found_hwnd
            if win32gui.IsWindowVisible(hwnd):
                _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                if win_pid == pid:
                    if use_class:
                        cname = win32gui.GetClassName(hwnd)
                        if cname.lower() == class_name.lower():
                            found_hwnd = hwnd
                    else:
                        wtitle = win32gui.GetWindowText(hwnd)
                        if title.lower() in wtitle.lower():
                            found_hwnd = hwnd

        if 'win32gui' in sys.modules:
            try:
                win32gui.EnumWindows(enum_windows_callback, None)
            except Exception:
                pass
        if found_hwnd:
            break

    if not found_hwnd:
        ErrorMessage = "Expected program window is not found"
        logError(0, f"StartProgram: {ErrorMessage}")
        return -4

    if serverName != "":
        start_title_check = time.time()
        while time.time() - start_title_check < gSettings.ConnectTimeout:
            cur_title = win32gui.GetWindowText(found_hwnd) if 'win32gui' in sys.modules else ""
            logDebug(0, f"StartProgram: pid= {pid}, serverName= '{serverName}', currentTitle= '{cur_title}' -- looking")
            if serverName.lower() in cur_title.lower():
                logDebug(0, f"StartProgram: pid= {pid}, serverName= '{serverName}', currentTitle= '{cur_title}' -- found")
                break
            time.sleep(2)

        if 'win32gui' in sys.modules:
            win32gui.SetWindowText(found_hwnd, serverName)
            logDebug(0, f"StartProgram: Changed window title to '{serverName}'")

            if gSettings.ScreenMode == "Maximize":
                logDebug(0, "StartProgram: Maximize window")
                win32gui.ShowWindow(found_hwnd, win32con.SW_MAXIMIZE)

    logDebug(0, "StartProgram: Program started")
    return pid


def EndScript():
    SemaphoreRelease()
    logDebug(0, "EndScript: exitApp, finished")
    sys.exit(0)


def Regular(rdpFilename):
    global gSettings, ErrorMessage
    logDebug(0, f"Regular: RDP filename='{rdpFilename}'")

    programTitle = "ahk_class TscShellContainerClass"
    logDebug(0, f"Regular: programTitle= '{programTitle}'")

    commandLine = f'{gSettings.Program} "{rdpFilename}"'
    logDebug(0, f"Regular: commandLine= '{commandLine}'")

    try:
        proc = subprocess.Popen(commandLine)
        pid = proc.pid
    except Exception as e:
        ErrorMessage = "Program is not found or cannot be started"
        logError(0, f"Regular: {ErrorMessage}, lastError= {e}")
        return -1

    logDebug(0, f"Regular: Run pid= {pid}")
    time.sleep(2)
    return 0


def BeyondTrust(rdpFilename, filename_base):
    global gSettings, ErrorMessage

    m = re.search(r"(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", filename_base, re.IGNORECASE)
    if m:
        serverName = m.group(1).replace(" ", "_")
    else:
        ErrorMessage = f"RDP filename '{rdpFilename}' has incorrect format"
        logError(0, f"BeyondTrust: {ErrorMessage}")
        return -1

    programTitle = "ahk_class TscShellContainerClass"
    logDebug(0, f"BeyondTrust: programTitle= '{programTitle}'")

    cloneFilename = getCloneFilename(serverName)
    logDebug(0, f"BeyondTrust: serverName= '{serverName}', cloneFilename= '{cloneFilename}'")

    commandLine = f'"{gSettings.Program}" "{cloneFilename}"'
    if gSettings.ScreenMode == "Fullscreen":
        commandLine += " /f"
    else:
        commandLine += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"
    logDebug(0, f"BeyondTrust: commandLine= '{commandLine}'")

    lock_timeout_ms = 1000 * (1 + gSettings.ConnectTimeout)
    rc = 0
    if SemaphoreAcquire(lock_timeout_ms):
        ip_list = []
        rc = CloneRdpFile(PAM_TYPE_BEYONDTRUST, rdpFilename, cloneFilename, serverName, ip_list)
        ip = ip_list[0] if ip_list else ""
        logDebug(0, f"BeyondTrust: rdpFilename= {rdpFilename}, cloneFilename= {cloneFilename}, serverName= {serverName}, ip= {ip}")

        updateHosts = (rc == 1)

        if rc < 0:
            logError(0, f"BeyondTrust: CloneRdpFile - {ErrorMessage}")
        else:
            if updateHosts:
                rc = UpdateHostsFile("add", ip, serverName)
                if rc < 0:
                    logError(0, f"BeyondTrust: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
            else:
                logWarning(0, "No update to hosts file")

            if rc >= 0:
                rc = StartProgram(serverName, commandLine, programTitle, gSettings.ConnectTimeout)
                if rc < 0:
                    logError(0, f"BeyondTrust: StartProgram - {ErrorMessage}")
                else:
                    logInfo(0, f"BeyondTrust: mstsc session started to '{serverName}'")

                if updateHosts:
                    rc = UpdateHostsFile("remove", ip, serverName)
                    if rc < 0:
                        logError(0, f"BeyondTrust: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        SemaphoreRelease()

        if gSettings.Cleanup:
            logDebug(0, f"BeyondTrust: Deleting '{cloneFilename}'")
            deleteFile(cloneFilename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        logError(0, f"BeyondTrust: {ErrorMessage}")
        rc = -1

    return rc


def Symantec1(ip, port, serverName):
    global gSettings, ErrorMessage, gTemplateDefaultRdpFilename

    user_name = os.getenv("USERNAME", "user")
    if gSettings.MultiUser:
        serverName = f"{serverName}-{user_name}"

    programTitle = "ahk_class TscShellContainerClass"
    logDebug(0, f"Symantec1: programTitle= '{programTitle}'")

    commandLine = f'"{gSettings.Program}" /v:{serverName}:{port}'
    if gSettings.ScreenMode == "Fullscreen":
        commandLine += " /f"
    else:
        commandLine += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"
    logDebug(0, f"Symantec1: commandLine= '{commandLine}'")

    lock_timeout_ms = 1000 * (1 + gSettings.ConnectTimeout)
    rc = 0
    if SemaphoreAcquire(lock_timeout_ms):
        my_docs = os.path.expanduser(r"~\Documents")
        defaultRdpFilename = os.path.join(my_docs, "default.rdp")
        if not os.path.exists(defaultRdpFilename) and os.path.exists(gTemplateDefaultRdpFilename):
            shutil.copy(gTemplateDefaultRdpFilename, defaultRdpFilename)

        logDebug(0, f"Symantec1: defaultRdpFilename - {defaultRdpFilename}")
        updateHosts = False
        if os.path.exists(defaultRdpFilename):
            rc = CloneRdpFile(PAM_TYPE_SYMANTEC, defaultRdpFilename, defaultRdpFilename)
            updateHosts = (rc == 1)
            if rc < 0:
                logError(0, f"Symantec1: CloneRdpFile - {ErrorMessage}")

        if updateHosts:
            rc = UpdateHostsFile("add", ip, serverName)
            if rc < 0:
                logError(0, f"Symantec1: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
        else:
            logWarning(0, "No update to hosts file")

        if rc >= 0:
            rc = StartProgram(serverName, commandLine, programTitle, gSettings.ConnectTimeout)
            if rc < 0:
                logError(0, f"Symantec1: StartProgram - {ErrorMessage}")
            else:
                logInfo(0, f"Symantec1: mstsc started to {serverName}")

            if updateHosts:
                rc = UpdateHostsFile("remove", ip, serverName)
                if rc < 0:
                    logError(0, f"Symantec1: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        SemaphoreRelease()
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        logError(0, f"Symantec1: {ErrorMessage}")
        rc = -1

    return rc


def Symantec2(rdpFilename):
    global gSettings, ErrorMessage

    if "~" in rdpFilename:
        rdpFilename = get_long_path_name(rdpFilename)

    filename_base = os.path.splitext(os.path.basename(rdpFilename))[0]
    m = re.search(r"(.*_)?(.*)_PAMGateway", filename_base, re.IGNORECASE)
    if m:
        serverName = m.group(2).replace(" ", "_")
        user_name = os.getenv("USERNAME", "user")
        if gSettings.MultiUser:
            serverName = f"{serverName}-{user_name}"

        cloneFilename = getCloneFilename(serverName)
        logDebug(0, f"Symantec2: serverName= '{serverName}', cloneFilename= '{cloneFilename}'")
    else:
        ErrorMessage = f"RDP filename '{rdpFilename}' has incorrect format"
        logError(0, f"Symantec2: {ErrorMessage}")
        return -1

    programTitle = "ahk_class TscShellContainerClass"
    logDebug(0, f"Symantec2: programTitle= '{programTitle}'")

    commandLine = f'"{gSettings.Program}" "{cloneFilename}"'
    if gSettings.ScreenMode == "Fullscreen":
        commandLine += " /f"
    else:
        commandLine += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"
    logDebug(0, f"Symantec2: commandLine= '{commandLine}'")

    lock_timeout_ms = 1000 * (1 + gSettings.ConnectTimeout)
    rc = 0
    if SemaphoreAcquire(lock_timeout_ms):
        ip_list = []
        rc = CloneRdpFile(PAM_TYPE_SYMANTEC2, rdpFilename, cloneFilename, serverName, ip_list)
        ip = ip_list[0] if ip_list else ""
        logDebug(0, f"Symantec2: rdpFilename= {rdpFilename}, cloneFilename= {cloneFilename}, serverName= {serverName}, ip= {ip}")

        if rc < 0:
            logError(0, f"Symantec2: CloneRdpFile - {ErrorMessage}")
        else:
            logDebug(0, "No update to hosts file required for Symantec2")
            rc = StartProgram(serverName, commandLine, programTitle, gSettings.ConnectTimeout)
            if rc < 0:
                logError(0, f"Symantec2: StartProgram - {ErrorMessage}")
            else:
                logInfo(0, f"Symantec2: mstsc session started to '{serverName}'")

        SemaphoreRelease()

        if gSettings.Cleanup:
            logDebug(0, f"Symantec2: Deleting '{cloneFilename}'")
            deleteFile(cloneFilename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        logError(0, f"Symantec2: {ErrorMessage}")
        rc = -1

    return rc


def Senhasegura(localUsername, remoteUsername, port, serverName):
    global gSettings, ErrorMessage, gTemplateDefaultRdpFilename

    programTitle = "ahk_class TscShellContainerClass"
    logDebug(0, f"Senhasegura: programTitle= '{programTitle}'")

    username = f"{localUsername}[{remoteUsername}@{serverName}]"
    logDebug(0, f"Senhasegura: username= '{username}'")

    user_name = os.getenv("USERNAME", "user")
    if gSettings.MultiUser:
        serverName = f"{serverName}-{user_name}"

    serverName = serverName.replace(" ", "_")
    cloneFilename = getCloneFilename(serverName)
    logDebug(0, f"Senhasegura: serverName= '{serverName}', cloneFilename= '{cloneFilename}'")

    my_docs = os.path.expanduser(r"~\Documents")
    defaultRdpFilename = os.path.join(my_docs, "default.rdp")
    if not os.path.exists(defaultRdpFilename) and os.path.exists(gTemplateDefaultRdpFilename):
        shutil.copy(gTemplateDefaultRdpFilename, defaultRdpFilename)

    commandLine = f'"{gSettings.Program}" "{cloneFilename}"'
    if gSettings.ScreenMode == "Fullscreen":
        commandLine += " /f"
    else:
        commandLine += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"
    logDebug(0, f"Senhasegura: commandLine= '{commandLine}'")

    lock_timeout_ms = 1000 * (1 + gSettings.ConnectTimeout)
    rc = 0
    if SemaphoreAcquire(lock_timeout_ms):
        ip_list = []
        rc = CloneRdpFile(PAM_TYPE_SENHASEGURA, defaultRdpFilename, cloneFilename, serverName, ip_list, username)
        ip = ip_list[0] if ip_list else ""

        updateHosts = (rc == 1)

        if rc < 0:
            logError(0, f"Senhasegura: CloneRdpFile - {ErrorMessage}")
        else:
            if updateHosts:
                rc = UpdateHostsFile("add", ip, serverName)
                if rc < 0:
                    logError(0, f"Senhasegura: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
            else:
                logWarning(0, "No update to hosts file")

            if rc >= 0:
                rc = StartProgram(serverName, commandLine, programTitle, gSettings.ConnectTimeout)
                if rc < 0:
                    logError(0, f"Senhasegura: StartProgram - {ErrorMessage}")
                else:
                    logInfo(0, f"Senhasegura: mstsc session started to '{serverName}'")

                if updateHosts:
                    rc = UpdateHostsFile("remove", ip, serverName)
                    if rc < 0:
                        logError(0, f"Senhasegura: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        SemaphoreRelease()

        if gSettings.Cleanup:
            logDebug(0, f"Senhasegura: Deleting '{cloneFilename}'")
            deleteFile(cloneFilename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        logError(0, f"Senhasegura: {ErrorMessage}")
        rc = -1

    return rc


def CyberArk(rdpFilename):
    global gSettings, ErrorMessage

    filename_base = os.path.splitext(os.path.basename(rdpFilename))[0]
    m = re.search(r"(.*?), PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", filename_base, re.IGNORECASE)
    if m:
        serverName = m.group(1).replace(" ", "_")
        user_name = os.getenv("USERNAME", "user")
        if gSettings.MultiUser:
            serverName = f"{serverName}-{user_name}"

        cloneFilename = getCloneFilename(serverName)
        logDebug(0, f"CyberArk: serverName= '{serverName}', cloneFilename= '{cloneFilename}'")
    else:
        ErrorMessage = f"RDP filename '{rdpFilename}' has incorrect format"
        logError(0, f"CyberArk: {ErrorMessage}")
        return -1

    programTitle = "ahk_class TscShellContainerClass"
    logDebug(0, f"CyberArk: programTitle= '{programTitle}'")

    commandLine = f'"{gSettings.Program}" "{cloneFilename}"'
    if gSettings.ScreenMode == "Fullscreen":
        commandLine += " /f"
    else:
        commandLine += f" /w:{gSettings.WindowWidth} /h:{gSettings.WindowHeight}"
    logDebug(0, f"CyberArk: commandLine= '{commandLine}'")

    lock_timeout_ms = 1000 * (1 + gSettings.ConnectTimeout)
    rc = 0
    if SemaphoreAcquire(lock_timeout_ms):
        ip_list = []
        rc = CloneRdpFile(PAM_TYPE_CYBERARK, rdpFilename, cloneFilename, serverName, ip_list)
        ip = ip_list[0] if ip_list else ""
        logDebug(0, f"CyberArk: rdpFilename= {rdpFilename}, cloneFilename= {cloneFilename}, serverName= {serverName}, ip= {ip}")

        updateHosts = (rc == 1)

        if rc < 0:
            logError(0, f"CyberArk: CloneRdpFile - {ErrorMessage}")
        else:
            if updateHosts:
                rc = UpdateHostsFile("add", ip, serverName)
                if rc < 0:
                    logError(0, f"CyberArk: UpdateHostsFile (add), rc= {rc} - '{ErrorMessage}'")
            else:
                logWarning(0, "No update to hosts file")

            if rc >= 0:
                rc = StartProgram(serverName, commandLine, programTitle, gSettings.ConnectTimeout)
                if rc < 0:
                    logError(0, f"CyberArk: StartProgram - {ErrorMessage}")
                else:
                    logInfo(0, f"CyberArk: mstsc session started to '{serverName}'")

                if updateHosts:
                    rc = UpdateHostsFile("remove", ip, serverName)
                    if rc < 0:
                        logError(0, f"CyberArk: UpdateHostsFile (remove), rc= {rc} - '{ErrorMessage}'")

        SemaphoreRelease()

        if gSettings.Cleanup:
            logDebug(0, f"CyberArk: Deleting '{cloneFilename}'")
            deleteFile(cloneFilename)
    else:
        ErrorMessage = "Cannot acquire access to critical files in time."
        logError(0, f"CyberArk: {ErrorMessage}")
        rc = -1

    return rc


def main():
    global gSettings, gLockTimeout, gFilenameFull, gFilenamePath, gFilenameBase, gFilenameExt
    global gTemplateDefaultRdpFilename, ErrorMessage

    args = sys.argv[1:]

    logDebug(0, "main: start -------------- ")
    logDebug(0, f"main: version= {gVersion}")
    logDebug(0, f"main: CommandLine ArgCount: {len(args)}")

    for n, param in enumerate(args, 1):
        logDebug(0, f"main: CommandLine Arg[{n}]= '{param}'")

    if len(args) == 1:
        if re.search(r"^(--|-|/)(Ver|Version)$", args[0], re.IGNORECASE):
            show_msg_box(f"Version {gVersion}", gProgramTitle)
            sys.exit(0)
        if re.search(r"^(--|-|/)(Lic|Licens)$", args[0], re.IGNORECASE):
            show_msg_box(f"License {gVersion}", gProgramTitle)
            sys.exit(0)

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    gTemplateDefaultRdpFilename = os.path.join(script_dir, "Template-Default.rdp")

    system_prop_filename = os.path.join(script_dir, "pam-rdp.system.properties")
    gSettings = read_properties(system_prop_filename, PROPERTY_TYPE_SYSTEM)

    default_prop_filename = os.path.join(script_dir, "pam-rdp.user.properties")
    appdata = os.getenv("APPDATA", "")
    user_prop_path = os.path.join(appdata, "PAM-Exchange", "PAM-RDP-Connect")
    user_prop_filename = os.path.join(user_prop_path, "pam-rdp.user.properties")

    if not os.path.exists(user_prop_filename):
        os.makedirs(user_prop_path, exist_ok=True)
        if os.path.exists(default_prop_filename):
            shutil.copy(default_prop_filename, user_prop_filename)

    gSettings = read_properties(user_prop_filename, PROPERTY_TYPE_USER, gSettings)
    gLockTimeout = 1000 * (1 + gSettings.ConnectTimeout)

    gFilenameFull = ""
    gFilenamePath = ""
    gFilenameBase = ""
    gFilenameExt = ""

    # Heartbeat program
    if gSettings.Heartbeat:
        gHeartbeatProgram = gSettings.HeartbeatProgram
        if os.path.exists(gHeartbeatProgram):
            logInfo(0, f"main: Starting heartbeat program '{gHeartbeatProgram}'")
            try:
                subprocess.Popen(gHeartbeatProgram)
            except Exception as e:
                logError(0, f"main: Cannot start heartbeat program '{gHeartbeatProgram}', lastError= {e}")
        else:
            logError(0, f"main: Heartbeat program '{gHeartbeatProgram}' is not found")

    if len(args) == 1:
        filename = args[0]
        logDebug(0, f"main: regular - args[1]= '{filename}'")

        if filename.lower().endswith(".rdp"):
            gFilenameFull = filename
            if "~" in gFilenameFull:
                gFilenameFull = get_long_path_name(gFilenameFull)
                logDebug(0, f"main: regular - Long gFilenameFull= '{gFilenameFull}'")

            gFilenamePath = os.path.dirname(gFilenameFull)
            gFilenameBase, gFilenameExt = os.path.splitext(os.path.basename(gFilenameFull))

            if gSettings.pamType == PAM_TYPE_BEYONDTRUST and re.search(r"(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.IGNORECASE):
                logDebug(0, "main: regular - Beyondtrust .rdp filename, continue")
            elif gSettings.pamType == PAM_TYPE_SYMANTEC and re.search(r"_PAMGateway", gFilenameBase, re.IGNORECASE):
                gSettings.pamType = PAM_TYPE_SYMANTEC2
                logDebug(0, "main: regular - Symantec PAMGateway filename, continue")
            elif gSettings.pamType == PAM_TYPE_CYBERARK and re.search(r"PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.IGNORECASE):
                logDebug(0, "main: regular - CyberArk .rdp filename, continue")
            else:
                logDebug(0, f"main: call Regular using gFilenameFull= '{gFilenameFull}'")
                rc = Regular(gFilenameFull)
                logDebug(0, f"main: regular - finished, rc= {rc}")
                EndScript()
        else:
            logDebug(0, "main: regular - not an .rdp file as argument, continue")

    if gSettings.pamType == PAM_TYPE_BEYONDTRUST:
        if len(args) != 1 or not re.search(r"(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.IGNORECASE):
            show_msg_box("This program requires 1 parameter\n\npam-rdp c:\\.....\\SQL2-d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp", gProgramTitle, f"IconX T{gSettings.PromptTimeout}")
            EndScript()

        logDebug(0, f"main: call BeyondTrust using filename= '{gFilenameFull}'")
        rc = BeyondTrust(gFilenameFull, gFilenameBase)
        if rc < 0:
            logError(0, f"main: BeyondTrust - ErrorMessage= '{ErrorMessage}'")
            show_msg_box(ErrorMessage, gProgramTitle, f"IconX T{gSettings.PromptTimeout}")

        logDebug(0, f"main: BeyondTrust - finished, rc= {rc}")

    elif gSettings.pamType == PAM_TYPE_SYMANTEC:
        invalid_args = False
        ip = ""
        port = ""
        deviceName = ""

        if len(args) >= 3:
            ip = args[0]
            port = args[1]
            deviceName = " ".join(args[2:]).strip().replace(" ", "_")
        else:
            invalid_args = True

        if invalid_args:
            show_msg_box("This program requires 3 parameters\n\npam-rdp <Local IP> <First Port> <Device Name>", gProgramTitle, f"IconX T{gSettings.PromptTimeout}")
            EndScript()

        logDebug(0, f"main: Call Symantec using ip= '{ip}', port= '{port}', name= '{deviceName}'")
        rc = Symantec1(ip, port, deviceName)
        if rc < 0:
            logError(0, f"main: Symantec - ErrorMessage= '{ErrorMessage}'")
            show_msg_box(ErrorMessage, gProgramTitle, f"IconX T{gSettings.PromptTimeout}")

        logDebug(0, f"main: Symantec - finished, rc= {rc}")
        gSettings.Cleanup = False

    elif gSettings.pamType == PAM_TYPE_SYMANTEC2:
        if len(args) != 1 or not re.search(r"(.*_)?(.*)_PAMGateway", gFilenameBase, re.IGNORECASE):
            show_msg_box("This program requires 1 or 3 parameters\n\n1: pam-rdp <filename.rdp\n\n3: pam-rdp <Local IP> <First Port> <Device Name>", gProgramTitle, f"IconX T{gSettings.PromptTimeout}")
            EndScript()

        logDebug(0, f"main: Call Symantec2 using filename= '{gFilenameFull}'")
        rc = Symantec2(gFilenameFull)
        if rc < 0:
            logError(0, f"main: Symantec2 - ErrorMessage= '{ErrorMessage}'")
            show_msg_box(ErrorMessage, gProgramTitle, f"IconX T{gSettings.PromptTimeout}")

        logDebug(0, f"main: Symantec2 - finished, rc= {rc}")

    elif gSettings.pamType == PAM_TYPE_SENHASEGURA:
        invalid_args = False
        local_username = ""
        remote_username = ""
        device_name = ""

        if len(args) >= 1:
            username_arg = args[0]
            m = re.search(r"(.*?)\[(.*)@(.*)\]$", username_arg)
            if m:
                local_username = m.group(1)
                remote_username = m.group(2)
                device_name = m.group(3)
            elif len(args) >= 3:
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
            show_msg_box("Incorrect format for connection to Senhasegura\n\nUse \npam-rdp <localUsername>[remoteUsername$serverName]\n\nor\n\npam-rdp <localUsername> <remoteUsername> <serverName>", gProgramTitle, f"IconX T{gSettings.PromptTimeout}")
            EndScript()

        logDebug(0, f"main: Call Senhasegura using localUsername= '{local_username}', remoteUsername= '{remote_username}', name= '{device_name}', port= {gSettings.Port}")
        rc = Senhasegura(local_username, remote_username, gSettings.Port, device_name)
        if rc < 0:
            logError(0, f"main: Senhasegura - ErrorMessage= '{ErrorMessage}'")
            show_msg_box(ErrorMessage, gProgramTitle, f"IconX T{gSettings.PromptTimeout}")

        logDebug(0, f"main: Senhasegura - finished, rc= {rc}")
        gSettings.Cleanup = False

    elif gSettings.pamType == PAM_TYPE_CYBERARK:
        if len(args) != 1 or not re.search(r"(.*?), PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", gFilenameBase, re.IGNORECASE):
            show_msg_box("This program requires 1 parameter\n\npam-rdp c:\\.....\\SQL2, PAM Address.d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp", gProgramTitle, f"IconX T{gSettings.PromptTimeout}")
            EndScript()

        logDebug(0, f"main: call CyberArk using gFilenameFull= '{gFilenameFull}'")
        rc = CyberArk(gFilenameFull)
        if rc < 0:
            logError(0, f"main: CyberArk - ErrorMessage= '{ErrorMessage}'")
            show_msg_box(ErrorMessage, gProgramTitle, f"IconX T{gSettings.PromptTimeout}")

        logDebug(0, f"main: CyberArk - finished, rc= {rc}")

    if gSettings.Cleanup and gFilenameFull:
        logDebug(0, f"main: Cleanup - Deleting '{gFilenameFull}'")
        deleteFile(gFilenameFull)
    else:
        logDebug(0, f"main: Cleanup - No cleanup done '{gFilenameFull}'")

    EndScript()


if __name__ == "__main__":
    main()
