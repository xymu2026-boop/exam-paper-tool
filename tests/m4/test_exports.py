"""Integration tests for ``/api/export/*`` routes."""

from __future__ import annotations

from pathlib import Path

import pytest


def _upload_process_crop(client, sample_jpeg, child_id='K1', subject='数学'):
    """Helper: upload + process + create one mistake; return mistake_id."""
    files = {'file': ('p.jpg', sample_jpeg, 'image/jpeg')}
    data = {'child_id': child_id, 'subject': subject, 'paper_type': '作业'}
    pid = client.post(
        '/api/papers/upload', files=files, data=data
    ).json()['paper_id']
    client.post(f'/api/papers/{pid}/process')
    mid = client.post(
        '/api/mistakes',
        json={
            'paper_id': pid,
            'crop_x': 0,
            'crop_y': 0,
            'crop_width': 50,
            'crop_height': 50,
        },
    ).json()['mistake_id']
    return mid


# ---------------------------------------------------------------------------
# Export PDF
# ---------------------------------------------------------------------------

def test_export_pdf_success(client, sample_jpeg, fake_m5):
    mid1 = _upload_process_crop(client, sample_jpeg)
    mid2 = _upload_process_crop(client, sample_jpeg)

    r = client.post(
        '/api/export/pdf',
        json={
            'child_id': 'K1',
            'mistake_ids': [mid1, mid2],
            'layout': 'one_per_page',
            'title': 'K1 数学错题',
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['export_id'] >= 1
    assert body['pdf_url'].startswith('/static/data/exports/')
    assert body['pdf_url'].endswith(f'{body["export_id"]}.pdf')

    # Confirm M5 was invoked with the correct paths and config.
    image_paths, output_path, cfg = fake_m5['last_call']
    assert len(image_paths) == 2
    assert all(Path(p).is_file() for p in image_paths)
    assert output_path.endswith(f'{body["export_id"]}.pdf')
    assert cfg.layout == 'one_per_page'
    assert cfg.title == 'K1 数学错题'


def test_export_pdf_default_layout(client, sample_jpeg, fake_m5):
    mid = _upload_process_crop(client, sample_jpeg)
    r = client.post(
        '/api/export/pdf',
        json={'child_id': 'K1', 'mistake_ids': [mid]},
    )
    assert r.status_code == 200
    _, _, cfg = fake_m5['last_call']
    assert cfg.layout == 'one_per_page'


def test_export_pdf_invalid_layout(client, sample_jpeg):
    mid = _upload_process_crop(client, sample_jpeg)
    r = client.post(
        '/api/export/pdf',
        json={
            'child_id': 'K1',
            'mistake_ids': [mid],
            'layout': 'spiral',
        },
    )
    assert r.status_code == 400


def test_export_pdf_empty_mistake_ids(client):
    r = client.post(
        '/api/export/pdf',
        json={'child_id': 'K1', 'mistake_ids': []},
    )
    assert r.status_code == 400


def test_export_pdf_unknown_mistake(client):
    r = client.post(
        '/api/export/pdf',
        json={'child_id': 'K1', 'mistake_ids': [9999]},
    )
    assert r.status_code == 404


def test_export_pdf_child_id_mismatch(client, sample_jpeg):
    mid = _upload_process_crop(client, sample_jpeg, child_id='K1')
    r = client.post(
        '/api/export/pdf',
        json={'child_id': 'K2', 'mistake_ids': [mid]},
    )
    assert r.status_code == 400


def test_export_pdf_m5_failure(client, sample_jpeg, fake_m5):
    mid = _upload_process_crop(client, sample_jpeg)
    fake_m5['mode'] = 'failure'
    r = client.post(
        '/api/export/pdf',
        json={'child_id': 'K1', 'mistake_ids': [mid]},
    )
    assert r.status_code == 500


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def test_export_history(client, sample_jpeg, fake_m5):
    mid1 = _upload_process_crop(client, sample_jpeg)
    mid2 = _upload_process_crop(client, sample_jpeg)
    client.post(
        '/api/export/pdf',
        json={'child_id': 'K1', 'mistake_ids': [mid1]},
    )
    client.post(
        '/api/export/pdf',
        json={'child_id': 'K1', 'mistake_ids': [mid1, mid2]},
    )

    r = client.get('/api/export/history')
    assert r.status_code == 200
    body = r.json()
    assert len(body['exports']) == 2
    # Order is most-recent-first; mistake_ids should be a list[int].
    assert isinstance(body['exports'][0]['mistake_ids'], list)
    assert all(isinstance(i, int) for i in body['exports'][0]['mistake_ids'])
    assert all(e['pdf_url'].startswith('/static/data/exports/')
               for e in body['exports'])


def test_export_history_filter_by_child(client, sample_jpeg, fake_m5):
    mid_k1 = _upload_process_crop(client, sample_jpeg, child_id='K1')
    mid_k2 = _upload_process_crop(client, sample_jpeg, child_id='K2',
                                  subject='语文')
    client.post('/api/export/pdf',
                json={'child_id': 'K1', 'mistake_ids': [mid_k1]})
    client.post('/api/export/pdf',
                json={'child_id': 'K2', 'mistake_ids': [mid_k2]})

    r = client.get('/api/export/history', params={'child_id': 'K1'})
    assert r.status_code == 200
    items = r.json()['exports']
    assert len(items) == 1
    assert items[0]['child_id'] == 'K1'
