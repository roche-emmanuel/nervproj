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
            self.clone_repository(self.settings['dest_folder'])
            return True

        return False

    def clone_repository(self, dest_folder=None, proj=None):
        """Checkout the repository for the given project into the given local folder"""
        if proj is None:
            proj = self.ctx.get_current_project()

        if dest_folder is None:
            dest_folder = proj.get_name(False)
