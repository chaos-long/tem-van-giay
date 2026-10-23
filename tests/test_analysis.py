"""Check that algorithm illustrations show real processing, without leaking references."""
import base64
import json
from pathlib import Path
import sys
import uuid

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from matcher import prepare, texture
from server import create_app
from test_app import make_paper, payload, register, scene


@pytest.fixture
def analysis_client(tmp_path, monkeypatch):
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    monkeypatch.delenv('SUPABASE_SERVICE_KEY', raising=False)
    app = create_app(tmp_path, admin_token='test-key')
    app.testing = True
    return app.test_client()


def decode_stage(stage):
    assert stage['title'] and stage['description']
    raw = base64.b64decode(stage['image'].split(',')[-1], validate=True)
    assert raw.startswith(b'\x89PNG\r\n\x1a\n')
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    assert image is not None and image.size
    assert image.shape[:2] == (stage['height'], stage['width'])
    return image


def stages_of(analysis):
    assert analysis['version'] == 1
    stages = {stage['id']: stage for stage in analysis['stages']}
    assert len(stages) == len(analysis['stages']), 'Stage ids must be unique.'
    assert {'rectified', 'gray', 'texture', 'features'} <= stages.keys()
    for stage in stages.values():
        decode_stage(stage)
    return stages


def assert_query_only(analysis, registered_id=None):
    stages = stages_of(analysis)
    assert not {'correspondences', 'aligned', 'difference', 'reference'} & stages.keys()
    forbidden = {'product', 'product_id', 'reference_id', 'reference_image',
                 'candidate', 'candidates', 'match'}

    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden & value.keys(), 'Unmatched analysis revealed a reference.'
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(analysis)
    serialized = json.dumps(analysis, ensure_ascii=False)
    assert 'PRIVATE-REFERENCE-CODE' not in serialized
    assert 'PRIVATE-REFERENCE-NAME' not in serialized
    if registered_id:
        assert registered_id not in serialized


@pytest.mark.parametrize('endpoint', ['/api/inspect', '/api/match'])
@pytest.mark.parametrize('explain', [None, False])
def test_analysis_is_opt_in(analysis_client, endpoint, explain):
    data = payload(scene(make_paper(12)))
    if explain is not None:
        data['explain'] = explain
    response = analysis_client.post(endpoint, json=data)
    assert response.status_code == 200, response.json
    assert 'analysis' not in response.json


def test_inspect_visuals_are_actual_rectified_pixels(analysis_client):
    image = scene(make_paper(12), changed=True)
    sample = prepare(image)
    response = analysis_client.post('/api/inspect', json={**payload(image), 'explain': True})
    assert response.status_code == 200, response.json
    analysis = response.json['analysis']
    stages = stages_of(analysis)
    assert analysis['eligible'] is True
    assert analysis['quality'] == sample.quality
    assert analysis['quality_message'] is None or isinstance(analysis['quality_message'], str)
    assert (stages['rectified']['width'], stages['rectified']['height']) == (640, 448)
    for stage_id in ['gray', 'texture', 'features']:
        assert (stages[stage_id]['width'], stages[stage_id]['height']) == (512, 358)
    np.testing.assert_array_equal(decode_stage(stages['rectified']), sample.image)
    np.testing.assert_array_equal(decode_stage(stages['gray']), sample.gray)
    displayed = decode_stage(stages['texture'])
    if displayed.ndim == 3:
        displayed = cv2.cvtColor(displayed, cv2.COLOR_BGR2GRAY)
    # Display contrast may be stretched, but it must preserve the measured bandpass.
    correlation = np.corrcoef(texture(sample.gray).ravel(), displayed.ravel())[0, 1]
    assert abs(correlation) > .97
    assert displayed.std() > 1


