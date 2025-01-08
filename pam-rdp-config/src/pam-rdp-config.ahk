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
#SingleInstance force
Persistent true
DetectHiddenWindows true

;OnMessage(0x16, SystemEvent)

;-------
; Information about the script 
SplitPath(A_ScriptFullPath, , , , &gScriptName)
gVersion:= "2.9.0"

global gProgramTitle:= "PAM RDP Connect Configuration"		; title for pop-up messages

global gSelfPid:= DllCall("GetCurrentProcessId")
global gSelfPidHex:= Format("{:04x}",gSelfPid)

;-------
if (A_Args.Length == 1) {
	if (RegExMatch(A_Args[1], "i)(--|-|/)?(V|Ver|Version)")) {
		MsgBox("Version " gVersion,gProgramTitle, "IconI")
		ExitApp
	}
	if (RegExMatch(A_Args[1], "i)(--|-|/)?(L|Lic|Licens)")) {
		MsgBox("License " gVersion,gProgramTitle, "IconI")
		ExitApp
	}
}

global LOG_ALWAYS:= 0
global LOG_ERROR:= 1
global LOG_WARNING:= 2
global LOG_INFO:= 3
global LOG_DEBUG:= 4
global LOG_TRACE:= 5

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

LogAlways(A_LineNumber, "-------- version " gVersion)

; roll log files before we begin
LogRoll(gLogFile,5,5)

; ---------
; Set property file and read content
;--------

global PROPERTY_TYPE_USER:= 1
global PROPERTY_TYPE_SYSTEM:= 2

