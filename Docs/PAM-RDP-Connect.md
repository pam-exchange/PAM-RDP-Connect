# PAM RDP Connect

**PAM RDP Connect** is a tool that enhances your experience when connecting to Windows machines through a Privileged Access Management (PAM) server. It works with various PAM solutions, including:
- BeyondTrust Password Safe
- Senhasegura PAM
- CyberArk
- Symantec PAM

When you use a standard RDP client like `mstsc.exe` with a PAM solution, the client shows the PAM server's address in the window title and connection bar, not the actual machine you're connected to. This can be confusing when you have multiple sessions open.

![](./ConnectionBar-PamServer.png)

**PAM RDP Connect** solves this by making sure the correct endpoint name is displayed in the connection bar, so you always know which machine you're working on.

![](./ConnectionBar-End-point.png)

The tool also allows you to customize your RDP settings, such as font smoothing and local drive mapping, for a better experience.

## How it Works

The tool works by tricking the RDP client. It adds an entry to your computer's `hosts` file that maps the IP address of the PAM server to the hostname of the endpoint machine. It then modifies the `.rdp` file to use this new entry. When `mstsc.exe` starts, it checks the `hosts` file first and displays the correct endpoint name in the connection bar.

A Windows service is included to handle the necessary permissions for modifying the `hosts` file.

## Post-installation setup

After installing **PAM RDP Connect**, you'll need to make a small change to your computer's settings. By default, `.rdp` files are opened by the Windows Remote Desktop Connection client. You'll need to change this so that they're opened by `pam-rdp.exe` instead.

1. Find an `.rdp` file on your computer. If you don't have one, you can create a dummy file with the `.rdp` extension.
2. Right-click on the file and select **Properties**.
3. In the **Properties** window, click the **Change** button next to **Opens with**.
4. Select **More Apps**, then find and select `pam-rdp.exe`. The default installation path is `C:\Program Files\PAM-Exchange\PAM-RDP-Connect`.

![](./RDP-Properties-04.png)

That's it! Now, when you download an `.rdp` file from your PAM server, it will be opened with **PAM RDP Connect**, and you'll see the correct server name in the RDP session.

## Other settings

You can customize your RDP settings by editing the `pam-rdp.user.properties` file. The first time you run `pam-rdp.exe`, this file is copied to `%AppData%\PAM-Exchange\PAM-RDP-Connect`. You can also use the configuration GUI to edit the settings.

![](./pam-rdp-config.png)

The settings you can change include:
- Screen mode
- Remote wallpaper
- Smart window sizing
- Font smoothing
- Local drive mapping
- Cleanup of downloaded `.rdp` files
- Security prompts
- Session color depth
- Prompt timeout
- Connection timeout

If these settings are defined, they will apply to all RDP sessions started with **PAM RDP Connect**.

## Local drives vs. Remote Network Drives

You can use local drive mapping to transfer files between your computer and the remote machine. When you enable this feature, your local drives will be available in `Network > tsclient` in the RDP session. This is useful for small files, but for larger files, it's better to use a network share.

Keep in mind that the user you're logged in as on the remote machine is controlled by the PAM server, so you'll need to make sure that the user has the necessary permissions to access the network share.

## Error handling

If you run into any issues, here are a few things to try:

### Failed to authenticate to one or more factors

This error can happen for a few reasons:
- You're using **Direct connect** in the PAM GUI. Make sure you're using the lightning icon instead.
- You have old RDP credentials saved on your computer. You can remove them in the Windows Credentials Manager.
- Your browser cache is causing issues. Try clearing it.

### Cannot connect to remote computer

If you get an error saying that the remote computer can't be connected to, it's possible that the `hosts` file on your computer has been corrupted. You can fix this by:
1. Stopping the **PAM-RDP-Connect Service**.
2. Deleting the `c:\windows\system32\drivers\etc\hosts.backup` file.
3. Opening the `hosts` file in a text editor and saving it with ASCII or UTF-8 encoding.
4. Starting the **PAM-RDP-Connect Service**.
