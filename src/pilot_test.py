import os
import time
import datetime
import uuid
import subprocess
import re
import platform
import psutil
import pandas as pd
import numpy as np
import joblib
import json
import pickle
from pathlib import Path
from collections import deque

def get_ping_latency(target):
    try:
        if platform.system().lower() == "windows":
            output = subprocess.check_output(["ping", "-n", "1", "-w", "1000", target], stderr=subprocess.STDOUT, text=True)
            match = re.search(r'(?:time|tiempo)[=<]\s*(\d+)\s*ms', output, re.IGNORECASE)
            if match:
                return float(match.group(1))
        else:
            output = subprocess.check_output(["ping", "-c", "1", "-W", "1", target], stderr=subprocess.STDOUT, text=True)
            match = re.search(r'time=([\d.]+)\s*ms', output, re.IGNORECASE)
            if match:
                return float(match.group(1))
    except Exception as e:
        pass
    return None

def main():
    duration = 300
    target = "1.1.1.1"
    
    out_dir = Path("data/telemetry/pilot")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    session_id = f"pilot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    csv_path = out_dir / f"{session_id}.csv"
    meta_path = out_dir / f"{session_id}_metadata.json"
    
    # Load Models
    mod_r = joblib.load("models/modelo_reactivo.joblib")
    mod_p = joblib.load("models/modelo_predictivo.joblib")
    prep_r = joblib.load("models/preprocesador_reactivo.joblib")
    prep_p = joblib.load("models/preprocesador_predictivo.joblib")
    
    with open('models/model_metadata.json', 'r') as f:
        meta = json.load(f)
    
    art_r = joblib.load("models/artefactos_reactivo.pkl")
    le_r = art_r["encoder"]
    features_r = art_r["columnas_esperadas"]
    
    art_p = joblib.load("models/artefactos_predictivo.pkl")
    features_p = art_p["columnas_esperadas"]
    umbral_predictivo = art_p["umbral"]
    
    # Network interface
    stats = psutil.net_io_counters(pernic=True)
    interface = list(stats.keys())[0]
    for nic, stat in stats.items():
        if stat.bytes_sent > 0 and stat.bytes_recv > 0 and nic != "lo":
            interface = nic
            break
            
    net_stats_prev = psutil.net_io_counters(pernic=True).get(interface)
    time_prev = time.time()
    
    last_ping_time = 0
    current_latency = None
    latencies = []
    
    # Buffer for predictive
    history = deque(maxlen=120)
    current_profile = "high"
    
    collected_rows = []
    errors = []
    
    start_loop = time.time()
    print("Iniciando prueba piloto de 5 minutos...")
    
    packet_loss_count = 0
    total_probes = 0
    
    try:
        while True:
            current_time = time.time()
            elapsed_total = current_time - start_loop
            if elapsed_total >= duration:
                break
                
            loop_start = time.time()
            
            # 1. Collect Telemetry
            net_stats_curr = psutil.net_io_counters(pernic=True).get(interface)
            time_curr = time.time()
            elapsed_interval = time_curr - time_prev
            if elapsed_interval <= 0: elapsed_interval = 0.001
            
            sent_bytes = net_stats_curr.bytes_sent - net_stats_prev.bytes_sent if net_stats_curr else 0
            recv_bytes = net_stats_curr.bytes_recv - net_stats_prev.bytes_recv if net_stats_curr else 0
            
            upload_mbps = max(0.0, (sent_bytes * 8) / elapsed_interval / 1_000_000)
            download_mbps = max(0.0, (recv_bytes * 8) / elapsed_interval / 1_000_000)
            
            net_stats_prev = net_stats_curr
            time_prev = time_curr
            
            if time_curr - last_ping_time >= 5.0:
                total_probes += 1
                lat = get_ping_latency(target)
                last_ping_time = time_curr
                if lat is not None:
                    current_latency = lat
                    latencies.append(lat)
                else:
                    packet_loss_count += 1
                    current_latency = None
            
            jitter_ms = None
            if len(latencies) > 1:
                jitter_ms = abs(latencies[-1] - latencies[-2])
                
            packet_loss = (packet_loss_count / total_probes * 100) if total_probes > 0 else 0.0
            
            history.append(upload_mbps)
            
            # 2. Run Reactive Inference
            # default mock values for missing hardware telemetry
            row_r = {
                "upload_mbps": upload_mbps,
                "download_mbps": download_mbps,
                "ping_ms": current_latency if current_latency is not None else 500.0,
                "network_type": 1,
                "cat_technology": 1,
                "signal_strength": -80
            }
            df_r = pd.DataFrame([row_r])[features_r]
            try:
                X_r = prep_r.transform(df_r)
                probs_r = mod_r.predict_proba(X_r)[0]
                pred_r_idx = np.argmax(probs_r)
                perfil_recomendado = le_r.inverse_transform([pred_r_idx])[0]
                probabilidad_reactiva = probs_r[pred_r_idx]
            except Exception as e:
                errors.append(f"Error inferencia reactiva: {e}")
                perfil_recomendado = "unknown"
                probabilidad_reactiva = 0.0
            
            # 3. Run Predictive Inference
            arr = np.array(history)
            req_mbps = meta.get("profile_configuration", {}).get(current_profile, 5.0)
            
            row_p = {
                "throughput_mean": np.mean(arr),
                "throughput_median": np.median(arr),
                "throughput_min": np.min(arr),
                "throughput_max": np.max(arr),
                "throughput_std": np.std(arr) if len(arr) > 1 else 0.0,
                "throughput_p10": np.percentile(arr, 10),
                "throughput_p25": np.percentile(arr, 25),
                "throughput_first": arr[0],
                "throughput_last": arr[-1],
                "throughput_change": arr[-1] - arr[0],
                "throughput_slope": np.polyfit(np.arange(len(arr)), arr, 1)[0] if len(arr) > 1 else 0.0,
                "throughput_coefficient_variation": (np.std(arr) / np.mean(arr)) if np.mean(arr) > 0 else 0.0,
                "measurements_count": len(arr),
                "lookback_duration_seconds": len(arr),
                "proportion_below_low": np.mean(arr < meta.get("profile_configuration", {}).get("low", 1.5)),
                "proportion_below_medium": np.mean(arr < meta.get("profile_configuration", {}).get("medium", 3.0)),
                "proportion_below_high": np.mean(arr < req_mbps),
                "transport_type": 1,
                "current_profile": 2 if current_profile == 'high' else 1 if current_profile == 'medium' else 0,
                "required_capacity_mbps": req_mbps
            }
            
            df_p = pd.DataFrame([row_p])[features_p]
            try:
                X_p = prep_p.transform(df_p)
                probs_p = mod_p.predict_proba(X_p)[0]
                prob_downgrade = probs_p[1]
                pred_p = "downgrade_needed" if prob_downgrade >= umbral_predictivo else "maintain"
            except Exception as e:
                errors.append(f"Error inferencia predictiva: {e}")
                pred_p = "unknown"
                prob_downgrade = 0.0
            
            # 4. Agent Simulation logic
            decision_simulada = "maintain"
            if pred_p == "downgrade_needed":
                decision_simulada = "downgrade"
            
            # 5. Build Row
            out_row = {
                "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                "session_id": session_id,
                "upload_mbps": upload_mbps,
                "download_mbps": download_mbps,
                "latency_ms": current_latency,
                "jitter_ms": jitter_ms,
                "packet_loss_percent": packet_loss,
                "fps": None,
                "dropped_frames": None,
                "total_frames": None,
                "bitrate_kbps": None,
                "obs_output_active": None,
                "stream_status": None,
                "perfil_actual": current_profile,
                "perfil_recomendado": perfil_recomendado,
                "probabilidad_reactiva": float(probabilidad_reactiva),
                "prediccion_futura": pred_p,
                "probabilidad_downgrade": float(prob_downgrade),
                "decision_simulada": decision_simulada,
                "accion_real_aplicada": "none",
                "actual_degradation": ""
            }
            collected_rows.append(out_row)
            
            elapsed_work = time.time() - loop_start
            sleep_time = 1.0 - elapsed_work
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        print("Interrumpido por el usuario.")
    except Exception as e:
        errors.append(str(e))
        
    duration_real = time.time() - start_loop
    
    # Save CSV
    df = pd.DataFrame(collected_rows)
    df.to_csv(csv_path, index=False)
    
    missing_by_col = df.isnull().sum().to_dict()
    
    # Metadata
    meta_info = {
        "session_id": session_id,
        "duration_seconds": duration_real,
        "rows_collected": len(df),
        "missing_values_by_column": missing_by_col,
        "average_upload_mbps": df["upload_mbps"].mean(),
        "average_download_mbps": df["download_mbps"].mean(),
        "average_latency_ms": df["latency_ms"].mean(),
        "average_jitter_ms": df["jitter_ms"].mean(),
        "packet_loss_percent": packet_loss,
        "predictions_reactive": df["perfil_recomendado"].value_counts().to_dict(),
        "predictions_predictive": df["prediccion_futura"].value_counts().to_dict(),
        "downgrade_alerts": int((df["prediccion_futura"] == "downgrade_needed").sum()),
        "errors": errors
    }
    
    with open(meta_path, "w") as f:
        json.dump(meta_info, f, indent=4)
        
    print(f"\\n--- RESUMEN DE PRUEBA PILOTO ---")
    print(f"Modelos cargados: Reactivo ({meta['reactive_model_selected']}), Predictivo ({meta['predictive_model_selected']})")
    print(f"Duracion de la prueba: {duration_real:.2f} s")
    print(f"Archivo CSV: {csv_path}")
    print(f"Archivo de metadatos: {meta_path}")
    print(f"Metricas recopiladas (filas): {len(df)}")
    print(f"Velocidad de subida prom: {df['upload_mbps'].mean():.2f} Mbps")
    print(f"Latencia prom: {df['latency_ms'].mean():.2f} ms")
    print(f"Predicciones reactivas: {meta_info['predictions_reactive']}")
    print(f"Predicciones predictivas: {meta_info['predictions_predictive']}")
    print(f"Alertas downgrade_needed: {meta_info['downgrade_alerts']}")
    print(f"Errores encontrados: {len(errors)}")
    print(f"Confirmacion: OBS no fue modificado.")
    print(f"Confirmacion: Los modelos no fueron reentrenados.")

if __name__ == "__main__":
    main()
