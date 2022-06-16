"""Collection of admin utility functions"""
import logging
import os
import time
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.nvp_project import NVPProject

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = ScriptRunner(ctx)
    ctx.register_component('runner', comp)


class ScriptRunner(NVPComponent):
    """ScriptRunner component used to run scripts commands on the sub projects"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

        self.scripts = ctx.get_config().get("scripts", {})

        # Also extend the parser:
        ctx.define_subparsers("main", {'run': None})
        psr = ctx.get_parser('main.run')
        psr.add_argument("script_name", type=str, default="run",
                         help="Name of the script to execute")
        psr.add_argument("--show-help", dest="show_script_help", action="store_true",
                         help="Display the help from the script command itself")

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == 'run':
            proj = self.ctx.get_current_project()
            sname = self.get_param('script_name')
            self.run_script(sname, proj)
            return True

        return False

    def fill_placeholders(self, my_entry, hlocs):
        """Fill the placeholders in a given entry"""
        if my_entry is None:
            return None

        for loc, rep in hlocs.items():
            my_entry = my_entry.replace(loc, rep)

        return my_entry

    def has_script(self, script_name):
        """Check if a given script name is available."""
        projs = self.ctx.get_projects()
        for proj in projs:
            desc = proj.get_script(script_name)
            if desc is not None:
                return True

        desc = self.scripts.get(script_name, None)
        return desc is not None

    def run_script(self, script_name: str, proj: NVPProject | None):
        """Run a given script on a given project"""

        # Get the script from the config:
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

        if desc is None:
            logger.warning("No script named %s found", script_name)
            return

        key = f"{self.platform}_cmd"
        cmd = desc[key] if key in desc else desc['cmd']

        hlocs = {}
        hlocs["${PROJECT_ROOT_DIR}"] = proj.get_root_dir() if proj is not None else self.ctx.get_root_dir()
        hlocs["${NVP_ROOT_DIR}"] = self.ctx.get_root_dir()

        # check if we should use python in this command:
        tools = self.get_component('tools')
        env_name = desc.get("custom_python_env", None)
        pdesc = tools.get_tool_desc("python")

        if env_name is not None:
            # Get the environment dir:
            pyenv = self.get_component("pyenvs")

            env_dir = pyenv.get_py_env_dir(env_name)

            pyenv_dir = self.get_path(env_dir, env_name)

            # Check if the pyenv already exist, and otherwise we automatically create it here:
            if not self.dir_exists(pyenv_dir):
                logger.info("Creating python env %s...", env_name)
                pyenv.setup_py_env(env_name)

            py_path = self.get_path(pyenv_dir, pdesc['sub_path'])
        else:
            # use the default python path:
            pyenv_dir = pdesc["base_path"]
            py_path = tools.get_tool_path('python')

        hlocs["${PYTHON}"] = py_path
        hlocs["${PY_ENV_DIR}"] = pyenv_dir

        if "nodejs_env" in desc:
            nodejs = self.get_component("nodejs")
            env_name = desc['nodejs_env']
            env_dir = nodejs.get_env_dir(env_name)
            node_root_dir = self.get_path(env_dir, env_name)
            hlocs["${NODE_ENV_DIR}"] = node_root_dir
            node_path = nodejs.get_node_path(env_name)
            hlocs["${NODE}"] = node_path
            hlocs["${NPM}"] = f"{node_path} {node_root_dir}/node_modules/npm/bin/npm-cli.js"

        if isinstance(cmd, str):
            cmd = self.fill_placeholders(cmd, hlocs)
            cmd = cmd.split(" ")
        else:
            cmd = [self.fill_placeholders(elem, hlocs) for elem in cmd]

        cmd = [el for el in cmd if el != ""]

        cwd = self.fill_placeholders(desc.get('cwd', None), hlocs)

        env = None
        if "python_path" in desc:
            elems = desc["python_path"]
            elems = [self.fill_placeholders(el, hlocs).replace("\\", "/") for el in elems]
            sep = ";" if self.is_windows else ":"
            pypath = sep.join(elems)
            logger.debug("Using pythonpath: %s", pypath)
            env = os.environ.copy()
            env['PYTHONPATH'] = pypath

        # If we have an environment created, we should ensure that we set the PWD correctly:
        if env is not None and cwd is not None:
            env['PWD'] = cwd

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

        # Execute that command:
        logger.debug("Executing script command: %s (cwd=%s)", cmd, cwd)

        auto_restart = desc.get("auto_restart", False)
        notify = self.config.get("notify_script_errors", True)

        while True:
            success, rcode, outputs = self.execute(cmd, cwd=cwd, env=env, outfile=logfile)

            if not success:
                outs = "\n".join(outputs)
                logger.error(
                    "Error occured in script command:\ncmd=%s\ncwd=%s\nreturn code=%s\nlastest outputs:\n%s", cmd, cwd,
                    rcode or "None", outs)

            if not success and notify:
                # And exception occured in the sub process, so we should send a notification:
                msg = ":warning: **WARNING:** an exception occured in the following command:\n"
                msg += f"{cmd}\n"
                msg += f"cwd={cwd}\n\n"
                msg += "=> Check the logs for details."

                rchat = self.get_component("rchat")
                rchat.send_message(msg, channel="problem-reports")

                msg = "<p style=\"color: #fd0202;\">**WARNING:** an exception occured in the following command:</p>"
                msg += f"<p><em>{cmd}</em></p>"
                msg += f"<p>cwd={cwd}</p>"
                msg += "<p >=> Check the logs for details.</p>"

                email = self.get_component("email")
                email.send_message("[NervProj] Exception notification", msg)

            if success or not auto_restart:
                break

            # Check if we have a restart delay:
            delay = desc.get("restart_delay", None)
            if delay is not None:
                time.sleep(delay)

        if logfile is not None:
            logfile.close()
