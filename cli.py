"""Main module used for the environment setup of NervProj"""
import sys
import logging
import argparse

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

subparsers = parser.add_subparsers(title='subcommands',
                                   dest='cmd',
                                   description='Available subcommands',
                                   help='Subcommands additional help')

admin_p = subparsers.add_parser("admin")

sub_p = admin_p.add_subparsers(help='sub-sub-command help', dest='sub_cmd')
cmd_p = sub_p.add_parser("install-cli-alias")
cmd_p.add_argument("install_cli_alias", nargs="?", default='nv_cli', type=str,
                   help="Install bash alias for the NervProj CLI")


args = parser.parse_args()

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO,
                    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                    datefmt='%Y/%m/%d %H:%M:%S')


logger.info("Received arguments: %s", vars(args))


# Handle the args:
if args.cmd == 'admin':
    if args.sub_cmd == 'install-cli-alias':
        logger.info("Should install cli alias here with name %s", args.install_cli_alias)

# NVLBuilder(vars(args))

# Example of file patching code:
# file= self.get_path(build_dir, "src/core/linux/SDL_evdev_kbd.c")
# self.replace_in_file(file, "#include <unistd.h>", "#include <unistd.h>\n#include <stdlib.h>")
# self.replace_in_file(file, "atexit(kbd_cleanup_atexit);", "std::atexit(kbd_cleanup_atexit);")
