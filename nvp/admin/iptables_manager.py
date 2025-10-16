"""IPTablesManager handling component"""

import logging
import re
import shlex
import time
from datetime import datetime

import nvp.core.utils as utl
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

NTP_SERVERS = {
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
    "131.107.13.100",
    "129.6.15.28",
}

WHITELIST_SET = "mac_whitelist"
BLOCKED_SET = "blocked_local_ips"


class IPTablesManager(NVPComponent):
    """IPTablesManager component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.ipv = 4
        self.dryrun = False
        self.state = None
        self.config = ctx.get_config().get("iptables")
        if self.config is None:
            self.config = self.ctx.get_project("NervHome").get_config().get("iptables")

        # Get the devices file list:
        self.devices = self.load_config_entry("devices")
        self.mac_groups = self.load_config_entry("mac_groups")
        self.internet_schedule = self.load_config_entry("internet_schedule")
        self.rules = self.load_config_entry("templates")

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

        if cmd == "update_dhcp_devices":
            self.update_dhcp_devices()
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

    def run_ip(self, args, retcode=False):
        """Run the ip command."""
        app = "ip"

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
        entries = self.rules[rname]

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

    def get_arp_ip_mapping(self):
        """Get the IP mapping with arp"""
        arp_output = self.run_arp("-n")

        # Regular expression to match IP, MAC, and Interface
        pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+(?:ether\s+([\da-f:]+)\s+)?\S*\s+(\S+)")

        # Extracted data:
        ip_map = {}

        for match in pattern.finditer(arp_output):
            ip = match.group(1)
            mac = match.group(2) if match.group(2) else "INCOMPLETE"
            if mac == "INCOMPLETE":
                # Ignore this entry:
                continue

            interface = match.group(3)
            if ip in ip_map:
                # add the MAC to the list:
                ip_map[ip].append((mac.upper(), interface))
            else:
                ip_map[ip] =[(mac.upper(), interface)]

        return ip_map
    
    def get_mac_ip_mapping(self):
        """Get the MAC/IP mapping with arp"""
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
        #
        # return {elem[1]: (elem[0], elem[2]) for elem in devices if elem[1] != "INCOMPLETE"}

        # Now turn this into a MAC map:
        mac_to_ip_interfaces = {}

        # Process each device in the list
        for ip, mac, interface in devices:
            # Skip incomplete entries if you don't want them
            if mac == "INCOMPLETE":
                continue

            # If this MAC is not in the dictionary yet, add it with an empty list
            if mac not in mac_to_ip_interfaces:
                mac_to_ip_interfaces[mac] = []

            # Add the IP/interface pair to this MAC's list
            mac_to_ip_interfaces[mac].append((ip, interface))

        return mac_to_ip_interfaces

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

        # Iterate on each ruleset:
        for days, rules in schedule.items():
            active_days = days.split("|")
            if day_str not in active_days:
                # Rules not applicable today
                continue

            for rule in rules:
                start_end = rule.split("-")
                # Get the start time:
                parts = start_end[0].split(":")
                if len(parts) == 2:
                    parts.append("0")
                start_ts = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                parts = start_end[1].split(":")
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

        self.create_set(sname, "hash:net", list(NTP_SERVERS))
        logger.info("Created NTP server list ipset %s", sname)

    def get_all_ref_ips(self, grp):
        """Get all the ref IPs for a given group."""
        ips = []
        devs = self.devices

        for elem in grp:
            ref_ips = devs[elem]["ip"]

            if isinstance(ref_ips, str):
                ref_ips = [ref_ips]

            ips.append(ref_ips[0])

        return ips

    def update_blocked_ip_list(self, set_name, ips, add_to_list):
        """Update the blocked IP set."""
        prev_block_list = self.get_set_content(set_name)
        for ip in ips:
            if ip in prev_block_list and not add_to_list:
                logger.info("Unblocking ip address %s", ip)
                self.remove_from_set(set_name, ip)
            elif ip not in prev_block_list and add_to_list:
                logger.info("Blocking ip address %s", ip)
                self.add_to_set(set_name, ip)

    def get_entry(self, sname, defval):
        """Retrieve a state value."""
        if self.state is None:
            state_file = self.get_path(self.ctx.get_home_dir(), ".nvp", "state_iptables.json")
            self.state = {}
            if self.file_exists(state_file):
                self.state = self.read_json(state_file) or {}

        return self.state.get(sname, defval)

    def set_entry(self, sname, val):
        """assign a state value."""
        state_file = self.get_path(self.ctx.get_home_dir(), ".nvp", "state_iptables.json")
        if self.state is None:
            self.state = {}
            if self.file_exists(state_file):
                self.state = self.read_json(state_file) or {}

        self.state[sname] = val
        self.write_json(self.state, state_file)

    def flush_ip_neighbours(self):
        """Flush the IP neighbours."""

        last_flush_time = self.get_entry("last_flush_time", 0)
        cur_time = time.time()

        # Use a delay of 10 minutes:
        if (cur_time - last_flush_time) > 600:
            self.set_entry("last_flush_time", cur_time)
            logger.info("Flushing IP neighbours.")

            utl.send_rocketchat_message(":warning: Flushing IP neighbours.")
            self.run_ip(["neigh", "flush", "all"])

        # read/write an ip state file:

    def mac_map_to_triplets(self, mac_map):
        """Convert mac map to triplets list."""
        tlist = []
        for mac, ips in mac_map.items():
            for ip, intf in ips:
                tlist.append(f"{mac.upper()}_{ip}_{intf}")
        return tlist

    def contains_map_ip_intf(self, tlist, mac, ip, intf):
        """Check if the triplet list contains a MAC/IP/INTF triplet."""
        key = f"{mac.upper()}_{ip}_{intf}"
        return key in tlist

    def create_ipsets(self):
        """Create the ipsets if missing."""
        if not self.has_set(WHITELIST_SET):
            logger.info("Creating set %s", WHITELIST_SET)
            self.create_set(WHITELIST_SET, "hash:net")

        if not self.has_set(BLOCKED_SET):
            logger.info("Creating set %s", BLOCKED_SET)
            self.create_set(BLOCKED_SET, "hash:net")

    def select_valid_ip(self, mac_map, triplets, dev_name, intf="eno2"):
        """Select a valid mac/ip pair."""
        devs = self.devices
        macs = devs[dev_name]["mac"]
        ips = devs[dev_name]["ip"]

        if isinstance(macs, str):
            macs = [macs]

        macs = [mac.upper() for mac in macs]

        if all(mac not in mac_map for mac in macs):
            # This device is not active:
            return (None, None)

        if isinstance(ips, str):
            ips = [ips]

        # Keep track of all valid triplets:
        valid_ips = []
        for mac in macs:
            for ip in ips:
                if self.contains_map_ip_intf(triplets, mac, ip, intf):
                    valid_ips.append((ip, mac))

        if len(valid_ips) == 0:
            # Did not find correct IP for that device:
            got_ips = []
            for mac in macs:
                if mac in mac_map:
                    got_ips += mac_map[mac]

            logger.error(
                "No valid Ip found for %s (MAC %s): expected: %s, got: %s",
                dev_name,
                macs,
                ips,
                got_ips,
            )
            self.flush_ip_neighbours()
            return (None, None)

        if len(valid_ips) > 1:
            count = self.get_entry("multiple_valid_ips_warning_count", 0)
            if count % 10 == 0:
                logger.warning("Found multiple valid ips for same device (%s): %s", dev_name, valid_ips)
            count += 1
            self.set_entry("multiple_valid_ips_warning_count", count)

        return valid_ips[0]

    def get_device_group(self, dev_name):
        """Get the group name for a given device."""
        for grp_name, devs in self.mac_groups.items():
            if dev_name in devs:
                return grp_name

        return None

    def is_in_schedule(self, dev_name):
        """Check if a given device name is current in schedule."""
        # Get the group containing this device:
        grp_name = self.get_device_group(dev_name)

        if grp_name is None:
            # Device is not in a group
            msg = f"No group found for device {dev_name}"
            self.warn(msg)
            utl.send_rocketchat_message(f":warning: {msg}")
            # Consider in schedule by default.
            return True, False
    
        # Check if there is a schedule for that group:
        sch = self.internet_schedule
        if grp_name not in sch:
            msg = f"No schedule specified for group {grp_name}"
            self.warn(msg)
            utl.send_rocketchat_message(f":warning: {msg}")
            return True, False
        

        if self.check_in_schedule(sch[grp_name]):
            # In schdule
            return True, False
        
        # We should also check here if we should enforce blocking this IP
        enforce_blocks = self.config.get("enforce_blocking", [])

        if grp_name in enforce_blocks:
            return False, True
        
        return False, False

    def consolidate_allowed_ips(self, allowed_ips):
        """Consolidate the allowed IPS."""
        # Once we have the list of allowed/blocked IPS we still need to check 
        # if we have any MAC address mismatch reported by arp:
        ip_map = self.get_arp_ip_mapping()

        # For each IP we get a list of (MAC, intf) elements:
        # Check each entry from our allowed list:
        final_allowed_ips = set()

        # Add all the non-user interface IPs from ARP:
        user_interfaces = ["eno1", "eno2", "macvlan-shim"]
        for ip, milist in ip_map.items():
            for mac, intf in milist:
                if intf not in user_interfaces:
                    # We expect the IP to start with 172.
                    if not ip.startswith("172."):
                        msg = f"Unexpected {ip} on interface {intf} (mac={mac})"
                        self.warn(msg)
                        utl.send_rocketchat_message(f":warning: {msg}")
                        continue

                    final_allowed_ips.add(ip)
                    break

        for ip, macs in allowed_ips.items():
            # Check if we currently have an arp entry for this IP:
            if ip in ip_map:
                # We have an entry on arp, so we check that the mac we expect is
                # indeed what we see:
                cur_macs = [mac for mac,_ in ip_map[ip]]
                valid_mac = any(mac in cur_macs for mac in macs)

                if not valid_mac:
                    msg = f"Detected invalid MACs {cur_macs} for IP {ip})"
                    self.warn(msg)
                    utl.send_rocketchat_message(f":warning: {msg}")

                # Note: may not add the IP as allowed here ?
            
            # Add the IP as valid:
            final_allowed_ips.add(ip)

        return final_allowed_ips

    def collect_allowed_ips(self):
        """Collect the list of currently allowed and blocked IPs."""
        allowed_ips = {}
        # and for each IP we map the corresponding allowed set of MAC addresses:

        blocked_ips = set()

        for dname, desc in self.devices.items():
            device_ips = desc["ip"] if isinstance(desc["ip"], list) else [desc["ip"]]

            # Given the device name, we can figure out here if it should be whitelisted or not:
            is_allowed, is_blocked = self.is_in_schedule(dname)

            if not is_allowed:
                # Check if we should block those IPs:
                if is_blocked:
                    # Add the corresponding IPs to the blocked list:
                    blocked_ips.update(set(device_ips))

                # Should not add the IPs to the allowed list:
                continue
            
            # Otherwise we add one entry for each IP with the corresponding list of MACs:
            device_macs = set(desc["mac"] if  isinstance(desc["mac"], list) else [desc["mac"]])

            for ip in device_ips:
                if ip in blocked_ips:
                    msg = f"Cannot allow IP {ip} as it is also in the enforced blocked list."
                    self.warn(msg)
                    utl.send_rocketchat_message(f":warning: {msg}")
                    continue

                if ip in allowed_ips:
                    # Update the existing set of MACs:
                    allowed_ips[ip].update(device_macs)
                else:
                    # Add a new set:
                    allowed_ips[ip] = device_macs

        allowed_ips = self.consolidate_allowed_ips(allowed_ips)

        return allowed_ips, blocked_ips
    
    def replace_set_content(self, set_name, new_ips, hint):
        """Replace a set content."""
        prev_content = set(self.get_set_content(set_name))

        to_add = new_ips - prev_content
        to_remove = prev_content - new_ips

        for ip in to_add:
            logger.info("%s ip address %s", hint, ip)
            self.add_to_set(set_name, ip)
        for ip in to_remove:
            logger.info("Un-%s ip address %s", hint, ip)
            self.remove_from_set(set_name, ip)

    def update_mac_wl(self):
        """Update the whitelisted IPs"""
        # create the set if needed:
        self.create_ipsets()

        # Get the list of allowed/blocked IPs:
        allowed_ips, blocked_ips = self.collect_allowed_ips()

        self.replace_set_content(WHITELIST_SET, allowed_ips, "WhiteListing")
        self.replace_set_content(BLOCKED_SET, blocked_ips, "Blocking")

    def update_mac_wl_v0(self):
        """Update the WAN access rule"""
        grps = self.mac_groups
        # logger.info("Found MAC groups:: %s", grps)

        enforce_blocks = self.config.get("enforce_blocking", [])
        mac_map = self.get_mac_ip_mapping()

        # create the set if needed:
        self.create_ipsets()

        # l0 = self.has_set(WHITELIST_SET)
        # logger.info("Has mac_whitelist: %s", l0)
        # l1 = self.has_set("blacklist")
        # logger.info("Has blacklist: %s", l1)

        devs = self.devices

        prev_list = self.get_set_content(WHITELIST_SET)
        # logger.info("Previous list contained %d elements", len(prev_list))
        changes = False
        found = []

        # First we add all the IPs that are not on the eno2/eno1/macvlan-shim interfaces:
        for mac, ips in mac_map.items():
            for ip, intf in ips:
                if intf in ["eno1", "eno2", "macvlan-shim"]:
                    continue

                if ip not in prev_list:
                    self.check(ip not in found, "Ip %s was already whitelisted.", ip)

                    logger.info("Adding IP %s for MAC %s on %s", ip, mac, intf)
                    self.add_to_set(WHITELIST_SET, ip)
                    changes = True
                    prev_list.append(ip)
                else:
                    found.append(ip)

        triplets = self.mac_map_to_triplets(mac_map)

        # Iterate on the enable groups:
        sch = self.internet_schedule
        for grp_name, schedule in sch.items():
            # logger.info("%s: %s", grp_name, state)
            # Add each element from that group to the set:
            grp = grps[grp_name]

            in_schedule = self.check_in_schedule(schedule)

            if grp_name in enforce_blocks:
                # We should update the list of blocked ips:
                self.update_blocked_ip_list(BLOCKED_SET, self.get_all_ref_ips(grp), not in_schedule)

            if in_schedule:
                for elem in grp:
                    valid_ip, valid_mac = self.select_valid_ip(mac_map, triplets, elem)

                    if valid_ip is None:
                        continue

                    if valid_ip not in prev_list:
                        logger.info(
                            "Adding IP %s for %s (grp: %s) (MAC: %s)",
                            valid_ip,
                            elem,
                            grp_name,
                            valid_mac,
                        )
                        self.add_to_set(WHITELIST_SET, valid_ip)
                        changes = True
                    else:
                        # logger.info("IP %s already in list", ip, mac)
                        found.append(valid_ip)

        # Remove the non wanted elements:
        to_remove = [elem for elem in prev_list if elem not in found]
        for elem in to_remove:
            dev_name = "<unknown>"
            for dname, desc in devs.items():
                device_ips = desc["ip"] if isinstance(desc["ip"], list) else [desc["ip"]]
                if elem in device_ips:
                    dev_name = dname
                    break

            logger.info("Removing IP %s (for %s)", elem, dev_name)
            self.remove_from_set(WHITELIST_SET, elem)
            changes = True

        if changes:
            content = self.get_set_content(WHITELIST_SET)
            # logger.info("Updated IP whitelist: %s", content)
            logger.info("Updated IP whitelist contains %d elements.", len(content))

    def parse_dhcp_config(self, dhcp_config_file):
        """Parse DHCP config file and extract host entries."""
        try:
            with open(dhcp_config_file, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: DHCP config file '{dhcp_config_file}' not found.")
            return None

        found_hosts = set()

        # Pattern to match host entries
        host_pattern = re.compile(r"^\s*host\s+(\S+)\s*\{")
        mac_pattern = re.compile(r"^\s*hardware\s+ethernet\s+([a-fA-F0-9:]+);")
        ip_pattern = re.compile(r"^\s*fixed-address\s+([0-9.]+);")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            host_match = host_pattern.match(line)

            if host_match:
                hostname = host_match.group(1)
                mac = None
                ip = None

                # Look for MAC and IP in the next few lines
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("}"):
                    mac_match = mac_pattern.match(lines[j])
                    ip_match = ip_pattern.match(lines[j])

                    if mac_match:
                        mac = mac_match.group(1).lower()
                    if ip_match:
                        ip = ip_match.group(1)

                    j += 1

                if mac and ip:
                    hstr = f"{hostname.lower()}|{mac.lower()}|{ip}"
                    # self.info("Found host in DHCP: %s", hstr)
                    found_hosts.add(hstr)

                i = j
            else:
                i += 1

        return found_hosts

    def update_dhcp_devices(self):
        """Update the dhcp devices."""
        dhcp_file = "/etc/dhcp/dhcpd.conf"
        found_hosts = self.parse_dhcp_config(dhcp_file)

        # Also collect the same list of entries from our devices:
        cur_hosts = set()
        hosts = {}
        for hname, desc in self.devices.items():
            mac = desc["mac"]
            ip = desc["ip"]
            if isinstance(mac, list):
                mac = mac[0]
            if isinstance(ip, list):
                ip = ip[0]

            hstr = f"{hname.lower()}|{mac.lower()}|{ip}"
            hosts[hname.lower()] = (mac.lower(), ip)
            cur_hosts.add(hstr)

        added_hosts = cur_hosts - found_hosts
        removed_hosts = found_hosts - cur_hosts

        update_needed = False
        if len(removed_hosts) != 0:
            self.info("Removing hosts: %s", removed_hosts)
            update_needed = True
        if len(added_hosts) != 0:
            self.info("Adding hosts: %s", added_hosts)
            update_needed = True

        if update_needed:
            # Rewrite the DCHP config file:
            header_file = self.ctx.resolve_path(self.config["dhcp_header"])
            # self.info("Should read header from: %s", header_file)

            header = self.read_text_file(header_file)

            # Now write the host lines:
            lines = [header]
            for hname, desc in hosts.items():
                lines.append(f"host {hname} " + "{")
                lines.append(f"  hardware ethernet {desc[0]};")
                lines.append(f"  fixed-address {desc[1]};")
                lines.append("}")

            content = "\n".join(lines)

            # self.info("Should write content: %s", content)

            # Write the file in the home dir:
            dst_file = self.get_path(self.ctx.get_home_dir(), "dhcpd.conf")
            self.info("Writing file %s...", dst_file)
            self.write_text_file(content, dst_file)

            # Backup previous file:
            self.info("Backing up %s...", dhcp_file)
            cmd = ["sudo", "mv", dhcp_file, dhcp_file + ".bak"]
            _, stderr, returncode = self.execute_command(cmd)

            if returncode != 0:
                logger.error("Failed to backup dhcpd config: %s", stderr)
                return

            # Move new file:
            self.info("Moving file %s...", dst_file)
            cmd = ["sudo", "mv", dst_file, dhcp_file]
            _, stderr, returncode = self.execute_command(cmd)

            if returncode != 0:
                logger.error("Failed to move dhcpd config: %s", stderr)
                return

            # Updating rights:
            self.info("Updating rights on %s...", dhcp_file)
            cmd = ["sudo", "chown", "root:root", dhcp_file]
            _, stderr, returncode = self.execute_command(cmd)

            if returncode != 0:
                logger.error("Failed to change rights on dhcpd config: %s", stderr)
                return

            self.info("Restarting DHCPD service...")
            self.restart_dhcpd_service()
            self.info("Done restarting DHCPD service.")
        else:
            self.info("No update needed for dhcpd service.")

    def restart_dhcpd_service(self):
        """Restart dhcpd service."""
        cmd = ["sudo", "service", "isc-dhcp-server", "restart"]
        stdout, stderr, returncode = self.execute_command(cmd)

        if returncode != 0:
            logger.error("Failed to restart dhcpd: %s", stderr)
            return None

        # Otherwise print the output:
        return stdout


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

    psr = context.build_parser("update_dhcp_devices")

    psr = context.build_parser("update_mac_whitelist")
    # psr.add_str("config_name")("Config to write.")

    psr = context.build_parser("write")
    psr.add_str("config_name")("Config to write.")
    psr.add_flag("-d", "--dry-run", dest="dry_run")("Specify dryrun flag")
    comp.run()
