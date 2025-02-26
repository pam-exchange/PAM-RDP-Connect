# pam-rdp.sysem.properties

Sample system properties for CyberArk

```
; PAM-RDP System or installation properties
; These settings are not to be modified by users
; and are configured by the company hosting
; the PAM servers

[main]
; Change the PAMtype to reflect the PAM server. 
;PAMtype= BeyondTrustPasswordSafe
;PAMtype= SymantecPAM
;PAMtype= Senhasegura
PAMtype= CyberArk


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


[CyberArk]
; The settings in this and subsequent settings are for 
; CyberArk

; port is the port used when connecting the RDP client to PAM
port= 3389

; cntServer is the number of PAM servers for CyberArk. 
; Use just one (1) server or a load balancer in the [server1] configuration. 
cntServer= 1

;-----------------------------------------
; CyberArk server
[server1]
ip= 192.168.242.101
dns= cyberark01.prod.pam-exchange.ch
hostname= cyberark01
```