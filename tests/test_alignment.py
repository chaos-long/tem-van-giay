"""Bounded refinement must improve alignment, not invent paper correspondences."""
from dataclasses import replace
import cv2
import numpy as np
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matcher
from matcher import _bounded_alignment, _texture_score, compare, decide, prepare
from test_app import make_paper, scene


def fixture_alignment():
    reference = prepare(scene(make_paper(23)))
    h, w = reference.gray.shape
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    gray = cv2.remap(reference.gray, xx + 1.2, yy - .7, cv2.INTER_LINEAR)
    query = replace(reference, gray=gray)
    target = np.float32([(x, y) for y in range(30, h-20, 25) for x in range(30, w-20, 25)])
    source = target - np.float32([1.2, -.7])
    valid = np.ones((h, w), bool)
    initial = _texture_score(gray, reference.gray, valid)
    return query, reference, source, target, valid, initial


def test_subpixel_refinement_improves_same_texture_and_stays_bounded():
    q, r, source, target, valid, initial = fixture_alignment()
    result, image, mask, info = _bounded_alignment(q, r, np.eye(3), source, target, initial, q.gray, valid)
    assert result['score'] > initial['score'] + .15
    assert result['score'] > .9
    assert info['max_local_shift_px'] <= info['local_shift_limit_px'] == 3
    assert image.shape == r.gray.shape and mask.dtype == bool


@pytest.mark.parametrize('ecc_failure', ['exception', 'runaway'])
def test_bad_ecc_falls_back_without_changing_image(monkeypatch, ecc_failure):
    q, r, _, _, valid, initial = fixture_alignment()
    # No local cell may move when it has no supporting feature anchors.
    anchors = np.float32([[-100, -100], [-90, -100], [-100, -90]])
    def bad_ecc(*args, **kwargs):
        if ecc_failure == 'exception':
            raise cv2.error('No convergence')
        warp = np.eye(3, dtype=np.float32)
        warp[0, 2] = 100
        return 1., warp
    monkeypatch.setattr(cv2, 'findTransformECC', bad_ecc)
    result, image, _, info = _bounded_alignment(q, r, np.eye(3), anchors, anchors, initial, q.gray, valid)
    assert result['score'] == initial['score']
    assert np.array_equal(image, q.gray)
    assert info['method'] == 'ransac' and info['local_cells'] == 0


def test_refinement_does_not_bypass_missing_feature_correspondences(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Refinement must follow strong real feature support')
    monkeypatch.setattr(matcher, '_bounded_alignment', forbidden)
    a = prepare(scene(make_paper(23)))
    other = prepare(scene(make_paper(87)))
    assert decide(other, [('a', a)])['status'] == 'no_match'


def test_shared_layout_with_different_fine_texture_is_rejected():
    # Identical coarse marks provide strong geometry; independent grain must fail NCC.
    rng = np.random.default_rng(45)
    images = []
    for seed in (31, 32):
        grain = np.random.default_rng(seed).normal(0, 45, (500, 700)).astype(np.float32)
        gray = np.clip(190 + cv2.GaussianBlur(grain, (0, 0), .65), 0, 255).astype(np.uint8)
        images.append(gray)
    for _ in range(110):
        x, y = int(rng.integers(65, 630)), int(rng.integers(55, 445))
        for image in images:
            cv2.circle(image, (x, y), 8, 110, -1, cv2.LINE_AA)
    samples = [prepare(scene(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))) for image in images]
    result = compare(*samples)
    assert result is not None and result['inliers'] >= 30 and result['coverage_tiles'] >= 6
    assert result['score'] < .64
    assert decide(samples[0], [('wrong', samples[1])])['status'] == 'no_match'
