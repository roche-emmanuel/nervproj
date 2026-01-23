"""
Copernicus GLO-30 DEM Dataset Downloader
Downloads the global 30m resolution Digital Elevation Model from Copernicus.
"""
# Example command to download with aws:
# nvp aws s3 cp --no-sign-request s3://copernicus-dem-30m/Copernicus_DSM_COG_10_S90_00_W176_00_DEM/Copernicus_DSM_COG_10_S90_00_W176_00_DEM.tif .

# Example command to download tiles:
# nvp copernicus_dl --lat=-22,-20 --lon=55,56

# Example to generate an heightmap:
# nvp copernicus_genmap --lat=-22.00 --lon=54.50 --xsize=2.0 --ysize=2.0 --xres=8192 --yres=8192 -o output.png --scale=10.0 [obsolete]

# or:
# nvp copernicus_genmap --lat=-22.00 --lon=54.50 --size=2.0 --res=16384 -o output.png --scale=10.0 [obsolete]

# For unreal engine terrain:
# nvp copernicus_genmap --lat-min=-21.3929 --lat-max=-20.8671 --lon-min=55.2131 --lon-max=55.8414 --res=8129 -o output.png --hscale=10.0 --noise-amp=60
# This generate a terrain of size=~69.942km so in unreal we need a scale factor of: 69942/8128 = 8.605068  -> 860.5068

# Note: hscale=10.0 is good for unreal engine for instance as 1 unit = 10cm

# To check: 
# https://github.com/mdbartos/pysheds
# https://richdem.readthedocs.io/en/latest/

import math
import numpy as np
from PIL import Image
from noise import snoise2
import pyfastnoisesimd as fns
from landlab import RasterModelGrid
from landlab.components import FlowAccumulator, StreamPowerEroder

import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

