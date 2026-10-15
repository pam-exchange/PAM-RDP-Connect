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

import os
import sys
import re
import shutil
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

gVersion = "2.9.0"
gProgramTitle = "PAM RDP Connect Configuration"

# Global paths
script_path = os.path.abspath(sys.argv[0])
script_dir = os.path.dirname(script_path)

property_filename = "pam-rdp.user.properties"
install_property_filename = os.path.join(script_dir, property_filename)

user_property_path = os.path.join(os.environ.get("APPDATA", ""), "PAM-Exchange", "PAM-RDP-Connect")
user_property_filename = os.path.join(user_property_path, property_filename)

if not os.path.exists(user_property_path):
    try:
        os.makedirs(user_property_path, exist_ok=True)
    except Exception:
        pass

if os.path.exists(user_property_filename):
    load_property_filename = user_property_filename
else:
    load_property_filename = install_property_filename


class Settings:
    def __init__(self):
        self.ScreenMode = "Fullscreen"
        self.WindowWidth = "1024"
        self.WindowHeight = "768"
        self.UseFontSmoothing = True
        self.AllowWallpaper = False
        self.UseSmartSizing = False
        self.LocalDriveMapping = ""
        self.Cleanup = True
        self.AcceptSecurityMessages = True
        self.SessionBpp = "24"
        self.PromptTimeout = "15"
        self.ConnectTimeout = "60"
        self.LogLevel = "Debug"


def read_properties(filename):
    s = Settings()
    if not os.path.exists(filename):
        return s

    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(filename, encoding="utf-8-sig")
    except Exception:
        try:
            config.read(filename)
        except Exception:
            pass

    log_level = config.get("main", "loglevel", fallback="DEBUG").strip().capitalize()
    if log_level in ["Error", "Warning", "Info", "Debug", "Trace"]:
        s.LogLevel = log_level

    x = config.get("main", "cleanup", fallback="true").strip()
    s.Cleanup = ("false" not in x.lower())

    x = config.get("main", "connecttimeout", fallback=config.get("main", "connectiontimeout", fallback="60")).strip()
    s.ConnectTimeout = x

    x = config.get("main", "prompttimeout", fallback="15").strip()
    s.PromptTimeout = x

    x = config.get("main", "screenmode", fallback="Fullscreen").strip()
    if re.search(r"^Window$", x, re.I):
        s.ScreenMode = "Window"
    elif re.search(r"^Maximize$", x, re.I):
        s.ScreenMode = "Maximize"
    elif re.search(r"^Fullscreen$", x, re.I):
        s.ScreenMode = "Fullscreen"

    s.WindowWidth = config.get("main", "windowwidth", fallback="1024").strip()
    s.WindowHeight = config.get("main", "windowheight", fallback="768").strip()

    x = config.get("main", "usefontsmoothing", fallback="true").strip()
    s.UseFontSmoothing = ("true" in x.lower())

    x = config.get("main", "wallpaper", fallback="false").strip()
    s.AllowWallpaper = ("true" in x.lower())

    x = config.get("main", "sessionbpp", fallback="24").strip()
    if x in ["16", "24", "32"]:
        s.SessionBpp = x

    s.LocalDriveMapping = config.get("main", "localdrivemapping", fallback="").strip()

    x = config.get("main", "acceptsecuritymessages", fallback="true").strip()
    s.AcceptSecurityMessages = ("true" in x.lower())

    x = config.get("main", "usesmartsizing", fallback="false").strip()
    s.UseSmartSizing = ("true" in x.lower())

    return s


