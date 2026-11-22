# Feature Specification: Building Landmark Visibility

**Feature Branch**: `001-building-visibility`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Determine which San Francisco buildings have a line of sight to the Golden Gate Bridge, Alcatraz Island, and the Bay Bridge, using public building footprint and height data. Other buildings can block the view. The dataset is downloaded by a script that pins its version and checks its checksum. Correctness is checked against small hand-worked cases, such as three box-shaped buildings and a target whose visibility is worked out by hand. The output should be a format that can be easily checked, and useful for a web page that shows the results is a separate, later feature."

## Clarifications

### Session 2026-11-21

- Q: When the building data gives more than one height for a building, which one is used? → A: The observer uses the typical (median) roof height, and the obstruction uses the highest recorded height. Viewing from inside, at floor level, is deferred to a later feature. (Originally "lowest roof height". It was revised on 2026-11-22 because the data's minimum field includes edge cells at street level; see research R1.)
- Q: For an L-shaped, U-shaped or courtyard building whose geometric center falls outside the footprint, where is the observer? → A: Always at the geometric center, even when it falls outside the footprint.
- Q: Does the ground-elevation model show bare ground or the surface including buildings and trees? → A: Bare ground only, with buildings, trees and other structures removed.

## User Scenarios & Testing *(mandatory)*

The primary user is the project owner, who needs trustworthy visibility results and must be
able to check them. A secondary consumer is the later web-page feature, which will read the
results this feature produces.

### User Story 1 - Visibility for a small, hand-checkable scene (Priority: P1)

The project owner describes a small scene: a few box-shaped buildings with known footprints and
heights, plus a target with a known location and height. The system reports, for each building,
whether that building can see the target, and if not, what blocks it. The owner compares the
answer with one worked out by hand.

**Why this priority**: This is the core visibility rule. If it is wrong on a three-building
scene, it is wrong for the whole city, and a city-wide answer cannot be checked by hand.
Getting it right on small cases first is the foundation for everything else.

**Independent Test**: Run the system on a hand-worked fixture scene, with no city data
involved. Every building's result must match the hand-worked answer.

**Acceptance Scenarios**:

1. **Given** three box-shaped buildings in a row, A, B and C, with a target beyond C, where B is
   taller than the sight line from A to the target, **When** visibility is computed, **Then** A
   is reported as not visible, with B as the blocker.
2. **Given** the same row, where B is shorter than the sight line from A to the target,
   **When** visibility is computed, **Then** A is reported as visible.
3. **Given** a building with no other building between it and the target, **When** visibility
   is computed, **Then** it is reported as visible.
4. **Given** any building, **When** visibility is computed, **Then** the building never blocks
   its own view.
5. **Given** a landmark with two reference points, where one point is blocked and the other is
   clear, **When** visibility is computed, **Then** the landmark is reported as visible, and
   the record shows which point is in view and what blocks the other.
6. **Given** a ridge of ground between a building and the target that rises above the sight
   line, **When** visibility is computed, **Then** the building is reported as not visible,
   with the ground as the blocker.

---

### User Story 2 - Obtain the city data reproducibly (Priority: P2)

The project owner runs a single command that downloads the public San Francisco building
footprint and height dataset and the public bare-ground elevation model. The command always fetches
the same pinned versions and confirms each file is intact before anything uses it.

**Why this priority**: City-wide results are only meaningful and repeatable if everyone works
from the identical dataset. The dataset is too large to keep in the repository, so retrieval
must be reliable and verifiable.

**Independent Test**: Run the download command on a clean machine. It must produce a file whose
integrity check passes. Corrupting the file must cause the check to fail.

**Acceptance Scenarios**:

1. **Given** no local copy of the dataset, **When** the owner runs the download command,
   **Then** the pinned version is downloaded and the integrity check passes.
2. **Given** a downloaded file that does not match the expected checksum, **When** the download
   command or any later step checks it, **Then** the system stops with a clear error, and no
   results are produced from that file.
3. **Given** a valid local copy already present, **When** the owner runs the download command
   again, **Then** it is not re-downloaded.

---

### User Story 3 - City-wide visibility results (Priority: P3)

The project owner runs the visibility computation over every building in the pinned dataset,
for all three landmarks. The output is a results file with one record per building, which the
owner can spot-check and the later web page can read directly.

**Why this priority**: This is the end goal, but it depends on Stories 1 and 2 being correct.

**Independent Test**: Run the computation on the pinned dataset and pick ten buildings at
random. For each, the owner must be able to confirm from the output alone which landmarks were
judged visible and why any were not, for example which building blocked the view.

**Acceptance Scenarios**:

1. **Given** the verified dataset, **When** the city-wide computation runs, **Then** the
   results file contains exactly one record per building, with a visible or not-visible result
   for each of the three landmarks.
2. **Given** a building whose view of a landmark is blocked, **When** the owner looks up its
   record, **Then** the record identifies what blocked the view.
3. **Given** the same dataset and software version, **When** the computation runs twice,
   **Then** the two results files are identical.

---

### Edge Cases

- **Missing or invalid height**: a building with no height, zero height or a malformed
  footprint is kept in the output and marked as "not evaluated", with the reason. It is never
  silently dropped, and it does not block other buildings' views.
- **Grazing sight lines**: a sight line that only touches the edge or top of another building,
  without passing through it, counts as not blocked. This makes hand-worked answers
  unambiguous.
- **Irregular footprints**: for an L-shaped, U-shaped or courtyard building, the viewpoint may
  sit above open ground or a neighboring lot. It is still treated as that building's viewpoint,
  and that building still does not block its own view. If the viewpoint falls inside a
  neighboring building's block, that neighbor blocks the view as normal.
- **Adjacent buildings**: buildings that share a wall can block each other like any other
  building.
- **Buildings near or on the landmarks**: buildings on Treasure Island, Yerba Buena Island or
  Alcatraz are evaluated like any other building. A building on Alcatraz is reported as seeing
  Alcatraz.
- **Distance**: there is no maximum viewing distance. A building is judged only on whether the
  sight line is clear, allowing for the curvature of the Earth.
- **Bad download**: if the download fails partway or produces a checksum mismatch, the partial
  file is not used and the error states what went wrong.

## Requirements *(mandatory)*

### Functional Requirements

**Visibility rule**

- **FR-001**: The system MUST decide, for each building and each landmark, whether an
  unobstructed straight sight line exists from the building's viewpoint to the landmark.
  The viewpoint is a single point at the building's roof height, directly above the geometric
  center of its footprint. The geometric center is used even when it falls outside the
  footprint, for example in a courtyard. The viewpoint's height is the building's typical
  (median) roof elevation.
- **FR-002**: Each landmark MUST be represented by a small set of documented reference points,
  for example both tower tops and midspan of a bridge, or several points around the island.
  A landmark MUST count as visible from a building when at least one of its reference points
  has an unobstructed sight line from the building's viewpoint.
- **FR-003**: Other buildings MUST be treated as solid blocks rising from their footprint to
  their ground elevation plus their highest recorded height, and MUST block a sight line that
  passes through them. Where the source data gives only one height for a building, that
  height is used for both the observer and the obstruction.
- **FR-004**: The ground MUST block sight lines that pass below its surface, using a public
  bare-ground elevation model of the city, which excludes buildings, trees and other
  structures. That model is a second pinned dataset, subject to the
  same version, checksum and provenance rules as the building data (FR-009 to FR-012).
- **FR-005**: A building MUST NOT block its own view.
- **FR-006**: A sight line that only touches an obstruction's surface MUST count as not
  blocked.
- **FR-007**: Sight-line calculations MUST allow for the curvature of the Earth.

**Landmarks**

- **FR-008**: Each of the three landmarks (Golden Gate Bridge, Alcatraz Island, San Francisco –
  Oakland Bay Bridge) MUST be defined by fixed, documented reference locations and heights,
  stored in a reviewable file in the repository together with their sources.

**Data**

- **FR-009**: A download command MUST fetch one specific, pinned version of each city
  dataset: the public San Francisco building footprint and height dataset, and the public
  bare-ground elevation model.
- **FR-010**: The download command MUST verify each file against a recorded checksum. A
  mismatch MUST stop the process and MUST NOT leave a file that later steps would use.
- **FR-011**: The city datasets MUST NOT be stored in the repository.
- **FR-012**: Each dataset's source, version, date and license MUST be recorded in the
  repository before the dataset is used.

**Output**

- **FR-013**: The system MUST produce a results file with exactly one record per building in
  the dataset. Each record contains the building's identifier from the source dataset, its
  location, and a result for each landmark: visible, not visible or not evaluated.
- **FR-014**: For each not-visible result, the record MUST name, for each of the landmark's
  reference points, what blocked the view: the identifier of the first blocking building, or
  the ground.
- **FR-014a**: For each visible result, the record MUST list which of the landmark's
  reference points are in view.
- **FR-015**: For each not-evaluated result, the record MUST state the reason.
- **FR-016**: The results file MUST record the dataset version, the landmark definitions
  version and the software version that produced it.
- **FR-017**: The results file MUST be in an open, widely supported format that can be opened
  in a spreadsheet or text editor and also read by a web page, without this feature's code.
- **FR-018**: Given identical inputs, the system MUST produce byte-identical results files.

**Verification**

- **FR-019**: The repository MUST include small hand-worked fixture scenes, each with its
  expected answer and the hand calculation behind it, including at least: three box-shaped
  buildings in a row with a blocked case and a clear case, a grazing sight line, a building
  that would block itself if FR-005 were not applied, a landmark with one blocked and one
  clear reference point, and a ridge of ground that blocks the view.
- **FR-020**: The system MUST be able to run on a fixture scene in place of the city
  dataset, producing results in the same format as FR-013.

### Key Entities

- **Building**: a structure from the source dataset. It has a source identifier, a footprint
  shape, a typical roof height (used for its viewpoint), a highest height (used when it blocks
  others) and a ground elevation. A building is both an observer and a
  potential obstruction.
- **Landmark**: one of the three targets. It has a name, a small set of named reference
  points with locations and heights, and a documented source for those values.
- **Ground Elevation Model**: the height of the bare ground across the city, excluding
  buildings and vegetation. It is used both
  to place buildings and as an obstruction.
- **Scene**: the buildings, ground and landmarks for one computation run, either a small
  hand-worked fixture or the full city data.
- **Visibility Result**: one building's outcome for one landmark: visible, not visible (with
  the blocker) or not evaluated (with the reason).
