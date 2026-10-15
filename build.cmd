@echo off
set PY_HOME=C:\opt\Python313
set GCC_HOME=C:\opt\w64devkit
set INNO_HOME=C:\opt\InnoSetup-6.3.3

if defined PY_HOME set PATH=%PY_HOME%;%PY_HOME%\Scripts;%PATH%

set DIST=.\dist
if exist %DIST% rmdir /S /Q %DIST%
mkdir %DIST%

rem
rem Build pam-rdp from python source
rem
set WORK=.\tmp
if exist %WORK% rmdir /S /Q %WORK%
mkdir %WORK%

set PYOPTS=--noconfirm --onefile --distpath %DIST% --workpath %WORK%
set SRC=.\pam-rdp\src
set CFG=.\pam-rdp\config
set NAME=pam-rdp

pyinstaller %PYOPTS% --icon="%SRC%\%NAME%.ico" --version-file="%SRC%\%NAME%-version.txt" %SRC%\%NAME%.py
if %ERRORLEVEL% NEQ 0 (
    echo Failed to compile %NAME%.py
    exit /b %ERRORLEVEL%
)

rmdir /S /Q %WORK%
if exist %NAME%.spec erase /Q /F %NAME%.spec

rem
rem Copy sample properties file
rem 
xcopy /S /I /Y %CFG%\*.* %DIST%

rem
rem Build pam-rdp-config from python source
rem
set WORK=.\tmp
if exist %WORK% rmdir /S /Q %WORK%
mkdir %WORK%

set PYOPTS=--noconfirm --onefile --noconsole --distpath %DIST% --workpath %WORK%
set SRC=.\pam-rdp-config\src
set NAME=pam-rdp-config

pyinstaller %PYOPTS% --icon="%SRC%\%NAME%.ico" --version-file="%SRC%\%NAME%-version.txt" %SRC%\%NAME%.py
if %ERRORLEVEL% NEQ 0 (
    echo Failed to compile %NAME%.py
    exit /b %ERRORLEVEL%
)

rmdir /S /Q %WORK%
if exist %NAME%.spec erase /Q /F %NAME%.spec

rem
rem Build pam-rdp-service from C source
rem
set WORK=.\tmp
if exist %WORK% rmdir /S /Q %WORK%
mkdir %WORK%

set SRC=.\pam-rdp-service\src
set CFG=.\pam-rdp-service\config
set NAME=pam-rdp-service

if defined GCC_HOME set PATH=%GCC_HOME%\bin;%PATH%

windres "%SRC%\%NAME%.rc" -O coff -o "%WORK%\%NAME%.res"
gcc -O2 -Wall -o "%DIST%\%NAME%.exe" "%SRC%\%NAME%.c" "%WORK%\%NAME%.res" -ladvapi32 -lpsapi
if %ERRORLEVEL% NEQ 0 (
    echo Failed to compile %NAME%.c
    exit /b %ERRORLEVEL%
)

rmdir /S /Q %WORK%
copy /Y "%CFG%\%NAME%.properties" "%DIST%"

rem
rem Copy documentation and other files 
rem 
xcopy /S /I /Y Docs %DIST%\Docs

copy /Y version %DIST%
copy /Y LICENSE %DIST%

rem
rem InnoSetup
rem
set INNO_SCRIPT=.\pam-rdp-setup\pam-rdp-setup.iss
%INNO_HOME%\ISCC.exe /O%DIST% %INNO_SCRIPT%

rem 
rem Package to a zip file
rem
set NAME=PAM-RDP-Connect
if exist %NAME%.zip erase /Q /F %NAME%.zip
cd %DIST%
zip -r ..\%NAME%.zip *.*
cd ..
