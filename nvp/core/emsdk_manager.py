"""EMSDK manager component"""
import logging

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

    def process_cmd_path(self, cmd):
        """Process a given command path"""

        if cmd == "install":
            target = self.get_param("target")
            # logger.info("Should install emsdk target %s here.", target)
            self.execute_emsdk(["install", target])
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
        res, rcode, outs = self.execute(cmd, cwd=cwd)

        if not res:
            logger.error("emsdk command %s (in %s) failed with return code %d:\n%s", cmd, cwd, rcode, outs)
            self.throw("Detected emsdk command failure.")


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("emsdk", EmsdkManager(context))

    psr = context.build_parser("install")
    psr.add_str("target", nargs="?", default="latest")("Installation target")
    # psr.add_str("-o", "--output", dest="output_file")("Output file to generate.")
    # psr.add_float("-g", "--gain", dest="gain", default=1.0)("Volume gain factor")

    comp.run()