class CopernicusManager(NVPComponent):
    """CopernicusManager component class"""

    def __init__(self, ctx: NVPContext):
        """class constructor"""
        NVPComponent.__init__(self, ctx)
        # self.base_url = "https://copernicus-dem-30m.s3.amazonaws.com"
        self.base_url = "s3://copernicus-dem-30m"

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "download":
            self.download_data()
            return True
        
        if cmd == "gen_heightmap":
            self.generate_heightmap()
            return True
    
        return False

    def generate_tile_list(self, lat_range, lon_range):
        """
        Generate list of all GLO-30 tile names.
        Tiles are named like: Copernicus_DSM_COG_10_N00_00_E006_00_DEM
        Coverage: 90N to 90S, 180W to 180E in 1-degree tiles
        """
        tiles = []
        
        # Latitude: 90N to 90S (but actual coverage is ~85N to 90S)
        for lat in range(lat_range[0], lat_range[1]):  # 85N to 90S
            lat_hem = 'N' if lat >= 0 else 'S'
            lat_str = f"{abs(lat):02d}_00"
            
            # Longitude: 180W to 180E
            for lon in range(lon_range[0], lon_range[1]):
                lon_hem = 'E' if lon >= 0 else 'W'
                lon_str = f"{abs(lon):03d}_00"
                
                tile_name = f"Copernicus_DSM_COG_10_{lat_hem}{lat_str}_{lon_hem}{lon_str}_DEM"
                tiles.append(tile_name)
        
        return tiles

    def get_tile_url(self, tile_name: str) -> str:
        """Get the download URL for a specific tile."""
        # Construct S3 URL path
        url = f"{self.base_url}/{tile_name}/{tile_name}.tif"
        return url

    def download_tile(self, tile_name, out_dir):
        """Download a given tile."""
        output_file = self.get_path(out_dir , f"{tile_name}.tif")
        
        # Skip if already downloaded
        if self.file_exists(output_file):
            self.info("File %s already exists.", output_file)
            return

        url = self.get_tile_url(tile_name)
        self.info("Downloading %s...", url)
        # tools = self.get_component("tools")
        # tools.download_file(url, output_file)
        self.execute_nvp("aws", "s3", "cp", "--no-sign-request", url, output_file)

    def get_available_tiles(self, out_dir):
        """
        Load available tile list from JSON cache, or fetch from S3 if missing.
        """
        json_file = self.get_path(out_dir, "available_tiles.json")

        if self.file_exists(json_file):
            self.info("Loading available tiles from %s", json_file)
            return set(self.read_json(json_file))

        self.info("Fetching available tiles from S3...")
        tiles = self.fetch_available_tiles_from_s3()

        self.write_json(sorted(list(tiles)), json_file)
        self.info("Saved %d available tiles to %s", len(tiles), json_file)

        return tiles

    def execute_nvp(self, *args):
        """Execute an nvp script."""
        root_dir = self.ctx.get_root_dir()

        cmd = [self.get_path(root_dir, "nvp.bat")] + list(args)

        return self.execute_command(cmd)

    def fetch_available_tiles_from_s3(self):
        """
        Run `aws s3 ls` on the bucket root and extract tile folder names.
        """
        outputs, _errs, rcode = self.execute_nvp(
            "aws", "s3", "ls", "--no-sign-request", self.base_url
        )

        self.check(rcode==0, "Cannot fetch tiles from S3.")
        
        return self.parse_s3_ls_output(outputs)

    def parse_s3_ls_output(self, output):
        """
        Parse aws s3 ls output and extract folder names.
        Expected format:
            PRE Copernicus_DSM_COG_10_N00_00_E006_00_DEM/
        """
        tiles = set()

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("PRE"):
                name = line.split()[-1].rstrip("/")
                tiles.add(name)

        return tiles
    
    def download_data(self):
        """Download the copernicus dataset."""
        lats =  [int(k) for k in self.get_param("lat_range").split(",")]
        lons =  [int(k) for k in self.get_param("lon_range").split(",")]

        out_dir = self.get_param("output_dir")
        if out_dir is None:
            out_dir = self.get_cwd()

        available_tiles = self.get_available_tiles(out_dir)
        self.info("Found %d available tiles", len(available_tiles))

        tile_names = self.generate_tile_list(lats, lons)
        self.info("Generated %d tile names", len(tile_names))

        for tname in tile_names:
            if tname not in available_tiles:
                self.debug("Tile %s not available, skipping", tname)
                continue
    
            self.download_tile(tname, out_dir)

    def get_tile_bounds(self, lat, lon):
        """
        Returns the integer tile origin for a given lat/lon.
        """
        return math.floor(lat), math.floor(lon)


    def tiles_for_bbox(self, lat0, lon0, lat1, lon1):
        """
        Compute all Copernicus tile names intersecting a bbox.
        """
        tiles = []

        for lat in range(math.floor(lat0), math.ceil(lat1)):
            for lon in range(math.floor(lon0), math.ceil(lon1)):
                lat_hem = 'N' if lat >= 0 else 'S'
                lon_hem = 'E' if lon >= 0 else 'W'

                tile = (
                    f"Copernicus_DSM_COG_10_"
                    f"{lat_hem}{abs(lat):02d}_00_"
                    f"{lon_hem}{abs(lon):03d}_00_DEM"
                )
                tiles.append(tile)

        return tiles
    
    def add_fractal_noise_v0(self, heightmap, scale=100.0, amplitude=5.0, octaves=4):
        h, w = heightmap.shape
        noise_map = np.zeros_like(heightmap, dtype=np.float32)

        for y in range(h):
            for x in range(w):
                noise_map[y, x] = snoise2(
                    x / scale,
                    y / scale,
                    octaves=octaves,
                    persistence=0.5,
                    lacunarity=2.0
                )

        return heightmap + noise_map * amplitude

    def add_fractal_noise_v1(self, heightmap, scale=1.0, amplitude=5.0, octaves=4):
        seed = np.random.randint(2**31)
        N_threads = None

        perlin = fns.Noise(seed=seed, numWorkers=N_threads)
        perlin.frequency = 0.02 * scale
        # perlin.noiseType = fns.NoiseType.Perlin
        perlin.noiseType = fns.NoiseType.PerlinFractal
        perlin.fractalType = fns.FractalType.FBM
        perlin.fractal.octaves = octaves
        perlin.fractal.lacunarity = 2.1
        perlin.fractal.gain = 0.45
        perlin.perturb.perturbType = fns.PerturbType.NoPerturb
        noise_map = perlin.genAsGrid(heightmap.shape)

        return heightmap + noise_map * amplitude

    def add_fractal_noise(self, heightmap, scale=1.0, amplitude=5.0):
        # cf. https://pyfastnoisesimd.readthedocs.io/en/latest/python_api.html
        seed = np.random.randint(2**31)
        N_threads = None

        perlin = fns.Noise(seed=seed, numWorkers=N_threads)
        perlin.frequency = 0.02 * scale
        # perlin.noiseType = fns.NoiseType.Perlin
        perlin.noiseType = fns.NoiseType.SimplexFractal
        perlin.fractalType = fns.FractalType.Billow
        perlin.fractal.octaves = 7
        perlin.fractal.lacunarity = 2.0
        perlin.fractal.gain = 0.5
        perlin.perturb.perturbType = fns.PerturbType.GradientFractal
        perlin.perturb.amplitude = 1.5
        perlin.perturb.octaves = 7
        perlin.perturb.frequency = 0.2 * 0.001
        perlin.perturb.lacunarity = 2.0
        perlin.perturb.gain = 0.5

        # Calculate next power of 2 for each dimension
        def next_power_of_2(n):
            return 2 ** int(np.ceil(np.log2(n)))
        
        noise_shape = tuple(next_power_of_2(dim) for dim in heightmap.shape)
        
        # Generate noise at power-of-2 size
        noise_map = perlin.genAsGrid(noise_shape)
        
        # Crop to original heightmap size
        noise_map = noise_map[:heightmap.shape[0], :heightmap.shape[1]]
        
        self.info("Noise map range: min=%.2f max=%.2f", noise_map.min(), noise_map.max())

        return heightmap + noise_map * amplitude

    # Note: the method below is way too slow (even at 4k resolution it will take ages.)
    def apply_erosion(self, heightmap, size, lat0):
        """Apply erosion with landlab."""
        # After creating your initial heightmap
        shape = heightmap.shape

        # Convert degrees to meters
        # At the equator: 1 degree ≈ 111,320 meters
        # For latitude adjustment:
        meters_per_degree_lat = 111320  # roughly constant
        meters_per_degree_lon = 111320 * np.cos(np.radians(lat0 + size[1]/2))  # varies with latitude

        dx = (size[0] * meters_per_degree_lon) / shape[0]  # meters per pixel in x
        dy = (size[1] * meters_per_degree_lat) / shape[1]  # meters per pixel in y


        grid = RasterModelGrid(shape, xy_spacing=(dx, dy))
        grid.add_field('topographic__elevation', heightmap.flatten().astype(float), at='node')

        fa = FlowAccumulator(grid)
        sp = StreamPowerEroder(grid, K_sp=0.001)

        for i in range(100):  # erosion timesteps
            self.info("Running erosion step %d/100...", i+1)
            fa.run_one_step()
            sp.run_one_step(dt=1000)

        heightmap = grid.at_node['topographic__elevation'].reshape(shape).astype(np.float32)
        return heightmap

    def generate_heightmap(self):
        lat0 = self.get_param("lat_min")
        lon0 = self.get_param("lon_min")
        lat1 = self.get_param("lat_max")
        lon1 = self.get_param("lon_max")

        nodata_height = self.get_param("no_data_height")
        self.info("Using no-data height value: %f", nodata_height)

        # size = self.get_param("size")
        # xsize = float(self.get_param("xsize", size))
        # ysize = float(self.get_param("ysize", size))
        xsize = abs(lon1-lon0)
        ysize = abs(lat1-lat0)
        size = max(xsize, ysize)
        clat = (lat1+lat0)*0.5
        clon = (lon1+lon0)*0.5
        lat0 = clat - size*0.5
        lat1 = clat + size*0.5
        lon0 = clon - size*0.5
        lon1 = clon + size*0.5

        km_size = 111.320 * size
        self.info("Effective coords: lat0=%.6f, lon0=%.6f, lat1=%.6f, lon1=%.6f, size=%.6f (~%.3fkm)", lat0,lon0,lat1,lon1,size,km_size)

        res = self.get_param("res")
        xres = res
        yres = res
        # xres = int(self.get_param("xres", res))
        # yres = int(self.get_param("yres", res))
        scale = float(self.get_param("hscale"))

        out_file = self.get_param("output_file")
        if out_file is None:
            out_file = "heightmap.png"

        self.info("Generating heightmap:")
        self.info("  BBOX: lat [%f, %f], lon [%f, %f]", lat0, lat1, lon0, lon1)
        self.info("  Resolution: %dx%d", xres, yres)

        # Target grid
        transform = from_bounds(lon0, lat0, lon1, lat1, xres, yres)

        target = np.full((yres, xres), np.nan, dtype=np.float32)

        tiles = self.tiles_for_bbox(lat0, lon0, lat1, lon1)
        self.info("Using %d tiles", len(tiles))

        for tile in tiles:
            tif = self.get_path(self.get_cwd(), f"{tile}.tif")
            if not self.file_exists(tif):
                continue

            self.info("Reading %s", tile)

            with rasterio.open(tif) as src:
                temp = np.full((yres, xres), np.nan, dtype=np.float32)

                reproject(
                    source=rasterio.band(src, 1),
                    destination=temp,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.bilinear,
                    src_nodata=src.nodata,
                    dst_nodata=np.nan,
                )

                mask = ~np.isnan(temp)

                valid = temp[mask]

                if valid.size > 0:
                    self.info(
                        "Tile %s range: min=%.2f max=%.2f",
                        tile,
                        valid.min(),
                        valid.max(),
                    )
                else:
                    self.warn("Tile %s has no valid data in ROI", tile)
                    
                # Composite: only write valid pixels
                target[mask] = temp[mask]


        # Convert to uint16
        valid = target[~np.isnan(target)]

        if valid.size > 0:
            self.info(
                "Final heightmap range (meters): min=%.2f max=%.2f",
                valid.min(),
                valid.max(),
            )
        else:
            self.warn("Final heightmap has no valid data")
        

        heightmap = np.nan_to_num(target, nan=nodata_height)*scale

        # self.info("Adding erosion...")
        # heightmap = self.apply_erosion(heightmap, [xsize, ysize], lat0 + ysize*0.5)

        amp = self.get_param("noise_amp")
        self.info("Adding fractal noise with amplitude=%f...", amp)
        heightmap = self.add_fractal_noise(heightmap, scale=0.3, amplitude=amp*scale)

        self.info(
            "Final range with noise (meters): min=%.2f max=%.2f",
            heightmap.min(),
            heightmap.max(),
        )
    
        self.info("Writing image file...")
        heightmap = np.clip(heightmap-nodata_height, 0, 65535).astype(np.uint16)

        img = Image.fromarray(heightmap, mode="I;16")
        img.save(out_file)

        self.info("Heightmap saved to %s", out_file)
        
