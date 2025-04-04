"""ETOPO 2022 manager class."""

import logging
import os
import re
import struct

import cv2
import lz4.frame
import numpy as np
import rasterio
import zstandard as zstd
from PIL import Image
from scipy import ndimage

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)

TILE_SIZE = (3600, 3600)  # Tile dimensions in pixels
TILE_DEGREES = 15  # Each tile covers 15x15 degrees


def closest_power_of_2_below(n):
    """Find the largest power of 2 that is less than or equal to n."""
    # Get the largest power of 2 that fits within n
    return 2 ** int(np.floor(np.log2(n)))


def get_power_of_2_dimensions(shape):
    """Convert a shape tuple to the closest power of 2 dimensions below."""
    height, width = shape
    new_height = closest_power_of_2_below(height)
    new_width = closest_power_of_2_below(width)
    return (new_height, new_width)


class EtopoManager(NVPComponent):
    """EtopoManager component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "gen":
            factor = self.get_param("downscale_factor")
            folder = self.get_param("input_dir")
            if folder is None:
                folder = self.get_cwd()
            return self.generate_elevation_map(folder, factor)

        if cmd == "resize":
            imgfile = self.get_param("input_file")
            tsize = self.get_param("target_size")
            return self.resize_image(imgfile, tsize)

        return False

    # Function to extract coordinates from ETOPO filename
    def extract_coordinates(self, filename):
        """
        Extract latitude and longitude from ETOPO 2022 filename.
        Example: 'ETOPO_2022_v1_15s_N45W075_surface.tif'
        indicates 45°N, 75°W.
        """
        # Extract latitude and longitude using regex pattern
        match = re.search(r"([NS])(\d+)([EW])(\d+)", filename)
        if not match:
            raise ValueError(f"Could not parse coordinates from filename: {filename}")

        lat_dir, lat, lon_dir, lon = match.groups()
        lat = int(lat)
        lon = int(lon)

        # Convert to array indices
        # For a (43200, 86400) array covering -90 to 90 lat and -180 to 180 lon:
        # - Each degree is 43200/180 = 240 rows (latitude)
        # - Each degree is 86400/360 = 240 columns (longitude)
        # - Origin is at top-left (90°N, 180°W)

        # Calculate row index (latitude)
        # 90 - lat for N, 90 + lat for S
        row_start = int((90 - lat if lat_dir == "N" else 90 + lat) * 240)

        # Calculate column index (longitude)
        # lon for E, 360 - lon for W
        # Apply an offset of 180 deg east to get the output in range [-180, 180]:
        lon += 180
        col_start = int((lon if lon_dir == "E" else 360 - lon) * 240)

        return row_start, col_start

    # Function to load a tile and place it in the global array
    def load_tile(self, filepath, global_array, downscale):
        """Load a GeoTIFF tile and place it in the correct position in the global array"""
        filename = os.path.basename(filepath)

        # Get the starting position for this tile in the global array
        row_start, col_start = self.extract_coordinates(filename)

        # Should apply the downscale on those coords:
        row_start = row_start // downscale
        col_start = col_start // downscale

        # Read the geotiff data
        with rasterio.open(filepath) as src:
            tile_data = src.read(1)  # Read the first band

        tile_data[tile_data == -99999] = np.nan
        # Apply the downscaling:
        arr = self.downsample_block_mean(tile_data, downscale)

        # amini = np.nanmin(tile_data)
        # amaxi = np.nanmax(tile_data)
        # print(f"Array range [{amini}, {amaxi}]")

        # Place the tile in the global array
        row_end = row_start + arr.shape[0]
        col_end = col_start + arr.shape[1]

        # Check if the tile fits within array bounds
        self.check(row_end <= global_array.shape[0] and col_end <= global_array.shape[1], "Out of range data array!")
        global_array[row_start:row_end, col_start:col_end] = arr

    def get_tile_range(self, filepath):
        """Simple check of tile data range."""
        with rasterio.open(filepath) as src:
            tile_data = src.read(1)  # Read the first band

            tile_data[tile_data == -99999] = np.nan
            amini = np.nanmin(tile_data)
            amaxi = np.nanmax(tile_data)

            return amini, amaxi

    def downsample_block_mean(self, arr, block_size=4):
        """
        Downsample array by averaging blocks of pixels.
        Fast and memory-efficient implementation.

        Parameters:
        -----------
        arr : numpy.ndarray
            Input array to downsample
        block_size : int
            Factor by which to downsample (e.g., 4 means output will be 1/4 the size)

        Returns:
        --------
        numpy.ndarray
            Downsampled array
        """
        # Calculate new dimensions
        new_shape = (arr.shape[0] // block_size, block_size, arr.shape[1] // block_size, block_size)

        # Reshape and take mean over blocks
        return np.nanmean(arr.reshape(new_shape), axis=(1, 3))

    # Process all files
    def process_all_tiles(self, geotiff_files, folder, downscale):
        """Process all the available tiles."""

        logger.info("Processing %d GeoTIFF files...", len(geotiff_files))

        # After the first pass we have those results:
        # vmin = -10907.0
        # vmax = 8585.7158203125

        # Create an empty global array to hold all the data
        ashape = (43200 // downscale, 86400 // downscale)  # Final array shape (rows, columns)

        logger.info("Creating destination array of shape %s", ashape)
        arr = np.zeros(ashape, dtype=np.float32)

        # Process each file
        num = len(geotiff_files)

        # for i, file in enumerate(geotiff_files):
        #     print(f"{i+1}/{num}: Processing {file}...")
        #     amin, amax = get_tile_range(folder+"/"+file)
        #     if i==0:
        #         vmin = amin
        #         vmax = amax
        #     else:
        #         vmin = min(vmin, amin)
        #         vmax = max(vmax, amax)

        # print(f"Global data range is: [{vmin}, {vmax}]")

        for i, file in enumerate(geotiff_files):
            logger.info("%d/%d: Processing %s...", i + 1, num, file)
            self.load_tile(folder + "/" + file, arr, downscale)

        return arr

    def float32_to_uint16(self, float_array, vmin, vmax):
        # Clip the input array to the specified range
        clipped = np.clip(float_array, vmin, vmax)

        # Scale to [0, 1] range
        normalized = (clipped - vmin) / (vmax - vmin)

        # Scale to full uint16 range [0, 65535] and convert
        uint16_array = (normalized * 65535).astype(np.uint16)

        return uint16_array

    def save_uint16_as_lz4(self, array, output_path):
        """Save as lz4."""
        shape = array.shape
        logger.info("Saving file %s...", output_path)

        with open(output_path, "wb") as f:
            # Write shape as two uint64 values
            f.write(np.array(shape, dtype=np.uint64).tobytes())
            # Compress and write the data
            compressed = lz4.frame.compress(array.tobytes())
            f.write(compressed)

    def save_uint16_as_zstd(self, array, output_path, compression_level=19):
        """Save as zstd."""
        logger.info("Saving file %s...", output_path)

        # Create compressor
        cctx = zstd.ZstdCompressor(level=compression_level)

        with open(output_path, "wb") as f:
            # Write header: magic bytes, dtype code, ndim, and shape
            f.write(b"ZSTD")  # Magic bytes to identify our format
            f.write(struct.pack("<H", 16))  # uint16 bit depth (16 bits)
            f.write(struct.pack("<B", array.ndim))  # Number of dimensions

            # Write shape as uint64
            for dim in array.shape:
                f.write(struct.pack("<Q", dim))

            # Compress and write the data
            compressed = cctx.compress(array.tobytes())
            f.write(compressed)

    def save_uint16_as_raw(self, array, output_path):
        """Save as raw."""
        shape = array.shape
        logger.info("Saving file %s...", output_path)

        with open(output_path, "wb") as f:
            # Write shape as two uint64 values
            f.write(np.array(shape, dtype=np.uint64).tobytes())
            f.write(array.tobytes())

    def save_uint16_as_png(self, array, output_path):
        # Make sure the array is uint16
        if array.dtype != np.uint16:
            raise ValueError("Array must be uint16")

        logger.info("Saving file %s...", output_path)

        # compression_level = 9
        # cv2.imwrite(output_path, array, [cv2.IMWRITE_PNG_COMPRESSION, compression_level])

        # Convert to PIL Image
        # For single channel, we use mode 'I;16' for 16-bit unsigned integer
        img = Image.fromarray(array, mode="I;16")

        # Save as PNG
        img.save(output_path, format="PNG")

        print(f"Saved 16-bit PNG to {output_path}")

    def terrain_aware_quantize(self, heights, feature_threshold=50, base_bits=8, feature_bits=12, _compression_level=7):
        """
        Compresses height data with higher precision for important terrain features.

        Parameters:
        -----------
        heights : numpy.ndarray (dtype=uint16)
            Original height data
        feature_threshold : int
            Threshold for detecting important features (local variance)
        base_bits : int
            Precision for flat areas
        feature_bits : int
            Precision for important features
        """
        # Detect important terrain features (high local variance)
        # Calculate local height variance using a 5x5 window
        local_variance = ndimage.generic_filter(heights, np.var, size=5)

        # Create feature mask where variance exceeds threshold
        feature_mask = local_variance > feature_threshold

        # Create quantization masks
        base_shift = 16 - base_bits
        feature_shift = 16 - feature_bits

        # Apply different quantization to flat areas vs. features
        quantized = np.zeros_like(heights)
        quantized[~feature_mask] = (heights[~feature_mask] >> base_shift) << base_shift
        quantized[feature_mask] = (heights[feature_mask] >> feature_shift) << feature_shift

        # # Compress with metadata
        # header = np.array([feature_threshold, base_bits, feature_bits], dtype=np.uint16)
        # data_to_compress = np.concatenate((header, quantized.flatten()))

        # # Compress
        # compressor = zstd.ZstdCompressor(level=compression_level)
        # compressed = compressor.compress(data_to_compress.tobytes())

        # return compressed
        return quantized

    def generate_elevation_map(self, input_folder, downscale):
        """Generate the elevation map."""
        logger.info("Generate etopo map from %s...", input_folder)

        files = self.get_all_files(input_folder, r"\.tif$")
        arr = self.process_all_tiles(files, input_folder, downscale)

        # Rescale to target size:
        nshape = get_power_of_2_dimensions(arr.shape)
        logger.info("Rescaling array from %s to %s...", arr.shape, nshape)

        arr = cv2.resize(arr, (nshape[1], nshape[0]), interpolation=cv2.INTER_LANCZOS4)

        vmin = np.amin(arr)
        vmax = np.amax(arr)

        logger.info("Global data range is: [%f, %f]", vmin, vmax)

        nunnan = np.count_nonzero(arr == np.nan)
        logger.info("Number of nans: %d", nunnan)
        self.check(nunnan == 0, "Found nan in data: %d", nunnan)

        # Rescale to power of 2
        arr = self.float32_to_uint16(arr, vmin, vmax)
        w = arr.shape[1]
        h = arr.shape[0]

        # Quantize the data:
        suffix = ""
        if self.get_param("quantize", False):
            logger.info("Quantizing terrain heights...")
            suffix = "_q"
            arr = self.terrain_aware_quantize(arr)

        bname = f"etopo2022_16bit_{w}x{h}{suffix}"

        self.save_uint16_as_png(arr, f"{bname}.png")
        # self.save_uint16_as_zstd(arr, f"{bname}.bin")
        # self.save_uint16_as_lz4(arr, f"{bname}.lz4")
        # self.save_uint16_as_raw(arr, f"{bname}.raw")

        content = f"vmin={vmin}\nvmax={vmax}"
        self.write_text_file(content, f"{bname}.txt")
        return True

    def resize_image(self, imgfile, tsize):
        """Resize an input image."""
        shape = tsize.split("x")
        w = int(shape[0])
        h = int(shape[1])

        # Load the image using cv2
        arr = cv2.imread(imgfile)
        if arr is None:
            raise ValueError(f"Could not load image: {imgfile}")

        # Resize the image
        arr = cv2.resize(arr, (w, h), interpolation=cv2.INTER_LANCZOS4)

        # Create output filename with dimensions
        filename, ext = os.path.splitext(imgfile)
        output_file = f"{filename}_{w}x{h}{ext}"

        # Save the resized image
        # cv2.imwrite(output_file, arr)
        compression_level = 9
        cv2.imwrite(output_file, arr, [cv2.IMWRITE_PNG_COMPRESSION, compression_level])

        # # Convert to PIL Image
        # img = Image.fromarray(arr, mode="RGB")

        # # Save as PNG
        # img.save(output_file, format="PNG")

        return True


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("EtopoManager", EtopoManager(context))

    psr = context.build_parser("gen")
    # psr.add_str("tag_name")("Input tag to generate a thumbnail for")
    psr.add_str("-i", "--input-dir", dest="input_dir")("Input directory")
    psr.add_int("-d", "--downscale", dest="downscale_factor", default=4)("Downscale factor to use")
    psr.add_flag("-q", "--quantize", dest="quantize")("Quantize terrain data")

    psr = context.build_parser("resize")
    psr.add_str("-i", "--input", dest="input_file")("Input file to resize")
    psr.add_str("-s", "--size", dest="target_size")("target size")

    comp.run()
