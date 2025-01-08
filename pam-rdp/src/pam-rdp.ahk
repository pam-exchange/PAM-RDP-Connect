/*
Copyright (C) 2024-2025 PAM Exchange

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
USA
*/

#Requires AutoHotkey 2.0+
;#SingleInstance force    --- must *not* be SingleInstance
DetectHiddenWindows true

;-------
; Information about the script 
SplitPath(A_ScriptFullPath, , , , &gScriptName)
gVersion:= "2.9.0"

global gProgramTitle:= "PAM RDP Connect"		; title for pop-up messages

global gSelfPid:= DllCall("GetCurrentProcessId")
global gSelfPidHex:= Format("{:04x}",gSelfPid)

global gLockFilename:= A_Temp "\" gScriptName ".lock"
global gLockHandle:= 0
global gPipeName:= "PAM-RDP-SERVICE"

;-------
; Constants
;
global LOG_ALWAYS:= 0
global LOG_ERROR:= 1
global LOG_WARNING:= 2
global LOG_INFO:= 3
global LOG_DEBUG:= 4
global LOG_TRACE:= 5

global PAM_TYPE_BEYONDTRUST:= "BeyondTrustPasswordSafe"
global PAM_TYPE_SYMANTEC:= "SymantecPAM"
global PAM_TYPE_SYMANTEC2:= "SymantecPAMGateway"
global PAM_TYPE_SENHASEGURA:= "Senhasegura"
global PAM_TYPE_CYBERARK:= "CyberArk"

global PROPERTY_TYPE_SYSTEM:= 1
global PROPERTY_TYPE_USER:= 2

;-------
; Log files and more
;
timestamp := FormatTime(, "yyyyMMdd")
;gLogFile= %gScriptPath%\%gScriptName%-%timestamp%.log
;global gLogFile:= "c:\windows\temp\pam-rdp-" timestamp ".log"
;global gLogFile:= A_Temp "\" gScriptName "-" timestamp ".log"
global gLogFile:= A_Temp "\" gScriptName ".log"
global gLogLevel:= LOG_DEBUG
global ErrorMessage:= ""

; roll log files before we begin
LogRoll(gLogFile,5,5)


;-------
logDebug(A_LineNumber, "main: start -------------- ")
logDebug(A_LineNumber, "main: version= " gVersion)


; -----
; Write command line to log
;
logDebug(A_LineNumber, "main: CommandLine ArgCount: " A_Args.Length )

for n, param in A_Args  ; For each parameter:
{
	logDebug(A_LineNumber, "main: CommandLine Arg[" n "]= '" param "'")
}

;-------
if (A_Args.Length == 1) {
	if (RegExMatch(A_Args[1], "i)(--|-|/){1}(Ver|Version)")) {
		MsgBox("Version " gVersion,gProgramTitle, "IconI")
		ExitApp
	}
	if (RegExMatch(A_Args[1], "i)(--|-|/){1}(Lic|Licens)")) {
		MsgBox("License " gVersion,gProgramTitle, "IconI")
		ExitApp
	}
}

; -----------
; Setup

/*Menu, Tray, NoStandard
;Menu, Tray, MainWindow
Menu, Tray, Add, Exit, EndScript
Menu, Tray, Default, Exit
;Menu, Tray, Click, 1
Menu, Tray, Tip, %gProgramTitle%
*/

; --- 
; Copy/read property file
;
SplitPath(A_ScriptFullPath, , &dir, &ext, &name)

; filename for template-default.rdp
global gTemplateDefaultRdpFilename:= dir "\Template-Default.rdp"

; read system properties
systemPropertyFilename:= dir "\" name ".system.properties"
global gSettings:= ReadProperties(systemPropertyFilename,PROPERTY_TYPE_SYSTEM)

defaultPropertyFilename:= dir "\" name ".user.properties"
userPropertyPath:= A_AppData "\PAM-Exchange\PAM-RDP-Connect"
userPropertyFilename:= userPropertyPath "/" name ".user.properties"
if (!FileExist(userPropertyFilename)) {
	DirCreate(userPropertyPath)
	FileCopy(defaultPropertyFilename, userPropertyFilename)
}

; Read user properties
gSettings:= ReadProperties(userPropertyFilename,PROPERTY_TYPE_USER, gSettings)
global gLockTimeout:= 1000*(1+gSettings.ConnectTimeout)	; Must recalculate as settings.ConnectTimout may have been changed from properties

; Filename from command line
global gFilenameFull:= ""
global gFilenamePath:= ""
global gFilenameBase:= ""
global gFilenameExt:= ""

;------------------------
; Heartbeat program (after ReadProperties)
if (gSettings.Heartbeat) {
	SplitPath(A_ScriptFullPath, , &dir, &ext, &name)
	;gHeartbeatProgramName:= "PAM RDP Heartbeat"
	;gHeartbeatProgram:= dir "\" gHeartbeatProgramName
	gHeartbeatProgram:= gSettings.HeartbeatProgram

	If (FileExist(gHeartbeatProgram))
	{
;		If WinExist( gHeartbeatProgramName ) {
;			logDebug(A_LineNumber, "main: Heartbeat program '" gHeartbeatProgramName "' is already running")
;		}
;		else {
			logInfo(A_LineNumber, "main: Starting heartbeat program '" gHeartbeatProgram "'")
			try {
				Run(gHeartbeatProgram)
			}
			catch as e
			{
				logError(A_LineNumber, "main: Cannot start heartbeat program '" gHeartbeatProgram "', lastError= " e.Message)
			}
;		}
	}
	else 
		logError(A_LineNumber, "main: Heartbeat program '" gHeartbeatProgram "' is not found")
}

; --------------
; First check if this is a regular .rdp file
if (A_Args.Length = 1)
{
	filename:= A_Args[1]
	logDebug(A_LineNumber, "main: regular - args[1]= '" filename "'")

	if (RegExMatch(filename, "i)\.rdp$")>0) {
	
		gFilenameFull:= filename
		if (InStr(gFilenameFull,"~")) {
			; 8.3 short name in rdpFilename
			gFilenameFull:= GetLongPathName(gFilenameFull)
			logDebug(A_LineNumber, "main: regular - Long gFilenameFull= '" gFilenameFull "'")
		}
		SplitPath(gFilenameFull, , &gFilenamePath, &gFilenameExt, &gFilenameBase)
		
		if (gSettings.PamType=PAM_TYPE_BEYONDTRUST && RegExMatch(gFilenameBase, "i)(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")>0) {
			logDebug(A_LineNumber, "main: regular - Beyondtrust .rdp filename, continue")
		}
		else if (gSettings.PamType = PAM_TYPE_SYMANTEC && RegExMatch(gFilenameBase, "i)_PAMGateway")>0) {
			gSettings.PamType:= PAM_TYPE_SYMANTEC2
			logDebug(A_LineNumber, "main: regular - Symantec PAMGateway filename, continue")
		}
		else if (gSettings.PamType = PAM_TYPE_CYBERARK && RegExMatch(gFilenameBase, "i)PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")>0) {
			logDebug(A_LineNumber, "main: regular - CyberArk .rdp filename, continue")
		}
		else {
			logDebug(A_LineNumber, "main: call Regular using gFilenameFull= '" gFilenameFull "'")
			rc:= Regular(gFilenameFull)
			
			logDebug(A_LineNumber, "main: regular - finished, rc= " rc)
			EndScript()
		}
	}
	else {
		logDebug(A_LineNumber, "main: regular - not an .rdp file as argument, continue")
	}
}

;------------------------
if (gSettings.PamType = PAM_TYPE_BEYONDTRUST) {
	if (A_Args.Length != 1 || RegExMatch(gFilenameBase, "i)(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$") <= 0) {
		; parameter not recognized nor accepted
		MsgBox("This program requires 1 parameter`n`npam-rdp c:\.....\SQL2-d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp", gProgramTitle, "IconX T" gSettings.PromptTimeout)
		EndScript()
	}

	logDebug(A_LineNumber, "main: call BeyondTrust using filename= '" gFilenameFull "'")
	rc:= BeyondTrust(gFilenameFull)
	if (rc < 0) {
		logError(A_LineNumber, "main: BeyondTrust - ErrorMessage= '" ErrorMessage "'")
		MsgBox(ErrorMessage, gProgramTitle, "IconX T" gSettings.PromptTimeout)
	}
	 
	logDebug(A_LineNumber, "main: BeyondTrust - finished, rc= " rc)
}

