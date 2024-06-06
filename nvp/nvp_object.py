"""NVP base object class"""

import collections
import configparser
import json

# import traceback
import logging
import os
import pprint
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import unicodedata
import urllib
from datetime import date, datetime
from queue import Queue
from threading import Thread

import jstyleson
import requests
import urllib3
import xxhash
import yaml
from yaml.loader import SafeLoader

logger = logging.getLogger(__name__)

printer = pprint.PrettyPrinter(indent=2)


class NVPCheckError(Exception):
    """Basic class representing an NVP exception."""


class ProgressFileWrapper:
    """A file-like object that wraps a file and a callback for progress reporting."""

    def __init__(self, callback):
        # self.file = file
        self.callback = callback

    def write(self, data):
        """write method"""
        # logger.info("Writing data...")
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        self.callback(data)
        # self.file.write(data)

    def close(self):
        """close method"""
        self.callback(None)
        # self.file.close()


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
        return sys.platform.startswith("win32")

    @property
    def is_linux(self):
        """chekc if we are on linux"""
        return sys.platform.startswith("linux")

    def check(self, cond, fmt, *args):
        """Check that a condition is true or raise an exception"""
        if cond is not True:
            raise NVPCheckError(fmt % args)

    def throw(self, fmt, *args):
        """raise an exception"""
        raise NVPCheckError(fmt % args)

    def safe_call(self, func, excepts, delay=2.0, retries=10, err_cb=None):
        """Execute a given code block safely, catching potential
        temporary errors and retrying as needed."""

        count = 1
        while True:
            try:
                return func()
            except Exception as err:  # pylint: disable=broad-except
                found = False
                for ecls in excepts:
                    if isinstance(err, ecls):
                        if err_cb is not None:
                            found = err_cb(err)
                        else:

                            logger.error(
                                "Exception %s occured in safe block (trial %d/%d)",
                                ecls.__name__,
                                count,
                                retries,
                            )

                            # logger.error("Exception occured in safe block (trial %d/%d):\n%s",
                            #              count+1, retries, traceback.format_exc())
                            # wait a moment if needed:
                            if delay > 0.0:
                                time.sleep(delay)
                        count += 1
                        found = True
                        break

                if count >= retries:
                    self.throw("save_call failed.")

                if not found:
                    # re-raise the exception:
                    raise err

    def pretty_print(self, obj):
        """Pretty print an object"""
        if obj is None:
            return "None"

        return printer.pformat(obj)

    def get_hostname(self):
        """Retrieve the hostname of the system"""
        return socket.gethostname()

    def get_thread_id(self):
        """Retrieve the current thread id"""
        return threading.get_ident()

    def get_time(self):
        """Retrieve the current time"""
        return time.time()

    def get_date(self):
        """Retrieve the current date"""
        return date.today()

    def get_now(self):
        """Retrieve the current datetime"""
        return datetime.now()

    def get_timestamp(self):
        """Retrieve the current unix timestamp"""
        return int(self.get_time())

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

    def get_chmod(self, my_path):
        """Retrieve the chmod of a file as a string"""

        stt = os.stat(my_path)
        smode = stt.st_mode
        uval = 0
        if smode & stat.S_IRUSR:
            uval += 4
        if smode & stat.S_IWUSR:
            uval += 2
        if smode & stat.S_IXUSR:
            uval += 1
        gval = 0
        if smode & stat.S_IRGRP:
            gval += 4
        if smode & stat.S_IWGRP:
            gval += 2
        if smode & stat.S_IXGRP:
            gval += 1
        oval = 0
        if smode & stat.S_IROTH:
            oval += 4
        if smode & stat.S_IWOTH:
            oval += 2
        if smode & stat.S_IXOTH:
            oval += 1

        return f"{uval}{gval}{oval}"

    def dir_exists(self, *parts):
        """Check if a directory exists."""
        return os.path.isdir(self.get_path(*parts))

    def file_exists(self, *parts):
        """Check if a file exists."""
        return os.path.isfile(self.get_path(*parts))

    def symlink_exists(self, *parts):
        """Check if a symlink exists."""
        return os.path.islink(self.get_path(*parts))

    def create_symlink(self, src, dest):
        """Create a symlink from source to dest"""
        os.symlink(src, dest)

    def path_exists(self, *parts):
        """Check if a path exists."""
        return os.path.exists(self.get_path(*parts))

    def is_relative_path(self, my_path):
        """Return true if the given path is relative"""
        return not os.path.isabs(my_path)

    def is_absolute_path(self, my_path):
        """Return true if the given path is absolute"""
        return os.path.isabs(my_path)

    def to_relative_path(self, my_path, base_dir):
        """Get a relative path from the given base dir"""
        return os.path.relpath(my_path, start=base_dir)

    def to_absolute_path(self, my_path):
        """Get an absolute path"""
        return os.path.abspath(my_path)

    def get_parent_folder(self, *parts, level=0):
        """Retrieve the parent folder from any path."""
        my_path = self.get_path(*parts)
        pdir = os.path.dirname(my_path)
        while level > 0:
            pdir = os.path.abspath(self.get_path(pdir, os.pardir))
            level -= 1

        return pdir

    def get_filename(self, *parts):
        """Retrieve the filename from a given full path"""
        my_path = self.get_path(*parts)
        return os.path.basename(my_path)

    def get_file_size(self, my_path):
        """Retrieve the size of a given file"""
        infos = os.lstat(my_path)
        return infos.st_size

    def get_file_mtime(self, my_path):
        """Retrieve the size of a given file"""
        infos = os.lstat(my_path)
        return int(infos.st_mtime)

    def get_cwd(self):
        """Return the current CWD"""
        cwd = os.getenv("PWD", os.getcwd())
        if self.is_windows and cwd.startswith("/"):
            # We are probably in a cygwin env:
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

    def compute_file_hash(self, fpath, blocksize=65536):
        """Compute the hash for a given file path"""
        # cf. https://www.programcreek.com/python/example/111324/xxhash.xxh64
        hasher = xxhash.xxh64()
        with open(fpath, "rb") as file:
            buf = file.read(blocksize)
            # otherwise hash the entire file
            while len(buf) > 0:
                hasher.update(buf)
                buf = file.read(blocksize)

        return hasher.intdigest()

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

    def move_path(self, src_path, dest_path, create_parent=False):
        """Move the source path to the destination path"""
        if src_path == dest_path:
            return

        if create_parent:
            parent_dir = self.get_parent_folder(dest_path)
            if not self.dir_exists(parent_dir):
                self.make_folder(parent_dir)

        # shutil.move(src_path, dest_path)
        os.rename(src_path, dest_path)

    def rename_folder(self, src_path, dest_path, create_parent=False, remove_existing=False):
        """Rename a folder"""
        if src_path == dest_path:
            return

        if self.dir_exists(dest_path):
            if remove_existing:
                self.remove_folder(dest_path, recursive=True)
            else:
                self.throw("Folder %s already exists.", dest_path)

        self.move_path(src_path, dest_path, create_parent=create_parent)

    def rename_file(self, src_path, dest_path, create_parent=False):
        """Rename a file"""
        if src_path == dest_path:
            return

        if self.file_exists(dest_path):
            self.remove_file(dest_path)

        self.move_path(src_path, dest_path, create_parent=create_parent)

    def is_folder_empty(self, fpath):
        """Check if a given folder is empty"""
        if self.dir_exists(fpath):
            return len(os.listdir(fpath)) == 0
        return True

    def set_path_extension(self, src_path, ext):
        """Change the extension of a given path"""
        parts = os.path.splitext(src_path)
        return parts[0] + ext

    def get_path_extension(self, src_path):
        """Get the extension of a given path"""
        parts = os.path.splitext(src_path)
        return parts[1]

    def read_binary_file(self, *parts, mode="rb"):
        """Read the content of a file as string."""

        fname = self.get_path(*parts)
        with open(fname, mode) as file:
            content = file.read()
        return content

    def read_text_file(self, *parts, mode="r"):
        """Read the content of a file as string."""

        fname = self.get_path(*parts)
        with open(fname, mode, encoding="utf-8") as file:
            content = file.read()
        return content

    def write_binary_file(self, content, *parts, mode="wb"):
        """Write content of file"""

        fname = self.get_path(*parts)
        with open(fname, mode) as file:
            file.write(content)

    def write_text_file(self, content, *parts, mode="w", newline=None, encoding="utf-8"):
        """Write content of file"""

        fname = self.get_path(*parts)
        with open(fname, mode, encoding=encoding, newline=newline) as file:
            file.write(content)

    def url_encode_path(self, file_path):
        """Apply URL encoding rules to a given file path"""
        return urllib.parse.quote(file_path, safe="")

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

    def write_json(self, data, *parts, indent=2, encoding="utf-8"):
        """Write a structure as JSON file"""
        content = jstyleson.dumps(data, indent=indent)
        self.write_text_file(content, *parts, encoding=encoding)

    def read_yaml(self, *parts) -> dict:
        """Read a YAML file as dict"""
        fname = self.get_path(*parts)
        try:
            with open(fname, "r", encoding="utf-8") as file:
                data = yaml.load(file, Loader=SafeLoader)
            return data
        except yaml.YAMLError as err:
            logger.error("Error parsing yaml file %s: %s", fname, str(err))
            raise err

    def write_yaml(self, data: dict, *parts, sort_keys=True):
        """Save a dict as YAML file"""
        fname = self.get_path(*parts)
        try:
            pdir = os.path.dirname(fname)
            if pdir != "":
                os.makedirs(pdir, exist_ok=True)
            with open(fname, "w+", encoding="utf-8") as file:
                yaml.dump(data, file, sort_keys=sort_keys)
        except yaml.YAMLError as err:
            logger.error("Error writing yaml file %s: %s", fname, str(err))
            raise err

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
        with open(filename, "r", encoding="utf-8") as file:
            filedata = file.read()

        # Replace the target string
        filedata = filedata.replace(src, repl)

        # Write the file out again
        with open(filename, "w", encoding="utf-8") as file:
            file.write(filedata)

    def copy_folder(self, src_folder, dst_folder):
        """Copy a source folder to a destination folder."""
        shutil.copytree(src_folder, dst_folder)

    def copy_file(self, src_file, dst_file, force=False, progress_threhold=5 * 1024 * 1024):
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
        if progress_threhold >= 0 and self.get_file_size(src_file) > progress_threhold:
            self.copy_file_with_progress(src_file, dst_file)
        else:
            shutil.copyfile(src_file, dst_file)
        return True

    def get_time_string(self, seconds):
        """Convert number of seconds into time string"""
        if seconds is None:
            return "???"

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        hours, minutes, seconds = int(hours), int(minutes), int(seconds)
        if hours > 0:
            return f"{hours}h{minutes:02d}m{seconds:02d}s"
        if minutes > 0:
            return f"{minutes}m{seconds:02d}s"
        return f"{seconds}s"

    def copy_file_with_progress(self, src_file, dst_file, prefix="", chunk_size=1024 * 1024, max_speed=0):
        """Copy a file with progress report"""

        if not self.file_exists(src_file):
            return False

        total_size = self.get_file_size(src_file)
        bytes_copied = 0
        max_len = 0
        mean_speed = 0.0

        start_time = time.time()
        with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
            while True:
                data = fsrc.read(chunk_size)
                if not data:
                    sys.stdout.write("\r" + (" " * max_len) + "\r")
                    sys.stdout.flush()
                    break

                nbytes = len(data)

                cur_time = time.time()
                # elapsed = cur_time - last_time
                elapsed = cur_time - start_time
                # last_time = cur_time
                if elapsed > 0.0:
                    # cur speed in kbytes/secs
                    # cur_speed = nbytes / (1024 * elapsed)
                    # mean_speed += (cur_speed - mean_speed) * speed_adapt
                    # Mean_speed in bytes/secs:
                    mean_speed = bytes_copied / elapsed

                bytes_copied += nbytes

                # Compute the estimated remaining time:
                remaining_size = total_size - bytes_copied
                remaining_time = remaining_size / mean_speed if mean_speed > 0 else None
                time_str = self.get_time_string(remaining_time)

                fdst.write(data)
                frac = bytes_copied / total_size
                done = int(50 * frac)
                msg = f"\r{prefix}[{'=' * done}{' ' * (50-done)}] {bytes_copied}/{total_size} {frac*100:.3f}% @ {mean_speed/(1024.0*1024.0):.0f}MB/s ETA: {time_str}"
                max_len = max(max_len, len(msg) + 1)
                sys.stdout.write(msg)
                sys.stdout.flush()

                if max_speed > 0:
                    # Max_speed will be in bytes/secs:
                    # We should take a speed limit into consideration here:

                    # we downloaded dlsize in elapsed seconds
                    # and we have the limit of max_speed bytes per seconds.
                    # Compute how long we should take to download dlsize in seconds:
                    dl_dur = bytes_copied / max_speed
                    if elapsed < dl_dur:
                        # We took less time than the requirement so far, so we should speed
                        # for the remaining time:
                        time.sleep(dl_dur - elapsed)
                        # last_time = time.time()
        return True
        # sys.stdout.write("\n")
        # sys.stdout.flush()

    def get_download_callback(self, dst_file, total_size, prefix="", max_speed=0):
        """Write data to a file with progress report This will return a
        callback which should receive the data as argument.
        Calling the callback with None will clear the output line"""

        cbdata = {"bytes_copied": 0, "max_len": 0, "mean_speed": 0.0}

        start_time = time.time()

        def callback(data):

            if not data:
                sys.stdout.write("\r" + (" " * cbdata["max_len"]) + "\r")
                sys.stdout.flush()
                sys.stdout.write("\r")
                sys.stdout.flush()
                return

            nbytes = len(data)

            cur_time = time.time()
            elapsed = cur_time - start_time

            # last_time = cur_time
            if elapsed > 0.0:
                cbdata["mean_speed"] = cbdata["bytes_copied"] / elapsed

            cbdata["bytes_copied"] += nbytes

            # Compute the estimated remaining time:
            remaining_size = total_size - cbdata["bytes_copied"]
            remaining_time = remaining_size / cbdata["mean_speed"] if cbdata["mean_speed"] > 0 else None
            time_str = self.get_time_string(remaining_time)

            dst_file.write(data)
            frac = cbdata["bytes_copied"] / total_size
            done = int(50 * frac)
            msg = f"\r{prefix}[{'=' * done}{' ' * (50-done)}] {cbdata['bytes_copied']}/{total_size} "
            msg += f"{frac*100:.3f}% @ {cbdata['mean_speed']/1024.0:.0f}KB/s ETA: {time_str}"

            if len(msg) < cbdata["max_len"]:
                msg += " " * (cbdata["max_len"] - len(msg))
            else:
                # cbdata["max_len"] = max(cbdata["max_len"], len(msg))
                cbdata["max_len"] = len(msg)

            sys.stdout.write(msg)
            sys.stdout.flush()

            if max_speed > 0:
                # Max_speed will be in bytes/secs:
                # We should take a speed limit into consideration here:

                # we downloaded dlsize in elapsed seconds
                # and we have the limit of max_speed bytes per seconds.
                # Compute how long we should take to download dlsize in seconds:
                dl_dur = cbdata["bytes_copied"] / max_speed
                if elapsed < dl_dur:
                    # We took less time than the requirement so far, so we should speed
                    # for the remaining time:
                    time.sleep(dl_dur - elapsed)
                    # last_time = time.time()

        return callback

    def get_progress_callback(self, dst_file, total_steps, steps_cb=None, prefix="", max_speed=0):
        """Write data to a file with progress report This will return a
        callback which should receive the data as argument.
        Calling the callback with None will clear the output line"""

        cbdata = {"done_steps": 0, "max_len": 0, "mean_speed": 0.0, "last_time": 0.0}

        start_time = time.time()

        def callback(data):

            # logger.info("In callback with data %s", data)
            if not data:
                sys.stdout.write("\r" + (" " * cbdata["max_len"]) + "\r")
                sys.stdout.flush()
                sys.stdout.write("\r")
                sys.stdout.flush()
                return

            num_steps = len(data) if steps_cb is None else steps_cb(data)

            # nbytes = len(data)

            cur_time = time.time()
            elapsed = cur_time - start_time

            # last_time = cur_time
            if elapsed > 0.0:
                cbdata["mean_speed"] = cbdata["done_steps"] / elapsed

            cbdata["done_steps"] += num_steps

            # Compute the estimated remaining time:
            remaining_steps = total_steps - cbdata["done_steps"]
            remaining_time = remaining_steps / cbdata["mean_speed"] if cbdata["mean_speed"] > 0 else None
            time_str = self.get_time_string(remaining_time)

            if dst_file is not None:
                dst_file.write(data)

            if (cur_time - cbdata["last_time"]) > 0.2:
                # Update the display:
                cbdata["last_time"] = cur_time

                frac = cbdata["done_steps"] / total_steps
                done = int(50 * frac)
                msg = f"\r{prefix}[{'=' * done}{' ' * (50-done)}] {cbdata['done_steps']}/{total_steps} "
                msg += f"{frac*100:.3f}% @ {cbdata['mean_speed']:.0f} iter/s ETA: {time_str}"

                if len(msg) < cbdata["max_len"]:
                    msg += " " * (cbdata["max_len"] - len(msg))
                else:
                    # cbdata["max_len"] = max(cbdata["max_len"], len(msg))
                    cbdata["max_len"] = len(msg)

                sys.stdout.write(msg)
                sys.stdout.flush()

            if max_speed > 0:
                # Max_speed will be in bytes/secs:
                # We should take a speed limit into consideration here:

                # we downloaded dlsize in elapsed seconds
                # and we have the limit of max_speed bytes per seconds.
                # Compute how long we should take to download dlsize in seconds:
                dl_dur = cbdata["done_steps"] / max_speed
                if elapsed < dl_dur:
                    # We took less time than the requirement so far, so we should speed
                    # for the remaining time:
                    time.sleep(dl_dur - elapsed)
                    # last_time = time.time()

        return callback

    def wrap_write_progress(self, dst_file, total_steps, steps_cb=None, prefix="", max_speed=0):
        """Return a file wrapper to report write process"""

        callback = self.get_progress_callback(dst_file, total_steps, steps_cb, prefix, max_speed)
        # return ProgressFileWrapper(dst_file, callback)
        return ProgressFileWrapper(callback)

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

        if "content-length" not in response.headers:
            return False

        return int(response.headers.get("content-length")) > 0

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
        return home_drive + home_path

    def execute(self, cmd, **kwargs):
        """Execute a command optionally displaying the outputs."""

        verbose = kwargs.get("verbose", True)
        cwd = kwargs.get("cwd", None)
        env = kwargs.get("env", None)
        check = kwargs.get("check", True)
        outfile = kwargs.get("outfile", None)
        print_outputs = kwargs.get("print_outputs", True)
        output_buffer = kwargs.get("output_buffer", None)
        num_last_outputs = kwargs.get("num_last_outputs", 20)
        encoding = kwargs.get("encoding", "utf-8")
        check_call = kwargs.get("use_check_call", False)

        if check_call:
            # Simple mechanism with check_call usage:
            stdout = None if verbose else subprocess.DEVNULL
            stderr = None if verbose else subprocess.DEVNULL
            try:
                # logger.info("Check_call for %s...", cmd)
                subprocess.check_call(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env)
                return True, 0, None
            except subprocess.CalledProcessError as err:
                outputs = str(err).splitlines()
                return False, err.returncode, outputs

        # stdout = None if verbose else subprocess.DEVNULL
        # stderr = None if verbose else subprocess.DEVNULL
        stdout = subprocess.PIPE if verbose else subprocess.DEVNULL
        stderr = subprocess.PIPE if verbose else subprocess.DEVNULL

        # cf. https://stackoverflow.com/questions/31833897/
        # python-read-from-subprocess-stdout-and-stderr-separately-while-preserving-order
        def reader(pipe, queue, sid):
            """Reader function for a stream"""
            try:
                with pipe:
                    # Note: need to read the char one by one here, until we find a \r or \n value:
                    buf = b""

                    def readop():
                        return pipe.read(1)

                    for char in iter(readop, b""):
                        if char != b"\r":
                            buf += char

                        if char == b"\r" or char == b"\n":
                            queue.put((sid, buf))
                            buf = b""

                        # Add the carriage return on the new line:
                        if char == b"\r":
                            buf += char

                    # for line in iter(pipe.readline, b''):
                    #     queue.put((id, line))
            finally:
                queue.put(None)

        # Keep the latest outputs to report in case of error:
        lastest_outputs = collections.deque(maxlen=num_last_outputs)

        # logger.info("Executing command: %s", cmd)
        try:
            proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env, bufsize=0)
            if verbose:
                # cf. https://stackoverflow.com/questions/4374455/how-to-set-sys-stdout-encoding-in-python-3
                sys.stdout.reconfigure(encoding="utf-8")

                myq = Queue()
                Thread(target=reader, args=[proc.stdout, myq, 0]).start()
                Thread(target=reader, args=[proc.stderr, myq, 1]).start()
                for _ in range(2):
                    for _source, line in iter(myq.get, None):

                        try:
                            line = line.decode(encoding)
                        except UnicodeDecodeError:
                            try:
                                # line = line.decode("cp1252")
                                line = line.decode("cp850")
                            except UnicodeDecodeError:
                                logger.error("Unicode error on subprocess output line: %s", line)
                                continue

                        # Should not be needed here since we are not sending the '\n' character anyway:
                        # sline = line.strip()
                        sline = line
                        lastest_outputs.append(sline)
                        if print_outputs:
                            # print(f"{source}: {sline}")
                            # print(sline)
                            sys.stdout.write(sline)
                            sys.stdout.flush()
                        if output_buffer is not None:
                            output_buffer.append(sline)
                        if outfile is not None:
                            outfile.write(sline.replace("\r\n", "\n"))
                            outfile.flush()

            logger.debug("Waiting for subprocess to finish...")
            proc.wait()
            logger.debug("Returncode: %d", proc.returncode)

            if proc.returncode != 0 and check:
                if check:
                    msg = f"Subprocess terminated with error code {proc.returncode} (cmd={cmd})"
                    logger.error(msg)

                # This operation seems to be a failure, so we return the latest outputs:
                return False, proc.returncode, lastest_outputs

            return True, proc.returncode, None

        except subprocess.SubprocessError as err:
            logger.error("Error occured in subprocess for %s:\n%s", cmd, str(err))
            return False, None, lastest_outputs

        except PermissionError as err:
            logger.error(
                "PermissionError occured in subprocess for %s:\n%s\nkwargs=%s",
                cmd,
                str(err),
                kwargs,
            )
            return False, None, lastest_outputs

        except KeyboardInterrupt:
            logger.info("Interrupting subprocess...")
            os.kill(proc.pid, signal.SIGINT)

            logger.info("Waiting for subprocess to finish...")
            proc.wait()
            logger.info("Returncode: %d", proc.returncode)
            return True, proc.returncode, None

    def get_all_files(self, folder, exp=".*", recursive=False):
        """Get all the files matching a given pattern in a folder."""

        # prepare a pattern:
        p = re.compile(exp)
        num = len(folder) + 1
        if recursive:
            # Retrieve all files in a given folder recursively
            res = []
            # logDEBUG("Searching for files in %s" % folder)
            for root, _directories, filenames in os.walk(folder):
                # for directory in directories:
                #         print os.path.join(root, directory)
                for filename in filenames:
                    fname = os.path.join(root, filename)
                    if os.path.isfile(fname) and p.search(fname) is not None:
                        # logDEBUG("Found file: %s" % fname)
                        # We should remove the foldre prefix here:
                        res.append(fname[num:])
            return res
        else:
            return [
                f for f in os.listdir(folder) if (os.path.isfile(os.path.join(folder, f)) and p.search(f) is not None)
            ]

    def get_all_folders(self, folder, exp=".*", recursive=False):
        """Get all the folders matching a given pattern in a folder."""

        # prepare a pattern:
        p = re.compile(exp)
        num = len(folder) + 1
        if recursive:
            # Retrieve all files in a given folder recursively
            res = []
            # logDEBUG("Searching for files in %s" % folder)
            for root, directories, _filenames in os.walk(folder):
                # for directory in directories:
                #         print os.path.join(root, directory)
                for filename in directories:
                    fname = os.path.join(root, filename)
                    if os.path.isdir(fname) and p.search(fname) is not None:
                        # logDEBUG("Found file: %s" % fname)
                        # We should remove the foldre prefix here:
                        res.append(fname[num:])
            return res
        else:
            return [
                f for f in os.listdir(folder) if (os.path.isdir(os.path.join(folder, f)) and p.search(f) is not None)
            ]

    def prepend_env_list(self, paths, env, key="PATH"):
        """Add a list of paths to the environment PATH variable."""
        sep = ";" if self.is_windows else ":"

        if isinstance(paths, str):
            paths = [paths]

        dest_list = []
        if key in env:
            dest_list = env[key].split(sep)

        insert_idx = 0
        for elem in paths:
            subs = elem.split(sep)
            for path_elem in subs:
                if path_elem not in dest_list:
                    dest_list.insert(insert_idx, path_elem)
                    insert_idx += 1

        # logger.info("All paths in append_env_list: %s", all_paths)
        env[key] = sep.join(dest_list)
        return env

    def append_env_list(self, paths, env, key="PATH"):
        """Add a list of paths to the environment PATH variable."""
        sep = ";" if self.is_windows else ":"

        if isinstance(paths, str):
            paths = [paths]

        dest_list = []
        if key in env:
            dest_list = env[key].split(sep)

        for elem in paths:
            subs = elem.split(sep)
            for path_elem in subs:
                if path_elem not in dest_list:
                    dest_list.append(path_elem)

        # logger.info("All paths in append_env_list: %s", all_paths)
        env[key] = sep.join(dest_list)
        return env

    def get_online_content(self, url, timeout=20):
        """Get the content from a given URL"""
        logger.info("Sending request on %s...", url)
        response = requests.get(url, timeout=timeout)
        content = response.text

        return content

    # cf. https://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-filename
    def slugify(self, value, allow_unicode=False):
        """
        Taken from https://github.com/django/django/blob/master/django/utils/text.py
        Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
        dashes to single dashes. Remove characters that aren't alphanumerics,
        underscores, or hyphens. Convert to lowercase. Also strip leading and
        trailing whitespace, dashes, and underscores.
        """
        value = str(value)
        if allow_unicode:
            value = unicodedata.normalize("NFKC", value)
        else:
            value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^\w\s-]", "", value.lower())
        return re.sub(r"[-\s]+", "-", value).strip("-_")

    def make_get_request(
        self,
        url,
        params=None,
        timeout=None,
        max_retries=20,
        headers=None,
        retry_delay=0.1,
        **kwargs,
    ):
        """Make a get request"""

        status_codes = kwargs.get("status_codes", [200])

        count = 0
        while max_retries == 0 or count < max_retries:
            try:
                logger.debug("Sending request...")
                resp = requests.get(url, timeout=timeout, params=params, headers=headers)

                if resp is None:
                    count += 1
                    logger.error(
                        "No response received from get request to %s, retrying (%d/%d)...",
                        url,
                        count,
                        max_retries,
                    )
                    continue

                if resp.status_code not in status_codes:
                    count += 1
                    logger.error(
                        "Received bad status %d from get request to %s (params=%s): %s, retrying (%d/%d)...",
                        resp.status_code,
                        url,
                        params or "None",
                        resp.text,
                        count,
                        max_retries,
                    )
                    time.sleep(retry_delay)
                    continue

                return resp

            except (
                urllib3.exceptions.ReadTimeoutError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
            ):
                count += 1
                logger.error(
                    "Exception occured in get request to %s, retrying (%d/%d)...",
                    url,
                    count,
                    max_retries,
                )

        return None

    def make_post_request(
        self,
        url,
        data=None,
        timeout=None,
        max_retries=20,
        headers=None,
        retry_delay=0.1,
    ):
        """Make a post request"""

        count = 0
        while max_retries == 0 or count < max_retries:
            try:
                logger.debug("Sending request...")
                resp = requests.post(url, timeout=timeout, data=data, headers=headers)

                if resp is None:
                    count += 1
                    logger.error(
                        "No response received from post request to %s, retrying (%d/%d)...",
                        url,
                        count,
                        max_retries,
                    )
                    continue

                if resp.status_code != 200:
                    count += 1
                    logger.error(
                        "Received bad status %d from post request to %s (data=%s), retrying (%d/%d)...",
                        resp.status_code,
                        url,
                        data or "None",
                        count,
                        max_retries,
                    )
                    time.sleep(retry_delay)
                    continue

                return resp

            # note: could cache generic requests exception requests.exceptions.RequestException below.
            except (
                urllib3.exceptions.ReadTimeoutError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.Timeout,
            ):
                count += 1
                logger.error(
                    "Exception occured in post request to %s, retrying (%d/%d)...",
                    url,
                    count,
                    max_retries,
                )

        return None

    def fill_placeholders(self, content, hlocs):
        """Fill the placeholders in a given content"""
        if content is None:
            return None

        # If content is a list, then we process each element in the list:
        if isinstance(content, list):
            return [self.fill_placeholders(elem, hlocs) for elem in content]

        # If content is a dict, then we process each element in the dict:
        if isinstance(content, dict):
            return {key: self.fill_placeholders(elem, hlocs) for key, elem in content.items()}

        # Ignore non-strings:
        if not isinstance(content, str):
            return content

        for loc, rep in hlocs.items():
            if rep is None:
                logger.debug("Ignoring invalid replacement for %s in %s", loc, content)
                continue
            content = content.replace(loc, rep)

        return content
