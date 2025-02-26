# pam-rdp.user.properties

```
[main]
; LogLevel for pam-rdp.exe. 
; Valid values are ERROR, WARNING, INFO, DEBUG, TRACE
; Default value is DEBUG
LogLevel= DEBUG

; promptTimeout for GUI pop-ups. If a pop-up window is shown, the user 
; can "OK" to close the pop-up message. 
; If not acknowleged by the user, the pop-up will close after <timeout>
; seconds.
promptTimeout= 15

; connectionTimeout is the maximum time for opening a session through
; PAM to the end-point. Depending on the end-point location and connection
; time to the end-point, the value may need to be increased.
; If a connection is not established in <connectioinTimeout> seconds,
; the start attempt is stopped.
connectionTimeout= 45

; Control the window mode of the RDP session
; valid values are: window|maximize|fullscreen
;   window     - use the windowWidth/windowHeight parameters.
;   maximize   - make the window as large as possible without going 
;                into fullscreen mode.
;   fullscreen - use MSTSC fullscreen mode. This is default.
screenMode= fullscreen

; windowWidth and windowHeight can be used to overwrite the 
; parameters used by the PAM server. The settings are only 
; used when screenMode is window.
; Default windowWidth is 1024.
; Default windowHeight is 768.
;windowWidth= 1024
;windowHeight= 768

; allowFontSmoothing can be used if Password Safe is configured to allow
; font smoothing. The downloaded RDP file does not set this flag. 
; If the option is defined and set to "true", the RDP file will be updated
; to allow font smoothing. Keep in mind that the Password Safe server
; must permit font smoothing for this to work.
; Update default.rdp (Symantec).
allowFontSmoothing= true

; wallpaper can be to transmit the wallpaper from the remote server.
; If the option is defined and set to "true", the RDP file will be updated
; to allow wallpaper.
; Symantec: Update default.rdp
wallpaper= false

; sessionBpp can be used to change/force the session bpp settings.
; If the real-end point does not support the bpp, this setting can not 
; be used to increase a "16-bit" RDP session to the end-point to a higher
; value. It can be used to decrease the bpp from the real end-point.
; Symantec: Update default.rdp
sessionBpp= 24

; localDriveMapping can be used to set the local drives to be mapped in the 
; mstsc session. The syntax is like the regular RDP file used by mstsc.
; If the setting is not defined or empty, no drive mapping is used.
; Symantec: Update default.rdp

;localDriveMapping= C:\;K:\;DynamicDrives
;localDriveMapping= C:\;K:\
;localDriveMapping= *
;localDriveMapping= 
localDriveMapping= C:\;DynamicDrives

; acceptSecurityMessages can be automatically accepted. 
; Messages will be shown when different from "true".
; If omitted, no changes in RDP file is done.
; Symantec: Update default.rdp
acceptSecurityMessages= true

; useSmartSizing flag is controlling if the RDP session is scaling
; when the window is resized.
; Symantec: Update default.rdp
useSmartSizing= false
```