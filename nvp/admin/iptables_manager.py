"""IPTablesManager handling component"""

import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class IPTablesManager(NVPComponent):
    """IPTablesManager component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        # self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "list":
            chain = self.get_param("chain")
            ipv = self.get_param("ip_version")
            self.list_rules(chain, ipv)
            return True

        return False

    def list_rules(self, _chain, ipv):
        """List iptables rules."""
        ipv = ipv or 4

        app = "iptables-save" if ipv == 4 else "ip6tables-save"
        cmd = ["sudo", app]
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            logger.error("Failed to retrieve rules: %s", stderr)
            return

        # Otherwise print the output:
        logger.info(stdout)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("IPTablesManager", IPTablesManager(context))

    psr = context.build_parser("list")
    psr.add_str("-c", "--chain", dest="chain")("Target chain for the listing.")
    psr.add_int("-v", "--ip-version", dest="ip_version", default=4)("IP version for the listing.")

    comp.run()
