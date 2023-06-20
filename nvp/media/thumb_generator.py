"""ThumbGen handling component

This component is used to generate youtube thumbnails from a given description in yaml"""

import logging

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class ThumbGen(NVPComponent):
    """ThumbGen component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "gen-thumb":
            logger.info("Should generate thumbnail here.")
            return True

        return False


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("ThumbGen", ThumbGen(context))

    psr = context.build_parser("gen-thumb")
    # psr.add_flag("-f", "--use-folder-name", dest="use_folder_name")("Rename using parent folder name")
    # psr.add_str("tag_name", nargs="?", default="all")("input file where to read the config settings from")
    psr.add_str("tag_name")("Input tag to generate a thumbnail for")
    psr.add_str("-i", "--input", dest="input_file", default="youtube_videos.yml")(
        "input file where to read the config settings from"
    )

    comp.run()
