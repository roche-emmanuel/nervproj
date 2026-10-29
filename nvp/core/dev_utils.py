"""Dev utils module."""

import fnmatch
import logging
import os
import re
from datetime import datetime

import numpy as np
from PIL import Image

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

# --- Content pack layout (see DevUtils._write_pack) ---------------------------------------
# A pack is ONE file, laid out for a reader that can load only the first ~260 KB of a
# document directly and reaches the rest through search returning ~2 KB chunks.
PACK_INDEX_MAX_BYTES = 150_000  # the index must stay well inside the direct-read window
PACK_OUTLINE_CAPS = (60, 30, 15, 0)  # max symbols listed per file, tried in turn until the index fits
PACK_MARKER = "//~ "  # prefix of the packer's locator lines (not part of the packed files)
PACK_MARKER_EVERY_LINES = 40
PACK_MARKER_EVERY_BYTES = 1500


class DevUtils(NVPComponent):
    """DevUtils component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)
        self.config = self.get_packs_config()
        self.packs = self.load_config_entry("packs")

    def get_packs_config(self):
        """Load and cache the content_packs section from the NervHome config."""
        cfg = self.ctx.get_config().get("content_packs")
        if cfg is None:
            cfg = self.ctx.get_project("NervHome").get_config().get("content_packs")
        self.check(cfg is not None, "No 'content_packs' section found in config.")
        return cfg

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

    def build_content_packs(self, pack_name):
        """Build one or all enabled content packs from the NervHome config.

        If pack_name is given, only that pack is processed (regardless of its
        'enabled' flag).  Otherwise every pack whose 'enabled' flag is True is
        processed in the order they appear in the config.

        Each pack gathers the files of all its 'steps' entries and writes ONE file,
        <name>.api.txt, made of:

        - a header explaining how to read the pack;
        - an INDEX: every file with its size, line count, the line range it occupies in
          the pack, and an outline of its classes/functions (kept small enough to sit
          entirely inside the first ~260 KB, which is all a reader may load directly);
        - the files themselves, sorted by path, each between a FILE / END FILE line, with
          a locator line every few dozen lines so that any search hit identifies its file.

        Path placeholders (e.g. ${NVL_DIR}) in 'folder' and 'output' values
        are resolved via self.resolve_path() before use.
        """
        default_output_dir = self.resolve_path(self.config.get("default_output_dir", os.getcwd()))

        self.check(pack_name is not None, "invalid pack name")
        pack = self.packs.get(pack_name)
        self.check(pack is not None, "No content pack named '%s' found in config.", pack_name)

        name = pack_name
        # output_dir = self.resolve_path(pack.get("output_dir", default_output_dir))
        output_dir = default_output_dir
        output = self.get_path(output_dir, f"{name}.api.txt")
        steps = pack.get("steps")
        include_api_txt = False

        logger.info("Building content pack '%s' => %s (%d step(s)).", name, output, len(steps))

        text_entries = []
        binary_entries = []
        seen = set()
        for step in steps:
            folder = self.resolve_path(step.get("folder", os.getcwd()))
            ignore_patterns = step.get("ignore", None)
            source = os.path.basename(os.path.normpath(folder)) or folder

            # patterns may be a single string or a list of strings.
            # Each entry is gathered separately so that wildcard expansion is
            # scoped to one pattern group at a time.
            raw = step.get("patterns")
            pattern_list = raw if isinstance(raw, list) else [raw]

            for patterns in pattern_list:
                texts, bins, _total = self._collect_entries(folder, patterns, ignore_patterns, include_api_txt)
                for bucket, found in ((text_entries, texts), (binary_entries, bins)):
                    for entry in found:
                        key = (folder, entry["path"])
                        if key in seen:
                            continue  # the same file matched by two pattern groups
                        seen.add(key)
                        entry["source"] = source
                        bucket.append(entry)

        self._write_pack(name, output, text_entries, binary_entries)
        logger.info("Content pack '%s' done.", name)

    # ------------------------------------------------------------------
    # Content pack writer (single-file "virtual filesystem" format)
    # ------------------------------------------------------------------

    _PY_SYMBOL = re.compile(r"^(\s*)(?:async\s+)?(class|def)\s+(\w+)")
    _JS_SYMBOL = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\(|function)"
    )
    _MD_HEADING = re.compile(r"^(#{1,3})\s+(.*\S)")
    _JINJA_BLOCK = re.compile(r"\{%-?\s*(?:block|macro)\s+(\w+)")
    _CPP_SYMBOL = re.compile(r"^\s*(?:class|struct|namespace|enum(?:\s+class)?)\s+(\w+)")

    @classmethod
    def _outline(cls, path, lines):
        """Return a short list of 'symbol (Lnn)' strings describing the structure of a file.

        Understands Python (classes, methods, top-level functions), JavaScript, Markdown
        headings, Jinja blocks/macros and C++ class/struct/namespace declarations; any other
        file type gives an empty outline.
        """
        ext = os.path.splitext(path)[1].lower()
        out = []
        if ext == ".py":
            current_class = None
            for n, line in enumerate(lines, start=1):
                m = cls._PY_SYMBOL.match(line)
                if m is None:
                    continue
                indent = len(m.group(1).replace("\t", "    "))
                kind, name = m.group(2), m.group(3)
                if kind == "class" and indent == 0:
                    current_class = name
                    out.append(f"class {name} (L{n})")
                elif kind == "def" and indent == 0:
                    current_class = None
                    out.append(f"def {name} (L{n})")
                elif kind == "def" and indent <= 4 and current_class:
                    out.append(f"{current_class}.{name} (L{n})")
        elif ext in (".js", ".mjs"):
            for n, line in enumerate(lines, start=1):
                m = cls._JS_SYMBOL.match(line)
                if m:
                    out.append(f"{m.group(1) or m.group(2)} (L{n})")
        elif ext in (".md", ".markdown"):
            in_fence = False
            for n, line in enumerate(lines, start=1):
                if line.lstrip().startswith("```"):
                    in_fence = not in_fence
                m = None if in_fence else cls._MD_HEADING.match(line)
                if m:
                    out.append(f"{'#' * len(m.group(1))} {m.group(2).strip()} (L{n})")
        elif ext in (".html", ".jinja", ".j2"):
            for n, line in enumerate(lines, start=1):
                m = cls._JINJA_BLOCK.search(line)
                if m:
                    out.append(f"block {m.group(1)} (L{n})")
        elif ext in (".h", ".hpp", ".hh", ".cpp", ".cc", ".cxx"):
            for n, line in enumerate(lines, start=1):
                m = cls._CPP_SYMBOL.match(line)
                if m:
                    out.append(f"{m.group(1)} (L{n})")
        return out

    @staticmethod
    def _wrap_list(items, prefix, width=118):
        """Join *items* with ', ' and wrap them in comment lines starting with *prefix*."""
        lines, cur = [], prefix
        for i, item in enumerate(items):
            piece = item + ("," if i < len(items) - 1 else "")
            if len(cur) + len(piece) + 1 > width and cur != prefix:
                lines.append(cur.rstrip())
                cur = prefix
            cur += piece + " "
        if cur != prefix:
            lines.append(cur.rstrip())
        return lines

    @staticmethod
    def _split_file_lines(text):
        """Return the lines of *text* (no phantom empty last line when it ends with a newline)."""
        lines = text.split("\n")
        if len(lines) > 1 and lines[-1] == "":
            lines.pop()
        return lines

    @staticmethod
    def _body_lines(display, lines):
        """Render one file: a FILE line, its content with a locator line every few dozen lines,
        an END FILE line and a blank line.  Locator lines say that the NEXT line is line N of the file.
        """
        size = len("\n".join(lines).encode("utf-8"))
        out = [f"// ===== FILE: {display} ({size} bytes, {len(lines)} lines) ====="]
        since_lines, since_bytes = 0, 0
        for n, line in enumerate(lines, start=1):
            if n > 1 and (since_lines >= PACK_MARKER_EVERY_LINES or since_bytes >= PACK_MARKER_EVERY_BYTES):
                out.append(f"{PACK_MARKER}{display}:{n}")
                since_lines, since_bytes = 0, 0
            out.append(line)
            since_lines += 1
            since_bytes += len(line) + 1
        out.append(f"// ===== END FILE: {display} =====")
        out.append("")
        return out

    def _build_pack_index(self, name, files, binaries, starts, outline_cap):
        """Build the header + index lines of a pack.

        *starts* maps display name -> (first, last) line of the file block in the pack; numbers are
        zero-padded to a fixed width so the number of index lines never depends on them.
        """
        total_bytes = sum(f["bytes"] for f in files)
        idx = [
            f"// ===== CONTENT PACK: {name} =====",
            f"// Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}: {len(files)} text file(s), {total_bytes} bytes of text,"
            f" {len(binaries)} binary file(s) (listed only).",
            "// This single file is a snapshot of a set of files, like a small virtual filesystem; each file is shown verbatim.",
            "//",
            "// HOW TO READ THIS PACK",
            "// - Do not read the whole pack. Only the first ~260 KB can be loaded directly, and this index is built to fit there:",
            "//   look the file up in the INDEX below, then open just that file.",
            "// - Each file starts at '// ===== FILE: <path> (...) =====' and ends at '// ===== END FILE: <path> ====='.",
            "//   The 'pack lines' column gives those two line numbers in this file: with a line-based reader",
            "//   (offset/limit, `sed -n 'A,Bp'`, an editor) you can open exactly one file.",
            "// - Without a line-based reader, search for the file name (e.g. 'task_notes_panel.py') or for a symbol of its outline.",
            f"//   Every few dozen lines a locator line '{PACK_MARKER}<path>:<N>' is inserted, meaning 'the next line is line N of",
            "//   <path>', so any search hit, however small, tells which file and which line it comes from.",
            f"// - Lines starting with '{PACK_MARKER.rstrip()}' (and the FILE / END FILE lines) are added by the packer: they are NOT part of",
            "//   the files and must never be copied back into code. Line numbers (Lnn, :N) refer to the original files.",
            "// - Paths use forward slashes. Files are sorted by path, so a folder's files are next to each other.",
            "// - Empty files are skipped; binary files appear at the end of the index with their size only.",
            "//",
            "// ===== INDEX =====",
            "// path | bytes | lines | pack lines (first-last)",
        ]
        for f in files:
            first, last = starts.get(f["display"], (0, 0))
            idx.append(f"// {f['display']} | {f['bytes']} | {f['line_count']} | {first:07d}-{last:07d}")
            symbols = f["outline"][:outline_cap] if outline_cap else []
            if symbols:
                more = len(f["outline"]) - len(symbols)
                if more > 0:
                    symbols = symbols + [f"... +{more} more"]
                idx.extend(self._wrap_list(symbols, "//     ", 118))
        if binaries:
            idx.append("//")
            idx.append("// ===== BINARY FILES (not included) =====")
            for b in binaries:
                idx.append(f"// {b['display']} ({b['size']} bytes, binary)")
        idx.append("// ===== END OF INDEX =====")
        idx.append("")
        return idx

    def _write_pack(self, name, output, text_entries, binary_entries):
        """Write the single-file pack *output* (see build_content_packs for the layout)."""
        # --- display names: forward slashes, prefixed by the step's folder only on collisions ---
        counts = {}
        for e in text_entries + binary_entries:
            e["norm"] = e["path"].replace("\\", "/")
            counts[e["norm"]] = counts.get(e["norm"], 0) + 1
        for e in text_entries + binary_entries:
            e["display"] = e["norm"] if counts[e["norm"]] == 1 else f"{e['source']}/{e['norm']}"

        text_entries = sorted(text_entries, key=lambda e: e["display"].lower())
        binary_entries = sorted(binary_entries, key=lambda e: e["display"].lower())

        files = []
        for e in text_entries:
            lines = self._split_file_lines(e["text"])
            files.append(
                {
                    "display": e["display"],
                    "lines": lines,
                    "line_count": len(lines),
                    "bytes": len("\n".join(lines).encode("utf-8")),
                    "outline": self._outline(e["display"], lines),
                }
            )
        binaries = [{"display": e["display"], "size": e["size"]} for e in binary_entries]

        # --- pick the richest outline size for which the index still fits the direct-read window ---
        idx = []
        for cap in PACK_OUTLINE_CAPS:
            idx = self._build_pack_index(name, files, binaries, {}, cap)
            if len("\n".join(idx).encode("utf-8")) <= PACK_INDEX_MAX_BYTES:
                break
        else:
            logger.warning(
                "Index of pack '%s' is %d bytes even without outlines: it may not fit the direct-read window.",
                name,
                len("\n".join(idx).encode("utf-8")),
            )
        used_cap = cap

        # --- bodies, and where each file lands (the index length is fixed: numbers are zero-padded) ---
        bodies = {f["display"]: self._body_lines(f["display"], f["lines"]) for f in files}
        line_no = len(idx)  # lines already written; the first body line is line_no + 1
        starts = {}
        for f in files:
            body = bodies[f["display"]]
            starts[f["display"]] = (line_no + 1, line_no + len(body) - 1)  # FILE line .. END FILE line
            line_no += len(body)
        idx = self._build_pack_index(name, files, binaries, starts, used_cap)

        out_lines = list(idx)
        for f in files:
            out_lines.extend(bodies[f["display"]])
        text = "\n".join(out_lines) + "\n"
        self.write_text_file(text, output, mode="w")
        logger.info(
            "Wrote pack %s: %d file(s), %d bytes (index: %d lines, outlines capped at %d symbols per file).",
            output,
            len(files),
            len(text.encode("utf-8")),
            len(idx),
            used_cap,
        )

    @staticmethod
    def _expand_braces(pattern):
        """Expand {a,b} alternatives (nested ones included) into a list of plain patterns.

        Example: "textures/**/*.{jpg,png}" => ["textures/**/*.jpg", "textures/**/*.png"]
        """
        m = re.search(r"\{([^{}]*)\}", pattern)
        if m is None:
            return [pattern]
        out = []
        for alt in m.group(1).split(","):
            out.extend(DevUtils._expand_braces(pattern[: m.start()] + alt + pattern[m.end() :]))
        return out

    @staticmethod
    def _split_patterns(patterns):
        """Split a semicolon-separated pattern string and expand any {a,b} alternatives."""
        result = []
        for p in patterns.split(";"):
            p = p.strip()
            if p:
                result.extend(DevUtils._expand_braces(p))
        return result

    @staticmethod
    def _glob_to_regex(pattern):
        """Convert a glob pattern with ** support to a regular expression.

        - "**/" matches zero or more directories (so "a/**/b.png" matches "a/b.png" and "a/x/y/b.png")
        - a trailing or inline "**" matches anything, including "/"
        - "*" matches any run of characters except "/"
        - "?" matches a single character except "/"
        - "[...]" character classes are supported ("[!...]" for negation)
        """
        pattern = pattern.replace("\\", "/")
        i, n, res = 0, len(pattern), ""
        while i < n:
            c = pattern[i]
            if pattern.startswith("**", i):
                i += 2
                if pattern.startswith("/", i):
                    i += 1
                    res += "(?:.*/)?"
                else:
                    res += ".*"
                continue
            if c == "*":
                res += "[^/]*"
            elif c == "?":
                res += "[^/]"
            elif c == "[" and pattern.find("]", i + 1) != -1:
                j = pattern.find("]", i + 1)
                cls = pattern[i + 1 : j]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                res += "[" + cls + "]"
                i = j
            else:
                res += re.escape(c)
            i += 1
        return res

    @staticmethod
    def _fnmatch_ex(path, pattern):
        """fnmatch extended with ** support (matches zero or more path segments).

        Patterns without '**' keep the plain fnmatch semantics, where '*' also
        matches across '/' (so "*.h" selects headers at any depth).
        """
        path = path.replace("\\", "/")
        if "**" not in pattern:
            return fnmatch.fnmatch(path, pattern)
        return re.fullmatch(DevUtils._glob_to_regex(pattern), path) is not None

    def _collect_entries(self, folder, patterns=None, ignore_patterns=None, include_api_txt=False):
        """Select the files of *folder* and read them.

        Returns (text_entries, binary_entries, total_text_size).  Text entries are dicts with
        'path' (relative to folder), 'size' (bytes on disk) and 'text', sorted by size ascending;
        binary entries only have 'path' and 'size'.  Empty files are dropped.

        The selection rules (include filter, exclude filter, binary detection, *.api.txt and
        .git/.github exclusions) are described in collect_content().
        """
        # --- include filter ---
        if patterns is not None:
            glob_patterns = self._split_patterns(patterns)
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
                allfiles = [f for f in allfiles if any(self._fnmatch_ex(f, p) for p in glob_patterns)]
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
            ignore_globs = self._split_patterns(ignore_patterns)
            allfiles = [f for f in allfiles if not any(self._fnmatch_ex(f, p) for p in ignore_globs)]

        if not allfiles:
            logger.info("No files matched the selection criteria.")
            return [], [], 0

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

        binary_entries = []
        for f in sorted(binary_files, key=lambda f: file_sizes[f]):
            logger.info("Skipping binary file %s (%d bytes)", f, file_sizes[f])
            binary_entries.append({"path": f, "size": file_sizes[f]})

        text_entries = []
        for f in sorted(text_files, key=lambda f: file_sizes[f]):
            size = file_sizes[f]
            pct = (size / total_size * 100.0) if total_size > 0 else 0.0
            logger.info("Reading file %s (%d bytes, %.1f%%)", f, size, pct)
            text_entries.append({"path": f, "size": size, "text": self.read_text_file(self.get_path(folder, f))})

        logger.info(
            "Collected %d text files and %d binary files, total size: %d bytes.",
            len(text_files),
            len(binary_files),
            total_size,
        )
        return text_entries, binary_entries, total_size

    def collect_content(
        self, folder, patterns=None, ignore_patterns=None, output_file=None, include_api_txt=False, append=False
    ):
        """Collect all content from files in the given folder.

        File selection works in three steps:

        1. Include filter (-p / patterns): if provided, keep only files whose
           relative path matches at least one of the semicolon-separated glob
           patterns (e.g. "*.h;gui/*.cpp;config/*.yml").  Patterns support '**'
           (zero or more directories) and {a,b} alternatives
           (e.g. "textures/**/*.{jpg,png}").  When omitted, all files found
           recursively under folder are kept.

        2. Exclude filter (-x / ignore_patterns): if provided, drop any file
           whose relative path matches at least one of the semicolon-separated
           glob patterns (same syntax as above).  Applied after the include filter.

        3. Binary detection: binary files are not inlined but still appear in
           the output as a header-only entry (filename + size) so the reader
           knows they exist.  When -p is given, all matched files are treated
           as text (the caller is assumed to know the file type).

        *.api.txt files are always excluded unless include_api_txt is True.

        Text files are written in ascending size order (smallest first, largest
        last), preceded by binary-file header lines.  Each entry reports its
        size in bytes and as a percentage of the combined total.

        This command keeps the simple single-file format.  The indexed, size-limited
        multi-part format is only produced by build_content_packs().

        output_file sets the destination file name (default: "content.api.txt").
        When append is True, content is appended instead of overwriting.
        """
        text_entries, binary_entries, total_size = self._collect_entries(
            folder, patterns, ignore_patterns, include_api_txt
        )
        if not text_entries and not binary_entries:
            return

        contents = []

        # Binary file headers first, sorted by size ascending.
        for e in binary_entries:
            contents.append(f"// File: {e['path']} ({e['size']} bytes, binary)")

        # Text file contents, sorted by size ascending (smallest first, largest last).
        for e in text_entries:
            pct = (e["size"] / total_size * 100.0) if total_size > 0 else 0.0
            contents.append(f"// File: {e['path']} ({e['size']} bytes, {pct:.1f}% of total):\n")
            contents.append(e["text"])

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
        "Supports '**' and {a,b} alternatives (e.g. 'tex/**/*.{jpg,png}'). "
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
