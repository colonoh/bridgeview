# Research: Building Landmark Visibility

Phase 0 output for [plan.md](plan.md). Each section records a decision, why it was chosen, and
what else was considered. All facts below were checked on 2026-11-21 unless noted.

## R1. Building footprint and height data

**Decision**: Use the DataSF **Building Footprints** dataset (Socrata ID `ynuv-fyni`, 177,023
footprints). Take a one-time GeoJSON export, then publish that exact file as a GitHub Release
asset on this repository. The download command fetches it from the release and checks its
SHA-256.

**Facts**:
- Source: <https://data.sfgov.org/Geographic-Locations-and-Boundaries/Building-Footprints/ynuv-fyni>
- License: Open Data Commons Public Domain Dedication and License (PDDL 1.0). Redistribution is
  permitted, so mirroring the file as a release asset is allowed.
- Footprints come from a 2010 Pictometry 3D model, split along likely firewalls (2017). The
  height fields are zonal statistics from LiDAR over each footprint. The dataset's
  `data_as_of` date is 2023-09-11.
- The identifier `sf16_bldgid`, for example `201006.0000001`, is unique per footprint.
- Fields used, all present for all 177,023 rows:
  - `median_1st_m`: median first-return surface elevation over the footprint, in metres,
    NAVD88. This is a typical roof elevation.
  - `peak_1st_m`: highest first-return surface elevation over the footprint, in metres,
    NAVD88.
  - `gnd_min_m`: lowest bare-ground elevation over the footprint, in metres, NAVD88. It is
    kept for reporting only.
  - `hgt_mincm`: the minimum height above ground over the footprint, in centimetres.

**Why mirror it**: the portal reloads the dataset daily (`data_loaded_at` changes every day),
so a live export's checksum would change daily even when the content doesn't. A release asset
is fixed, so it can be pinned and verified (FR-009, FR-010).

**Observer height: decided by the owner on 2026-11-22.** The observer uses
**`median_1st_m`**, and obstructions use **`peak_1st_m`**. The dataset has no clean "lowest roof"
field. Here are the options compared on a random sample of 5,000 buildings, as height above
ground:

| Option | 10th pct | Median | 90th pct | Buildings ≤ 1.5 m |
|---|---|---|---|---|
| `hgt_mincm` (minimum) | 1.4 | 3.4 | 6.2 | 594 |
| median − 1 std. dev. | 4.6 | 6.2 | 10.0 | 22 |
| `hgt_majoritycm` | 5.5 | 7.3 | 11.6 | 11 |
| `hgt_meancm` | 5.4 | 7.2 | 11.1 | 3 |
| **median (chosen)** | 5.5 | 7.4 | 11.4 | 4 |
| `hgt_maxcm` (maximum, the same surface as `peak_1st_m`) | 6.5 | 9.4 | 13.7 | 1 |
| `p2010_zmaxn88ft` (3D model; missing for 32,060 buildings) | 6.8 | 10.7 | 15.9 | 81 |

The minimum includes edge cells at street level, so it isn't a roof. The median is steady and
isn't moved by spikes.

**Known limitation**: all heights come from the 2010 LiDAR. Buildings completed after 2010
probably carry the height of their 2010 site. Rebuilding heights from the 2023 USGS LiDAR
point cloud is a candidate later feature (spec Assumptions).

**Alternatives considered**:
- Pinning a live Socrata export by checksum: rejected, because the checksum changes daily.
- OpenStreetMap buildings: rejected, because height coverage is sparse and uneven.
- Microsoft or Overture building footprints: rejected, because the height estimates are
  coarser than the LiDAR statistics.

## R2. Bare-ground elevation model

**Decision**: Use the **USGS 3DEP 1-metre DEM, project CA_SanFrancisco_B23**: four 10 km
tiles, about 523 MB in total, downloaded from their stable USGS URLs and pinned by SHA-256.

| Tile | Bytes |
|------|-------|
| `USGS_1M_10_x54y418_CA_SanFrancisco_B23.tif` | 176,580,019 |
| `USGS_1M_10_x54y419_CA_SanFrancisco_B23.tif` | 111,944,984 |
| `USGS_1M_10_x55y418_CA_SanFrancisco_B23.tif` | 147,948,547 |
| `USGS_1M_10_x55y419_CA_SanFrancisco_B23.tif` | 86,461,076 |

Base URL: `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/CA_SanFrancisco_B23/TIFF/`