;------------------------
if (gSettings.PamType = PAM_TYPE_SYMANTEC) {

	invalidArgs:= false
	if (A_Args.Length >= 3)
	{
		;
		; symantec1 is used
		;
		; assume it is called using "pam-rdp <LocalIP> <LocalPort> <deviceName>"
		ip:= ""
		port:= ""
		deviceName:= ""
		for n, param in A_Args {
			Switch n
			{
			Case 1: 
				ip:= param
			Case 2: 
				port:= param
			Default:
				deviceName:= deviceName " " param
			}		
		}
		deviceName:= Trim(deviceName)
		deviceName:= StrReplace(deviceName," ","_")
	}
	else {
		invalidArgs:= true
	}
	
	if (invalidArgs) {
		; parameter not recognized nor accepted
		MsgBox("This program requires 3 parameters`n`npam-rdp <Local IP> <First Port> <Device Name>", gProgramTitle, "IconX T" gSettings.PromptTimeout)
		EndScript()
	}
	
	logDebug(A_LineNumber, "main: Call Symantec using ip= '" ip "', port= '" port "', name= '" deviceName "'")
	rc:= Symantec1(ip,port,deviceName)
	if (rc < 0) {
		logError(A_LineNumber, "main: Symantec - ErrorMessage= '" ErrorMessage "'")
		MsgBox(ErrorMessage, gProgramTitle, "IconX T" gSettings.PromptTimeout)
	}
	
	logDebug(A_LineNumber, "main: Symantec - finished, rc= " rc)
	
	; no cleanup here
	gSettings.Cleanup:= false
}

;------------------------
if (gSettings.PamType = PAM_TYPE_SYMANTEC2) {

	if (A_Args.Length != 1 || RegExMatch(gFilenameBase, "i)(.*_)?(.*)_PAMGateway") <= 0) {
		; parameter not recognized nor accepted
		MsgBox("This program requires 1 or 3 parameters`n`n1: pam-rdp <filename.rdp`n`n3: pam-rdp <Local IP> <First Port> <Device Name>", gProgramTitle, "IconX T" gSettings.PromptTimeout)
		EndScript()
	}
		
	logDebug(A_LineNumber, "main: Call Symantec2 using filename= '" gFilenameFull)
	rc:= Symantec2(gFilenameFull)
	if (rc < 0) {
		logError(A_LineNumber, "main: Symantec2 - ErrorMessage= '" ErrorMessage "'")
		MsgBox(ErrorMessage, gProgramTitle, "IconX T" gSettings.PromptTimeout)
	}
	
	logDebug(A_LineNumber, "main: Symantec2 - finished, rc= " rc)
}

;------------------------
if (gSettings.PamType = PAM_TYPE_SENHASEGURA) {

	invalidArgs:= false
	if (A_Args.Length >= 1) {
		username:= A_Args[1]
		logDebug(A_LineNumber, "main: Senhasegura - username= '" username "'")

		localUsername:= ""
		remoteUsername:= ""
		deviceName:= ""
		
		if (RegExMatch(username, "(.*?)\[(.*)@(.*)\]$", &x) > 0) {
			; patameter is in the form <localUsername>[<remoteusername>@<serverName>]
			localUsername:= x[1]
			remoteUsername:= x[2]
			deviceName:= x[3]
		} 
		else {
			for n, param in A_Args {
				Switch n
				{
				Case 1: 
					localUsername:= param
				Case 2: 
					remoteUsername:= param
				Default:
					deviceName:= deviceName " " param
				}		
			}
		}
		
		if (localUsername != "" && remoteUsername != "" && deviceName!="") {
			deviceName:= Trim(deviceName)
			deviceName:= StrReplace(deviceName," ","_")
		}
		else {
			invalidArgs:= true
		}
	}
	else {
		invalidArgs:= true
	}
	
	if (invalidArgs) {
		MsgBox("Incorrect format for connection to Senhasegura`n`nUse `npam-rdp <localUsername>[remoteUsername$serverName]`n`nor`n`npam-rdp <localUsername> <remoteUsername> <serverName>", gProgramTitle, "IconX T" gSettings.PromptTimeout)
		EndScript()
	}
	
	logDebug(A_LineNumber, "main: Call Senhasegura using localUsername= '" localUsername "', remoteUsername= '" remoteUsername "', name= '" deviceName "', port= " gSettings.port)
	rc:= Senhasegura(localUsername,remoteUsername,gSettings.port,deviceName)
	if (rc < 0) {
		logError(A_LineNumber, "main: Senhasegura - ErrorMessage= '" ErrorMessage "'")
		MsgBox(ErrorMessage, gProgramTitle, "IconX T" gSettings.PromptTimeout)
	}
	
	logDebug(A_LineNumber, "main: Senhasegura - finished, rc= " rc)
	
	; no cleanup here
	gSettings.Cleanup:= false
}

;------------------------
if (gSettings.PamType = PAM_TYPE_CYBERARK) {
	if (A_Args.Length != 1 || RegExMatch(name, "i)(.*?), PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$") <= 0) {
		; parameter not recognized nor accepted
		MsgBox("This program requires 1 parameter`n`npam-rdp c:\.....\SQL2, PAM Address.d6c2efa4-f38a-4b65-9438-0e07900899ef.rdp", gProgramTitle, "IconX T" gSettings.PromptTimeout)
		EndScript()
	}

	logDebug(A_LineNumber, "main: call CyberArk using gFilenameFull= '" gFilenameFull "'")
	rc:= CyberArk(gFilenameFull)
	if (rc < 0) {
		logError(A_LineNumber, "main: CyberArk - ErrorMessage= '" ErrorMessage "'")
		MsgBox(ErrorMessage, gProgramTitle, "IconX T" gSettings.PromptTimeout)
	}
	
	logDebug(A_LineNumber, "main: CyberArk - finished, rc= " rc)
}

/*
 * Cleanup downloaded .rdp file
 */
if (gSettings.Cleanup) {
	logDebug(A_LineNumber, "main: Cleanup - Deleting '" gFilenameFull "'")
	deleteFile(gFilenameFull)
} 
else {
	logDebug(A_LineNumber, "main: Cleanup - No cleanup done '" gFilenameFull "'")
}

EndScript()

;*****************************************************************************************************

;---------------------------------------------------------------------------------
; Finished 
EndScript()
{
	; always release the semaphore, regardless of it being used or not
	SemaphoreRelease()

	logDebug(A_LineNumber, "EndScript: exitApp, finished")
	exitApp
}

;---------------------------------------------------------------------------------
Regular(rdpFilename) 
{
	logDebug(A_LineNumber, "Regular: RDP filename='" rdpFilename "'")

	global gSettings, ErrorMessage

	programTitle:= "ahk_class TscShellContainerClass"
	logDebug(A_LineNumber, "Regular: programTitle= '" programTitle "'")

	commandLine:= gSettings.Program ' "' rdpFilename '"'
	logDebug(A_LineNumber, "Regular: commandLine= '" commandLine "'")

	; run the program
	try {
		Run(commandLine,,,&pid)
	}
	catch as e
	{
		ErrorMessage:= "Program is not found or cannot be started"
		logError(A_LineNumber, "Regular: " ErrorMessage ", lastError= " e.Message)
		return -1
	}
	logDebug(A_LineNumber, "Regular: Run pid= " pid)

	Sleep(2000)
	return 0
}

