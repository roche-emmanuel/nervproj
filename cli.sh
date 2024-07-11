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
    
    if [[ "$1" == "build-python" ]]; then
        local python_default_version=$python_version
        python_version=${2:-$python_default_version}
    fi

    # On linux we should call the python cli directly:
    # Get the project root folder:
    local root_dir=$(readlink -f $ROOT_DIR/)
    # echo "NervLand root dir is: $root_dir"

    local req_file="requirements.txt"
    local platform="linux"
    local ssltarget="linux-x86_64"

    if [[ -f /sys/firmware/devicetree/base/model ]] && grep -q "Raspberry" /sys/firmware/devicetree/base/model; then
        req_file="rasp_requirements.txt"
        # Should also check here if we are on aarch64 or armv7l
        local ARCH=$(uname -m)
        if [[ "${ARCH}" == "aarch64" ]]; then
            platform="raspberry64"
            ssltarget=linux-generic64
        else
            platform="raspberry"
            ssltarget=linux-generic32
        fi
    fi

    # Check if we already have python:
    local tools_dir=$root_dir/tools/${platform}
    if [[ ! -d $tools_dir ]]; then
        echo "Creating tools/${platform} folder..."
        mkdir $tools_dir
    fi

    local python_dir=$tools_dir/python-$python_version
    local tmp_dir=$root_dir/temp
    local python_tmp_dir=$tmp_dir/out/python-$python_version
    local python_path=$python_dir/bin/python3
    local python_pkg=$root_dir/tools/packages/python-$python_version-${platform}.tar.xz

    local build_required=no
    if [[ ! -d $python_dir ]]; then
        build_required=yes
    fi
    
    if [[ "$1" == "build-python" ]]; then
        # We don't remove the current python installation as it might already be in use.
        # rm -Rf $python_dir
        if [[ -e "$python_pkg" ]]; then
            # We should rename this package to .bak
            if [[ -e "$python_pkg.bak" ]]; then
                echo Removing previous $python_pkg.bak file.
                rm $python_pkg.bak
            fi
            mv $python_pkg $python_pkg.bak
        fi
        
        # Force building python:
        build_required=yes
    fi

    if [[ $build_required == "yes" ]]; then
        # Check if we already have the python.7z
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

            if [[ -d $tmp_dir ]]; then
                echo "Clearing temp folder $tmp_dir..."
                rm -Rf $tmp_dir
            fi

            echo "Creating temp folder $tmp_dir..."
            mkdir $tmp_dir

            # First we should build openssl statically only:
            sslversion="3.0.14"
            # sslversion="1.1.1w"
            sslbuilddir=$tmp_dir/openssl-$sslversion
            ssldir=$tmp_dir/ssl
            sslfile=openssl-$sslversion.tar.gz
            
            cd $tmp_dir
            if [[ -d $sslbuilddir ]]; then
                echo "Removing previous $sslbuilddir..."
                rm -Rf $sslbuilddir
            fi
            if [[ -d $ssldir ]]; then
                echo "Removing previous $ssldir..."
                rm -Rf $ssldir
            fi

            if [[ -e $sslfile ]]; then
                echo "Removing previous $sslfile..."
                rm -Rf $sslfile
            fi

            sslurl=https://www.openssl.org/source/$sslfile
            echo Building OpenSSL $sslversion...
            wget $sslurl
            tar -xvf $sslfile
            cd $sslbuilddir
            ./Configure $ssltarget no-shared --prefix=$ssldir
            # ./Configure $ssltarget -static --prefix=$ssldir
            make -j`nproc`
            make install_sw

            cd $tmp_dir

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
            cd $pyfolder

            # should ensure that the dependency packages are installed (?)
            # sudo apt-get install libbz2-dev liblzma-dev

            # On raspberry pi for instance, could install:
            # sudo apt install build-essential tk-dev libncurses5-dev 
            # libncursesw5-dev libreadline-dev libdb5.3-dev libgdbm-dev libsqlite3-dev 
            # libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev
            # => Note tk-dev could be ignored as it is very large (+500MB)
            
            echo "Configuring python..."
            ./configure --enable-optimizations --with-openssl=$ssldir --prefix=$python_tmp_dir CFLAGS="-I$ssldir/include -fPIC" CXXFLAGS="-I$ssldir/include -fPIC" LDFLAGS="-L$ssldir/lib64 -ldl" 
            # --enable-loadable-sqlite-extensions --with-system-expat --with-system-ffi CPPFLAGS=-I/usr/local/include LDFLAGS=-L/usr/local/lib

            echo "Building python..."
            make -j`nproc`
            # make

            echo "Installing python..."
            make install

            # echo "Running python tests..."
            # make test

            # And we create the package:
            echo "Generating python tool package $python_version-${platform}.tar.xz..."
            cd $tmp_dir/out
            tar cJf python-$python_version-${platform}.tar.xz python-$python_version
            mv python-$python_version-${platform}.tar.xz $root_dir/tools/packages/

            # Now we rename the destination folder:
            # But only if it doesn't exist yet:
            if [[ -d $python_dir ]]; then
                echo "Done generating python package."
                echo "=> No installation performed since $python_dir already exists."

                echo "Removing python build folder..."
                cd $root_dir
                rm -Rf $tmp_dir

                exit 0
            fi

            mv $python_tmp_dir $python_dir

            # removing python build folder:
            echo "Removing python build folder..."
            cd $root_dir
            rm -Rf $tmp_dir

            echo "Done generating python package."

            # Exit if we were only requesting to build python:
            [[ "$1" == "build-python" ]] && exit 0
        fi

        # Once we have deployed the base python tool package we start with upgrading pip:
        echo "Upgrading pip..."
        $python_path -m pip install --no-warn-script-location --upgrade pip 

        # Finally we install the python requirements:
        echo "Installing python requirements..."
        $python_path -m pip install --no-warn-script-location -r $root_dir/tools/${req_file}
    fi

    if [[ "$1" == "--install-py-reqs" ]]; then
        echo "Installing python requirements..."
        $python_path -m pip install --no-warn-script-location -r $root_dir/tools/${req_file}
    elif [[ "$1" == "--pre-commit" ]]; then
        echo "black outputs:" >$root_dir/pre-commit.log
        $python_path -m black --line-length 120 $root_dir/$2 >>$root_dir/pre-commit.log 2>&1
        echo "isort outputs:" >>$root_dir/pre-commit.log
        $python_path -m isort --profile black $root_dir/$2 >>$root_dir/pre-commit.log 2>&1
        echo "flake8 outputs:" >>$root_dir/pre-commit.log
        $python_path -m flake8 --max-line-length=120 --ignore="E203,W503" $root_dir/$2 >>$root_dir/pre-commit.log 2>&1
        status=$?
        if [[ "$status" == "0" ]]; then
            echo "OK"
        else
            echo "FAILED"
        fi
    elif [[ "$1" == "python" ]]; then
        # shift the args by one:
        shift
        $python_path "$@"
    elif [[ "$1" == "pip" ]]; then
        # shift the args by one:
        shift
        $python_path -m pip "$@"
    else
        # Execute the command in python:
        $python_path $root_dir/cli.py "$@"
    fi
}

nvp() {
    if [[ "$1" == "home" ]]; then
        # check if we are requesting the home of a sub project:
        if [[ -z "$2" ]]; then
            # We simply go to the home of nervproj:
            cd "$ROOT_DIR"
        else
            # Find the home dir of the sub project:
            local home_dir=$(nvp get_dir -p $2)
            if [[ -d "$home_dir" ]]; then
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

if [[ "$#" != "0" ]]; then
    nvp "$@"
else
    echo "NervProj manager loaded."
fi
