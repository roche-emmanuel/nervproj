#!/usr/bin/env bash

# cf. https://stackoverflow.com/questions/59895/how-can-i-get-the-source-directory-of-a-bash-script-from-within-the-script-itsel
ROOT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

run_cli_windows()
{
    # On windows we should simply rely on the cli.bat script below:
    ROOT_DIR="`cygpath -w $ROOT_DIR`"
    cmd /C "$ROOT_DIR\\cli.bat" "$@"
}

run_cli_linux()
{
    local python_version="3.10.2"
    local unzip_version="21.07"

    # On linux we should call the python cli directly:
    # Get the project root folder: 
    local root_dir=`readlink -f $ROOT_DIR/`
    echo "NervLand root dir is: $root_dir"
    
    # Check if we already have python:
    local tools_dir=$root_dir/tools/linux

    local tmp_dir=$root_dir/temp
    if [[ ! -d $tmp_dir ]]; then
        echo "Creating temp folder..."
        mkdir $tmp_dir
    fi

    local unzip_dir=$tools_dir/7zip-$unzip_version
    local unzip_path=$unzip_dir/7zzs

    if [[ ! -d $unzip_dir ]]; then
        echo "Extracting 7zip tool..."
        pushd $tools_dir > /dev/null
        tar xvJf ../packages/7zip-$unzip_version-linux.tar.xz
        popd > /dev/null
    fi

    local python_dir=$tools_dir/python-$python_version
    local python_path=$python_dir/bin/python3

    if [[ ! -d $python_dir ]]; then
        # Check if we already have the python.7z 
        local python_pkg=$root_dir/tools/packages/python-$python_version-linux.7z

        if [[ -e "$python_pkg" ]]; then
            echo "Extracting $python_pkg..."
            $unzip_path x -o"$tools_dir" "$python_pkg" > /dev/null
        else
            local pyfolder="Python-$python_version"
            local tarfile="$pyfolder.tar.xz"
            local url="https://www.python.org/ftp/python/$python_version/$tarfile"

            pushd $tmp_dir > /dev/null

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
            pushd $pyfolder > /dev/null

            # should ensure that the dependency packages are installed (?)
            # sudo apt-get install libbz2-dev liblzma-dev

            echo "Configuring python..."
            ./configure --enable-optimizations --prefix=$python_dir.tmp CFLAGS=-fPIC CXXFLAGS=-fPIC
            # --enable-loadable-sqlite-extensions --with-system-expat --with-system-ffi CPPFLAGS=-I/usr/local/include LDFLAGS=-L/usr/local/lib

            echo "Building python..."
            # Note: Building with optimizations is very slow:
            make

            echo "Installing python..."
            make install

            popd > /dev/null
            popd > /dev/null

            # Now we rename the destination folder:
            mv $python_dir.tmp $python_dir


            # And we create the 7z package:
            echo "Generating python tool package..."
            $unzip_path a -t7z $python_pkg $python_dir -m0=lzma2 -mx=9 -aoa -mfb=64 -md=32m -ms=on -r

            # removing python build folder:
            echo "Removing python build folder..."
            rm -Rf temp/$pyfolder*

            echo "Done generating python package."
        fi

        # Once we have deployed the base python tool package we start with upgrading pip:
        echo "Upgrading pip..."
        $python_path -m pip install --upgrade pip

        # Finally we install the python requirements:
        echo "Installing python requirements..."
        $python_path -m pip install -r $root_dir/tools/requirements.txt
    fi
    
    # Execute the command in python:
    $python_path $root_dir/scripts/cli.py "$@"
}


if [ "$#" != "0" ]; then
    if [ "$1" == "home" ]; then
        echo "Going to: $ROOT_DIR"
        cd "$ROOT_DIR"
    else
        echo "running cli..."

        # Check if we are on a windows or a linux system:
        pname=`uname -s`

        case $pname in
        CYGWIN*)
            run_cli_windows "$@"
            ;;
        *)
            run_cli_linux "$@"
            ;;
        esac
    fi
fi
