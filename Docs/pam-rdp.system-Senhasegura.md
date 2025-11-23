# pam-rdp.system.properties

This file contains system-level settings for **PAM RDP Connect**. These settings are typically configured by an administrator and should not be modified by users.

## Sample for Senhasegura

```
[main]
; PAMtype specifies the PAM solution you are using.
; Valid values are:
;   - BeyondTrustPasswordSafe
;   - SymantecPAM
;   - Senhasegura
;   - CyberArk
PAMtype= Senhasegura

; heartbeat is a program that prevents remote servers from starting
; their screen savers.
heartbeat= true

; mstscProgram is the path to the Microsoft RDP client.
mstscProgram= c:\windows\system32\mstsc.exe

; multiUser should be set to "true" when running in a multi-user
; environment like Citrix. This adds a username suffix to connection
; hostnames to avoid conflicts.
multiUser= false

[Senhasegura]
; port is the port used to connect to the PAM server.
port= 3389

; cntServer is the number of PAM servers.
cntServer= 1

; The following section specifies the IP address, DNS name, and hostname
; for the server.
[server1]
ip= 192.168.242.101
dns= senhase01.prod.pam-exchange.ch
hostname= senhase01
```
