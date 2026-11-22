# Data Model: Building Landmark Visibility

Phase 1 output for [plan.md](plan.md). Unless stated otherwise, coordinates are EPSG:26910
metres, and heights are NAVD88 metres.

## Building

One footprint from the building dataset, or from a fixture scene.

| Field | Type | Source (city data) | Rules |
|---|---|---|---|
| `building_id` | str | `sf16_bldgid` | Unique within a scene; this is also the sort key for output |
| `footprint` | Polygon or MultiPolygon | `shape`, reprojected from EPSG:4326 | Must be valid and non-empty, or the building is not evaluated |
| `viewpoint_z` | float, m | `median_1st_m` (research R1) | Must be finite |
| `top_z` | float, m | `peak_1st_m` | Must be finite and ≥ `viewpoint_z`; if lower, it is raised to `viewpoint_z` and a warning is logged |
| `ground_z` | float, m | `gnd_min_m` | Reported only; the ground check uses the elevation model |

**Derived**:
- `viewpoint`: the footprint's geometric centroid at height `viewpoint_z`. This holds even
  when the centroid is outside the footprint (clarification Q2).
- `evaluable`: true unless one of the "not evaluated" reasons below applies.

**Not-evaluated reasons**, which form a closed set:
- `invalid_geometry`
- `missing_height`: `viewpoint_z` or `top_z` is missing or not finite, or `viewpoint_z` is at
  or below `ground_z` when `ground_z` is given. The last case covers zero-height buildings.
- `viewpoint_outside_elevation_model`: the centroid falls on nodata or outside the elevation
  model.
- `viewpoint_below_ground`: `viewpoint_z` is below the elevation model at the centroid.

A building that is not evaluated still gets a row in the output, with that reason. It is also
left out as an obstruction (spec Edge Cases).

## Landmark and ReferencePoint

Loaded from `src/bridgeview/landmarks.toml`, or from the scene file for fixtures.

| Field | Type | Rules |
|---|---|---|
| `landmarks_version` | str | Required at the top level of `landmarks.toml`. Optional in fixture scenes, where it defaults to `"fixture"`. Written into every output row. |
| `Landmark.id` | str | One of `golden_gate`, `alcatraz` or `bay_bridge` for the city; free-form for fixtures |
| `Landmark.name` | str | Human-readable name |
| `ReferencePoint.id` | str | Unique across all landmarks; contains no `;`, `=` or `,` |
| `ReferencePoint.lat`, `.lon` | float | WGS84; converted to EPSG:26910 on load. Fixture scenes give EPSG:26910 `x` and `y` in their place (contracts/scene-fixture.md). |
| `ReferencePoint.z` | float, m | NAVD88 |
| `ReferencePoint.source` | str | Required: the citation for the position and height |

## GroundModel

The bare-ground elevation grid.

| Field | Type | Rules |
|---|---|---|
| `origin_x`, `origin_y` | float, m | The top-left corner of the grid, EPSG:26910 |
| `resolution` | float, m | 1.0 for the city |
| `z` | 2-D float32 array | NaN where the source has nodata |

It provides one operation, `sample(x, y) → z`, with bilinear interpolation. It returns NaN
outside the grid.

The city model is the four pinned tiles, cropped to the extent of the buildings plus 500 m and
cached as a `.npy` file under `data/cache/`. For a fixture, it is a small grid, or a constant
plane, defined in the scene file.

## Scene

Everything one computation run needs: the buildings, a GroundModel, the landmarks and their
reference points, and the fields below.

| Field | Type | Rules |
|---|---|---|
| `Scene.dataset_version` | str | For the city, the pinned dataset ids joined with `+`, in `datasets.toml` order. For a fixture, the scene's `name`. |
| `Scene.landmarks_version` | str | Taken from `landmarks_version` (see Landmark) |

## SightLine (internal)

One line from a building's viewpoint to one ReferencePoint.

- `d_total`: the horizontal distance, in metres.
- The corrected target height: `z_t' = z_t − (1−k)·d_total²/(2R)`.
- The sight-line height at distance `d`: `h(d) = z_v + (z_t' − z_v)·d/d_total`.
- An obstruction point at distance `d` with height `z` has corrected height
  `z − (1−k)·d²/(2R)`.
- Outcome: `clear`, `blocked_by_building(building_id)` or `blocked_by_ground`. The first
  blocker is the one nearest the observer.

The constants are k = 0.13, R = 6,371,000 m, and a blocking margin of 0.001 m.

## VisibilityResult

There is one per (building, landmark) pair.

| Field | Values |
|---|---|
| `status` | `visible`: at least one point is clear. `not_visible`: all points are blocked. `not_evaluated`: the building isn't evaluable. |
| `visible_points` | Ordered list of the ReferencePoint ids that are clear, in landmarks-file order |
| `blockers` | Ordered list of `(point_id, blocker)` for the blocked points. `blocker` is `building:<id>` or `ground`. |

**State rules**:
- `not_evaluated` if and only if the building isn't evaluable. Both lists are then empty.
- `visible` if and only if `visible_points` is non-empty.
- Each of a landmark's points appears exactly once, in either `visible_points` or `blockers`.

## DatasetPin

One entry in the `datasets.toml` file at the repository root.

| Field | Type | Rules |
|---|---|---|
| `id` | str | For example `sf-buildings-20261121` or `usgs-1m-x54y418` |
| `url` | str | HTTPS |
| `sha256` | str | 64 hexadecimal characters |
| `size` | int | Bytes; checked before the hash |
| `filename` | str | The name under `data/raw/` |
| `source`, `license`, `retrieved` | str | Provenance (FR-012); also summarised in `docs/data-sources.md` |