;---------------------------------------------------------------------------------
BeyondTrust(rdpFilename) 
{
	logDebug(A_LineNumber, "BeyondTrust: RDP filename='" rdpFilename "'")
	
	global gSettings, gLockTimeout, ErrorMessage
	global PAM_TYPE_BEYONDTRUST

	; c:\.....\SQL2-d6c2efa4-f38a-4b65-9438-0e07900899ef
	;SplitPath(rdpFilename, , &dir, &ext, &name)
	if (RegExMatch(gFilenameBase, "i)(.*?)-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", &x) >0) {
		serverName:= StrReplace(x[1]," ","_")
	} 
	else {
		ErrorMessage:= "RDP filename '" rdpFilename "' has incorrect format"
		logError(A_LineNumber, "BeyondTrust: " ErrorMessage)
		return -1
	}

	; Default title of opened mstsc window when opening an RDP file
	;SetTitleMatchMode, RegEx
	;programTitle:= "^" serverName " - " serverName ".* - .*"
	programTitle:= "ahk_class TscShellContainerClass"
	logDebug(A_LineNumber, "BeyondTrust: programTitle= '" programTitle "'")

	commandLine:= gSettings.Program " " cloneFilename
	if (gSettings.ScreenMode = "Fullscreen")
		commandLine:= commandLine " /f"
	else
		commandLine:= commandLine " /w:" gSettings.WindowWidth " /h:" gSettings.WindowHeight
	logDebug(A_LineNumber, "BeyondTrust: commandLine= '" commandLine "'")

	cloneFilename:= getCloneFilename(serverName)
	logDebug(A_LineNumber, "BeyondTrust: serverName= '" serverName "', cloneFilename= '" cloneFilename "'")
	
	if (SemaphoreAcquire( gLockTimeout )) {
		; Update rdp file with new serverName
		ip:= ""
		rc:= CloneRdpFile( PAM_TYPE_BEYONDTRUST, rdpFilename, cloneFilename, serverName, &ip )
		logDebug(A_LineNumber, "BeyondTrust: rdpFilename= " rdpFilename ", cloneFilename= " cloneFilename ", serverName= " serverName ", ip= " ip)
		
		updateHosts:= (rc == 1)

		if (rc < 0) {
			logError(A_LineNumber, "BeyondTrust: CloneRdpFile - " ErrorMessage)
		} 
		else {
			if (updateHosts) {
				; add entry to hosts file
				rc:= UpdateHostsFile("add",ip,serverName)
				if (rc < 0) {
					logError(A_LineNumber, "BeyondTrust: UpdateHostsFile (add), rc= " rc " - '" ErrorMessage "'")
				}
			} else {
				logWarning(A_LineNumber, "No update to hosts file")
			}
			
			if (rc >= 0) {
				; start mstsc
				rc:= StartProgram( serverName, commandLine, programTitle, gSettings.ConnectTimeout )
				if (rc < 0)
					logError(A_LineNumber, "BeyondTrust: StartProgram - " ErrorMessage)
				else {
					logInfo(A_LineNumber, "BeyondTrust: mstsc session started to '" serverName "'")
				}
				
				if (updateHosts) {
					; remove entry from hosts file
					rc:= UpdateHostsFile("remove",ip,serverName)
					if (rc < 0) {
						logError(A_LineNumber, "BeyondTrust: UpdateHostsFile (remove), rc= " rc " - '" ErrorMessage "'")
					}
				}
			}
		}
		; Release critical section for others to use
		SemaphoreRelease()

		if (gSettings.Cleanup) {
			logDebug(A_LineNumber, "BeyondTrust: Deleting '" cloneFilename "'")
			deleteFile(cloneFilename)
		} 

	} 
	else {
		ErrorMessage:= "Cannot acquire access to critical files in time."
		logError(A_LineNumber, "BeyondTrust: " ErrorMessage)
		rc:= -1
	}
	return rc
}

;---------------------------------------------------------------------------------
Symantec1(ip,port,serverName) 
{
	logDebug(A_LineNumber, "Symantec1: ip= '" ip "', port= '" port "', serverName= '" serverName "'")

	global gSettings, gLockTimeout, ErrorMessage, gTemplateDefaultRdpFilename
	global PAM_TYPE_SYMANTEC

	if (gSettings.MultiUser)
		serverName:= serverName "-" A_Username
			
	; Default title of opened mstsc window when opening an RDP file
	;programTitle:= serverName ":" port " - Remote Desktop Connection"
	programTitle:= "ahk_class TscShellContainerClass"
	logDebug(A_LineNumber, "Symantec1: programTitle= '" programTitle "'")
	
	commandLine:= gSettings.Program " /v:" serverName ":" port
	if (gSettings.ScreenMode = "Fullscreen")
		commandLine:= commandLine " /f"
	else
		commandLine:= commandLine " /w:" gSettings.WindowWidth " /h:" gSettings.WindowHeight
	logDebug(A_LineNumber, "Symantec1: commandLine= '" commandLine "'")
	
	if (SemaphoreAcquire( gLockTimeout )) {
	
		defaultRdpFilename:= A_MyDocuments "\default.rdp"
		if (!FileExist(defaultRdpFilename)) {
			FileCopy(gTemplateDefaultRdpFilename, defaultRdpFilename)
		}
	
		logDebug(A_LineNumber, "Symantec1: defaultRdpFilename - " defaultRdpFilename)
		if (FileExist(defaultRdpFilename)) {
			; update default.rdp 
			; Continue even if there are errors
			rc:= CloneRdpFile( PAM_TYPE_SYMANTEC, defaultRdpFilename, defaultRdpFilename )
			updateHosts:= (rc == 1)

			if (rc<0) {
				logError(A_LineNumber, "Symantec1: CloneRdpFile - " ErrorMessage)
			}
		}

		if (updateHosts) {
			; add entry to hosts file
			rc:= UpdateHostsFile("add",ip,serverName)
			if (rc < 0) {
				logError(A_LineNumber, "Symantec1: UpdateHostsFile (add), rc= " rc " - '" ErrorMessage "'")
			}
		} else {
			logWarning(A_LineNumber, "No update to hosts file")
		}
			
		if (rc >= 0) {
			; start mstsc
			rc:= StartProgram( serverName, commandLine, programTitle, gSettings.ConnectTimeout )
			if (rc < 0)
				logError(A_LineNumber, "Symantec1: StartProgram - " ErrorMessage)				
			else {
				logInfo(A_LineNumber, "Symantec1: mstsc started to " serverName)
			}

			if (updateHosts) {
				; remove entry from hosts file
				rc:= UpdateHostsFile("remove",ip,serverName)
				if (rc < 0) {
					logError(A_LineNumber, "Symantec1: UpdateHostsFile (remove), rc= " rc " - '" ErrorMessage "'")
				}
			}
		}

		; Release critical section for others to use
		SemaphoreRelease()
	} 
	else {
		ErrorMessage:= "Cannot acquire access to critical files in time."
		logError(A_LineNumber, "Symantec1: " ErrorMessage)
		rc:= -1
	}
	return rc
}

;---------------------------------------------------------------------------------
Symantec2(rdpFilename) 
{
	logDebug(A_LineNumber, "Symantec2: RDP filename='" rdpFilename "'")
	
	global gSettings, gLockTimeout, ErrorMessage
	global PAM_TYPE_SYMANTEC2

	if (InStr(rdpFilename,"~")) {
		; 8.3 short name in rdpFilename
		rdpFilename:= GetLongPathName(rdpFilename)
		logDebug(A_LineNumber, "Symantec2: Long filename= '" rdpFilename "'")
	}

	; pamRDS1_Win 3_PAMGateway_2024.09.06_10.37_GMT+2
	; Win 3_PAMGateway_2024.09.06_10.37_GMT+2
	SplitPath(rdpFilename, , &dir, &ext, &name)
	if (RegExMatch(name, "i)(.*_)?(.*)_PAMGateway", &x) >0) {
		serverName:= StrReplace(x[2]," ","_")
		
		if (gSettings.MultiUser) 
			serverName:= serverName "-" A_Username

		cloneFilename:= getCloneFilename(serverName)
		logDebug(A_LineNumber, "Symantec2: serverName= '" serverName "', cloneFilename= '" cloneFilename "'")
	} 
	else {
		ErrorMessage:= "RDP filename '" rdpFilename "' has incorrect format"
		logError(A_LineNumber, "Symantec2: " ErrorMessage)
		return -1
	}

	; Default title of opened mstsc window when opening an RDP file
	;SetTitleMatchMode, RegEx
	;programTitle:= "^" serverName " - " serverName ".* - .*"
	programTitle:= "ahk_class TscShellContainerClass"
	logDebug(A_LineNumber, "Symantec2: programTitle= '" programTitle "'")

	commandLine:= gSettings.Program " " cloneFilename
	if (gSettings.ScreenMode = "Fullscreen")
		commandLine:= commandLine " /f"
	else
		commandLine:= commandLine " /w:" gSettings.WindowWidth " /h:" gSettings.WindowHeight
	logDebug(A_LineNumber, "Symantec2: commandLine= '" commandLine "'")

	if (SemaphoreAcquire( gLockTimeout )) {
		; Update rdp file with new serverName
		ip:= ""
		rc:= CloneRdpFile( PAM_TYPE_SYMANTEC2, rdpFilename, cloneFilename, serverName, &ip )
		logDebug(A_LineNumber, "Symantec2: rdpFilename= " rdpFilename ", cloneFilename= " cloneFilename ", serverName= " serverName ", ip= " ip)
		
		if (rc < 0) {
			logError(A_LineNumber, "Symantec2: CloneRdpFile - " ErrorMessage)
		} 
		else {
			logDebug(A_LineNumber, "No update to hosts file required for Symantec2")
			
			; start mstsc
			rc:= StartProgram( serverName, commandLine, programTitle, gSettings.ConnectTimeout )
			if (rc < 0)
				logError(A_LineNumber, "Symantec2: StartProgram - " ErrorMessage)
			else {
				logInfo(A_LineNumber, "Symantec2: mstsc session started to '" serverName "'")
			}
		}
		; Release critical section for others to use
		SemaphoreRelease()

		if (gSettings.Cleanup) {
			logDebug(A_LineNumber, "Symantec2: Deleting '" cloneFilename "'")
			deleteFile(cloneFilename)
		} 

	} 
	else {
		ErrorMessage:= "Cannot acquire access to critical files in time."
		logError(A_LineNumber, "Symantec2: " ErrorMessage)
		rc:= -1
	}
	return rc
}

