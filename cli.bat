@echo off

SETLOCAL ENABLEDELAYEDEXPANSION

@REM Retrieve the current folder:
@REM cli script is located directly in the root, so we don't need the '..' in path:
@REM cd /D %~dp0..
cd /D %~dp0
FOR /F %%i IN (".") DO set NVP_ROOT_DIR=%%~fi

set NVP_DIR=%NVP_ROOT_DIR%
@REM echo Using NervProj root folder: %NVP_DIR%

@REM Extract the python env if needed:
set py_vers=3.10.1
set TOOLS_DIR=%NVP_DIR%\tools\windows\
set UNZIP=%TOOLS_DIR%\7zip-9.20\7za.exe
set PYTHON=%TOOLS_DIR%\python-%py_vers%\python.exe

@REM Check if python is extracted already:
if not exist "%PYTHON%" (
    echo Extracting python tool...
    %UNZIP% x -o"%TOOLS_DIR%" "%NVP_DIR%\tools\packages\python-%py_vers%-windows.7z" > nul

    @REM Upgrade pip:
    %PYTHON% -m pip install --upgrade pip

    @REM Install requirements:
    %PYTHON% -m pip install -r %NVP_DIR%\tools\requirements.txt
)

@REM call the python app with the provided arguments:
%PYTHON% %NVP_DIR%\cli.py %*
