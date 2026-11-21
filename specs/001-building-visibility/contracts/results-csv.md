# Contract: Results CSV

This is the only hand-off to the later web-page feature (spec FR-013 to FR-018).

## Encoding

- UTF-8 with no byte-order mark, `\n` line endings, and `,` as the delimiter. Fields are quoted
  per RFC 4180 only when needed.
- There is one header row, then exactly one row per building in the scene, sorted by
  `building_id` as plain text in ascending order.
- Numbers use fixed decimals: `lon` and `lat` have 7, and `*_m` columns have 2. Missing values
  are empty strings.

## Columns, in this order

| # | Column | Example | Meaning |
|---|---|---|---|
| 1 | `building_id` | `201006.0000001` | Source identifier |
| 2 | `lon` | `-122.3987654` | Viewpoint longitude, WGS84 |
| 3 | `lat` | `37.7912345` | Viewpoint latitude, WGS84 |
| 4 | `viewpoint_z_m` | `48.20` | Viewpoint height, NAVD88 m |
| 5 | `not_evaluated_reason` | `invalid_geometry` | Empty unless the building wasn't evaluated |
| 6–8 | `golden_gate_status`, `golden_gate_visible_points`, `golden_gate_blockers` | see below | |
| 9–11 | `alcatraz_status`, `alcatraz_visible_points`, `alcatraz_blockers` | | |
| 12–14 | `bay_bridge_status`, `bay_bridge_visible_points`, `bay_bridge_blockers` | | |
| 15 | `dataset_version` | `sf-buildings-20261121+usgs-1m-ca-sf-b23` | |
| 16 | `landmarks_version` | `1` | |
| 17 | `software_version` | `0.2.0` | The installed `bridgeview` package version |

For a fixture scene, columns 6–14 repeat once per landmark in the scene's landmark order,
using the scene's landmark ids.

## Per-landmark cells

- `<id>_status`: `visible`, `not_visible` or `not_evaluated`.
- `<id>_visible_points`: the visible point ids, separated by `;`, for example
  `ggb_south_tower;ggb_north_tower`.
- `<id>_blockers`: `point_id=blocker` pairs separated by `;`, where `blocker` is
  `building:<building_id>` or `ground`. For example:
  `ggb_midspan=building:201006.0004521;ggb_south_tower=ground`.

## Invariants (tested)

1. The row count equals the number of buildings in the scene, and `building_id` values are
   unique (SC-007).
2. `status = not_evaluated` if and only if `not_evaluated_reason` is non-empty. Both list cells
   are then empty.
3. `status = visible` if and only if `visible_points` is non-empty.
4. Each of a landmark's point ids appears exactly once across `visible_points` and
   `blockers`, unless the status is `not_evaluated`.
5. Two runs on the same inputs produce byte-identical files, whatever `--workers` is set to.
