------------------------------------------------- 
PAM-RDP starter
------------------------------------------------- 

This is the short description about the PAM RDP starter. 

When launching an RDP session using Microsoft Windows standard RDP 
client, the mstsc program, the sessions are opened through the 
Privileged Access Management server. The PAM server will be seen as the 
remote server end-point and the window title and connection bar (full 
screen) will be the PAM server itself. If you only open one session at a 
time, this is no big deal. However, if you open many sessions to 
different end-points, the mstsc program will see them as being the same 
end-point (the address of the PAM server). 

The PAM-RDP program is a starter program for mstsc. It will change 
hostname/address seen by the mstsc program to reflect the real 
end-point, thus when opening multiple sessions to different end-points, 
the window title and connection bar will identify the real end-point and 
not just the PAM server. 

The PAM-RDP starter program has been tested with Broadcom/Symantec PAM 
and Beyondtrust Password Safe. 

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

The PAM-RDP starter program is a used with the standard Windows RDP 
client (mstsc). When starting mstsc through the PAM-RDP starter program, 
the window title and connection bar (in fullscreen) will be changed to 
reflect the real end-point name. When you open sessions to many 
different servers, you can clearly identify the RDP session by the name 
of the real end-point connected to through the PAM server. 


------------------------------------------------- 
Installation 
------------------------------------------------- 

The PAM-RDP starter program is delivered as a setup.exe and a 
pam-rdp.msi program. To install the PAM-RDP, run either program as an 
Administrator on the user desktop. You will be prompted to grant the 
installer admin rights before installing the files. When installed, the 
programs will be installed in C:\Program Files\PAM-Exchange\PAM-RDP 
directory. Can be changed in the installer. 

The files installed are: 

pam-rdp.exe           Called by the user 
pam-rdp-heartbeat.exe Program to avoid screen saver on servers 
pam-rdp.properties    Configuration for the pam-rdp.exe 
pam-service.exe       Windows Helper service 
log4cplus.dll         Logging DLL used by pam-service.exe
getopt.dll            Options DLL used by pam-service.exe
logging.properties    Logging configuration used by pam-service.exe 

The logging.properties should be left unchanged. For troubleshooting, 
the loglevel can be changed. The syntax is like log4j. 

The pam-rdp.properties file must be updated to reflect the PAM 
environment and the desired behaviour when using pam-rdp.

During installation the pam-service.exe is setup as a Windows service. 
When the program is uninstalled, the service is also stopped and removed 
as a service. If for some reason the service is not removed and the 
pam-service.exe is not uninstalled, it is possible to uninstall the 
service directly. As an administrator run the command "pam-service 
/uninstall". However, this should be done automatically when 
uninstalling the PAM Connect program through the Programs and Features 
Windows setting. 

The pam-rdp-heartbeat program is a desktop utility started when an RDP
session is started through the pam-rdp program. The pam-rdp-heartbeat
program will send heartbeat messages to servers opened through mstsc
and stop them from starting their screen saver. 
This must only be used when a user desktop screen saver is used.
Heartbeat program may not be included in installer. 

------------------------------------------------- 
pam-rdp.properties configuration 
------------------------------------------------- 

After installation of PAM-RDP the pam-rdp.properties file must be 
changed to reflect the environment used.

Details of the individual settings are found as comments in the 
sample property file.


------------------------------------------------- 
Configuration - BeyondTrust Password Safe
------------------------------------------------- 

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


------------------------------------------------- 
Configuration - Symantec PAM
------------------------------------------------- 

Used with Broadcom/Symantec PAM pam-rdp.exe expects three parameters; the 
loop-back address, the port number and the device name. The device name 
is used as window title and connection bar name. 

In PAM, a TCP service is created having the command: <path>\pam-rdp.exe 
<Local IP> <First Port> "<Device Name>". The parameters to the program 
must be exactly as specified, i.e. do not use the real IP or port, but 
literally as written. 

The new service must be assigned to devices and a user policy for this 
service must be created.

------------------------------------------------- 
Configuration - Senhasegura PAM
------------------------------------------------- 

Used with Senhasegura the PAM pam-rdp.exe expects one or three parameters; 

1) pam-rdp <localUsername>[<remoteUsername>@<deviceName>]
2) pam-rdp <localUsername> <remoteUsername> <deviceName> 

The IP address/DNS/Hostname of the Senhasegura server (or load balancer) is 
configured in the pam-rdp.system.properties file. The program will use the 
Default.rdp file for general settings. If the file contains a full address
and/or username, these will be replaced with the correct values.


------------------------------------------------- 
Multi-user environments
------------------------------------------------- 

If the pam-service and program is used in a multi-user environment, e.g. 
Citrix, all users share the same hosts file. If the multiUser flag is 
set to "true" in the pam-rdp.properties file, all connection hostnames 
are suffixed with the username of the session user. I.e. if two 
different Citrix uses both connect to the same server, they will see the 
server as "hostname-user1" or "hostname-user2". 


------------------------------------------------- 
Log files
------------------------------------------------- 

pam-service.exe uses a logfile c:\windows\temp\pam-service.log. When the 
size of the log file reaches 5 MB, it will be rolled to 
pam-service.log.1. An existing pam-service.log.1 file will be rolled to 
pam-service.log.2. This continues until pam-service.log.5, which will be 
deleted when pam-service.log.4 is rolled. 

