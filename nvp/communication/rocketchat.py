"""Rocketchat utility functions"""

import json
import logging
import time

import requests

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return RocketChat(ctx)


class RocketChat(NVPComponent):
    """RocketChat component used to send automatic messages ono rocketchat server"""

    def __init__(self, ctx: NVPContext):
        """Script runner constructor"""
        NVPComponent.__init__(self, ctx)

        # Get the config for this component:
        self.config = ctx.get_config().get("rocketchat", None)

        self.user_id = None
        self.token = None
        self.base_url = None

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "send":
            msg = self.get_param("message")
            channel = self.get_param("channel")
            self.send_message(msg, channel=channel)
            return True

        return False

    def send_message(self, message, channel=None, max_retries=5):
        """Method used to send a message on the configured rocketchat server."""
        # logger.info("Should send the rocketchat message: '%s'", message)

        if self.config is None:
            logger.error("No configuration provided for rocketchat: cannot send message:\n%s", message)
            return False

        # assert self.config is not None, "No configuration provided for rocketchat."

        self.user_id = self.config["user_id"]
        self.token = self.config["token"]
        self.base_url = self.config["base_url"]

        if channel is None:
            channel = self.config["default_channel"]

        infos = self.get_channel_infos(channel, max_retries=max_retries)
        if infos is None:
            infos = self.get_group_infos(channel, max_retries=max_retries)

        if infos is None:
            logger.error("Cannot find channel with name '%s'", channel)
            return False

        msg = {"rid": infos["_id"], "msg": message}

        res = self.post("/api/v1/chat.sendMessage", {"message": msg}, max_retries=max_retries)

        if res is None or "success" not in res or res["success"] is False:
            logger.error("Cannot send rocketchat message: %s", res)
            return False

        return True

    def send_request(self, req_type, url, data, max_retries=5, auth=True):
        """Send a REST request to the rocketchat server"""

        # logDEBUG("Sending payload: %s" % payload)
        headers = {"content-type": "application/json", "cache-control": "no-cache"}

        if auth:
            headers["X-Auth-Token"] = self.token
            headers["X-User-Id"] = self.user_id

        try_count = 0
        while max_retries <= 0 or try_count < max_retries:
            try:
                if req_type == "GET":
                    response = requests.request(req_type, self.base_url + url, params=data, headers=headers)
                else:
                    payload = json.dumps(data)
                    response = requests.request(req_type, self.base_url + url, data=payload, headers=headers)
                res = json.loads(response.text)
                return res
            except requests.exceptions.RequestException as err:
                logger.error("Request exception detected: %s", str(err))

            # wait 1 seconds:
            time.sleep(2)

            # Increment the try count:
            try_count += 1

        return None

    def get(self, url, data, max_retries=5, auth=True):
        """Send a get request to the server"""
        return self.send_request("GET", url, data, max_retries, auth)

    def post(self, url, data, max_retries=5, auth=True):
        """Send a post request to the server"""
        return self.send_request("POST", url, data, max_retries, auth)

    def get_channel_infos(self, chname, max_retries=5):
        """Retrieve channel infos"""
        res = self.get("/api/v1/channels.info", {"roomName": chname}, max_retries=max_retries)

        # Res might be none in case of network failure:
        if res is None:
            return None

        # logDEBUG("Result: %s" % res)
        # CHECK(res['success']==True, "Cannot retrieve channel infos: %s" % res)
        # return res['channel']
        # Res might be none:
        if "success" in res and res["success"]:
            return res["channel"]
        return None

    def get_group_infos(self, chname, max_retries=5):
        """Retrieve group infos"""
        res = self.get("/api/v1/groups.info", {"roomName": chname}, max_retries=max_retries)

        # Res might be none in case of network failure:
        if res is None:
            return None

        # logDEBUG("Result: %s" % res)
        # CHECK(res['success']==True, "Cannot retrieve group infos: %s" % res)
        # return res['group']
        if "success" in res and res["success"]:
            return res["group"]
        return None


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("rchat", RocketChat(context))

    context.define_subparsers(
        "main",
        {
            "send": None,
        },
    )

    psr = context.get_parser("main.send")
    psr.add_argument("message", type=str, help="Simple message that we should send")
    psr.add_argument("-c", "--channel", dest="channel", type=str, help="Channel where to send the message.")

    comp.run()
