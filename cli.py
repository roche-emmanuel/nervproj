"""Main module used for the environment setup of NervProj"""
import sys
import logging
import argparse

from nvp.admin_manager import AdminManager
from nvp.build_manager import BuildManager

# print(f"Received arguments: {sys.argv[1:]}")

# prepare the builder class:

logger = logging.getLogger(__name__)


# We build a parser for the arguments:
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

subparsers = parser.add_subparsers(title='main commands',
                                   dest='cmd',
                                   description='Available main commands below:',
                                   help='Main commands additional help')

home_p = subparsers.add_parser("home")

admin_p = subparsers.add_parser("admin")

sub_p = admin_p.add_subparsers(title='sub commands',
                               dest='sub_cmd',
                               description='Available sub commands below:',
                               help='Sub commands additional help')
cmd_p = sub_p.add_parser("install-cli")
# cmd_p.add_argument("install_cli_alias", nargs="?", default='nvp', type=str,
#                    help="Install bash alias for the NervProj CLI")

tools_p = subparsers.add_parser("tools")

sub_p = tools_p.add_subparsers(title='sub commands',
                               dest='sub_cmd',
                               description='Available sub commands below:',
                               help='Sub commands additional help')
cmd_p = sub_p.add_parser("install")

args = parser.parse_args()

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO,
                    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                    datefmt='%Y/%m/%d %H:%M:%S')


# logger.info("Received arguments: %s", vars(args))

if args.cmd == 'admin':
    AdminManager(vars(args))

if args.cmd == 'tools':
    BuildManager(vars(args))

    # if args.sub_cmd == 'install-cli':
    #     logger.info("Should install cli alias here with name %s", args.install_cli_alias)

# NVLBuilder(vars(args))

# Example of file patching code:
# file= self.get_path(build_dir, "src/core/linux/SDL_evdev_kbd.c")
# self.replace_in_file(file, "#include <unistd.h>", "#include <unistd.h>\n#include <stdlib.h>")
# self.replace_in_file(file, "atexit(kbd_cleanup_atexit);", "std::atexit(kbd_cleanup_atexit);")
