"""Collection of tools utility functions"""
import os
import sys
import logging
import requests

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = ToolsManager(ctx)
    ctx.register_component('tools', comp)


class ToolsManager(NVPComponent):
    """Tools command manager class"""

    def __init__(self, ctx: NVPContext):
        """Tools commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        base_dir = self.ctx.get_root_dir()
        self.tools_dir = self.get_path(base_dir, "tools", self.platform)

        self.tools = {}

        desc = {
            "tools": {"install": None},
        }
        ctx.define_subparsers("main", desc)

    def initialize(self):
        """Initialize this component as needed before usage."""
        if self.initialized is False:
            self.setup_tools()
            self.initialized = True

    def setup_tools(self):
        """Setup all the tools on this platform."""
        # Prepare the tool paths:
        tools = self.config[f'{self.platform}_tools']

        sep = "\\" if self.ctx.is_windows() else "/"

        for desc in tools:
            tname = desc['name']
            if 'path' in desc:
                # logger.debug("Using system path '%s' for %s tool", desc['path'], tname)
                self.tools[tname] = {
                    'name': tname,
                    'path': desc['path'],
                }

                assert 'sub_tools' not in desc, f"Cannot add sub tools from system tool desc {tname}"
            else:
                full_name = f"{tname}-{desc['version']}"
                install_path = self.get_path(self.tools_dir, full_name)
                tpath = self.get_path(install_path, desc['sub_path'])
                if not self.file_exists(tpath):

                    # retrieve the most appropriate source package for that tool:
                    pkg_file = self.retrieve_tool_package(desc)

                    # Extract the package:
                    self.extract_package(pkg_file, self.tools_dir, rename=full_name)

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
                    'base_path': install_path,
                    'path': tpath.replace("/", sep),
                    'name': tname,
                    'version': desc['version'],
                }
                self.tools[tname] = tdesc

                # Ensure the execution permission is set:
                self.add_execute_permission(tdesc['path'])

                # Check if we have sub_tools inside this tool folder:
                subs = desc.get('sub_tools', {})
                for sub_name, sub_path in subs.items():
                    sdesc = {
                        'base_path': install_path,
                        'name': sub_name,
                        'path': self.get_path(install_path, sub_path).replace("/", sep)
                    }
                    self.tools[sub_name] = sdesc
                    self.add_execute_permission(sdesc['path'])

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
        pkg_urls = [base_url+canonical_pkg_name+ext for base_url in pkg_urls for ext in extensions]

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
        return desc['path']

    def get_tools_dir(self):
        """Retrieve the base tools directory"""
        return self.tools_dir

    def get_unzip_path(self):
        """Retrieve unzip tool path."""
        return self.get_tool_path('7zip')

    def get_cmake_path(self):
        """Retrieve xmake tool path."""
        return self.get_tool_path('cmake')

    def get_git_path(self):
        """Retrieve git tool path."""
        return self.get_tool_path('git')

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 == 'tools':
            cmd1 = self.ctx.get_command(1)
            if cmd1 == "install":
                self.initialize()

            return True

        return False

    def download_file(self, url, dest_file):
        """Helper function used to download a file with progress report."""

        if url.startswith("git@"):
            logger.info("Checking out git repo %s...", url)
            cmd = [self.get_git_path(), "clone", url, dest_file]
            self.execute(cmd)
            return

        # Check if this is a valid local file:
        if self.file_exists(url):
            # Just copy the file in that case:
            logger.info("Copying file from %s...", url)
            self.copy_file(url, dest_file, True)
            return

        logger.info("Downloading file from %s...", url)
        with open(dest_file, "wb") as fdd:
            response = requests.get(url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                fdd.write(response.content)
            else:
                dlsize = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dlsize += len(data)
                    fdd.write(data)
                    frac = dlsize / total_length
                    done = int(50 * frac)
                    sys.stdout.write(f"\r[{'=' * done}{' ' * (50-done)}] {dlsize}/{total_length} {frac*100:.3f}%")
                    sys.stdout.flush()

                sys.stdout.write('\n')
                sys.stdout.flush()

    def extract_package(self, src_pkg_path, dest_dir, rename=None):
        """Extract source package into the target dir folder."""

        logger.info("Extracting %s...", src_pkg_path)

        # check what is our expected extracted name:
        cur_name = self.remove_file_extension(os.path.basename(src_pkg_path))

        expected_name = cur_name if rename is None else rename
        dst_dir = self.get_path(dest_dir, expected_name)
        src_dir = self.get_path(dest_dir, cur_name)

        # Ensure that the destination/source folders do not exists:
        assert not self.path_exists(dst_dir), f"Unexpected existing path: {dst_dir}"
        assert not self.path_exists(src_dir), f"Unexpected existing path: {src_dir}"

        # check if this is a tar.xz archive:
        if src_pkg_path.endswith(".tar.xz"):
            cmd = ["tar", "-xvJf", src_pkg_path, "-C", dest_dir]
        elif src_pkg_path.endswith(".tar.gz") or src_pkg_path.endswith(".tgz"):
            cmd = ["tar", "-xvzf", src_pkg_path, "-C", dest_dir]
        elif src_pkg_path.endswith(".7z.exe"):
            cmd = [self.get_unzip_path(), "x", "-o"+dest_dir+"/"+expected_name, src_pkg_path]
        else:
            cmd = [self.get_unzip_path(), "x", "-o"+dest_dir, src_pkg_path]
        self.execute(cmd, self.settings['verbose'])

        # Check if renaming is necessary:
        if not self.path_exists(dst_dir):
            assert self.path_exists(src_dir), f"Missing extracted path {src_dir}"
            logger.debug("Renaming folder %s to %s", cur_name, rename)
            self.rename_folder(src_dir, dst_dir)

        logger.debug("Done extracting package.")

    def _post_install_git_windows(self, install_path, _desc):
        """Run post install for portable git on windows"""

        # There should be a "post-install.bat" script in the install folder:
        sfile = self.get_path(install_path, "post-install.bat")
        assert self.file_exists(sfile), "No post-install.bat script found."

        # We should not delete that file automatically at this end of it,
        # as this would trigger an error:
        self.replace_in_file(sfile, "@DEL post-install.bat", "")

        cmd = [self.get_path(install_path, "git-cmd.exe"), "--no-needs-console",
               "--hide", "--no-cd", "--command=post-install.bat"]

        logger.info("Executing command: %s", cmd)
        self.execute(cmd, cwd=install_path, verbose=True)

        # Finally we remove the script file:
        self.remove_file(sfile)

        # here we should also ensure that we have a global .gitconfig file registered for our user:
        git = self.get_component('git')
        git.setup_global_config()