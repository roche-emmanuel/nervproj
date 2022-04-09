"""Rocketchat utility functions"""
import logging
import os
import json
import requests
import time

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def register_component(ctx: NVPContext):
    """Register this component in the given context"""
    comp = RocketChat(ctx)
    ctx.register_component('rocketchat', comp)


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

        # Also extend the parser:
        ctx.define_subparsers("main", {'rchat': None})
        psr = ctx.get_parser('main.rchat')
        psr.add_argument("message", type=str,
                         help="Message that should be send on the rocketchat server")

    def process_command(self, cmd):
        """Check if this component can process the given command"""

        if cmd == 'rchat':
            msg = self.ctx.get_settings()['message']
            self.send_message(msg)
            return True

        return False

    def send_message(self, message):
        """Method used to send a message on the configured rocketchat server."""
        logger.info("Should send the rocketchat message: '%s'", message)

        assert self.config is not None, "No configuration provided for rocketchat."

        self.user_id = self.config['user_id']
        self.token = self.config['token']
        self.base_url = self.config['base_url']

        channel = self.config['default_channel']

        infos = self.get_channel_infos(channel)
        if infos is None:
            infos = self.get_group_infos(channel)

        assert infos is not None, f"Cannot find channel with name {channel}"

        msg = {
            'rid': infos['_id'],
            'msg': message
        }

        res = self.post("/api/v1/chat.sendMessage", {'message': msg})

        if 'success' not in res or res['success'] is False:
            logger.error("Cannot send rocketchat message: %s", res)
            return False

        return True

    def send_request(self, req_type, url, data, max_retries=5, auth=True):
        """Send a REST request to the rocketchat server"""

        # logDEBUG("Sending payload: %s" % payload)
        headers = {'content-type': "application/json", 'cache-control': "no-cache"}

        if auth:
            headers['X-Auth-Token'] = self.token
            headers['X-User-Id'] = self.user_id

        try_count = 0
        while max_retries <= 0 or try_count < max_retries:
            try:
                if req_type == "GET":
                    response = requests.request(req_type, self.base_url+url, params=data, headers=headers)
                else:
                    payload = json.dumps(data)
                    response = requests.request(req_type, self.base_url+url, data=payload, headers=headers)
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

    def get_channel_infos(self, chname):
        """Retrieve channel infos"""
        res = self.get("/api/v1/channels.info", {'roomName': chname})
        # logDEBUG("Result: %s" % res)
        # CHECK(res['success']==True, "Cannot retrieve channel infos: %s" % res)
        # return res['channel']
        if res['success']:
            return res['channel']
        return None

    def get_group_infos(self, chname):
        """Retrieve group infos"""
        res = self.get("/api/v1/groups.info", {'roomName': chname})

        # logDEBUG("Result: %s" % res)
        # CHECK(res['success']==True, "Cannot retrieve group infos: %s" % res)
        # return res['group']
        if res['success']:
            return res['group']
        return None
