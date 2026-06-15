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
# nvp copernicus_genmap --lat-min=-21.3929 --lat-max=-20.8671 --lon-min=55.2131 --lon-max=55.8414 --res=8161 -o hf_reunion_8k_ue.png --hscale=10.0 --noise-amp=60
# This generate a terrain of size=~69.942km so in unreal we need a scale factor of: 69942/8128 = 8.605068  -> 860.5068

# Note: hscale is a vertical exaggeration factor applied to elevation data before encoding
#       (e.g. hscale=2.0 doubles the apparent relief). Default 1.0 = real-world scale.
#
# Heightmap encoding convention (UE5):
#   UE reads: localZ_cm = (raw_u16 - 32768) / 128 * DrawScale3D.Z
#   So raw 32768 = Z 0 (world origin / sea level).
#
#   We encode using the full 16-bit range by normalising to the actual data extents:
#     max_range       = max(elev_max_m, abs(elev_min_m))   after vertical exaggeration
#     counts_per_m    = 32767.0 / max_range
#     raw             = clip(elevation_m * counts_per_m + 32768, 0, 65535)
#
#   The matching UE DrawScale3D.Z (written to sidecar as "height_scale") is:
#     ue_height_scale_cm = 12800.0 * max_range / 32767.0
#
#   This gives zero clipping and maximum precision for any terrain, regardless of
#   elevation range, without any manual hscale tuning.

# To check: 
# https://github.com/mdbartos/pysheds
# https://richdem.readthedocs.io/en/latest/

import json
import math
import os
import numpy as np
from PIL import Image
from noise import snoise2
import pyfastnoisesimd as fns
from landlab import RasterModelGrid
from landlab.components import FlowAccumulator, StreamPowerEroder

