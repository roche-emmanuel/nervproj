""" NVP plug entrypoint module for ${PROJ_NAME} """

import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger('${PROJ_NAME}')


def register_nvp_plugin(context, proj):
    """This function should register this plugin in the current NVP context"""
    logger.info("Registering ${PROJ_NAME} NVP plugin.")
    proj.register_component('${PROJ_NAME}', MyComponent(context))


class MyComponent(NVPComponent):
    """Example component class"""

    def __init__(self, ctx: NVPContext):
        """Constructor for component"""
        NVPComponent.__init__(self, ctx)

        # define parsers and build required logic from here:
        # desc = {
        #     "build": {"libs": None},
        # }
        # ctx.define_subparsers("main", desc)
        # psr = ctx.get_parser('main.build')
        # psr.add_argument("-c", "--compiler", dest='compiler_type', type=str,
        #                  help="Specify which type of compiler should be selected")
