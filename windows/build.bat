@echo off
rem ===== Сборка установщика NetPulse для Windows 10/11 =====
rem Нужно: Python 3.10+ (python.org) и Inno Setup 6 (jrsoftware.org/isinfo.php)
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [1/3] Установка зависимостей...
python -m pip install --upgrade pip >nul
python -m pip install -r ..\requirements.txt pyinstaller || goto :error

echo [2/3] Сборка NetPulse.exe (PyInstaller)...
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build netpulse.spec || goto :error

echo [3/3] Сборка установщика (Inno Setup)...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup 6 не найден. Установите: winget install JRSoftware.InnoSetup
    echo Портативная версия уже готова: windows\dist\NetPulse\NetPulse.exe
    goto :error
)
"%ISCC%" installer.iss || goto :error

echo.
echo Готово! Установщик: windows\Output\
dir /b Output\*.exe
pause
exit /b 0

:error
echo.
echo Сборка прервана с ошибкой.
pause
exit /b 1