from scipy.ndimage import gaussian_filter

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
        
        proj = self.ctx.get_project("NervHome")
        self.config = proj.get_config().get("copernicus", {})

        self._default_tiles_dir = self.config["default_tiles_dir"]

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

    def apply_underwater_blend(self, heightmap, undersea_height):
        """
        Blend underwater areas with a fixed undersea height using gaussian blur transition.
        
        Args:
            heightmap: The heightmap array with noise already added
            nodata_height: The sea level height value
            scale: The height scale factor
            
        Returns:
            The blended heightmap
        """
        blur_radius = self.get_param("underwater_blur_radius", 150.0)
        blend_power = self.get_param("underwater_blend_power", 2.0)
        
        self.info("Applying underwater blend: blur_radius=%.1f, power=%.1f, undersea_height=%.1f", 
                  blur_radius, blend_power, undersea_height)
        
        # Create mask: 1.0 for ground (>0), 0.0 for sea (<=0)
        # Note: heightmap already has nodata_height added, so check against nodata_height*scale
        ground_mask = (heightmap > 0.0).astype(np.float32)
        
        # Apply gaussian blur to the mask
        blurred_mask = gaussian_filter(ground_mask, sigma=blur_radius)
        
        # Apply power to make values closer to 0 quickly
        blurred_power = np.power(np.clip(blurred_mask*2.0, 0.0, 1.0), blend_power)
        # blurred_power = np.power(blurred_mask, blend_power)
        
        # Create undersea height array
        undersea_array = np.full_like(heightmap, undersea_height)
        
        # Blend heightmap with undersea height
        blended = heightmap * blurred_power + undersea_array * (1.0 - blurred_power)
        
        self.info("Underwater blend complete. Range: min=%.2f max=%.2f", 
                  blended.min(), blended.max())
        
        return blended
    
    # Valid UE5 landscape heightmap resolutions (quads per side + 1)
    UE_VALID_RESOLUTIONS = [127, 253, 505, 1009, 2017, 4033, 8129, 16257]

    @staticmethod
    def snap_to_ue_res(res):
        """
        Round a requested resolution to the nearest valid UE5 landscape size.
        UE5 requires landscape dimensions of the form (2^n * C + 1) for specific C values.
        Valid sizes: 127, 253, 505, 1009, 2017, 4033, 8129, 16257
        Returns (snapped_res, was_snapped).
        """
        valid = CopernicusManager.UE_VALID_RESOLUTIONS
        nearest = min(valid, key=lambda v: abs(v - res))
        return nearest, nearest != res

    @staticmethod
    def compute_ue_scale(size_m, res):
        """
        Compute the XY scale factor to paste into UE5 Landscape settings.
        UE5 uses centimetres internally; the landscape quad count is (res - 1).
        Returns ue_scale in cm/quad, e.g. 860.5068 for a 69942m / 8129-res terrain.
        """
        quads = res - 1
        return (size_m / quads) * 100.0  # metres -> centimetres

    @staticmethod
    def compute_size_m(lat0, lon0, lat1, lon1):
        """
        Approximate the real-world side length in metres for a square geographic bbox.
        Uses the mean-latitude cosine correction for the longitude dimension and
        the standard 111320 m/degree for the latitude dimension.
        Returns size_m (the larger of the two sides, consistent with the square-snap
        already performed in generate_heightmap).
        """
        mean_lat = (lat0 + lat1) * 0.5
        lat_m = abs(lat1 - lat0) * 111320.0
        lon_m = abs(lon1 - lon0) * 111320.0 * math.cos(math.radians(mean_lat))
        return max(lat_m, lon_m)

    def write_sidecar(self, out_file, lat0, lon0, lat1, lon1, res,
                      ue_height_scale_cm, elev_min_m=None, elev_max_m=None):
        """
        Write a JSON sidecar alongside the heightmap PNG with all metadata
        needed by ArgusWorldBuilder to configure the UE5 landscape import.

        ue_height_scale_cm is the DrawScale3D.Z value (in cm) that UE must use to
        correctly reconstruct real-world elevations from the encoded heightmap.
        It is derived from the actual data extents — not a manual input parameter.

        sea_level_raw is always 32768: the raw uint16 value that maps to Z=0 in UE5:
          localZ_cm = (raw_u16 - 32768) / 128 * DrawScale3D.Z

        elev_min_m / elev_max_m are the physical elevation extents (metres) of the
        exported heightmap after vertical exaggeration, for diagnostics.
        """
        size_m = self.compute_size_m(lat0, lon0, lat1, lon1)
        ue_scale = self.compute_ue_scale(size_m, res)

        # Origin is the south-west corner (min lat, min lon)
        origin_lat = min(lat0, lat1)
        origin_lon = min(lon0, lon1)

        sidecar = {
            "origin_lat":    round(origin_lat, 6),
            "origin_lon":    round(origin_lon, 6),
            "size_m":        round(size_m, 3),
            "ue_scale":      round(ue_scale, 4),
            # DrawScale3D.Z for the UE landscape actor (cm).
            # Derived from actual data extents: 12800 * max_range / 32767
            "height_scale":  round(ue_height_scale_cm, 4),
            "res_x":         res,
            "res_y":         res,
            # Encoding reference: raw 32768 = sea level = UE Z 0.
            # localZ_cm = (raw_u16 - 32768) / 128 * DrawScale3D.Z
            "sea_level_raw": 32768,
            "elev_min_m":    round(float(elev_min_m), 2) if elev_min_m is not None else None,
            "elev_max_m":    round(float(elev_max_m), 2) if elev_max_m is not None else None,
        }

        stem, _ = os.path.splitext(out_file)
        sidecar_path = stem + ".json"

        self.write_json(sidecar, sidecar_path)

        self.info("Sidecar written to %s", sidecar_path)
        self.info("  origin_lat=%.6f  origin_lon=%.6f", origin_lat, origin_lon)
        self.info("  size_m=%.1f  ue_scale=%.4f  height_scale=%.4f cm", size_m, ue_scale, ue_height_scale_cm)
        self.info("  sea_level_raw=32768  elev_min_m=%.2f  elev_max_m=%.2f",
                  elev_min_m if elev_min_m is not None else float('nan'),
                  elev_max_m if elev_max_m is not None else float('nan'))
        return sidecar_path

    def generate_heightmap(self):

        cfgfile = self.get_param("config")
        cfg = {}
        if cfgfile is not None:
            cfg = self.read_yaml(cfgfile)

        lat0 = self.get_param("lat_min", cfg.get("min_lat"))
        lon0 = self.get_param("lon_min", cfg.get("min_lon"))
        lat1 = self.get_param("lat_max", cfg.get("max_lat"))
        lon1 = self.get_param("lon_max", cfg.get("max_lon"))

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

        res = self.get_param("res", cfg.get("res"))
        # scale is the internal pipeline unit factor (metres → pipeline units).
        # We keep the pipeline in raw metres (scale=1.0); vertical exaggeration
        # (hscale) is applied only at the final encoding step, not here.
        scale = 1.0

        # --ue-res: snap to nearest valid UE5 landscape resolution
        if self.get_param("ue_res", cfg.get("snap_ue_res")):
            snapped, was_snapped = self.snap_to_ue_res(res)
            if was_snapped:
                self.warn(
                    "--ue-res: requested res=%d is not a valid UE5 landscape size. "
                    "Snapping to nearest valid size: %d. "
                    "Valid sizes: %s",
                    res, snapped, CopernicusManager.UE_VALID_RESOLUTIONS,
                )
                res = snapped
            else:
                self.info("--ue-res: res=%d is already a valid UE5 landscape size.", res)

        xres = res
        yres = res

        undersea_height = self.get_param("undersea_height", cfg.get("undersea_height", -200)) * scale
        self.info("Using undersea height value: %f", undersea_height)

        # --world-id: write output into <cwd>/output/<world_id>/heightmap.png
        out_dir = self.get_param("output_dir", cfg.get("output_dir"))
        if out_dir is None:
            out_dir = self.get_cwd()

        self.make_folder(out_dir)
        out_file = self.get_path(out_dir, "heightmap.png")

        self.info("Generating heightmap:")
        self.info("  BBOX: lat [%f, %f], lon [%f, %f]", lat0, lat1, lon0, lon1)
        self.info("  Resolution: %dx%d", xres, yres)

        # Target grid
        transform = from_bounds(lon0, lat0, lon1, lat1, xres, yres)

        target = np.full((yres, xres), np.nan, dtype=np.float32)

        tiles = self.tiles_for_bbox(lat0, lon0, lat1, lon1)
        self.info("Using %d tiles", len(tiles))

        tiles_dir = self.get_param("tiles_dir", cfg.get("tiles_dir", self._default_tiles_dir))

        for tile in tiles:
            tif = self.get_path(tiles_dir, f"{tile}.tif")
            if not self.file_exists(tif):
                self.warn("Missing glo30 tile %s", tif)
                continue

            self.info("Reading %s", tile)

            with rasterio.open(tif) as src:
                temp = np.full((yres, xres), np.nan, dtype=np.float32)

                self.info("Source no data is: %s", src.nodata)

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


        self.info("Found %d nodata pixels is result.", np.count_nonzero(np.isnan(target)))

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
        
        # Actually we have data everywhere, so we should replace height <=0.0 with sea height(=no data height)

        heightmap = np.nan_to_num(target*scale, nan=undersea_height)

        # self.info("Adding erosion...")
        # heightmap = self.apply_erosion(heightmap, [xsize, ysize], lat0 + ysize*0.5)
        # Apply underwater blending
        amp = self.get_param("noise_amp", cfg.get("noise_amp", 50.0))

        # Note: we move up by the noise amplitude here because we can still add this noise down afterwards:
        heightmap = self.apply_underwater_blend(heightmap, undersea_height + amp*scale)
        # heightmap[heightmap<=0.0] = undersea_height + amp*scale
        # heightmap[heightmap<=0.0] = undersea_height
        
        self.info("Adding fractal noise with amplitude=%f...", amp*scale)
        heightmap = self.add_fractal_noise(heightmap, scale=0.4, amplitude=amp*scale)

        # ── Vertical exaggeration + elevation extents ─────────────────────────
        # hscale is a pure vertical exaggeration factor (1.0 = real-world scale,
        # 2.0 = double the relief, etc.). The pipeline above works in metres
        # (scale=1.0), so this is a direct multiply.
        vert_exag = float(self.get_param("hscale", cfg.get("hscale", 1.0)))
        heightmap_m = heightmap * vert_exag

        elev_min = heightmap_m.min()
        elev_max = heightmap_m.max()
        self.info(
            "Final range with noise (meters, hscale=%.2f): min=%.2f max=%.2f",
            vert_exag, elev_min, elev_max,
        )

        # ── Encode: fill full 16-bit range, sea level at raw 32768 ───────────
        #
        # UE5 formula:  localZ_cm = (raw_u16 - 32768) / 128 * DrawScale3D.Z
        #
        # We choose counts_per_metre so that the largest elevation excursion
        # (above or below sea level) maps exactly to the edge of the 16-bit range,
        # leaving no headroom wasted and guaranteeing no clipping.
        #
        #   max_range        = max(elev_max, abs(elev_min))
        #   counts_per_metre = 32767.0 / max_range
        #   raw              = clip(elevation_m * counts_per_metre + 32768, 0, 65535)
        #
        # The matching DrawScale3D.Z that makes UE reconstruct true metres is:
        #   ue_height_scale_cm = 12800.0 * max_range / 32767.0
        #
        # (Derivation: localZ_cm = elevation_m * 100
        #              = (raw - 32768) / 128 * DrawScale3D.Z
        #              = elevation_m * counts_per_metre / 128 * DrawScale3D.Z
        #  => DrawScale3D.Z = 12800 / counts_per_metre = 12800 * max_range / 32767)

        max_range = max(elev_max, abs(elev_min))
        counts_per_metre = 32767.0 / max_range
        ue_height_scale_cm = 12800.0 * max_range / 32767.0

        self.info(
            "Encoding: max_range=%.2f m  counts_per_metre=%.4f  "
            "ue_height_scale_cm=%.4f",
            max_range, counts_per_metre, ue_height_scale_cm,
        )

        encoded = heightmap_m * counts_per_metre + 32768.0
        encoded = np.clip(encoded, 0.0, 65535.0)

        self.info("Writing image file...")
        heightmap_u16 = encoded.astype(np.uint16)

        img = Image.fromarray(heightmap_u16, mode="I;16")
        img.save(out_file)

        self.info("Heightmap saved to %s", out_file)

        # Write JSON sidecar (default on, skip with --no-sidecar)
        if not self.get_param("no_sidecar", cfg.get("no_sidecar", False)):
            self.write_sidecar(out_file, lat0, lon0, lat1, lon1, res,
                               ue_height_scale_cm,
                               elev_min_m=elev_min, elev_max_m=elev_max)
        
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

    psr.add_str("-c", "--config", dest="config")("Config file")

    psr.add_float("--lat-min")("Min lattitude")
    psr.add_float("--lat-max")("Max lattitude")
    psr.add_float("--lon-min")("Min longitude")
    psr.add_float("--lon-max")("Max longitude")
    psr.add_int("--res")("Default Output size (pixels)")
    # psr.add_str("--xres")("Output width (pixels)")
    # psr.add_str("--yres")("Output height (pixels)")
    psr.add_float("--hscale")("Scale for height")
    psr.add_float("--noise-amp")("Noise amplitude")
    psr.add_float("--undersea-height")("undersea height value")
    psr.add_str("--tiles-dir", dest="tiles_dir")("Input tiles directory")
    psr.add_str("-o","--output-dir", dest="output_dir")("Output directory")
    psr.add_flag("--ue-res", dest="ue_res")(
        "Snap --res to the nearest valid UE5 landscape size "
        "(127, 253, 505, 1009, 2017, 4033, 8129, 16257)"
    )
    psr.add_flag("--no-sidecar", dest="no_sidecar")(
        "Suppress JSON sidecar output (sidecar is written by default)"
    )

    comp.run()
