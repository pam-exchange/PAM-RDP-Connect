# pam-rdp.user.properties

This file allows you to customize your RDP settings.

```
[main]
; LogLevel for pam-rdp.exe.
; Valid values are ERROR, WARNING, INFO, DEBUG, TRACE.
; Default value is DEBUG.
LogLevel= DEBUG

; promptTimeout for GUI pop-ups. If a pop-up window is shown, it will
; close automatically after the specified number of seconds.
promptTimeout= 15

; connectionTimeout is the maximum time to wait for a connection to be
; established. If a connection is not established in the specified
; number of seconds, the attempt will be aborted.
connectionTimeout= 45

; screenMode controls the window mode of the RDP session.
; Valid values are: window, maximize, fullscreen.
;   window     - opens the session in a window with a fixed size.
;   maximize   - opens the session in a maximized window.
;   fullscreen - opens the session in fullscreen mode.
screenMode= fullscreen

; windowWidth and windowHeight are used when screenMode is set to
; "window".
; Default windowWidth is 1024.
; Default windowHeight is 768.
;windowWidth= 1024
;windowHeight= 768

; allowFontSmoothing enables or disables font smoothing in the RDP
; session.
allowFontSmoothing= true

; wallpaper enables or disables the remote wallpaper.
wallpaper= false

; sessionBpp sets the color depth of the RDP session.
; Valid values are 16, 24, and 32.
sessionBpp= 24

; localDriveMapping specifies which local drives to map in the RDP
; session.
;   C:\;K:\;DynamicDrives - Maps C:, K:, and any drives that are
;                           attached later.
;   C:\                    - Maps only the C: drive.
;   *                      - Maps all drives.
localDriveMapping= C:\;DynamicDrives

; acceptSecurityMessages automatically accepts security prompts.
acceptSecurityMessages= true

; useSmartSizing enables or disables smart sizing, which scales the
; remote desktop to fit the window size.
useSmartSizing= false
```