SplitPath(A_ScriptFullPath, , &dir, &ext, &name)
propertyFilename:= "pam-rdp.user.properties"
global installPropertyFilename:= dir "\" propertyFilename
userPropertyPath:= A_AppData "\PAM-Exchange\PAM-RDP-Connect"
global userPropertyFilename:= userPropertyPath "/" propertyFilename
userPropertyFilename:= StrReplace(userPropertyFilename, "/", "\")

if (!FileExist(userPropertyPath)) {
	DirCreate(userPropertyPath)
}

if (FileExist(userPropertyFilename)) {
	global loadPropertyFilename:= userPropertyFilename
} 
else {
	global loadPropertyFilename:= installPropertyFilename
}

; Read properties
global gSettings:= ReadProperties(loadPropertyFilename,PROPERTY_TYPE_USER)
global displayPropertyFilename:= StrReplace( loadPropertyFilename, "PAM-Exchange\PAM-RDP-Connect", "...")
gSettings.displayPropertyFilename:= displayPropertyFilename

; Load texts, build gui and show it
global gTexts:= GetTexts()
global myGui:= GuiBuild()
GuiSetValues(myGui,gSettings)
myGui.Show("autosize")
WinWaitClose(gProgramTitle)
ExitApp

;--------------------------------------------------------------------------------------------------------
GuiBuildMenu() 
{
	global gTexts

	Tray:= A_TrayMenu
	Tray.Delete() ; V1toV2: not 100% replacement of NoStandard, Only if NoStandard is used at the beginning
	;Menu, Tray, MainWindow
	Tray.Add("Show", MyGui_Show)
	Tray.Add()
	Tray.Add("Exit", MyGui_Close)
	Tray.Default := "Show"
	;Tray.Tip(gProgramTitle)
	;Tray.Click("1")

	FileMenu := Menu()
	FileMenu.Add(gTexts.mnuFileOpenTxt, mnuFileOpenEvent)
	FileMenu.Add(gTexts.mnuFileSaveTxt, mnuFileSaveEvent)
	FileMenu.Add(gTexts.mnuFileSaveAsTxt, mnuFileSaveAsEvent)
	FileMenu.Add()
	FileMenu.Add(gTexts.mnuFileExitTxt, MyGui_Close)

	HelpMenu := Menu()
	HelpMenu.Add(gTexts.mnuHelpQuickGuideTxt, mnuHelpQuickGuideEvent)
	HelpMenu.Add()
	HelpMenu.Add(gTexts.mnuHelpAboutTxt, mnuHelpAboutEvent)

	; Attach the sub-menus that were created above.
	global MyMenuBar := MenuBar()
	MyMenuBar.Add(gTexts.mnuFileTxt, FileMenu)
	MyMenuBar.Add(gTexts.mnuHelpTxt, HelpMenu)
	
	return MyMenuBar
}

;--------------------------------------------------------------------------------------------------------
GuiBuild() {
	global gTexts
	global gSettings

	myGui:= GUI("+SysMenu +Owner -ToolWindow +MinimizeBox -MaximizeBox +E0x40000",gProgramTitle)
	myGui.MenuBar:= GuiBuildMenu()
	myGui.OnEvent("Close", MyGui_Close)
	myGui.OnEvent("Size", MyGui_Size)

	global margin:= 10
	myGui.MarginX:= myGui.MarginY:= margin

	edtWidth1:= 60
	edtWidth2:= 200

	global btnWidth:= 2*margin+MaxLength(gTexts.btnOkTxt, gTexts.btnOk2Txt,gTexts.btnCancelTxt)
	global btnWidthBorder:= 2

	wMax:= MaxLength( gTexts.ConnectTimeoutTxt, gTexts.PromptTimeoutTxt, gTexts.ScreenModeTxt, gTexts.UseFontSmoothingTxt, gTexts.allowWallpaperTxt, gTexts.sessionBppTxt, gTexts.localDriveMappingTxt, gTexts.AcceptSecurityMessagesTxt, gTexts.useSmartSizingTxt, gTexts.cleanupTxt, gTexts.logLevelTxt )

	rdoSize:= 32
	w1:= 3*rdoSize+GetTextSize(gTexts.screenModeWindowTxt)+GetTextSize(gTexts.screenModeMaximizeTxt)+GetTextSize(gTexts.screenModeFullscreenTxt)
	w2:= 64+GetTextSize(gTexts.ScreenModeWindowSizeTxt)+2*edtWidth1+GetTextSize(gTexts.ScreenModeWindowMultiplyTxt)
	w1:= 2*margin+ (w1<w2 ? w2:w1)
	w2:= wMax+edtWidth2
	gb2Width:= 2*margin+ (w1<w2 ? w2:w1)
	
	w1:= GetTextSize(displayPropertyFilename,,700)
	w2:= gb2Width
	gb1Width:= 2*margin+(w1<w2 ? w2:w1)

	myGui.Add("GroupBox", "xm+" margin " ym+" margin*2 " w" gb2Width " R3", gTexts.ScreenModeTxt)

	;--- ScreenMode
	;myGui.Add("Text", "xm section +right w" wMax, gTexts.ScreenModeTxt)
	ctrlScreenModeWindow:= myGui.Add("Radio", "x" 3*margin " yp+24 Group vctrlScreenModeWindow", gTexts.screenModeWindowTxt)
	ctrlScreenModeWindow.OnEvent("Click", ScreenModeSizeEnable.Bind("Window"))
	
	ctrlScreenModeMaximize:= myGui.Add("Radio", "yp vctrlScreenModeMaximize", gTexts.screenModeMaximizeTxt)
	ctrlScreenModeMaximize.OnEvent("Click", ScreenModeSizeEnable.Bind("Maximize"))
	
	ctrlScreenModeFullscreen:= myGui.Add("Radio", "yp vctrlScreenModeFullscreen", gTexts.screenModeFullscreenTxt)
	ctrlScreenModeFullscreen.OnEvent("Click", ScreenModeSizeEnable.Bind("Fullscreen"))

	ctrlScreenModeWindowSizeTxt:= myGui.Add("Text", "x" 3*margin " yp+32 vctrlScreenModeWindowSizeTxt", gTexts.ScreenModeWindowSizeTxt)

	ctrlWindowWidth:= myGui.Add("Edit", "xp+" GetTextSize(gTexts.ScreenModeWindowSizeTxt)+margin " yp-4 vctrlWindowWidth +right +0x2000 w" edtWidth1)
	ctrlWindowWidth.SetFont("s10", "Courier New")
	
	ctrlScreenModeWindowMultiplyTxt:= myGui.Add("Text", "yp vctrlScreenModeWindowMultiplyTxt", gTexts.ScreenModeWindowMultiplyTxt)
	
	ctrlWindowHeight:= myGui.Add("Edit", "yp vctrlWindowHeight +right +0x2000 w" edtWidth1)
	ctrlWindowHeight.SetFont("s10", "Courier New")
	
	myGui.Add("Text", "x" 2*margin " section +right w" wMax, gTexts.UseFontSmoothingTxt)
	ctrlUseFontSmoothing:= myGui.Add("CheckBox", "ys vctrlUseFontSmoothing")

	myGui.Add("Text", "x" 2*margin " section +right w" wMax, gTexts.allowWallpaperTxt)
	ctrlAllowWallpaper:= myGui.Add("CheckBox", "ys vctrlAllowWallpaper")

	myGui.Add("Text", "x" 2*margin " section +right w" wMax, gTexts.useSmartSizingTxt)
	ctrlUseSmartSizing:= myGui.Add("CheckBox", "ys vctrlUseSmartSizing")

	myGui.Add("Text", "x" 2*margin " section +Right w" wMax, gTexts.localDriveMappingTxt)
	ctrlLocalDriveMapping:= myGui.Add("Edit", "x" wMax+3*margin " yp-4 vctrlLocalDriveMapping w" edtWidth2)
	ctrlLocalDriveMapping.SetFont("s10", "Courier New")

	myGui.Add("Text", "x" 2*margin " section +Right", gTexts.cleanupTxt)
	ctrlCleanup:= myGui.Add("CheckBox", "ys vctrlCleanup")

	myGui.Add("Text", "x" 2*margin " section +Right", gTexts.AcceptSecurityMessagesTxt)
	ctrlAcceptSecurityMessages:= myGui.Add("CheckBox", "ys vctrlAcceptSecurityMessages")

	myGui.Add("Text", "x" 2*margin " section +Right w" wMax, gTexts.sessionBppTxt)
	ctrlSessionBpp16:= myGui.Add("Radio", "ys Group vctrlSessionBpp16", gTexts.sessionBpp16Txt)
	ctrlSessionBpp24:= myGui.Add("Radio", "ys vctrlSessionBpp24", gTexts.sessionBpp24Txt)
	ctrlSessionBpp32:= myGui.Add("Radio", "ys vctrlSessionBpp32", gTexts.sessionBpp32Txt)
	
	myGui.Add("Text", "x" 2*margin "  section +Right w" wMax, gTexts.PromptTimeoutTxt)
	ctrlPromptTimeout:= myGui.Add("Edit", "x" wMax+3*margin " yp-4 w" edtWidth1 " +right +0x2000 vctrlPromptTimeout")
	ctrlPromptTimeout.SetFont("s10", "Courier New")

	myGui.Add("Text", "x" 2*margin "  section +Right w" wMax, gTexts.ConnectTimeoutTxt)
	ctrlConnectTimeout:= myGui.Add("Edit", "x" wMax+3*margin " yp-4 w" edtWidth1 " +Right +0x2000 vctrlConnectTimeout")
	ctrlConnectTimeout.SetFont("s10", "Courier New")

	myGui.Add("Text", "x" 2*margin " section +Right w" wMax, gTexts.LogLevelTxt)
	myGui.Add("DropDownList", "x" wMax+3*margin " yp-4  UpperCase vctrlLogLevel", ["Error","Warning","Info","Debug","Trace"])

	ctrlPropertyFilename:= myGui.Add("GroupBox", "xm ym w" gb1Width " R15 vctrlPropertyFilename", gSettings.displayPropertyFilename)
	ctrlPropertyFilename.SetFont("w700")

	ctrlBtnCancel:= myGui.Add("Button", "section Default vctrlBtnCancel w" btnWidth, gTexts.btnCancelTxt) 
	ctrlBtnCancel.OnEvent("Click", MyGui_Close)
	global ctrlBtnOK:= myGui.Add("Button", "ys vctrlBtnOK w" btnWidth, gTexts.btnOKTxt) 
	ctrlBtnOK.OnEvent("Click", mnuFileOkEvent)

	global loadPropertyFilename, userPropertyFilename, installPropertyFilename
	if (loadPropertyFilename == installPropertyFilename) {
		ctrlBtnOk.text:= gTexts.btnOk2Txt
	}

	return myGui
}

;--------------------------------------------------------------------------------------------------------
GuiSetValues(myGui, settings) {
	switch settings.ScreenMode, false
	{
	case "Window": ctrlScreenMode:= myGui['ctrlScreenModeWindow']
	case "Maximize": ctrlScreenMode:= myGui['ctrlScreenModeMaximize']
	case "Fullscreen": ctrlScreenMode:= myGui['ctrlScreenModeFullscreen']
	}	
	ctrlScreenMode.Value:= 1
	ctrlScreenMode.Focus()
	ScreenModeSizeEnable(settings.ScreenMode, ctrlScreenMode)

	myGui['ctrlWindowWidth'].text:= settings.WindowWidth
	myGui['ctrlWindowHeight'].text:= settings.WindowHeight

	myGui['ctrlUseFontSmoothing'].Value:= settings.UseFontSmoothing
	myGui['ctrlAllowWallpaper'].Value:= settings.AllowWallpaper
	myGui['ctrlUseSmartSizing'].Value:= settings.UseSmartSizing
	myGui['ctrlLocalDriveMapping'].Value:= settings.LocalDriveMapping
	myGui['ctrlCleanup'].Value:= settings.Cleanup
	myGui['ctrlAcceptSecurityMessages'].Value:= settings.AcceptSecurityMessages

	switch settings.SessionBpp
	{
	case 16: myGui['ctrlSessionBpp16'].Value:= 1
	case 24: myGui['ctrlSessionBpp24'].Value:= 1
	case 32: myGui['ctrlSessionBpp32'].Value:= 1
	}

	myGui['ctrlConnectTimeout'].Text:= settings.ConnectTimeout
	myGui['ctrlPromptTimeout'].Text:= settings.PromptTimeout

	myGui['ctrlLogLevel'].Value:= settings.LogLevel

	myGui['ctrlPropertyFilename'].text:= settings.DisplayPropertyFilename
}

;-------------------------
;ScreenModeSizeEnable(A_GuiEvent, GuiCtrlObj, Info, *)
ScreenModeSizeEnable(A_GuiEvent, ctrl, *)
{
	;MsgBox( "_GuiEvent= " A_GuiEvent "`nctrl.name " ctrl.name)
	
	myGui:= ctrl.gui

	;MsgBox("A_GuiEvent = " A_GuiEvent)
	if (A_GuiEvent = "Window") {
		myGui['ctrlScreenModeWindowSizeTxt'].Enabled := true
		myGui['ctrlScreenModeWindowMultiplyTxt'].Enabled := true
		myGui['ctrlWindowWidth'].Enabled := true
		myGui['ctrlWindowHeight'].Enabled := true
	}
	else {
		myGui['ctrlScreenModeWindowSizeTxt'].Enabled := false
		myGui['ctrlScreenModeWindowMultiplyTxt'].Enabled := false
		myGui['ctrlWindowWidth'].Enabled := false
		myGui['ctrlWindowHeight'].Enabled := false
	}
	return
}


;--------------------------------------------------------------------------------------------------------
mnuFileOpenEvent(Item, *) {
	global myGui, loadPropertyFilename, gSettings, ctrlBtnOk, userPropertyFilename, installPropertyFilename
	
	openFilename:= StrReplace(loadPropertyFilename, "/", "\")
	SplitPath(openFilename, , &dir, &ext, &name)
	openFilename := FileSelect("", dir, "Open Property File", "Properties (*.properties)")
	if (openFilename != "") {
		loadPropertyFilename:= openFilename
		gSettings:= ReadProperties(loadPropertyFilename,PROPERTY_TYPE_USER)

		displayPropertyFilename:= StrReplace( openFilename, "PAM-Exchange\PAM-RDP-Connect", "...")
		gSettings.displayPropertyFilename:= displayPropertyFilename

		if (loadPropertyFilename == installPropertyFilename) {
			ctrlBtnOk.text:= gTexts.btnOK2Txt
		} else {
			ctrlBtnOk.text:= gTexts.btnOkTxt
		}
		
		GuiSetValues(MyGui, gSettings)
	}
	return
}

;--------------------------------------------------------------------------------------------------------
mnuFileOkEvent(Item, *) {
	
/*
	global myGui
	values:= myGui.Submit(false)
	
	str:= ""
	For Name, Value in values.OwnProps() {
		str:= str "`n" Name "= " Value
	}
	MsgBox(str)
	return
*/	
	global loadPropertyFilename, installPropertyFilename
	if (loadPropertyFilename = installPropertyFilename) {
		rc:= mnuFileSaveAsEvent(Item)
	}
	else {
		rc:= mnuFileSaveEvent(Item)
	}
	if (rc==0) {
		ExitApp
	}
}

;--------------------------------------------------------------------------------------------------------
mnuFileSaveEvent(Item, *) {
	global loadPropertyFilename, installPropertyFilename
	if (loadPropertyFilename = installPropertyFilename) {
		rc:= mnuFileSaveAsEvent(Item)
	}
	else {
		saveFilename:= loadPropertyFilename
		writeProperties( saveFilename )
		MsgBox(gTexts.msgFileSavedTxt "`n`n" saveFilename, gProgramTitle, 0)
		rc:= 0
	}
	return rc
}

;--------------------------------------------------------------------------------------------------------
mnuFileSaveAsEvent(Item, *) {
	logDebug(A_LineNumber, "mnuFileSaveAsEvent: FileSaveAsEvent")
	global userPropertyFilename, loadPropertyFilename, gProgramTitle
	global myGui, gTexts, gSettings
	
	saveFilename:= userPropertyFilename
	saveFilename:= StrReplace(saveFilename, "/", "\")
	logDebug(A_LineNumber, "mnuFileSaveAsEvent: suggested saveFilename= " saveFilename)
	saveFilename := FileSelect("S24", saveFilename, gProgramTitle " - Select File", "Properties (*.properties)")
	
	if (saveFilename != "") {
		logDebug(A_LineNumber, "mnuFileSaveAsEvent: selected saveFilename= " saveFilename)
		WriteProperties( saveFilename )

		MsgBox(gTexts.msgFileSavedTxt "`n`n" saveFilename, gProgramTitle, 0)
		
		displayPropertyFilename:= StrReplace( saveFilename, "PAM-Exchange\PAM-RDP-Connect", "...")
		gSettings.displayPropertyFilename:= displayPropertyFilename
		myGui['ctrlPropertyFilename'].Text:= displayPropertyFilename
		return 0
	}
	else {
		logDebug(A_LineNumber, "mnuFileSaveAsEvent: user cancel or error")
		return -1
	}
}

;--------------------------------------------------------------------------------------------------------
mnuHelpQuickGuideEvent(Item, *) {
	global gTexts, gProgramTitle,gVersion
	str:= "PAM-RDP-Connect Configuration`n----------------------------------`n`n"
	str:= str gTexts.QuickGuideTxt
	str:= str "`n`nVersion " gVersion
	str:= str "`nCopyright ©2020-2024 Columbus A/S"

    MsgBox(str, gProgramTitle, "IconI")
}

;--------------------------------------------------------------------------------------------------------
mnuHelpAboutEvent(Item, *) {
	global gTexts, gProgramTitle
	str:= "PAM-RDP-Connect Configuration`n----------------------------------`n`n"
	str:= str gTexts.AboutTxt
	str:= str "`n`nVersion " gVersion
	str:= str "`nCopyright ©2020-2024 Columbus A/S"

    MsgBox(str, gProgramTitle, "IconI")
}

;--------------------------------------------------------------------------------------------------------
MyGui_Close(*) { 
    ExitApp
}

;--------------------------------------------------------------------------------------------------------
MyGui_Size(thisGui,MinMax,Width,Height) {
	if (MinMax = -1) {
		;thisGui.Hide()
		;WinHide(gProgramTitle)
	}
	else {
		static Reposition:= true
		if (reposition) {
		
			global btnWidthBorder
			btn:= thisGui["ctrlBtnOK"]
			btn.GetPos(&btnX, &btnY, &btnWidth, &btnHeight)
			btnWidth:= btnWidth+2*btnWidthBorder
		
			thisGui.GetPos(&X, &Y, &Width, &Height)
			btn.Move(Width-btnWidth-2*thisGui.MarginX )
		
/*		
			global margin
			global ctrlBtnOK
			global btnWidth
			global btnWidthBorder
			thisGui.GetPos(&X, &Y, &Width, &Height)
			;MsgBox("Width= " Width "`nHeight= " Height)
			ctrlBtnOK.Move(Width-btnWidth-2*margin - 2*btnWidthBorder)
*/
			reposition:= false
		}
	}
}

;--------------------------------------------------------------------------------------------------------
MyGui_Show(A_ThisMenuItem, A_ThisMenuItemPos, MyMenu)
{
	global gProgramTitle
	
	WinShow(gProgramTitle)
	WinActivate(gProgramTitle)
	WinRestore(gProgramTitle)
	return
}

;--------------------------------------------------------------------------------------------------------
MaxLength(params*) {
	wMax:= 0
    for i,s in params {
		wTmp:= GetTextSize( s )
		wMax:= (wMax < wTmp) ? wTmp : wMax
	}
    return wMax
}

;--------------------------------------------------------------------------------------------------------
GetTextSize(pStr, pSize:=8, pWeight:= 400, pFont:="", pHeight:=false) {
   oGui9 := Gui()
   oGui9.SetFont("s" pSize " w" pWeight, pFont)
   strCtrl:= oGui9.Add("Text", "R1", pStr)
   strCtrl.GetPos(&TX, &TY, &TW, &TH)
   oGui9.Destroy()
   Return pHeight ? TW "," TH : TW
}


;--------------------------------------------------------------------------------------------------------
SystemEvent(wParam, lParam, msg, hwnd) {
/*
	; 0x16 EVENT_SYSTEM_MINIMIZESTART
	if (wParam == 0x16) {
		class:= WinGetClass("ahk_id " hwnd)
		if (class == "TscShellContainerClass") {
			WinHide("ahk_id " hwnd) 
			;Send "!{Escape}"
			return false
		}
	}
*/
}

;--------------------------------------------------------------------------------------------------------
GetTexts() {
	txt:= Object()

	txt.mnuFileTxt:= "&File"
	txt.mnuFileOpenTxt:= "&Open"
	txt.mnuFileSaveTxt:= "&Save"
	txt.mnuFileSaveAsTxt:= "Save &as ..."
	txt.mnuFileExitTxt:= "E&xit"

	txt.mnuHelpTxt:= "&Help"
	txt.mnuHelpQuickGuideTxt:= "Quick &guide"
	txt.mnuHelpAboutTxt:= "&About"

	txt.LogLevelTxt:= "Log level"
	txt.LogLevelErrorTxt:= "ERROR"
	txt.LogLevelWarningTxt:= "WARNING"
	txt.LogLevelInfoTxt:= "INFO"
	txt.LogLevelDebugTxt:= "DEBUG"
	txt.LogLevelTraceTxt:= "TRACE"

	txt.userPropertyFilenameTxt:= "Current property file"
	txt.ConnectTimeoutTxt:= "Connection Timeout"
	txt.PromptTimeoutTxt:= "Prompt Timeout"

	txt.ScreenModeTxt:= "Screen Mode"
	txt.ScreenModeWindowTxt:= "Window"
	txt.ScreenModeMaximizeTxt:= "Maximize"
	txt.ScreenModeFullscreenTxt:= "Fullscreen"
	txt.ScreenModeWindowMultiplyTxt:= "×"
	txt.SceenModeWindowWidthTxt:= "Width"
	txt.SceenModeWindowHeightTxt:= "Height"
	txt.ScreenModeWindowSizeTxt:= txt.SceenModeWindowWidthTxt " " txt.ScreenModeWindowMultiplyTxt " " txt.SceenModeWindowHeightTxt

	txt.UseFontSmoothingTxt:= "Use font smoothing"
	txt.allowWallpaperTxt:= "Show remote wallpaper"
	txt.localDriveMappingTxt:= "Local drive mapping"
	txt.AcceptSecurityMessagesTxt:= "Accept Security Prompts"
	txt.useSmartSizingTxt:= "Use smart window sizing"
	txt.sessionBppTxt:= "Session Colour depth"
	txt.sessionBpp16Txt:= "16"
	txt.sessionBpp24Txt:= "24"
	txt.sessionBpp32Txt:= "32"
	txt.cleanupTxt:= "Delete RDP file after use"

	txt.btnOKTxt:= "&Save"
	txt.btnOK2Txt:= "&Save As"
	txt.btnCancelTxt:= "&Cancel"

	txt.msgFileSavedTxt:= "Properties saved to file"

	txt.AboutTxt:= "PAM-RDP-Connect Configuration is used to update the user's properties file for PAM-RDP-Connect."
	txt.QuickGuideTxt:= "The user's property settings in pam-rdp.user.properties files can be updated using the configuration GUI.\nThe program is used to update the settings a user can or should modify. System settings must be updateded using a standard text editor. System settings includes the addresses of PAM servers.\n\nThe default user's configuraion is loaded from the users %AppData% directory. If a property file is not found, the property file from the installation location is used. When saving the file, it is recommended to use the default location suggested. This is where the PAM-RDP-Connect program will read the properties from."
	
	txt.AboutTxt:= StrReplace(txt.AboutTxt,"\n","`n")
	txt.QuickGuideTxt:= StrReplace(txt.QuickGuideTxt,"\n","`n")

	return txt
}

;--------------------------------------------------------------------------------------------------------
; read pam-rdp.properties
;
ReadProperties( filename, pType:= 0 )
{
	global PROPERTY_TYPE_USER, PROPERTY_TYPE_SYSTEM
	global LOG_ERROR, LOG_WARNING, LOG_INFO, LOG_DEBUG, LOG_TRACE
	global gLogLevel
	
	settings:= object()
	
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
		x := IniRead(filename, "main", "cleanup", defCleanup)
		logDebug(A_LineNumber, "ReadProperties: cleanup = '" x "'")
		settings.Cleanup:= !InStr(x, "false")
					
		;----------------------
		; ConnectTimeout
		;----------------------
		x:= IniRead(filename, "main", "ConnectTimeout", defConnectTimeout)
		logDebug(A_LineNumber, "ReadProperties: ConnectTimeout= '" x "' (file/default)")
		if (!IsInteger(x) or IsSpace(x) or x <= 0 or x >= 900) {
			x:= defConnectTimeout
		}
		settings.ConnectTimeout:= x
		logInfo(A_LineNumber, "ReadProperties: ConnectTimeout= '" settings.ConnectTimeout "' (final)")

		;----------------------
		; PromptTimeout
		;----------------------
		x:= IniRead(filename, "main", "promptTimeout", defPromptTimeout)
		logDebug(A_LineNumber, "ReadProperties: PromptTimeout= '" x "' (file/default)")
		if (!IsInteger(x) or IsSpace(x) or x <= 0 or x >= 60) {
			x:= defPromptTimeout
		}
		settings.PromptTimeout:= x
		logInfo(A_LineNumber, "ReadProperties: ConnectTimeout= '" settings.PromptTimeout "' (final)")


		;----------------------
		; ScreenMode / Width, Height
		;----------------------
		x:= IniRead(filename, "main", "screenMode", defScreenMode)
		logDebug(A_LineNumber, "ReadProperties: gScreenMode= '" x "' (file/default)")
		if (!RegExMatch(x, "i)(Window|Fullscreen|Maximize)")) {
			x:= "Fullscreen"
		}
		settings.ScreenMode:= x
		logInfo(A_LineNumber, "ReadProperties: gScreenMode= '" settings.ScreenMode "' (final)")
		
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
		settings.WindowWidth:= locWidth
		settings.WindowHeight:= locHeight
		logInfo(A_LineNumber, "ReadProperties: ScreenMode= " settings.ScreenMode ", WindowWidth= " settings.WindowWidth ", WindowHeight=" settings.WindowHeight " (final)")

		;----------------------
		; UseFontSmoothing
		;----------------------
		x := IniRead(filename, "main", "UseFontSmoothing", defUseFontSmoothing)
		logDebug(A_LineNumber, "ReadProperties: UseFontSmoothing= '" x "' (file/default)")
		settings.UseFontSmoothing:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: UseFontSmoothing= '" settings.UseFontSmoothing "' (final)")
		
		
		;----------------------
		; AllowWallpaper
		;----------------------
		x := IniRead(filename, "main", "wallpaper", defAllowWallpaper)
		logDebug(A_LineNumber, "ReadProperties: wallpaper= '" x "' (file/default)")
		settings.AllowWallpaper:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: wallpaper= '" settings.AllowWallpaper "' (final)")

		;----------------------
		; SessionBpp
		;----------------------
		x := IniRead(filename, "main", "sessionBpp", defSessionBpp)
		logDebug(A_LineNumber, "ReadProperties: sessionBpp= '" x "' (file/default)")
		if (x != 16 and x != 24 and x != 32)
			x:= defSessionBpp
		settings.SessionBpp:= x
		logInfo(A_LineNumber, "ReadProperties: sessionBpp= '" settings.SessionBpp "' (final)")
		
		;----------------------
		; LocalDriveMapping
		;----------------------
		x:= IniRead(filename, "main", "localDriveMapping", defLocalDriveMapping)
		logDebug(A_LineNumber, "ReadProperties: localDriveMapping= '" x "' (file/default/final)")
		settings.LocalDriveMapping:= x

		;----------------------
		; AcceptSecurityMessages
		;----------------------
		x := IniRead(filename, "main", "acceptSecurityMessages", defAcceptSecurityMessages)
		logDebug(A_LineNumber, "ReadProperties: acceptSecurityMessages= '" x "' (file/default)")
		settings.AcceptSecurityMessages:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: acceptSecurityMessages= '" settings.AcceptSecurityMessages "' (final)")
		
		;----------------------
		; UseSmartSizing
		;----------------------
		x := IniRead(filename, "main", "useSmartSizing", defUseSmartSizing)
		logDebug(A_LineNumber, "ReadProperties: gUseSmartSizing= '" x "' (file/default)")
		settings.UseSmartSizing:= InStr(x, "true")
		logInfo(A_LineNumber, "ReadProperties: gUseSmartSizing= '" settings.UseSmartSizing "' (final)")
	}
	
	; Not PROPERTY_TYPE_USER
	else {
		logError(A_LineNumber, "ReadProperties: Unsupported property type")
	}
	
	return settings
}	

;--------------------------------------------------------------------------------------------------------
; Write pam-rdp.properties
;
WriteProperties( outputFilename )
{
	logDebug(A_LineNumber, "writeProperties: " outputFilename)
	
	global LOG_ERROR, LOG_WARNING, LOG_INFO, LOG_DEBUG, LOG_TRACE
	global myGui
	
	settings:= myGui.Submit(false)
	
	if FileExist( outputFilename ) {
		logDebug(A_LineNumber, "writeProperties: Delete file '" outputFilename "'")
		FileDelete(outputFilename)
	}

	wrtAcceptSecurityMessages:= "AcceptSecurityMessages= " ((settings.ctrlAcceptSecurityMessages) ? "true" : "false")
	wrtUseFontSmoothing:= "UseFontSmoothing= " ((settings.ctrlUseFontSmoothing) ? "true" : "false")
	wrtAllowWallpaper:= "Wallpaper= " ((settings.ctrlAllowWallpaper) ? "true" : "false")
	wrtCleanup:= "Cleanup= " ((settings.ctrlCleanup) ? "true" : "false")
	wrtConnectionTimeout:= "ConnectionTimeout= " settings.ctrlConnectTimeout
	wrtWidth:= ((settings.ctrlScreenModeWindow) ? "" : ";") "WindowWidth= " settings.ctrlWindowWidth
	wrtHeight:= ((settings.ctrlScreenModeWindow) ? "" : ";") "WindowHeight= " settings.ctrlWindowHeight
	wrtLocalDriveMapping:= "LocalDriveMapping= " settings.ctrlLocalDriveMapping
	wrtPromptTimeout:= "PromptTimeout= " settings.ctrlPromptTimeout
	wrtScreenMode:= "ScreenMode= " ((settings.ctrlScreenModeWindow) ? "Window" : (settings.ctrlScreenModeMaximize) ? "Maximize" : "Fullscreen")
	wrtSessionBpp:= "SessionBpp= " ((settings.ctrlSessionBpp16) ? "16" : (settings.ctrlSessionBpp24) ? "24" : "32")
	wrtUseSmartSizing:= "UseSmartSizing= " ((settings.ctrlUseSmartSizing) ? "true" : "false")
	wrtLogLevel:= "LogLevel= " settings.ctrlLogLevel

	content:= "[main]"
	content:= content "`n; Control the window mode of the RDP session"
	content:= content "`n; valid values are: window|maximize|fullscreen"
	content:= content "`n;   window     - use the windowWidth/windowHeight parameters."
	content:= content "`n;   maximize   - make the window as large as possible without going "
	content:= content "`n;                into fullscreen mode."
	content:= content "`n;   fullscreen - use MSTSC fullscreen mode. This is default."
	content:= content "`n" wrtScreenMode

	content:= content "`n"
	content:= content "`n; windowWidth and windowHeight can be used to overwrite the "
	content:= content "`n; parameters used by the PAM server. The settings are only "
	content:= content "`n; used when screenMode is window."
	content:= content "`n" wrtWidth
	content:= content "`n" wrtHeight

	content:= content "`n"
	content:= content "`n; allowFontSmoothing can be used if Password Safe is configured to allow"
	content:= content "`n; font smoothing. The downloaded RDP file does not set this flag. "
	content:= content "`n; If the option is defined and set to 'true', the RDP file will be updated"
	content:= content "`n; to allow font smoothing. Keep in mind that the Password Safe server"
	content:= content "`n; must permit font smoothing for this to work."
	content:= content "`n; Update default.rdp (Symantec)."
	content:= content "`n" wrtUseFontSmoothing

	content:= content "`n"
	content:= content "`n; wallpaper can be to transmit the wallpaper from the remote server."
	content:= content "`n; If the option is defined and set to `"true`", the RDP file will be updated"
	content:= content "`n; to allow wallpaper."
	content:= content "`n; Symantec: Update default.rdp"
	content:= content "`n" wrtAllowWallpaper

	content:= content "`n"
	content:= content "`n; useSmartSizing flag is controlling if the RDP session is scaling"
	content:= content "`n; when the window is resized."
	content:= content "`n; Symantec: Update default.rdp"
	content:= content "`n" wrtUseSmartSizing

	content:= content "`n"
	content:= content "`n; localDriveMapping can be used to set the local drives to be mapped in the "
	content:= content "`n; mstsc session. The syntax is like the regular RDP file used by mstsc."
	content:= content "`n; If the setting is not defined or empty, no drive mapping is used."
	content:= content "`n; Symantec: Update default.rdp"
	content:= content "`n"
	content:= content "`n;localDriveMapping= C:\;K:\;DynamicDrives"
	content:= content "`n;localDriveMapping= C:\;K:\"
	content:= content "`n;localDriveMapping= *"
	content:= content "`n;localDriveMapping= "
	content:= content "`n" wrtLocalDriveMapping

	content:= content "`n"
	content:= content "`n; Cleanup will control if downloaded RDP files are removed after use."
	content:= content "`n" wrtCleanup

	content:= content "`n"
	content:= content "`n; acceptSecurityMessages can be automatically accepted. "
	content:= content "`n; Messages will be shown when different from `"true`"."
	content:= content "`n; If omitted, no changes in RDP file is done."
	content:= content "`n; Symantec: Update default.rdp"
	content:= content "`n" wrtAcceptSecurityMessages

	content:= content "`n"
	content:= content "`n; sessionBpp can be used to change/force the session bpp settings."
	content:= content "`n; If the real-end point does not support the bpp, this setting can not "
	content:= content "`n; be used to increase a `"16-bit`" RDP session to the end-point to a higher"
	content:= content "`n; value. It can be used to decrease the bpp from the real end-point."
	content:= content "`n; accepted values are 16, 24 or 32"
	content:= content "`n; Symantec: Update default.rdp"
	content:= content "`n" wrtSessionBpp

	content:= content "`n"
	content:= content "`n; promptTimeout for GUI pop-ups. If a pop-up window is shown, the user "
	content:= content "`n; can press <OK> to close the pop-up message. "
	content:= content "`n; If not acknowleged by the user, the pop-up will close after <timeout>"
	content:= content "`n; seconds."
	content:= content "`n" wrtPromptTimeout

	content:= content "`n"
	content:= content "`n; connectionTimeout is the maximum time for opening a session through"
	content:= content "`n; PAM to the end-point. Depending on the end-point location and connection"
	content:= content "`n; time to the end-point, the value may need to be increased."
	content:= content "`n; If a connection is not established in <connectioinTimeout> seconds,"
	content:= content "`n; the start attempt is stopped."
	content:= content "`n" wrtConnectionTimeout

	content:= content "`n"
	content:= content "`n; LogLevel for pam-rdp.exe. "
	content:= content "`n; Valid values are ERROR, WARNING, INFO, DEBUG, TRACE"
	content:= content "`n; Default value is DEBUG"
	content:= content "`n" wrtLogLevel 
	content:= content "`n"

	FileAppend(content, outputFilename)

	return 1
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

