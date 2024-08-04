"""Collection of admin utility functions"""

import copy
import logging
import os
import re
import time
from pathlib import Path

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = ScriptRunner(ctx)
    ctx.register_component("runner", comp)


class ScriptRunner(NVPComponent):
    """ScriptRunner component used to run scripts commands on the sub projects"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

        self.scripts = ctx.get_config().get("scripts", {})

        # Also extend the parser:
        ctx.define_subparsers("main", {"run": None})
        psr = ctx.get_parser("main.run")
        psr.add_argument("script_name", type=str, default="run", help="Name of the script to execute")
        psr.add_argument(
            "--show-help",
            dest="show_script_help",
            action="store_true",
            help="Display the help from the script command itself",
        )

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "run":
            proj = self.ctx.get_current_project()
            sname = self.get_param("script_name")
            self.run_script(sname, proj)
            return True

        return False

    def list_scripts(self):
        """List of all available scripts"""
        # logger.info("Should list all the available scripts here.")
        snames = []

        projs = self.ctx.get_projects()
        for proj in projs:
            snames += proj.get_script_names()

        snames += list(self.scripts.keys())

        snames = list(set(snames))
        snames.sort()

        print("List of available NVP scripts:")
        for sname in snames:
            print(f"- {sname}")

    def has_script(self, script_name):
        """Check if a given script name is available."""
        projs = self.ctx.get_projects()
        for proj in projs:
            desc = proj.get_script(script_name)
            if desc is not None:
                return True

        desc = self.scripts.get(script_name, None)
        return desc is not None

    def get_script_parameters(self):
        """Retrieve all the script parameters"""
        projs = self.ctx.get_projects()
        sparams = {}
        for proj in projs:
            params = proj.get_config().get("script_parameters", {})
            for pname, pval in params.items():
                if pname in sparams and sparams[pname] != pval:
                    logger.warning(
                        "Overriding script parameter %s: %s => %s",
                        pname,
                        sparams[pname],
                        pval,
                    )
                sparams[pname] = pval
        return sparams

    def get_script_desc(self, script_name: str, proj: NVPProject | None):
        """Retrieve a script desc by name"""
        desc = None
        if proj is not None:
            desc = proj.get_script(script_name)

        if desc is None:
            # Then search in all projects:
            projs = self.ctx.get_projects()
            for proj in projs:
                desc = proj.get_script(script_name)
                if desc is not None:
                    break

        if desc is None:
            desc = self.scripts.get(script_name, None)

        if desc is not None and "inherit" in desc:
            # Inherit the given script:
            ihname = desc["inherit"]
            pdesc = self.get_script_desc(ihname, proj)
            for key, val in pdesc.items():
                if key not in desc:
                    desc[key] = val

        return desc

    def run_script(self, script_name: str, proj: NVPProject | None):
        """Run a given script given by name on a given project"""
        desc = self.get_script_desc(script_name, proj)
        self.run_script_desc(desc, script_name, proj)

    def fill_placeholders(self, content, hlocs):
        """Re-implementation of fill_placeholders to handle processing of tool paths"""
        content = super().fill_placeholders(content, hlocs)

        # Also find if we have any mention of a tool path or tool dir in there:
        pat = re.compile(r"\$\[([^:]+):([a-z]+)\]")
        tools = self.get_component("tools")
        match = pat.search(content)
        while match is not None:

            # Get the source match:
            match_str = match.group(0)

            # get the request type:
            req_type = match.group(1)

            # Get the tool name:
            tool_name = match.group(2)

            # Compute the replacement:
            match req_type:
                case "TOOL_PATH":
                    replacement = tools.get_tool_path(tool_name)
                case "TOOL_DIR":
                    replacement = tools.get_tool_dir(tool_name)
                case "TOOL_ROOT_DIR":
                    replacement = tools.get_tool_root_dir(tool_name)
                case _:
                    self.throw("Invalid replacement request type: %s", req_type)

            # Replace in the string:
            logger.info("Replacing '%s' with '%s'", match_str, replacement)
            content = content.replace(match_str, replacement)

            match = pat.search(content)

        return content

    def run_script_desc(self, desc, script_name: str, proj: NVPProject | None):
        """Run a given script desc on a given project"""

        if desc is None:
            logger.warning("No script named %s found", script_name)
            return

        # If the desc contains a "script" entry, then we should retrive the corresponding script and
        # extend it with the settings we have in the current desc:
        if "script" in desc:
            sname = desc["script"]

            # We should not have both "script" and "cmd" entries:
            self.check("cmd" not in desc, "Should not have cmd here")
            self.check("windows_cmd" not in desc, "Should not have windows_cmd here")
            self.check("linux_cmd" not in desc, "Should not have linux_cmd here")

            # Retrieve the curresponding script desc:
            # The name of the script will be the first word, and the
            # following words should be considered additional command line arguments:
            words = sname.split()
            sname = words.pop(0)
            args = " ".join(words) if len(words) > 0 else None

            desc2 = self.get_script_desc(sname, proj)

            if desc2 is None:
                logger.warning("No script named %s found", sname)
                return

            # We should adapt the subscript desc and then run it:
            desc2 = copy.deepcopy(desc2)

            for key, val in desc.items():
                if key in ["script"]:
                    # We do not override that entry.
                    continue

                desc2[key] = val

            # If desc2 is a script call then we append the args to the script,
            # otherwise we append to the cmd entry:
            if args is not None:
                if "script" in desc2:
                    desc2["script"] += f" {args}"
                else:
                    for key in ["cmd", f"{self.platform}_cmd"]:
                        if key in desc2:
                            desc2[key] += f" {args}"

            # Finally we run that script and return:
            self.run_script_desc(desc2, sname, proj)
            return

        key = f"{self.platform}_cmd"
        cmd = desc[key] if key in desc else desc["cmd"]

        hlocs = {}
        # Note the project root dir below might still be None:
        hlocs["${PROJECT_ROOT_DIR}"] = proj.get_root_dir() if proj is not None else self.ctx.get_root_dir()
        hlocs["${NVP_ROOT_DIR}"] = self.ctx.get_root_dir()
        hlocs["${SCRIPT_NAME}"] = script_name
        hlocs["${EXE_SUFFIX}"] = ".exe" if self.platform == "windows" else ""
        hlocs["${HOME}"] = str(Path.home()).replace("\\", "/")

        if "vars" in desc:
            for k, v in desc["vars"].items():
                hlocs["${" + k + "}"] = self.fill_placeholders(v, hlocs)

        # check if we should use python in this command:
        tools = self.get_component("tools")
        env_name = desc.get("custom_python_env", None)
        pdesc = tools.get_tool_desc("python")
        additional_paths = []
        if env_name is not None:
            # Get the environment dir:
            pyenv = self.get_component("pyenvs")

            env_dir = pyenv.get_py_env_dir(env_name)

            pyenv_dir = self.get_path(env_dir, env_name)

            # Check if the pyenv already exist, and otherwise we automatically create it here:
            if not self.dir_exists(pyenv_dir):
                logger.info("Creating python env %s...", env_name)
                pyenv.setup_py_env(env_name)

            py_path = self.get_path(pyenv_dir, pdesc["sub_path"])

            hlocs["${PYTHON_DIR}"] = self.get_parent_folder(py_path)
            additional_paths.append(self.get_parent_folder(py_path))
        else:
            # use the default python path:
            pyenv_dir = pdesc["base_path"]
            py_path = tools.get_tool_path("python")

        hlocs["${PYTHON}"] = py_path
        hlocs["${PY_ENV_DIR}"] = pyenv_dir
        hlocs["${NVP}"] = f"{py_path} {self.ctx.get_root_dir()}/cli.py"

        if tools.has_tool("ninja"):
            hlocs["${NINJA}"] = tools.get_tool_path("ninja")

        if "nodejs_env" in desc:
            nodejs = self.get_component("nodejs")
            env_name = desc["nodejs_env"]
            env_dir = nodejs.get_env_dir(env_name)
            node_root_dir = self.get_path(env_dir, env_name)
            hlocs["${NODE_ENV_DIR}"] = node_root_dir
            node_path = nodejs.get_node_path(env_name)
            hlocs["${NODE}"] = node_path
            hlocs["${NPM}"] = f"{node_path} {node_root_dir}/node_modules/npm/bin/npm-cli.js"

        sparams = self.get_script_parameters()
        # logger.info("Using script parameters: %s", sparams)
        for pname, pvalue in sparams.items():
            hlocs[f"${{{pname}}}"] = self.fill_placeholders(pvalue, hlocs)

        if "params" in desc:
            params = desc["params"]
            for pname, pvalue in params.items():
                hlocs[f"${{{pname}}}"] = self.fill_placeholders(pvalue, hlocs)

        if isinstance(cmd, str):
            cmd = self.fill_placeholders(cmd, hlocs)
            cmd = cmd.split(" ")
        else:
            cmd = [self.fill_placeholders(elem, hlocs) for elem in cmd]

        cmd = [el for el in cmd if el != ""]

        cwd = desc.get("cwd", None)
        if cwd is None:
            # If no CWD is provided we should use the current HOME folder as default:
            # Update: actually we really need to use get_cwd() or None here.
            # Otherwise some commands (like "nvp git commit") will not work.
            cwd = self.get_cwd()

            # cwd = self.ctx.get_home_dir()

        cwd = self.fill_placeholders(cwd, hlocs)

        env = os.environ.copy()

        key = f"{self.platform}_env_vars"
        env_dict = desc[key] if key in desc else desc.get("env_vars", None)

        # check if we have a system specific env_var list and use it instead in that case:
        pname = self.get_hostname().lower()
        key = f"{pname}.env_vars"
        if key in desc:
            env_dict = desc[key]

        if env_dict is not None:
            for key, val in env_dict.items():

                env[key] = self.fill_placeholders(val, hlocs)

        sep = ";" if self.is_windows else ":"

        if len(additional_paths) > 0:
            # Add the additional paths:
            val = sep.join(additional_paths)
            os.environ["PATH"] = self.fill_placeholders(val, hlocs) + sep + os.environ["PATH"]
            env["PATH"] = os.environ["PATH"]

        def add_env_paths(key):
            if key in desc:
                val = desc[key].replace(";", sep)
                os.environ["PATH"] = self.fill_placeholders(val, hlocs) + sep + os.environ["PATH"]
                env["PATH"] = os.environ["PATH"]

        add_env_paths("env_paths")
        add_env_paths(f"{self.platform}_env_paths")
        add_env_paths(f"{pname}.env_paths")

        if "python_path" in desc:
            elems = desc["python_path"]
            elems = [self.fill_placeholders(el, hlocs).replace("\\", "/") for el in elems]
            sep = ";" if self.is_windows else ":"
            pypath = sep.join(elems)
            logger.debug("Using pythonpath: %s", pypath)
            env = env or os.environ.copy()
            env["PYTHONPATH"] = pypath

        # If we have an environment created, we should ensure that we set the PWD correctly:
        if env is not None and cwd is not None:
            env["PWD"] = cwd

        # Check if we have additional args to pass to the command:
        args = self.ctx.get_additional_args()
        # Manually collect the additional args: (same results as above)
        # idx = sys.argv.index(script_name)
        # args = sys.argv[idx+1:]
        if len(args) > 0:
            cmd += args

        if self.get_param("show_script_help", False):
            cmd += ["--help"]

        logfile = None
        if "log_file" in desc:
            filename = self.fill_placeholders(desc["log_file"], hlocs)
            logfile = open(filename, "w", encoding="utf-8")

        lockfile = None
        if "lock_file" in desc:
            lockfile = self.fill_placeholders(desc["lock_file"], hlocs)
            folder = self.get_parent_folder(lockfile)
            self.make_folder(folder)

        if lockfile is not None and self.file_exists(lockfile):
            logger.warning("'%s' prevented: lock file exists (%s). ", script_name, lockfile)
            return

        # Create the lockfile otherwise if applicable:
        if lockfile is not None:
            Path(lockfile).touch()

        # Execute that command:
        logger.debug("Executing script command: %s (cwd=%s)", cmd, cwd)

        auto_restart = desc.get("auto_restart", False)
        notify = self.config.get("notify_script_errors", True)
        encoding = desc.get("output_encoding", "utf-8")

        # Override notify level if applicable for this script:
        if "notify" in desc:
            notify = desc["notify"]

        while True:
            try:
                success, rcode, outputs = self.execute(cmd, cwd=cwd, env=env, outfile=logfile, encoding=encoding)
            except Exception:
                logger.error("Exception trying to execute '%s' in cwd='%s'", cmd, cwd)
                return

            if not success:
                outs = "".join(outputs)
                logger.error(
                    "Error occured in script command:\ncmd=%s\ncwd=%s\nreturn code=%s\nlastest outputs:\n%s",
                    cmd,
                    cwd,
                    rcode or "None",
                    outs,
                )

            if not success and notify:
                # And exception occured in the sub process, so we should send a notification:
                msg = ":warning: **WARNING:** an exception occured in the following command:\n"
                msg += f"{cmd}\n"
                msg += f"cwd={cwd}\n\n"
                msg += "=> Check the logs for details."

                rchat = self.get_component("rchat")
                rchat.send_message(msg, channel="problem-reports")

                msg = '<p style="color: #fd0202;">**WARNING:** an exception occured in the following command:</p>'
                msg += f"<p><em>{cmd}</em></p>"
                msg += f"<p>cwd={cwd}</p>"
                msg += "<p >=> Check the logs for details.</p>"

                email = self.get_component("email")
                email.send_message("[NervProj] Exception notification", msg)

            restart_requested = auto_restart

            restart_file = self.get_path(cwd, "nvp_restart_requested")
            if self.file_exists(restart_file):
                self.remove_file(restart_file)
                restart_requested = True
                logger.info("Process restart requested for %s.", script_name)

            if not success and auto_restart:
                logger.info("Process failed, auto restart requested for %s.", script_name)
                restart_requested = True

            if not restart_requested:
                break

            # Check if we have a restart delay:
            delay = desc.get("restart_delay", 60)
            if delay is not None:
                logger.info("Waiting %s seconds to restart process...", delay)
                time.sleep(delay)

            logger.info("Restarting %s...", script_name)

        if logfile is not None:
            logfile.close()

        # Remove the lock file if any:
        if lockfile is not None:
            self.remove_file(lockfile)
