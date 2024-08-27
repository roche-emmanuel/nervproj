"""Module for Netcdf Manager
"""

import logging

from deepdiff import DeepDiff

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext
from nvp.tools.ncschema import NCSchema

logger = logging.getLogger(__name__)


class NetCDFManager(NVPComponent):
    """NetCDFManager component class"""

    def __init__(self, ctx: NVPContext):
        """class constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "extract_schemas":
            pat = self.get_param("pattern")
            # logger.info("Using pattern: %s", pat)

            # get all the files in the input folder:
            folder = self.get_cwd()
            all_files = self.get_all_files(folder, exp=pat, recursive=True)
            for fname in all_files:
                full_path = self.get_path(folder, fname)
                output_file = self.set_path_extension(full_path, ".schema.yaml")
                self.write_schema(full_path, output_file)
            return True

        if cmd == "compare_schemas":
            pat = self.get_param("pattern")
            # logger.info("Using pattern: %s", pat)

            # get all the files in the input folder:
            folder = self.get_cwd()
            all_files = self.get_all_files(folder, exp=pat, recursive=True)
            if len(all_files) <= 1:
                logger.info("Nothing schema found.")
                return True

            # Read the first schema as reference:
            ref_schema = self.read_yaml(self.get_path(folder, all_files[0]))
            all_files.pop(0)

            diffs_found = False
            for fname in all_files:
                full_path = self.get_path(folder, fname)
                schema = self.read_yaml(full_path)
                if self.compare_schemas(ref_schema, schema):
                    diffs_found = True

            if not diffs_found:
                logger.info("No difference found.")

            return True

        return False

    def write_schema(self, input_file, output_file):
        """Write the schema of a given netcdf file to file."""

        logger.info("Should write schema for %s to %s", input_file, output_file)

        # Create an NCSchema for this file:
        schema = NCSchema(input_file)
        logger.info("Extracted %d variables.", len(schema.variables))
        schema.write_yaml_file(output_file)

    def compare_schemas(self, ref_schema, schema):
        """Compare 2 schemas listing the differences"""
        diff = DeepDiff(ref_schema, schema, ignore_order=True)
        if diff is None:
            return False

        ignored_changes = [
            "root['grp_attribs']['root']['product_name']",
            "root['grp_attribs']['root']['sensing_end_time_utc']",
            "root['grp_attribs']['root']['sensing_start_time_utc']",
            "root['grp_attribs']['status/processing']['source']",
        ]

        count = 0

        logger.info("Differences found:")
        for change_type, changes in diff.items():
            logger.info("%s:", change_type)
            if change_type in ["values_changed", "type_changes"]:
                for change, change_details in changes.items():
                    if change in ignored_changes:
                        continue

                    ref_value = change_details.get("old_value", "N/A")
                    cur_value = change_details.get("new_value", "N/A")
                    logger.info("  %s: %s -> %s", change, ref_value, cur_value)
                    count += 1
            elif change_type in [
                "dictionary_item_added",
                "dictionary_item_removed",
                "iterable_item_added",
                "iterable_item_removed",
            ]:
                for change in changes:
                    if change_type.endswith("_added"):
                        logger.info("  %s: None -> %s", change, changes[change])
                    else:  # removed
                        logger.info("  %s: %s -> None", change, changes[change])
                    count += 1
            else:
                for change in changes:
                    logger.info("  %s", change)
                    count += 1

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("NetCDFManager", NetCDFManager(context))

    psr = context.build_parser("extract_schemas")
    psr.add_str("-p", "--pattern", dest="pattern", default=r"\.nc$")("Input file pattern")

    psr = context.build_parser("compare_schemas")
    psr.add_str("-p", "--pattern", dest="pattern", default=r"\.schema\.yaml$")("Schema file pattern")

    comp.run()
