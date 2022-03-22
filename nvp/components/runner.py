"""Collection of admin utility functions"""
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

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

        # Also extend the parser:
        ctx.define_subparsers("main", {'run': None})
        psr = ctx.get_parser('main.run')
        psr.add_argument("script_name", type=str, default="run",
                         help="Name of the script to execute")

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == 'run':
            proj = self.ctx.get_current_project()
            sname = self.ctx.get_settings()['script_name']
            proj.run_script(sname)
            return True

        return False
