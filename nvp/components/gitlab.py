"""Collection of gitlab utility functions"""
import logging
import sys
import re
import time
import json
import requests

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = GitlabManager(ctx)
    ctx.register_component('gitlab', comp)

# cf. Gitlab REST API documentation: https://docs.gitlab.com/ee/api/api_resources.html


class GitlabManager(NVPComponent):
    """Gitlab command manager class"""

    def __init__(self, ctx: NVPContext):
        """Gitlab commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        self.proj = None
        self.base_url = None
        self.access_token = None
        self.proj_id = None

    def send_request(self, req_type, url, data=None, max_retries=5, auth=True):
        """Method used to send a generic request to the server."""

        headers = {'content-type': "application/json", 'cache-control': "no-cache"}

        assert self.base_url is not None, "Invalid base url."

        if auth:
            assert self.access_token is not None, "Invalid access token."
            headers['PRIVATE-TOKEN'] = self.access_token

        try_count = 0
        while max_retries <= 0 or try_count < max_retries:
            try:
                if req_type == "GET":
                    response = requests.request(req_type, self.base_url+url, params=data, headers=headers)
                    res = json.loads(response.text)
                elif req_type == "DELETE":
                    response = requests.request(req_type, self.base_url+url, headers=headers)
                    res = response.text
                else:
                    payload = json.dumps(data)
                    response = requests.request(req_type, self.base_url+url, data=payload, headers=headers)
                    res = json.loads(response.text)
                return res
            except requests.exceptions.RequestException as err:
                logger.error("Request exception detected: %s", str(err))
            # except Exception as err:
            #     logger.error('No response from URL: %s', str(err))

            # wait 1 seconds:
            time.sleep(2)

            # Increment the try count:
            try_count += 1

        return None

    def get(self, url, data=None, max_retries=5, auth=True):
        """Send a get request"""
        return self.send_request("GET", url, data, max_retries, auth)

    def post(self, url, data, max_retries=5, auth=True):
        """Send a post request"""
        return self.send_request("POST", url, data, max_retries, auth)

    def put(self, url, data, max_retries=5, auth=True):
        """Send a put request"""
        return self.send_request("PUT", url, data, max_retries, auth)

    def delete(self, url, data=None, max_retries=5, auth=True):
        """Send a delete request"""
        return self.send_request("DELETE", url, data, max_retries, auth)

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
        cmd1 = self.settings.get('l1_cmd', None)
        hname = f"process_{cmd0}" if cmd1 is None else f"process_{cmd0}_{cmd1}"

        handler = self.get_method(hname)
        if not handler:
            logger.warning("No handler available with name '%s'", hname)
            return

        handler()

    def has_project(self, pname):
        """Check if a given project should be considered available"""
        for pdesc in self.config.get("projects", []):
            if pname in pdesc['names']:
                return True

        return False

    def get_project_path(self, pname=None):
        """Search for the location of a project given its name"""

        proj_path = None
        def_paths = self.config.get("project_paths", [])

        proj_desc = None
        if pname is None:
            assert self.proj is not None, "Invalid current project."
            proj_desc = self.proj
        else:
            for pdesc in self.config.get("projects", []):
                if pname in pdesc['names']:
                    proj_desc = pdesc
                    break

        assert proj_desc is not None, f"Invalid project {pname}"

        all_paths = [self.get_path(base_path, proj_name) for base_path in def_paths
                     for proj_name in proj_desc['names']]

        if 'paths' in proj_desc:
            all_paths = proj_desc['paths'] + all_paths

        proj_path = self.ctx.select_first_valid_path(all_paths)

        assert proj_path is not None, f"No valid path for project '{pname}'"

        # Return that project path:
        return proj_path

    def read_git_config(self, *parts):
        """Read the important git config elements from a given file"""
        cfg_file = self.get_path(*parts)

        if not self.file_exists(cfg_file):
            return None

        cfg = {
            'remotes': {}
        }

        # Read the config file and split on lines:
        lines = self.read_text_file(cfg_file).split("\n")

        current_ctx = None
        ctx_name = None

        # Example data:
        # [remote "gitlab"]
        #   url = ssh://git@gitlab.nervtech.org:22002/gmv/simcore.git

        ctx_pat = re.compile(r"^\[([^\s]+)\s\"([^\"]+)\"\]$")
        url_pat = re.compile(r"^url\s*=\s*(.*)$")

        git_pat = re.compile(r"^git@([^:]+):(.*)$")
        git_ssh_pat = re.compile(r"^ssh://git@([^:/]+)(:[0-9]+)?/(.*)$")

        for line in lines:
            # logger.info("Found line: %s", line)
            line = line.strip()

            if current_ctx == "remote":
                mval = url_pat.match(line)
                if mval is not None:
                    url = mval.group(1)
                    # logger.info("Found url %s for remote %s", url, ctx_name)
                    desc = cfg['remotes'].setdefault(ctx_name, {})
                    desc['url'] = url

                    # find the git user prefix in the url
                    gitm = git_ssh_pat.match(url) if url.startswith("ssh://") else git_pat.match(url)
                    if gitm is None:
                        logger.error("Cannot parse git URL: %s", url)
                    else:
                        # logger.info("Groups: %s", gitm.groups())
                        ngrp = len(gitm.groups())
                        desc['server'] = gitm.group(1)
                        if ngrp == 2:
                            desc['sub_path'] = gitm.group(2)
                        else:
                            desc['port'] = int(gitm.group(2)[1:])
                            desc['sub_path'] = gitm.group(3)

            mval = ctx_pat.match(line)
            if mval is not None:
                current_ctx = mval.group(1)
                ctx_name = mval.group(2)
                # logger.info("Entering context %s %s", current_ctx, ctx_name)

        return cfg

    def setup_gitlab_api(self):
        """Setup the elements required for the gitlab API usage.
        return True on success, False otherwise."""
        proj_dir = self.get_project_path()

        git_cfg = self.read_git_config(proj_dir, ".git", "config")
        logger.info("Read git config: %s", git_cfg)

        if git_cfg is None:
            logger.error("Invalid git repository in %s", proj_dir)
            return False

        # get the origin remote:
        rname = "origin"
        if not rname in git_cfg['remotes']:
            logger.error("No '%s' remote git repository in %s", rname, proj_dir)
            return False

        remote_cfg = git_cfg['remotes'][rname]

        # retrieve the server from that remote:
        if not 'server' in remote_cfg:
            logger.error("No server extracted from remote config: %s", remote_cfg)
            return False

        sname = remote_cfg['server']

        # Check if we have an access token for that server:
        tokens = self.config.get("gitlab_access_tokens", {})

        if not sname in tokens:
            logger.error("No access token availble for gitlab server %s", sname)
            return False

        # logger.info("Should use access token %s for %s", self.access_token, sname)

        # store the base_url and access_token:
        self.base_url = f"https://{sname}/api/v4"
        self.access_token = tokens[sname]

        # We should now URL encode the project name:
        self.proj_id = remote_cfg['sub_path'].replace(".git", "").replace("/", "%2F")

        # logger.info("Using project URL encoded path: %s", self.proj_id)
        return True

    def process_milestone_list(self):
        """List of the milestone available in the current project"""

        # logger.info("Should list all milestones here from %s", self.proj)
        if not self.setup_gitlab_api():
            return

        res = self.get(f"/projects/{self.proj_id}/milestones")
        logger.info("Got result: %s", self.pretty_print(res))

    def process_milestone_add(self):
        """Add a milestone in the current project given a title, desc
        start and end date"""

        # logger.info("Should list all milestones here from %s", self.proj)
        if not self.setup_gitlab_api():
            return

        title = self.settings['title']
        desc = self.settings['description']
        start_date = self.settings['start_date']
        end_date = self.settings['end_date']

        logger.info("Should add a new milestone with: title=%s, desc=%s, start_date=%s, end_date=%s",
                    title, desc, start_date, end_date)

        assert title is not None, "Title is mandatory to create a milestone."

        data = {'title': title}
        if desc is not None:
            data['description'] = desc
        if start_date is not None:
            data['start_date'] = start_date
        if end_date is not None:
            data['due_date'] = end_date

        logger.info("Project url: %s", self.proj_id)
        res = self.post(f"/projects/{self.proj_id}/milestones", data)
        # res = self.post(f"/projects/10/milestones", data)
        # logger.info("Got result: %s", self.pretty_print(res))
        mid = res['id']
        web_url = res['web_url']
        logger.info("Created milestone '%s': id=%s, url=%s", title, mid, web_url)

    def process_get_dir(self):
        """Retrieve the root dir for a given sub project and
        return that path on stdout"""

        proj_dir = self.get_project_path()

        if self.ctx.is_windows():
            proj_dir = self.to_cygwin_path(proj_dir)

        sys.stdout.write(proj_dir)
        sys.stdout.flush()
