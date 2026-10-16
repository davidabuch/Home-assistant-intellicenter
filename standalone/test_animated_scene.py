"""Regression checks for the Pool & Spa Family decorative backyard scene."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_approved_composited_photo_is_present_and_served():
    photo = ROOT / "web/backyard-final.jpg"
    assert photo.is_file()
    assert photo.stat().st_size > 100_000
    assert photo.read_bytes()[:3] == bytes.fromhex("ffd8ff")
    server = (ROOT / "server.py").read_text()
    assert '"/backyard-final.jpg": ("web/backyard-final.jpg", "image/jpeg")' in server


def test_live_markup_uses_one_decorative_scene_not_photo_layers():
    html = (ROOT / "web/index.html").read_text()
    assert 'id="backyardScene"' in html
    assert 'class="scene-art"' not in html
    assert 'photo-on-layer' not in html
    for name in (
        "backyard-static-off.jpg",
        "scene-on-pool.png",
        "scene-on-spa.png",
        "scene-on-jets.png",
        "scene-on-slide.png",
        "scene-on-spillway.png",
        "scene-on-light.png",
        "scene-on-spa-light.png",
    ):
        assert name not in html


def test_backyard_photo_is_static_and_independent_of_ha_state():
    js = (ROOT / "web/app.js").read_text()
    scene = js[js.index("function updateScene()"):js.index("function render(){")]
    assert "function updateScene(){}" in scene
    assert "state[" not in scene
    assert "classList.toggle" not in scene
    assert "send(" not in scene
    assert "api(" not in scene


def test_css_forces_original_single_photo_and_retires_layers():
    css = (ROOT / "web/style.css").read_text()
    assert "url('/backyard-final.jpg')" in css
    assert "one composited decorative photograph" in css
    assert ".backyard-scene .photo-on-layer" in css
    assert "display:none!important" in css


def test_service_worker_precaches_only_recovered_scene_assets():
    sw = (ROOT / "web/sw.js").read_text()
    assert '"/backyard-final.jpg"' in sw
    assert 'pathname.startsWith("/api/")' in sw
    assert "backyard-static-off.jpg" not in sw
    assert "scene-on-" not in sw


def test_scene_remains_noninteractive_and_controls_remain_live():
    html = (ROOT / "web/index.html").read_text()
    js = (ROOT / "web/app.js").read_text()
    assert 'aria-hidden="true"' in html
    assert 'id="backyardScene"' in html
    assert 'send("light"' in js
    assert 'send(key,on?"off":"on")' in js
    assert 'api("state")' in js
    assert 'api("permissions")' in js


def test_glass_controls_keep_confirmed_state_highlight_and_accessibility():
    css = (ROOT / "web/style.css").read_text()
    js = (ROOT / "web/app.js").read_text()
    assert "backdrop-filter:blur(19px)" in css
    assert "#controls #features .feature-tile.active" in css
    assert 'setAttribute("aria-checked",String(on))' in js
    assert 'toggle.disabled=busy||!["on","off"].includes(e.state)' in js


def test_offline_scene_lab_is_not_publicly_served():
    server = (ROOT / "server.py").read_text()
    assert "scene-lab.html" not in server


def test_approved_reference_chrome_and_mobile_glass_contract():
    html = (ROOT / "web/index.html").read_text()
    css = (ROOT / "web/style.css").read_text()
    sw = (ROOT / "web/sw.js").read_text()
    assert 'class="reference-toolbar"' not in html
    assert "Features ON" not in html
    assert "Live Water Features" not in html
    assert 'class="settings-orb"' not in html
    assert "reference-match-2" in html
    assert "#controls{padding-top:clamp(245px,45dvh,510px)!important}" in css
    assert "#controls #features .feature-tile" in css
    assert "min-height:76px!important" in css
    assert "#controls #sanitation .feature-tile::after" in css
    assert "reference-match-2" in sw
