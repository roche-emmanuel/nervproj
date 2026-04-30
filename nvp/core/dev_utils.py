"""Dev utils module."""

import fnmatch
import logging
import os
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
        self.packs_config = None

    def get_packs_config(self):
        """Load and cache the content_packs section from the NervHome config."""
        if self.packs_config is None:
            cfg = self.ctx.get_config().get("content_packs")
            if cfg is None:
                cfg = self.ctx.get_project("NervHome").get_config().get("content_packs")
            self.check(cfg is not None, "No 'content_packs' section found in config.")
            self.packs_config = cfg
        return self.packs_config

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
            input_folder = self.get_param("input_folder") or os.getcwd()
            patterns = self.get_param("patterns")
            ignore_patterns = self.get_param("ignore_patterns")
            output_file = self.get_param("output_file")
            include_api_txt = self.get_param("include_api_txt", False)
            append = self.get_param("append", False)
            self.collect_content(input_folder, patterns, ignore_patterns, output_file, include_api_txt, append)
            return True

        if cmd == "build-content-packs":
            pack_name = self.get_param("pack_name")
            self.build_content_packs(pack_name)
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

    def build_content_packs(self, pack_name=None):
        """Build one or all enabled content packs from the NervHome config.

        If pack_name is given, only that pack is processed (regardless of its
        'enabled' flag).  Otherwise every pack whose 'enabled' flag is True is
        processed in the order they appear in the config.

        Each pack drives one or more collect_content calls (one per 'steps'
        entry).  The first step of each pack always overwrites the output file;
        subsequent steps append to it automatically.

        Path placeholders (e.g. ${NVL_DIR}) in 'folder' and 'output' values
        are resolved via self.resolve_path() before use.
        """
        cfg = self.get_packs_config()
        default_output_dir = self.resolve_path(cfg.get("default_output_dir", os.getcwd()))
        packs = cfg.get("packs", [])

        # Select which packs to run.
        if pack_name is not None:
            packs = [p for p in packs if p.get("name") == pack_name]
            self.check(len(packs) > 0, "No content pack named '%s' found in config.", pack_name)
        else:
            packs = [p for p in packs if p.get("enabled", True)]

        for pack in packs:
            name = pack.get("name", "<unnamed>")
            output_dir = self.resolve_path(pack.get("output_dir", default_output_dir))
            output = self.get_path(output_dir, f"{name}.api.txt")
            steps = pack.get("steps", [])
            include_api_txt = pack.get("include_api_txt", False)

            logger.info("Building content pack '%s' => %s (%d step(s)).", name, output, len(steps))

            first_call = True
            for step in steps:
                folder = self.resolve_path(step.get("folder", os.getcwd()))
                ignore_patterns = step.get("ignore", None)

                # patterns may be a single string or a list of strings.
                # Each entry is passed as a separate collect_content call so
                # that wildcard expansion is scoped to one pattern group at a time.
                raw = step.get("patterns")
                pattern_list = raw if isinstance(raw, list) else [raw]

                for patterns in pattern_list:
                    # First overall call writes fresh; every subsequent one appends.
                    self.collect_content(folder, patterns, ignore_patterns, output, include_api_txt, not first_call)
                    first_call = False

            logger.info("Content pack '%s' done.", name)

    def collect_content(
        self, folder, patterns=None, ignore_patterns=None, output_file=None, include_api_txt=False, append=False
    ):
        """Collect all content from files in the given folder.

        File selection works in three steps:

        1. Include filter (-p / patterns): if provided, keep only files whose
           relative path matches at least one of the semicolon-separated glob
           patterns (e.g. "*.h;gui/*.cpp;config/*.yml").  When omitted, all
           files found recursively under folder are kept.

        2. Exclude filter (-x / ignore_patterns): if provided, drop any file
           whose relative path matches at least one of the semicolon-separated
           glob patterns.  Applied after the include filter.

        3. Binary detection: binary files are not inlined but still appear in
           the output as a header-only entry (filename + size) so the reader
           knows they exist.  When -p is given, all matched files are treated
           as text (the caller is assumed to know the file type).

        *.api.txt files are always excluded unless include_api_txt is True.

        Text files are written in ascending size order (smallest first, largest
        last), preceded by binary-file header lines.  Each entry reports its
        size in bytes and as a percentage of the combined total.

        output_file sets the destination file name (default: "content.api.txt").
        When append is True, content is appended instead of overwriting.
        """
        # --- include filter ---
        if patterns is not None:
            glob_patterns = [p.strip() for p in patterns.split(";") if p.strip()]
            # Optimisation: if none of the patterns contain a wildcard, treat them as
            # direct file paths and skip the costly recursive directory scan entirely.
            if not any(c in p for p in glob_patterns for c in ("*", "?", "[")):
                allfiles = []
                for p in glob_patterns:
                    fpath = self.get_path(folder, p)
                    if self.file_exists(fpath):
                        allfiles.append(p)
                    else:
                        logger.warning("Pattern '%s' does not match any file (resolved to: %s).", p, fpath)
            else:
                allfiles = self.get_all_files(folder, recursive=True)
                allfiles = [f for f in allfiles if any(fnmatch.fnmatch(f, p) for p in glob_patterns)]
        else:
            # No explicit pattern: collect all files; binary ones become header-only entries.
            allfiles = self.get_all_files(folder, recursive=True)

        # --- always exclude *.api.txt unless the caller explicitly opts in ---
        if not include_api_txt:
            allfiles = [f for f in allfiles if not fnmatch.fnmatch(f, "*.api.txt")]

        # --- always exclude files coming from .git/ or .github/ trees (at any depth) ---
        allfiles = [
            f
            for f in allfiles
            if not any(
                fnmatch.fnmatch(f.replace("\\", "/"), p)
                for p in (".git/*", "*/.git/*", ".github/*", "*/.github/*", "*.private.h")
            )
        ]

        # --- exclude filter ---
        if ignore_patterns is not None:
            ignore_globs = [p.strip() for p in ignore_patterns.split(";") if p.strip()]
            allfiles = [f for f in allfiles if not any(fnmatch.fnmatch(f, p) for p in ignore_globs)]

        if not allfiles:
            logger.info("No files matched the selection criteria.")
            return

        # Pre-compute file sizes. Empty files are excluded entirely.
        file_sizes = {f: self.get_file_size(self.get_path(folder, f)) for f in allfiles}
        allfiles = [f for f in allfiles if file_sizes[f] > 0]

        # Split into text and binary — always, regardless of whether patterns were given.
        # A glob like "*.h" may still accidentally match binary files (e.g. logo.ico
        # caught by a broad wildcard), so we never skip the binary check.
        binary_files = [f for f in allfiles if self.is_binary_file(self.get_path(folder, f))]
        binary_set = set(binary_files)
        text_files = [f for f in allfiles if f not in binary_set]

        # Percentages are computed relative to text content only — binary files are
        # listed for reference but their size does not count towards the total.
        total_size = sum(file_sizes[f] for f in text_files)

        contents = []

        # Binary file headers first, sorted by size ascending.
        for f in sorted(binary_files, key=lambda f: file_sizes[f]):
            size = file_sizes[f]
            logger.info("Skipping binary file %s (%d bytes)", f, size)
            contents.append(f"// File: {f} ({size} bytes, binary)")

        # Text file contents, sorted by size ascending (smallest first, largest last).
        for f in sorted(text_files, key=lambda f: file_sizes[f]):
            size = file_sizes[f]
            pct = (size / total_size * 100.0) if total_size > 0 else 0.0
            logger.info("Reading file %s (%d bytes, %.1f%%)", f, size, pct)
            contents.append(f"// File: {f} ({size} bytes, {pct:.1f}% of total):\n")
            contents.append(self.read_text_file(self.get_path(folder, f)))

        logger.info(
            "Collected %d text files and %d binary files, total size: %d bytes.",
            len(text_files), len(binary_files), total_size,
        )
        dest = output_file or "content.api.txt"
        self.write_text_file("\n".join(contents), dest, mode="a" if append else "w")
        logger.info("%s content to %s.", "Appended" if append else "Written", dest)

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
    psr.add_str("-i", "--input", dest="input_folder", nargs="?", default=None)(
        "Root folder to collect from. Defaults to the current working directory."
    )
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
    psr.add_flag("--include-api-txt", dest="include_api_txt")(
        "When set, *.api.txt files are not excluded from the collection."
    )
    psr.add_flag("-a", "--append", dest="append")(
        "When set, content is appended to the output file instead of overwriting it."
    )

    psr = context.build_parser("build-content-packs")
    psr.add_str("pack_name", nargs="?", default=None)(
        "Name of the content pack to build. When omitted, all enabled packs are built."
    )

    psr = context.build_parser("clean-log")
    psr.add_str("input_file")("Log file to clean")

    comp.run()