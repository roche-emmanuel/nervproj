"""Whisper handling component - WhisperX version (No pyannote VAD)

This component is used to access OpenAI whisper via WhisperX and translate audio to text
with improved word-level timestamps and alignment.

This version avoids pyannote.audio dependency issues by using alternative VAD."""

import logging
import os
import time

import torch
import whisperx

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

            return self.convert_audio_to_text_whisperx(file, model)

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
            self.convert_audio_to_text_whisperx(fname, model)

        return True

    def convert_audio_to_text_whisperx(self, file, model_size="large-v3"):
        """Translate an audio file to text with WhisperX"""
        # cf. https://github.com/m-bain/whisperX

        start_time = time.time()

        # Detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"

        logger.info("Loading WhisperX model '%s' on device '%s'...", model_size, device)

        # Load model with vad_onset/vad_offset to avoid pyannote dependency
        model = whisperx.load_model(
            model_size,
            device,
            compute_type=compute_type,
            language="en",  # Set to None for auto-detection, or specify language code
            vad_options={"vad_onset": 0.500, "vad_offset": 0.363},
        )

        # Load audio
        logger.info("Loading audio file: %s", file)
        audio = whisperx.load_audio(file)

        # Transcribe with WhisperX
        logger.info("Transcribing...")
        result = model.transcribe(audio, batch_size=16)  # Adjust based on your GPU memory

        detected_language = result.get("language", "en")
        logger.info("Detected language: %s", detected_language)

        # Align whisper output for better word-level timestamps
        try:
            logger.info("Aligning timestamps...")
            model_a, metadata = whisperx.load_align_model(language_code=detected_language, device=device)

            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

            # Clean up alignment model
            del model_a

        except Exception as e:
            logger.warning("Alignment failed (will use base timestamps): %s", str(e))
            # Continue with unaligned results

        # Extract full text
        segments = result["segments"]
        txt = " ".join([segment["text"].strip() for segment in segments])

        elapsed = time.time() - start_time

        # Write text file
        self.write_text_file(txt, file + ".txt")
        logger.info("Done converting audio to text in %.2f secs", elapsed)
        logger.info("Generated output: %s", txt[:200] + "..." if len(txt) > 200 else txt)

        # Process word-level timestamps
        word_list = []
        punctuations = ",.?!:;"

        for segment in segments:
            if "words" not in segment:
                # Fallback: if no word-level timestamps, create approximate ones
                words_in_segment = segment["text"].strip().split()
                segment_duration = segment["end"] - segment["start"]
                time_per_word = segment_duration / max(len(words_in_segment), 1)

                for i, word_str in enumerate(words_in_segment):
                    word_str = word_str.strip()
                    if len(word_str) > 0 and word_str[-1] in punctuations:
                        word_str = word_str[:-1]

                    if len(word_str) < 1:
                        continue

                    word_start = segment["start"] + (i * time_per_word)
                    word_end = word_start + time_per_word

                    word_list.append(
                        {
                            "word": word_str,
                            "start": round(word_start, 3),
                            "end": round(word_end, 3),
                            "score": segment.get("avg_logprob", 0.0),
                        }
                    )
                continue

            for word_info in segment["words"]:
                word_str = word_info["word"].strip()

                # Remove punctuation from end of word
                if len(word_str) > 0 and word_str[-1] in punctuations:
                    word_str = word_str[:-1]

                if len(word_str) < 1:
                    continue

                word_list.append(
                    {
                        "word": word_str,
                        "start": round(word_info.get("start", 0.0), 3),
                        "end": round(word_info.get("end", 0.0), 3),
                        "score": word_info.get("score", 0.0),
                    }
                )

        # Write word list as JSON file
        out_file = self.set_path_extension(file, ".json")
        self.write_json(word_list, out_file)
        logger.info("Wrote %d words with timestamps to: %s", len(word_list), out_file)

        # Clean up
        del model
        if device == "cuda":
            torch.cuda.empty_cache()

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

        # If we wrote only 1 chunk in the end then we can just remove it:
        if idx == 1:
            self.remove_file(self.set_path_extension(filename, "_chunk0.txt"))
            logger.info("Not splitting file with %d words.", num)
        else:
            logger.info("Splitted file of %d words in %d chunks", num, idx)

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("WhisperGen", WhisperGen(context))

    psr = context.build_parser("convert")
    psr.add_str("-i", "--input", dest="input_file", default="all")("Audio file to convert to text")
    psr.add_str("-m", "--model", dest="model", default="large-v3")("Model to use for the convertion")
    psr.add_int("-n", "--nwords", dest="num_words", default=3000)("Number of words to write per chunk.")

    psr = context.build_parser("split_text")
    psr.add_str("-i", "--input", dest="input_file")("Text file to split")
    psr.add_int("-n", "--nwords", dest="num_words", default=3000)("Number of words to write per chunk.")

    comp.run()
