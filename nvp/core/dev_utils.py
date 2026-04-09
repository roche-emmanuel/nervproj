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
            ignore_patterns = self.get_param("ignore_patterns")
            output_file = self.get_param("output_file")
            self.collect_content(input_folder, patterns, ignore_patterns, output_file)
            return True

        if cmd == "clean-log":
            input_file = self.get_param("input_file")
            self.clean_log_file(input_file)
            return True

        return False

    @staticmethod
    def is_binary_file(filepath):
        """Return True if the file appears to be binary.

        Reads the first 8 KB and checks for null bytes, which are a reliable
        indicator of binary content in practice.
        """
        try:
            with open(filepath, "rb") as fh:
                chunk = fh.read(8192)
            return b"\x00" in chunk
        except OSError:
            return True

    def collect_content(self, folder, patterns=None, ignore_patterns=None, output_file=None):
        """Collect all content from files in the given folder.

        File selection works in three steps:

        1. Include filter (-p / patterns): if provided, keep only files whose
           relative path matches at least one of the semicolon-separated glob
           patterns (e.g. "*.h;gui/*.cpp;config/*.yml").  When omitted, all
           non-binary files found recursively under folder are kept.

        2. Exclude filter (-x / ignore_patterns): if provided, drop any file
           whose relative path matches at least one of the semicolon-separated
           glob patterns.  Applied after the include filter.

        3. Binary guard: files that survive both filters are skipped silently
           if they turn out to be binary (only relevant when no -p is given,
           since explicit patterns imply the caller knows the file type).

        Each included file is preceded by a header line reporting its size in
        bytes and as a percentage of the total content size.

        output_file sets the destination file name (default: "content.api.txt").
        """
        allfiles = self.get_all_files(folder, recursive=True)

        # --- include filter ---
        if patterns is not None:
            glob_patterns = [p.strip() for p in patterns.split(";") if p.strip()]
            allfiles = [f for f in allfiles if any(fnmatch.fnmatch(f, p) for p in glob_patterns)]
        else:
            # No explicit pattern: collect everything that is not binary.
            allfiles = [f for f in allfiles if not self.is_binary_file(self.get_path(folder, f))]

        # --- exclude filter ---
        if ignore_patterns is not None:
            ignore_globs = [p.strip() for p in ignore_patterns.split(";") if p.strip()]
            allfiles = [f for f in allfiles if not any(fnmatch.fnmatch(f, p) for p in ignore_globs)]

        if not allfiles:
            logger.info("No files matched the selection criteria.")
            return

        # Pre-compute file sizes so we can report percentages.
        file_sizes = {f: self.get_file_size(self.get_path(folder, f)) for f in allfiles}
        total_size = sum(file_sizes.values())

        contents = []
        for f in allfiles:
            size = file_sizes[f]
            pct = (size / total_size * 100.0) if total_size > 0 else 0.0
            logger.info("Reading file %s (%d bytes, %.1f%%)", f, size, pct)
            contents.append(f"// File: {f} ({size} bytes, {pct:.1f}% of total):\n")
            contents.append(self.read_text_file(self.get_path(folder, f)))

        logger.info("Collected %d files, total size: %d bytes.", len(allfiles), total_size)
        self.write_text_file("\n".join(contents), output_file or "content.api.txt")

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
        "Defaults to all non-binary files when omitted."
    )
    psr.add_str("-x", "--ignore", dest="ignore_patterns", nargs="?", default=None)(
        "Semicolon-separated glob patterns for files to exclude (e.g. '*.min.js;build/*'). "
        "Applied after the -p include filter."
    )
    psr.add_str("-o", "--output", dest="output_file", nargs="?", default=None)(
        "Output file name. Defaults to 'content.api.txt' when omitted."
    )

    psr = context.build_parser("clean-log")
    psr.add_str("input_file")("Log file to clean")

    comp.run()
