"""Public background transport/cache coverage; no Home Assistant requests."""
import io
from pathlib import Path
import re
import unittest
from PIL import Image
import test_icons

WEB = Path(__file__).resolve().parents[1] / 'web'


class PhotographicBackgroundTests(unittest.TestCase):
    def test_finished_photo_is_public_and_never_calls_equipment(self):
        body, headers = test_icons.IconTests().request('/backyard-final.jpg', 'pool.test')
        self.assertEqual(body, (WEB / 'backyard-final.jpg').read_bytes())
        self.assertEqual(headers['Content-Type'], 'image/jpeg')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        with Image.open(io.BytesIO(body)) as im:
            self.assertEqual(im.size, (836, 1881))
            # Full-width photo covers all tested phone heights without tiling.
            for width, height in ((375, 812), (393, 852), (430, 932)):
                self.assertGreaterEqual(im.height * width / im.width, height)

    def test_grass_overlays_retired_and_cache_shell_versions_match(self):
        css, html, sw = [(WEB / name).read_text() for name in ('style.css', 'index.html', 'sw.js')]
        for text in (css, html, sw):
            self.assertNotIn('lawnForeground', text)
            self.assertNotIn('lawn-photo.svg', text)
        self.assertNotIn('body::after', css)
        self.assertNotIn('data:image/jpeg;base64', css)
        self.assertFalse((WEB / 'lawn-photo.svg').exists())
        token = re.search(r'/style.css\?v=([^"\s]+)', html).group(1)
        self.assertIn('/style.css?v=' + token, sw)
        self.assertIn('/app.js?v=' + token, sw)
        self.assertIn('/backyard-final.jpg', sw)
        self.assertIn('new URL(req.url).pathname.startsWith("/api/")', sw)
        self.assertIn('req.method!=="GET"', sw)
