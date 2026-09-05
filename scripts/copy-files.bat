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
rem /XD and /XF keep the launcher's own files out of the mirror. It writes
rem pristine <name>_launcher_clean copies next to the files it tweaks and uses
rem them to revert; purging them as "extra" would make its next snapshot capture
rem already-tweaked data as the clean baseline.
robocopy "%SOURCE%" "%DEST%" /MIR /NP /NDL /NJH /NJS /R:2 /W:2 ^
    /XD "*_launcher_clean" "mod-tweaks" /XF "*_launcher_clean.json"

echo.
if errorlevel 8 goto :failed
if errorlevel 1 goto :copied
echo No changes: the install already matches the repo.
goto :eof

:copied
echo Done.
goto :eof

:failed
echo Copy failed. Close D2R and the launcher, then run this again.
exit /b 1
