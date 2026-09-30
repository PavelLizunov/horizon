"""Trusted SVG geometry/layering and purpose-specific icon contracts."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'docs' / 'assets' / 'dashboard'
NS = {'s': 'http://www.w3.org/2000/svg'}


def test_chip_pin_ends_join_trace_starts_on_both_faces():
    root = ET.parse(ASSETS / 'chip.svg').getroot()
    pins = root.find("s:g[@data-layer='pins']/s:path", NS).get('d')
    endpoints = {(int(x), int(y2)) for x, y1, y2 in re.findall(r'M(\d+) (\d+)V(\d+)', pins)}
    traces = root.find("s:g[@data-layer='traces']", NS)
    starts = set()
    for path in traces:
        starts.update((int(x), int(y)) for x, y in re.findall(r'M(\d+) (\d+)V', path.get('d')) if int(y) > 200)
    assert len(starts) == 10
    assert starts <= endpoints
    layers = [g.get('data-layer') for g in root.findall('s:g', NS)]
    assert layers.index('traces') < layers.index('package') < layers.index('pins')


def test_server_blocks_draw_back_to_front():
    root = ET.parse(ASSETS / 'server.svg').getroot()
    stack = next(g for g in root.findall('s:g', NS) if g.get('transform') == 'translate(0 15)')
    assert [g.get('transform') for g in stack] == ['translate(0 159)', 'translate(0 106)', 'translate(0 53)', 'translate(0 0)']


def test_svg_assets_have_no_active_or_external_content():
    for path in ASSETS.glob('*.svg'):
        root = ET.parse(path).getroot()
        assert root.tag.endswith('svg')
        for node in root.iter():
            assert node.tag.rsplit('}', 1)[-1] not in {'script', 'foreignObject', 'image'}
            assert not any(k.startswith('on') or k.endswith('href') for k in node.attrib)


def test_icons_are_function_specific_and_no_font_glyphs():
    base = ASSETS.parents[2]
    text = (base / 'docs/assets/horizon-dashboard.js').read_text()
    assert 'bookmark-saved' in text and 'function icon(name)' in text
    assert '<use href=' not in text  # Material link rewriting treats href as an HTML property.
    for relative in ('deploy/dashboard_hook.py', 'docs/assets/horizon-dashboard.js'):
        text = (base / relative).read_text()
        assert '⌕' not in text
        assert '>×</button>' not in text
        assert '✓ В отложенном' not in text
