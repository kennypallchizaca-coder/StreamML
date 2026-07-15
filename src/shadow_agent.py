import json
import joblib
import pandas as pd
from pathlib import Path
from src.telemetry_buffer import TelemetryBuffer
from src.feature_builder_v2 import build_predictive_features

class ShadowAgent:
    def __init__(self, config_path="config/shadow_agent_config.json"):
        self.config_path = Path(config_path)
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            
        self.release_dir = Path(self.config['release_directory'])
        manifest_path = Path(self.config['manifest_path'])
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            self.manifest = json.load(f)
            
        self._load_models()
        
        self.buffer = TelemetryBuffer(
            lookback_seconds=self.config.get('predictive_lookback_seconds', 120),
            min_coverage=self.config.get('minimum_buffer_coverage', 0.8)
        )
        
        self.threshold = self.manifest.get('predictive_threshold', 0.55)
        self.default_profile = self.config.get('default_current_profile', 'medium')
        
        # Mapeo Profile
        self.profile_map = {'low': 1, 'medium': 2, 'high': 3}
        
    def _load_models(self):
        try:
            self.reactive_model = joblib.load(self.release_dir / self.manifest['reactive_model_path'])
            self.predictive_model = joblib.load(self.release_dir / self.manifest['predictive_model_path'])
            self.reactive_prep = joblib.load(self.release_dir / self.manifest['preprocessors'][0])
            self.predictive_prep = joblib.load(self.release_dir / self.manifest['preprocessors'][1])
        except Exception as e:
            raise RuntimeError(f"Error cargando modelos: {e}")

    def resolve_downgrade_class_index(self, model) -> int:
        classes = list(model.classes_)
        if 'downgrade_needed' in classes:
            return classes.index('downgrade_needed')
        elif 1 in classes:
            return classes.index(1)
        else:
            raise ValueError(f"Clase positiva no encontrada en model.classes_: {classes}")
            
            
    def process_sample(self, row: dict) -> dict:
        result = row.copy()
        result['action_applied'] = 'none'
        result['inference_status'] = 'invalid_sample'
        result['reactive_prediction'] = None
        result['predictive_prediction'] = None
        result['degradation_probability'] = None
        result['recommendation'] = None
        
        # Calcular observed_throughput_mbps
        bitrate = result.get('bitrate_kbps')
        upload = result.get('upload_traffic_mbps')
        
        try:
            bitrate_val = float(bitrate) if bitrate is not None and bitrate != '' else -1
        except (ValueError, TypeError):
            bitrate_val = -1
            
        try:
            upload_val = float(upload) if upload is not None and upload != '' else -1
        except (ValueError, TypeError):
            upload_val = -1
            
        if bitrate_val > 0:
            result['obs_bitrate_mbps'] = bitrate_val / 1000.0
            result['observed_throughput_mbps'] = bitrate_val / 1000.0 # Legacy fallback para tests
            result['predictive_input_source'] = 'obs_bitrate'
        else:
            result['obs_bitrate_mbps'] = None
            
        if upload_val > 0:
            result['network_traffic_upload_mbps'] = upload_val
            if 'observed_throughput_mbps' not in result or result['observed_throughput_mbps'] is None:
                result['observed_throughput_mbps'] = upload_val
                result['predictive_input_source'] = 'upload_traffic'
        else:
            result['network_traffic_upload_mbps'] = None

        if 'observed_throughput_mbps' not in result:
            result['observed_throughput_mbps'] = None

        if result.get('observed_throughput_mbps') is None:
            result['predictive_input_source'] = 'unavailable'

        # El dataset predictivo usa throughput de descarga (Ghent) como proxy de capacidad disponible.
        # Ninguna de nuestras fuentes en runtime (obs_bitrate, upload_traffic) representa capacidad
        # disponible (capacity). Por lo tanto, no tenemos una fuente compatible.
        if 'predictive_throughput_mbps' not in result:
            result['predictive_throughput_mbps'] = None
            result['predictive_input_source'] = 'unavailable'

        # Añadir al buffer antes de validar métricas reactivas
        buffer_added = self.buffer.add_sample(result)
        
        coverage, count = self.buffer.get_coverage()
        result['buffer_measurements'] = count
        result['buffer_coverage'] = round(coverage, 3)

        if not buffer_added:
            return result
        
        # Validar métricas reactivas
        req_reactive = self.manifest['reactive_features']
        can_run_reactive = True
        try:
            for feat in req_reactive:
                if result.get(feat) is None or result[feat] == '' or float(result[feat]) < 0:
                    can_run_reactive = False
                    break
        except (ValueError, TypeError):
            can_run_reactive = False

        if can_run_reactive:
            try:
                df_react = pd.DataFrame([{f: result[f] for f in req_reactive}])
                X_react = self.reactive_prep.transform(df_react)
                pred_idx = self.reactive_model.predict(X_react)[0]
                result['reactive_prediction'] = str(pred_idx)
                result['inference_status'] = 'reactive_only'
            except Exception:
                result['inference_status'] = 'error'
                can_run_reactive = False
        else:
            result['inference_status'] = 'insufficient_network_capacity'
        
        if not self.buffer.is_ready():
            result['recommendation'] = 'insufficient_buffer'
            return result
            
        # Inferencia predictiva
        # Si no existe una fuente compatible con el throughput de entrenamiento:
        if result.get('predictive_throughput_mbps') is None:
            result['predictive_prediction'] = None
            result['degradation_probability'] = None
            result['recommendation'] = 'incompatible_input'
            result['inference_status'] = 'incompatible_feature_source'
            return result
            
        try:
            df_buffer = self.buffer.get_dataframe()
            
            # Usar predictive_throughput_mbps como throughput_mbps
            df_buffer['throughput_mbps'] = df_buffer['predictive_throughput_mbps']
            
            # Usar default_profile
            curr_prof_int = self.profile_map.get(self.default_profile, 2)
            
            # Construir variables
            df_pred = build_predictive_features(df_buffer, current_profile=curr_prof_int, configuration=self.manifest)
            
            # Predecir
            X_pred = self.predictive_prep.transform(df_pred)
            probs = self.predictive_model.predict_proba(X_pred)[0]
            
            prob_idx = self.resolve_downgrade_class_index(self.predictive_model)
            
            if len(probs) <= prob_idx:
                raise ValueError(f"predict_proba shape inválido. Índices: {len(probs)}, esperado al menos: {prob_idx + 1}")
                
            prob_degrade = probs[prob_idx]
            
            import numpy as np
            if not np.isfinite(prob_degrade):
                raise ValueError("Probabilidad no es finita")
            if not (0.0 <= prob_degrade <= 1.0):
                raise ValueError("Probabilidad fuera de rango [0, 1]")
                
            pred_class = 'downgrade_needed' if prob_degrade >= self.threshold else 'maintain'
            
            result['predictive_prediction'] = pred_class
            result['degradation_probability'] = float(prob_degrade) # No redondear internamente
            
            if pred_class == 'downgrade_needed':
                result['recommendation'] = 'downgrade'
            else:
                result['recommendation'] = 'maintain'
                
            result['inference_status'] = 'full_inference'
            
        except Exception as e:
            result['degradation_probability'] = None
            result['predictive_prediction'] = None
            result['recommendation'] = 'inference_error'
            result['inference_status'] = 'error'
            
        return result
