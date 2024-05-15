@echo off
echo Deleting old files
rm -R "C:\Program Files (x86)\Diablo II Resurrected\mods\Merged\Merged.mpq\data"
echo Copying files
robocopy "C:\dev\d2r\d2r-reimagined\data" "C:\Program Files (x86)\Diablo II Resurrected\mods\Merged\Merged.mpq\data" /MIR /E /IS /IT