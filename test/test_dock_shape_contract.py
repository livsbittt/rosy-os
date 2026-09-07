"""도크 형상 계약 — Gazebo 모델과 감지기가 갈라지지 않게 고정한다.

형상 하나를 두 곳이 안다: `src/rosy_gz_sim/models/dock/model.sdf` 가 시뮬레이터에
기둥을 세우고, `rosy_core.docking.profile.DockProfile` 이 그 배치를 찾는다. 둘이
어긋나면 **스윕은 감지기가 찾지 않는 형상을 재고, 그 결과가 판정으로 나간다** —
기하 후보가 탈락했다는 결론이 실은 SDF 오타였다는 뜻이 된다.

`test_dock_profile.py` 는 이것을 잡지 못한다. 그쪽 합성 스캔은 전부 `DockProfile`
에서 만들어지므로 프로파일과 테스트가 정의상 서로 일치한다. 이 파일이 그 고리를
닫는 유일한 곳이다.

가운데 기둥의 20 mm 전진에는 부호가 있다. 로봇은 도크의 **−x** 면으로 들어오므로
"로봇 쪽으로"는 음수다. 부호를 뒤집으면 거울상 배치가 되고, 그것은 pytest 가 아니라
Gazebo 에서만 드러난다.

설계: docs/plans/2026-09-07-dock-detector-measurement-rig-design.md
"""

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src" / "rosy_gz_sim" / "models" / "dock" / "model.sdf"

#: 바닥 기준 스캔 평면. base_link 가 28 mm, rplidar_link 가 그 위로 67 mm.
SCAN_PLANE_M = 0.095


def _profile_module():
    entry = str(ROOT / "src" / "rosy_core")
    if entry not in sys.path:
        sys.path.insert(0, entry)
    from rosy_core.docking import profile

    return profile


def _sdf_posts() -> list[tuple[float, float, float, float, float]]:
    """`post_*` 원통 visual 을 (x, y, z, 반지름, 길이) 로. 횡 오름차순."""
    root = ET.parse(MODEL).getroot()
    posts = []
    for visual in root.iter("visual"):
        if not visual.get("name", "").startswith("post_"):
            continue
        cylinder = visual.find(".//cylinder")
        if cylinder is None:
            continue
        pose = [float(value) for value in visual.find("pose").text.split()]
        posts.append((pose[0], pose[1], pose[2],
                      float(cylinder.find("radius").text),
                      float(cylinder.find("length").text)))
    return sorted(posts, key=lambda post: post[1])


def _raycast(centres, radius, x, y, yaw, step, half=0.6):
    """센서 프레임 (x, y, yaw) 에 놓인 기둥들의 스캔."""
    placed = [(x + cx * math.cos(yaw) - cy * math.sin(yaw),
               y + cx * math.sin(yaw) + cy * math.cos(yaw))
              for cx, cy in centres]
    count = int(half / step)
    angle_min = -count * step
    ranges = []
    for index in range(2 * count + 1):
        bearing = angle_min + index * step
        dx, dy = math.cos(bearing), math.sin(bearing)
        best = math.inf
        for px, py in placed:
            along = dx * px + dy * py
            offset = px * px + py * py - radius * radius
            disc = along * along - offset
            if disc < 0.0 or along <= 0.0:
                continue
            hit = along - math.sqrt(disc)
            if 0.0 < hit < best:
                best = hit
        ranges.append(best if math.isfinite(best) else math.inf)
    return ranges, angle_min, step


def test_the_model_stands_the_posts_the_profile_looks_for():
    posts = _sdf_posts()
    profile = _profile_module().DockProfile()

    from_sdf = tuple((round(x, 4), round(y, 4)) for x, y, _, _, _ in posts)
    from_profile = tuple((round(x, 4), round(y, 4))
                         for x, y in profile.post_points())
    assert from_sdf == from_profile, (
        f"model.sdf stands posts at {from_sdf} but DockProfile looks for "
        f"{from_profile}; a sweep would measure a shape the fit does not want")


def test_the_model_uses_the_post_radius_the_fit_assumes():
    # 반지름은 중심 추정에 직접 들어간다 — 어긋나면 깊이가 그만큼 치우친다.
    posts = _sdf_posts()
    profile = _profile_module().DockProfile()
    for x, y, _, radius, _ in posts:
        assert math.isclose(radius, profile.post_radius_m), (
            f"post at ({x}, {y}) has radius {radius}, profile assumes "
            f"{profile.post_radius_m}")


def test_every_post_crosses_the_scan_plane():
    # 바닥에 깔린 것은 LiDAR 에 보이지 않는다. 기둥이 95 mm 를 지나지 않으면
    # 시뮬레이터에는 도크가 서 있고 스캔에는 아무것도 없다.
    for x, y, z, _, length in _sdf_posts():
        bottom, top = z - length / 2.0, z + length / 2.0
        assert bottom <= SCAN_PLANE_M <= top, (
            f"post at ({x}, {y}) spans z {bottom:.3f}..{top:.3f} and misses "
            f"the {SCAN_PLANE_M} m scan plane")


def test_the_fit_recovers_a_pose_from_the_models_own_geometry():
    module = _profile_module()
    profile = module.DockProfile()
    posts = _sdf_posts()
    centres = [(x, y) for x, y, _, _, _ in posts]
    radius = posts[0][3]
    step = math.radians(0.24)

    for truth_x, truth_y, truth_yaw_deg in [
            (0.700, 0.000, 0.0),
            (0.500, 0.030, 8.0),
            (0.350, -0.045, -12.0),
            (0.250, 0.060, 15.0)]:
        yaw = math.radians(truth_yaw_deg)
        ranges, angle_min, increment = _raycast(
            centres, radius, truth_x, truth_y, yaw, step)
        got = module.fit(ranges, angle_min, increment, profile,
                         module.SensorOffset(), now=0.0)
        assert got.found, (
            f"the model's own geometry was not recognised at "
            f"({truth_x}, {truth_y}, {truth_yaw_deg} deg): {got.reason}")
        assert got.observation.y == pytest.approx(truth_y, abs=0.002)


def test_a_mirrored_middle_post_is_refused():
    """이 파일의 검사가 공허하지 않다는 증거.

    가운데 기둥의 전진 부호만 뒤집은 배치를 거부하지 못한다면, 위의 일치
    검사들은 통과해도 아무것도 보장하지 않는다. 여유는 크지 않다 — 20 mm
    오프셋이 거울 중복에 주는 신호가 그만큼 약하고, 네 번째 기둥이 그것을
    키우는 알려진 지렛대다.
    """
    module = _profile_module()
    profile = module.DockProfile()
    posts = _sdf_posts()
    mirrored = [(-x, y) for x, y, _, _, _ in posts]
    radius = posts[0][3]

    ranges, angle_min, increment = _raycast(
        mirrored, radius, 0.500, 0.0, 0.0, math.radians(0.24))
    got = module.fit(ranges, angle_min, increment, profile,
                     module.SensorOffset(), now=0.0)
    assert not got.found, (
        "a mirrored layout was accepted, so the shape checks above prove "
        "nothing about the sign convention")
