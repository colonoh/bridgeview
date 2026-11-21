# Contract: Hand-Worked Fixture Scene

Fixture scenes live in `tests/fixtures/scenes/<name>.toml`. Each sits next to a
`<name>.expected.csv` file that follows [results-csv.md](results-csv.md) and holds the
hand-worked answer. Each scene file starts with a comment block that shows the hand
calculation (FR-019).

## Format (TOML)

```toml
name = "three_boxes_blocked"
crs = "EPSG:26910"          # required; fixtures sit at real SF-area coordinates
curvature = false           # optional, default true; false makes hand arithmetic exact

[ground]                     # either a constant plane...
constant_z = 0.0
# ...or a grid:
# origin_x = 550000.0; origin_y = 4182000.0; resolution = 1.0
# z = [[0.0, 0.0, ...], ...]   # rows go north to south

[[buildings]]
id = "A"
footprint = [[550000, 4180000], [550010, 4180000], [550010, 4180010], [550000, 4180010]]
viewpoint_z = 10.0
top_z = 10.0

[[landmarks]]
id = "target"
name = "Target"
[[landmarks.points]]
id = "t1"
x = 550100.0                 # fixtures give EPSG:26910 x and y directly, not lat and lon
y = 4180005.0
z = 10.0
source = "fixture"
```

## Required fixture scenes (SC-001: at least 6)

| Scene | What it proves | Spec reference |
|---|---|---|
| `three_boxes_blocked` | A, B, C in a row, with B above the A→target line, so A is blocked by B | US1 scenario 1 |
| `three_boxes_clear` | The same row with B below the line, so A is visible | US1 scenario 2 |
| `grazing` | A sight line exactly touches B's top edge, so it is not blocked | FR-006 |
| `self_block` | The observer's own `top_z` is above its `viewpoint_z`, and the building is still visible | FR-005 |
| `two_points` | One point is blocked and one is clear, so the landmark is visible and both lists are filled | US1 scenario 5 |
| `ground_ridge` | A grid with a ridge above the line, so the blocker is `ground` | US1 scenario 6 |
| `courtyard` | A U-shaped footprint whose centroid is outside it | Clarification Q2 |
| `curvature` | A low line over about 10 km of flat ground, blocked only once curvature is applied | FR-007 |
