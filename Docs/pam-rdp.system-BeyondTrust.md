# pam-rdp.system.properties

This file contains system-level settings for **PAM RDP Connect**. These settings are typically configured by an administrator and should not be modified by users.

## Sample for BeyondTrust Password Safe

```
[main]
; PAMtype specifies the PAM solution you are using.
; Valid values are:
;   - BeyondTrustPasswordSafe
;   - SymantecPAM
;   - Senhasegura
;   - CyberArk
PAMtype= BeyondTrustPasswordSafe

; heartbeat is a program that prevents remote servers from starting
; their screen savers.
heartbeat= true

; mstscProgram is the path to the Microsoft RDP client.
mstscProgram= c:\windows\system32\mstsc.exe

; multiUser should be set to "true" when running in a multi-user
; environment like Citrix. This adds a username suffix to connection
; hostnames to avoid conflicts.
multiUser= false

[BeyondTrustPasswordSafe]
; port is the port used to connect to the PAM server.
port= 4489

; cntServer is the number of servers in the Password Safe cluster.
cntServer= 3

; The following sections specify the IP address, DNS name, and hostname
; for each server in the cluster.
[server1]
ip= 192.168.242.11
dns= pam-srv-01.prod.pam-exchange.ch
hostname= pam-srv-01

[server2]
ip= 192.168.242.33
dns= pam-srv-02.prod.pam-exchange.ch
hostname= pam-srv-02

[server3]
; This is the load balancer.
ip= 192.168.242.10
dns= pam.pam-exchange.ch
hostname= pam
```
