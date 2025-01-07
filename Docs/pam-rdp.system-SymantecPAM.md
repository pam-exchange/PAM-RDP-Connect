# pam-rdp.sysem.properties - Symantec

'''
; PAM-RDP System or installation properties
; These settings are not to be modified by users
; and are configured by the company hosting
; the PAM servers

[main]
; Change the PAMtype to reflect the PAM server. 
;PAMtype= BeyondTrustPasswordSafe
PAMtype= SymantecPAM
;PAMtype= Senhasegura
;PAMtype= CyberArk


; heartbeat is a program launched at the users desktop.
; The program will send messages to open RDP session preventing
; them from starting the screen saver on the server.
; The users desktop screen saver i not affected.
; Default is "false"
heartbeat= true

; mstscProgram is the path and program name for the mstsc program.
mstscProgram= c:\windows\system32\mstsc.exe

; multiUser is a flag set to "true" when the service is running 
; in multi-user environment (e.g. Citrix). If running on a 
; multi-user environment, the connection hostnames are suffixed 
; with the login username.
; The default value is "false". 
multiUser= false


[SymantecPAM]
; There are no specific settings for SymantecPAM

'''