import argparse
import time
import sys
from pathlib import Path

# Agregar src al path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.telemetry_collector import TelemetryCollector

def main():
    parser = argparse.ArgumentParser(description="Ejecuta el recolector base de telemetría.")
    parser.add_argument("--duration", type=int, default=30, help="Duración en segundos a recolectar.")
    args = parser.parse_args()

    try:
        collector = TelemetryCollector(
            config_path=project_root / "config/shadow_agent_config.json",
            schema_path=project_root / "config/telemetry_schema.json"
        )
    except Exception as e:
        print(f"Error inicializando recolector: {e}")
        sys.exit(1)

    print(f"session_id: {collector.session_id}")
    print(f"output_file: {collector.output_file}")
    print(f"duration: {args.duration} segundos")

    measurements = 0
    start_time = time.time()
    status = "completed"

    try:
        while (time.time() - start_time) < args.duration:
            loop_start = time.time()
            
            success = collector.collect_sample()
            if success:
                measurements += 1
            else:
                print("Error de escritura durante la recolección.")
                status = "error"
                break
                
            elapsed = time.time() - loop_start
            sleep_time = max(0, collector.sample_interval - elapsed)
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        status = "interrupted"

    print(f"measurements: {measurements}")
    print(f"status: {status}")

if __name__ == "__main__":
    main()