pam-rdp.exe uses a logfile in the users temp directory. It is typically 
set in the environment variable TEMP. The logfile is %TEMP%\pam-rdp.log. 
Like the pam-service.log, this log file is also rolled and at most 5 
revisions are kept. 


------------------------------------------------- 
Security considerations
------------------------------------------------- 

The program pam-rdp.exe is running in the regular user context and 
should not have any additional privileges on the user desktop. 

The service pam-service.exe is running as Local System. This will 
allow the service to change the hosts file without any security prompts. 
It will only accept connections from the pam-rdp.exe progam. To restrict 
the access rights of the service further, a new local or domain user can 
be used to run the service. The user running the service must have 
write/modify permission to the hosts file.

It is recommended to use a shadow hosts file, which then will be used 
as basis before the pam-service will update the hosts file with the 
new entry used when opening a session. The shadow host filename is 
'hosts.shadow' located in the same directory as the hosts file. 

If a shadow file is not used, the service will create a backup file of 
the current hosts file when the pam-service is started. When the  
pam-service is stopped the shadow (or backup) hosts file is copied
back to the hosts file. 

If a screen saver is started on the server it is difficult for the user 
to open the session again, as they do not know the login password. The 
pam-rdp-heartbeat program will send heartbeat messages to the server and 
effectivly stop the screen saver from starting, thus keeping the session 
open until closed by the user. If a user does not have a screen saver on 
their desktop, this should never be used. Connections directly to a 
server through VMware console or physical access will still use the 
server's screen saver. 
 

------------------------------------------------- 
Known issues
------------------------------------------------- 

Path and filenames using UTF-16 may not work correctly.


------------------------------------------------- 
Version history
------------------------------------------------- 

2024-04-22 2.9.0 - Converted pam-rdp.ahk and pam-rdp-config.ahk to 
                   AutoHotKey version 2

2024-02-27 2.8.0 - Added GUI program to update configuration
                 - Added documentation
                 - Program and documentation in desktop menu "Start>PAM Connect"
                 - Added support for Senhasegura PAM

2024-02-08 2.7.3 - Write command line arguments to log
                 - Allow Heartbeat if ScreenSaver is not secure
                 - SymantecPAM: assemble deviceName from args[3],args[4], ...
                 - SymantecPAM: Also ignore Symantec PAM Windows

2023-08-21 2.7.2 - Solved comments in hosts file corrupted content

2023-06-21 2.7.1 - Allow space in filenames of RDP files.

2023-05-26 2.7.0 - pam-rdp.properties can be edited in the users %AppData%
                   directory. This file will be used. If not found
                   the file in install directory will be used.
                 - Changed copyright notice
                 - Start regular RDP file (when BeyondTrust only)

2022-06-05 2.6.1 - Additional PAM servers in customer build

2022-05-12 2.6.0 - Open RDP session even if the PAM server is not 
                   included in the pam-rdp.properties file.

2021-01-07 2.5   - Removed Heartbeat program for specific customers.

2021-01-04 2.4   - Start pam-rdp-heartbeat, if configured
                 - Added pam-rdp-heartbeat program.
                 - Added 'screenMode' parameter.
                 - Removed  'Fullscreen' parameter.
                 - New screenMode 'Maximize' using the entire desktop 
                   except the task bar.

2020-12-18 2.3   - Allow space in RDP filename (BeyonTrust).
                 - New flag acceptSecurityMessages in pam-rdp.properties.
                   When set to "true" the security certificate 
                   warnings are ignored. Default is to show warnings.
                 - Silent accept prompt to trust connection to a new 
                   server.
                 - Updated "Terms & Conditions" file.
                 - Updated "-license" option.

2020-10-17 2.2   - Handle 8.3 path/filename for RDP file (BeyondTrust). 
                 - Handle 8.3 path/filename for calling pam-rdp client. 
                 - Added "multiUser" flag for Citrix and RDS 
                   environments. The hostname/connection name is 
                   suffixed with the username.
                 - Backup/restore of the hosts file is done when the 
                   service is started/stopped. If another program or 
                   user updates the hosts file, such changes may be 
                   lost when the service is stopped.
                 - First write original hosts content before adding 
                   new entries. Removing entries only in entries
                   added.
                 - Update default.rdp if found (Symantec).
                 - Resolved parameter conflict when updating rdp-file.

2020-09-15 2.1   - Removed "loadbalancer" section. 
                   Add an extra server as loadbalancer instead.
                 - Added "wallpaper=true|false" in BTPS section.
                 - Service now authenticate calling application.

2020-07-22 2.0   - Isolated the parts updating the hosts file to a 
                   Windows service. The service runs with higher
                   privileges and the user does no longer need to have 
                   write access to the hosts file. 
                 - Added a GUI installer.
                 - Changed the mechanism for logging. This version uses
                   a logfile rolling mechanism to limit the number of 
                   logfiles.
                    
2020-07-07 1.0   - Using mechanisms to detect the windows started
                   by the pam-rdp starter. Still a requirement that
                   the user has write access to the hosts file.
                 - Better mechanism to control when an mstsc session has
                   started. 
                 - Added a lock/unlock mechanism to synchronize
                   multiple (parallel) runs of pam-rdp.
                    
2020-06-28 0.x   - Initial POC command file to demonstrate and proof 
                   the approach used to update the hosts file indeed 
                   does resolve the naming in windows title and connection
                   bar in mstsc.

---- end-of-file ---