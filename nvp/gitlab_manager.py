"""Collection of gitlab utility functions"""
import logging

from nvp.manager_base import ManagerBase

logger = logging.getLogger(__name__)


class GitlabManager(ManagerBase):
    """Gitlab command manager class"""

    def __init__(self, settings):
        """Gitlab commands manager constructor"""
        ManagerBase.__init__(self, settings)

        self.proj = None
        self.process_command()

    def process_command(self):
        """Process a command"""
        pname = self.settings['project']

        for pdesc in self.config.get("projects", []):
            if pname in pdesc['names']:
                self.proj = pdesc

        if self.proj is None:
            logger.warning("Invalid project '%s'", pname)
            return

        cmd0 = self.settings['l0_cmd']
        cmd1 = self.settings['l1_cmd']

        handler = self.get_method(f"process_{cmd0}_{cmd1}")
        if not handler:
            logger.warning("No handler available for '%s %s'", cmd0, cmd1)
            return

        handler()

    def has_project(self, pname):
        """Check if a given project should be considered available"""
        for pdesc in self.config.get("projects", []):
            if pname in pdesc['names']:
                return True

        return False

    def get_project_path(self, pname):
        """Search for the location of a project given its name"""

        proj_path = None
        for pdesc in self.config.get("projects", []):
            if pname in pdesc['names']:
                # Select the first valid path for that project:
                proj_path = self.select_first_valid_path(pdesc['paths'])
                break

        assert proj_path is not None, f"No valid path for project '{pname}'"

        # Return that project path:
        return proj_path

    def process_milestone_list(self):
        """List of the milestone available in the current project"""

        logger.info("Should list all milestones here from %s", self.proj)
