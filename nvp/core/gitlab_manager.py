"""Collection of gitlab utility functions"""
import json
import logging
import re
import time

import requests

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return GitlabManager(ctx)


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

        headers = {"content-type": "application/json", "cache-control": "no-cache"}

        assert self.base_url is not None, "Invalid base url."

        if auth:
            assert self.access_token is not None, "Invalid access token."
            headers["PRIVATE-TOKEN"] = self.access_token

        try_count = 0
        while max_retries <= 0 or try_count < max_retries:
            try:
                if req_type == "GET":
                    response = requests.request(req_type, self.base_url + url, params=data, headers=headers)
                    res = json.loads(response.text)
                elif req_type == "DELETE":
                    response = requests.request(req_type, self.base_url + url, headers=headers)
                    res = response.text
                else:
                    payload = json.dumps(data)
                    response = requests.request(req_type, self.base_url + url, data=payload, headers=headers)
                    res = json.loads(response.text)

                if not response.ok:
                    # This is an error:
                    logger.error("Error detected: %s", res)
                    return None

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

    def process_command(self, cmd0):
        """Process a command"""

        if cmd0 == "milestone":
            cmd1 = self.ctx.get_command(1)

            hname = f"process_{cmd0}" if cmd1 is None else f"process_{cmd0}_{cmd1}"

            handler = self.get_method(hname)
            if not handler:
                logger.warning("No handler available with name '%s'", hname)
            else:
                handler()

            return True

        return False

    def read_git_config(self, *parts):
        """Read the important git config elements from a given file"""
        cfg_file = self.get_path(*parts)

        if not self.file_exists(cfg_file):
            return None

        cfg = {"remotes": {}}

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
                    desc = cfg["remotes"].setdefault(ctx_name, {})
                    desc["url"] = url

                    # find the git user prefix in the url
                    gitm = git_ssh_pat.match(url) if url.startswith("ssh://") else git_pat.match(url)
                    if gitm is None:
                        logger.error("Cannot parse git URL: %s", url)
                    else:
                        # logger.info("Groups: %s", gitm.groups())
                        ngrp = len(gitm.groups())
                        desc["server"] = gitm.group(1)
                        if ngrp == 2:
                            desc["sub_path"] = gitm.group(2)
                        else:
                            desc["port"] = int(gitm.group(2)[1:])
                            desc["sub_path"] = gitm.group(3)

            mval = ctx_pat.match(line)
            if mval is not None:
                current_ctx = mval.group(1)
                ctx_name = mval.group(2)
                # logger.info("Entering context %s %s", current_ctx, ctx_name)

        return cfg

    def setup_gitlab_api(self, project=None):
        """Setup the elements required for the gitlab API usage.
        return True on success, False otherwise."""

        proj_dir = self.ctx.resolve_root_dir(project)

        if proj_dir is None:
            logger.error("Cannot resolve current project root directory")
            return False

        git_cfg = self.read_git_config(proj_dir, ".git", "config")
        logger.debug("Read git config: %s", git_cfg)

        if git_cfg is None:
            logger.error("Invalid git repository in %s", proj_dir)
            return False

        # get the origin remote:
        rname = "origin"
        if rname not in git_cfg["remotes"]:
            logger.error("No '%s' remote git repository in %s", rname, proj_dir)
            return False

        remote_cfg = git_cfg["remotes"][rname]

        # retrieve the server from that remote:
        if "server" not in remote_cfg:
            logger.error("No server extracted from remote config: %s", remote_cfg)
            return False

        sname = remote_cfg["server"]

        # Check if we have an access token for that server:
        tokens = self.config.get("gitlab_access_tokens", {})

        if sname not in tokens:
            logger.error("No access token availble for gitlab server %s", sname)
            return False

        # logger.info("Should use access token %s for %s", self.access_token, sname)

        # store the base_url and access_token:
        self.base_url = f"https://{sname}/api/v4"
        self.access_token = tokens[sname]

        # We should now URL encode the project name:
        self.proj_id = self.url_encode_path(remote_cfg["sub_path"].replace(".git", ""))

        # logger.info("Using project URL encoded path: %s", self.proj_id)
        return True

    def find_milestone_by_title(self, title, project=None):
        """Find a milestone by title"""

        if not self.setup_gitlab_api(project):
            return

        params = {}
        assert title is not None, "Invalid milestone title"
        params["title"] = title

        res = self.get(f"/projects/{self.proj_id}/milestones", params)
        # logger.info("Got result: %s", self.pretty_print(res))
        if len(res) == 0:
            return None

        # Typical result:
        # { 'created_at': '2022-03-21T15:16:22.451Z',
        # 'description': 'Automatically generated milestone for SimCore v22.4',
        # 'due_date': '2022-04-30',
        # 'id': 114,
        # 'iid': 88,
        # 'project_id': 98,
        # 'start_date': '2022-04-01',
        # 'state': 'active',
        # 'title': 'SimCore v22.4',
        # 'updated_at': '2022-03-21T15:16:22.451Z',
        # 'web_url': 'https://gitlab.gmv-insyen.com/core/simcore/-/milestones/88'}

        return res[0]

    def add_milestone(self, data, project=None):
        """Add a milestone to the given project using the provided data"""
        if not self.setup_gitlab_api(project):
            return

        assert data["title"] is not None, "Title is mandatory to create a milestone."
        logger.info("Project url: %s", self.proj_id)
        res = self.post(f"/projects/{self.proj_id}/milestones", data)
        # res = self.post(f"/projects/10/milestones", data)
        # logger.info("Got result: %s", self.pretty_print(res))
        if res is not None:
            mid = res["id"]
            web_url = res["web_url"]
            logger.info("Created milestone '%s': id=%s, url=%s", data["title"], mid, web_url)

    def close_milestone(self, mid, project=None):
        """Close a milestone given its ID"""

        if not self.setup_gitlab_api(project):
            return
        data = {"state_event": "close"}

        res = self.put(f"/projects/{self.proj_id}/milestones/{mid}", data)
        logger.info("Closed milestone: %s", self.pretty_print(res))

    def update_file(self, data, project=None):
        """Send an update to a single file given the input data.
        Data should contain the following elements at least:
        data = {
            'file_path': "sources/scMX/include/mx/version.h",
            'branch': 'master',
            'author_email': 'eroche@gmv.com',
            'author_name': 'manu',
            'content': content,
            'commit_message': f"Automatic update to version v{year-2000}.{month}"
        }

        See https://docs.gitlab.com/ee/api/repository_files.html#create-new-file-in-repository
        for more details."""

        if not self.setup_gitlab_api(project):
            return

        # Ensure the file path is url-encoded:
        src_path = data["file_path"]
        del data["file_path"]
        fpath = self.url_encode_path(src_path)

        res = self.put(f"/projects/{self.proj_id}/repository/files/{fpath}", data)
        logger.info("Update file result: %s", self.pretty_print(res))

    def create_tag(self, data, project=None):
        """Create a tag with the given data on the target project,
        data should contain the following:
        data = {
            'tag_name': title,
            'ref': 'master',
            'message': f"Automatic tag generated for {title}"
        }

        See https://docs.gitlab.com/ee/api/tags.html#create-a-new-tag
        for more details."""

        if not self.setup_gitlab_api(project):
            return

        res = self.post(f"/projects/{self.proj_id}/repository/tags", data)
        logger.info("Create tag result: %s", self.pretty_print(res))

    def process_milestone_list(self):
        """List of the milestone available in the current project"""

        # logger.info("Should list all milestones here from %s", self.proj)
        title = self.settings["title"]
        if title is not None:
            res = self.find_milestone_by_title(title)
        else:
            if not self.setup_gitlab_api():
                return
            res = self.get(f"/projects/{self.proj_id}/milestones")

        logger.info("Got result: %s", self.pretty_print(res))

    def process_milestone_add(self):
        """Add a milestone in the current project given a title, desc
        start and end date"""

        # logger.info("Should list all milestones here from %s", self.proj)
        title = self.settings["title"]
        desc = self.settings["description"]
        start_date = self.settings["start_date"]
        end_date = self.settings["end_date"]

        logger.info(
            "Should add a new milestone with: title=%s, desc=%s, start_date=%s, end_date=%s",
            title,
            desc,
            start_date,
            end_date,
        )

        data = {"title": title}
        if desc is not None:
            data["description"] = desc
        if start_date is not None:
            data["start_date"] = start_date
        if end_date is not None:
            data["due_date"] = end_date

        self.add_milestone(data)

    def process_milestone_close(self):
        """Close a milestone in the current project given a title or id"""

        # logger.info("Should list all milestones here from %s", self.proj)
        mid = self.settings["milestone_id"]

        if mid is None:
            title = self.settings["title"]
            assert title is not None, "Title or id are required to close a milestone."
            mstone = self.find_milestone_by_title(title)
            if mstone is None:
                logger.warning("No milestone found with title %s", title)
                return
            mid = mstone["id"]

        self.close_milestone(mid)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("gitlab")

    context.define_subparsers("main", {"milestone": ["add", "list", "close"]})

    psr = context.get_parser("main.milestone.add")
    psr.add_argument("-p", "--project", dest="project", type=str, default="none", help="Select the current sub-project")
    psr.add_argument("-t", "--title", dest="title", type=str, help="Title for the new milestone")
    psr.add_argument("-d", "--desc", dest="description", type=str, help="Description for the new milestone")
    psr.add_argument("-s", "--start", dest="start_date", type=str, help="Start date for the new milestone")
    psr.add_argument("-e", "--end", dest="end_date", type=str, help="End date for the new milestone")

    psr = context.get_parser("main.milestone.list")
    psr.add_argument("-t", "--title", dest="title", type=str, help="Title of the listed milestone")

    psr = context.get_parser("main.milestone.close")
    psr.add_argument("-t", "--title", dest="title", type=str, help="Title for the milestone to close")
    psr.add_argument("--id", dest="milestone_id", type=int, help="ID for the milestone to close")

    comp.run()
