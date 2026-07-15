import argparse
import time
import sys
import csv
from pathlib import Path

# Agregar src al path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.telemetry_collector import TelemetryCollector
from src.shadow_agent import ShadowAgent

def main():
    parser = argparse.ArgumentParser(description="Ejecuta el recolector de telemetría y el agente sombra en tiempo real.")
    parser.add_argument("--duration", type=int, default=30, help="Duración en segundos a ejecutar.")
    args = parser.parse_args()

    try:
        collector = TelemetryCollector(
            config_path=project_root / "config/shadow_agent_config.json",
            schema_path=project_root / "config/telemetry_schema.json"
        )
    except Exception as e:
        print(f"Error inicializando recolector: {e}")
        sys.exit(1)

    try:
        agent = ShadowAgent(config_path=project_root / "config/shadow_agent_config.json")
    except Exception as e:
        print(f"Error inicializando ShadowAgent: {e}")
        sys.exit(1)

    session_id = collector.session_id
    output_dir = project_root / "data/telemetry/predictions"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    shadow_output_file = output_dir / f"{session_id}_runtime_shadow.csv"

    print(f"--- RUNTIME SHADOW MODE ---")
    print(f"session_id: {session_id}")
    print(f"telemetry_file: {collector.output_file}")
    print(f"predictions_file: {shadow_output_file}")
    print(f"duration: {args.duration} segundos")

    measurements = 0
    reactives = 0
    maintain_count = 0
    downgrade_count = 0
    prob_min = 1.0
    prob_max = 0.0
    predictive_activation_time = None
    action_none_ok = True

    start_time = time.time()
    status = "completed"

    try:
        with open(shadow_output_file, 'w', newline='', encoding='utf-8') as fout:
            # Obtener campos desde el schema
            headers = collector.fields.copy()
            
            if 'inference_status' not in headers:
                headers.extend([
                    'buffer_measurements', 'buffer_coverage', 'inference_status', 
                    'obs_bitrate_mbps', 'network_traffic_upload_mbps', 'network_traffic_download_mbps',
                    'predictive_throughput_mbps', 'predictive_input_source'
                ])

            writer = csv.DictWriter(fout, fieldnames=headers)
            writer.writeheader()

            while (time.time() - start_time) < args.duration:
                loop_start = time.time()
                
                # Recolecta la muestra
                row = collector.collect_sample()
                if row:
                    # Procesa la muestra en el agente sombra
                    res = agent.process_sample(row)
                    
                    measurements += 1
                    
                    if res.get('reactive_prediction') is not None:
                        reactives += 1
                        
                    prob = res.get('degradation_probability')
                    if prob is not None:
                        prob_min = min(prob_min, prob)
                        prob_max = max(prob_max, prob)
                        
                        if predictive_activation_time is None:
                            predictive_activation_time = res.get('timestamp_utc')
                            
                    pred = res.get('predictive_prediction')
                    if pred == 'maintain':
                        maintain_count += 1
                    elif pred == 'downgrade_needed':
                        downgrade_count += 1
                        
                    if res.get('action_applied') != 'none':
                        action_none_ok = False
                        
                    # Guardar el resultado en el CSV
                    filtered_res = {k: res.get(k) for k in headers}
                    writer.writerow(filtered_res)
                    fout.flush() # Asegurar que se escribe en disco

                    print(f"[{measurements}] buffer={res.get('buffer_coverage', 0):.2f} pred={pred} (prob={prob}) status={res.get('inference_status')}")

                else:
                    print("Error de lectura/escritura durante la recolección.")
                    status = "error"
                    break
                    
                elapsed = time.time() - loop_start
                sleep_time = max(0, collector.sample_interval - elapsed)
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        status = "interrupted"
        print("\nEjecución interrumpida por el usuario.")

    print("\n--- RESUMEN RUNTIME SOMBRA ---")
    print(f"Status de ejecución: {status}")
    print(f"Muestras procesadas: {measurements}")
    print(f"Predicciones reactivas generadas: {reactives}")
    print(f"Activación modelo predictivo: {predictive_activation_time if predictive_activation_time else 'No alcanzada'}")
    print(f"Maintain recomendados: {maintain_count}")
    print(f"Downgrade recomendados: {downgrade_count}")
    if prob_max > 0 or prob_min < 1.0:
        print(f"Rango de probabilidades: [{prob_min:.4f}, {prob_max:.4f}]")
    else:
        print("Rango de probabilidades: N/A")
    print(f"action_applied = none: {action_none_ok}")
    print(f"Archivo de predicciones guardado en: {shadow_output_file}")

if __name__ == "__main__":
    main()
