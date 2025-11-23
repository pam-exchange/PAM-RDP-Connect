# PAM RDP Connect

This tool is a companion for the standard Microsoft RDP client (`mstsc.exe`) and is used with Privileged Access Management (PAM) solutions. When you connect to a remote Windows machine through a PAM solution, the RDP client shows the address of the PAM server in the window title and connection bar, not the actual machine you're working on. This can be confusing if you have multiple sessions open.

`pam-rdp.exe` solves this problem by ensuring the real endpoint's name is displayed.

![PAM RDP Connect](/Docs/ConnectionBar-PamServer.png)

## How It Works

The tool tricks `mstsc.exe` by adding an entry to your computer's `hosts` file. This entry maps the IP address of the PAM server to the hostname of the endpoint machine. It also modifies the `.rdp` file to use this new entry. When `mstsc.exe` connects, it looks at the `hosts` file first, and your session is labeled with the correct endpoint name.

A Windows service is included to handle the necessary permissions for modifying the `hosts` file.

## Supported PAM solutions

The `pam-rdp.exe` starter program has been tested with the following PAM solutions:
- Broadcom/Symantec PAM
- Senhasegura
- CyberArk
- BeyondTrust Password Safe

See the [user documentation](/Docs/PAM-RDP-Connect.md) for details.

## Building the solution

To build the solution, you will need:
- AutoHotKey v2
- Python 3.13
- Inno Setup 6.3.3

Before you start, edit the `build.cmd` file to match the installation paths for these tools. You will also need to install `pyinstaller` for the Python service.

**Important:** Before building, it is recommended that you adapt the property files `pam-rdp.system.properties` and `pam-rdp.user.properties` to your PAM environment. Sample properties are available for different PAM solutions.

Run `build.cmd` to compile the scripts and create an installer in the `./dist` directory. The installer includes all necessary run-time files, so users do not need to install any additional software.

## Configuration

- [pam-rdp.user.properties](/Docs/pam-rdp.user.md)
- [pam-rdp.system.properties - BeyondTrust Password Safe](/Docs/pam-rdp.system-BeyondTrust.md)
- [pam-rdp.system.properties - Symantec](/Docs/pam-rdp.system-Symantec.md)
- [pam-rdp.system.properties - Senhasegura](/Docs/pam-rdp.system-Senhasegura.md)
- [pam-rdp.system.properties - CyberArk](/Docs/pam-rdp.system-CyberArk.md)

## Multi-user environments

The `pam-rdp.exe` program can be used in multi-user environments like Citrix. If the `multiUser` flag is set to `true` in `pam-rdp.properties`, all connection hostnames will be suffixed with the username, allowing different users to connect to the same server without conflicts.

Note: This feature has not been tested.

## Log files

Log files for `pam-rdp-service.exe` are located at `c:\windows\temp\pam-rdp-service.log`. Log files for `pam-rdp.exe` are in the user's `%TEMP%` directory at `%TEMP%\pam-rdp.log`. Both files are rolled over to prevent them from becoming too large.

## Security considerations

The `pam-rdp.exe` program runs in the user's context and does not require any additional privileges. The `pam-rdp-service.exe` runs as a Windows service with Local System privileges, which allows it to modify the `hosts` file. The service only accepts connections from `pam-rdp.exe`.

The service creates a backup of the `hosts` file on startup and restores it on shutdown.

There is a companion program, [PAM-RDP-Heartbeat](https://github.com/pam-exchange/PAM-RDP-Heartbeat), which can be used to prevent remote servers from activating their screen savers.
