"""Integration tests for ``/api/mistakes/*`` routes."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.m4_web_backend import config as m4_config


def _upload_and_process(client, sample_jpeg, child_id='K1', subject='数学'):
    files = {'file': ('p.jpg', sample_jpeg, 'image/jpeg')}
    data = {'child_id': child_id, 'subject': subject, 'paper_type': '作业'}
    up = client.post('/api/papers/upload', files=files, data=data)
    assert up.status_code == 200, up.text
    pid = up.json()['paper_id']
    pr = client.post(f'/api/papers/{pid}/process')
    assert pr.status_code == 200, pr.text
    return pid


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_mistake_success(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)

    body = {
        'paper_id': pid,
        'crop_x': 10,
        'crop_y': 20,
        'crop_width': 100,
        'crop_height': 80,
        'note': 'tricky',
        'error_type': '粗心',
    }
    r = client.post('/api/mistakes', json=body)
    assert r.status_code == 200, r.text
    mid = r.json()['mistake_id']
    assert mid >= 1

    # Both cropped image files should exist on disk.
    out_dir = m4_config.MISTAKES_DIR / str(mid)
    assert (out_dir / 'original.jpg').is_file()
    assert (out_dir / 'clean.jpg').is_file()


def test_create_mistake_paper_not_found(client):
    r = client.post(
        '/api/mistakes',
        json={
            'paper_id': 12345,
            'crop_x': 0,
            'crop_y': 0,
            'crop_width': 10,
            'crop_height': 10,
        },
    )
    assert r.status_code == 404


def test_create_mistake_unprocessed_paper(client, sample_jpeg):
    """A paper still in ``pending`` status has no images to crop from."""
    files = {'file': ('p.jpg', sample_jpeg, 'image/jpeg')}
    data = {'child_id': 'K1', 'subject': '数学', 'paper_type': '作业'}
    up = client.post('/api/papers/upload', files=files, data=data)
    pid = up.json()['paper_id']

    r = client.post(
        '/api/mistakes',
        json={
            'paper_id': pid,
            'crop_x': 0,
            'crop_y': 0,
            'crop_width': 10,
            'crop_height': 10,
        },
    )
    assert r.status_code == 400


def test_create_mistake_rejects_invalid_dimensions(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    r = client.post(
        '/api/mistakes',
        json={
            'paper_id': pid,
            'crop_x': 0,
            'crop_y': 0,
            'crop_width': 0,  # invalid
            'crop_height': 10,
        },
    )
    assert r.status_code == 400


def test_create_mistake_rejects_invalid_error_type(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    r = client.post(
        '/api/mistakes',
        json={
            'paper_id': pid,
            'crop_x': 0,
            'crop_y': 0,
            'crop_width': 10,
            'crop_height': 10,
            'error_type': 'BOGUS',
        },
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_mistakes(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    for _ in range(3):
        client.post(
            '/api/mistakes',
            json={
                'paper_id': pid,
                'crop_x': 0,
                'crop_y': 0,
                'crop_width': 50,
                'crop_height': 50,
            },
        )

    r = client.get('/api/mistakes')
    assert r.status_code == 200
    body = r.json()
    assert body['total'] == 3
    assert len(body['mistakes']) == 3

    # Filter by paper_id.
    r2 = client.get('/api/mistakes', params={'paper_id': pid})
    assert r2.json()['total'] == 3

    # URL fields should be populated.
    assert all(m['mistake_image_url'] is not None for m in body['mistakes'])


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_mistake_status(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    mid = client.post(
        '/api/mistakes',
        json={'paper_id': pid, 'crop_x': 0, 'crop_y': 0,
              'crop_width': 10, 'crop_height': 10},
    ).json()['mistake_id']

    r = client.patch(
        f'/api/mistakes/{mid}',
        json={'status': 'printed'},
    )
    assert r.status_code == 200, r.text
    assert r.json()['success'] is True

    listed = client.get('/api/mistakes', params={'status': 'printed'}).json()
    assert listed['total'] == 1


def test_update_mistake_note_and_error_type(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    mid = client.post(
        '/api/mistakes',
        json={'paper_id': pid, 'crop_x': 0, 'crop_y': 0,
              'crop_width': 10, 'crop_height': 10},
    ).json()['mistake_id']

    r = client.patch(
        f'/api/mistakes/{mid}',
        json={'note': 'remember the carry', 'error_type': '计算错误'},
    )
    assert r.status_code == 200
    # Verify persistence.
    listed = client.get('/api/mistakes').json()['mistakes']
    matched = next(m for m in listed if m['id'] == mid)
    assert matched['note'] == 'remember the carry'
    assert matched['error_type'] == '计算错误'


def test_update_mistake_not_found(client):
    r = client.patch('/api/mistakes/99999', json={'status': 'printed'})
    assert r.status_code == 404


def test_update_mistake_rejects_empty_body(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    mid = client.post(
        '/api/mistakes',
        json={'paper_id': pid, 'crop_x': 0, 'crop_y': 0,
              'crop_width': 10, 'crop_height': 10},
    ).json()['mistake_id']
    r = client.patch(f'/api/mistakes/{mid}', json={})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_mistake(client, sample_jpeg):
    pid = _upload_and_process(client, sample_jpeg)
    mid = client.post(
        '/api/mistakes',
        json={'paper_id': pid, 'crop_x': 0, 'crop_y': 0,
              'crop_width': 10, 'crop_height': 10},
    ).json()['mistake_id']

    r = client.delete(f'/api/mistakes/{mid}')
    assert r.status_code == 200
    assert r.json()['success'] is True

    # Subsequent delete should 404.
    r2 = client.delete(f'/api/mistakes/{mid}')
    assert r2.status_code == 404


def test_delete_mistake_not_found(client):
    r = client.delete('/api/mistakes/99999')
    assert r.status_code == 404
