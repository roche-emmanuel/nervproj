"""
Copernicus GLO-30 DEM Dataset Downloader
Downloads the global 30m resolution Digital Elevation Model from Copernicus.
"""
# Example command to download with aws:
# nvp aws s3 cp --no-sign-request s3://copernicus-dem-30m/Copernicus_DSM_COG_10_S90_00_W176_00_DEM/Copernicus_DSM_COG_10_S90_00_W176_00_DEM.tif .

# Example command to download tiles:
# nvp copernicus --lat=-22,-20 --lon=55,56

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

if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("CopernicusManager", CopernicusManager(context))

    psr = context.build_parser("download")
    psr.add_str("--lat", dest="lat_range", default="-85,90")("Latitude range")
    psr.add_str("--lon", dest="lon_range", default="-180,180")("Longitude range")
    psr.add_str("-o","--output-dir", dest="output_dir")("Output directory")
    # psr.add_str("-p", "--pattern", dest="pattern", default=r"\.nc$")("Input file pattern")

    comp.run()
