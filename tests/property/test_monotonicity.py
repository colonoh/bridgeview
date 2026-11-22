"""Hypothesis properties of the visibility rule (plan: Constitution Check II).

Random scenes of axis-aligned boxes on flat ground, with curvature off.
"""

from dataclasses import replace

import shapely
from hypothesis import given, settings
from hypothesis import strategies as st

from bridgeview.ground import GroundModel
from bridgeview.results import VISIBLE
from bridgeview.scene import Building, Landmark, ReferencePoint, Scene, assess_buildings
from bridgeview.visibility import compute_visibility

X0, Y0 = 550000.0, 4180000.0


@st.composite
def scenes(draw: st.DrawFn) -> Scene:
    n = draw(st.integers(2, 6))
    buildings = []
    for i in range(n):
        x = draw(st.integers(0, 180))
        y = draw(st.integers(0, 180))
        w = draw(st.integers(4, 20))
        h = draw(st.integers(4, 20))
        vz = float(draw(st.integers(5, 60)))
        top = vz + float(draw(st.integers(0, 20)))
        fp = shapely.box(X0 + x, Y0 + y, X0 + x + w, Y0 + y + h)
        buildings.append(Building(f"b{i}", fp, vz, top))
    pts = tuple(
        ReferencePoint(f"p{k}", X0 + draw(st.integers(-50, 250)), Y0 + draw(st.integers(-50, 250)),
                       float(draw(st.integers(0, 80))), "test")
        for k in range(draw(st.integers(1, 3)))
    )
    ground = GroundModel.constant(0.0)
    return Scene("prop", assess_buildings(buildings, ground), ground,
                 (Landmark("lm", "LM", pts),), "prop", "prop", curvature=False)


def _clear(scene: Scene) -> dict[tuple[str, str], bool]:
    out = {}
    for r in compute_visibility(scene):
        lm = r.landmarks[0]
        for p in lm.visible_points:
            out[(r.building_id, p)] = True
        for p, _ in lm.blockers:
            out[(r.building_id, p)] = False
    return out


def _with(scene: Scene, buildings: list[Building]) -> Scene:
    return replace(scene, buildings=assess_buildings(buildings, scene.ground))


@settings(max_examples=60, deadline=None)
@given(scenes(), st.data())
def test_raising_an_obstruction_never_reveals(scene: Scene, data: st.DataObject) -> None:
    i = data.draw(st.integers(0, len(scene.buildings) - 1))
    before = _clear(scene)
    bs = list(scene.buildings)
    b = bs[i]
    bs[i] = replace(b, top_z=b.top_z + data.draw(st.integers(1, 30)))  # type: ignore[operator]
    after = _clear(_with(scene, bs))
    for (obs, p), clear in after.items():
        if obs != b.building_id and clear:
            assert before[(obs, p)], (obs, p)


@settings(max_examples=60, deadline=None)
@given(scenes(), st.data())
def test_removing_a_building_never_hides(scene: Scene, data: st.DataObject) -> None:
    i = data.draw(st.integers(0, len(scene.buildings) - 1))
    before = _clear(scene)
    bs = list(scene.buildings)
    removed = bs.pop(i)
    after = _clear(_with(scene, bs))
    for (obs, p), clear in before.items():
        if obs != removed.building_id and clear:
            assert after[(obs, p)], (obs, p)


@settings(max_examples=60, deadline=None)
@given(scenes(), st.data())
def test_raising_the_observer_never_hides(scene: Scene, data: st.DataObject) -> None:
    i = data.draw(st.integers(0, len(scene.buildings) - 1))
    b = scene.buildings[i]
    before = _clear(scene)
    lift = float(data.draw(st.integers(1, 30)))
    bs = list(scene.buildings)
    # Raise only the viewpoint (top_z follows if it would fall below), so b's
    # strength as an obstruction for others stays the same where possible.
    bs[i] = replace(b, viewpoint_z=b.viewpoint_z + lift, top_z=max(b.top_z, b.viewpoint_z + lift))  # type: ignore[operator, type-var]
    after = _clear(_with(scene, bs))
    for p in scene.landmarks[0].points:
        if before[(b.building_id, p.id)]:
            assert after[(b.building_id, p.id)], p.id


@settings(max_examples=60, deadline=None)
@given(scenes())
def test_never_blocked_by_itself(scene: Scene) -> None:
    for r in compute_visibility(scene):
        for _, blocker in r.landmarks[0].blockers:
            assert blocker != f"building:{r.building_id}"
        assert r.landmarks[0].status in (VISIBLE, "not_visible")