;---------------------------------------------------------------------------------
Senhasegura(localUsername,remoteUsername,port,serverName) 
{
	logDebug(A_LineNumber, "Senhasegura: localUsername= '" localUsername "', remoteUsername= '" remoteUsername "', port= '" port "', serverName= '" serverName "'")

	global gSettings, gLockTimeout, ErrorMessage, gTemplateDefaultRdpFilename
	global PAM_TYPE_SENHASEGURA

	; Default title of opened mstsc window when opening an RDP file
	;programTitle:= serverName ":" port " - Remote Desktop Connection"
	programTitle:= "ahk_class TscShellContainerClass"
	logDebug(A_LineNumber, "Senhasegura: programTitle= '" programTitle "'")

	; Assemble the Senhasegura username before cheking for "MultiUser"
	username:= localUsername "[" remoteUsername "@" serverName "]"
	logDebug(A_LineNumber, "Senhasegura: username= '" username "'")

	if (gSettings.MultiUser)
		serverName:= serverName "-" A_Username
			
	serverName:= StrReplace(serverName," ","_")

	cloneFilename:= getCloneFilename(serverName)
	logDebug(A_LineNumber, "Senhasegura: serverName= '" serverName "', cloneFilename= '" cloneFilename "'")
	
	defaultRdpFilename:= A_MyDocuments "\default.rdp"
	if (!FileExist(defaultRdpFilename)) {
		FileCopy(gTemplateDefaultRdpFilename, defaultRdpFilename)
	}
	
	commandLine:= gSettings.Program " " cloneFilename
	if (gSettings.ScreenMode = "Fullscreen")
		commandLine:= commandLine " /f"
	else
		commandLine:= commandLine " /w:" gSettings.WindowWidth " /h:" gSettings.WindowHeight
	logDebug(A_LineNumber, "Senhasegura: commandLine= '" commandLine "'")

	if (SemaphoreAcquire( gLockTimeout )) {
		; Update rdp file with new serverName
		ip:= ""
		rc:= CloneRdpFile( PAM_TYPE_SENHASEGURA, defaultRdpFilename, cloneFilename, serverName, &ip, username )
		
		updateHosts:= (rc == 1)

		if (rc < 0) {
			logError(A_LineNumber, "Senhasegura: CloneRdpFile - " ErrorMessage)
		} 
		else {
			if (updateHosts) {
				; add entry to hosts file
				rc:= UpdateHostsFile("add",ip,serverName)
				if (rc < 0) {
					logError(A_LineNumber, "Senhasegura: UpdateHostsFile (add), rc= " rc " - '" ErrorMessage "'")
				}
			} else {
				logWarning(A_LineNumber, "No update to hosts file")
			}
			
			if (rc >= 0) {
				; start mstsc
				rc:= StartProgram( serverName, commandLine, programTitle, gSettings.ConnectTimeout )
				if (rc < 0)
					logError(A_LineNumber, "Senhasegura: StartProgram - " ErrorMessage)
				else {
					logInfo(A_LineNumber, "Senhasegura: mstsc session started to '" serverName "'")
				}
				
				if (updateHosts) {
					; remove entry from hosts file
					rc:= UpdateHostsFile("remove",ip,serverName)
					if (rc < 0) {
						logError(A_LineNumber, "Senhasegura: UpdateHostsFile (remove), rc= " rc " - '" ErrorMessage "'")
					}
				}
			}
		}
		; Release critical section for others to use
		SemaphoreRelease()

		if (gSettings.Cleanup) {
			logDebug(A_LineNumber, "Senhasegura: Deleting '" cloneFilename "'")
			deleteFile(cloneFilename)
		} 
	} 
	else {
		ErrorMessage:= "Cannot acquire access to critical files in time."
		logError(A_LineNumber, "Senhasegura: " ErrorMessage)
		rc:= -1
	}
	return rc
}

;---------------------------------------------------------------------------------
CyberArk(rdpFilename) 
{
	logDebug(A_LineNumber, "CyberArk: RDP filename='" rdpFilename "'")
	
	global gSettings, gLockTimeout, ErrorMessage
	global PAM_TYPE_CYBERARK

	; c:\.....\SQL2, PSM Address.d6c2efa4-f38a-4b65-9438-0e07900899ef
	SplitPath(rdpFilename, , &dir, &ext, &name)
	if (RegExMatch(name, "i)(.*?), PSM Address\.[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", &x) >0) {
		serverName:= StrReplace(x[1]," ","_")
		
		if (gSettings.MultiUser) 
			serverName:= serverName "-" A_Username
			
		cloneFilename:= getCloneFilename(serverName)
		logDebug(A_LineNumber, "CyberArk: serverName= '" serverName "', cloneFilename= '" cloneFilename "'")
	} 
	else {
		ErrorMessage:= "RDP filename '" rdpFilename "' has incorrect format"
		logError(A_LineNumber, "CyberArk: " ErrorMessage)
		return -1
	}

	; Default title of opened mstsc window when opening an RDP file
	;SetTitleMatchMode, RegEx
	programTitle:= "ahk_class TscShellContainerClass"
	logDebug(A_LineNumber, "CyberArk: programTitle= '" programTitle "'")

	commandLine:= gSettings.Program " " cloneFilename
	if (gSettings.ScreenMode = "Fullscreen")
		commandLine:= commandLine " /f"
	else
		commandLine:= commandLine " /w:" gSettings.WindowWidth " /h:" gSettings.WindowHeight
	logDebug(A_LineNumber, "CyberArk: commandLine= '" commandLine "'")

	if (SemaphoreAcquire( gLockTimeout )) {
		; Update rdp file with new serverName
		ip:= ""
		rc:= CloneRdpFile( PAM_TYPE_CYBERARK, rdpFilename, cloneFilename, serverName, &ip )
		logDebug(A_LineNumber, "CyberArk: rdpFilename= " rdpFilename ", cloneFilename= " cloneFilename ", serverName= " serverName ", ip= " ip)
		
		updateHosts:= (rc == 1)

		if (rc < 0) {
			logError(A_LineNumber, "CyberArk: CloneRdpFile - " ErrorMessage)
		} 
		else {
			if (updateHosts) {
				; add entry to hosts file
				rc:= UpdateHostsFile("add",ip,serverName)
				if (rc < 0) {
					logError(A_LineNumber, "CyberArk: UpdateHostsFile (add), rc= " rc " - '" ErrorMessage "'")
				}
			} else {
				logWarning(A_LineNumber, "No update to hosts file")
			}
			
			if (rc >= 0) {
				; start mstsc
				rc:= StartProgram( serverName, commandLine, programTitle, gSettings.ConnectTimeout )
				if (rc < 0)
					logError(A_LineNumber, "CyberArk: StartProgram - " ErrorMessage)
				else {
					logInfo(A_LineNumber, "CyberArk: mstsc session started to '" serverName "'")
				}
				
				if (updateHosts) {
					; remove entry from hosts file
					rc:= UpdateHostsFile("remove",ip,serverName)
					if (rc < 0) {
						logError(A_LineNumber, "CyberArk: UpdateHostsFile (remove), rc= " rc " - '" ErrorMessage "'")
					}
				}
			}
		}
		; Release critical section for others to use
		SemaphoreRelease()

		if (gSettings.Cleanup) {
			logDebug(A_LineNumber, "CyberArk: Deleting '" cloneFilename "'")
			deleteFile(cloneFilename)
		} 
	} 
	else {
		ErrorMessage:= "Cannot acquire access to critical files in time."
		logError(A_LineNumber, "CyberArk: " ErrorMessage)
		rc:= -1
	}
	return rc
}