@pytest.mark.parametrize('endpoint', ['/api/inspect', '/api/match'])
def test_blank_paper_has_real_failure_analysis_without_invented_features(analysis_client, endpoint):
    blank = scene(np.full((500, 700, 3), 225, np.uint8))
    response = analysis_client.post(endpoint, json={**payload(blank), 'explain': True})
    assert response.status_code == 422, response.json
    assert response.json['status'] == 'quality_error'
    analysis = response.json['analysis']
    assert_query_only(analysis)
    assert analysis['eligible'] is False
    assert analysis['quality']['feature_count'] == 0
    assert analysis['quality_message']
    gray = decode_stage(stages_of(analysis)['gray'])
    assert gray.std() == 0


def test_match_visuals_agree_with_decision_and_stay_bounded(analysis_client):
    registered = register(analysis_client, scene(make_paper(12)))
    assert registered.status_code == 201, registered.json
    response = analysis_client.post('/api/match', json={
        **payload(scene(make_paper(12), changed=True)), 'explain': True})
    assert response.status_code == 200, response.json
    result = response.json
    assert result['status'] == 'matched'
    analysis = result['analysis']
    stages = stages_of(analysis)
    assert {'correspondences', 'aligned', 'difference'} <= stages.keys()
    assert analysis['decision']['status'] == 'matched'
    assert analysis['decision']['score'] == result['match']['score']
    assert analysis['decision']['inliers'] == result['match']['inliers']
    assert analysis['decision']['coverage_tiles'] == result['match']['coverage_tiles']
    assert analysis['decision']['inliers'] >= 14
    assert analysis['decision']['coverage_tiles'] >= 4
    assert analysis['decision']['threshold'] == .64
    assert analysis['decision']['margin'] == .08
    assert stages['correspondences']['width'] == 1024
    assert stages['correspondences']['height'] == 358
    # Like correspondences, this panel places the aligned query and reference
    # beside each other so the user can inspect the same regions directly.
    assert (stages['aligned']['width'], stages['aligned']['height']) == (1024, 358)
    assert (stages['difference']['width'], stages['difference']['height']) == (512, 358)
    assert len(response.data) < 3_000_000, 'Opt-in visuals should be practical on mobile Wi-Fi.'


def test_empty_database_analysis_shows_only_query(analysis_client):
    response = analysis_client.post('/api/match', json={
        **payload(scene(make_paper(12))), 'explain': True})
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'empty'
    analysis = response.json['analysis']
    assert analysis['decision']['status'] == 'empty'
    assert_query_only(analysis)


def test_unknown_paper_does_not_reveal_reference(analysis_client):
    registered = register(analysis_client, scene(make_paper(12)),
                          code='PRIVATE-REFERENCE-CODE', name='PRIVATE-REFERENCE-NAME')
    assert registered.status_code == 201, registered.json
    registered_id = registered.json['product']['id']
    response = analysis_client.post('/api/match', json={
        **payload(scene(make_paper(72), changed=True)), 'explain': True})
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'no_match'
    assert 'product' not in response.json
    assert response.json['analysis']['decision']['status'] == 'no_match'
    assert_query_only(response.json['analysis'], registered_id)


def test_ambiguous_match_does_not_expose_either_reference(analysis_client):
    registered = register(analysis_client, scene(make_paper(12)),
                          code='PRIVATE-REFERENCE-CODE', name='PRIVATE-REFERENCE-NAME')
    assert registered.status_code == 201, registered.json
    db = analysis_client.application.db
    row = db.rows()[0]
    second_id = str(uuid.uuid4())
    # Deliberately seed a duplicate through the DB to exercise the ambiguity gate;
    # normal admin registration correctly rejects this duplicate image.
    db.add(second_id, {'product_name': 'Second private reference', 'product_code': 'PRIVATE-2'},
           row['image'], json.loads(row['quality']))
    response = analysis_client.post('/api/match', json={
        **payload(scene(make_paper(12))), 'explain': True})
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'ambiguous'
    assert 'product' not in response.json
    assert response.json['analysis']['decision']['status'] == 'ambiguous'
    assert_query_only(response.json['analysis'], registered.json['product']['id'])
    assert second_id not in json.dumps(response.json['analysis'])
