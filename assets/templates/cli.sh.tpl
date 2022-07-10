#!/bin/bash

# cf. https://stackoverflow.com/questions/59895/how-can-i-get-the-source-directory-of-a-bash-script-from-within-the-script-itsel
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

_${PROJ_NAME}_run_cli_cygwin() {
    # On windows we should simply rely on the cli.bat script below:
    ROOT_DIR="$(cygpath -w $ROOT_DIR)"

    cmd /C "$ROOT_DIR\cli.bat" "$@"
}

_${PROJ_NAME}_run_cli_mingw() {
    # On windows we should simply rely on the cli.bat script below:
    ROOT_DIR="$(cygpath -w $ROOT_DIR)"

    "$ROOT_DIR\cli.bat" "$@"
}

_${PROJ_NAME}_run_cli_linux() {
    local python_version="${PY_VERSION}"

    # On linux we should call the python cli directly:
    # Get the project root folder:
    local root_dir=$(readlink -f $ROOT_DIR/)
    # echo "Project root dir is: $root_dir"

    # Check if we already have python:
    local tools_dir=$root_dir/tools/linux
    if [[ ! -d $tools_dir ]]; then
        echo "Creating tools/linux folder..."
        mkdir $tools_dir
    fi

    local python_dir=$tools_dir/python-$python_version
    local python_path=$python_dir/bin/python3

    if [[ ! -d $python_dir ]]; then
        # Get the path to package:
        local python_pkg=$root_dir/tools/packages/python-$python_version-linux.tar.xz

        echo "Extracting $python_pkg..."
        # $unzip_path x -o"$tools_dir" "$python_pkg" > /dev/null
        pushd $tools_dir >/dev/null
        tar xvJf $python_pkg
        popd >/dev/null

        # Once we have deployed the base python tool package we start with upgrading pip:
        echo "Upgrading pip..."
        $python_path -m pip install --upgrade pip --no-warn-script-location

        # Finally we install the python requirements:
        echo "Installing python requirements..."
        $python_path -m pip install -r $root_dir/tools/requirements.txt --no-warn-script-location
    fi

    if [ "$1" == "--install-py-reqs" ]; then
        echo "Installing python requirements..."
        $python_path -m pip install -r $root_dir/tools/requirements.txt --no-warn-script-location
    elif [ "$1" == "--pre-commit" ]; then
        echo "black outputs:" >$root_dir/pre-commit.log
        $python_path -m black --line-length 120 $root_dir/nvh 2>&1 >>$root_dir/pre-commit.log
        echo "isort outputs:" >>$root_dir/pre-commit.log
        $python_path -m isort --profile black $root_dir/nvh 2>&1 >>$root_dir/pre-commit.log
        echo "flake8 outputs:" >>$root_dir/pre-commit.log
        $python_path -m flake8 --max-line-length=120 --ignore="E203,W503" $root_dir/nvh 2>&1 >$root_dir/pre-commit.log
        status=$?
        if [ "$status" == "0" ]; then
            echo "OK"
        else
            echo "FAILED"
        fi
    elif [ "$1" == "python" ]; then
        # shift the args by one:
        shift
        $python_path "$@"
    elif [ "$1" == "pip" ]; then
        # shift the args by one:
        shift
        $python_path -m pip "$@"
    else
        # Execute the command in python:
        $python_path $root_dir/cli.py "$@"
    fi
}

${PROJ_NAME}() {
    # Install pre-commit hook if applicable:
    if [ -d $ROOT_DIR/.git ] && [ ! -f $ROOT_DIR/.git/hooks/pre-commit ]; then
        echo "Installing pre-commit hook..."
        echo '#!/bin/bash' >$ROOT_DIR/.git/hooks/pre-commit
        echo 'res=$(./cli.sh --pre-commit <src_folder_name_here>)' >>$ROOT_DIR/.git/hooks/pre-commit
        echo '[ "$res" == "OK" ] || (echo "Pre-commit hook failed, check the pre-commit.log file for details." && exit 1)' >>$ROOT_DIR/.git/hooks/pre-commit
    fi

    if [ "$1" == "home" ]; then
        # We simply go to the home of this project:
        cd "$ROOT_DIR"
    else
        # Check if we are on a windows or a linux system:
        pname=$(uname -s)

        case $pname in
        CYGWIN*)
            _${PROJ_NAME}_run_cli_cygwin "$@"
            ;;
        MINGW*)
            _${PROJ_NAME}_run_cli_mingw "$@"
            ;;
        *)
            _${PROJ_NAME}_run_cli_linux "$@"
            ;;
        esac
    fi
}

# cf. https://askubuntu.com/questions/141928/what-is-the-difference-between-bin-sh-and-bin-bash
(return 0 2>/dev/null) && sourced=1 || sourced=0
if [ "$sourced" == "0" ]; then
    ${PROJ_NAME} "$@"
else
    echo "${PROJ_NAME} command loaded."
fi
