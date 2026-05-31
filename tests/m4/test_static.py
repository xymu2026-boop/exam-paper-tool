"""Static-file mount tests + Swagger UI sanity checks."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_root_serves_frontend_index(client):
    r = client.get('/')
    assert r.status_code == 200
    # The conftest installs an index.html with a known title.
    assert '试卷宝' in r.text


def test_frontend_subpage_served(client):
    r = client.get('/paper.html')
    assert r.status_code == 200
    assert '<title>paper</title>' in r.text


def test_static_data_directory_served(client, sample_jpeg):
    """Files written under data/ must be reachable via /static/data/..."""
    files = {'file': ('p.jpg', sample_jpeg, 'image/jpeg')}
    data = {'child_id': 'K1', 'subject': '数学', 'paper_type': '作业'}
    up = client.post('/api/papers/upload', files=files, data=data)
    assert up.status_code == 200

    detail = client.get(f'/api/papers/{up.json()["paper_id"]}').json()
    url = detail['original_url']
    assert url.startswith('/static/data/originals/K1/')
    r = client.get(url)
    assert r.status_code == 200
    assert r.content[:3] == b'\xff\xd8\xff'  # JPEG magic bytes


def test_swagger_docs_available(client):
    r = client.get('/docs')
    assert r.status_code == 200
    assert 'swagger' in r.text.lower() or 'Swagger' in r.text


def test_openapi_spec_includes_all_routes(client):
    r = client.get('/openapi.json')
    assert r.status_code == 200
    spec = r.json()
    paths = set(spec['paths'].keys())

    expected = {
        '/api/papers/upload',
        '/api/papers/{paper_id}/process',
        '/api/papers',
        '/api/papers/{paper_id}',
        '/api/mistakes',
        '/api/mistakes/{mistake_id}',
        '/api/export/pdf',
        '/api/export/history',
    }
    missing = expected - paths
    assert not missing, f'Missing routes in OpenAPI: {missing}'


def test_app_title_is_chinese(client):
    spec = client.get('/openapi.json').json()
    assert spec['info']['title'] == '试卷宝 API'


def test_cors_allows_arbitrary_origin(client):
    """LAN deployment: any Origin must be accepted."""
    r = client.get('/api/papers', headers={'Origin': 'http://192.168.1.42'})
    assert r.status_code == 200
    # Starlette's CORSMiddleware echoes the origin (or '*') depending on
    # credentials.  Either form is acceptable.
    aco = r.headers.get('access-control-allow-origin')
    assert aco in ('*', 'http://192.168.1.42'), aco