**Facts**: bare earth, with buildings and vegetation removed, as the clarification requires.
Horizontal CRS is NAD83 / UTM zone 10N (EPSG:26910), and vertical is NAVD88 in metres. The
tiles together cover longitude −122.546 to −122.318 and latitude 37.675 to 37.856. That covers
all of San Francisco, including Alcatraz, Treasure Island and Yerba Buena Island.
Published 2024-08-26. USGS 3DEP data is in the public domain.

**To verify during implementation**: that the tiles hold data, not nodata, over Alcatraz and
Treasure Island. Buildings whose viewpoint falls on nodata are "not evaluated" (FR-015).

**Alternatives considered**:
- 3DEP 1/3 arc-second, about 10 m: rejected, because it is too coarse for street-scale
  ridges.
- The ground grid from the 2010 city LiDAR behind the footprint statistics: rejected, because
  it is not published as a downloadable raster.
- A digital surface model that includes buildings: rejected by clarification Q3.

## R3. Coordinate reference systems and vertical datum

**Decision**: Do all computation in **EPSG:26910 (NAD83 / UTM zone 10N, metres)**, with all
heights in **NAVD88 metres**. Write viewpoint locations out in WGS84 longitude and latitude
(EPSG:4326) for the web page.

**Rationale**: EPSG:26910 is the elevation model's native CRS, so the ~780 MB raster never has
to be resampled. Its scale error over San Francisco is about 0.04%, which is about 4 m over
10 km horizontally and changes sight-line slopes by a negligible amount. The building data
already gives heights in NAVD88.

**Alternatives considered**: EPSG:7131 (NAD83(2011) / San Francisco CS13, metres) has lower
distortion, but it would mean resampling the elevation raster, at a cost in time and accuracy.

**Tidal datums at NOAA station 9414290, San Francisco, epoch 1983–2001**, relative to NAVD88:
MLLW +0.02 m, MHW +1.61 m, MHHW +1.80 m. These convert published "height above water"
figures to NAVD88 (R5).

## R4. Earth curvature and refraction

**Decision**: Lower each point's effective height by `(1 − k) · d² / (2R)`, where `d` is the
horizontal distance from the observer, R = 6,371,000 m and k = 0.13, the standard refraction
coefficient. The sight line is then a straight line, in distance, between the observer and
the target's lowered height.

**Rationale**: At 10 km the drop is about 6.8 m, which is enough to change answers near the
limit. The correction is the standard one used in surveying and is easy to work out by hand
in fixtures.

## R5. Landmark reference points

**Decision**: Store the reference points in `src/bridgeview/landmarks.toml`, with a
`version` field. Positions are from OpenStreetMap, as tower centroids (ODbL, so the file
credits it). Heights are from official figures where available, converted to NAVD88 with R3.

| Landmark | Point id | Lat, lon (WGS84) | Height, NAVD88 m | Basis |
|---|---|---|---|---|
| Golden Gate Bridge | `ggb_south_tower` | 37.81401, −122.47789 | 227.4 | 746 ft above MLLW (goldengate.org) |
| | `ggb_north_tower` | 37.82550, −122.47923 | 227.4 | same |
| | `ggb_midspan` | 37.81976, −122.47856 | 68.9 | 220 ft clearance above MHHW (goldengate.org) |
| Alcatraz Island | `alc_lighthouse` | 37.82625, −122.42230 | 66.8 | focal plane 214 ft above MHW (USLHS) |
| | `alc_north`, `alc_south`, `alc_east`, `alc_west` | island extremities, chosen during implementation | ground + 2 m, taken from the R2 elevation model | a person standing on the shore |
| Bay Bridge | `bb_w1` … `bb_w4` | 37.79075, −122.38582 / 37.79559, −122.38065 / 37.80079, −122.37508 / 37.80562, −122.36990 | 160.3 | 526 ft (see note) |
| | `bb_sas_tower` | 37.81527, −122.35851 | 160.0 | 525 ft (Caltrans/MTC fact sheet) |

**Notes**:
- The west span tower height is reported as 526 ft (Wikipedia; OSM `height=160`) or 519 ft
  (one other source). The plan uses 526 ft. The 2 m difference is small next to other
  uncertainties, and the source is recorded in the file.
- The datum behind the 525 ft SAS tower figure isn't stated, so the plan assumes MLLW.
- The plan uses the midspan clearance, which is the underside of the deck, for
  `ggb_midspan`. That is slightly cautious.

