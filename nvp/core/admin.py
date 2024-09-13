"""Collection of admin utility functions"""

import glob
import logging
import os
import sys

import numpy as np
from PIL import Image

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return AdminManager(ctx)


class AdminManager(NVPComponent):
    """Admin command manager class"""

    def __init__(self, ctx: NVPContext):
        """Admin commands manager constructor"""
        NVPComponent.__init__(self, ctx)

    def install_cli(self):
        """Install a CLI script in .bashrc if application"""

        # Check if an $HOME folder is provider:
        home_dir = os.getenv("HOME")
        if home_dir is None:
            logger.error("Cannot install cli alias: no $HOME environment variable detected.")
            return

        logger.info("Home folder is: %s", home_dir)

        # Check if we have a .bashrc file in that folder:
        bashrc_file = self.get_path(home_dir, ".bashrc")
        if not self.file_exists(bashrc_file):
            logger.warning("Cannot install cli alias: no .bashrc file in HOME folder.")
            return

        script_path = self.get_path(self.ctx.get_root_dir(), "cli.sh")

        # If we are on windows, we may want to convert this path to a cygwin path
        # if we are in a cygwin environment (but running the native python executable):
        if self.is_windows:
            script_path = self.to_cygwin_path(script_path)
            assert script_path is not None, "Invalid cygwin environment."

        sline = f'\n[ -f "{script_path}" ] && source "{script_path}"\n'

        # Check if this string is already in the bashrc file:
        content = self.read_text_file(bashrc_file)

        if content.find(sline) == -1:
            # We should add the string:
            logger.info("Adding source file in .bashrc for NervProj")

            # Make a backup of the file:
            self.copy_file(bashrc_file, bashrc_file + ".bak", force=True)
            self.write_text_file(content + sline, bashrc_file, newline="\n")
        else:
            logger.info("NervProj setup file already referenced in .bashrc")

        # pp = pprint.PrettyPrinter(indent=2)
        # res = pp.pformat(dict(os.environ))
        # logger.info("Current environment is: %s", res)

    def install_python_requirements(self):
        """Install the requirements for the main python environment using pip"""

        logger.info("Upgrading pip...")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--no-warn-script-location"]
        self.execute(cmd)

        logger.info("Installing python requirements...")
        reqfile = self.get_path(self.ctx.get_root_dir(), "tools/requirements.txt")
        cmd = [sys.executable, "-m", "pip", "install", "-r", reqfile, "--no-warn-script-location"]
        # logger.info("Executing command: %s", cmd)
        self.execute(cmd)
        logger.info("Done installing python requirements.")

    def install_repository_bootstrap(self):
        """Install the bootstraped repository for this NervProj folder if not present already."""

        base_dir = self.ctx.get_root_dir()
        if self.dir_exists(base_dir, ".git"):
            logger.info(".git folder already exists, bootstrapping ignored.")
            return

        # We need to bootstrap in a temp folder:
        git = self.get_component("git")

        url = self.config["repository_url"]

        dest_dir = self.get_path(base_dir, "temp", "nervproj")
        logger.info("Cloning NervProj folder into %s...", dest_dir)
        git.clone_repository(url, dest_dir)

        # When cloning is done we should move the .git folder from the clone location into our root
        self.move_path(self.get_path(dest_dir, ".git"), self.get_path(base_dir, ".git"))

        # And finally we remove the remaining files:
        self.remove_folder(dest_dir)

        logger.info("Done bootstrapping NervProj project.")

    def setup_global_vscode_config(self, config_dir=None):
        """Setup global Visual studio code user settings"""

        if config_dir is None:
            # * on windows: in C:/Users/kenshin/AppData/Roaming/Code/User/settings.json
            # => should use os.getenv('APPDATA')
            # * on linux: in /home/kenshin/.config/Code/User/settings.json
            if self.is_windows:
                base_dir = os.getenv("APPDATA")
            else:
                base_dir = self.get_path(self.ctx.get_home_dir(), ".config")

            config_dir = self.get_path(base_dir, "Code", "User")

        cfg_file = self.get_path(config_dir, "settings.json")

        config = {}
        ref_config = None

        if not self.file_exists(cfg_file):
            # Ensure the folder exists:
            self.make_folder(config_dir)
        else:
            # Read the config:
            config = self.read_json(cfg_file)
            # Keep a copy to compare the changes:
            ref_config = self.read_json(cfg_file)

        # Now write the changes we want:
        tools = self.get_component("tools")

        config["git.path"] = tools.get_git_path()
        config["python.linting.pylintEnabled"] = True
        config["python.linting.enabled"] = True
        config["python.linting.pylintPath"] = tools.get_tool_path("pylint")
        config["python.linting.pylintArgs"] = [
            "--max-line-length=120",
            "--good-names=i,j,k,ex,Run,_,x,y,z,w,t,dt",
            "--good-names-rgxs=[a-z][0-9]$",
        ]
        config["python.defaultInterpreterPath"] = tools.get_tool_path("python")
        config["python.formatting.autopep8Path"] = tools.get_tool_path("autopep8")
        config["python.formatting.provider"] = "autopep8"
        config["python.formatting.autopep8Args"] = ["--max-line-length=120", "--experimental"]
        config["editor.formatOnSave"] = True
        config["cmakeFormat.exePath"] = tools.get_tool_path("cmake_format")

        if ref_config is None or config != ref_config:
            logger.info("Wrtting updated vscode settings in %s", cfg_file)
            self.write_json(config, cfg_file)
        else:
            logger.info("No change in %s", cfg_file)

    def init_project_config(self, proj_dir, proj_name):
        """Setup initial project local config elements"""
        config_dir = self.get_path(proj_dir, ".vscode")

        cfg_file = self.get_path(config_dir, "settings.template.json")
        self.make_folder(config_dir)

        # Location of the template files:
        template_dir = self.get_path(self.ctx.get_root_dir(), "assets", "templates")

        config = {}
        ref_config = None

        # Check if we should provide a python environment in this project:
        with_py = self.get_param("with_py_env", False)

        if with_py:
            logger.info("Setting up dedicated python env for %s", proj_name)

        if self.file_exists(cfg_file):
            # Read the config:
            config = self.read_json(cfg_file)
            # Keep a copy to compare the changes:
            ref_config = self.read_json(cfg_file)

        config["python.envFile"] = "${workspaceFolder}/.vs_env"

        ignore_elems = []

        if with_py:
            # We deploy the python packages:
            dest_dir = self.get_path(proj_dir, "tools", "packages")
            self.make_folder(dest_dir)
            # get the python version on windows:
            py_vers = {}
            sevenzip_vers = {}

            for plat_name in ["windows", "linux"]:
                for el in self.config[f"{plat_name}_tools"]:
                    if el["name"] == "python":
                        py_vers[plat_name] = el["version"]
                    if el["name"] == "7zip":
                        sevenzip_vers[plat_name] = el["version"]

            for plat_name, py_version in py_vers.items():
                for ext in [".7z", ".tar.xz"]:
                    file_name = f"python-{py_version}-{plat_name}{ext}"
                    src_file = self.get_path(self.ctx.get_root_dir(), "tools", "packages", file_name)
                    dst_file = self.get_path(dest_dir, file_name)
                    if self.file_exists(src_file) and not self.file_exists(dst_file):
                        logger.info("Adding package file %s", dst_file)
                        self.copy_file(src_file, dst_file)

            # more updates to vscode settings if we have a dedicated python env:
            cur_py_vers = py_vers[self.platform]

            ext = ".exe" if self.is_windows else ""

            config["python.defaultInterpreterPath"] = (
                f"${{workspaceFolder}}/tools/{self.platform}/python-{cur_py_vers}/python{ext}"
            )

            config["python.linting.enabled"] = True

            config["python.linting.flake8Enabled"] = True
            config["python.linting.flake8Path"] = (
                f"${{workspaceFolder}}/tools/{self.platform}/python-{cur_py_vers}/Scripts/flake8{ext}"
            )
            config["python.linting.flake8Args"] = [
                "--max-line-length=120",
                "--ignore=E203,W503",
                '--per-file-ignores="__init__.py:F401"',
            ]

            config["python.linting.pylintEnabled"] = True
            config["python.linting.pylintPath"] = (
                f"${{workspaceFolder}}/tools/{self.platform}/python-{cur_py_vers}/Scripts/pylint{ext}"
            )
            config["python.linting.pylintArgs"] = [
                "--max-line-length=120",
                "--good-names=i,j,k,ex,Run,_,x,y,z,w,t,dt",
                "--good-names-rgxs=[a-z][0-9]$",
            ]

            config["//python.formatting.provider"] = "autopep8"
            config["//python.formatting.autopep8Path"] = (
                f"${{workspaceFolder}}/tools/{self.platform}/python-{cur_py_vers}/Scripts/autopep8{ext}"
            )
            config["//python.formatting.autopep8Args"] = ["--max-line-length=120", "--experimental"]
            config["python.formatting.provider"] = "black"
            config["python.formatting.blackPath"] = (
                f"${{workspaceFolder}}/tools/{self.platform}/python-{cur_py_vers}/Scripts/black{ext}"
            )
            config["python.formatting.blackArgs"] = ["--line-length", "120"]

            config["python.sortImports.path"] = (
                f"${{workspaceFolder}}/tools/{self.platform}/python-{cur_py_vers}/Scripts/isort{ext}"
            )
            config["python.sortImports.args"] = ["--profile", "black"]
            config["[python]"] = {"editor.codeActionsOnSave": {"source.organizeImports": True}}

            config["editor.formatOnSave"] = True

            # Next, for the windows part we need to deploy the 7zip package too:
            folder_name = f"7zip-{sevenzip_vers['windows']}"
            src_folder = self.get_path(self.ctx.get_root_dir(), "tools", "windows", folder_name)
            dst_folder = self.get_path(proj_dir, "tools", "windows", folder_name)
            if not self.dir_exists(dst_folder):
                logger.info("Adding windows 7zip package at %s", dst_folder)
                self.copy_folder(src_folder, dst_folder)

            # Update the ignore elements:
            ignore_elems += [
                "",
                "# Ignore all the windows tools except the 7zip folder:",
                "tools/windows/*",
                "!tools/windows/7zip-*",
                "tools/linux/*",
            ]

            # Should also install an requirements.txt file:
            dest_file = self.get_path(proj_dir, "tools", "requirements.txt")
            if not self.file_exists(dest_file):
                logger.info("Installing pythong requirements file.")
                content = [
                    "# List here all the required python packages",
                    "# Then call cli.{sh/bat} --install-py-reqs",
                    "",
                    "black",
                    "flake8",
                    "isort",
                    "pylint",
                    "#autopep8",
                    "",
                ]
                content = "\n".join(content)
                self.write_text_file(content, dest_file)

            # Should install the cli script files:
            dest_file = self.get_path(proj_dir, "cli.py")
            if not self.file_exists(dest_file):
                logger.info("Writting cli python file %s", dest_file)
                content = self.read_text_file(template_dir, "cli.py.tpl")
                self.write_text_file(content, dest_file)

            dest_file = self.get_path(proj_dir, "cli.sh")
            if not self.file_exists(dest_file):
                logger.info("Writting cli shell file %s", dest_file)
                content = self.read_text_file(template_dir, "cli.sh.tpl")
                content = content.replace("${PROJ_NAME}", proj_name.lower())
                # Use the linux python version below:
                content = content.replace("${PY_VERSION}", py_vers["linux"])
                self.write_text_file(content, dest_file, newline="\n")

            dest_file = self.get_path(proj_dir, "cli.bat")
            if not self.file_exists(dest_file):
                logger.info("Writting cli batch file %s", dest_file)
                content = self.read_text_file(template_dir, "cli.bat.tpl")
                content = content.replace("${PROJ_NAME}", proj_name.upper())
                # Use the windows versionq below:
                content = content.replace("${PY_VERSION}", py_vers["windows"])
                content = content.replace("${ZIP_VERSION}", sevenzip_vers["windows"])
                self.write_text_file(content, dest_file)

        # Finish writting the vscode config:
        if ref_config is None or config != ref_config:
            logger.info("Wrtting updated vscode settings in %s", cfg_file)
            self.write_json(config, cfg_file)
        else:
            logger.info("No change in %s", cfg_file)

        # Also copy to actuall settings if we don't have the file yet:
        cfg_file2 = self.get_path(config_dir, "settings.json")
        if not self.file_exists(cfg_file2):
            logger.info("Copyging VSCode settings template to %s", cfg_file2)
            self.copy_file(cfg_file, cfg_file2)

        # Write the env file if needed:
        dest_file = self.get_path(proj_dir, ".vs_env")
        if not self.file_exists(dest_file):
            logger.info("Writting python env file %s", dest_file)
            content = self.read_text_file(template_dir, "vs_env.tpl")
            sep = ";" if self.is_windows else ":"
            content = content.replace("${NVP_ROOT_DIR}", "" if with_py else self.ctx.get_root_dir())
            content = content.replace("${SEP}", "" if with_py else sep)
            self.write_text_file(content, dest_file)

        # and write a .editorconfig file:
        dest_file = self.get_path(proj_dir, ".editorconfig")
        if not self.file_exists(dest_file):
            logger.info("Writting editor config file %s", dest_file)
            content = self.read_text_file(template_dir, "editorconfig.tpl")
            self.write_text_file(content, dest_file)

        # and write a .gitignore file:
        dest_file = self.get_path(proj_dir, ".gitignore")
        if not self.file_exists(dest_file):
            logger.info("Writting .gitignore file %s", dest_file)
            content = self.read_text_file(template_dir, "gitignore.tpl")
            content += "\n".join(ignore_elems)
            content += "\n"
            self.write_text_file(content, dest_file)

        # and write a .gitattributes file:
        dest_file = self.get_path(proj_dir, ".gitattributes")
        if not self.file_exists(dest_file):
            logger.info("Writting .gitattributes file %s", dest_file)
            content = self.read_text_file(template_dir, "gitattributes.tpl")
            self.write_text_file(content, dest_file)

        # write a nvp_config.json file:
        # dest_file = self.get_path(proj_dir, "nvp_config.json")
        # if not self.file_exists(dest_file):
        #     logger.info("Writting nvp_config.json file %s", dest_file)
        #     content = self.read_text_file(template_dir, "nvp_config.json.tpl")
        #     self.write_text_file(content, dest_file)

        # write a nvp_plug.py file:
        # dest_file = self.get_path(proj_dir, "nvp_plug.py")
        # if not self.file_exists(dest_file):
        #     logger.info("Writting nvp_plug.py file %s", dest_file)
        #     content = self.read_text_file(template_dir, "nvp_plug.py.tpl")
        #     content = content.replace("${PROJ_NAME}", proj_name)
        #     self.write_text_file(content, dest_file)

        # Add pull rebase = false to .git/config
        cfg_file = self.get_path(proj_dir, ".git", "config")
        assert self.file_exists(cfg_file), f"Cannot fine git config file at {cfg_file}"
        # Load that config:
        config = self.read_ini(cfg_file)
        save_needed = False

        if "pull" not in config:
            logger.info("Adding pull section in git config.")
            config["pull"] = {
                "rebase": "false",
            }
            save_needed = True
        else:
            pull = config["pull"]
            if pull["rebase"] != "false":
                logger.info("Updating git pull rebase from %s to %s", pull["rebase"], "false")
                pull["rebase"] = "false"
                save_needed = True

        if save_needed:
            self.write_ini(config, cfg_file)

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "install.cli":
            self.install_cli()
            return True

        if cmd == "install.reqs":
            self.install_python_requirements()
            return True

        if cmd == "install.repo":
            self.install_repository_bootstrap()
            return True

        if cmd == "init":
            self.setup_global_vscode_config()
            proj_name = self.get_param("project_name")

            if proj_name is not None:
                proj = self.ctx.get_project(proj_name)
            else:
                # Find the current project given our location:
                proj = self.ctx.get_current_project(True)

            # Doing some bootstrapping here:
            # we are not accepting none project anymore:
            self.check(proj is not None, "Cannot resolve the current project from cwd.")

            proj_dir = proj.get_root_dir()

            # proj_dir = proj.get_root_dir() if proj is not None else self.ctx.get_root_dir()
            # proj_name = proj.get_name(False) if proj is not None else "NervProj"
            self.init_project_config(proj_dir, proj_name)
            return True

        if cmd == "create-par2":
            files = self.get_param("input_files")
            redundancy = self.get_param("redundancy")
            nblocks = self.get_param("num_blocks")
            solid = self.get_param("solid", False)
            out_name = self.get_param("out_name")

            self.create_par2(files, redundancy, nblocks, solid, out_name)
            return True

        if cmd == "gen-cert":
            root_cert = self.get_param("root_cert")
            out_name = self.get_param("out_name")
            common_name = self.get_param("name")
            self.generate_certificate(out_name, common_name, root_cert)
            return True

        if cmd == "json-to-yaml":
            input_file = self.get_param("input_file")
            sort_keys = self.get_param("sort_keys")
            self.json_to_yaml(input_file, sort_keys)
            return True

        if cmd == "compare-folders":
            input_folder = self.get_param("input_folder")
            if input_folder is None:
                input_folder = self.get_cwd()
            ref_folder = self.get_param("ref_folder")
            if ref_folder is None:
                ref_folder = self.get_cwd()

            self.compare_folders(input_folder, ref_folder)
            return True

        return False

    def generate_certificate(self, cname, common_name, root_cert=None):
        """Generate an SSL certificate"""
        tools = self.get_component("tools")
        openssl = tools.get_tool_path("openssl")

        if common_name is None:
            common_name = cname

        # Write the config file:
        tpl_file = "ssl_root.cnf" if root_cert is None else "ssl_client.cnf"
        tpl_file = self.get_path(self.ctx.get_root_dir(), "assets", "templates", tpl_file)
        content = self.read_text_file(tpl_file)

        content = self.fill_placeholders(content, {"${COMMON_NAME}": common_name})
        if self.file_exists("config.cnf"):
            self.remove_file("config.cnf")

        self.write_text_file(content, "config.cnf")

        if root_cert is None:
            # Generate a root certificate:
            cmd1 = f"req -newkey rsa:2048 -sha256 -keyout {cname}_key.crt -out {cname}_req.crt -nodes -config ./config.cnf -batch"
            cmd2 = f"x509 -req -in {cname}_req.crt -sha256 -extfile ./config.cnf -extensions v3_ca -signkey {cname}_key.crt -out {cname}.crt -days 3650"
            cmd3 = f"x509 -subject -issuer -noout -in {cname}.crt"

        else:
            # Generate a non-root certificate:
            cmd1 = f"req -newkey rsa:2048 -sha256 -keyout {cname}_key.crt -out {cname}_req.crt -nodes -config ./config.cnf -batch"
            cmd2 = f"x509 -req -in {cname}_req.crt -sha256 -extfile ./config.cnf -extensions usr_cert -CA {root_cert}.crt -CAkey {root_cert}_key.crt -CAcreateserial -out {cname}_cert.crt -days 3650 -passin pass:"
            cmd3 = f"x509 -subject -issuer -noout -in {cname}.crt"

        cwd = self.get_cwd()
        logger.info("CWD: %s", cwd)
        # self.execute([openssl] + cmd0.split(), cwd=cwd)
        self.execute([openssl] + cmd1.split(), cwd=cwd)
        self.execute([openssl] + cmd2.split(), cwd=cwd)

        if root_cert is not None:
            # Combine the certificates:
            content1 = self.read_text_file(f"{cname}_cert.crt")
            content2 = self.read_text_file(f"{root_cert}.crt")
            self.write_text_file(content1 + content2, f"{cname}.crt")

        self.execute([openssl] + cmd3.split(), cwd=cwd)

    def create_par2(self, files, redundancy, nblocks, solid, out_name):
        """Create PAR2 archives for a given list of files"""

        fnames = files.split(",")
        flist = []
        for fname in fnames:
            if "*" in fname:
                # search for all files matching this wildcards:
                files = glob.glob(fname)
                for f in files:
                    flist.append(self.to_absolute_path(f))
            else:
                flist.append(self.to_absolute_path(fname))

        logger.info("Should create par2 files for: %s", flist)

        nfiles = len(flist)

        tools = self.get_component("tools")

        if solid:
            if nfiles > 1:
                self.check(out_name is not None, "Output name for PAR2 archives should be provided here.")
            tools.create_par2_archives(flist, redundancy=redundancy, nblocks=nblocks, out_name=out_name)
        else:
            # Iterate on each file:
            for fname in flist:
                tools.create_par2_archives(fname, redundancy=redundancy, nblocks=nblocks, out_name=out_name)

        logger.info("Done create PAR2 archives.")

    def json_to_yaml(self, input_file, sort_keys):
        """Convert a json file to yaml"""

        dst_file = self.set_path_extension(input_file, ".yml")
        content = self.read_json(input_file)
        self.write_yaml(content, dst_file, sort_keys=sort_keys)
        logger.info("Saved %s as %s", input_file, dst_file)

    def compare_images(self, image1_path, image2_path, tolerance=0.05):
        """Compare 2 images with a given tolerance threshold."""
        # Open images
        img1 = Image.open(image1_path)
        img2 = Image.open(image2_path)

        # Ensure images are the same size
        if img1.size != img2.size:
            return False

        # Ensure images are in the same mode (RGB, RGBA, etc.)
        if img1.mode != img2.mode:
            return False

        # Convert images to numpy arrays (as float to avoid overflow)
        arr1 = np.array(img1, dtype=np.float32)
        arr2 = np.array(img2, dtype=np.float32)

        # Calculate the difference
        diff = np.abs(arr1 - arr2)

        # Calculate the maximum possible difference (account for all channels)
        max_diff = 255.0 * np.prod(arr1.shape)

        # Calculate the actual difference percentage
        diff_percentage = np.sum(diff) / max_diff

        # Compare with tolerance
        return diff_percentage <= tolerance

    def compare_folders(self, input_folder, ref_folder):
        """Compare 2 folders."""

        if input_folder == ref_folder:
            logger.info("Folders are the same, nothing to compare.")
            return

        # get all input files:
        cur_files = self.get_all_files(input_folder, recursive=True)

        # Get all ref files:
        ref_files = self.get_all_files(ref_folder, recursive=True)

        diffs = 0

        # Check for the new files:
        for cfile in cur_files:
            if cfile not in cur_files:
                logger.info("File %s was added.", cfile)
                diffs += 1

        # iterate on all the ref files:
        for rfile in ref_files:
            if rfile not in cur_files:
                logger.info("File %s was removed.", rfile)
                diffs += 1
            else:
                # Compare the file sizes:
                cur_path = self.get_path(input_folder, rfile)
                ref_path = self.get_path(ref_folder, rfile)
                cur_size = self.get_file_size(cur_path)
                ref_size = self.get_file_size(ref_path)

                if cur_size != ref_size:
                    are_similar = False
                    if self.get_path_extension(rfile).lower() == ".png":
                        # logger.info("Comparing %s images...", rfile)
                        are_similar = self.compare_images(cur_path, ref_path, 0.0004)

                    if not are_similar:
                        logger.info("File %s size changed: %d => %d", rfile, ref_size, cur_size)
                        diffs += 1

        if diffs == 0:
            logger.info("Folders are identical.")
        else:
            logger.info("Found %d diffs between folders.", diffs)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("admin")

    context.define_subparsers("main", ["install.cli", "install.reqs", "install.repo"])

    psr = context.build_parser("init")
    psr.add_str("project_name", nargs="?", default=None)("Project to init")
    psr.add_flag("-p", "--with-py-env", dest="with_py_env")("Deploy python env.")

    psr = context.build_parser("create-par2")
    psr.add_str("-i", "--input", dest="input_files")("Input files or folder to consider when building the par2 files")
    psr.add_float("-r", "--redundancy", dest="redundancy", default=10.0)("Data redundancy")
    psr.add_int("-b", "--blocks", dest="num_blocks", default=3000)("Number of blocks")
    psr.add_flag("-s", "--solid", dest="solid")("Create a single par2 archives")
    psr.add_str("-o", "--output", dest="out_name")("Output name of the par2 archives")

    psr = context.build_parser("gen-cert")
    psr.add_str("out_name")("Output name for the certificate")
    psr.add_str("--name")("Common server name")
    psr.add_str("-r", "--root", dest="root_cert")(
        "Specify the root certificate to use, otherwise create a root certificate"
    )

    psr = context.build_parser("json-to-yaml")
    psr.add_str("input_file")("Input file to process")
    psr.add_flag("-s", "--sort-keys", dest="sort_keys")("Sort the keys when writing the file")

    psr = context.build_parser("compare-folders")
    psr.add_str("-i", "--input", dest="input_folder")("Input folder to process")
    psr.add_str("-r", "--ref", dest="ref_folder")("Ref folder to process")

    comp.run()