;---------------------------------------------------------------------------------
; Clone/Update RDP file
;
CloneRdpFile(pType,rdpFilename,cloneFilename,serverName:= "",&ip:= "", username:="")
{
	global gSettings, ErrorMessage
	global PAM_TYPE_BEYONDTRUST, PAM_TYPE_SYMANTEC, PAM_TYPE_SYMANTEC2, PAM_TYPE_SENHASEGURA, PAM_TYPE_CYBERARK
	rc:= 1
	
	;MsgBox(DisplayObj(gSettings))
	
	logDebug(A_LineNumber, "CloneRdpFile: pType= " pType ", rdpFilename= '" rdpFilename "', cloneFilename= '" cloneFilename "', serverName= '" serverName "'")
	;
	; Read rdp file and find/replace IP/DNS/Hostname with gServerName
	;
	try {
		content:= FileRead(rdpFilename)
	}
	catch as e{
		ErrorMessage:= "Cannot read file '" rdpFilename "'"
		logError(A_LineNumber, "CloneRdpFile: " ErrorMessage ", error=" e.Message)
		return -1
	}

	logTrace(A_LineNumber,"CloneRdpFile: Original content`n" content)
	
	; font smoothing
	if (gSettings.UseFontSmoothingDefined) {
		f:= gSettings.UseFontSmoothing
		if (InStr(content,"allow font smoothing")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'allow font smoothing' to '" f "'")
			content:= RegExReplace(content, "(allow font smoothing\:i)\:\d", "$1:" f)
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'allow font smoothing' with '" f "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "allow font smoothing:i:" f
		}
	}

	; session bpp
	if (gSettings.SessionBppDefined) {
		if (InStr(content,"session bpp")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'session bpp' to '" gSettings.SessionBpp "'")
			content:= RegExReplace(content, "(session bpp\:i)\:\d+", "$1:" gSettings.SessionBpp)
		}
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'session bpp' with '" gSettings.SessionBpp "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content "session bpp:i:" gSettings.SessionBpp
		}
	}
	
	; drive mapping
	if (gSettings.LocalDriveMappingDefined) {
		if (InStr(content,"drivestoredirect")) {
			; has drivestoredirect in RDP
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'drivestoredirect' to '" gSettings.LocalDriveMapping "'")
			content:= RegExReplace(content, "(drivestoredirect\:s)\:.*", "$1:" gSettings.LocalDriveMapping)
		}
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'drivestoredirect' with '" gSettings.LocalDriveMapping "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content "drivestoredirect:s:" gSettings.LocalDriveMapping
		}
	}
		
	; wallpaper
	if (gSettings.AllowWallpaperDefined) {
		f:= gSettings.AllowWallpaper
		
		if (InStr(content,"disable wallpaper")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'disable wallpaper' to '" f "'")
			content:= RegExReplace(content, "(disable wallpaper\:i)\:\d", "$1:" f)
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'disable wallpaper' with '" f "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "disable wallpaper:i:" f
		}

		; turn off networkautodetect
		if (InStr(content,"networkautodetect")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'networkautodetect' to '0'")
			content:= RegExReplace(content, "(networkautodetect\:i)\:\d", "$1:0")
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'networkautodetect' with '0'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "networkautodetect:i:0"
		}

		; set connection type
		if (InStr(content,"connection type")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'connection type' to '4'")
			content:= RegExReplace(content, "(connection type\:i)\:\d", "$1:4")
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'connection type' with '4'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "connection type:i:4"
		}

		; set bandwidthautodetect
		if (InStr(content,"bandwidthautodetect")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'bandwidthautodetect' to '0'")
			content:= RegExReplace(content, "(bandwidthautodetect\:i)\:\d", "$1:0")
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'bandwidthautodetect' with '0'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "bandwidthautodetect:i:0"
		}
	}

	; automatically accept security warning
	if (gSettings.AcceptSecurityMessagesDefined) {

		f:= (gSettings.AcceptSecurityMessages) ? 0 : 2

		if (InStr(content,"authentication level")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'authentication level' to '" f "'")
			content:= RegExReplace(content, "(authentication level\:i)\:\d", "$1:" f)
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'authentication level' with '" f "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "authentication level:i:" f
		}
	}

	; smart sizing
	if (gSettings.UseSmartSizingDefined) {

		f:= gSettings.UseSmartSizing
		if (InStr(content,"smart sizing")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'smart sizing' to '" f "'")
			content:= RegExReplace(content, "(smart sizing\:i)\:\d", "$1:" f)
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'smart sizing' with '" f "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "smart sizing:i:" f
		}
	}

	if (StrLen(serverName) > 0) {
		; If a serverName is given find the server IP address
		; and update the connection name in the rdp file
		
		if (pType == PAM_TYPE_BEYONDTRUST) {
			idx:= -1
			for i, elm in gSettings.PamInfo {

				match:= StrReplace(elm, ".", "\.")
				logTrace(A_LineNumber, "CloneRdpFile: i= " i ", elm= '" elm "', match= '" match "'")

				content:= RegExReplace(content, "(full address\:s)\:" match, "$1:" serverName, &found)
				if (found>0) {
					logDebug(A_LineNumber, "CloneRdpFile: Updated 'full address' to '" serverName "'")
					; idx is the loadbalancer/server index. 
					idx:= floor((i-1) / 3)
					logDebug(A_LineNumber, "CloneRdpFile: found i=" i ", idx=" idx ", elm=" elm)
					break
				}
			}
			if (idx == -1) {
				ErrorMessage:= "PAM server entry not found in '" rdpFilename "'"
				logWarning(A_LineNumber, "CloneRdpFile: " ErrorMessage)
				;logWarning(A_LineNumber, "CloneRdpFile: content`n" content)
				; return -2
				rc:= 2
			} 
			else {
				ip:= gSettings.PamInfo[1+3*idx]
				logDebug(A_LineNumber, "CloneRdpFile: ip= '" ip "'")
			}
		}
		if (pType == PAM_TYPE_SENHASEGURA | pType == PAM_TYPE_CYBERARK) {
			; an address is not found in content
			; add first gPamInfo address

			ip:= gSettings.PamInfo[1]
			logDebug(A_LineNumber, "CloneRdpFile: ip= '" ip "'")

			if (InStr(content,"full address")) {
				; has 'full address' in RDP
				logDebug(A_LineNumber, "CloneRdpFile: Updating 'full address' to '" serverName "'")
				content:= RegExReplace(content, "(full address\:s)\:.*", "$1:" serverName)
			}
			else {
				logDebug(A_LineNumber, "CloneRdpFile: Adding 'full address' with '" serverName "'")
				if (SubStr(content,-1) != "`n")
					content:= content "`n"
				content:= content "full address:s:" serverName
			}
		}
	}

	; username
	if (StrLen(username) > 0) {
		if (InStr(content,"username")) {
			logDebug(A_LineNumber, "CloneRdpFile: Updating 'username' to '" username "'")
			content:= RegExReplace(content, "(drivestoredirect\:s)\:.*", "$1:" username)
		} 
		else {
			logDebug(A_LineNumber, "CloneRdpFile: Adding 'username' with '" username "'")
			if (SubStr(content,-1) != "`n")
				content:= content "`n"
			content:= content  "username:s:" username
		}
	}
	
	content:= StrReplace(content, "`r`n", "`n")
	content:= StrReplace(content, "`n`n", "`n")
	content:= content "`n"
	
	logTrace(A_LineNumber, "CloneRdpFile: Updated content`n" content)
	
	; finally, write the updated content to file
	try {
		if (FileExist(cloneFilename))
			FileDelete(cloneFilename)
		FileAppend(content, cloneFilename, "UTF-8-RAW")
	} 
	catch as e{
		ErrorMessage:= "Cannot create RDP file '" cloneFilename "'"
		logError(A_LineNumber, "CloneRdpFile: " ErrorMessage ", lastError= " e.Message )
		rc:= -3
	}

	logDebug(A_LineNumber, "CloneRdpFile: finished, rc= " rc)
	return rc
}