if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("CopernicusManager", CopernicusManager(context))

    psr = context.build_parser("download")
    psr.add_str("--lat", dest="lat_range", default="-85,90")("Latitude range")
    psr.add_str("--lon", dest="lon_range", default="-180,180")("Longitude range")
    psr.add_str("-o","--output-dir", dest="output_dir")("Output directory")

    psr = context.build_parser("gen_heightmap")
    # psr.add_str("--lat")("Start latitude")
    # psr.add_str("--lon")("Start longitude")
    # psr.add_float("--size")("Default size (degrees)")
    # psr.add_str("--xsize")("Longitude size (degrees)")
    # psr.add_str("--ysize")("Latitude size (degrees)")

    psr.add_float("--lat-min")("Min lattitude")
    psr.add_float("--lat-max")("Max lattitude")
    psr.add_float("--lon-min")("Min longitude")
    psr.add_float("--lon-max")("Max longitude")
    psr.add_int("--res")("Default Output size (pixels)")
    # psr.add_str("--xres")("Output width (pixels)")
    # psr.add_str("--yres")("Output height (pixels)")
    psr.add_float("--hscale", default=1.0)("Scale for height")
    psr.add_float("--noise-amp", default=50.0)("Noise amplitude")
    psr.add_float("--no-data-height", default=-1000.0)("No data height value")
    psr.add_str("-o", "--output-file", dest="output_file")("Output PNG file")

    comp.run()