- **Dataset Pin**: the identity of the city dataset: source, version, retrieval location,
  checksum and license.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of buildings in every hand-worked fixture scene get the expected result,
  with at least 6 fixture scenes covering the cases in FR-019.
- **SC-002**: The owner can confirm or refute any single building's result from the results
  file, plus a map, in under 5 minutes.
- **SC-003**: In a spot check of 20 randomly chosen city buildings, the owner judges at least
  18 results correct by inspecting the area on a map or photo.
- **SC-004**: The full city-wide computation for all three landmarks finishes in under 1 hour
  on a typical developer laptop.
- **SC-005**: Two runs on the same inputs produce identical results files, every time.
- **SC-006**: A corrupted or wrong-version dataset is rejected before any results are produced,
  every time.
- **SC-007**: Every building in the dataset appears exactly once in the results file, with no
  silent drops.

## Assumptions

- The city-wide run covers every building in the chosen public dataset that lies within the
  City and County of San Francisco, including Treasure Island, Yerba Buena Island and Alcatraz.
- The chosen building dataset provides a footprint and a height for most buildings. A public
  bare-ground elevation model covering all of San Francisco, including the islands, is available.
  The exact datasets and versions are chosen during planning and recorded per FR-012.
- Trees, ground features finer than the elevation model's resolution, weather, haze and window
  placement are ignored. Visibility here means geometric line of sight only.
- Observing from the typical roof height and blocking at the highest height is deliberately
  cautious: it errs toward reporting a view as blocked.
- Building heights come from a 2010 LiDAR survey, while the footprints are from 2017. Buildings
  completed after 2010, such as Salesforce Tower, probably carry the height of their 2010 site,
  so they are under-represented both as observers and as obstructions. Fresh heights from the
  2023 USGS LiDAR are a candidate later feature. Rooftop spires and antennas are
  treated as solid blocks over the whole footprint. Observing from inside the building at
  floor level is a later feature.
- Observing from one point at the roof center and checking a few points per landmark is a
  deliberate simplification for this first version. Sampling more of the roof edge is a
  possible later refinement.
- Atmospheric refraction is handled with a standard fixed correction alongside Earth curvature,
  rather than modeled in detail.
- The results file is the only hand-off to the later web-page feature. That feature, and any
  map display, are out of scope here.
- The computation runs as a batch job on a developer machine. A live or on-demand service is
  out of scope.
