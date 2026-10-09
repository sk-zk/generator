A simple CLI script I use to check for updated metadata tiles in Look Around.
It downloads 25K random tiles within a GeoJSON polygon and prints their coordinates if the tile's modification date is newer than the date specified.

## Install
```sh
git clone https://github.com/sk-zk/generator.git --recursive
cd generator
[set up your environment as desired]
pip install -r requirements.txt
```

### Sample output
```sh
$ ./generator.py 2026-10-08 germany.geojson
12 (0.006%)
(50.001560, 10.916290) [69510/44451]
2026-10-09 20:55:34
61 (0.029%)
(49.638288, 8.768463) [68728/44656]
2026-10-09 21:02:46
63 (0.030%)
(49.960939, 7.397919) [68229/44474]
2026-10-09 20:59:14
91 (0.044%)
^C
```

The script reports the number of iterations (chunks of 50 tiles) and covered area in percent while it is running.
When a modified tile is found, it prints the lat/lon coordinates at the tile's center, the x/y coordinates
of the tile (z is always 17), and the modification date in local time.

### Options
Use `--envelope` to pass a bounding box instead of a GeoJSON file.

By default, polygons are simplified to improve performance. Pass `--no-simplify` to disable this.
