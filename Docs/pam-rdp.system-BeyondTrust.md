# pam-rdp.sysem.properties - BeyondTrust Password Safe

'''
; PAM-RDP System or installation properties
; These settings are not to be modified by users
; and are configured by the company hosting
; the PAM servers

[main]
; Change the PAMtype to reflect the PAM server. 
PAMtype= BeyondTrustPasswordSafe
;PAMtype= SymantecPAM
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


[BeyondTrustPasswordSafe]
; The settings in this and subsequent settings are for 
; BeyondTrust Password Safe

; port is the port used when connecting the RDP client to PAM
port= 4489

; The following sections are for the loadbalancer and every server in
; a Password Safe cluster. The server sections must be named
; as [serverX] where X is a sequence number starting with 1.
; If a server section is missing, the program may fail.
; The loadbalancer is one of the servers

; Subsequent sections must each each have an IP address, 
; a full DNS name and a hostname specified.

; cntServer is the number of PAM servers behind the loadbalancer 
; Subsequent server sections must match the number specified here.
cntServer= 3

[server1]
ip= 192.168.242.11
dns= pam-srv-01.prod.pam-exchange.ch
hostname= pam-srv-01

[server2]
ip= 192.168.242.33
dns= pam-srv-02.prod.pam-exchange.ch
hostname= pam-srv-02

[server3]
; load balancer
ip= 192.168.242.10
dns= pam.pam-exchange.ch
hostname= pam
'''
