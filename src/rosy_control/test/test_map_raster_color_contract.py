"""concept 16 §6 — /map.png의 색과 콘솔 캔버스의 색은 같은 값이어야 한다.

서버는 `sensing/map_raster.py`가 굽고 클라이언트는 `web/dashboard.html`이
그린다. 두 값이 어긋나면 오버레이가 섞이지 않고, 예전에 실제로 어긋나 있었다:
RGB 튜플이 BGR 배열에 그대로 들어가 PNG의 벽 색이 #e1e0d9가 아니라
#d9e0e1로 나왔다.

이 시험은 소스를 텍스트로 읽는다. `map_raster.py`를 import하면 numpy가
따라오는데 CI 의존 목록에 numpy가 없다(D-73: 이 모듈이 소유한 파일만 단언).
"""
import ast
import re
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
RASTER = PACKAGE_ROOT / 'rosy_control' / 'sensing' / 'map_raster.py'
CONSOLE = PACKAGE_ROOT / 'web' / 'dashboard.html'


def server_rgb():
    """`OCCUPANCY_RGB` 리터럴을 실행 없이 읽는다."""
    tree = ast.parse(RASTER.read_text(encoding='utf-8'))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if 'OCCUPANCY_RGB' in names:
            return {
                key.value: tuple(ast.literal_eval(value))
                for key, value in zip(node.value.keys, node.value.values)
            }
    raise AssertionError('map_raster.py에 OCCUPANCY_RGB 선언이 없다')


def console_tokens():
    text = CONSOLE.read_text(encoding='utf-8')
    found = {}
    for token in ('unk', 'free', 'wall'):
        match = re.search(rf'--{token}:\s*#([0-9a-fA-F]{{6}})', text)
        assert match, f'dashboard.html에 --{token} 토큰이 없다'
        found[token] = match.group(1).lower()
    return found


class MapRasterColorContractTest(unittest.TestCase):
    NAMES = (('unknown', 'unk'), ('free', 'free'), ('wall', 'wall'))

    def test_server_raster_matches_the_console_canvas(self):
        server = server_rgb()
        console = console_tokens()

        for server_key, token in self.NAMES:
            with self.subTest(color=server_key):
                rendered = '%02x%02x%02x' % server[server_key]
                self.assertEqual(
                    rendered,
                    console[token],
                    f'{server_key}: PNG는 #{rendered}, 캔버스는 #{console[token]}',
                )

    def test_bgr_is_derived_and_not_written_by_hand(self):
        """BGR을 손으로 적으면 채널 역전이 다시 생긴다. 파생이어야 한다."""
        source = RASTER.read_text(encoding='utf-8')
        self.assertIn('OCCUPANCY_BGR', source)
        self.assertRegex(
            source,
            r'OCCUPANCY_BGR\s*=\s*\{[^}]*reversed\(',
            'OCCUPANCY_BGR은 OCCUPANCY_RGB에서 뒤집어 파생해야 한다',
        )

    def test_the_javascript_mirror_agrees_with_its_own_css_token(self):
        """콘솔이 같은 값을 CSS와 JS 두 곳에 들고 있다(S8까지 남는 중복)."""
        text = CONSOLE.read_text(encoding='utf-8')
        css = console_tokens()
        mirror = re.search(r"unk:\s*'#([0-9a-fA-F]{6})'", text)

        assert mirror, 'dashboard.html의 JS 색 표에 unk가 없다'
        self.assertEqual(mirror.group(1).lower(), css['unk'])


if __name__ == '__main__':
    unittest.main()
