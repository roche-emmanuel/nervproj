"""Module for Netcdf Manager
"""

import logging

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

        return False

    def write_schema(self, input_file, output_file):
        """Write the schema of a given netcdf file to file."""

        logger.info("Should write schema for %s to %s", input_file, output_file)

        # Create an NCSchema for this file:
        schema = NCSchema(input_file)
        logger.info("Extracted %d variables.", len(schema.variables))
        schema.write_yaml_file(output_file)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("NetCDFManager", NetCDFManager(context))

    psr = context.build_parser("extract_schemas")
    psr.add_str("-p", "--pattern", dest="pattern", default="\.nc$")("Input file pattern")

    # psr = context.build_parser("compare_schemas")
    # psr.add_str("-p", "--pattern", dest="pattern", default="\.schema\.yaml$")("Schema file pattern")

    comp.run()
