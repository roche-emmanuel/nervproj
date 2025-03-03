"""IPTablesManager handling component"""

import logging
import re
import shlex
from datetime import datetime

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

NTP_SERVERS = [
    "128.138.140.44",
    "66.243.43.2",
    "192.36.144.22",
    "139.78.100.163",
    "131.107.1.10",
    "199.165.76.11",
    "140.142.16.34",
    "137.146.210.250",
    "129.7.1.66",
    "192.43.244.18",
    "158.121.104.4",
    "192.6.38.127",
    "216.133.140.77",
    "140.221.8.88",
    "66.243.43.2",
    "128.138.140.44",
    "131.107.13.100",
    "129.6.15.28",
]


class IPTablesManager(NVPComponent):
    """IPTablesManager component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.ipv = 4
        self.dryrun = False
        self.config = ctx.get_config().get("iptables")
        if self.config is None:
            self.config = self.ctx.get_project("NervHome").get_config().get("iptables")

        self.check(self.config is not None, "Invalid iptables config.")
        # logger.info("iptables configs: %s", self.config)

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        self.ipv = self.get_param("ip_version", 4)
        self.dryrun = self.get_param("dry_run", False)

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

        if cmd == "write":
            cfg = self.get_param("config_name")
            self.write_rules(cfg)
            return True

        if cmd == "update_mac_whitelist":
            # cfg = self.get_param("config_name")
            self.update_mac_wl()
            return True

        if cmd == "update_ntp_list":
            self.create_ntp_list()
            return True

        # if cmd == "monitor":
        #     iname = self.get_param("intf_name")
        #     self.monitor_traffic(iname)
        #     return True

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

        if self.dryrun:
            logger.info("Dryrun: %s", " ".join(cmd))
            return ""

        logger.info("running: %s", " ".join(cmd))
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            self.throw("Failed to execute command %s: %s", cmd, stderr)

        return stdout

    def run_arp(self, args):
        """Run the iptables command."""
        app = "arp"

        if isinstance(args, str):
            args = shlex.split(args)

        cmd = [app] + args

        if self.dryrun:
            logger.info("Dryrun: %s", " ".join(cmd))
            return ""

        # logger.info("running: %s", " ".join(cmd))
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            self.throw("Failed to execute command %s: %s", cmd, stderr)

        return stdout

    def run_ebt(self, args):
        """Run the ebtables command."""
        app = "ebtables"

        if isinstance(args, str):
            args = shlex.split(args)

        cmd = ["sudo", app] + args

        if self.dryrun:
            logger.info("Dryrun: %s", " ".join(cmd))
            return ""

        logger.info("running: %s", " ".join(cmd))
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            self.throw("Failed to execute command %s: %s", cmd, stderr)

        return stdout

    def run_ipset(self, args, retcode=False):
        """Run the ipset command."""
        app = "ipset"

        if isinstance(args, str):
            args = shlex.split(args)

        cmd = ["sudo", app] + args

        if self.dryrun:
            logger.info("Dryrun: %s", " ".join(cmd))
            return ""

        # logger.info("running: %s", " ".join(cmd))
        stdout, stderr, returncode = self.execute_command(cmd)

        if retcode:
            return returncode

        if returncode != 0:
            self.throw("Failed to execute command %s: %s", cmd, stderr)

        return stdout

    def has_set(self, set_name):
        """Check if a given set exists."""
        res = self.run_ipset(f"list {set_name}", True)
        return res == 0

    def create_set(self, sname, htype, elements=None):
        """Create an ipset."""
        self.run_ipset(["create", sname, htype])

        if elements is None:
            return

        # If we have elements we should add them here:
        for elem in elements:
            self.add_to_set(sname, elem)

    def add_to_set(self, sname, entry):
        """Create an element to a set"""
        self.run_ipset(["add", sname, entry])

    def remove_from_set(self, sname, entry):
        """Remove an element from a set."""
        self.run_ipset(["del", sname, entry])

    def get_set_content(self, sname):
        """Get content of one set."""
        out = self.run_ipset(["list", sname])

        # Split the string by "Members:" and take the second part
        mac_section = out.split("Members:")[1]

        # Split by lines and strip whitespace to get clean MAC addresses
        mac_list = [mac.strip() for mac in mac_section.strip().split("\n") if mac != ""]

        return mac_list

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
        logger.info("Saved iptables rules to file %s", file)

    def load_rules(self, file, flush=True):
        """Load the current iptable rules."""
        if flush:
            self.flush_all()

        app = "ip6tables-restore" if self.ipv == 6 else "iptables-restore"
        cmd = ["sudo", app, file]
        _, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            logger.error("Failed to restore rules from %s: %s", file, stderr)
            return

        logger.info("Loaded iptables rules to file %s", file)

    def write_policies(self, desc, source, prefix=""):
        """Write the filter policies."""
        key = desc[source]
        pols = self.config["policies"][key]
        for k, v in pols.items():
            cmd = f"{prefix} -P {k} {v}"
            self.run_ipt(cmd)

    def write_filter_policies(self, desc):
        """Write the filter policies."""
        self.write_policies(desc, "filter_policies")

    def write_nat_policies(self, desc):
        """Write the nat policies."""
        self.write_policies(desc, "nat_policies", "-t nat")

    def write_rule(self, rname, values, hlocs):
        """Write a rule template with the given values."""

        entries = self.config["templates"][rname]

        for entry in entries:
            entry = self.fill_placeholders(entry, hlocs)
            for val in values:
                cmd = self.fill_placeholders(entry, {"${VALUE}": str(val)})
                self.run_ipt(cmd)

    def write_rules(self, cfg_name, flush=True):
        """Write the rules from a given config."""
        # First we flush the rules:
        if flush:
            self.flush_all()

        desc = self.config[cfg_name]

        # Write the policies:
        self.write_filter_policies(desc)
        self.write_nat_policies(desc)

        # Prepare the hlocs:
        vdescs = desc["variables"]
        hlocs = {f"${{{vname}}}": val for vname, val in vdescs.items()}

        # Write the rules:
        rdescs = desc["rules"]
        for rdesc in rdescs:
            if isinstance(rdesc, str):
                # This is a simple rule with no values:
                self.write_rule(rdesc, [0], hlocs)
            else:
                for rname, values in rdesc.items():
                    self.write_rule(rname, values, hlocs)

    def get_mac_ip_mapping(self):
        """Get the MAC/IP mapping with arp"""
        cmd = ["arp", "-n"]

        arp_output = self.run_arp("-n")

        # Regular expression to match IP, MAC, and Interface
        pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+(?:ether\s+([\da-f:]+)\s+)?\S*\s+(\S+)")

        # Extracted data
        devices = []

        for match in pattern.finditer(arp_output):
            ip = match.group(1)
            mac = match.group(2) if match.group(2) else "INCOMPLETE"
            interface = match.group(3)
            devices.append((ip, mac.upper(), interface))

        # Print results
        # for ip, mac, iface in devices:
        #     print(f"IP: {ip}, MAC: {mac.upper()}, Interface: {iface}")

        # Note: here we have to be careful with the wifi extender MAC addresses:
        # because we will see the extender MAC address associated to
        return {elem[1]: (elem[0], elem[2]) for elem in devices if elem[1] != "INCOMPLETE"}

    def check_in_schedule(self, schedule):
        """Check if current time is in schedule."""

        if schedule == "always":
            return True

        if schedule == "never":
            return False

        # get the current day:
        now = datetime.now()
        day = now.weekday()
        day_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        day_str = day_map[day]

        cur_hour = now.hour
        cur_min = now.minute
        cur_sec = now.second

        cur_ts = cur_hour * 3600 + cur_min * 60 + cur_sec

        factor = 1.0

        # Iterate on each rule:
        for rule in schedule:
            if "days" in rule:
                active_days = rule["days"].split("|")
                if day_str not in active_days:
                    # Rule not applicable today
                    continue

            # Get the start time:
            parts = rule["start"].split(":")
            if len(parts) == 2:
                parts.append("0")
            start_ts = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

            parts = rule["end"].split(":")
            if len(parts) == 2:
                parts.append("0")
            end_ts = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

            if end_ts < start_ts:
                # In this case we add 24hours to the end:
                end_ts += 24 * 3600

            # Apply the factor on the duration:
            delta_secs = float(end_ts - start_ts)
            end_ts = int(start_ts + delta_secs * factor)

            end_ts = max(end_ts, start_ts)

            # After scaling, determine if end time is now on the next day or current day
            is_overnight_after_scaling = end_ts > 24 * 3600

            if is_overnight_after_scaling:
                # Remove 1 full day in this case:
                adjusted_end_ts = end_ts - 24 * 3600

                # Handle overnight case
                if cur_ts >= start_ts or cur_ts < adjusted_end_ts:
                    return True
            else:
                # Normal same-day schedule
                if start_ts <= cur_ts < end_ts:
                    return True

        return False

    def create_ntp_list(self):
        """Create the ntp servers list."""
        sname = "ntp_servers"

        if self.has_set(sname):
            logger.info("NTP server list ipset %s already exists", sname)
            return

        self.create_set(sname, "hash:net", NTP_SERVERS)
        logger.info("Created NTP server list ipset %s", sname)

    def update_mac_wl(self):
        """Update the WAN access rule"""
        grps = self.config.get("mac_groups", {})
        # logger.info("Found MAC groups:: %s", grps)
        sname = "mac_whitelist"

        mac_map = self.get_mac_ip_mapping()

        # create the set if needed:
        if not self.has_set(sname):
            logger.info("Creating set %s", sname)
            self.create_set(sname, "hash:net")
        # l0 = self.has_set(sname)
        # logger.info("Has mac_whitelist: %s", l0)
        # l1 = self.has_set("blacklist")
        # logger.info("Has blacklist: %s", l1)

        devs = self.config["devices"]

        grps = self.config["mac_groups"]

        prev_list = self.get_set_content(sname)
        # logger.info("Previous list contained %d elements", len(prev_list))
        changes = False
        found = []

        # First we add all the IPs that are not on the eno2/eno1 interfaces:
        for mac, desc in mac_map.items():
            ip = desc[0]

            if desc[1] in ["eno1", "eno2"]:
                continue

            if ip not in prev_list:
                self.check(ip not in found, "Ip %s was already whitelisted.", ip)

                logger.info("Adding IP %s for MAC %s on %s", ip, mac, desc[1])
                self.add_to_set(sname, ip)
                changes = True
            else:
                found.append(ip)

        # Iterate on the enable groups:
        sch = self.config.get("internet_schedule", {})
        for grp_name, schedule in sch.items():
            # logger.info("%s: %s", grp_name, state)
            # Add each element from that group to the set:
            grp = grps[grp_name]

            if self.check_in_schedule(schedule):
                for elem in grp:
                    mac = devs[elem]["mac"].upper()
                    ref_ip = devs[elem]["ip"]

                    # If that MAC is not connected, we ignore it:
                    if mac not in mac_map:
                        # logger.info("Mac %s not connected", mac)
                        continue

                    intf = mac_map[mac][1]
                    if intf != "eno2":
                        logger.info("Ignoring IP/MAC %s/%s in interface %s", ip, mac, intf)
                        continue

                    ip = mac_map[mac][0]
                    if ip != ref_ip:
                        allowed = False
                        if ref_ip == "192.168.2.8" and ip == "192.168.2.25":
                            # manu_uranus case allowed:
                            allowed = True

                        if not allowed:
                            logger.error(
                                "Detected IP mismatch for %s (MAC %s): expected: %s, got: %s",
                                elem,
                                mac,
                                ref_ip,
                                ip,
                            )
                            # continue

                    if ip not in prev_list:
                        logger.info(
                            "Adding IP %s for %s (grp: %s) (MAC: %s)",
                            ip,
                            elem,
                            grp_name,
                            mac,
                        )
                        self.add_to_set(sname, ip)
                        changes = True
                    else:
                        # logger.info("IP %s already in list", ip, mac)
                        found.append(ip)

        # Remove the non wanted elements:
        to_remove = [elem for elem in prev_list if elem not in found]
        for elem in to_remove:
            dev_name = "<unknown>"
            for dname, desc in devs.items():
                if desc["ip"] == elem:
                    dev_name = dname
                    break

            logger.info("Removing IP %s (for %s)", elem, dev_name)
            self.remove_from_set(sname, elem)
            changes = True

        if changes:
            content = self.get_set_content(sname)
            # logger.info("Updated IP whitelist: %s", content)
            logger.info("Updated IP whitelist contains %d elements.", len(content))


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

    # This will not work for now:
    # psr = context.build_parser("monitor")
    # psr.add_str("-i", dest="intf_name")("Interface to monitor.")

    psr = context.build_parser("update_ntp_list")

    psr = context.build_parser("update_mac_whitelist")
    # psr.add_str("config_name")("Config to write.")

    psr = context.build_parser("write")
    psr.add_str("config_name")("Config to write.")
    psr.add_flag("-d", "--dry-run", dest="dry_run")("Specify dryrun flag")
    comp.run()
