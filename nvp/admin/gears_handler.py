"""Simple helper script to extract header files from Gears Jfrog artifactory repository"""

import logging

# import time
import re
import zipfile

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


def create_component(ctx: NVPContext):
    """Create an instance of the component"""
    return GearsHandler(ctx)


class GearsHandler(NVPComponent):
    """GearsHandler component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "extract":
            in_dir = self.get_param("input_dir")
            out_dir = self.get_param("output_dir")
            if out_dir is None:
                out_dir = self.get_cwd()
            return self.extract_gears_headers(in_dir, out_dir)

    def extract_gears_headers(self, input_dir, output_dir):
        """Extract the gear header files"""
        # logger.info("Should extract gear headers from %s into %s", input_dir, output_dir)

        logger.info("Searching gears dependencies in %s...", input_dir)

        # Collect all the latest zip files:
        dep_pat = re.compile("^([^\-]+)-([0-9]+).zip")

        # Storage for the lates version of each dep and the corresponding fullpath:
        dep_versions = {}
        dep_files = {}

        all_files = self.get_all_files(input_dir, exp=r"\.zip$", recursive=True)
        for fname in all_files:
            fullpath = self.get_path(input_dir, fname)
            folder = self.get_parent_folder(fullpath)
            filename = self.get_filename(fullpath)

            # Check if that file matches an "depname-number.zip" pattern:
            match = dep_pat.search(filename)
            if match:
                depname = match.group(1)
                depver = int(match.group(2))
                # print(f"Found dep {depname} with version {depver}")
                # For each 'depname' we should only keep the latest depver:
                cur_ver = dep_versions.get(depname, -1)
                if depver > cur_ver:
                    logger.info("Upgrading %s to version %d", depname, depver)

                    dep_versions[depname] = depver
                    dep_files[depname] = fullpath

        logger.info("Collected %d gears dependencies. Extracting...")

        extract_dir = self.get_path(output_dir, "extracted")
        self.make_folder(extract_dir)

        for fname in dep_files.values():
            logger.info("Extracting %s", fname)

            with zipfile.ZipFile(fname, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

        # Next we collect all the .h files from the extract_dir, into a new include dir:
        include_dir = self.get_path(output_dir, "include")
        self.make_folder(include_dir)

        logger.info("Collecting header files...")

        all_files = self.get_all_files(extract_dir, recursive=True)

        for fname in all_files:
            ext = self.get_path_extension(fname)
            if ext not in [".h", ".hpp"]:
                continue

            if "{" in fname:
                continue

            # logger.info("Header: %s", fname)
            filename = self.get_filename(fname)
            fullpath = self.get_path(extract_dir, fname)

            dstpath = self.get_path(include_dir, filename)
            self.move_path(fullpath, dstpath)

        self.remove_folder(extract_dir, recursive=True)

        logger.info("Generating zip package...")
        output_folder = self.get_parent_folder(output_dir)
        pkg_name = self.get_filename(output_dir) + ".7z"

        tools = self.get_component("tools")
        tools.create_package(output_dir, output_folder, pkg_name)

        logger.info("Done.")

        # for root, d_names, f_names in os.walk(extract_dir):
        #     for f in f_names:
        #         # ignore the file starting with {NAME}
        #         if (f.lower().endswith(".h") or f.lower().endswith(".hpp")) and not f.startswith("{"):
        #             # print(f"Found file {f}")

        #             os.rename(os.path.join(root, f), os.path.join(include_dir, f))

        # # Remove the extracted dir:
        # shutil.rmtree(extract_dir)

        # print(f"Done: header files available in {include_dir}.")

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("GearsHandler", GearsHandler(context))

    psr = context.build_parser("extract")
    psr.add_str("input_dir")("Input dir to use")
    psr.add_str("-o", "--output", dest="output_dir")("Output destination")

    comp.run()
