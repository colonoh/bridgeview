# Data sources

This page records the provenance of every outside dataset that Bridgeview uses (constitution:
Technology Stack & Constraints; spec FR-012). The exact files, with URLs, sizes and SHA-256
hashes, are pinned in [`datasets.toml`](../datasets.toml). None of the data is committed to
this repository. `bridgeview download` fetches it into `data/raw/`.

## San Francisco building footprints

| | |
|---|---|
| Publisher | City and County of San Francisco, DataSF |
| Dataset | Building Footprints, Socrata ID `ynuv-fyni` |
| Source | <https://data.sfgov.org/Geographic-Locations-and-Boundaries/Building-Footprints/ynuv-fyni> |
| Version | DataSF `data_as_of` 2023-09-11. Footprints are from the 2010 Pictometry model, split in 2017; height statistics are from 2010 LiDAR. |
| License | [Open Data Commons PDDL 1.0](http://opendatacommons.org/licenses/pddl/1.0/) (public domain dedication) |
| Retrieved | Recorded per snapshot in `datasets.toml` (`retrieved`) |
| Used for | Footprints, observer height (`median_1st_m`), obstruction height (`peak_1st_m`) and building ground elevation (`gnd_min_m`) |
| How it is pinned | DataSF reloads the dataset daily, so its export checksum changes even when the content doesn't. A one-time GeoJSON export (`bridgeview snapshot-buildings`) is published as a GitHub Release asset on this repository, and that file is pinned. PDDL permits redistribution. |
| Known limitation | Heights are from 2010. Buildings completed after 2010 probably carry the height of their 2010 site (spec Assumptions). |

## Bare-ground elevation

| | |
|---|---|
| Publisher | U.S. Geological Survey, 3D Elevation Program (3DEP) |
| Dataset | 1-metre DEM, project `CA_SanFrancisco_B23`, tiles `x54y418`, `x54y419`, `x55y418` and `x55y419` |
| Source | <https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/CA_SanFrancisco_B23/TIFF/> (listed via the [TNM Access API](https://tnmaccess.nationalmap.gov/api/v1/products)) |
| Version | Published 2024-08-26 |
| License | U.S. Government work, public domain |
| Retrieved | Recorded in `datasets.toml` (`retrieved`) |
| Used for | Bare-earth ground surface for terrain blocking (FR-004) and for placing viewpoints. CRS EPSG:26910; heights NAVD88 metres. |
| Known gaps | Coverage over Alcatraz, Treasure Island and Yerba Buena Island is to be checked (tasks.md, the Alcatraz/Treasure Island coverage check in US3). |

## Landmark reference points

| | |
|---|---|
| Positions | © OpenStreetMap contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), retrieved 2026-11-21 via the Overpass API. Bridge tower and lighthouse centroids. |
| Heights | The Golden Gate Bridge Highway & Transportation District (tower height and clearance), the Caltrans/MTC SAS tower fact sheet, the U.S. Lighthouse Society (Alcatraz focal plane) and Wikipedia (Bay Bridge west-span towers). Each point's source is recorded in `src/bridgeview/landmarks.toml`. |
| Datum conversion | NOAA CO-OPS station 9414290 (San Francisco) tidal datums, epoch 1983–2001, used to convert "above water" heights to NAVD88 (research R3). |
