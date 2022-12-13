"""Collection of tools utility functions"""
import logging
import os
import sys
import time

import requests
import urllib3

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return ToolsManager(ctx)


class ToolsManager(NVPComponent):
    """Tools command manager class"""

    def __init__(self, ctx: NVPContext):
        """Tools commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        base_dir = self.ctx.get_root_dir()
        self.tools_dir = self.get_path(base_dir, "tools", self.platform)

        self.tools = {}

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.setup_tools()
            self.initialized = True

    def setup_tools(self):
        """Setup all the tools on this platform."""
        # Prepare the tool paths:
        tools = self.config[f"{self.platform}_tools"]

        sep = "\\" if self.is_windows else "/"

        for desc in tools:
            tname = desc["name"]
            if "path" in desc:
                # logger.debug("Using system path '%s' for %s tool", desc['path'], tname)
                self.tools[tname] = {
                    "name": tname,
                    "path": desc["path"],
                }

                assert "sub_tools" not in desc, f"Cannot add sub tools from system tool desc {tname}"
            else:
                full_name = f"{tname}-{desc['version']}"
                install_path = self.get_path(self.tools_dir, full_name)
                tpath = self.get_path(install_path, desc["sub_path"])
                if not self.file_exists(tpath):

                    # retrieve the most appropriate source package for that tool:
                    pkg_file = self.retrieve_tool_package(desc)

                    # Extract the package:
                    self.extract_package(pkg_file, self.tools_dir, target_dir=full_name)

                    # CHeck if we have a post install command:
                    fname = f"_post_install_{desc['name']}_{self.platform}"
                    postinst = self.get_method(fname.lower())
                    if postinst is not None:
                        logger.info("Running post install for %s...", full_name)
                        postinst(install_path, desc)

                    # Remove the source package:
                    # self.remove_file(pkg_file)

                # The tool path should really exist now:
                assert self.file_exists(tpath), f"No valid package provided for {full_name}"

                # Store the tool path:
                tdesc = {
                    "base_path": install_path,
                    "sub_path": desc["sub_path"],
                    "path": tpath.replace("/", sep),
                    "name": tname,
                    "version": desc["version"],
                }
                self.tools[tname] = tdesc

                # Ensure the execution permission is set:
                self.add_execute_permission(tdesc["path"])

                # Check if we have sub_tools inside this tool folder:
                subs = desc.get("sub_tools", {})
                for sub_name, sub_path in subs.items():
                    sdesc = {
                        "base_path": install_path,
                        "sub_path": sub_path,
                        "name": sub_name,
                        "path": self.get_path(install_path, sub_path).replace("/", sep),
                    }
                    self.tools[sub_name] = sdesc
                    self.add_execute_permission(sdesc["path"])

    def retrieve_tool_package(self, desc):
        """Retrieve the most appropriate package for a given tool and
        store it in a local folder for extraction."""

        # Tool packages can be searched with "per tool" urls, of inside the package urls.
        # priority shoould be given to per "tool url" if available:

        urls = desc.get("urls", [])

        # Next we should extend with the package urls:
        full_name = f"{desc['name']}-{desc['version']}"

        # add support for ".7z" or ".tar.xz" archives:
        canonical_pkg_name = f"tools/{full_name}-{self.platform}"
        extensions = [".7z", ".tar.xz"]
        pkg_urls = self.config.get("package_urls", [])
        pkg_urls = [base_url + canonical_pkg_name + ext for base_url in pkg_urls for ext in extensions]

        if self.config.get("prioritize_package_urls", False):
            urls = pkg_urls + urls
        else:
            urls = urls + pkg_urls

        # Next we select the first valid URL:
        url = self.ctx.select_first_valid_path(urls)
        logger.info("Retrieving package for %s from url %s", full_name, url)

        filename = os.path.basename(url)

        # We download the file directly into the tools_dir as we don't want to
        tgt_pkg_path = self.get_path(self.tools_dir, filename)

        if not self.file_exists(tgt_pkg_path):
            # Download that file locally:
            self.download_file(url, tgt_pkg_path)
        else:
            logger.info("Using already downloaded package source %s", tgt_pkg_path)

        pkg_file = tgt_pkg_path
        logger.debug("Using source package %s for %s", pkg_file, full_name)

        return pkg_file

    def get_tool_desc(self, tname):
        """Retrieve the description dic for a given tool by name"""

        assert tname in self.tools, f"No tool desc available for '{tname}'."
        return self.tools[tname]

    def get_tool_path(self, tname):
        """Retrieve the path for a given tool"""
        desc = self.get_tool_desc(tname)
        return desc["path"]

    def get_tool_dir(self, tname):
        """Retrieve the parent directory for a given tool"""
        tpath = self.get_tool_path(tname)
        return self.get_parent_folder(tpath)

    def get_tool_root_dir(self, tname):
        """Retrieve the root directory where a given tool is installed."""
        desc = self.get_tool_desc(tname)
        return desc["base_path"]

    def get_tools_dir(self):
        """Retrieve the base tools directory"""
        return self.tools_dir

    def get_unzip_path(self):
        """Retrieve unzip tool path."""
        return self.get_tool_path("7zip")

    def get_cmake_path(self):
        """Retrieve cmake tool path."""
        return self.get_tool_path("cmake")

    def get_ninja_path(self):
        """Retrieve ninja tool path."""
        return self.get_tool_path("ninja")

    def get_git_path(self):
        """Retrieve git tool path."""
        return self.get_tool_path("git")

    def get_par2_path(self):
        """Retrieve par2 tool path."""
        return self.get_tool_path("par2")

    def process_cmd_path(self, cmd):
        """Re-implementation of the process_command method."""

        if cmd == "install":
            self.initialize()
            return True

        return False

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

    def download_file(self, url, dest_file, prefix="", max_speed=0, max_retries=20, timeout=6, headers=None):
        """Helper function used to download a file with progress report."""

        if url.startswith("git@"):
            logger.info("Checking out git repo %s...", url)
            cmd = [self.get_git_path(), "clone", "--progress", url, dest_file]
            self.execute(cmd)
            return True

        # Check if this is a valid local file:
        if self.file_exists(url):
            # Just copy the file in that case:
            logger.info("Copying file from %s...", url)
            self.copy_file(url, dest_file, True)
            return True

        logger.info("Downloading file from %s...", url)
        dlsize = 0
        count = 0

        mean_speed = 0
        speed_adapt = 0.001

        tmp_file = dest_file + ".download"

        while count < max_retries:
            try:
                logger.debug("Sending request...")
                response = requests.get(url, stream=True, timeout=timeout, headers=headers)

                logger.debug("Retrieving content-length.")
                total_length = response.headers.get("content-length")
                if total_length is None:
                    count += 1
                    logger.info("Detected invalid stream size for %s, retrying (%d/%d)...", url, count, max_retries)
                    time.sleep(1.0)
                    continue

                # if total_length is None:  # no content length header
                #     logger.info("Downloading file of unknown size.")
                #     dlsize += len(response.content)
                #     logger.info("Got %d bytes", dlsize)
                #     fdd.write(response.content)

                #     sys.stdout.write(f"\r Downloaded {dlsize} bytes (unknown total size)")
                #     sys.stdout.flush()
                # else:

                logger.debug("Total file length is: %s", total_length)
                total_length = int(total_length)
                last_time = time.time()

                with open(tmp_file, "wb") as fdd:
                    for data in response.iter_content(chunk_size=4096):
                        nbytes = len(data)

                        cur_time = time.time()
                        elapsed = cur_time - last_time
                        last_time = cur_time
                        if elapsed > 0.0:
                            # cur speed in kbytes/secs
                            cur_speed = nbytes / (1024 * elapsed)
                            mean_speed += (cur_speed - mean_speed) * speed_adapt

                        dlsize += nbytes

                        # Compute the estimated remaining time:
                        remaining_size = total_length - dlsize
                        remaining_time = remaining_size / (1024.0 * mean_speed) if mean_speed > 0 else None
                        time_str = self.get_time_string(remaining_time)

                        fdd.write(data)
                        frac = dlsize / total_length
                        done = int(50 * frac)
                        sys.stdout.write(
                            f"\r{prefix}[{'=' * done}{' ' * (50-done)}] {dlsize}/{total_length} {frac*100:.3f}% @ {mean_speed:.0f}KB/s ETA: {time_str}"
                        )
                        sys.stdout.flush()
                        if max_speed > 0:
                            # We should take a speed limit into consideration here:

                            # we downloaded nbytes in elapsed seconds
                            # and we have the limit of max_speed bytes per seconds.
                            # Compute how long we should take to download nbytes in seconds:
                            dl_dur = nbytes / max_speed
                            if elapsed < dl_dur:
                                # We took less time than the requirement so far, so we should speed
                                # for the remaining time:
                                time.sleep(dl_dur - elapsed)
                                last_time = time.time()

                    sys.stdout.write("\n")
                    sys.stdout.flush()

                # The file was completely downloaded
                # So we can rename it:
                self.rename_file(tmp_file, dest_file)
                return True

            except (
                urllib3.exceptions.ReadTimeoutError,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
            ):
                count += 1
                logger.error("Exception occured while downloading %s, retrying (%d/%d)...", url, count, max_retries)
                self.remove_file(tmp_file)
                # Reset the dl size:
                dlsize = 0
                # self.remove_file(dest_file)

        logger.error("Cannot download file from %s in %d retries", url, max_retries)
        return False

    def unzip_package(self, src_pkg_path, dest_dir, target_name=None):
        """Unzip a package"""

        # check if this is a tar.xz archive:
        if src_pkg_path.endswith(".tar.xz"):
            cmd = ["tar", "-xvJf", src_pkg_path, "-C", dest_dir]
        elif src_pkg_path.endswith(".tar.gz") or src_pkg_path.endswith(".tgz"):
            cmd = ["tar", "-xvzf", src_pkg_path, "-C", dest_dir]
        elif src_pkg_path.endswith(".7z.exe"):
            if target_name is None:
                target_name = self.remove_file_extension(os.path.basename(src_pkg_path))
            cmd = [self.get_unzip_path(), "x", "-o" + dest_dir + "/" + target_name, src_pkg_path]
        else:
            cmd = [self.get_unzip_path(), "x", "-o" + dest_dir, src_pkg_path]
        self.execute(cmd, verbose=self.settings["verbose"])

    def extract_package(self, src_pkg_path, dest_dir, target_dir=None, extracted_dir=None):
        """Extract source package into the target dir folder."""

        logger.info("Extracting %s...", src_pkg_path)

        # check what is our expected extracted name:
        cur_name = self.remove_file_extension(os.path.basename(src_pkg_path))

        target_name = cur_name if target_dir is None else target_dir
        src_name = cur_name if extracted_dir is None else extracted_dir
        dst_dir = self.get_path(dest_dir, target_name)
        src_dir = self.get_path(dest_dir, src_name)

        # Ensure that the destination/source folders do not exists:
        assert not self.path_exists(dst_dir), f"Unexpected existing path: {dst_dir}"
        assert not self.path_exists(src_dir), f"Unexpected existing path: {src_dir}"

        self.unzip_package(src_pkg_path, dest_dir, target_name)
        # self.execute(cmd, True)

        # Check if renaming is necessary:
        if not self.path_exists(dst_dir):
            assert self.path_exists(src_dir), f"Missing extracted path {src_dir}"
            logger.debug("Renaming folder %s to %s", src_name, target_name)
            self.rename_folder(src_dir, dst_dir)

        logger.debug("Done extracting package.")

    def create_package(self, src_path, dest_folder, package_name):
        """Create an archive package given a source folder, destination folder
        and name for the zip file to create"""
        # 7z a -t7z -m0=lzma2 -mx=9 -aoa -mfb=64 -md=32m -ms=on -d=1024m -r

        # Note: we only create the package if the source folder exits:
        if not self.path_exists(src_path):
            logger.warning("Cannot create package: invalid source path: %s", src_path)
            return False

        dest_file = self.get_path(dest_folder, package_name)

        # Check if we should create a tar.xz here:
        if package_name.endswith(".tar.xz"):
            # Generate a tar.xz:
            cmd = ["tar", "cJf", dest_file, "-C", self.get_parent_folder(src_path), self.get_filename(src_path)]
        else:
            # Generate a 7zip package:
            cmd = [
                self.get_unzip_path(),
                "a",
                "-t7z",
                dest_file,
                src_path,
                "-m0=lzma2",
                "-mx=9",
                "-aoa",
                "-mfb=64",
                "-ms=on",
                "-mmt=2",
                "-r",
            ]
            # "-md=32m",

        self.execute(cmd, verbose=self.settings["verbose"])
        logger.debug("Done generating package %s", package_name)
        return True

    def _post_install_git_windows(self, install_path, _desc):
        """Run post install for portable git on windows"""

        # There should be a "post-install.bat" script in the install folder:
        sfile = self.get_path(install_path, "post-install.bat")
        assert self.file_exists(sfile), "No post-install.bat script found."

        # We should not delete that file automatically at this end of it,
        # as this would trigger an error:
        self.replace_in_file(sfile, "@DEL post-install.bat", "")

        cmd = [
            self.get_path(install_path, "git-cmd.exe"),
            "--no-needs-console",
            "--hide",
            "--no-cd",
            "--command=post-install.bat",
        ]

        logger.info("Executing command: %s", cmd)
        self.execute(cmd, cwd=install_path, verbose=True)

        # Finally we remove the script file:
        self.remove_file(sfile)

        # here we should also ensure that we have a global .gitconfig file registered for our user:
        git = self.get_component("git")
        git.setup_global_config()

    def create_par2_archives(self, src_path, redundancy=10, nblocks=3000):
        """Create a PAR2 archive from a given source path."""

        pdir = self.get_parent_folder(src_path)
        fname = self.get_filename(src_path)

        # Ensure we have int values:
        redundancy = int(redundancy)
        nblocks = int(nblocks)

        par2 = self.get_par2_path()
        if self.is_windows:
            cmd = [par2, "c", f"/sn{nblocks}", f"/rr{redundancy}", "/rd2", f"{fname}.par2", fname]
        else:
            cmd = [par2, "c", f"-b{nblocks}", f"-r{redundancy}", f"{fname}.par2", fname]

        logger.info("Executing command %s", cmd)
        self.execute(cmd, verbose=True, cwd=pdir)
        logger.info("Done creating par archives.")


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("tools")

    context.define_subparsers("main", ["install"])

    comp.run()