def write_properties(output_filename, settings):
    wrt_screen_mode = f"ScreenMode= {settings.ScreenMode}"
    wrt_width = ("" if settings.ScreenMode == "Window" else ";") + f"WindowWidth= {settings.WindowWidth}"
    wrt_height = ("" if settings.ScreenMode == "Window" else ";") + f"WindowHeight= {settings.WindowHeight}"
    wrt_use_font_smoothing = f"UseFontSmoothing= {'true' if settings.UseFontSmoothing else 'false'}"
    wrt_allow_wallpaper = f"Wallpaper= {'true' if settings.AllowWallpaper else 'false'}"
    wrt_use_smart_sizing = f"UseSmartSizing= {'true' if settings.UseSmartSizing else 'false'}"
    wrt_local_drive_mapping = f"LocalDriveMapping= {settings.LocalDriveMapping}"
    wrt_cleanup = f"Cleanup= {'true' if settings.Cleanup else 'false'}"
    wrt_accept_security_messages = f"AcceptSecurityMessages= {'true' if settings.AcceptSecurityMessages else 'false'}"
    wrt_session_bpp = f"SessionBpp= {settings.SessionBpp}"
    wrt_prompt_timeout = f"PromptTimeout= {settings.PromptTimeout}"
    wrt_connect_timeout = f"ConnectionTimeout= {settings.ConnectTimeout}"
    wrt_log_level = f"LogLevel= {settings.LogLevel.upper()}"

    content = f"""[main]
; Control the window mode of the RDP session
; valid values are: window|maximize|fullscreen
;   window     - use the windowWidth/windowHeight parameters.
;   maximize   - make the window as large as possible without going
;                into fullscreen mode.
;   fullscreen - use MSTSC fullscreen mode. This is default.
{wrt_screen_mode}

; windowWidth and windowHeight can be used to overwrite the
; parameters used by the PAM server. The settings are only
; used when screenMode is window.
{wrt_width}
{wrt_height}

; allowFontSmoothing can be used if Password Safe is configured to allow
; font smoothing. The downloaded RDP file does not set this flag.
; If the option is defined and set to 'true', the RDP file will be updated
; to allow font smoothing. Keep in mind that the Password Safe server
; must permit font smoothing for this to work.
; Update default.rdp (Symantec).
{wrt_use_font_smoothing}

; wallpaper can be to transmit the wallpaper from the remote server.
; If the option is defined and set to "true", the RDP file will be updated
; to allow wallpaper.
; Symantec: Update default.rdp
{wrt_allow_wallpaper}

; useSmartSizing flag is controlling if the RDP session is scaling
; when the window is resized.
; Symantec: Update default.rdp
{wrt_use_smart_sizing}

; localDriveMapping can be used to set the local drives to be mapped in the
; mstsc session. The syntax is like the regular RDP file used by mstsc.
; If the setting is not defined or empty, no drive mapping is used.
; Symantec: Update default.rdp

;localDriveMapping= C:\\;K:\\;DynamicDrives
;localDriveMapping= C:\\;K:\\
;localDriveMapping= *
;localDriveMapping=
{wrt_local_drive_mapping}

; Cleanup will control if downloaded RDP files are removed after use.
{wrt_cleanup}

; acceptSecurityMessages can be automatically accepted.
; Messages will be shown when different from "true".
; If omitted, no changes in RDP file is done.
; Symantec: Update default.rdp
{wrt_accept_security_messages}

; sessionBpp can be used to change/force the session bpp settings.
; If the real-end point does not support the bpp, this setting can not
; be used to increase a "16-bit" RDP session to the end-point to a higher
; value. It can be used to decrease the bpp from the real end-point.
; accepted values are 16, 24 or 32
; Symantec: Update default.rdp
{wrt_session_bpp}

; promptTimeout for GUI pop-ups. If a pop-up window is shown, the user
; can press <OK> to close the pop-up message.
; If not acknowleged by the user, the pop-up will close after <timeout>
; seconds.
{wrt_prompt_timeout}

; connectionTimeout is the maximum time for opening a session through
; PAM to the end-point. Depending on the end-point location and connection
; time to the end-point, the value may need to be increased.
; If a connection is not established in <connectioinTimeout> seconds,
; the start attempt is stopped.
{wrt_connect_timeout}

; LogLevel for pam-rdp.exe.
; Valid values are ERROR, WARNING, INFO, DEBUG, TRACE
; Default value is DEBUG
{wrt_log_level}
"""

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(content)


class PamRdpConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title(gProgramTitle)
        self.root.resizable(False, False)

        self.current_filename = load_property_filename
        self.settings = read_properties(self.current_filename)

        self.create_menu()
        self.create_widgets()
        self.load_settings_to_gui()

    def display_path(self, path):
        if "PAM-Exchange\\PAM-RDP-Connect" in path:
            return "..." + path[path.index("PAM-Exchange\\PAM-RDP-Connect") + len("PAM-Exchange"):]
        return path

    def create_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.on_open)
        file_menu.add_command(label="Save", command=self.on_save)
        file_menu.add_command(label="Save as ...", command=self.on_save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Quick guide", command=self.on_quick_guide)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.on_about)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Current file Frame
        self.file_frame = ttk.LabelFrame(main_frame, text=self.display_path(self.current_filename), padding="5")
        self.file_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Screen Mode Group
        sm_frame = ttk.LabelFrame(self.file_frame, text="Screen Mode", padding="10")
        sm_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5, padx=5)

        self.screen_mode_var = tk.StringVar(value="Fullscreen")
        rb_win = ttk.Radiobutton(sm_frame, text="Window", variable=self.screen_mode_var, value="Window", command=self.on_screen_mode_change)
        rb_max = ttk.Radiobutton(sm_frame, text="Maximize", variable=self.screen_mode_var, value="Maximize", command=self.on_screen_mode_change)
        rb_full = ttk.Radiobutton(sm_frame, text="Fullscreen", variable=self.screen_mode_var, value="Fullscreen", command=self.on_screen_mode_change)

        rb_win.grid(row=0, column=0, padx=5)
        rb_max.grid(row=0, column=1, padx=5)
        rb_full.grid(row=0, column=2, padx=5)

        size_frame = ttk.Frame(sm_frame)
        size_frame.grid(row=1, column=0, columnspan=3, pady=(5, 0), sticky="w")

        ttk.Label(size_frame, text="Width × Height ").grid(row=0, column=0)
        self.width_entry = ttk.Entry(size_frame, width=6, justify="right")
        self.width_entry.grid(row=0, column=1)
        ttk.Label(size_frame, text=" × ").grid(row=0, column=2)
        self.height_entry = ttk.Entry(size_frame, width=6, justify="right")
        self.height_entry.grid(row=0, column=3)

        # Options Frame inside file_frame
        opts_frame = ttk.Frame(self.file_frame)
        opts_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Use font smoothing
        ttk.Label(opts_frame, text="Use font smoothing", width=25, anchor="e").grid(row=0, column=0, sticky="e", pady=2)
        self.font_smoothing_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, variable=self.font_smoothing_var).grid(row=0, column=1, sticky="w", padx=5)

        # Show remote wallpaper
        ttk.Label(opts_frame, text="Show remote wallpaper", width=25, anchor="e").grid(row=1, column=0, sticky="e", pady=2)
        self.wallpaper_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, variable=self.wallpaper_var).grid(row=1, column=1, sticky="w", padx=5)

        # Use smart window sizing
        ttk.Label(opts_frame, text="Use smart window sizing", width=25, anchor="e").grid(row=2, column=0, sticky="e", pady=2)
        self.smart_sizing_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, variable=self.smart_sizing_var).grid(row=2, column=1, sticky="w", padx=5)

        # Local drive mapping
        ttk.Label(opts_frame, text="Local drive mapping", width=25, anchor="e").grid(row=3, column=0, sticky="e", pady=2)
        self.drive_mapping_entry = ttk.Entry(opts_frame, width=25)
        self.drive_mapping_entry.grid(row=3, column=1, sticky="w", padx=5)

        # Delete RDP file after use
        ttk.Label(opts_frame, text="Delete RDP file after use", width=25, anchor="e").grid(row=4, column=0, sticky="e", pady=2)
        self.cleanup_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, variable=self.cleanup_var).grid(row=4, column=1, sticky="w", padx=5)

        # Accept Security Prompts
        ttk.Label(opts_frame, text="Accept Security Prompts", width=25, anchor="e").grid(row=5, column=0, sticky="e", pady=2)
        self.accept_sec_var = tk.BooleanVar()
        ttk.Checkbutton(opts_frame, variable=self.accept_sec_var).grid(row=5, column=1, sticky="w", padx=5)

        # Session Colour depth
        ttk.Label(opts_frame, text="Session Colour depth", width=25, anchor="e").grid(row=6, column=0, sticky="e", pady=2)
        bpp_frame = ttk.Frame(opts_frame)
        bpp_frame.grid(row=6, column=1, sticky="w", padx=5)
        self.bpp_var = tk.StringVar(value="24")
        ttk.Radiobutton(bpp_frame, text="16", variable=self.bpp_var, value="16").grid(row=0, column=0)
        ttk.Radiobutton(bpp_frame, text="24", variable=self.bpp_var, value="24").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(bpp_frame, text="32", variable=self.bpp_var, value="32").grid(row=0, column=2)

        # Prompt Timeout
        ttk.Label(opts_frame, text="Prompt Timeout", width=25, anchor="e").grid(row=7, column=0, sticky="e", pady=2)
        self.prompt_timeout_entry = ttk.Entry(opts_frame, width=8, justify="right")
        self.prompt_timeout_entry.grid(row=7, column=1, sticky="w", padx=5)

        # Connection Timeout
        ttk.Label(opts_frame, text="Connection Timeout", width=25, anchor="e").grid(row=8, column=0, sticky="e", pady=2)
        self.connect_timeout_entry = ttk.Entry(opts_frame, width=8, justify="right")
        self.connect_timeout_entry.grid(row=8, column=1, sticky="w", padx=5)

        # Log level
        ttk.Label(opts_frame, text="Log level", width=25, anchor="e").grid(row=9, column=0, sticky="e", pady=2)
        self.log_level_combo = ttk.Combobox(opts_frame, values=["Error", "Warning", "Info", "Debug", "Trace"], width=12, state="readonly")
        self.log_level_combo.grid(row=9, column=1, sticky="w", padx=5)

        # Buttons Frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))

        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.root.quit)
        self.cancel_btn.grid(row=0, column=0, padx=5)

        self.save_btn = ttk.Button(btn_frame, text="Save", command=self.on_save)
        self.save_btn.grid(row=0, column=1, padx=5)

    def on_screen_mode_change(self):
        if self.screen_mode_var.get() == "Window":
            self.width_entry.config(state="normal")
            self.height_entry.config(state="normal")
        else:
            self.width_entry.config(state="disabled")
            self.height_entry.config(state="disabled")

    def load_settings_to_gui(self):
        self.screen_mode_var.set(self.settings.ScreenMode)
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, str(self.settings.WindowWidth))
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, str(self.settings.WindowHeight))

        self.font_smoothing_var.set(self.settings.UseFontSmoothing)
        self.wallpaper_var.set(self.settings.AllowWallpaper)
        self.smart_sizing_var.set(self.settings.UseSmartSizing)

        self.drive_mapping_entry.delete(0, tk.END)
        self.drive_mapping_entry.insert(0, self.settings.LocalDriveMapping)

        self.cleanup_var.set(self.settings.Cleanup)
        self.accept_sec_var.set(self.settings.AcceptSecurityMessages)

        self.bpp_var.set(self.settings.SessionBpp)

        self.prompt_timeout_entry.delete(0, tk.END)
        self.prompt_timeout_entry.insert(0, str(self.settings.PromptTimeout))

        self.connect_timeout_entry.delete(0, tk.END)
        self.connect_timeout_entry.insert(0, str(self.settings.ConnectTimeout))

        self.log_level_combo.set(self.settings.LogLevel)

        self.file_frame.config(text=self.display_path(self.current_filename))

        if self.current_filename == install_property_filename:
            self.save_btn.config(text="Save As")
        else:
            self.save_btn.config(text="Save")

        self.on_screen_mode_change()

    def get_settings_from_gui(self):
        s = Settings()
        s.ScreenMode = self.screen_mode_var.get()
        s.WindowWidth = self.width_entry.get().strip()
        s.WindowHeight = self.height_entry.get().strip()
        s.UseFontSmoothing = self.font_smoothing_var.get()
        s.AllowWallpaper = self.wallpaper_var.get()
        s.UseSmartSizing = self.smart_sizing_var.get()
        s.LocalDriveMapping = self.drive_mapping_entry.get().strip()
        s.Cleanup = self.cleanup_var.get()
        s.AcceptSecurityMessages = self.accept_sec_var.get()
        s.SessionBpp = self.bpp_var.get()
        s.PromptTimeout = self.prompt_timeout_entry.get().strip()
        s.ConnectTimeout = self.connect_timeout_entry.get().strip()
        s.LogLevel = self.log_level_combo.get()
        return s

    def on_open(self):
        filename = filedialog.askopenfilename(
            title="Open Property File",
            initialdir=os.path.dirname(self.current_filename),
            filetypes=[("Properties (*.properties)", "*.properties"), ("All files", "*.*")]
        )
        if filename:
            self.current_filename = filename
            self.settings = read_properties(self.current_filename)
            self.load_settings_to_gui()

    def on_save(self):
        if self.current_filename == install_property_filename:
            self.on_save_as()
        else:
            s = self.get_settings_from_gui()
            write_properties(self.current_filename, s)
            messagebox.showinfo(gProgramTitle, f"Properties saved to file\n\n{self.current_filename}")
            self.root.quit()

    def on_save_as(self):
        filename = filedialog.asksaveasfilename(
            title=f"{gProgramTitle} - Select File",
            initialdir=user_property_path,
            initialfile=property_filename,
            filetypes=[("Properties (*.properties)", "*.properties"), ("All files", "*.*")]
        )
        if filename:
            self.current_filename = filename
            s = self.get_settings_from_gui()
            write_properties(self.current_filename, s)
            messagebox.showinfo(gProgramTitle, f"Properties saved to file\n\n{self.current_filename}")
            self.settings = s
            self.load_settings_to_gui()

    def on_quick_guide(self):
        guide = (
            "PAM-RDP-Connect Configuration\n"
            "----------------------------------\n\n"
            "The user's property settings in pam-rdp.user.properties files can be updated using the configuration GUI.\n"
            "The program is used to update the settings a user can or should modify. System settings must be updated using a standard text editor. System settings includes the addresses of PAM servers.\n\n"
            "The default user's configuration is loaded from the users %AppData% directory. If a property file is not found, the property file from the installation location is used. When saving the file, it is recommended to use the default location suggested. This is where the PAM-RDP-Connect program will read the properties from.\n\n"
            f"Version {gVersion}\n"
            "Copyright ©2020-2024 Columbus A/S"
        )
        messagebox.showinfo(gProgramTitle, guide)

    def on_about(self):
        about = (
            "PAM-RDP-Connect Configuration\n"
            "----------------------------------\n\n"
            "PAM-RDP-Connect Configuration is used to update the user's properties file for PAM-RDP-Connect.\n\n"
            f"Version {gVersion}\n"
            "Copyright ©2020-2024 Columbus A/S"
        )
        messagebox.showinfo(gProgramTitle, about)


def main():
    args = sys.argv[1:]
    if len(args) == 1:
        if re.search(r"^(--|-|/)?(V|Ver|Version)$", args[0], re.I):
            print(f"Version {gVersion}")
            sys.exit(0)
        if re.search(r"^(--|-|/)?(L|Lic|Licens)$", args[0], re.I):
            print(f"License {gVersion}")
            sys.exit(0)

    root = tk.Tk()
    app = PamRdpConfigApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
