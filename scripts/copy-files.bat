@echo off
setlocal

set "SOURCE=C:\dev\d2r\d2r-reimagined-mod\data"
set "DEST=C:\Program Files (x86)\Diablo II Resurrected\mods\Reimagined\Reimagined.mpq\data"

echo Copying changed files to "%DEST%"
echo.

rem /MIR mirrors the tree, so files deleted from the repo are still removed from
rem the install without wiping and recopying everything first. Leaving off /IS
rem and /IT means robocopy skips identical files, and without /V those skips are
rem not printed: the output is only new, updated and removed files.
rem
rem The launcher's <name>_launcher_clean copies are excluded from the mirror
rem and removed separately below, so they do not flood the output as "extra".
robocopy "%SOURCE%" "%DEST%" /MIR /NP /NDL /NJH /NJS /R:2 /W:2 ^
    /XD "*_launcher_clean" /XF "*_launcher_clean.json"

echo.
if errorlevel 8 goto :failed
if errorlevel 1 (echo Done.) else (echo No changes: the install already matches the repo.)

rem The launcher snapshots <name>_launcher_clean once, then on every launch
rem copies that snapshot back over excel/, strings/, missiles.json etc. before
rem applying its tweaks. A stale snapshot silently reverts everything deployed
rem here, so remove them: the launcher re-snapshots from the fresh data on the
rem next launch.
set "CLEANED=0"
for /d /r "%DEST%" %%D in (*_launcher_clean) do (
    rd /s /q "%%D"
    set "CLEANED=1"
)
for /r "%DEST%" %%F in (*_launcher_clean.json) do (
    del /q "%%F"
    set "CLEANED=1"
)
if "%CLEANED%"=="1" echo Removed the launcher's clean-copy snapshots; it will rebuild them from this data on the next launch.
exit /b 0

:failed
echo Copy failed. Close D2R and the launcher, then run this again.
exit /b 1
