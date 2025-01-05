@echo off
set AHK_HOME=C:\opt\AutoHotKey-v2
set PY_HOME=C:\opt\Python313
set INNO_HOME=C:\opt\InnoSetup-6.3.3

set DIST=.\dist
if exist %DIST% rmdir /S /Q %DIST%
mkdir %DIST%

rem
rem Build pam-rdp from ahk source
rem
set SRC=.\pam-rdp\src
set CFG=.\pam-rdp\config
set NAME=pam-rdp
"%AHK_HOME%\Compiler\ahk2exe.exe" /in "%SRC%\%NAME%.ahk" /out "%DIST%\%NAME%.exe" /icon "%SRC%\%NAME%.ico" /base "%AHK_HOME%\AutoHotkey64.exe" /compress 2

rem
rem Copy sample properties file
rem 
rem copy /Y %CFG%\*.* %DIST%
xcopy /S /I /Y %CFG%\*.* %DIST%

rem
rem Build pam-rdp-config from ahk source
rem
set SRC=.\pam-rdp-config\src
set NAME=pam-rdp-config
"%AHK_HOME%\Compiler\ahk2exe.exe" /in "%SRC%\%NAME%.ahk" /out "%DIST%\%NAME%" /icon "%SRC%\%NAME%.ico" /base "%AHK_HOME%\AutoHotkey64.exe" /compress 2

rem
rem Build pam-rdp-service from python source
rem
set WORK=.\tmp
if exist %WORK% rmdir /S /Q %WORK%
mkdir %WORK%

set PYOPTS=--noconfirm --onefile --hidden-import=win32timezone --hidden-import=psutil --distpath %DIST% --workpath %WORK%
set SRC=.\pam-rdp-service\src
set CFG=.\pam-rdp-service\config
set NAME=pam-rdp-service

pyinstaller %PYOPTS% %SRC%\%NAME%.py

rmdir /S /Q %WORK%
rm /Y %NAME%.spec
copy /Y %CFG%\%NAME%.properties %DIST%

rem
rem Copy documentation and other files 
rem 
xcopy /S /I /Y Docs %DIST%\Docs

copy /Y version %DIST%
copy /Y LICENSE %DIST%

rem
rem InnoSetup
rem
set INNO_SCRIPT=.\pam-rdp-setup\PAM-Connect.iss
%INNO_HOME%\ISCC.exe /O%DIST% %INNO_SCRIPT%

rem 
rem Package to a zip file
rem
set NAME=PAM-Connect
if exist %NAME%.zip rm /Y %NAME%.zip
cd %DIST%
zip -r ..\%NAME%.zip *.*
cd ..

