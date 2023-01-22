"""StableDiffusion handling component"""
import logging
from random import randint

import torch
from omegaconf import OmegaConf
from pytorch_lightning import seed_everything

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class StableDiffusion(NVPComponent):
    """StableDiffusion component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        # self.config = ctx.get_config()["stable_diffusion"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "txt2img":
            return self.handle_text_to_image()

        return False

    def load_model_from_config(self, ckpt):
        """Load the model from config."""

        logger.info("Loading model from %s", ckpt)
        pl_sd = torch.load(ckpt, map_location="cpu")
        if "global_step" in pl_sd:
            logger.info("Global Step: %s", pl_sd["global_step"])
        sdict = pl_sd["state_dict"]
        return sdict

    def handle_text_to_image(self):
        """Handle stable diffusion text to image."""
        logger.info("Should handle text to image here.")
        seed = self.get_param("seed")

        if seed == -1:
            seed = randint(0, 1000000)

        logger.info("Seeding everything with global seed: %d", seed)
        seed_everything(seed)

        ckpt_file = self.get_param("ckpt_file")
        if ckpt_file is None:
            ckpt_file = self.get_path(self.ctx.get_root_dir(), "data", "stable_diffusion", "sd-v1-5.ckpt")

        logger.info("Using checkpoint file: %s", ckpt_file)

        sdict = self.load_model_from_config(ckpt_file)

        li, lo = [], []
        for key, _ in sdict.items():
            sp = key.split(".")
            if (sp[0]) == "model":
                if "input_blocks" in sp:
                    li.append(key)
                elif "middle_block" in sp:
                    li.append(key)
                elif "time_embed" in sp:
                    li.append(key)
                else:
                    lo.append(key)
        for key in li:
            sdict["model1." + key[6:]] = sdict.pop(key)
        for key in lo:
            sdict["model2." + key[6:]] = sdict.pop(key)

        logger.info("Building config...")
        config = self.get_path(self.ctx.get_root_dir(), "assets", "stable_diffusion", "v1-inference.yaml")

        config = OmegaConf.load(config)

        logger.info("Done")
        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("StableDiffusion", StableDiffusion(context))

    psr = context.build_parser("txt2img")
    psr.add_int("--seed", dest="seed", default=42)("Random seed for the whole process.")
    psr.add_str("--ckpt", dest="ckpt_file", default=None)("checkpoint file to use.")
    # psr.add_str("-a", "--add-audio", dest="add_audio")("additional audio stream to add in the video.")

    comp.run()
