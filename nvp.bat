@echo off

SETLOCAL ENABLEDELAYEDEXPANSION

@REM Store the source folder:
set cdir=%cd%

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

@REM check if the first argument is "--install-py-reqs"
IF /i "%~1" == "--install-py-reqs" goto install_reqs
IF /i "%~1" == "--pre-commit" goto pre_commit
IF /i "%~1" == "python" goto run_python
IF /i "%~1" == "pip" goto run_pip
IF /i "%~1" == "" goto ready

@REM Get back into the source folder:
cd /D %cdir%

@REM call the python app with the provided arguments:
%PYTHON% %NVP_DIR%\cli.py %*
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
goto common_exit

:install_reqs
%PYTHON% -m pip install -r %NVP_DIR%\tools\requirements.txt
goto common_exit

:pre_commit
%PYTHON% -m flake8 --max-line-length=120 %NVP_DIR%\nvp
%PYTHON% -m black --line-length 120 %NVP_DIR%\nvp
%PYTHON% -m isort --profile black %NVP_DIR%\nvp
goto common_exit

@REM cannot rely on %* when we use shift below:

:ready
echo NVP env ready. Use "nvp list-scripts" to get available scripts.
goto common_exit

:run_python
shift
%PYTHON% %1 %2 %3 %4 %5 %6 %7 %8 %9
goto common_exit

:run_pip
shift
%PYTHON% -m pip %1 %2 %3 %4 %5 %6 %7 %8 %9
goto common_exit

:common_exit
