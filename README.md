# PAM RDP Connect

When launching an RDP session using Microsoft Windows standard RDP 
client, the mstsc program, the sessions are opened through the 
Privileged Access Management server. The PAM server will be seen as the 
remote server end-point and the window title and connection bar (full 
screen) will be the PAM server itself. If you only open one session at a 
time, this is no big deal. However, if you open many sessions to 
different end-points, the RDP client sees them as being the same 
end-point (the address of the PAM server). 

![PAM RDP Connect](/Docs/ConnectionBar-PamServer.png)


The `pam-rdp.exe` program is a starter program for `mstsc`. It will change 
hostname/address seen by the mstsc program to reflect the real 
end-point, thus when opening multiple sessions to different end-points, 
the window title and connection bar will identify the real end-point and 
not just the PAM server. 

## How it works

PAM solutions in general will allow you to establish sessions
to various types of end-points. Of interest here is RDP sessions
to Windows systems. This is typically done by downloading an `.rdp`
file from the PAM server and start a local RDP Client (`mstsc.exe`)
using the downloaded `.rdp` file. The server used for the RDP session
is mostly the hostname/IP-address to the PAM server. The username is 
a shortlived one-time username, which the PAM server uses to map
the session to the real Windows system. On the user's desktop the 
server to which the RDP session is established to the PAM server and 
not the real end-point server. This is why the connection bar 
in `mstsc` is showing the PAM server as the connection server.

When using PAM RDP Connect the program is in essense adding a new entry 
in the user's `hosts` file. The new entry is 
the IP-address of the PAM server with a hostname for the real
end-point server. PAM RDP Connect will also change the downloaded `.rdp`
file to use the real end-point as server. When `mstsc` is 
using the `full address` entry in the .rdp file, it will first look 
in the desktop's `hosts` file before using DNS to find the IP-address
of the hostname. This is why a change in the hosts file can trick 
the system to use the PAM server as when connecting to the hostname of
the real end-point.
Seen from `mstsc` the session is established to hostname belonging to 
the real end-point although the IP-address belongs to the PAM server.
Important is that the RDP client is connected to an IP address with a 
hostname of the real end-point server. The hostname of the real 
end-point server is now shown in the connection bar.
In addition to updating the desktop's `hosts` file an entry is 
added to the registry, such that a hostname mismatch in the 
end-point X509 certificate is ignored. Well, not really ignored, but 
rather that the end-point hostname is a trusted end-point. 

In most cases the security setup on Windows desktops
will prevent a regular user of modifying the `hosts` file themself.
This is why there are two components of the PAM RDP Connect program.
One compoent is a Windows Service and one component is a starter program for 
`mstsc.exe`.

The program `pam-rdp-service` is the Window service running
in the context of the systems Local system Account. This user has
the permissions to modify the `hosts` file and will listen commands 
on a named pipe.

The program `pam-rdp` is running in  user context with limited security
permissions on the desktop. It does however have the permissions to 
download and modify an `.rdp` file from the PAM server. The program will
send a command to the pam-rdp-service via the named pipe. The commands 
can be to add or remove an entry in the `hosts` file. 

## Supported PAM servers

The `pam-rdp.exe` starter program has been tested with Broadcom/Symantec PAM, 
Senhasegura, CyberArk and Beyondtrust Password Safe. 

See the [user documentation](/Docs/PAM-RDP-Connect.md) for details.

When using Broadcom/Symantec PAM, the system will create loop-back 
addresses for the endpoint you want to connect to. I.e. if you have 
permisions to connect to a server and use either the built-in Java 
applet RDP client or a TCP service configured to start an RDP client, 
they will connect to a loop-back address (127.x.z.y address). This 
address is what the default RDP client (mstsc) will see in the window 
title and connection bar. 

When using BeyondTrust Password Safe to connect to an end-point an RDP 
file (extension .rdp) will be created and downloaded to the users 
desktop. In the RDP file the hostname/ip address of the Password Safe 
server is used. The file also include a session token allowing Password 
Safe to direct the connection to the real end-point. However, the RDP 
client is not aware of the real end-point address and only knows the 
address in the RDP file, which is the Password Safe server. 

The `pam-rdp.exe` program is a used with the standard Windows RDP 
client (mstsc). When starting mstsc through the PAM-RDP starter program, 
the window title and connection bar (in fullscreen) will be changed to 
reflect the real end-point name. When you open sessions to many 
different servers, you can clearly identify the RDP session by the name 
of the real end-point connected to through the PAM server. 

## Building the solution

The programs uses
- AutoHotKey v2 
- Python 3.13
- Inno Setup 6.3.3

Edit the command file build.cmd and change the paths for where the 
tools are installed.

The Python program (Windows service) requires that you install pyinstaller.

***Important***<br>
Before building and packaging the installer program, it is recommended that the 
property files `pam-rdp.system.properties` and `pam-rdp.user.properties` are adapted 
to you PAM environment. There are sample properties available for different PAM 
solutions.