;---------------------------------------------------------------------------------
; Start program from RDP file. 
;
StartProgram(serverName,command,title,timeout)
{
	global ErrorMessage

	logDebug(A_LineNumber, "StartProgram: serverName= '" serverName "', command= '" command "', title= '" title "', timeout= " timeout)

	; if the title starts with "ahk_class " the windowTitle match is a className
	useClass:= false
	if (RegExMatch(title, "i)^ahk_class\s+(.*)$", &x) >0) {
		useClass:= true
		className:= x[1]
		logDebug(A_LineNumber, "StartProgram: className= " className)
	} 
	
	; run the program
	try {
		Run(command,,,&pid)
	}
	catch as e
	{
		ErrorMessage:= "Program is not found or cannot be started"
		logError(A_LineNumber, "StartProgram: " ErrorMessage ", lastError= " e.message)
		return -1
	}
	logDebug(A_LineNumber, "StartProgram: Run pid= " pid)
	
	if (!WinWait("ahk_pid " pid,,timeout))
	{
		ErrorMessage:= "Timeout starting program"
		logError(A_LineNumber, "StartProgram: " ErrorMessage)
		return -2
	}
	HotIfWinNotActive "ahk_pid " pid
		WinActivate("ahk_pid " pid)
	
	if (!WinWaitActive("ahk_pid " pid,, 10))
	{
		ErrorMessage:= "Program cannot become active"
		logError(A_LineNumber, "StartProgram: " ErrorMessage)
		return -3
	}

	; Wait for the window
	if (useClass) {
		logDebug(A_LineNumber, "StartProgram: Waiting for program pid= " pid ", class= '" className "'")
		hwnd:= WinWait("ahk_pid " pid " ahk_class " className,,timeout)
	}
	else {
		logDebug(A_LineNumber, "StartProgram: Waiting for program pid= " pid ", title= '" title "'")
		hwnd:= WinWait(title " ahk_pid " pid ,,timeout)
	}
	if (!hwnd)
	{
		currentTitle:= WinGetTitle("ahk_pid " pid)
		logDebug(A_LineNumber, "StartProgram: pid= " pid ", currentTitle= '" currentTitle "'")
		ErrorMessage:= "Expected program window is not found"
		logError(A_LineNumber, "StartProgram: " ErrorMessage)
		return -4
	}
	
	if (serverName != "") {
		; set new windows title for window having the right pid and class
		loop gSettings.ConnectTimeout
		{
			currentTitle:= WinGetTitle("ahk_pid " pid " ahk_class TscShellContainerClass")
			logDebug(A_LineNumber, "StartProgram: pid= " pid ", severName= '" serverName "', currentTitle= '" currentTitle "' -- looking")
			if (InStr(currentTitle,serverName)) {
				logDebug(A_LineNumber, "StartProgram: pid= " pid ", severName= '" serverName "', currentTitle= '" currentTitle "' -- found")
				break
			} else {
				Sleep(2000)
			}
		}

		WinSetTitle(serverName, "ahk_pid " pid " ahk_class TscShellContainerClass")
		logDebug(A_LineNumber, "StartProgram: Changed window title to '" serverName "'")

		if (gSettings.ScreenMode = "Maximize") {
			logDebug(A_LineNumber, "StartProgram: Maximize window")
			WinMaximize("ahk_pid " pid)
		}
	}

	logDebug(A_LineNumber, "StartProgram: Program started")
	if (gLogLevel >= LOG_TRACE)
		MsgBox("mstsc started")
	return pid
}

;---------------------------------------------------------------------------------
getCloneFilename( serverName )
{
	cloneFilepath:= A_Temp
	logDebug(A_LineNumber, "getCloneFilename: cloneFilepath= '" cloneFilepath "'")
	if (InStr(cloneFilepath,"~")) {
		cloneFilepath:= GetLongPathName( cloneFilepath )
		logDebug(A_LineNumber, "getCloneFilename: Long cloneFilepath= '" cloneFilepath "'")
	}
	ts:= FormatTime(, "yyyyMMddhhmmss")
	cloneFilename:= cloneFilepath "\PAM-RDP-" serverName "-" ts ".rdp"
	logDebug(A_LineNumber, "getCloneFilename: serverName= '" serverName "', cloneFilename= '" cloneFilename "'")

	return cloneFilename
}

;---------------------------------------------------------------------------------
deleteFile( filename )
{
	logDebug(A_LineNumber, "deleteFile: Deleting '" filename "'")
	try {
		if (FileExist(filename))
			FileDelete(filename)
		logInfo(A_LineNumber, "deleteFile: Deleted file '" filename "'")
	} 
	catch as e
	{
		ErrorMessage:= "Cannot delete file '" filename "'"
		logError(A_LineNumber, "deleteFile: " ErrorMessage)
		logDebug(A_LineNumber, "deleteFile: " e.Message)
	}
}

