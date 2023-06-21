"""Whisper handling component

This component is used to access OpenAI whisper and translate audio to text"""

import logging
import os
import time

import torch
import whisper

from nvp.core.tools import ToolsManager
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class WhisperGen(NVPComponent):
    """WhisperGen component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "convert":
            file = self.get_param("input_file")
            model = self.get_param("model")
            return self.translate_audio(file, model)

        return False

    def translate_audio(self, file, model):
        """Translate an audio file to text"""
        logger.info("Should translate audio file to text: %s", file)

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")
        ffmpeg_dir = self.get_parent_folder(ffmpeg_path)
        # sys.path.append(ffmpeg_dir)
        # logger.info("Adding path to ffmpeg: %s", ffmpeg_dir)
        self.append_env_list([ffmpeg_dir], os.environ)

        # Check that cuda is available:
        self.check(torch.cuda.is_available(), "Torch CUDA backend is not available ?")

        start_time = time.time()
        logger.info("Loading model...")
        model = whisper.load_model(model)

        logger.info("Transcribing...")
        result = model.transcribe(file)
        txt = result["text"]
        elapsed = time.time() - start_time
        self.write_text_file(txt, file + ".txt")
        logger.info("Done converting auto to text in %.2f secs", elapsed)
        logger.info("Generated output: %s", txt)
        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("WhisperGen", WhisperGen(context))

    psr = context.build_parser("convert")
    psr.add_str("-i", "--input", dest="input_file")("Audio file to convert to text")
    psr.add_str("-m", "--model", dest="model", default="large")("Model to use for the convertion")

    comp.run()
