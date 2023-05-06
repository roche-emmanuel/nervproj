#!/usr/bin/env bash

# trap ctrl-c and call ctrl_c()
# trap ctrl_c INT

# function ctrl_c() {
#     echo "** Trapped CTRL-C"
# }

# cf. https://stackoverflow.com/questions/59895/how-can-i-get-the-source-directory-of-a-bash-script-from-within-the-script-itsel
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

_nvp_run_cli_windows() {
    # On windows we should simply rely on the cli.bat script below:
    ROOT_DIR="$(cygpath -w $ROOT_DIR)"
    cmd /C "$ROOT_DIR\\cli.bat" "$@"
}

_nvp_run_cli_linux() {
    local python_version="3.10.2"

    # On linux we should call the python cli directly:
    # Get the project root folder:
    local root_dir=$(readlink -f $ROOT_DIR/)
    # echo "NervLand root dir is: $root_dir"

    local req_file="requirements.txt"
    local platform="linux"

    if [ -f /sys/firmware/devicetree/base/model ] && grep -q "Raspberry" /sys/firmware/devicetree/base/model; then
        req_file="rasp_requirements.txt"
        # Should also check here if we are on aarch64 or armv7l
        local ARCH=$(uname -m)
        if [ "${ARCH}" == "aarch64" ]; then
            platform="raspberry64"
        else
            platform="raspberry"
        fi
    fi

    # Check if we already have python:
    local tools_dir=$root_dir/tools/${platform}
    if [[ ! -d $tools_dir ]]; then
        echo "Creating tools/${platform} folder..."
        mkdir $tools_dir
    fi

    local python_dir=$tools_dir/python-$python_version
    local python_path=$python_dir/bin/python3

    if [[ ! -d $python_dir ]]; then
        # Check if we already have the python.7z
        local python_pkg=$root_dir/tools/packages/python-$python_version-${platform}.tar.xz

        if [[ -e "$python_pkg" ]]; then
            echo "Extracting $python_pkg..."
            # $unzip_path x -o"$tools_dir" "$python_pkg" > /dev/null
            pushd $tools_dir >/dev/null
            tar xvJf $python_pkg
            popd >/dev/null
        else
            echo "Building python-$python_version from sources..."
            local pyfolder="Python-$python_version"
            local tarfile="$pyfolder.tar.xz"
            local url="https://www.python.org/ftp/python/$python_version/$tarfile"

            local tmp_dir=$root_dir/temp
            if [[ ! -d $tmp_dir ]]; then
                echo "Creating temp folder..."
                mkdir $tmp_dir
            fi

            pushd $tmp_dir >/dev/null

            # Remove any previous build folder:
            if [[ -d $pyfolder ]]; then
                echo "Removing previous $pyfolder..."
                rm -Rf $pyfolder
            fi
            if [[ -e $tarfile ]]; then
                echo "Removing previous $tarfile..."
                rm -Rf $tarfile
            fi

            echo "Downloading python sources from $url"
            wget -O $tarfile $url
            tar xvJf $tarfile

            # Enter into the python source folder:
            pushd $pyfolder >/dev/null

            # should ensure that the dependency packages are installed (?)
            # sudo apt-get install libbz2-dev liblzma-dev

            echo "Configuring python..."
            ./configure --enable-optimizations --prefix=$python_dir.tmp CFLAGS=-fPIC CXXFLAGS=-fPIC
            # --enable-loadable-sqlite-extensions --with-system-expat --with-system-ffi CPPFLAGS=-I/usr/local/include LDFLAGS=-L/usr/local/lib

            echo "Building python..."
            make

            echo "Installing python..."
            make install

            popd >/dev/null
            popd >/dev/null

            # Now we rename the destination folder:
            mv $python_dir.tmp $python_dir

            # And we create the 7z package:
            echo "Generating python tool package..."
            pushd $tools_dir >/dev/null
            tar cJf python-$python_version-${platform}.tar.xz python-$python_version
            mv python-$python_version-${platform}.tar.xz ../packages
            popd >/dev/null
            # $unzip_path a -t7z $python_pkg $python_dir -m0=lzma2 -mx=9 -aoa -mfb=64 -md=32m -ms=on -r

            # removing python build folder:
            echo "Removing python build folder..."
            rm -Rf temp/$pyfolder*

            echo "Done generating python package."
        fi

        # Once we have deployed the base python tool package we start with upgrading pip:
        echo "Upgrading pip..."
        $python_path -m pip install --upgrade pip --no-warn-script-location

        # Finally we install the python requirements:
        echo "Installing python requirements..."
        $python_path -m pip install -r $root_dir/tools/${req_file} --no-warn-script-location
    fi

    if [ "$1" == "--install-py-reqs" ]; then
        echo "Installing python requirements..."
        $python_path -m pip install -r $root_dir/tools/${req_file} --no-warn-script-location
    elif [ "$1" == "--pre-commit" ]; then
        echo "black outputs:" >$root_dir/pre-commit.log
        $python_path -m black --line-length 120 $root_dir/$2 >>$root_dir/pre-commit.log 2>&1
        echo "isort outputs:" >>$root_dir/pre-commit.log
        $python_path -m isort --profile black $root_dir/$2 >>$root_dir/pre-commit.log 2>&1
        echo "flake8 outputs:" >>$root_dir/pre-commit.log
        $python_path -m flake8 --max-line-length=120 --ignore="E203,W503" $root_dir/$2 >>$root_dir/pre-commit.log 2>&1
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

nvp() {
    if [ "$1" == "home" ]; then
        # check if we are requesting the home of a sub project:
        if [ "$2" == "" ]; then
            # We simply go to the home of nervproj:
            cd "$ROOT_DIR"
        else
            # Find the home dir of the sub project:
            local home_dir=$(nvp get_dir -p $2)
            if [ -d "$home_dir" ]; then
                cd $home_dir
            else
                echo "Invalid result: $home_dir"
            fi
        fi
    else
        # Check if we are on a windows or a linux system:
        pname=$(uname -s)

        case $pname in
        CYGWIN*)
            _nvp_run_cli_windows "$@"
            ;;
        *)
            _nvp_run_cli_linux "$@"
            ;;
        esac
    fi
}

if [ "$#" != "0" ]; then
    nvp "$@"
else
    echo "NervProj manager loaded."
fi
