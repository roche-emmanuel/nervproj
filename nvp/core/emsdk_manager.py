"""EMSDK manager component"""
import logging
import os

from nvp.nvp_compiler import NVPCompiler
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return EmsdkManager(ctx)


class EmsdkManager(NVPComponent):
    """EmsdkManager component"""

    def __init__(self, ctx: NVPContext):
        """Class constructor"""
        NVPComponent.__init__(self, ctx)
        self.compiler = None

    def process_cmd_path(self, cmd):
        """Process a given command path"""

        if cmd == "install":
            target = self.get_param("target")
            self.execute_emsdk(["install", target])
            return True

        if cmd == "activate":
            target = self.get_param("target")
            self.execute_emsdk(["activate", target])
            return True

        if cmd == "construct_env":
            self.execute_emsdk(["construct_env"])
            return True

        return False

    def execute_emsdk(self, args, cwd=None):
        """Execute the emsdk python file"""

        if cwd is None:
            cwd = self.get_cwd()

        tools = self.get_component("tools")
        py_path = tools.get_tool_path("python")

        emsdk_dir = tools.get_tool_dir("emsdk")
        emsdk_file = self.get_path(emsdk_dir, "emsdk.py")

        cmd = [py_path, emsdk_file] + args
        logger.info("emsdk command: %s", cmd)
        env = os.environ.copy()
        env["EMSDK_PY"] = py_path

        res, rcode, outs = self.execute(cmd, cwd=cwd, env=env)

        if not res:
            logger.error("emsdk command %s (in %s) failed with return code %d:\n%s", cmd, cwd, rcode, outs)
            self.throw("Detected emsdk command failure.")

    def get_compiler(self):
        """Get the EMCC compiler"""

        if self.compiler is not None:
            return self.compiler

        # First we must check if the installation is already done:
        tools = tools = self.get_component("tools")
        emsdk_dir = tools.get_tool_dir("emsdk")

        em_dir = self.get_path(emsdk_dir, "upstream", "emscripten")
        if not self.dir_exists(em_dir):
            logger.info("Installing emsdk packages...")
            self.execute_emsdk(["install", "latest"])

        # The emscripten folder must exist:
        self.check(self.dir_exists(em_dir), "Invalid emscripten dir: %s", em_dir)

        # Next we must get the node dir:
        folders = self.get_all_folders(self.get_path(emsdk_dir, "node"))
        node_path = None

        ext = ".exe" if self.is_windows else ""
        for folder in folders:
            filename = self.get_path(emsdk_dir, "node", folder, "bin", f"node{ext}")
            if self.file_exists(filename):
                node_path = filename
                break

        self.check(node_path is not None, "Cannot find node path in %s/node", emsdk_dir)

        # Get the python path
        folders = self.get_all_folders(self.get_path(emsdk_dir, "python"))
        python_path = None

        ext = ".exe" if self.is_windows else ""
        for folder in folders:
            filename = self.get_path(emsdk_dir, "python", folder, f"python{ext}")
            if self.file_exists(filename):
                python_path = filename
                break

        self.check(python_path is not None, "Cannot find python path in %s/python", emsdk_dir)

        # Get the JRE path
        folders = self.get_all_folders(self.get_path(emsdk_dir, "java"))
        jre_dir = None

        ext = ".exe" if self.is_windows else ""
        for folder in folders:
            filename = self.get_path(emsdk_dir, "java", folder, "bin", f"java{ext}")
            if self.file_exists(filename):
                jre_dir = self.get_path(emsdk_dir, "java", folder)
                break

        self.check(jre_dir is not None, "Cannot find java dir in %s/java", emsdk_dir)

        # Now we can create a compiler:
        self.compiler = NVPCompiler(
            self.ctx,
            {
                "type": "emcc",
                "root_dir": em_dir,
                "node_path": node_path,
                "python_path": python_path,
                "emsdk_dir": emsdk_dir,
                "jre_dir": jre_dir,
            },
        )

        return self.compiler


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("emsdk", EmsdkManager(context))

    psr = context.build_parser("install")
    psr.add_str("target", nargs="?", default="latest")("Installation target")

    psr = context.build_parser("activate")
    psr.add_str("target", nargs="?", default="latest")("Activation target")

    psr = context.build_parser("construct_env")

    comp.run()
