"""Static checks for the standalone animated scene: no new control surface."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def test_scene_asset_is_publicly_whitelisted():
    server = (ROOT / "server.py").read_text()
    assert '"/backyard-scene.svg": ("web/backyard-scene.svg", "image/svg+xml")' in server
    assert (ROOT / "web/backyard-scene.svg").is_file()

def test_animation_is_observation_only():
    js = (ROOT / "web/app.js").read_text()
    scene = js[js.index("function updateScene()"):js.index("function render(){")]
    assert 'send(' not in scene and 'api(' not in scene
    for key in ("pool", "spa", "slide", "spillway", "jets", "light"):
        assert key in scene

def test_shell_precaches_scene_without_api():
    sw = (ROOT / "web/sw.js").read_text()
    assert '"/backyard-scene.svg"' in sw
    assert 'pathname.startsWith("/api/")' in sw

def test_reduced_motion_and_hidden_tab_pause():
    css = (ROOT / "web/style.css").read_text()
    js = (ROOT / "web/app.js").read_text()
    assert "prefers-reduced-motion:reduce" in css
    assert "scene-paused" in css and "document.hidden" in js

def test_approved_photo_is_present_and_jpeg():
    photo = ROOT / "web/backyard-final.jpg"
    assert photo.is_file()
    assert photo.stat().st_size > 100_000
    assert photo.read_bytes()[:3] == bytes.fromhex("ffd8ff")
    server = (ROOT / "server.py").read_text()
    assert '"/backyard-final.jpg": ("web/backyard-final.jpg", "image/jpeg")' in server

def test_scene_is_not_control_endpoint():
    html = (ROOT / "web/index.html").read_text()
    js = (ROOT / "web/app.js").read_text()
    assert 'id="backyardScene"' in html
    assert 'state={};updateScene()' in js
    assert 'scene-paused' in js
