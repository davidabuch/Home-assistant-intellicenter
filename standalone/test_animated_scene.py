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


def test_glass_finish_keeps_stateful_highlight_and_accessibility():
    css = (ROOT / "web/style.css").read_text()
    js = (ROOT / "web/app.js").read_text()
    assert "backdrop-filter:blur(19px)" in css
    assert "#controls #features .feature-tile.active" in css
    assert 'setAttribute("aria-checked",String(on))' in js
    assert 'toggle.disabled=busy||!["on","off"].includes(e.state)' in js

def test_background_off_state_requires_clean_asset_before_animation_release():
    # The current approved photo visibly contains running slide and spillway water.
    # Preserve this release gate until a separate clean dry-base asset is committed.
    readme = (ROOT / "SCENE_ACCEPTANCE.md").read_text()
    assert "IN PROGRESS" in readme
    assert "dry" in readme.lower()


def test_offline_motion_lab_has_no_equipment_access():
    lab = (ROOT / "web/scene-lab.html").read_text()
    server = (ROOT / "server.py").read_text()
    assert "no HA connection" in lab
    assert "fetch(" not in lab and "/api/" not in lab
    assert "scene-lab.html" not in server  # Never expose test toggles on installed app.
    for cls in ("slide-running", "spillway-running", "jets-running", "pool-running", "spa-running", "light-running"):
        assert cls in lab


def test_independent_water_effect_masks_and_motion():
    css = (ROOT / "web/style.css").read_text()
    assert "--slide-x:" in css and "--fall-x:" in css
    assert "scene-waterfall-slide" in css
    assert "scene-bubble-rise" in css
    assert "prefers-reduced-motion:reduce" in css
    assert ".backyard-scene .slide-flow" in css
    assert ".backyard-scene .spillway-flow" in css


def test_clean_off_photo_is_present_and_served():
    photo=ROOT / "web/backyard-off.jpg"
    assert photo.is_file()
    assert photo.stat().st_size > 100_000
    assert photo.read_bytes()[:3] == bytes.fromhex("ffd8ff")
    server=(ROOT / "server.py").read_text()
    css=(ROOT / "web/style.css").read_text()
    sw=(ROOT / "web/sw.js").read_text()
    assert '"/backyard-off.jpg": ("web/backyard-off.jpg", "image/jpeg")' in server
    assert "url('/backyard-off.jpg')" in css
    assert 'cache.add("/backyard-off.jpg")' in sw


def test_scene_layers_share_photo_cover_coordinate_space():
    html=(ROOT / "web/index.html").read_text()
    lab=(ROOT / "web/scene-lab.html").read_text()
    css=(ROOT / "web/style.css").read_text()
    for markup in (html,lab):
        assert 'class="backyard-scene"' in markup
        assert 'class="scene-art"' in markup
        assert markup.index('class="scene-art"') < markup.index('class="scene-effect slide-flow"')
    assert 'aspect-ratio:651 / 1199' in css
    assert "background:#0a2840 url('/backyard-off.jpg')" in css
    assert ".scene-art .slide-flow" in css
    assert ".scene-art .spillway-flow" in css
    assert "clip-path:polygon" in css


def test_offline_photo_motion_is_isolated_and_uses_real_pixels():
    lab=(ROOT / "web/scene-lab.html").read_text()
    script=(ROOT / "web/scene-photo-motion.js").read_text()
    server=(ROOT / "server.py").read_text()
    assert 'src="./scene-photo-motion.js"' in lab
    assert "scene-photo-motion.js" not in server
    assert "backyard-off.jpg" in script
    assert "drawImage(image" in script and "ctx.clip()" in script
    assert 'scene.classList.contains("pool-running")' in script
    assert 'scene.classList.contains("spa-running")' in script
    assert 'fetch(' not in script and 'api(' not in script
