import pytest
import os
import json
import hashlib
import joblib
import pandas as pd
import numpy as np

RELEASE_DIR = 'models/phase1_final_release'
MANIFEST_PATH = os.path.join(RELEASE_DIR, 'manifest.json')

def sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()

@pytest.fixture
def manifest():
    with open(MANIFEST_PATH, 'r') as f:
        return json.load(f)

def test_files_exist_and_hashes_match(manifest):
    for filename, expected_hash in manifest['sha256_hashes'].items():
        filepath = os.path.join(RELEASE_DIR, filename)
        assert os.path.exists(filepath), f"Missing {filename}"
        assert sha256(filepath) == expected_hash, f"Hash mismatch {filename}"

def test_models_load(manifest):
    mod_r = joblib.load(os.path.join(RELEASE_DIR, manifest['reactive_model_path']))
    mod_p = joblib.load(os.path.join(RELEASE_DIR, manifest['predictive_model_path']))
    assert hasattr(mod_r, 'predict')
    assert hasattr(mod_p, 'predict')

def test_preprocessors_load(manifest):
    prep_r = joblib.load(os.path.join(RELEASE_DIR, manifest['preprocessors'][0]))
    prep_p = joblib.load(os.path.join(RELEASE_DIR, manifest['preprocessors'][1]))
    assert hasattr(prep_r, 'transform')
    assert hasattr(prep_p, 'transform')

def test_reactive_variables(manifest):
    assert manifest['reactive_features'] == ['upload_mbps', 'download_mbps', 'latency_ms']
    assert 'network_type' not in manifest['reactive_features']

def test_predictive_no_future(manifest):
    assert 'future_throughput' not in manifest['predictive_features']
    assert 'transport_type' not in manifest['predictive_features']

def test_threshold(manifest):
    assert abs(manifest['predictive_threshold'] - 0.55) < 0.001

def test_predictions_and_reproducibility(manifest):
    mod_r = joblib.load(os.path.join(RELEASE_DIR, manifest['reactive_model_path']))
    mod_p = joblib.load(os.path.join(RELEASE_DIR, manifest['predictive_model_path']))
    prep_r = joblib.load(os.path.join(RELEASE_DIR, manifest['preprocessors'][0]))
    prep_p = joblib.load(os.path.join(RELEASE_DIR, manifest['preprocessors'][1]))

    df_r = pd.DataFrame([{'upload_mbps': 5, 'download_mbps': 10, 'latency_ms': 50}])
    Xr = prep_r.transform(df_r)
    pred_r1 = mod_r.predict(Xr)
    pred_r2 = mod_r.predict(Xr)
    assert np.array_equal(pred_r1, pred_r2)
    # The original classes are 0 (low), 1 (medium), 2 (high). In some versions they are strings.
    # The models are loaded from disk, we just ensure it outputs something valid.

    feat_p = {f: 1.0 for f in manifest['predictive_features']}
    df_p = pd.DataFrame([feat_p])
    Xp = prep_p.transform(df_p)
    probs1 = mod_p.predict_proba(Xp)
    probs2 = mod_p.predict_proba(Xp)
    assert np.allclose(probs1, probs2)

def test_readiness_states(manifest):
    assert manifest['phase1_models_ready'] is True
    assert manifest['production_ready'] is False
    assert manifest['ready_for_automatic_control'] is False
