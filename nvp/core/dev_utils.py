"""Dev utils module."""

import fnmatch
import logging
import re

import numpy as np
from PIL import Image

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class DevUtils(NVPComponent):
    """DevUtils component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""
        if cmd == "compare-folders":
            input_folder = self.get_param("input_folder")
            if input_folder is None:
                input_folder = self.get_cwd()
            ref_folder = self.get_param("ref_folder")
            if ref_folder is None:
                ref_folder = self.get_cwd()

            self.compare_folders(input_folder, ref_folder)
            return True

        if cmd == "collect-content":
            input_folder = self.get_cwd()
            patterns = self.get_param("patterns")
            self.collect_content(input_folder, patterns)
            return True

        if cmd == "clean-log":
            input_file = self.get_param("input_file")
            self.clean_log_file(input_file)
            return True

        return False

    def collect_content(self, folder, patterns=None):
        """Collect all content from files in the given folder.

        If patterns is provided, it should be a semicolon-separated list of glob
        patterns used to select files (e.g. "*.h;gui/*.cpp;config/*.yml").
        Each pattern is matched against the relative file path, so subdirectory
        patterns like "gui/*.cpp" work as expected.

        When no patterns are given, the default selection is applied: .py, .h,
        .cpp and .wgsl files anywhere under the folder.
        """
        allfiles = self.get_all_files(folder, recursive=True)

        if patterns is not None:
            # Split the semicolon-separated list and strip any surrounding whitespace.
            glob_patterns = [p.strip() for p in patterns.split(";") if p.strip()]
            # Keep a file if it matches any of the provided glob patterns.
            allfiles = [f for f in allfiles if any(fnmatch.fnmatch(f, p) for p in glob_patterns)]
        else:
            # Default: collect the standard source/script extensions.
            exts = {".py", ".h", ".cpp", ".wgsl", ".yml", ".json"}
            allfiles = [f for f in allfiles if self.get_path_extension(f) in exts]

        contents = []
        for f in allfiles:
            self.info(f"Reading file {f}")
            contents.append(f"// File: {f}:\n")
            contents.append(self.read_text_file(self.get_path(folder, f)))

        self.write_text_file("\n".join(contents), "contents.log")

    def clean_log_file(self, input_file):
        """Clean a log file by removing [Debug 2] to [Debug 5] lines.

        Writes the result to <basename>.cleaned.log next to the input file,
        preserving original line endings.
        """
        content = self.read_text_file(input_file)
        lines = content.splitlines(keepends=True)

        pat = re.compile(r"\[Debug [2-5]\]")
        cleaned_lines = [line for line in lines if not pat.search(line)]

        removed = len(lines) - len(cleaned_lines)
        logger.info("Removed %d debug lines out of %d total.", removed, len(lines))

        base = self.set_path_extension(input_file, "")
        output_file = base + ".cleaned.log"
        self.write_text_file("".join(cleaned_lines), output_file)
        logger.info("Cleaned log written to %s", output_file)

    def compare_images(self, image1_path, image2_path, tolerance=0.05):
        """Compare 2 images with a given tolerance threshold."""
        # Open images
        img1 = Image.open(image1_path)
        img2 = Image.open(image2_path)

        # Ensure images are the same size
        if img1.size != img2.size:
            return False

        # Ensure images are in the same mode (RGB, RGBA, etc.)
        if img1.mode != img2.mode:
            return False

        # Convert images to numpy arrays (as float to avoid overflow)
        arr1 = np.array(img1, dtype=np.float32)
        arr2 = np.array(img2, dtype=np.float32)

        # Calculate the difference
        diff = np.abs(arr1 - arr2)

        # Calculate the maximum possible difference (account for all channels)
        max_diff = 255.0 * np.prod(arr1.shape)

        # Calculate the actual difference percentage
        diff_percentage = np.sum(diff) / max_diff

        # Compare with tolerance
        return diff_percentage <= tolerance

    def compare_folders(self, input_folder, ref_folder):
        """Compare 2 folders."""

        if input_folder == ref_folder:
            logger.info("Folders are the same, nothing to compare.")
            return

        # Get all input files:
        cur_files = self.get_all_files(input_folder, recursive=True)

        # Get all ref files:
        ref_files = self.get_all_files(ref_folder, recursive=True)

        diffs = 0

        # Check for new files (present in input but not in ref):
        for cfile in cur_files:
            if cfile not in ref_files:
                logger.info("File %s was added.", cfile)
                diffs += 1

        # Iterate on all the ref files:
        for rfile in ref_files:
            if rfile not in cur_files:
                logger.info("File %s was removed.", rfile)
                diffs += 1
            else:
                # Compare the file sizes:
                cur_path = self.get_path(input_folder, rfile)
                ref_path = self.get_path(ref_folder, rfile)
                cur_size = self.get_file_size(cur_path)
                ref_size = self.get_file_size(ref_path)

                if cur_size != ref_size:
                    are_similar = False
                    if self.get_path_extension(rfile).lower() == ".png":
                        are_similar = self.compare_images(cur_path, ref_path, 0.0005)

                    if not are_similar:
                        logger.info("File %s size changed: %d => %d", rfile, ref_size, cur_size)
                        diffs += 1

        if diffs == 0:
            logger.info("Folders are identical.")
        else:
            logger.info("Found %d diffs between folders.", diffs)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("DevUtils", DevUtils(context))

    psr = context.build_parser("compare-folders")
    psr.add_str("-i", "--input", dest="input_folder")("Input folder to process")
    psr.add_str("-r", "--ref", dest="ref_folder")("Ref folder to process")

    psr = context.build_parser("collect-content")
    psr.add_str("-p", "--patterns", dest="patterns", nargs="?", default=None)(
        "Semicolon-separated glob patterns to select files (e.g. '*.h;gui/*.cpp;*.log'). "
        "Defaults to .py/.h/.cpp/.wgsl when omitted."
    )

    psr = context.build_parser("clean-log")
    psr.add_str("input_file")("Log file to clean")

    comp.run()
