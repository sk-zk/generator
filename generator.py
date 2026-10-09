import argparse
import asyncio
import concurrent
import math
import random
import ssl
import sys
import threading
from datetime import datetime

import requests
import shapely
import urllib3
from colorama import Fore, Style
from pyproj import Transformer
from shapely.geometry import Point

sys.path.insert(0, r"lookaround")
import lookaround

tile_span = 40086474.44 / math.pow(2, 17)
tile_area = tile_span * tile_span
to_web_mercator = Transformer.from_crs(4326, 3857, always_xy=True)
thread_local = threading.local()


def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session


def download_all_tiles(coords):
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        return executor.map(download_tile, coords)


def download_tile(coords):
    session = get_session()
    tries = 0
    while tries < 5:
        try:
            tile = lookaround.get_coverage_tile(coords[0], coords[1], session=session)
            break
        except ConnectionError:
            tries += 1
        except requests.exceptions.SSLError:
            tries += 1
        except requests.exceptions.ConnectionError:
            tries += 1
        except ssl.SSLError:
            tries += 1
        except urllib3.exceptions.MaxRetryError:
            tries += 1
        except TimeoutError:
            tries += 1
    if tries >= 5:
        raise RuntimeError()
    return coords, tile


def web_mercator_to_tile_coord(x: float, y: float, tile_z: int) -> tuple[float, float]:
    extent = 20037508.342789244
    tiles_at_zoom = 2 ** tile_z
    
    norm_x = (x + extent) / (2 * extent)
    norm_y = (extent - y) / (2 * extent)
    norm_x = max(0.0, min(1.0, norm_x))
    norm_y = max(0.0, min(1.0, norm_y))
    
    tile_x = int(norm_x * tiles_at_zoom)
    tile_y = int(norm_y * tiles_at_zoom)
    tile_x = max(0, min(tiles_at_zoom - 1, tile_x))
    tile_y = max(0, min(tiles_at_zoom - 1, tile_y))
    
    return tile_x, tile_y


def generate_random_points(number: int, polygon) -> list[Point]:
    points = []
    min_x, min_y, max_x, max_y = polygon.bounds

    while len(points) < number:
        point = Point(random.uniform(min_x, max_x), random.uniform(min_y, max_y))
        if polygon.contains(point):
            points.append(point)

    return points


async def main(): 
    parser = argparse.ArgumentParser()
    parser.add_argument("date", type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
                        help="The cutoff date in year-month-day format. Tiles modified on this date or later will be shown.")
    parser.add_argument("geojson_path", type=str, nargs="?",
                        help="The GeoJSON polygon within which to fetch tiles.")
    parser.add_argument("--envelope", type=float, nargs=4, metavar=("lat1", "lon1", "lat2", "lon2"),
                        help="Alternatively: a rectangular bounding box within which to fetch tiles.")
    parser.add_argument("--no-simplify", action="store_true",
                        help="Disables polygon simplification.")
    parser.add_argument("--iters", type=int, nargs="?", default=500,
                        help="Specifies the number of iterations to run. Defaults to 500.")
    args = parser.parse_args()

    if args.envelope:
        polygon = shapely.box(args.envelope[1], args.envelope[0], args.envelope[3], args.envelope[2])
    elif args.geojson_path:
        with open(args.geojson_path, "r") as f:
            content = f.read()
            polygon = shapely.from_geojson(content)
            if not args.no_simplify:
                polygon = shapely.simplify(polygon, 0.01)
    else:
        print("No polygon specified.")
        exit(-1)

    polygon = shapely.transform(polygon, to_web_mercator.transform, interleaved=False)
    polygon_area = polygon.area

    chunk_size = 50
    seen_coords = set()
    tile_area_seen = 0

    for i in range(0, args.iters):
        print(f"{Fore.WHITE}{Style.DIM}"
              f"\r{i} ({(tile_area_seen / polygon_area):.3%})"
              f"{Fore.RESET}{Style.RESET_ALL}", end='', 
              flush=True,
              file=sys.stderr)
        points = generate_random_points(chunk_size, polygon)
        coords = {web_mercator_to_tile_coord(point.x, point.y, 17) for point in points}
        coords = coords.difference(seen_coords)
        seen_coords.update(coords)
        tile_area_seen += len(coords) * tile_area

        tiles = download_all_tiles(coords)

        newline = True
        for t in tiles:
            coords = t[0]
            tile = t[1]
            if tile.last_modified > args.date and len(tile.panos) > 0:
                if newline:
                    print()
                    newline = False
                top_left = lookaround.geo.tile_coord_to_wgs84(coords[0], coords[1], 17)
                bottom_right = lookaround.geo.tile_coord_to_wgs84(coords[0]+1, coords[1]+1, 17)
                center_lat = (top_left[0] + bottom_right[0]) / 2
                center_lon = (top_left[1] + bottom_right[1]) / 2
                print(f"({center_lat:.6f}, {center_lon:.6f}) [{coords[0]}/{coords[1]}]")
                print(tile.last_modified)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
        print()
    except KeyboardInterrupt:
        # ^ suppress printing huge traceback on ctrl+c
        print()
        exit()
