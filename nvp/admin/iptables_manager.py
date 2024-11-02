"""IPTablesManager handling component"""

import logging
import shlex

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class IPTablesManager(NVPComponent):
    """IPTablesManager component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.ipv = 4
        # self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        self.ipv = self.get_param("ip_version", 4)

        if cmd == "list":
            chain = self.get_param("chain")
            rules = self.list_rules(chain)
            if rules is not None:
                # Otherwise print the output:
                logger.info(rules)
            return True

        if cmd == "save":
            file = self.get_rules_file()
            self.save_rules(file)
            return True

        if cmd == "load":
            file = self.get_rules_file()
            self.load_rules(file)
            return True

        return False

    def get_rules_file(self, key="filename"):
        """Retrieve the filled rules filename."""
        file = self.get_param(key)
        file = file.replace("${HOME}", self.ctx.get_home_dir())
        file = file.replace("${IPV}", str(self.ipv))
        folder = self.get_parent_folder(file)
        self.make_folder(folder)
        return file

    def list_rules(self, _chain=None):
        """List iptables rules."""
        app = "ip6tables-save" if self.ipv == 6 else "iptables-save"
        cmd = ["sudo", app]
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            logger.error("Failed to retrieve rules: %s", stderr)
            return None

        # Otherwise print the output:
        return stdout

    def run_ipt(self, args):
        """Run the iptables command."""
        app = "ip6tables" if self.ipv == 6 else "iptables"

        if isinstance(args, str):
            args = shlex.split(args)

        cmd = ["sudo", app] + args
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            self.throw("Failed to execute command %s: %s", cmd, stderr)

        return stdout

    def flush_all(self):
        """Flush all the rules."""
        logger.info("Flushing existing iptables rules (v%d)...", self.ipv)

        # Flush all existing rules in filter and nat tables
        self.run_ipt("-F")
        self.run_ipt("-t nat -F")

        # Delete all user-defined chains
        self.run_ipt("-X")
        self.run_ipt("-t nat -X")

        # Set default policies to ACCEPT (can be changed to DROP if needed)
        self.run_ipt("-P INPUT ACCEPT")
        self.run_ipt("-P FORWARD ACCEPT")
        self.run_ipt("-P OUTPUT ACCEPT")
        self.run_ipt("-t nat -P PREROUTING ACCEPT")
        self.run_ipt("-t nat -P POSTROUTING ACCEPT")

        logger.info("iptables rules cleared.")

    def save_rules(self, file):
        """Save the current iptable rules."""
        rules = self.list_rules()

        self.write_text_file(rules, file)

    def load_rules(self, file, flush=True):
        """Load the current iptable rules."""
        if flush:
            self.flush_all()

        app = "ip6tables-restore" if self.ipv == 6 else "iptables-restore"
        cmd = ["sudo", app, file]
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            logger.error("Failed to restore rules from %s: %s", file, stderr)
            return
        logger.info(stdout)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("IPTablesManager", IPTablesManager(context))

    psr = context.build_parser("list")
    psr.add_int("-v", "--ip-version", dest="ip_version", default=4)("IP version.")
    psr.add_str("-c", "--chain", dest="chain")("Target chain for the listing.")

    psr = context.build_parser("save")
    psr.add_int("-v", "--ip-version", dest="ip_version", default=4)("IP version.")
    psr.add_str("-f", "--file", dest="filename", default="${HOME}/.nvp/iptable_rules.v${IPV}")(
        "File where to save the IPtable rules."
    )

    psr = context.build_parser("load")
    psr.add_int("-v", "--ip-version", dest="ip_version", default=4)("IP version.")
    psr.add_str("-f", "--file", dest="filename", default="${HOME}/.nvp/iptable_rules.v${IPV}")(
        "File where to load the IPtable rules from."
    )

    comp.run()
