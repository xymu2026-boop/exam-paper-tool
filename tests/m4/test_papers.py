"""Integration tests for ``/api/papers/*`` routes."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from src.m4_web_backend import config as m4_config


def _upload(client, *, filename='paper.jpg', content_type='image/jpeg',
            data=None, child_id='K1', subject='数学',
            paper_type='作业', title='单元1'):
    files = {'file': (filename, data or b'\x00' * 32, content_type)}
    form = {
        'child_id': child_id,
        'subject': subject,
        'paper_type': paper_type,
    }
    if title is not None:
        form['title'] = title
    return client.post('/api/papers/upload', files=files, data=form)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def test_upload_jpeg_success(client, sample_jpeg):
    r = _upload(client, filename='a.jpg', data=sample_jpeg)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['paper_id'] >= 1
    assert body['status'] == 'pending'

    # File should be on disk under the overridden ORIGINALS_DIR.
    matches = list(m4_config.ORIGINALS_DIR.rglob('*.jpg'))
    assert matches, 'uploaded JPEG was not persisted'
    # Sanity-check that the matching file lives in K1/数学.
    assert any('K1' in str(p) and '数学' in str(p) for p in matches)


def test_upload_png_success(client, sample_png):
    r = _upload(client, filename='a.png', content_type='image/png',
                data=sample_png)
    assert r.status_code == 200, r.text
    pngs = list(m4_config.ORIGINALS_DIR.rglob('*.png'))
    assert pngs


def test_upload_rejects_unsupported_extension(client):
    r = _upload(client, filename='evil.gif', content_type='image/gif',
                data=b'GIF89a fake')
    assert r.status_code == 400
    assert 'Unsupported' in r.json()['error']


def test_upload_rejects_oversized_file(client, monkeypatch):
    """A file larger than ``MAX_UPLOAD_SIZE`` must be refused."""
    monkeypatch.setattr(m4_config, 'MAX_UPLOAD_SIZE', 1024)  # 1KB cap
    big = b'A' * (4 * 1024)
    r = _upload(client, filename='big.jpg', data=big)
    assert r.status_code == 400
    assert 'too large' in r.json()['error'].lower()


def test_upload_rejects_invalid_child_id(client, sample_jpeg):
    r = _upload(client, child_id='K9', data=sample_jpeg)
    assert r.status_code == 400


def test_upload_rejects_invalid_subject(client, sample_jpeg):
    r = _upload(client, subject='物理', data=sample_jpeg)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------

def test_process_paper_success(client, sample_jpeg, fake_m1):
    up = _upload(client, data=sample_jpeg)
    assert up.status_code == 200
    paper_id = up.json()['paper_id']

    r = client.post(f'/api/papers/{paper_id}/process')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['status'] == 'processed'
    assert body['quality_score'] == pytest.approx(0.75)
    assert 'warnings' in body

    # Confirm M1 was called with the right paths.
    assert fake_m1['last_call'] is not None
    input_path, output_dir = fake_m1['last_call']
    assert Path(input_path).exists()
    assert Path(output_dir).exists()


def test_process_paper_m1_failure(client, sample_jpeg, fake_m1):
    up = _upload(client, data=sample_jpeg)
    paper_id = up.json()['paper_id']

    fake_m1['mode'] = 'failure'
    r = client.post(f'/api/papers/{paper_id}/process')
    assert r.status_code == 500
    assert 'simulated failure' in r.json()['error']

    # DB row should now reflect the failure.
    detail = client.get(f'/api/papers/{paper_id}').json()
    assert detail['status'] == 'failed'
    assert detail['error_message'] == 'simulated failure'


def test_process_paper_not_found(client):
    r = client.post('/api/papers/99999/process')
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------

def test_list_papers_empty(client):
    r = client.get('/api/papers')
    assert r.status_code == 200
    body = r.json()
    assert body['papers'] == []
    assert body['total'] == 0


def test_list_papers_after_uploads(client, sample_jpeg):
    _upload(client, child_id='K1', subject='数学', data=sample_jpeg)
    _upload(client, child_id='K2', subject='语文', data=sample_jpeg)
    _upload(client, child_id='K1', subject='数学', data=sample_jpeg)

    r = client.get('/api/papers')
    assert r.status_code == 200
    body = r.json()
    assert body['total'] == 3
    assert len(body['papers']) == 3

    # Filter by child_id.
    r2 = client.get('/api/papers', params={'child_id': 'K1'})
    assert r2.json()['total'] == 2

    # Filter by subject.
    r3 = client.get('/api/papers', params={'subject': '语文'})
    assert r3.json()['total'] == 1


def test_get_paper_detail(client, sample_jpeg):
    up = _upload(client, data=sample_jpeg)
    paper_id = up.json()['paper_id']

    r = client.get(f'/api/papers/{paper_id}')
    assert r.status_code == 200
    body = r.json()
    assert body['id'] == paper_id
    assert body['child_id'] == 'K1'
    assert body['subject'] == '数学'
    # URL fields should be derived from the on-disk path.
    assert body['original_url'].startswith('/static/data/originals/K1/')


def test_get_paper_not_found(client):
    r = client.get('/api/papers/123456')
    assert r.status_code == 404
    assert r.json()['error'] == 'Paper not found'