;---------------------------------------------------------------------------------
; read pam-rdp.properties
;
ReadProperties( filename, pType:= 0, settings:= 0 )
{
	global PROPERTY_TYPE_USER, PROPERTY_TYPE_SYSTEM
	global PAM_TYPE_BEYONDTRUST, PAM_TYPE_SYMANTEC, PAM_TYPE_SENHASEGURA, PAM_TYPE_CYBERARK
	global LOG_ERROR, LOG_WARNING, LOG_INFO, LOG_DEBUG, LOG_TRACE
	global gLogLevel, ErrorMessage
	
	if (!isObject(settings)) {
		settings:= object()
	}
	
	logDebug(A_LineNumber, "readProperties: pType= " pType ", filename= " filename )
	if (pType = 0) {
		pType:= PROPERTY_TYPE_USER
		logDebug(A_LineNumber, "readProperties: pType set to " pType )
	}
	
	if (!FileExist(filename)) {
		logAlways(A_LineNumber, "readProperties: file not found '" filename "' - use defaults")
	}

	settings.PropertyFilename:= filename

	if (pType = PROPERTY_TYPE_USER) {

		; Default settings
		
		defNotSet:= "Not Set"
		defScreenMode:= "Fullscreen"
		defWindowWidth:= 1024
		defWindowHeight:= 768
		defUseFontSmoothing:= "true"
		defSessionBpp:= 24
		defLocalDriveMapping:= ""
		defAllowWallpaper:= "false"
		defAcceptSecurityMessages:= "true"
		defUseSmartSizing:= "false"
		defCleanup:= "true"
		defLogLevel:= "DEBUG"
		defConnectTimeout:= 60
		defPromptTimeout:= 15

		; -----	
		x := IniRead(filename, "main", "LogLevel", defLogLevel)
		switch x
		{
		case "ERROR":   settings.LogLevel:= LOG_ERROR
		case "WARNING": settings.LogLevel:= LOG_WARNING
		case "INFO":    settings.LogLevel:= LOG_INFO
		case "DEBUG":   settings.LogLevel:= LOG_DEBUG
		case "TRACE":   settings.LogLevel:= LOG_TRACE
		Default:        settings.LogLevel:= LOG_DEBUG
		}
		gLogLevel:= settings.LogLevel
		logAlways(A_LineNumber, "ReadProperties: LogLevel= '" settings.LogLevel "'")
		
		;----------------------
		; Cleanup
		;----------------------
		x := IniRead(filename, "main", "cleanup", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: cleanup = '" x "' (file/default)")
		settings.CleanupDefined:= (x != defNotSet)
		settings.Cleanup:= !InStr(x, "false")
		logInfo(A_LineNumber, "ReadProperties: cleanup = '" settings.Cleanup "' (final)")
					
		;----------------------
		; ConnectTimeout
		;----------------------
		x:= IniRead(filename, "main", "ConnectTimeout", defConnectTimeout)
		logDebug(A_LineNumber, "ReadProperties: ConnectTimeout= '" x "' (file/default)")
		if (!IsInteger(x) or IsSpace(x) or x <= 0 or x >= 900) {
			x:= defConnectTimeout
		}
		settings.ConnectTimeout:= Integer(x)
		logInfo(A_LineNumber, "ReadProperties: ConnectTimeout= '" settings.ConnectTimeout "' (final)")

		;----------------------
		; PromptTimeout
		;----------------------
		x:= IniRead(filename, "main", "promptTimeout", defPromptTimeout)
		logDebug(A_LineNumber, "ReadProperties: PromptTimeout= '" x "' (file/default)")
		if (!IsInteger(x) or IsSpace(x) or x <= 0 or x >= 60) {
			x:= defPromptTimeout
		}
		settings.PromptTimeout:= Integer(x)
		logInfo(A_LineNumber, "ReadProperties: PromptTimeout= '" settings.PromptTimeout "' (final)")

		;----------------------
		; ScreenMode / Width, Height
		;----------------------
		x:= IniRead(filename, "main", "screenMode", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: ScreenMode= '" x "' (file/default)")
		settings.ScreenModeDefined:= (x != defNotSet)
		if (!RegExMatch(x, "i)(Window|Fullscreen|Maximize)")) {
			x:= "Fullscreen"
		}
		settings.ScreenMode:= x
		logInfo(A_LineNumber, "ReadProperties: ScreenMode= '" settings.ScreenMode "' (final)")
		
		if (settings.ScreenMode = "Fullscreen") {
			locWidth:= defWindowWidth
			locHeight:= defWindowHeight
		}
		else if (settings.ScreenMode = "Maximize") {
			settings.ScreenMode:= "Maximize"
			MonitorGetWorkArea(A_Index, &MonitorWorkAreaLeft, &MonitorWorkAreaTop, &MonitorWorkAreaRight, &MonitorWorkAreaBottom)
			SM_CYCAPTION := SysGet(4)
			locWidth:= MonitorWorkAreaRight
			locHeight:= MonitorWorkAreaBottom-SM_CYCAPTION
		} 
		else if (settings.ScreenMode = "Window") {
			settings.ScreenMode:= "Window"
			locWidth := IniRead(filename, "main", "windowWidth", defWindowWidth)
			logDebug(A_LineNumber, "ReadProperties: WindowWidth= '" locWidth "' (file/default)")
			if (!IsInteger(locWidth) or locWidth<=0)
				locWidth:= defWindowWidth

			locHeight := IniRead(filename, "main", "windowHeight", defWindowHeight)
			logDebug(A_LineNumber, "ReadProperties: WindowHeight= '" locHeight "' (file/default)")
			if (!IsInteger(locHeight) or locHeight<=0)
				locHeight:= defWindowHeight
		} else {
			settings.ScreenMode:= "Fullscreen"
		}
		settings.WindowWidth:= Integer(locWidth)
		settings.WindowHeight:= Integer(locHeight)
		logInfo(A_LineNumber, "ReadProperties: ScreenMode= " settings.ScreenMode ", WindowWidth= " settings.WindowWidth ", WindowHeight=" settings.WindowHeight " (final)")

		;----------------------
		; UseFontSmoothing
		;----------------------
		x := IniRead(filename, "main", "UseFontSmoothing", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: UseFontSmoothing= '" x "' (file/default)")
		settings.UseFontSmoothingDefined:= (x != defNotSet)
		settings.UseFontSmoothing:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: UseFontSmoothing= '" settings.UseFontSmoothing "' (final)")
		
		;----------------------
		; AllowWallpaper
		;----------------------
		x := IniRead(filename, "main", "wallpaper", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: wallpaper= '" x "' (file/default)")
		settings.AllowWallpaperDefined:= (x != defNotSet)
		settings.AllowWallpaper:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: wallpaper= '" settings.AllowWallpaper "' (final)")

		;----------------------
		; SessionBpp
		;----------------------
		x := IniRead(filename, "main", "sessionBpp", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: sessionBpp= '" x "' (file/default)")
		settings.SessionBppDefined:= (x != defNotSet)
		if (x != 16 and x != 24 and x != 32)
			x:= defSessionBpp
		settings.SessionBpp:= Integer(x)
		logInfo(A_LineNumber, "ReadProperties: sessionBpp= '" settings.SessionBpp "' (final)")
		
		;----------------------
		; LocalDriveMapping
		;----------------------
		x:= IniRead(filename, "main", "localDriveMapping", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: localDriveMapping= '" x "' (file/default/final)")
		settings.LocalDriveMappingDefined:= (x != defNotSet)
		settings.LocalDriveMapping:= x

		;----------------------
		; AcceptSecurityMessages
		;----------------------
		x := IniRead(filename, "main", "acceptSecurityMessages", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: acceptSecurityMessages= '" x "' (file/default)")
		settings.AcceptSecurityMessagesDefined:= (x != defNotSet)
		settings.AcceptSecurityMessages:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: acceptSecurityMessages= '" settings.AcceptSecurityMessages "' (final)")
		
		;----------------------
		; UseSmartSizing
		;----------------------
		x := IniRead(filename, "main", "useSmartSizing", defNotSet)
		logDebug(A_LineNumber, "ReadProperties: UseSmartSizing= '" x "' (file/default)")
		settings.UseSmartSizingDefined:= (x != defNotSet)
		settings.UseSmartSizing:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: UseSmartSizing= '" settings.UseSmartSizing "' (final)")
	}
	
	if (pType = PROPERTY_TYPE_SYSTEM) {
		; Default settings
		
		defPamType:= PAM_TYPE_BEYONDTRUST
		defHeartbeat:= "true"
		defHeartbeatProgram:= "C:\Program Files\PAM-Exchange\PAM-RDP-Heartbeat\pam-rdp-heartbeat.exe"
		defProgram:= "C:\Windows\system32\mstsc.exe"
		defMultiUser:= "false"

		;----------------------
		; pamType
		;----------------------
		x:= IniRead(filename, "main", "PAMtype", defPamType)
		logDebug(A_LineNumber, "ReadProperties: PamType= '" x "' (file/default)")
		match:= "i)(" PAM_TYPE_BEYONDTRUST "|" PAM_TYPE_SYMANTEC "|" PAM_TYPE_SENHASEGURA "|" PAM_TYPE_CYBERARK ")"
		if (!RegExMatch(x,match)) {
			x:= PAM_TYPE_BEYONDTRUST
			logWarning(A_LineNumber, "ReadProperties: PamType not OK, using default")
		}
		settings.pamType:= x
		logInfo(A_LineNumber, "ReadProperties: PamType= '" settings.pamType "' (final)")
		
		;----------------------
		; heartbeat
		;----------------------
		x:= IniRead(filename, "main", "heartbeat", defHeartbeat)
		logDebug(A_LineNumber, "ReadProperties: Heartbeat= '" x "' (file/default)")
		settings.Heartbeat:= InStr(x,"true")
		logInfo(A_LineNumber, "ReadProperties: Heartbeat= '" settings.Heartbeat "' (final)")

		if (settings.Heartbeat) {
			x:= IniRead(filename, "main", "heartbeatprogram", defHeartbeatProgram)
			logDebug(A_LineNumber, "ReadProperties: Heartbeat= '" x "' (file/default)")
			settings.HeartbeatProgram:= x
			logInfo(A_LineNumber, "ReadProperties: HeartbeatProgram= '" settings.HeartbeatProgram "' (final)")
		}

		;----------------------
		; Program
		;----------------------
		x:= IniRead(filename, "main", "mstscProgram", defProgram)
		logDebug(A_LineNumber, "ReadProperties: Program= '" x "' (file/default)")
		settings.Program:= x
		logInfo(A_LineNumber, "ReadProperties: Program= '" settings.Program "' (final)")

		;----------------------
		; MultiUser
		;----------------------
		x:= IniRead(filename, "main", "multiUser", defMultiUser)
		logDebug(A_LineNumber, "ReadProperties: MultiUser= '" x "' (file/default)")
		settings.MultiUser:= InStr(x,"true")
		logInfo(A_LineNumber, "ReadProperties: MultiUser= '" settings.MultiUser "' (final)")

		;----------------------
		; Port
		;----------------------
		if (settings.pamType = PAM_TYPE_BEYONDTRUST) {
			defPort:= 4489
		}
		else { 
			defPort:= 3389
		}
		x:= IniRead(filename, settings.pamType, "Port", defPort)
		logDebug(A_LineNumber, "ReadProperties: Port= '" x "' (file/default)")
		settings.Port:= (!IsInteger(x) or IsSpace(x)) ? defPort : Integer(x)
		logInfo(A_LineNumber, "ReadProperties: MultiUser= '" settings.Port "' (final)")

		;----------------------
		; CntServer
		;----------------------
		defCntServer:= 0
		x:= IniRead(filename, settings.pamType, "cntServer", defCntServer)
		logDebug(A_LineNumber, "ReadProperties: CntServer= '" x "' (file/default)")
		settings.CntServer:= (!IsInteger(x) or IsSpace(x)) ? defCntServer : Integer( x )
		logInfo(A_LineNumber, "ReadProperties: CntServer= '" settings.CntServer "' (final)")

		;----------------------
		; PamInfo / servers
		;----------------------
		PamInfo:= []
		err:= "ERROR"
		Loop settings.CntServer {
			x:= IniRead(filename, "Server" A_Index, "ip", err)
			y:= IniRead(filename, "Server" A_Index, "dns", err)
			z:= IniRead(filename, "Server" A_Index, "hostname", err)
			If (err != x and err != y and err != z) {
				PamInfo.push(x)
				PamInfo.push(y)
				PamInfo.push(z)
				logDebug(A_LineNumber, "ReadProperties: server - index= " A_Index ", ip= " x ", dns= " y ", hostname= " z)
			}
			else {
				logError(A_LineNumber, "ReadProperties: server - index= " A_Index ", ip= " x ", dns= " y ", hostname= " z)
			}
		}
		settings.PamInfo:= pamInfo

		; --- BeyondTrust (extra) ---
		if (settings.PamType == PAM_TYPE_BEYONDTRUST) {
		}

		; --- Senhasegura (extra) ---
		if (settings.PamType == PAM_TYPE_SENHASEGURA) {
		}

		; --- Symantec ---
		if (settings.PamType == PAM_TYPE_SYMANTEC) {
		}

		; --- CyberArk ---
		if (settings.PamType == PAM_TYPE_CYBERARK) {
		}
	}

	; MsgBox(DisplayObj(settings))
	
	return settings
}	

;---------------------------------------------------------------------------------
is64bit(){
    Return A_PtrSize = 8 ? 1 : 0
}

;---------------------------------------------------------------------------------
SemaphoreAcquire( timeout ) {
	global gLockFilename, gLockHandle, ErrorMessage
	
	EndTime:= A_TickCount+timeout
	
	Loop {
		gLockHandle:= FileOpen(gLockFilename, "rw-")
		if (gLockHandle) {
			logDebug(A_LineNumber, "SemaphoreAcquire: acquired - lockFilename= '" gLockFilename "', currentTime= " A_TickCount ", endTime= " EndTime)
			return 1
		}
		
		logDebug(A_LineNumber, "SemaphoreAcquire: waiting - lockFilename= '" gLockFilename "', currentTime= " A_TickCount ", endTime= " EndTime)
		Sleep 1000
		
	} Until A_TickCount>EndTime

	ErrorMessage:= "Timeout waiting for semaphore."
	logError(A_LineNumber, "SemaphoreAcquire: " ErrorMessage " - currentTime= " A_TickCount ", endTime= " EndTime)
	return 0
}

;---------------------------------------------------------------------------------
SemaphoreRelease() {
	global gLockHandle
	
	if (gLockHandle) {
		logDebug(A_LineNumber, "SemaphoreRelease: released")
		gLockHandle.close
		gLockHandle:= 0
	}
}

;---------------------------------------------------------------------------------
PipeMessage(msg, pipename:= "", timeout:= 10000) {

	global gLockFilename, gPipeName, ErrorMessage
	
	rc:= 0
	ErrorMessage:= ""
	if (strlen(pipename) == 0)
		pipename:= gPipeName
	
	logDebug(A_LineNumber, "PipeMessage: msg= '" msg "', pipename= '" pipename "', timeout= " timeout)
	
	if (!DllCall("WaitNamedPipe", "Str", "\\.\pipe\" pipename, "UInt", timeout)) {
		ErrorMessage:= "WaitNamedPipe failed, lastError= " A_LastError
		logError(A_LineNumber, "PipeMessage: " ErrorMessage)
		rc:= -1
	}
	else {
		Pipe := DllCall("CreateFile", "Str", "\\.\pipe\" pipename, "UInt", 0x80000000 | 0x40000000, "UInt", 0, "Ptr", 0, "UInt", 0x00000003, "UInt", 0x00000080, "Ptr", 0)
		if (!Pipe) {
			ErrorMessage:= "CreateFile failed, lastError= " A_LastError
			logError(A_LineNumber, "PipeMessage: " ErrorMessage)
			rc:= -2
		}
		else {
			BUFF_SIZE:= StrLen(msg)+1
			Buff:= Buffer(BUFF_SIZE,0)
			StrPut(msg, Buff, "CP0")
			
			if (!DllCall("WriteFile", "Ptr",Pipe, "Ptr",buff, "UInt",(StrLen(msg)), "UInt*",0, "Ptr",0)) {
				ErrorMessage:= "WriteFile failed, lastError= " A_LastError
				logError(A_LineNumber, "PipeMessage: " ErrorMessage)
				rc:= -3
			}
			else {
				Bytes:= 0
				Buff:= "***********************************************************************************************************************************"
				if (!DllCall("ReadFile", "Ptr",Pipe, "Str",Buff, "UInt",StrLen(Buff)-1, "UInt*",Bytes, "Ptr",0)) {
					ErrorMessage:= "ReadFile failed, lastError= " A_LastError
					logError(A_LineNumber, "PipeMessage: " ErrorMessage)
					rc:= -5
				}
				else {
					rsp:= StrGet(StrPtr(Buff),"CP0")
					logDebug(A_LineNumber, "PipeMessage: rsp= -->" rsp "<--")
					;MsgBox( "Pipe - ReadFile`nbuff`n" buff "`nrsp`n" rsp)
					if (InStr(rsp,"OK")==1) {
						;logDebug(A_LineNumber, "PipeMessage: rsp= OK")
						rc:= 1
					} 
					else {
						ErrorMessage:= rsp
						logError(A_LineNumber, "PipeMessage: rsp= " ErrorMessage)
						rc:= -4
					}
				}
			}
			
			DllCall("CloseHandle", "Ptr",Pipe)
		}
	} 
	return rc
}

;---------------------------------------------------------------------------------
; Update hosts files
;
UpdateHostsFile( cmd, ip, hostname )
{
	logDebug(A_LineNumber, "UpdateHostsFile: cmd= '" cmd "', ip= '" ip "', hostname= '" hostname "'")
	
	msg:= cmd " " ip " " hostname

	logDebug(A_LineNumber, "UpdateHostsFile: msg= '" msg "'")
	rc:= PipeMessage(msg)
	return rc
}

;---------------------------------------------------------------------------------
GetLongPathName(path)
{
	Buff:= "***************************************************************************************************************************************************"
	Buff:= Buff Buff Buff

	logTrace(A_LineNumber, "GetLongPathName: path= " path)
	rc:= DllCall("GetLongPathName", "Str",path, "Str",&Buff, "UInt",strlen(Buff))
	logTrace(A_LineNumber, "GetLongPathName: rc= " rc ", LastError= " A_LastError)
	logTrace(A_LineNumber, "GetLongPathName: Buff= " Buff)

	return Buff
}

;--------------------------------------------------------------------------------------------------------
; DisplayObj by FanaticGuru (inspired by tidbit and Lexikos v1 code)
DisplayObj(Obj, Depth := 5, IndentLevel := '')
{
	List := ''
	If Type(Obj) ~= 'Object|Gui'
		Obj := Obj.OwnProps()
	For k, v in Obj
	{
		List .= IndentLevel '[' k '] <' Type(v) '>'
		If (IsObject(v) && Depth > 1)
			List .= '`n' DisplayObj(v, Depth - 1, IndentLevel . '    ')
		Else
			If !isobject(v)
				List .= ' => ' v
		List .= '`n'
	}
	Return RTrim(List)
}

;--------------------------------------------------------------------------------------------------------
LogRoll(filename, maxSize:= 5, keep:=5) 
{

	; Roll files if the filename is larger than maxSize. 
	; Copy/move filename.4 to filename.5, filename.3 to filename.4, etc.
	; finally copy/move filename to filename.1
	; filename with highest index (keep value) is replaced with previous index file.
	
	if (maxSize < 1) 
		maxSize:= 1
	
	try {
		size:= FileGetSize(filename, "M")
	}
	catch {
		size:= 0
	}
	if (size>=maxSize) {
		logDebug(A_LineNumber, "LogRoll: roll files - filename= '" filename "', size= " size " MB, maxSize= " maxSize " MB")
		while (keep>1) {
			fn1:= filename "." keep
			fn2:= filename "." (keep-1)
			FileMove(fn2, fn1, "true")	; move and overwrite if exist
			if (A_LastError) {
				; using explicit filename, thus errorlevel is only set if the file exist and 
				; the move is unsuccessful. 
				ErrorMessage:= "Cannot copy/move '" fn2 "' to '" fn1 "', lastError= " A_LastError
				logError(A_LineNumber, "LogRoll: " ErrorMessage)
			}
			keep:= keep-1
		}
		FileMove(filename, fn2, "true")
		if (A_LastError) {
			; using explicit filename, thus errorlevel is only set if the file exist and 
			; the move is unsuccessful. 
			ErrorMessage:= "Cannot copy/move '" filename "' to '" fn2 "', lastError= " A_LastError
			logError(A_LineNumber, "LogRoll: " ErrorMessage)
		}
	}
}

;--------------------------------------------------------------------------------------------------------
log(level, line, msg) {
	global LOG_ERROR, LOG_WARNING, LOG_INFO, LOG_DEBUG, LOG_TRACE
	global gLogLevel
	global gSelfPidHex
	if (level <= gLogLevel) { 
		if (level == LOG_ALWAYS)
			levelTxt:= "ALW"
		if (level == LOG_ERROR)
			levelTxt:= "ERR"
		if (level == LOG_WARNING)
			levelTxt:= "WRN"
		if (level == LOG_INFO)
			levelTxt:= "INF"
		if (level == LOG_DEBUG)
			levelTxt:= "DBG"
		if (level == LOG_TRACE)
			levelTxt:= "TRC"
		
		TimeString := FormatTime(, "yy/MM/dd HH:mm:ss")
		txt:= TimeString " [" gSelfPidHex "] " levelTxt " " msg " [" line "]`n"
		h:= FileOpen(gLogFile,"a")
		h.write(txt)
		h.close()
	}
}

logTrace(line, msg) {
	global LOG_TRACE
	log(LOG_TRACE,line,msg)
}

logDebug(line, msg) {
	global LOG_DEBUG
	log(LOG_DEBUG,line,msg)
}

logInfo(line, msg) {
	global LOG_INFO
	log(LOG_INFO,line,msg)
}

logWarning(line, msg) {
	global LOG_WARNING
	log(LOG_WARNING,line,msg)
}

logError(line, msg) {
	global LOG_ERROR
	log(LOG_ERROR,line,msg)
}

logAlways(line, msg) {
	global LOG_ALWAYS
	log(LOG_ALWAYS,line,msg)
}
;--- end of script ---
