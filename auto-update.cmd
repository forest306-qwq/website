@echo off
cd /d "%~dp0"
echo Updating homepage, column lists and counts from article files...
echo Keep this window open while writing articles. Ctrl+C stops watching.
python -u "%~dp0tools\update_content.py" --watch
if errorlevel 1 echo Update failed. Check the error above. Python 3 is required.
pause
