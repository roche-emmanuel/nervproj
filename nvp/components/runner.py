"""Collection of admin utility functions"""
import logging
import os

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

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == 'run':
            proj = self.ctx.get_current_project()
            sname = self.get_param('script_name')
            self.run_script(sname, proj)
            return True

        return False

    def fill_placeholders(self, my_entry, proj: NVPProject):
        """Fill the placeholders in a given entry"""
        if my_entry is None:
            return None

        root_dir = proj.get_root_dir() if proj is not None else self.ctx.get_root_dir()
        my_entry = my_entry.replace("${PROJECT_ROOT_DIR}", root_dir)
        my_entry = my_entry.replace("${NVP_ROOT_DIR}", self.ctx.get_root_dir())

        return my_entry

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

        cmd = self.fill_placeholders(cmd, proj)

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

        cmd = cmd.replace("${PYTHON}", py_path)
        cmd = cmd.replace("${ENV_DIR}", pyenv_dir)
        cmd = cmd.split(" ")
        cmd = [el for el in cmd if el != ""]

        cwd = self.fill_placeholders(desc.get('cwd', None), proj)

        env = None
        if "python_path" in desc:
            elems = desc["python_path"]
            elems = [self.fill_placeholders(el, proj).replace("\\", "/") for el in elems]
            sep = ";" if self.is_windows else ":"
            pypath = sep.join(elems)
            logger.debug("Using pythonpath: %s", pypath)
            env = os.environ.copy()
            env['PYTHONPATH'] = pypath

        # If we have an environment created, we should ensure that we set the PWD correctly:
        if env is not None:
            env['PWD'] = cwd

        # Check if we have additional args to pass to the command:
        args = self.ctx.get_additional_args()
        if len(args) > 0:
            cmd += args

        # Execute that command:
        logger.debug("Executing script command: %s (cwd=%s)", cmd, cwd)
        self.execute(cmd, cwd=cwd, env=env)
