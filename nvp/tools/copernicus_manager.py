"""
Copernicus GLO-30 DEM Dataset Downloader
Downloads the global 30m resolution Digital Elevation Model from Copernicus.
"""

import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
import time

from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

class CopernicusManager(NVPComponent):
    """CopernicusManager component class"""

    def __init__(self, ctx: NVPContext):
        """class constructor"""
        NVPComponent.__init__(self, ctx)

    def process_cmd_path(self, cmd):
        """Check if this component can process the given command"""

        if cmd == "download":
            self.info("Should download copernicus data here.")
            return True
        
        return False

if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("CopernicusManager", CopernicusManager(context))

    psr = context.build_parser("download")
    # psr.add_str("-p", "--pattern", dest="pattern", default=r"\.nc$")("Input file pattern")

    comp.run()


#!/usr/bin/env python3

class GLO30Downloader:
    def __init__(self, output_dir: str = "./glo30_data", max_workers: int = 4):
        """
        Initialize the downloader.
        
        Args:
            output_dir: Directory to save downloaded files
            max_workers: Number of parallel download threads
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        self.base_url = "https://copernicus-dem-30m.s3.amazonaws.com"
        
    def generate_tile_list(self) -> List[str]:
        """
        Generate list of all GLO-30 tile names.
        Tiles are named like: Copernicus_DSM_COG_10_N00_00_E006_00_DEM
        Coverage: 90N to 90S, 180W to 180E in 1-degree tiles
        """
        tiles = []
        
        # Latitude: 90N to 90S (but actual coverage is ~85N to 90S)
        for lat in range(85, -91, -1):  # 85N to 90S
            lat_hem = 'N' if lat >= 0 else 'S'
            lat_str = f"{abs(lat):02d}_00"
            
            # Longitude: 180W to 180E
            for lon in range(-180, 180):
                lon_hem = 'E' if lon >= 0 else 'W'
                lon_str = f"{abs(lon):03d}_00"
                
                tile_name = f"Copernicus_DSM_COG_10_{lat_hem}{lat_str}_{lon_hem}{lon_str}_DEM"
                tiles.append(tile_name)
        
        return tiles
    
    def get_tile_url(self, tile_name: str) -> str:
        """Get the download URL for a specific tile."""
        # Extract coordinates from tile name
        parts = tile_name.split('_')
        lat_part = parts[4]  # e.g., N00
        lon_part = parts[5]  # e.g., E006
        
        # Construct S3 URL path
        url = f"{self.base_url}/{tile_name}/{tile_name}.tif"
        return url
    
    def download_tile(self, tile_name: str, retries: int = 3) -> Tuple[str, bool, str]:
        """
        Download a single tile.
        
        Args:
            tile_name: Name of the tile to download
            retries: Number of retry attempts
            
        Returns:
            Tuple of (tile_name, success, message)
        """
        url = self.get_tile_url(tile_name)
        output_file = self.output_dir / f"{tile_name}.tif"
        
        # Skip if already downloaded
        if output_file.exists():
            return (tile_name, True, "Already exists")
        
        for attempt in range(retries):
            try:
                response = requests.get(url, stream=True, timeout=30)
                
                # 404 means tile doesn't exist (ocean or no data area)
                if response.status_code == 404:
                    return (tile_name, False, "No data (404)")
                
                response.raise_for_status()
                
                # Download with progress
                total_size = int(response.headers.get('content-length', 0))
                
                with open(output_file, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                    else:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                
                return (tile_name, True, f"Downloaded ({total_size / 1024 / 1024:.1f} MB)")
                
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    # Clean up partial download
                    if output_file.exists():
                        output_file.unlink()
                    return (tile_name, False, f"Error: {str(e)}")
        
        return (tile_name, False, "Max retries exceeded")
    
    def download_all(self, region: str = "global"):
        """
        Download all tiles or a specific region.
        
        Args:
            region: "global" or specify lat/lon bounds (future enhancement)
        """
        print(f"Generating tile list for {region} coverage...")
        tiles = self.generate_tile_list()
        print(f"Total tiles to check: {len(tiles)}")
        print(f"Using {self.max_workers} parallel workers")
        print(f"Output directory: {self.output_dir}")
        print("\nStarting download...\n")
        
        downloaded = 0
        skipped = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_tile = {
                executor.submit(self.download_tile, tile): tile 
                for tile in tiles
            }
            
            # Process completed downloads
            for i, future in enumerate(as_completed(future_to_tile), 1):
                tile_name, success, message = future.result()
                
                if success:
                    if "Already exists" in message:
                        skipped += 1
                        status = "SKIP"
                    else:
                        downloaded += 1
                        status = "OK"
                else:
                    if "404" not in message:  # Don't count 404s as failures
                        failed += 1
                        status = "FAIL"
                    else:
                        status = "N/A"
                
                # Progress output
                if i % 100 == 0 or status in ["OK", "FAIL"]:
                    print(f"[{i}/{len(tiles)}] {status:4s} {tile_name}: {message}")
        
        print(f"\n{'='*60}")
        print(f"Download complete!")
        print(f"  Downloaded: {downloaded}")
        print(f"  Skipped (existing): {skipped}")
        print(f"  Failed: {failed}")
        print(f"  No data tiles: {len(tiles) - downloaded - skipped - failed}")
        print(f"{'='*60}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download Copernicus GLO-30 DEM dataset"
    )
    parser.add_argument(
        "--output-dir", 
        default="./glo30_data",
        help="Output directory for downloaded tiles (default: ./glo30_data)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel download workers (default: 4)"
    )
    parser.add_argument(
        "--region",
        default="global",
        help="Region to download: 'global' (default: global)"
    )
    
    args = parser.parse_args()
    
    downloader = GLO30Downloader(
        output_dir=args.output_dir,
        max_workers=args.workers
    )
    
    downloader.download_all(region=args.region)

