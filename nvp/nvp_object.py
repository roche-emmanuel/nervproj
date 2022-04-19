"""NVP base object class"""
import configparser

import logging
import os
import stat
import pprint
import time
import re
import sys
import subprocess
import shutil
import json
import urllib
import jstyleson
import requests

logger = logging.getLogger(__name__)

printer = pprint.PrettyPrinter(indent=2)


def onerror(func, path, _exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    # cf. https://stackoverflow.com/questions/2656322/shutil-rmtree-fails-on-windows-with-access-is-denied
    # Is the error an access error?
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise  # pylint: disable=misplaced-bare-raise


class NVPObject(object):
    """Base NVP object class"""

    @property
    def is_windows(self):
        """chekc if we are on windows"""
        return sys.platform.startswith('win32')

    @property
    def is_linux(self):
        """chekc if we are on linux"""
        return sys.platform.startswith('linux')

    def pretty_print(self, obj):
        """Pretty print an object"""
        if obj is None:
            return "None"

        return printer.pformat(obj)

    def get_method(self, method_name):
        """Retrieve a method by name in self, or return None if not found"""
        return getattr(self, method_name, None)

    def add_execute_permission(self, *parts):
        """Add the execute permission to a given file"""
        filename = self.get_path(*parts)

        # check if we already have the execution permission:
        if not os.access(filename, os.X_OK):
            logger.info("Adding execute permission on %s", filename)
            stt = os.stat(filename)
            os.chmod(filename, stt.st_mode | stat.S_IEXEC)

    def set_chmod(self, my_path, modes):
        """Set the access rights for a given path"""
        um = int(modes[0])
        gm = int(modes[1])
        om = int(modes[2])
        mode = 0
        if um & 1:
            mode |= stat.S_IXUSR
        if um & 2:
            mode |= stat.S_IWUSR
        if um & 4:
            mode |= stat.S_IRUSR
        if gm & 1:
            mode |= stat.S_IXGRP
        if gm & 2:
            mode |= stat.S_IWGRP
        if gm & 4:
            mode |= stat.S_IRGRP
        if om & 1:
            mode |= stat.S_IXOTH
        if om & 2:
            mode |= stat.S_IWOTH
        if om & 4:
            mode |= stat.S_IROTH

        os.chmod(my_path, mode)

    def dir_exists(self, *parts):
        """Check if a directory exists."""
        return os.path.isdir(self.get_path(*parts))

    def file_exists(self, *parts):
        """Check if a file exists."""
        return os.path.isfile(self.get_path(*parts))

    def path_exists(self, *parts):
        """Check if a path exists."""
        return os.path.exists(self.get_path(*parts))

    def is_relative_path(self, my_path):
        """Return true if the given path is relative"""
        return not os.path.isabs(my_path)

    def is_absolute_path(self, my_path):
        """Return true if the given path is absolute"""
        return os.path.isabs(my_path)

    def get_parent_folder(self, *parts):
        """Retrieve the parent folder from any path."""
        my_path = self.get_path(*parts)
        return os.path.dirname(my_path)

    def get_filename(self, *parts):
        """Retrieve the filename from a given full path"""
        my_path = self.get_path(*parts)
        return os.path.basename(my_path)

    def get_file_size(self, my_path):
        """Retrieve the size of a given file"""
        infos = os.lstat(my_path)
        return infos.st_size

    def get_cwd(self):
        """Return the current CWD"""
        cwd = os.getenv("PWD", os.getcwd())
        if cwd.startswith("/cygdrive/"):
            cwd = self.from_cygwin_path(cwd)
        return cwd

    def get_path(self, *parts):
        """Create a file path from parts"""
        return os.path.join(*parts)

    def make_folder(self, *parts):
        """Create a folder recursively if it doesn't exist yet
        and return the complete path"""

        folder = self.get_path(*parts)
        if not self.dir_exists(folder):
            # Create the dependency build folder:
            os.makedirs(folder, exist_ok=True)

        return folder

    def remove_folder(self, *parts, recursive=True):
        """Helper method used to remove a given folder either recursively or not."""

        folder = self.get_path(*parts)
        while self.dir_exists(folder):
            try:
                if recursive:
                    shutil.rmtree(folder, onerror=onerror)
                else:
                    os.rmdir(folder)
            except OSError as exp:
                logger.warning("Failed to remove folder %s: %s", folder, str(exp))
                time.sleep(1.0)

    def remove_file(self, *parts):
        """Remove a given file from the system."""
        fname = self.get_path(*parts)
        if self.file_exists(fname):
            os.remove(fname)

    def move_path(self, src_path, dest_path):
        """Move the source path to the destination path"""
        if src_path != dest_path:
            shutil.move(src_path, dest_path)

    def rename_folder(self, src_path, dest_path):
        """Rename a folder"""
        self.move_path(src_path, dest_path)

    def rename_file(self, src_path, dest_path):
        """Rename a file"""
        self.move_path(src_path, dest_path)

    def is_folder_empty(self, fpath):
        """Check if a given folder is empty"""
        if self.dir_exists(fpath):
            return len(os.listdir(fpath)) == 0
        return True

    def set_path_extension(self, src_path, ext):
        """Change the extension of a given path"""
        parts = os.path.splitext(src_path)
        return parts[0]+ext

    def get_path_extension(self, src_path):
        """Get the extension of a given path"""
        parts = os.path.splitext(src_path)
        return parts[1]

    def read_text_file(self, *parts, mode="r"):
        """Read the content of a file as string."""

        fname = self.get_path(*parts)
        with open(fname, mode, encoding="utf-8") as file:
            content = file.read()
        return content

    def write_text_file(self, content, *parts, mode="w", newline=None):
        """Write content of file"""

        fname = self.get_path(*parts)
        with open(fname, mode, encoding="utf-8", newline=newline) as file:
            file.write(content)

    def url_encode_path(self, file_path):
        """Apply URL encoding rules to a given file path"""
        return urllib.parse.quote(file_path, safe='')

    def read_json(self, *parts):
        """Read JSON file as object"""
        fname = self.get_path(*parts)
        try:
            content = self.read_text_file(*parts)
            return jstyleson.loads(content)
        except json.decoder.JSONDecodeError as err:
            logger.error("Error parsing json file %s: %s", fname, str(err))
            logger.error("Content is: %s", self.pretty_print(content))
            raise err

    def write_json(self, data, *parts, indent=2):
        """Write a structure as JSON file"""
        content = jstyleson.dumps(data, indent=indent)
        self.write_text_file(content, *parts)

    def read_ini(self, *parts):
        """Read a configparser object from a given file"""
        fname = self.get_path(*parts)
        config = configparser.ConfigParser()
        config.read(fname)
        return config

    def write_ini(self, config, *parts, newline=None):
        """Write a config parser object as ini file"""
        fname = self.get_path(*parts)
        with open(fname, "w", encoding="utf-8", newline=newline) as file:
            config.write(file)

    def replace_in_file(self, filename, src, repl):
        """Replace a given statement with another in a given file, and then
        re-write that file in place."""

        # Read in the file
        with open(filename, 'r', encoding="utf-8") as file:
            filedata = file.read()

        # Replace the target string
        filedata = filedata.replace(src, repl)

        # Write the file out again
        with open(filename, 'w', encoding="utf-8") as file:
            file.write(filedata)

    def copy_file(self, src_file, dst_file, force=False):
        """copy a source file to a destination file, overriding
        destination if force==True"""

        if not self.file_exists(src_file):
            return False

        if self.file_exists(dst_file):
            if force:
                # Remove this file first:
                self.remove_file(dst_file)
            else:
                return False

        shutil.copyfile(src_file, dst_file)
        return True

    def remove_file_extension(self, filename):
        "Remove extensio from a filename, also taking care of tar.XX formats"

        fname = filename.lower()
        if fname.endswith(".tar.bz2"):
            return filename[:-8]
        if fname.endswith(".tar.xz") or fname.endswith(".tar.gz"):
            return filename[:-7]
        if fname.endswith(".7z.exe"):
            return filename[:-7]

        fname, _ext = os.path.splitext(filename)
        return fname

    def is_downloadable(self, url):
        """Check if a given URL is downloadable"""
        # cf. https://stackoverflow.com/questions/61629856/how-to-check-whether-a-url-is-downloadable-or-not
        # headers = requests.head(url).headers
        # return 'attachment' in headers.get('Content-Disposition', '')
        response = requests.get(url, stream=True)
        if not response.ok:
            return False

        if not 'content-length' in response.headers:
            return False

        return int(response.headers.get('content-length')) > 0

    def to_cygwin_path(self, *parts):
        """Try convert a windows path to a cygwin path if applicable"""
        fname = self.get_path(*parts)
        try:
            res = subprocess.check_output(["cygpath.exe", fname])
            # Convert to string an remove trailing newlines:
            return res.decode("utf-8").rstrip()
        except FileNotFoundError:
            return None

    def from_cygwin_path(self, *parts):
        """Try convert a cygwin path to windows path if applicable"""
        fname = self.get_path(*parts)
        try:
            res = subprocess.check_output(["cygpath.exe", "-w", fname])
            # Convert to string an remove trailing newlines:
            return res.decode("utf-8").rstrip()
        except FileNotFoundError:
            return None

    def get_win_home_dir(self):
        """Retrieve the canonical home directory on windows."""
        home_drive = os.getenv("HOMEDRIVE")
        home_path = os.getenv("HOMEPATH")
        assert home_drive is not None and home_path is not None, "Invalid windows home drive or path"
        return home_drive+home_path

    def execute(self, cmd, verbose=True, cwd=None, env=None, check=True):
        """Execute a command optionally displaying the outputs."""

        stdout = None if verbose else subprocess.DEVNULL
        stderr = None if verbose else subprocess.DEVNULL
        # logger.info("Executing command: %s", cmd)
        if check:
            subprocess.check_call(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env)
        else:
            subprocess.run(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env, check=False)

    def get_all_files(self, folder, exp=".*", recursive=False):
        """Get all the files matching a given pattern in a folder."""

        # prepare a pattern:
        p = re.compile(exp)
        num = len(folder)+1
        if recursive:
            # Retrieve all files in a given folder recursively
            res = []
            # logDEBUG("Searching for files in %s" % folder)
            for root, _directories, filenames in os.walk(folder):
                # for directory in directories:
                #         print os.path.join(root, directory)
                for filename in filenames:
                    fname = os.path.join(root, filename)
                    if (os.path.isfile(fname) and p.search(fname) is not None):
                        # logDEBUG("Found file: %s" % fname)
                        # We should remove the foldre prefix here:
                        res.append(fname[num:])
            return res
        else:
            return [f for f in os.listdir(folder) if (os.path.isfile(os.path.join(folder, f)) and p.search(f) is not None)]

    def get_all_folders(self, folder, exp=".*", recursive=False):
        """Get all the folders matching a given pattern in a folder."""

        # prepare a pattern:
        p = re.compile(exp)
        num = len(folder)+1
        if recursive:
            # Retrieve all files in a given folder recursively
            res = []
            # logDEBUG("Searching for files in %s" % folder)
            for root, directories, _filenames in os.walk(folder):
                # for directory in directories:
                #         print os.path.join(root, directory)
                for filename in directories:
                    fname = os.path.join(root, filename)
                    if (os.path.isdir(fname) and p.search(fname) is not None):
                        # logDEBUG("Found file: %s" % fname)
                        # We should remove the foldre prefix here:
                        res.append(fname[num:])
            return res
        else:
            return [f for f in os.listdir(folder) if (os.path.isdir(os.path.join(folder, f)) and p.search(f) is not None)]

    def prepend_env_list(self, paths, env, key="PATH"):
        """Add a list of paths to the environment PATH variable."""
        sep = ";" if self.is_windows else ":"
        all_paths = set()

        if isinstance(paths, str):
            paths = [paths]

        for elem in paths:
            all_paths = all_paths.union(set(elem.split(sep)))

        if key in env:
            plist = set(env[key].split(sep))
            all_paths = all_paths.union(plist)

        # logger.info("All paths in prepend_env_list: %s", all_paths)
        env[key] = sep.join(all_paths)
        return env

    def append_env_list(self, paths, env, key="PATH"):
        """Add a list of paths to the environment PATH variable."""
        sep = ";" if self.is_windows else ":"
        all_paths = set()

        if isinstance(paths, str):
            paths = [paths]

        for elem in paths:
            all_paths = all_paths.union(set(elem.split(sep)))

        if key in env:
            plist = set(env[key].split(sep))
            all_paths = plist.union(all_paths)

        # logger.info("All paths in append_env_list: %s", all_paths)
        env[key] = sep.join(all_paths)
        return env
