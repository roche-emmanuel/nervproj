"""
Copernicus / ESA land-data pipeline manager.

Covers three offline data products used by the ArgusWorldBuilder vegetation pipeline:

  1. GLO-30 DEM  (elevation)
     Source : s3://copernicus-dem-30m  (1° tiles, GeoTIFF, no sign-in)
     Command: gen_heightmap

  2. ESA WorldCover 10 m  (land cover classes)
     Source : s3://esa-worldcover/v200/2021/map  (3°×3° tiles, GeoTIFF, no sign-in)
     Command: gen_landcover
     Output : landcover.png  (uint8, 11-class values) + landcover.json sidecar
     Classes: 10=Trees 20=Shrubland 30=Grassland 40=Cropland 50=BuiltUp
              60=Bare 70=Snow 80=Water 90=HerbaceousWetland 95=Mangroves 100=Moss

  3. CGLS HRL Tree Cover Density 10 m  (canopy closure %)
     Source : https://land.copernicus.eu  (100×100 km tiles, manual download)
              s3://copernicus-land-hrl-forest (unofficial mirror, where available)
     Command: gen_tree_density
     Output : tree_density.png  (uint8, 0-100 % canopy) + tree_density.json sidecar
     Fallback: when tiles are absent a flat uint8 raster is synthesised from the
               config key  vegetation.default_tree_density  (default 50).

     Leaf-type classification is NOT downloaded as a separate raster: the default
     leaf type for the world is set via  vegetation.default_leaf_type  in the world
     YAML config (values: "broadleaf" | "coniferous" | "mixed", default "broadleaf").
     VegetationPlacer reads this single config value to pick the tree species palette.

Usage examples (heightmap — unchanged):
  nvp gen_heightmap --lat-min=-21.39 --lat-max=-20.87 --lon-min=55.21 --lon-max=55.84 --res=8129 -o output/reunion_4k

Usage examples (land cover):
  nvp gen_landcover -c output/reunion_4k/world.yml
  nvp gen_landcover --lat-min=-21.39 --lat-max=-20.87 --lon-min=55.21 --lon-max=55.84 --res=4033 -o output/reunion_4k

Usage examples (tree density):
  nvp gen_tree_density -c output/reunion_4k/world.yml
  nvp gen_tree_density --lat-min=-21.39 --lat-max=-20.87 --lon-min=55.21 --lon-max=55.84 --res=4033 -o output/reunion_4k
  # If HRL tiles are absent the fallback flat raster is written automatically.
"""

# Example command to download DEM tiles:
# nvp download --lat=-22,-20 --lon=55,56

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

