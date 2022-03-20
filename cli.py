"""Main module used for the environment setup of NervProj"""
import sys
import logging
import argparse

from nvp.admin_manager import AdminManager
from nvp.build_manager import BuildManager
from nvp.gitlab_manager import GitlabManager

# print(f"Received arguments: {sys.argv[1:]}")

# prepare the builder class:

logger = logging.getLogger(__name__)


def define_subparsers(parent, desc, lvl=0, pname="main", plist=None):
    """define subparsers recursively."""

    if plist is None:
        plist = {"main": parent}

    subparsers = parent.add_subparsers(title=f'Level{lvl} commands',
                                       dest=f'l{lvl}_cmd',
                                       description=f'Available level{lvl} commands below:',
                                       help=f'Level{lvl} commands additional help')
    for key, sub_desc in desc.items():
        logger.info("Adding parser for %s", key)
        ppp = subparsers.add_parser(key)
        sub_name = f"{pname}.{key}"
        plist[sub_name] = ppp

        # Check if we have more sub parsers:
        if sub_desc is not None:
            plist = define_subparsers(ppp, sub_desc, lvl+1, sub_name, plist)

    return plist


parser = argparse.ArgumentParser()

# cf. https://stackoverflow.com/questions/15301147/python-argparse-default-value-or-specified-value
parser.add_argument("--check-deps", dest='check_deps', nargs='?', type=str, const="all",
                    help="Check and build the dependencies required for NervProj")
parser.add_argument("--rebuild", dest='rebuild', action='store_true',
                    help="Force rebuilding from sources")
parser.add_argument("--install-python-requirements", dest='install_python_requirements', action='store_true',
                    help="Install the requirements for the python env.")
parser.add_argument("-v", "--verbose", dest='verbose', action='store_true',
                    help="Enable display of verbose debug outputs.")
parser.add_argument("-p", "--project", dest='project', type=str, default="none",
                    help="Select the current sub-project")


parser_desc = {
    "home": None,
    "admin": {
        "install-cli": None
    },
    "tools": {'install': {}},
    "milestone": {"add": {}, "list": {}},
}

parsers = define_subparsers(parser, parser_desc)
psr = parsers['main.milestone.add']
psr.add_argument("-p", "--project", dest='project', type=str, default="none",
                 help="Select the current sub-project")
psr.add_argument("-t", "--title", dest='title', type=str,
                 help="Title for the new milestone")
psr.add_argument("-d", "--desc", dest='description', type=str,
                 help="Description for the new milestone")
psr.add_argument("-s", "--start", dest='start_date', type=str,
                 help="Start date for the new milestone")
psr.add_argument("-e", "--end", dest='end_date', type=str,
                 help="End date for the new milestone")

args = parser.parse_args()

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO,
                    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                    datefmt='%Y/%m/%d %H:%M:%S')


# logger.info("Received arguments: %s", vars(args))

if args.l0_cmd == 'admin':
    AdminManager(vars(args))

if args.l0_cmd == 'tools':
    BuildManager(vars(args))

if args.l0_cmd == 'milestone':
    GitlabManager(vars(args))

    # if args.sub_cmd == 'install-cli':
    #     logger.info("Should install cli alias here with name %s", args.install_cli_alias)

# NVLBuilder(vars(args))

# Example of file patching code:
# file= self.get_path(build_dir, "src/core/linux/SDL_evdev_kbd.c")
# self.replace_in_file(file, "#include <unistd.h>", "#include <unistd.h>\n#include <stdlib.h>")
# self.replace_in_file(file, "atexit(kbd_cleanup_atexit);", "std::atexit(kbd_cleanup_atexit);")
