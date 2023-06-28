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
            nwords = self.get_param("num_words")
            model = self.get_param("model")
            if file == "all":
                return self.process_all_files(model, nwords)

            return self.convert_audio_to_text(file, model, nwords)

        if cmd == "split_text":
            file = self.get_param("input_file")
            nwords = self.get_param("num_words")

            return self.split_text_chunks(file, nwords)

        return False

    def process_all_files(self, model, nwords):
        """Process all the video files not already processed in the current folder"""
        cur_dir = self.get_cwd()
        all_files = self.get_all_files(cur_dir, recursive=False)
        exts = [".mkv", ".mp3", ".mp4"]
        for fname in all_files:
            ext = self.get_path_extension(fname).lower()
            if ext not in exts:
                continue

            # Check if we already have the text file:
            if self.file_exists(self.get_path(cur_dir, fname + ".txt")):
                continue

            # Otherwise we process this file:
            self.convert_audio_to_text(fname, model, nwords)

        return True

    def convert_audio_to_text(self, file, model, nwords):
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

        # When done generating a file we should also count the number of words, and split on
        # multiple chunks if needed:
        self.split_text_chunks(file + ".txt", nwords)

        return True

    def split_text_chunks(self, filename, num_words):
        """Split a given text file into multiple chunk files"""

        content = self.read_text_file(filename)
        words = content.split(" ")

        num = len(words)
        if num < num_words:
            logger.info("No need to split text content with %d words", num)
            return True

        cur_words = []
        idx = 0

        for word in words:
            cur_words.append(word)
            if len(cur_words) >= num_words and word[-1] == ".":
                # Write a chunk file:
                chunkfile = self.set_path_extension(filename, f"_chunk{idx}.txt")
                self.write_text_file(" ".join(cur_words), chunkfile)
                idx += 1
                cur_words = []

        if len(cur_words) > 0:
            # Write the remaining words:
            chunkfile = self.set_path_extension(filename, f"_chunk{idx}.txt")
            self.write_text_file(" ".join(cur_words), chunkfile)
            idx += 1
            cur_words = []

        logger.info("Splitted file of %d words in %d chunks", num, idx)

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("WhisperGen", WhisperGen(context))

    psr = context.build_parser("convert")
    psr.add_str("-i", "--input", dest="input_file", default="all")("Audio file to convert to text")
    psr.add_str("-m", "--model", dest="model", default="large")("Model to use for the convertion")
    psr.add_int("-n", "--nwords", dest="num_words", default=2500)("Number of words to write per chunk.")

    psr = context.build_parser("split_text")
    psr.add_str("-i", "--input", dest="input_file")("Text file to split")
    psr.add_int("-n", "--nwords", dest="num_words", default=2500)("Number of words to write per chunk.")

    comp.run()
