import os
import json
import hashlib
import joblib
import pandas as pd
import numpy as np

def sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()

def verify():
    print("--- Verificando Phase 1 Release ---")
    release_dir = 'models/phase1_final_release'
    manifest_path = os.path.join(release_dir, 'manifest.json')
    
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
        
    print("Verificando hashes...")
    for filename, expected_hash in manifest['sha256_hashes'].items():
        filepath = os.path.join(release_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Missing artifact: {filepath}")
        actual_hash = sha256(filepath)
        if actual_hash != expected_hash:
            raise ValueError(f"Hash mismatch for {filename}")
            
    print("Cargando modelos desde el directorio release...")
    mod_r = joblib.load(os.path.join(release_dir, manifest['reactive_model_path']))
    mod_p = joblib.load(os.path.join(release_dir, manifest['predictive_model_path']))
    prep_r = joblib.load(os.path.join(release_dir, manifest['preprocessors'][0]))
    prep_p = joblib.load(os.path.join(release_dir, manifest['preprocessors'][1]))
    
    # Comprobar inputs
    assert manifest['reactive_features'] == ['upload_mbps', 'download_mbps', 'latency_ms'], "Variables reactivas incorrectas"
    
    # Inferencia Tecnica
    print("Verificando inferencia y reproducibilidad...")
    df_r = pd.DataFrame([{'upload_mbps': 5, 'download_mbps': 10, 'latency_ms': 50}])
    Xr = prep_r.transform(df_r)
    pred_r1 = mod_r.predict(Xr)
    pred_r2 = mod_r.predict(Xr)
    assert np.array_equal(pred_r1, pred_r2), "Reactivo no reproducible"
    
    feat_p = {f: 1.0 for f in manifest['predictive_features']}
    df_p = pd.DataFrame([feat_p])
    Xp = prep_p.transform(df_p)
    probs1 = mod_p.predict_proba(Xp)
    probs2 = mod_p.predict_proba(Xp)
    assert np.allclose(probs1, probs2), "Predictivo no reproducible"
    
    threshold = manifest['predictive_threshold']
    assert abs(threshold - 0.55) < 0.001, f"Umbral incorrecto: {threshold}"
    
    print("Estados finales:")
    assert manifest['phase1_models_ready'], "phase1_models_ready is False"
    assert not manifest['production_ready'], "production_ready is True!"
    assert not manifest['ready_for_automatic_control'], "ready_for_automatic_control is True!"
    
    print("\nPHASE 1 RELEASE VERIFIED")

if __name__ == '__main__':
    verify()