from scipy.ndimage import gaussian_filter, distance_transform_edt

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

        if cmd == "gen_landcover":
            self.generate_landcover()
            return True

        if cmd == "gen_tree_density":
            self.generate_tree_density()
            return True

        return False

    def generate_tile_list(self, lat_range, lon_range):
        """
        Generate list of all GLO-30 tile names.
        Tiles are named like: Copernicus_DSM_COG_10_N00_00_E006_00_DEM
        Coverage: 90 N to 90 S, 180 W to 180 E in 1-degree tiles
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
            # self.info("File %s already exists.", output_file)
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

    def apply_underwater_blend(self, heightmap, undersea_height, cfg=None):
        """
        Smoothly lift below-sea-level areas toward sea level near the coastline
        using an exact Euclidean distance-to-shore map.

        Strategy:
          1. Build a shore mask: True where elevation > 0 (land), False in ocean.
          2. Run distance_transform_edt on the *ocean* pixels to get, for every
             underwater pixel, the exact Euclidean distance (in pixels) to the
             nearest land pixel.  Land pixels get distance 0 by definition.
          3. Normalise by transition_radius and clamp to [0, 1] to get a
             normalised distance  t  in [0, 1]:
               t = 0  → right at the shoreline  → lift to sea level (0 m)
               t = 1  → at or beyond the radius  → keep at undersea_height
          4. Apply blend_power for curve shaping, then lerp:
               elevation = lerp(0, undersea_height, t^blend_power)
          5. Above-sea-level pixels are never touched.

        Parameters (CLI arg > config file key > hardcoded default):
          underwater_transition_radius – distance in pixels beyond which the
                                         floor stays at undersea_height (default 150).
          underwater_blend_power       – exponent on the normalised distance;
                                         > 1 keeps the floor flat far from shore
                                         and concentrates the ramp at the coast;
                                         < 1 makes a gentler, wider ramp (default 2.0).

        Args:
            heightmap:       2-D float32 array of elevations (metres).
            undersea_height: Floor elevation for deep-ocean pixels (e.g. −200 m).
            cfg:             Optional config dict for parameter defaults.
        Returns:
            Modified heightmap; above-sea pixels are identical to the input.
        """
        if cfg is None:
            cfg = {}

        transition_radius = float(self.get_param(
            "underwater_transition_radius",
            cfg.get("underwater_transition_radius", 150.0),
        ))
        blend_power = float(self.get_param(
            "underwater_blend_power",
            cfg.get("underwater_blend_power", 2.0),
        ))

        self.info(
            "Applying underwater distance-lift: transition_radius=%.1f px, "
            "blend_power=%.2f, undersea_height=%.1f m",
            transition_radius, blend_power, undersea_height,
        )

        # --- 1. Shore mask: True = land (elev > 0), False = ocean -------------
        land_mask = heightmap > 0.0

        # --- 2. Exact Euclidean distance to nearest land pixel ----------------
        # distance_transform_edt measures distance from every *False* pixel to
        # the nearest *True* pixel.  Land pixels report 0.
        # input must be bool: True = foreground (land), False = background (ocean)
        dist_to_shore = distance_transform_edt(~land_mask).astype(np.float32)

        self.info(
            "Distance-to-shore map: max=%.1f px  (transition_radius=%.1f px)",
            dist_to_shore.max(), transition_radius,
        )

        # --- 3. Normalised distance clamped to [0, 1] -------------------------
        # t = 0 at the shoreline, t = 1 at or beyond transition_radius
        t = np.clip(dist_to_shore / transition_radius, 0.0, 1.0)

        # --- 4. Curve shaping + lerp to target elevation ----------------------
        # t^p with p > 1: most of the ramp happens close to shore; floor stays
        # flat near undersea_height beyond the transition zone.
        t_curved = np.power(t, blend_power)

        # lerp: elevation at the shore (t=0) = 0 m, at full depth (t=1) = undersea_height
        lifted = undersea_height * t_curved  # = 0*(1-t_curved) + undersea_height*t_curved

        # --- 5. Apply only to ocean pixels; land is untouched -----------------
        result = np.where(land_mask, heightmap, lifted)

        self.info(
            "Underwater lift complete. Range: min=%.2f max=%.2f",
            result.min(), result.max(),
        )

        return result
    
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

    # ------------------------------------------------------------------
    # WorldCover land-cover helpers
    # ------------------------------------------------------------------

    # ESA WorldCover 2021 v200 — public S3, no sign-in required.
    # Tiles are 3°×3° named by their SW corner, e.g.:
    #   s3://esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_S24E054_Map.tif
    WORLDCOVER_S3_BASE = "s3://esa-worldcover/v200/2021/map"

    # WorldCover class values (uint8) — stored in sidecar for VegetationPlacer.
    WORLDCOVER_CLASSES = {
        10:  "Trees",
        20:  "Shrubland",
        30:  "Grassland",
        40:  "Cropland",
        50:  "BuiltUp",
        60:  "Bare",
        70:  "Snow",
        80:  "Water",
        90:  "HerbaceousWetland",
        95:  "Mangroves",
        100: "Moss",
    }

    def _worldcover_tile_name(self, lat, lon):
        """
        Return the WorldCover tile filename for the 3°×3° cell whose SW corner
        is at (lat, lon).  Both must already be snapped to multiples of 3.
        Example: lat=-24 lon=54 → "ESA_WorldCover_10m_2021_v200_S24E054_Map.tif"
        """
        lat_hem = "N" if lat >= 0 else "S"
        lon_hem = "E" if lon >= 0 else "W"
        return (
            f"ESA_WorldCover_10m_2021_v200_"
            f"{lat_hem}{abs(lat):02d}{lon_hem}{abs(lon):03d}_Map.tif"
        )

    def _worldcover_tiles_for_bbox(self, lat0, lon0, lat1, lon1):
        """
        Return all WorldCover tile names whose 3°×3° cells intersect the bbox.
        SW corners are aligned to multiples of 3 degrees.
        """
        # snap SW corner of first tile downward to nearest multiple of 3
        lat_start = int(math.floor(lat0 / 3.0)) * 3
        lon_start = int(math.floor(lon0 / 3.0)) * 3

        tiles = []
        lat = lat_start
        while lat < lat1:
            lon = lon_start
            while lon < lon1:
                tiles.append(self._worldcover_tile_name(lat, lon))
                lon += 3
            lat += 3
        return tiles

    def _download_worldcover_tile(self, tile_name, tiles_dir):
        """Download a single WorldCover tile from the public S3 bucket."""
        out_path = self.get_path(tiles_dir, tile_name)
        if self.file_exists(out_path):
            self.info("WorldCover tile already cached: %s", tile_name)
            return out_path

        url = f"{self.WORLDCOVER_S3_BASE}/{tile_name}"
        self.info("Downloading WorldCover tile %s ...", tile_name)
        self.execute_nvp("aws", "s3", "cp", "--no-sign-request", url, out_path)
        return out_path

    def _reproject_uint8_tile(self, src_path, target_array, transform, nodata_val=0):
        """
        Reproject a uint8 GeoTIFF into target_array (uint8, same shape as the
        output raster) using nearest-neighbour resampling — preserves class values.
        Pixels that fall outside the source tile remain unchanged (0 = nodata).
        """
        with rasterio.open(src_path) as src:
            temp = np.zeros(target_array.shape, dtype=np.uint8)
            reproject(
                source=rasterio.band(src, 1),
                destination=temp,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs="EPSG:4326",
                resampling=Resampling.nearest,
                src_nodata=src.nodata if src.nodata is not None else nodata_val,
                dst_nodata=nodata_val,
            )
            # Composite: only overwrite pixels that the tile actually covers.
            valid_mask = temp != nodata_val
            target_array[valid_mask] = temp[valid_mask]

    def _resolve_bbox_and_res(self, cfg):
        """
        Shared helper: extract lat/lon bbox and output resolution from CLI params
        or from a world config dict.  Returns (lat0, lon0, lat1, lon1, res, out_dir).
        lat0/lon0 = SW corner (min), lat1/lon1 = NE corner (max).

        Applies the same bbox squaring as generate_heightmap: the longer axis
        determines the side length and both axes are expanded symmetrically around
        the centre, so the output canvas covers exactly the same geographic square
        that the heightmap covers.
        """
        lat0 = float(self.get_param("lat_min", cfg.get("min_lat", cfg.get("bounding_box", {}).get("min_lat"))))
        lon0 = float(self.get_param("lon_min", cfg.get("min_lon", cfg.get("bounding_box", {}).get("min_lon"))))
        lat1 = float(self.get_param("lat_max", cfg.get("max_lat", cfg.get("bounding_box", {}).get("max_lat"))))
        lon1 = float(self.get_param("lon_max", cfg.get("max_lon", cfg.get("bounding_box", {}).get("max_lon"))))

        self.check(
            None not in (lat0, lon0, lat1, lon1),
            "Bounding box required: provide --lat-min/max/lon-min/max or a world config YAML.",
        )

        # Square the bbox exactly as generate_heightmap does: take the larger of
        # the two degree-extents and expand both axes symmetrically around the
        # centre.  This guarantees landcover/tree_density pixels align 1-to-1
        # with heightmap pixels when both are generated at the same --res.
        xsize = abs(lon1 - lon0)
        ysize = abs(lat1 - lat0)
        size  = max(xsize, ysize)
        clat  = (lat0 + lat1) * 0.5
        clon  = (lon0 + lon1) * 0.5
        lat0  = clat - size * 0.5
        lat1  = clat + size * 0.5
        lon0  = clon - size * 0.5
        lon1  = clon + size * 0.5

        self.info(
            "Squared bbox: lat[%.6f, %.6f] lon[%.6f, %.6f] (%.4f deg / ~%.1f km)",
            lat0, lat1, lon0, lon1, size, size * 111.320,
        )

        # default resolution matches the heightmap res if set in config, else 4033
        res = int(self.get_param("res", cfg.get("res", cfg.get("vegetation", {}).get("map_res", 4033))))

        out_dir = self.get_param("output_dir", cfg.get("data_dir"))
        if out_dir is None:
            cfgfile = self.get_param("config")
            if cfgfile:
                out_dir = os.path.dirname(os.path.abspath(cfgfile))
            else:
                out_dir = self.get_cwd()

        return lat0, lon0, lat1, lon1, res, out_dir

    def _write_veg_sidecar(self, out_file, lat0, lon0, lat1, lon1, res, extra):
        """
        Write a JSON sidecar for a vegetation map PNG (landcover or tree_density).
        'extra' is a dict of additional keys merged into the sidecar.
        """
        size_m = self.compute_size_m(lat0, lon0, lat1, lon1)
        ue_scale = self.compute_ue_scale(size_m, res)

        sidecar = {
            "origin_lat": round(min(lat0, lat1), 6),
            "origin_lon": round(min(lon0, lon1), 6),
            "size_m":     round(size_m, 3),
            "ue_scale":   round(ue_scale, 4),
            "res_x":      res,
            "res_y":      res,
        }
        sidecar.update(extra)

        stem, _ = os.path.splitext(out_file)
        sidecar_path = stem + ".json"
        self.write_json(sidecar, sidecar_path)
        self.info("Sidecar written to %s", sidecar_path)
        return sidecar_path

    def generate_landcover(self):
        """
        Download ESA WorldCover 10m tiles for the world bbox, mosaic them, and
        export a uint8 PNG (landcover.png) whose pixel values are WorldCover class
        codes (10, 20, 30, … 100).  A JSON sidecar lists the class legend.

        CLI / config keys consumed:
          --lat-min/max  --lon-min/max   bbox (or read from world YAML)
          --res                          output pixel resolution (default 4033)
          -o / --output-dir              destination folder
          -c / --config                  world YAML (overridden by explicit CLI args)
          --tiles-dir                    cache dir for raw WorldCover GeoTIFFs
          --no-sidecar                   suppress JSON sidecar
        """
        cfgfile = self.get_param("config")
        cfg = self.read_yaml(cfgfile) if cfgfile else {}

        lat0, lon0, lat1, lon1, res, out_dir = self._resolve_bbox_and_res(cfg)
        self.make_folder(out_dir)

        tiles_dir = self.get_param(
            "tiles_dir",
            cfg.get("worldcover_tiles_dir", self.get_path(self._default_tiles_dir, "worldcover")),
        )
        self.make_folder(tiles_dir)

        self.info(
            "Generating land-cover map: BBOX lat[%.5f,%.5f] lon[%.5f,%.5f]  res=%d",
            lat0, lat1, lon0, lon1, res,
        )

        # Build output raster (uint8, 0 = nodata / outside any tile)
        transform = from_bounds(lon0, lat0, lon1, lat1, res, res)
        canvas = np.zeros((res, res), dtype=np.uint8)

        tile_names = self._worldcover_tiles_for_bbox(lat0, lon0, lat1, lon1)
        self.info("WorldCover tiles needed: %d", len(tile_names))

        for tile_name in tile_names:
            tile_path = self._download_worldcover_tile(tile_name, tiles_dir)
            if not self.file_exists(tile_path):
                self.warn("WorldCover tile not available, skipping: %s", tile_name)
                continue
            self.info("Mosaicking %s", tile_name)
            self._reproject_uint8_tile(tile_path, canvas, transform, nodata_val=0)

        # Save as single-channel uint8 PNG.
        # PIL mode "L" = 8-bit greyscale, which stores uint8 class codes losslessly.
        img = Image.fromarray(canvas, mode="L")
        out_file = self.get_path(out_dir, "landcover.png")
        img.save(out_file)
        self.info("Land-cover map saved to %s", out_file)

        hcfg = cfg.get("heighmap", {})
        if not self.get_param("no_sidecar", hcfg.get("no_sidecar", False)):
            self._write_veg_sidecar(out_file, lat0, lon0, lat1, lon1, res, {
                "source":  "ESA_WorldCover_10m_2021_v200",
                "classes": self.WORLDCOVER_CLASSES,
            })

    # ------------------------------------------------------------------
    # CGLS Tree Cover Density helpers
    # ------------------------------------------------------------------

    # CGLS HRL TCD tiles follow the EEA 100×100 km reference grid (ETRS89-LAEA).
    # They are *not* on a simple lat/lon grid and must be downloaded manually
    # from https://land.copernicus.eu or via the Copernicus Data Space API.
    # We look for pre-downloaded GeoTIFFs in the configured tiles directory and
    # fall back to a flat synthetic raster when tiles are missing.

    def _tcd_tiles_for_bbox(self, tiles_dir):
        """
        Return all .tif files found in tiles_dir that look like TCD tiles.
        We accept any .tif in the directory; the caller filters by spatial overlap
        during reprojection (pixels outside the source bbox remain 0).
        """
        if not self.file_exists(tiles_dir):
            return []
        tifs = [
            self.get_path(tiles_dir, f)
            for f in os.listdir(tiles_dir)
            if f.lower().endswith(".tif")
        ]
        return tifs

    def generate_tree_density(self):
        """
        Produce a uint8 PNG (tree_density.png, values 0-100) representing canopy
        closure percentage per pixel.

        Data source priority:
          1. CGLS HRL Tree Cover Density GeoTIFF tiles pre-downloaded into
             cfg["tcd_tiles_dir"] (or --tiles-dir).  Any .tif files found there
             are mosaicked with nearest-neighbour resampling.
          2. If no tiles are found: synthesise a flat raster whose value equals
             cfg["vegetation"]["default_tree_density"] (default 50).

        CLI / config keys consumed (same as gen_landcover plus):
          vegetation:
            default_tree_density: 50    # 0-100 %, used when no TCD tiles available
            default_leaf_type:    "broadleaf"   # broadleaf | coniferous | mixed
        """
        cfgfile = self.get_param("config")
        cfg = self.read_yaml(cfgfile) if cfgfile else {}

        lat0, lon0, lat1, lon1, res, out_dir = self._resolve_bbox_and_res(cfg)
        self.make_folder(out_dir)

        veg_cfg = cfg.get("vegetation", {})
        default_density = int(veg_cfg.get("default_tree_density", 50))
        default_leaf_type = veg_cfg.get("default_leaf_type", "broadleaf")

        tiles_dir = self.get_param(
            "tiles_dir",
            cfg.get("tcd_tiles_dir", self.get_path(self._default_tiles_dir, "tcd")),
        )

        self.info(
            "Generating tree-density map: BBOX lat[%.5f,%.5f] lon[%.5f,%.5f]  res=%d",
            lat0, lat1, lon0, lon1, res,
        )

        transform = from_bounds(lon0, lat0, lon1, lat1, res, res)
        canvas = np.zeros((res, res), dtype=np.uint8)

        tif_files = self._tcd_tiles_for_bbox(tiles_dir)
        used_real_data = False

        if tif_files:
            self.info("Found %d TCD tile(s) in %s", len(tif_files), tiles_dir)
            for tif_path in tif_files:
                self.info("Mosaicking TCD tile: %s", os.path.basename(tif_path))
                try:
                    self._reproject_uint8_tile(tif_path, canvas, transform, nodata_val=0)
                    used_real_data = True
                except Exception as exc:
                    self.warn("Failed to read TCD tile %s: %s", tif_path, exc)
        else:
            self.info(
                "No TCD tiles found in %s — using default density %d%%",
                tiles_dir, default_density,
            )

        if not used_real_data:
            # Flat fallback: fill entire canvas with the configured default density.
            canvas[:] = np.clip(default_density, 0, 100)
            self.info("Fallback tree-density raster: %d%% uniform", default_density)

        out_file = self.get_path(out_dir, "tree_density.png")
        img = Image.fromarray(canvas, mode="L")
        img.save(out_file)
        self.info("Tree-density map saved to %s", out_file)

        hcfg = cfg.get("heighmap", {})
        if not self.get_param("no_sidecar", hcfg.get("no_sidecar", False)):
            self._write_veg_sidecar(out_file, lat0, lon0, lat1, lon1, res, {
                "source":            "CGLS_HRL_TCD_10m" if used_real_data else "synthetic_fallback",
                "value_range":       "0-100 (canopy closure %)",
                "default_density":   default_density,
                "default_leaf_type": default_leaf_type,
                "used_real_data":    used_real_data,
            })

    # ------------------------------------------------------------------

    def generate_heightmap(self):

        cfgfile = self.get_param("config")
        cfg = {}
        if cfgfile is not None:
            cfg = self.read_yaml(cfgfile)

        bb = cfg.get("bounding_box", {})
        lat0 = self.get_param("lat_min", bb.get("min_lat"))
        lon0 = self.get_param("lon_min", bb.get("min_lon"))
        lat1 = self.get_param("lat_max", bb.get("max_lat"))
        lon1 = self.get_param("lon_max", bb.get("max_lon"))

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

        hcfg = cfg.get("heightmap", {})
        res = self.get_param("res", hcfg.get("resolution"))
        # scale is the internal pipeline unit factor (metres → pipeline units).
        # We keep the pipeline in raw metres (scale=1.0); vertical exaggeration
        # (hscale) is applied only at the final encoding step, not here.
        scale = 1.0

        # --ue-res: snap to nearest valid UE5 landscape resolution
        if self.get_param("ue_res", hcfg.get("snap_ue_res")):
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

        undersea_height = self.get_param("undersea_height", hcfg.get("undersea_height", -200)) * scale
        self.info("Using undersea height value: %f", undersea_height)

        # --world-id: write output into <cwd>/output/<world_id>/heightmap.png
        out_dir = self.get_param("output_dir", cfg.get("data_dir"))
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
            self.download_tile(tile, tiles_dir)

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
        amp = self.get_param("noise_amp", hcfg.get("noise_amp", 50.0))

        # Note: we move up by the noise amplitude here because we can still add this noise down afterwards:
        heightmap = self.apply_underwater_blend(heightmap, undersea_height + amp*scale, cfg=hcfg)
        # heightmap[heightmap<=0.0] = undersea_height + amp*scale
        # heightmap[heightmap<=0.0] = undersea_height
        
        self.info("Adding fractal noise with amplitude=%f...", amp*scale)
        heightmap = self.add_fractal_noise(heightmap, scale=0.4, amplitude=amp*scale)

        # ── Vertical exaggeration + elevation extents ─────────────────────────
        # hscale is a pure vertical exaggeration factor (1.0 = real-world scale,
        # 2.0 = double the relief, etc.). The pipeline above works in metres
        # (scale=1.0), so this is a direct multiply.
        vert_exag = float(self.get_param("hscale", hcfg.get("hscale", 1.0)))
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
        if not self.get_param("no_sidecar", hcfg.get("no_sidecar", False)):
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

    # ── gen_landcover ──────────────────────────────────────────────────────────
    psr = context.build_parser("gen_landcover")
    psr.add_str("-c", "--config", dest="config")(
        "World config YAML (same file used by the UE commandlet)"
    )
    psr.add_float("--lat-min")("Min latitude  (south edge)")
    psr.add_float("--lat-max")("Max latitude  (north edge)")
    psr.add_float("--lon-min")("Min longitude (west edge)")
    psr.add_float("--lon-max")("Max longitude (east edge)")
    psr.add_int("--res")(
        "Output resolution in pixels (default: vegetation.map_res from config, or 4033)"
    )
    psr.add_str("--tiles-dir", dest="tiles_dir")(
        "Directory to cache downloaded WorldCover GeoTIFF tiles"
    )
    psr.add_str("-o", "--output-dir", dest="output_dir")("Output directory")
    psr.add_flag("--no-sidecar", dest="no_sidecar")(
        "Suppress JSON sidecar output"
    )

    # ── gen_tree_density ───────────────────────────────────────────────────────
    psr = context.build_parser("gen_tree_density")
    psr.add_str("-c", "--config", dest="config")(
        "World config YAML (same file used by the UE commandlet)"
    )
    psr.add_float("--lat-min")("Min latitude  (south edge)")
    psr.add_float("--lat-max")("Max latitude  (north edge)")
    psr.add_float("--lon-min")("Min longitude (west edge)")
    psr.add_float("--lon-max")("Max longitude (east edge)")
    psr.add_int("--res")(
        "Output resolution in pixels (default: vegetation.map_res from config, or 4033)"
    )
    psr.add_str("--tiles-dir", dest="tiles_dir")(
        "Directory to cache pre-downloaded CGLS TCD GeoTIFF tiles "
        "(if absent a synthetic fallback raster is generated)"
    )
    psr.add_str("-o", "--output-dir", dest="output_dir")("Output directory")
    psr.add_flag("--no-sidecar", dest="no_sidecar")(
        "Suppress JSON sidecar output"
    )

    comp.run()
