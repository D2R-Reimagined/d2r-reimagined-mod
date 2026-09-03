@echo off
setlocal
set "PROFILE=%~1"
if not defined PROFILE set "PROFILE=standard"
if /I "%PROFILE%"=="standard" goto build
if /I "%PROFILE%"=="d2rl" goto build
echo Usage: copy-files.bat standard^|d2rl
exit /b 1
:build
node "%~dp0build.mjs" --profile "%PROFILE%"
if errorlevel 1 exit /b 1
echo Build ready: %~dp0..\build\%PROFILE%\mods\Reimagined
echo Copy the generated mod folder to your installation. No installed files were changed.
