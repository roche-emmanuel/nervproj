"""Collection of admin utility functions"""
import os
import sys
import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = GitManager(ctx)
    ctx.register_component('git', comp)


class GitManager(NVPComponent):
    """Git command manager class"""

    def __init__(self, ctx: NVPContext):
        """Git commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        desc = {
            "git": {
                "clone": None
            }
        }
        ctx.define_subparsers("main", desc)
        psr = ctx.get_parser('main.git.clone')
        psr.add_argument("dest_folder", type=str, nargs='?', default=None,
                         help="Name of the folder where to checkout the project")

    def process_command(self, cmd0):
        """Re-implementation of the process_command method."""

        if cmd0 != 'git':
            return False

        cmd1 = self.ctx.get_command(1)
        # cmd2 = self.ctx.get_command(2)
        if cmd1 == 'clone':
            self.clone_project_repository(self.settings['dest_folder'])
            return True

        return False

    def clone_repository(self, url, dest_folder):
        """Clone a given url into a given folder"""

        # Ensure the parent folder exists:
        base_dir = self.get_parent_folder(dest_folder)
        self.make_folder(base_dir)

        tools = self.get_component('tools')

        # Build the git command:
        cmd = [tools.get_git_path(), "clone", url, dest_folder]

        # Execute the command:
        logger.info("Executing command: %s", cmd)
        self.execute(cmd)

    def clone_project_repository(self, dest_folder=None, proj=None):
        """Checkout the repository for the given project into the given local folder"""
        if proj is None:
            proj = self.ctx.get_current_project()

        if dest_folder is None:
            dest_folder = proj.get_name(False)

        # check if dest_folder is relative or absolute:
        if self.is_relative_path(dest_folder):
            logger.info("Current CWD: %s", self.get_cwd())
            dest_folder = self.get_path(self.get_cwd(), dest_folder)

        # get the project url:
        url = proj.get_repository_url()

        self.clone_repository(url, dest_folder)
