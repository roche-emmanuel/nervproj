"""NVP base object class"""
from asyncio.subprocess import DEVNULL

import logging
import os
import stat
import pprint
import time
import subprocess
import shutil
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

    def dir_exists(self, *parts):
        """Check if a directory exists."""
        return os.path.isdir(self.get_path(*parts))

    def file_exists(self, *parts):
        """Check if a file exists."""
        return os.path.isfile(self.get_path(*parts))

    def path_exists(self, *parts):
        """Check if a path exists."""
        return os.path.exists(self.get_path(*parts))

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

    def read_json(self, *parts):
        """Read JSON file as object"""
        content = self.read_text_file(*parts)
        return jstyleson.loads(content)

    def write_json(self, data, *parts):
        """Write a structure as JSON file"""
        content = jstyleson.dumps(data)
        self.write_text_file(content, *parts)

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

    def execute(self, cmd, verbose=True, cwd=None, env=None):
        """Execute a command optionally displaying the outputs."""

        stdout = None if verbose else DEVNULL
        stderr = None if verbose else DEVNULL
        # logger.info("Executing command: %s", cmd)
        subprocess.check_call(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env)
        # subprocess.check_call(cmd)