"""brotli handling component

This component is used to compress/decompress with brotli"""

import logging
import time

import brotli

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class BrotliHandler(NVPComponent):
    """BrotliHandler component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "compress":
            file = self.get_param("input_file")
            outfile = self.get_param("output_file")
            return self.compress_file(file, outfile)

        if cmd == "decompress":
            file = self.get_param("input_file")
            outfile = self.get_param("output_file")
            return self.decompress_file(file, outfile)

        return False

    def compress_file(self, input_file, output_file=None):
        """Compress a file"""
        if output_file is None:
            output_file = input_file + ".br"

        params = {
            # 'mode': brotli.MODE_TEXT  # Set to brotli.MODE_TEXT for text-based files
            "mode": brotli.MODE_GENERIC,
            "quality": 11,
            "lgwin": 22,
            "lgblock": 0,
        }

        start_time = time.time()
        content = self.read_binary_file(input_file)
        logger.info("Compressing %s...", input_file)
        compressed = brotli.compress(content, **params)

        # write the compressed data:
        self.write_binary_file(compressed, output_file)

        elapsed = time.time() - start_time
        logger.info("Compressed %s in %.2fsecs", input_file, elapsed)

        return True

    def decompress_file(self, input_file, output_file=None):
        """Compress a file"""
        if output_file is None:
            output_file = self.set_path_extension(input_file, "")

        start_time = time.time()
        content = self.read_binary_file(input_file)
        logger.info("Decompressing %s...", input_file)
        decompressed = brotli.decompress(content)

        # write the compressed data:
        self.write_binary_file(decompressed, output_file)

        elapsed = time.time() - start_time
        logger.info("Decompressed %s in %.2fsecs", input_file, elapsed)

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("BrotliHandler", BrotliHandler(context))

    psr = context.build_parser("compress")
    psr.add_str("input_file")("File to compress")
    psr.add_str("-o", "--output", dest="output_file")("Output destination for compress")
    psr = context.build_parser("decompress")
    psr.add_str("input_file")("File to decompress")
    psr.add_str("-o", "--output", dest="output_file")("Output destination for decompress")

    comp.run()
