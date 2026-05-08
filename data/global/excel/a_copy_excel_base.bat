@echo off
setlocal enabledelayedexpansion

:: --- CONFIGURATION SECTION ---
:: Path to the excel directory (relative to this script or absolute)
set "SOURCE_DIR=%~dp0"
:: Remove trailing backslash if present
if "%SOURCE_DIR:~-1%"=="\" set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"
set "DEST_DIR=%SOURCE_DIR%\base"

:: Files to EXCLUDE from the copy process (space separated)
set "EXCLUDE_FILES=treasureclassex.txt a_copy_excel_base.bat"
:: -----------------------------

echo Copying files from %SOURCE_DIR% to %DEST_DIR%...
echo Excluding: %EXCLUDE_FILES%

:: Loop through files in the source directory
for %%F in ("%SOURCE_DIR%\*.txt") do (
    set "filename=%%~nxF"
    set "skip=0"
    
    :: Check if current file is in the exclusion list
    for %%E in (%EXCLUDE_FILES%) do (
        if /i "!filename!"=="%%E" set "skip=1"
    )
    
    if "!skip!"=="1" (
        echo Skipping "!filename!" ^(excluded^)
    ) else (
        set "dest_file=%DEST_DIR%\!filename!"
        set "should_copy=1"
        
        if exist "!dest_file!" (
            fc /b "%%F" "!dest_file!" >nul
            if not errorlevel 1 set "should_copy=0"
        )
        
        if "!should_copy!"=="1" (
            echo Copying "!filename!"...
            if not exist "%DEST_DIR%\" mkdir "%DEST_DIR%"
            copy /y "%%F" "%DEST_DIR%\" >nul
        ) else (
            echo Skipping "!filename!" ^(no changes detected^)
        )
    )
)

echo Done.
