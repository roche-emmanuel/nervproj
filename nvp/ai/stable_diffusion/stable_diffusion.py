"""StableDiffusion handling component"""

import logging
import os
import time
from contextlib import nullcontext
from random import randint

import numpy as np
import torch
from einops import rearrange, repeat
from omegaconf import OmegaConf
from optimUtils import split_weighted_subprompts
from PIL import Image
from pytorch_lightning import seed_everything
from torch import autocast
from tqdm import tqdm, trange

# Disable the warning message on CLIPTextModel
from transformers import logging as tlog

tlog.set_verbosity_error()
# tlog.set_verbosity_warning()

from nvp.ai.stable_diffusion.ldm.util import instantiate_from_config
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class StableDiffusion(NVPComponent):
    """StableDiffusion component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.device = None

        # self.config = ctx.get_config()["stable_diffusion"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "txt2img":
            device = self.get_param("device")
            return self.handle_text_to_image(device)

        return False

    def gpu_release(self, tensor):
        """Release a tensor/model allocated on the gpu"""
        if tensor.device != "cpu":
            # mem = torch.cuda.memory_allocated() / 1e6
            del tensor
            torch.cuda.empty_cache()
            # while torch.cuda.memory_allocated() / 1e6 >= mem:
            #     logger.info("Waiting to download model CS on CPU...")
            #     time.sleep(1)

    def to_device(self, tensor):
        """Send a given tensor/model to the current target device"""
        self.check(self.device is not None, "Device not assigned.")

        return tensor.to(self.device)

    def load_model_from_config(self, ckpt):
        """Load the model from config."""

        logger.info("Loading model from %s", ckpt)
        pl_sd = torch.load(ckpt, map_location="cpu")
        if "global_step" in pl_sd:
            logger.info("Global Step: %s", pl_sd["global_step"])
        sdict = pl_sd["state_dict"]
        return sdict

    def load_img(self, path, h0, w0):
        """Load an image from the system and prepare a torch tensor from it"""

        image = Image.open(path).convert("RGB")
        w, h = image.size

        logger.info("Loaded input image of size (%d, %d) from %s", w, h, path)
        if h0 is not None and w0 is not None:
            h, w = h0, w0

        w, h = map(lambda x: x - x % 64, (w, h))  # resize to integer multiple of 32

        logger.info("New image size (%d,%d)", w, h)
        # image = image.resize((w // 8, h // 8), resample=Image.LANCZOS)
        image = image.resize((w, h), resample=Image.LANCZOS)
        image = np.array(image).astype(np.float32) / 255.0
        image = image[None].transpose(0, 3, 1, 2)
        image = torch.from_numpy(image)
        return 2.0 * image - 1.0

    def handle_text_to_image(self, device):
        """Handle stable diffusion text to image."""
        # logger.info("Should handle text to image here.")
        self.device = device
        seed = self.get_param("seed")

        tic = time.time()

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
        config_file = self.get_path(self.ctx.get_root_dir(), "assets", "stable_diffusion", "v1-inference.yaml")

        config = OmegaConf.load(config_file)

        img_height = self.get_param("height")
        img_width = self.get_param("width")
        precision = self.get_param("precision")

        img_file = self.get_param("init_image")
        init_image = None
        init_latent = None
        if img_file is not None:
            # load the init image:
            logger.info("Using init image: %s", img_file)
            # we keep the init image on the cpu:
            init_image = self.load_img(img_file, img_height, img_width)

        logger.info("Instanciating models...")

        model = instantiate_from_config(config.modelUNet)
        _, _ = model.load_state_dict(sdict, strict=False)
        model.eval()
        model.unet_bs = self.get_param("unet_bs")

        model.cdevice = device
        model.turbo = self.get_param("turbo")

        model_cs = instantiate_from_config(config.modelCondStage)
        _, _ = model_cs.load_state_dict(sdict, strict=False)
        model_cs.eval()
        model_cs.cond_stage_model.device = device

        model_fs = instantiate_from_config(config.modelFirstStage)
        _, _ = model_fs.load_state_dict(sdict, strict=False)
        model_fs.eval()

        del sdict

        start_code = None
        n_samples = self.get_param("n_samples")
        latent_channels = self.get_param("latent_channels")
        down_factor = self.get_param("down_factor")
        n_rows = self.get_param("n_rows")
        n_iter = self.get_param("n_iter")
        scale = self.get_param("scale")
        ddim_steps = self.get_param("ddim_steps")
        ddim_eta = self.get_param("ddim_eta")
        sampler = self.get_param("sampler")
        img_format = self.get_param("format")
        smode = self.get_param("seed_mode")
        strength = self.get_param("strength")
        self.check(0 <= strength <= 1.0, "Invalid strength value.")

        # Prepare the t_enc variable:
        t_enc = int(strength * ddim_steps)

        output_dir = self.get_param("output_dir")
        if output_dir is None:
            output_dir = self.get_cwd()

        if self.is_relative_path(output_dir):
            # Add the cwd if the output dir is relative:
            output_dir = self.get_path(self.get_cwd(), output_dir)

        if not self.dir_exists(output_dir):
            self.make_folder(output_dir)

        logger.debug("Using output folder: %s", output_dir)

        batch_size = n_samples
        n_rows = n_rows if n_rows > 0 else batch_size

        if init_image is not None:
            init_image = repeat(init_image, "1 ... -> b ...", b=batch_size)

            # Note: this is on the cpu side:
            init_latent = model_fs.get_first_stage_encoding(
                model_fs.encode_first_stage(init_image)
            )  # move to latent space

            # Move to target device:
            init_latent = self.to_device(init_latent)

        if device != "cpu" and precision == "autocast":
            # Note: we only convert to half *after* preparing the init_latent array,
            # since on the cpu "slow_conv2d_cpu" doesn't support half format.
            model.half()
            model_cs.half()
            model_fs.half()
            if init_latent is not None:
                init_latent = init_latent.half()
                self.check(init_latent.device != "cpu", "Invalid init latent device: %s", init_latent.device)

        if self.get_param("fixed_code"):
            start_code = torch.randn(
                [n_samples, latent_channels, img_height // down_factor, img_width // down_factor], device=device
            )

        prompt = self.get_param("prompt", None)
        self.check(prompt is not None, "Invalid prompt.")

        logger.debug("Using prompt: %s", prompt)
        prompts = batch_size * [prompt]

        if precision == "autocast" and device != "cpu":
            precision_scope = autocast
        else:
            precision_scope = nullcontext

        seeds = ""
        sample_path = output_dir
        base_count = len(os.listdir(sample_path))
        if smode == "continue":
            seed += base_count

        with torch.no_grad():

            for _ in trange(n_iter, desc="Sampling"):
                with precision_scope("cuda"):

                    # Send the model on the device:
                    model_cs_dev = self.to_device(model_cs)

                    uc = None
                    if scale != 1.0:
                        uc = model_cs_dev.get_learned_conditioning(batch_size * [""])

                    if isinstance(prompts, tuple):
                        prompts = list(prompts)

                    subprompts, weights = split_weighted_subprompts(prompts[0])
                    if len(subprompts) > 1:
                        c = torch.zeros_like(uc)
                        total_weight = sum(weights)
                        # normalize each "sub prompt" and add it
                        for idx, subp in enumerate(subprompts):
                            weight = weights[idx]
                            # if not skip_normalize:
                            weight = weight / total_weight
                            c = torch.add(c, model_cs_dev.get_learned_conditioning(subp), alpha=weight)
                    else:
                        c = model_cs_dev.get_learned_conditioning(prompts)

                    shape = [n_samples, latent_channels, img_height // down_factor, img_width // down_factor]

                    self.gpu_release(model_cs_dev)

                    # Starting point of the image in latent space:
                    # if none is specified then random noise will be used:
                    x0 = None
                    num_steps = ddim_steps

                    if init_latent is not None:
                        # A source image was provided,
                        # So we encode the corresponding latents:
                        # encode (scaled latent)
                        self.check(init_latent.device != "cpu", "Invalid init latent device: %s", init_latent.device)
                        # logger.info("init_latent shape: %s", init_latent.shape)

                        x0 = model.stochastic_encode(
                            init_latent,
                            torch.tensor([t_enc] * batch_size).to(device),
                            seed,
                            ddim_eta,
                            ddim_steps,
                        )
                        num_steps = t_enc

                    samples_ddim = model.sample(
                        S=num_steps,
                        conditioning=c,
                        x0=x0,
                        seed=seed,
                        shape=shape,
                        verbose=False,
                        unconditional_guidance_scale=scale,
                        unconditional_conditioning=uc,
                        eta=ddim_eta,
                        x_T=start_code,
                        sampler=sampler,
                    )

                    model_fs_dev = self.to_device(model_fs)

                    logger.info("Saving images (shape: %s)...", samples_ddim.shape)

                    for i in range(batch_size):

                        x_samples_ddim = model_fs_dev.decode_first_stage(samples_ddim[i].unsqueeze(0))
                        x_sample = torch.clamp((x_samples_ddim + 1.0) / 2.0, min=0.0, max=1.0)
                        x_sample = 255.0 * rearrange(x_sample[0].cpu().numpy(), "c h w -> h w c")
                        Image.fromarray(x_sample.astype(np.uint8)).save(
                            os.path.join(sample_path, f"{base_count:05}_seed_{seed}.{img_format}")
                        )
                        seeds += str(seed) + ","
                        seed += 1
                        base_count += 1

                    self.gpu_release(model_fs_dev)

                    del samples_ddim
                    logger.info("memory_final = %s MiB", torch.cuda.memory_allocated() / 1e6)

        toc = time.time()

        time_taken = (toc - tic) / 60.0

        logger.info(
            "Samples finished in %.2f minutes and exported to %s\nSeeds used = %s",
            time_taken,
            sample_path,
            str(seeds[:-1]),
        )

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("StableDiffusion", StableDiffusion(context))

    psr = context.build_parser("txt2img")
    psr.add_int("--seed", dest="seed", default=42)("Random seed for the whole process.")
    psr.add_int("--unet_bs", dest="unet_bs", default=1)(
        "Slightly reduces inference time at the expense of high VRAM (value > 1 not recommended )"
    )
    psr.add_str("--ckpt", dest="ckpt_file", default=None)("checkpoint file to use.")
    psr.add_str("--device", dest="device", default="cuda")("specify GPU (cuda/cuda:0/cuda:1/...)")
    psr.add_str("--precision", dest="precision", default="autocast", choices=["full", "autocast"])(
        "evaluate at this precision, can be full or autocast"
    )
    psr.add_str("-o", "--output", dest="output_dir", default=None)("Output folder")
    psr.add_str("--prompt", dest="prompt")("The prompt to render")
    psr.add_str("-i", "--img", dest="init_image")("Init image to use for inference")
    psr.add_str("--smode", dest="seed_mode", default="continue")(
        "Define how the seed number should be changed depending on the existing content in dest folder."
    )
    psr.add_flag("--turbo", dest="turbo")("Reduces inference time on the expense of 1GB VRAM")
    psr.add_flag("--fixed_code", dest="fixed_code")("if enabled, uses the same starting code across samples")
    psr.add_int("--n_iter", dest="n_iter", default=1)("Sample this often")
    psr.add_int("-H", "--height", dest="height", default=512)("Image height, in pixel space")
    psr.add_int("-W", "--width", dest="width", default=512)("Image width, in pixel space")
    psr.add_int("-C", "--channels", dest="latent_channels", default=4)("Latent channels")
    psr.add_int("-f", "--down-factor", dest="down_factor", default=8)("Downsampling factor")
    psr.add_int("-n", "--samples", dest="n_samples", default=5)(
        "How many samples to produce for each given prompt. A.k.a. batch size"
    )
    psr.add_int("--n_rows", dest="n_rows", default=0)("rows in the grid (default: n_samples)")
    psr.add_int("--ddim_steps", dest="ddim_steps", default=50)("number of ddim sampling steps")
    psr.add_float("--scale", dest="scale", default=7.5)(
        "unconditional guidance scale: eps = eps(x, empty) + scale * (eps(x, cond) - eps(x, empty))"
    )
    psr.add_float("--strength", dest="strength", default=0.5)(
        "Strength for noising/unnoising. 1.0 corresponds to full destruction of information in init image"
    )
    psr.add_float("--ddim_eta", dest="ddim_eta", default=0.0)("ddim eta (eta=0.0 corresponds to deterministic sampling")
    psr.add_str(
        "--sampler",
        dest="sampler",
        default="plms",
        choices=["ddim", "plms", "heun", "euler", "euler_a", "dpm2", "dpm2_a", "lms"],
    )("Sampler to use.")
    psr.add_str(
        "--format",
        dest="format",
        default="png",
        choices=["jpg", "png"],
    )("Output format to write")

    comp.run()