## R6. Visibility algorithm and performance

**Decision**: Compute each sight line exactly against building footprints, and sample the
elevation model along the line for the ground.

1. **Buildings**: for each observer, build the sight lines to all reference points (13
   per building, so about 2.3M lines in total). Find the footprints each line crosses with a
   spatial index (shapely `STRtree.query`, vectorised and run in C). For each crossed
   footprint, take the stretch of line inside it. The obstruction minus the sight line,
   `z_top − c·d² − (z_obs + s·d)`, is a downward-curving function of the distance `d`, so its
   maximum over the stretch can be found exactly at an end or at its peak. A building blocks
   when that maximum exceeds **+1 mm**, which leaves grazing lines unblocked (FR-006).
   The observer's own footprint is excluded (FR-005). So are footprints that contain the
   target point, so a landmark's own structure doesn't block it.
2. **Ground**: sample the elevation model every 1 m along the line, with bilinear
   interpolation, skipping the first and last 2 m. The ground blocks when a sample exceeds the
   corrected sight line by more than 1 mm.
3. **First blocker**: the blocker nearest to the observer (FR-014).
4. **Scale**: work in batches of observers across all CPU cores using `multiprocessing`. The
   elevation model is cropped to San Francisco and cached as a memory-mapped array, so worker
   processes share it without copying. Estimated load: about 300 footprint crossings per line,
   about 8×10⁸ building checks, and about 10¹⁰ ground samples. That fits in the 1-hour target
   (SC-004) on 8 cores. A benchmark task confirms this early.

**Alternatives considered**:
- Rasterise the buildings and march along each line through one combined height grid:
  simpler and faster, but not exact, so grazing and box fixtures would depend on the grid
  size. It is kept as a fallback pre-filter if the benchmark misses the target.
- GPU or compiled extensions: rejected for now under the simplicity principle.

## R7. Output format

**Decision**: Produce a single **CSV** file, UTF-8 with `\n` line endings, sorted by
`building_id`. Number formatting is fixed: 7 decimal places for longitude and latitude, and 2
for metres. The run metadata goes in columns on every row. The full column contract is in
[contracts/results-csv.md](contracts/results-csv.md).

**Rationale**: CSV opens in a spreadsheet or text editor (FR-017), and a web page can load it
directly. Repeating the three metadata columns on every row satisfies FR-016 with one file.
It costs little, since the strings are short and repeated values compress well. Fixed sorting
and formatting give byte-identical reruns (FR-018).

**Alternatives considered**:
- GeoJSON: it can't be opened in a spreadsheet.
- GeoParquet: it isn't readable in a text editor.
- CSV plus a separate metadata JSON: that makes two files to keep in step.

## R8. New dependencies

| Package | Kind | Justification |
|---|---|---|
| `rasterio` | runtime | Reads the elevation GeoTIFFs. geopandas, shapely and pyproj don't read rasters. Wheels for Python 3.14 (cp314) exist for Linux, macOS and Windows (1.5.2). |
| `mypy` | dev | The constitution requires a static type check before merge (Principle V), and CI has none yet. Wheels for Python 3.14 exist (2.4.1). |

Python's built-in `tomllib`, `hashlib` and `urllib` cover the pin file, checksums and
downloads, so no other packages are needed.

## Sources

- [DataSF Building Footprints](https://data.sfgov.org/Geographic-Locations-and-Boundaries/Building-Footprints/ynuv-fyni), from the Socrata metadata API
- [USGS TNM Access API](https://tnmaccess.nationalmap.gov/api/v1/products), 1 m DEM product listing
- [Golden Gate Bridge design and construction statistics](https://goldengate.org/bridge/history-research/statistics-data/design-construction-stats)
- [MTC/Caltrans SAS tower fact sheet](https://es.mtc.ca.gov/sites/default/files/Tower_Factsheet.pdf)
- [U.S. Lighthouse Society: Alcatraz Island](https://archives.uslhs.org/places/alcatraz-island)
- [San Francisco–Oakland Bay Bridge (Wikipedia)](https://www.wikipedia.org/wiki/Oakland_Bay_Bridge)
- [NOAA CO-OPS datums, station 9414290](https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/9414290/datums.json?units=metric)
- OpenStreetMap via the Overpass API (ODbL): GGB towers ways 1330049620 and 1330832680, Bay Bridge towers ways 432712476–432712479 and 237735191, Alcatraz lighthouse way 99202294
