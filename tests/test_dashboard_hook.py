"""Native hook regression tests with scratch published pages only."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_dashboard import BODY


@pytest.fixture
def hook():
    path = Path(__file__).resolve().parents[1] / 'deploy' / 'dashboard_hook.py'
    spec = importlib.util.spec_from_file_location('dashboard_hook_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Files:
    def __init__(self, body=BODY):
        self.files = [SimpleNamespace(src_uri='digest/2026-09-30-ru/tech-news-1.md', name='tech-news-1', content_string=body),
                      SimpleNamespace(src_uri='digest/2026-09-30-ru/index.md', name='index', content_string='## Технологии\n<ul><li><a href="tech-news-1/">Article</a></li></ul>')]
    def documentation_pages(self):
        return self.files


def test_build_catalog_and_no_js_cards(hook,tmp_path):
    hook.on_files(Files(),SimpleNamespace())
    page=SimpleNamespace(file=SimpleNamespace(src_uri='index.md'),meta={})
    output=hook.on_page_markdown('',page,None,None)
    assert 'href="digest/2026-09-30-ru/tech-news-1/"' in output
    assert 'Демонстрацион' not in output
    assert page.meta['dashboard_home']
    hook.on_post_build(SimpleNamespace(site_dir=str(tmp_path)))
    data=json.loads((tmp_path/'assets/dashboard/catalog.json').read_text())
    assert len(data['items'])==1
    assert data['items'][0]['profile_name']=='Технологии'
    assert data['items'][0]['audio_ready'] is False


def test_audio_refresh_rebuild(hook):
    hook.on_files(Files(),None)
    assert not hook.PUBLIC['items'][0]['audio_ready']
    hook.on_files(Files(BODY+'<audio class="hz-narration" src="https://example.com/pass.opus"></audio>'),None)
    assert hook.PUBLIC['items'][0]['audio_ready']


def test_bad_published_page_blocks_partial_catalog(hook):
    with pytest.raises(ValueError,match='coverage incomplete'):
        hook.on_files(Files('unsupported format'),None)


def test_clean_clone_truthful_empty_state(hook):
    files=Files();files.files=[]
    hook.on_files(files,None)
    assert hook.PUBLIC['items']==[]
    assert 'Пока нет опубликованных материалов' in hook.homepage()


def test_article_snapshot_cannot_close_script(hook):
    body=BODY.replace('Реальная статья','Bad </script><script>alert(1)</script>')
    hook.on_files(Files(body),None)
    page=SimpleNamespace(file=SimpleNamespace(url='digest/2026-09-30-ru/tech-news-1/'))
    output=hook.on_page_content('<p>body</p>',page,None,None)
    assert '<script' not in output
    assert 'data-snapshot="{&quot;' in output
    import html, re
    snapshot = re.search(r'data-snapshot="([^"]+)"', output).group(1)
    parsed = json.loads(html.unescape(snapshot))
    assert parsed['id'] == '2026-09-30-ru-tech-news-1'
    assert '<script>alert' not in output
    assert output.endswith('<p>body</p>')


def test_duplicate_identity_rejected(hook):
    files=Files();files.files.append(files.files[0])
    with pytest.raises(ValueError,match='duplicate'):
        hook.on_files(files,None)
