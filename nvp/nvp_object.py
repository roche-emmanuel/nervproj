"""NVP base object class"""
import configparser

# import traceback
import logging
import os
import stat
import pprint
import time
import unicodedata
import re
import threading
import sys
import subprocess
import shutil
import collections
from threading import Thread
from queue import Queue
import signal
import json
import urllib
from datetime import date, datetime
import jstyleson
import requests
import xxhash
import urllib3

logger = logging.getLogger(__name__)

printer = pprint.PrettyPrinter(indent=2)


class NVPCheckError(Exception):
    """Basic class representing an NVP exception."""


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

                            logger.error("Exception %s occured in safe block (trial %d/%d)",
                                         ecls.__name__, count, retries)

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

    def compute_file_hash(self, fpath, blocksize=65536):
        """Compute the hash for a given file path"""
        # cf. https://www.programcreek.com/python/example/111324/xxhash.xxh64
        hasher = xxhash.xxh64()
        with open(fpath, 'rb') as file:
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

        shutil.move(src_path, dest_path)

    def rename_folder(self, src_path, dest_path, create_parent=False):
        """Rename a folder"""
        self.move_path(src_path, dest_path, create_parent=create_parent)

    def rename_file(self, src_path, dest_path, create_parent=False):
        """Rename a file"""
        self.move_path(src_path, dest_path, create_parent=create_parent)

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

    def copy_folder(self, src_folder, dst_folder):
        """Copy a source folder to a destination folder."""
        shutil.copytree(src_folder, dst_folder)

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
        encoding = kwargs.get("encoding", 'utf-8')

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
                    buf = b''

                    def readop():
                        return pipe.read(1)

                    for char in iter(readop, b''):
                        if char != b'\r':
                            buf += char

                        if char == b'\r' or char == b'\n':
                            queue.put((sid, buf))
                            buf = b''

                        # Add the carriage return on the new line:
                        if char == b'\r':
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
                myq = Queue()
                Thread(target=reader, args=[proc.stdout, myq, 0]).start()
                Thread(target=reader, args=[proc.stderr, myq, 1]).start()
                for _ in range(2):
                    for _source, line in iter(myq.get, None):
                        try:
                            line = line.decode(encoding)
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
                            outfile.write(sline+'\n')
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
            value = unicodedata.normalize('NFKC', value)
        else:
            value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower())
        return re.sub(r'[-\s]+', '-', value).strip('-_')

    def make_get_request(self, url, params=None, timeout=None, max_retries=20, headers=None, retry_delay=0.1, **kwargs):
        """Make a get request"""

        status_codes = kwargs.get("status_codes", [200])

        count = 0
        while max_retries == 0 or count < max_retries:
            try:
                logger.debug("Sending request...")
                resp = requests.get(url, timeout=timeout, params=params, headers=headers)

                if resp is None:
                    count += 1
                    logger.error("No response received from get request to %s, retrying (%d/%d)...",
                                 url, count, max_retries)
                    continue

                if resp.status_code not in status_codes:
                    count += 1
                    logger.error("Received bad status %d from get request to %s (params=%s): %s, retrying (%d/%d)...",
                                 resp.status_code, url, params or "None", resp.text, count, max_retries)
                    time.sleep(retry_delay)
                    continue

                return resp

            except (urllib3.exceptions.ReadTimeoutError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout):
                count += 1
                logger.error("Exception occured in get request to %s, retrying (%d/%d)...", url, count, max_retries)

        return None

    def make_post_request(self, url, data=None, timeout=None, max_retries=20, headers=None, retry_delay=0.1):
        """Make a post request"""

        count = 0
        while max_retries == 0 or count < max_retries:
            try:
                logger.debug("Sending request...")
                resp = requests.post(url, timeout=timeout, data=data, headers=headers)

                if resp is None:
                    count += 1
                    logger.error("No response received from post request to %s, retrying (%d/%d)...",
                                 url, count, max_retries)
                    continue

                if resp.status_code != 200:
                    count += 1
                    logger.error("Received bad status %d from post request to %s (data=%s), retrying (%d/%d)...",
                                 resp.status_code, url, data or "None", count, max_retries)
                    time.sleep(retry_delay)
                    continue

                return resp

            # note: could cache generic requests exception requests.exceptions.RequestException below.
            except (urllib3.exceptions.ReadTimeoutError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout):
                count += 1
                logger.error("Exception occured in post request to %s, retrying (%d/%d)...", url, count, max_retries)

        return None

    def fill_placeholders(self, content, hlocs):
        """Fill the placeholders in a given content"""
        if content is None:
            return None

        for loc, rep in hlocs.items():
            content = content.replace(loc, rep)

        return content
