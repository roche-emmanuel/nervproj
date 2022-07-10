@echo off

SETLOCAL ENABLEDELAYEDEXPANSION

@REM Retrieve the current folder:
@REM cli script is located directly in the root, so we don't need the '..' in path:
@REM cd /D %~dp0..
cd /D %~dp0
FOR /F %%i IN (".") DO set ${PROJ_NAME}_ROOT_DIR=%%~fi

set ${PROJ_NAME}_DIR=%${PROJ_NAME}_ROOT_DIR%
@REM echo Using NervProj root folder: %${PROJ_NAME}_DIR%

@REM Extract the python env if needed:
set py_vers=${PY_VERSION}
set TOOLS_DIR=%${PROJ_NAME}_DIR%\\tools\\windows\\
set UNZIP=%TOOLS_DIR%\\7zip-${ZIP_VERSION}\\7za.exe
set PYTHON=%TOOLS_DIR%\\python-%py_vers%\\python.exe

@REM Check if python is extracted already:
if not exist "%PYTHON%" (
    echo Extracting python tool...
    %UNZIP% x -o"%TOOLS_DIR%" "%${PROJ_NAME}_DIR%\\tools\\packages\\python-%py_vers%-windows.7z" > nul

    @REM Upgrade pip:
    %PYTHON% -m pip install --upgrade pip --no-warn-script-location

    @REM Install requirements:
    %PYTHON% -m pip install -r %${PROJ_NAME}_DIR%\\tools\\requirements.txt --no-warn-script-location
)

@REM check if the first argument is "--install-py-reqs"
IF /i "%~1" == "--install-py-reqs" goto install_reqs
IF /i "%~1" == "--pre-commit" goto pre_commit
IF /i "%~1" == "python" goto run_python
IF /i "%~1" == "pip" goto run_pip

%PYTHON% %${PROJ_NAME}_DIR%\cli.py %*
goto common_exit

:install_reqs
%PYTHON% -m pip install -r %${PROJ_NAME}_DIR%\\tools\\requirements.txt --no-warn-script-location
goto common_exit

:pre_commit
echo black outputs: >%${PROJ_NAME}_DIR%\pre_commit.log
%PYTHON% -m black --line-length 120 %${PROJ_NAME}_DIR%\%~2 >>%${PROJ_NAME}_DIR%\pre_commit.log 2>&1
echo: >>%${PROJ_NAME}_DIR%\pre_commit.log
echo isort outputs: >>%${PROJ_NAME}_DIR%\pre_commit.log
%PYTHON% -m isort --profile black %${PROJ_NAME}_DIR%\%~2 >>%${PROJ_NAME}_DIR%\pre_commit.log 2>&1
echo: >>%${PROJ_NAME}_DIR%\pre_commit.log
echo Flake8 outputs: >>%${PROJ_NAME}_DIR%\pre_commit.log
%PYTHON% -m flake8 --max-line-length=120 --ignore="E203,W503" %${PROJ_NAME}_DIR%\%~2 >>%${PROJ_NAME}_DIR%\pre_commit.log 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo FAILED
) else (
    echo OK
)
goto common_exit

@REM cannot rely on %* when we use shift below:

:run_python
shift
%PYTHON% %1 %2 %3 %4 %5 %6 %7 %8 %9
goto common_exit

:run_pip
shift
%PYTHON% -m pip %1 %2 %3 %4 %5 %6 %7 %8 %9
goto common_exit

:common_exit