Run the build.cmd and it will compile and package the AutoHotKey and Pyton scripts 
with the required run-time embedded into the file. Users
do not have to install any additional software on their desktops.

After successful build the directory ./dist will include the files. They are also 
packaged into a single zip-file.
It is sufficient to use the PAM-RDP-Connect-Install-2.9.exe installer program on
user's desktop.

## Configuration

[pam-rdp.user.properties](/Docs/pam-rdp.user.md)

[pam-rdp.system.properties - BeyondTrust Password Safe](/Docs/pam-rdp.system-BeyondTrust.md)<br>
[pam-rdp.system.properties - Symantec](/Docs/pam-rdp.system-Symantec.md)<br>
[pam-rdp.system.properties - Senhasegura](/Docs/pam-rdp.system-Senhasegura.md)<br>
[pam-rdp.system.properties - CyberArk](/Docs/pam-rdp.system-CyberArk.md)
 
### Configuration - BeyondTrust Password Safe

When used with BeyondTrust Password Safe a session RDP file is downloaded
for the session. The browser can be set to launch .rdp files automaticaly.
It may be necessary to change the file association for .rdp files
from the Windows default mstsc.exe program to the new pam-rdp.exe program.
File associations are user specific and users must set this themselves.
It is possible to change file associations through GPO settings.

Used with BeyondTrust Password Safe pam-rdp.exe expects one parameter; 
the rdp file downloaded from Password Safe. The name of the RDP file is 
like <hostname>-d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp, where the 
<hostname> and hex code will change for every new end-point and 
requested session (RDP file). The hostname is used as window title and 
connection bar name. 

### Configuration - Symantec PAM

Used with Broadcom/Symantec PAM pam-rdp.exe expects three parameters; the 
loop-back address, the port number and the device name. The device name 
is used as window title and connection bar name. 

In PAM, a TCP service is created having the command: `<path>\pam-rdp.exe 
<Local IP> <First Port> "<Device Name>"`. The parameters to the program 
must be exactly as specified, i.e. do not use the real IP or port, but 
literally as written. 

The new service must be assigned to devices and a user policy for this 
service must be created.


### Configuration - Senhasegura PAM

Used with Senhasegura the PAM pam-rdp.exe expects one or three parameters; 

`pam-rdp <localUsername>[<remoteUsername>@<deviceName>]`

`pam-rdp <localUsername> <remoteUsername> <deviceName>` 

The IP address/DNS/Hostname of the Senhasegura server (or load balancer) is 
configured in the pam-rdp.system.properties file. The program will use the 
Default.rdp file for general settings. If the file contains a full address
and/or username, these will be replaced with the correct values.


## Multi-user environments

If the pam-service and program is used in a multi-user environment, e.g. 
Citrix, all users share the same hosts file. If the multiUser flag is 
set to "true" in the pam-rdp.properties file, all connection hostnames 
are suffixed with the username of the session user. I.e. if two 
different Citrix uses both connect to the same server, they will see the 
server as "hostname-user1" or "hostname-user2". 

Note: This feature has not been tested.

## Log files

pam-rdp-service.exe uses a logfile c:\windows\temp\pam-rdp-service.log. When the 
size of the log file reaches 5 MB, it will be rolled to 
pam-service.log.1. An existing pam-service.log.1 file will be rolled to 
pam-service.log.2. This continues until pam-service.log.5, which will be 
deleted when pam-service.log.4 is rolled. 

pam-rdp.exe uses a logfile in the users temp directory. It is typically 
set in the environment variable TEMP. The logfile is %TEMP%\pam-rdp.log. 
Like the pam-service.log, this log file is also rolled and at most 5 
revisions are kept. 

## Security considerations

The `pam-rdp.exe` program is running in the regular user context and 
should not have any additional privileges on the user desktop. 

The `pam-rdp-service.exe` is installed as a Windows service and is running in context of Local System. 
This will allow the service to change the hosts file without any 
security prompts. It will only accept connections from the pam-rdp.exe 
progam. To restrict the access rights of the service further, a new 
local or domain user can be used to run the service. The user running 
the service must have write/modify permission to the hosts 
file.

The service will create a backup file of the current hosts file when the 
pam-rdp-service service is started. When the pam-service is stopped the 
shadow (or backup) hosts file is copied back to the hosts file. 

There is a companion program `PAM-RDP-Heartbeat`, which can be used 
in environments where the servers are configured with screen savers.
Having a screen saver configured on a server makes perfect sense. 
However, when connecting through a PAM solution the password for the 
login account is not known and it may be seen as an unnecessary burden 
for users always having to close the connection and reestablish it again
through the PAM server.

See [PAM-RDP-Heartbeat](https://github.com/pam-exchange/PAM-RDP-Heartbeat) for more details.
 
