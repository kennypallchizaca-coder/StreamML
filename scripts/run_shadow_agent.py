import argparse
import sys
import csv
import glob
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.shadow_agent import ShadowAgent

def main():
    parser = argparse.ArgumentParser(description="Ejecuta el agente de inferencia en modo sombra.")
    parser.add_argument("--input", type=str, help="Ruta al archivo CSV de telemetría a procesar.")
    parser.add_argument("--latest", action="store_true", help="Procesa el CSV más reciente en data/telemetry.")
    args = parser.parse_args()

    if not args.input and not args.latest:
        print("Debe proporcionar --input o --latest.")
        sys.exit(1)

    input_file = None
    if args.latest:
        csv_files = glob.glob(str(project_root / "data/telemetry/*.csv"))
        # Excluir example
        csv_files = [f for f in csv_files if "example" not in f]
        if not csv_files:
            print("No se encontraron archivos CSV en data/telemetry/")
            sys.exit(1)
        input_file = max(csv_files, key=lambda f: Path(f).stat().st_mtime)
    else:
        input_file = args.input

    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Archivo no encontrado: {input_path}")
        sys.exit(1)

    output_dir = project_root / "data/telemetry/predictions"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    session_id = input_path.stem
    output_path = output_dir / f"{session_id}_shadow.csv"

    print(f"Iniciando procesamiento de: {input_path}")
    print(f"Salida en: {output_path}")

    try:
        agent = ShadowAgent(config_path=project_root / "config/shadow_agent_config.json")
    except Exception as e:
        print(f"Error inicializando ShadowAgent: {e}")
        sys.exit(1)

    processed = 0
    reactives = 0
    maintain_count = 0
    downgrade_count = 0
    prob_min = 1.0
    prob_max = 0.0
    predictive_activation_time = None
    action_none_ok = True

    try:
        with open(input_path, 'r', encoding='utf-8') as fin, \
             open(output_path, 'w', newline='', encoding='utf-8') as fout:
            
            reader = csv.DictReader(fin)
            
            headers = reader.fieldnames
            if 'inference_status' not in headers:
                headers.extend(['buffer_measurements', 'buffer_coverage', 'inference_status'])
                
            writer = csv.DictWriter(fout, fieldnames=headers)
            writer.writeheader()

            for row in reader:
                res = agent.process_sample(row)
                processed += 1
                
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
                    
                # Fill missing keys if any
                filtered_res = {k: res.get(k) for k in headers}
                writer.writerow(filtered_res)

    except KeyboardInterrupt:
        print("Procesamiento interrumpido por el usuario.")
    except Exception as e:
        print(f"Error durante el procesamiento: {e}")

    print("\n--- RESUMEN MODO SOMBRA ---")
    print(f"Muestras procesadas: {processed}")
    print(f"Predicciones reactivas generadas: {reactives}")
    print(f"Activacion modelo predictivo: {predictive_activation_time if predictive_activation_time else 'No alcanzada'}")
    print(f"Maintain recomendados: {maintain_count}")
    print(f"Downgrade recomendados: {downgrade_count}")
    if prob_max > 0 or prob_min < 1.0:
        print(f"Rango de probabilidades: [{prob_min:.4f}, {prob_max:.4f}]")
    else:
        print("Rango de probabilidades: N/A")
    print(f"action_applied = none: {action_none_ok}")
    print(f"Archivo guardado en: {output_path}")

if __name__ == "__main__":
    main()
