"""Collection of gitlab utility functions"""

import json
import re
import time
from datetime import datetime

import requests

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return GitlabManager(ctx)


# cf. Gitlab REST API documentation: https://docs.gitlab.com/ee/api/api_resources.html


class GitlabManager(NVPComponent):
    """Gitlab command manager class"""

    def __init__(self, ctx: NVPContext):
        """Gitlab commands manager constructor"""
        NVPComponent.__init__(self, ctx)

        self.base_url = None
        self.access_token = None
        self.proj_id = None

        # Read tokens from our main config before override:
        self.tokens = self.config.get("gitlab_access_tokens", {})

        self.config = ctx.get_config().get("gitlab")
        if self.config is None:
            self.config = self.ctx.get_project("NervHome").get_config().get("gitlab")

        self.label_sets = self.load_config_entry("label_sets")
        # self.info("Label sets: %s", self.label_sets)

        self.project_descs = self.load_config_entry("projects")
        # self.info("Gitlab project descs: %s", self.project_descs)

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
                    response = requests.request(
                        req_type, self.base_url + url, params=data, headers=headers, timeout=4.0
                    )
                    res = json.loads(response.text)
                elif req_type == "DELETE":
                    response = requests.request(req_type, self.base_url + url, headers=headers, timeout=4.0)
                    res = response.text
                else:
                    payload = json.dumps(data)
                    response = requests.request(
                        req_type, self.base_url + url, data=payload, headers=headers, timeout=4.0
                    )
                    res = json.loads(response.text)

                if not response.ok:
                    # This is an error:
                    self.error("Error detected: %s", res)
                    return None

                return res
            except requests.exceptions.RequestException as err:
                self.error("Request exception detected: %s", str(err))
            # except Exception as err:
            #     self.error('No response from URL: %s', str(err))

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

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "milestone.add":
            self.process_milestone_add()
            return True

        if cmd == "milestone.list":
            self.process_milestone_list()
            return True

        if cmd == "milestone.close":
            self.process_milestone_close()
            return True

        if cmd == "label.add":
            lbl_name = self.get_param("label_name")
            lbl_desc = self.get_param("description")
            lbl_color = self.get_param("label_color")
            lbl_priority = self.get_param("label_priority")

            self.add_label(lbl_name, lbl_color, lbl_desc, lbl_priority)
            return True

        if cmd == "label.list":
            self.list_labels()
            return True

        if cmd == "update.labels":
            pname = self.get_param("project_name", None)
            self.update_labels(pname)
            return True

        if cmd == "update.milestones":
            pname = self.get_param("project_name", None)
            self.update_milestones(pname)
            return True

        if cmd == "package.upload":
            package_name = self.get_param("package_name")
            package_version = self.get_param("package_version")
            file_name = self.get_param("file_name")
            pname = self.get_param("project_name", None)
            self.upload_package(pname, package_name, package_version, file_name, file_name)
            return True

        if cmd == "package.list":
            pname = self.get_param("project_name", None)
            res = self.list_packages(pname)
            self.info("List of packages for %s: %s", pname, self.pretty_print(res))
            return True

        if cmd == "package.remove":
            pname = self.get_param("project_name")
            pid = self.get_param("package_id")
            self.remove_package(pname, pid)
            return True

        if cmd == "package.list-files":
            pname = self.get_param("project_name")
            pid = self.get_param("package_id")
            res = self.list_package_files(pname, pid)
            self.info("List of packages files for %s: %s", pname, self.pretty_print(res))
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
            # self.info("Found line: %s", line)
            line = line.strip()

            if current_ctx == "remote":
                mval = url_pat.match(line)
                if mval is not None:
                    url = mval.group(1)
                    # self.info("Found url %s for remote %s", url, ctx_name)
                    desc = cfg["remotes"].setdefault(ctx_name, {})
                    desc["url"] = url

                    # find the git user prefix in the url
                    gitm = git_ssh_pat.match(url) if url.startswith("ssh://") else git_pat.match(url)
                    if gitm is None:
                        self.error("Cannot parse git URL: %s", url)
                    else:
                        # self.info("Groups: %s", gitm.groups())
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
                # self.info("Entering context %s %s", current_ctx, ctx_name)

        return cfg

    def setup_gitlab_api(self, project=None):
        """Setup the elements required for the gitlab API usage.
        return True on success, False otherwise."""
        if self.proj_id is not None:
            # Setup already done.
            return True

        proj_dir = None

        pname = self.get_param("project_name", None)
        if pname is not None:
            proj_dir = self.ctx.get_project(pname)
            self.info("Retrieved root dir %s for project %s", proj_dir, pname)

        if proj_dir is None:
            self.info("Setting up gitlab with proj: %s", project.get_name() if project is not None else "None")
            proj_dir = self.ctx.resolve_root_dir(project)

        if proj_dir is None:
            self.error("Cannot resolve current project root directory")
            return False

        git_cfg = self.read_git_config(proj_dir, ".git", "config")
        self.info("Read git config: %s", git_cfg)

        if git_cfg is None:
            self.error("Invalid git repository in %s", proj_dir)
            return False

        # get the origin remote:
        rname = "origin"
        if rname not in git_cfg["remotes"]:
            self.error("No '%s' remote git repository in %s", rname, proj_dir)
            return False

        remote_cfg = git_cfg["remotes"][rname]

        # retrieve the server from that remote:
        if "server" not in remote_cfg:
            self.error("No server extracted from remote config: %s", remote_cfg)
            return False

        sname = remote_cfg["server"]

        # Check if we have an access token for that server:
        if sname not in self.tokens:
            self.error("No access token available for gitlab server %s", sname)
            return False

        # self.info("Should use access token %s for %s", self.access_token, sname)
        self.setup_token(sname, remote_cfg["sub_path"].replace(".git", ""))

        # self.info("Using project URL encoded path: %s", self.proj_id)
        return True

    def setup_token(self, sname, url):
        """Setup the token."""
        # store the base_url and access_token:
        self.base_url = f"https://{sname}/api/v4"
        self.access_token = self.tokens[sname]

        # We should now URL encode the project name:
        self.proj_id = self.url_encode_path(url)

    def find_milestone_by_title(self, title, project=None):
        """Find a milestone by title"""

        if not self.setup_gitlab_api(project):
            return

        params = {}
        assert title is not None, "Invalid milestone title"
        params["title"] = title

        res = self.get(f"/projects/{self.proj_id}/milestones", params)
        # self.info("Got result: %s", self.pretty_print(res))
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
        self.info("Project url: %s", self.proj_id)
        res = self.post(f"/projects/{self.proj_id}/milestones", data)
        # res = self.post(f"/projects/10/milestones", data)
        # self.info("Got result: %s", self.pretty_print(res))
        if res is not None:
            mid = res["id"]
            web_url = res["web_url"]
            self.info("Created milestone '%s': id=%s, url=%s", data["title"], mid, web_url)

    def close_milestone(self, mid, project=None):
        """Close a milestone given its ID"""

        if not self.setup_gitlab_api(project):
            return
        data = {"state_event": "close"}

        res = self.put(f"/projects/{self.proj_id}/milestones/{mid}", data)
        self.info("Closed milestone: %s", self.pretty_print(res))

    def add_label(self, name, color, desc=None, priority=None, project=None, update=False):
        """Add a label to the given project using the provided data"""
        if not self.setup_gitlab_api(project):
            return

        # Data should contain:
        # name (str)
        # color (str) ex: "#FFAABB"
        # description (str)
        # priority (int>=0)

        assert name is not None, "Name is mandatory to create a label."
        assert color is not None, "Color is mandatory to create a label."

        data = {
            "color": color,
        }

        if not update:
            data["name"] = name

        if desc is not None:
            data["description"] = desc
        if priority is not None:
            data["priority"] = priority

        url = f"/projects/{self.proj_id}/labels"

        if update:
            res = self.put(f"{url}/{name}", data)
        else:
            res = self.post(url, data)

        # self.info("Got result: %s", self.pretty_print(res))
        if res is not None:
            lbl_id = res["id"]
            self.info("Created/Updated label '%s' with id=%s", name, lbl_id)

    def list_labels(self, project=None):
        """Get the list of labels for a project."""
        if not self.setup_gitlab_api(project):
            return

        data = {
            "per_page": 100,
        }

        res = self.get(f"/projects/{self.proj_id}/labels", data)
        # self.info("Got labels: %s", self.pretty_print(res))

        # Write a proper dict of labels:
        labels = {}
        for lbl in res:
            name = lbl["name"]
            if name in labels:
                self.error("Found duplicated label %s", name)
                continue
            labels[name] = {
                "color": lbl["color"],
                "description": lbl["description"],
                "priority": int(lbl["priority"]) if lbl["priority"] is not None else None,
            }

        # self.info("Found labels: %s", labels)
        self.check(len(labels) < 100, "Too many labels found!")

        return labels

    def get_project_id_from_name(self, project_name_or_path):
        """Get the numeric project ID from a project name or URL-encoded path.

        Args:
            project_name_or_path (str): Project name, path, or URL-encoded path

        Returns:
            int: Numeric project ID, or None if not found
        """
        # URL encode the project name/path in case it contains special characters
        encoded_name = self.url_encode_path(project_name_or_path)

        # Use the projects API endpoint to get project details
        res = self.get(f"/projects/{encoded_name}")

        if res is not None and "id" in res:
            project_id = res["id"]
            # self.info("Found project ID %d for '%s'", project_id, project_name_or_path)
            return project_id
        else:
            self.error("Could not find project ID for '%s'", project_name_or_path)
            return None

    def list_packages(self, proj_name):
        """List available packages for a given project."""
        self.check(proj_name in self.project_descs, "Cannot list packages for %s", proj_name)

        pdesc = self.project_descs[proj_name]
        self.setup_token(pdesc["server"], pdesc["url"])

        # Construct the API URL
        pid = self.get_project_id_from_name(pdesc["url"])
        url = f"/projects/{pid}/packages"

        res = self.get(url)
        return res

    def list_package_files(self, proj_name, package_id):
        """List available package files for a given project."""
        self.check(proj_name in self.project_descs, "Cannot list packages for %s", proj_name)

        pdesc = self.project_descs[proj_name]
        self.setup_token(pdesc["server"], pdesc["url"])

        # Construct the API URL
        pid = self.get_project_id_from_name(pdesc["url"])
        url = f"/projects/{pid}/packages/{package_id}/package_files"
        res = self.get(url)
        return res

    def remove_package(self, proj_name, package_id):
        """Remove a given package."""
        self.check(proj_name in self.project_descs, "Cannot list packages for %s", proj_name)

        pdesc = self.project_descs[proj_name]
        self.setup_token(pdesc["server"], pdesc["url"])

        # Construct the API URL
        pid = self.get_project_id_from_name(pdesc["url"])
        url = f"/projects/{pid}/packages/{package_id}"
        res = self.delete(url)
        return res

    def upload_package(self, proj_name, package_name, package_version, file_name, source_file):
        """Upload a package file to GitLab's generic package registry.

        Args:
            proj_name (str): Project name
            package_name (str): Name of the package
            package_version (str): Version of the package
            file_name (str): Name of the file as it will appear in the registry
            source_file (str): Path to the local file to upload

        Returns:
            dict: Response from GitLab API if successful, None if failed
        """
        if proj_name is None:
            # Get the project name from current folder:
            proj = self.ctx.get_current_project(True)
            if proj is None:
                self.error("Cannot resolved git project from folder %s", self.get_cwd())
                return

            proj_name = proj.get_name()
            self.info("Resolved project: %s", proj_name)

        self.check(proj_name in self.project_descs, "Cannot upload package for %s", proj_name)

        pdesc = self.project_descs[proj_name]
        self.setup_token(pdesc["server"], pdesc["url"])

        # Validate inputs
        assert package_name is not None, "Package name is mandatory"
        assert package_version is not None, "Package version is mandatory"
        assert file_name is not None, "File name is mandatory"
        assert source_file is not None, "Source file path is mandatory"

        # Check if source file exists
        if not self.file_exists(source_file):
            self.error("Source file does not exist: %s", source_file)
            return None

        # URL encode the file name to handle special characters
        encoded_file_name = file_name.replace("\\", "/")
        # encoded_file_name = self.url_encode_path(encoded_file_name)
        # self.info("Encoded filename is: %s", encoded_file_name)

        # Construct the API URL
        pid = self.get_project_id_from_name(pdesc["url"])
        # url = f"/projects/{self.proj_id}/packages/generic/{package_name}/{package_version}/{encoded_file_name}"
        url = f"/projects/{pid}/packages/generic/{package_name}/{package_version}/{encoded_file_name}"
        # url = f"/projects/{pdesc['url']}/packages/generic/{package_name}/{package_version}/{encoded_file_name}"

        # self.info("Using url: '%s'", url)
        ext = self.get_path_extension(file_name)
        is_text = ext in [".txt", ".log"]

        try:
            # Prepare headers
            headers = {
                "PRIVATE-TOKEN": self.access_token,
                "cache-control": "no-cache",
                # "content-type": "text/plain" if is_text else "application/octet-stream",
                # "content-type": "text/plain" if is_text else "application/zip",
                "content-type": "application/octet-stream",
                # "content-type": "application/zip",
            }

            # Open and upload the file
            with open(source_file, "rb") as file_data:
                response = requests.put(
                    self.base_url + url,
                    headers=headers,
                    data=file_data,
                    timeout=600.0 * 3,  # Longer timeout for file uploads: 30mins
                )

            if response.status_code == 201:
                self.info("Successfully uploaded package file: %s/%s/%s", package_name, package_version, file_name)

                # Try to parse JSON response, but handle cases where it might not be JSON
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # Return a simple success indicator if response isn't JSON
                    return {"status": "success", "status_code": 201}
            else:
                # Handle error responses
                try:
                    error_data = response.json()
                    self.error("Failed to upload package file. Status: %d, Error: %s", response.status_code, error_data)
                except json.JSONDecodeError:
                    self.error(
                        "Failed to upload package file. Status: %d, Response: %s", response.status_code, response.text
                    )
                return None

        except requests.exceptions.RequestException as err:
            self.error("Request exception during package upload: %s", str(err))
            return None
        except IOError as err:
            self.error("File I/O error during package upload: %s", str(err))
            return None
        except Exception as err:
            self.error("Unexpected error during package upload: %s", str(err))
            return None

    def update_labels(self, pname=None):
        """Update all the project labels."""
        if pname == "all":
            # Iterate on each project in this case:
            for pname in self.project_descs:
                self.update_labels(pname)
            return

        if pname is None:
            # Get the project name from current folder:
            proj = self.ctx.get_current_project(True)
            if proj is None:
                self.error("Cannot resolved git project from folder %s", self.get_cwd())
                return

            pname = proj.get_name()
            self.info("Resolved project: %s", pname)

        self.check(pname in self.project_descs, "Cannot update labels for %s", pname)

        pdesc = self.project_descs[pname]
        self.setup_token(pdesc["server"], pdesc["url"])
        self.info("Updating labels for %s", pname)

        # self.info("Should update labels here for %s", pname)
        labels = self.list_labels(pname)

        # Get the set of labels to use for this project:
        tgt_labels = {}
        for lset_name in pdesc["labels"]:
            # Get the label set:
            lset = self.label_sets[lset_name]
            for lname, desc in lset.items():
                data = {
                    "color": desc[0],
                    "description": desc[1],
                    "priority": desc[2] if len(desc) >= 3 else None,
                }
                tgt_labels[lname] = data

        # Iterate on those labels:
        for lname, desc in tgt_labels.items():
            if lname not in labels:
                self.info("Adding label %s to %s...", lname, pname)
                self.add_label(lname, desc["color"], desc["description"])
            elif labels[lname] != desc:
                self.info("Updating label %s in %s...", lname, pname)
                self.add_label(lname, desc["color"], desc["description"], update=True)

    def get_milestone_ids(self):
        """Retrieve the milestone ids."""
        now = datetime.now()

        # Current year and month
        cur_year = now.year % 100  # Get last 2 digits of year
        cur_month = now.month

        # Previous month
        if cur_month == 1:
            prev_year = (now.year - 1) % 100
            prev_month = 12
        else:
            prev_year = cur_year
            prev_month = cur_month - 1

        # Next month
        if cur_month == 12:
            next_year = (now.year + 1) % 100
            next_month = 1
        else:
            next_year = cur_year
            next_month = cur_month + 1

        return {
            "prev": (prev_year, prev_month),
            "cur": (cur_year, cur_month),
            "next": (next_year, next_month),
        }

    def update_milestones(self, pname=None):
        """Update the project default milestones."""
        if pname == "all":
            # Iterate on each project in this case:
            for pname in self.project_descs:
                self.update_milestones(pname)
            return

        if pname is None:
            # Get the project name from current folder:
            proj = self.ctx.get_current_project(True)
            if proj is None:
                self.error("Cannot resolved git project from folder %s", self.get_cwd())
                return

            pname = proj.get_name()
            self.info("Resolved project: %s", pname)

        self.check(pname in self.project_descs, "Cannot update milestones for %s", pname)

        pdesc = self.project_descs[pname]

        if pdesc.get("update_milestones", True) is not True:
            self.info("Ignoring milestones update for %s", pname)
            return

        self.setup_token(pdesc["server"], pdesc["url"])
        self.info("Updating milestones for %s", pname)

        # Figure out what are the previous/current/next milestone numbers:
        mids = self.get_milestone_ids()
        fmt = pdesc.get("milestone_format", "v%d.%d")

        for mtype, ids in mids.items():
            # Create the milestone if it doesn't exist yet:
            yn, mn = ids[0], ids[1]
            mname = fmt % (yn, mn)

            if self.find_milestone_by_title(mname) is None:
                self.info("Creating milestone '%s'", mname)
                data = {"title": mname}
                self.add_milestone(data)

            if mtype == "prev":
                mstone = self.find_milestone_by_title(mname)
                if mstone is None:
                    self.warn("No milestone found with title %s", mname)
                    continue

                if mstone["state"] == "active":
                    mid = mstone["id"]

                    # Close that milestone:
                    self.info("Closing milestone %s", mname)
                    self.close_milestone(mid)

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
        self.info("Update file result: %s", self.pretty_print(res))

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
        self.info("Create tag result: %s", self.pretty_print(res))

    def process_milestone_list(self):
        """List of the milestone available in the current project"""

        # self.info("Should list all milestones here from %s", self.proj)
        title = self.get_param("title")
        if title is not None:
            res = self.find_milestone_by_title(title)
        else:
            if not self.setup_gitlab_api():
                return
            res = self.get(f"/projects/{self.proj_id}/milestones")

        self.info("Got result: %s", self.pretty_print(res))

    def process_milestone_add(self):
        """Add a milestone in the current project given a title, desc
        start and end date"""

        # self.info("Should list all milestones here from %s", self.proj)
        title = self.get_param("title")
        desc = self.get_param("description")
        start_date = self.get_param("start_date")
        end_date = self.get_param("end_date")

        self.info(
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

        # self.info("Should list all milestones here from %s", self.proj)
        mid = self.settings["milestone_id"]

        if mid is None:
            title = self.settings["title"]
            assert title is not None, "Title or id are required to close a milestone."
            mstone = self.find_milestone_by_title(title)
            if mstone is None:
                self.warn("No milestone found with title %s", title)
                return
            mid = mstone["id"]

        self.close_milestone(mid)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.get_component("gitlab")

    # comp = context.register_component("gitlab", GitlabManager(context))

    psr = context.build_parser("milestone.add")
    psr.add_str("-p", "--project", dest="project")("Select the current sub-project")
    psr.add_str("-t", "--title", dest="title")("Title for the new milestone")
    psr.add_str("-d", "--desc", dest="description")("Description for the new milestone")
    psr.add_str("-s", "--start", dest="start_date")("Start date for the new milestone")
    psr.add_str("-e", "--end", dest="end_date")("End date for the new milestone")

    psr = context.build_parser("milestone.list")
    psr.add_str("-t", "--title", dest="title")("Title of the listed milestone")

    psr = context.build_parser("milestone.close")
    psr.add_str("-t", "--title", dest="title")("Title of the milestone to close")
    psr.add_int("--id", dest="milestone_id")("ID for the milestone to close")

    psr = context.build_parser("label.list")

    psr = context.build_parser("label.add")
    psr.add_str("label_name")("Label name")
    psr.add_str("label_color")("Label color")
    psr.add_str("-d", "--description", dest="description")("Label description")
    psr.add_int("-p", "--priority", dest="label_priority")("Label priority")

    psr = context.build_parser("update.labels")
    psr.add_str("-p", "--project", dest="project_name")("Project name")

    psr = context.build_parser("update.milestones")
    psr.add_str("-p", "--project", dest="project_name")("Project name")

    psr = context.build_parser("package.upload")
    psr.add_str("-p", "--project", dest="project_name")("Project name")
    psr.add_str("package_name")("Package name")
    psr.add_str("package_version")("Package version")
    psr.add_str("file_name")("File name")

    psr = context.build_parser("package.list")
    psr.add_str("project_name")("Project name")

    psr = context.build_parser("package.remove")
    psr.add_str("project_name")("Project name")
    psr.add_int("package_id")("Package id")

    psr = context.build_parser("package.list-files")
    psr.add_str("project_name")("Project name")
    psr.add_int("package_id")("Package_id")

    comp.run()


# Command examples:
# nvp gitlab package upload -p argus simcore-daily "26.01.29" simcore/guardian.igpack
