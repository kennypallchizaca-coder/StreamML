import argparse
import json
import logging
import time
import datetime
import uuid
import subprocess
import re
import platform
import psutil
import pandas as pd
from pathlib import Path
import sys

def setup_logging():
    Path("reports").mkdir(exist_ok=True)
    logging.basicConfig(
        filename="reports/telemetry_collector.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger("").addHandler(console)

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

def validate_schema(schema_path):
    with open(schema_path, "r") as f:
        data = json.load(f)
    return data["schema"]

def create_row(schema, values):
    row = {}
    for col, meta in schema.items():
        val = values.get(col, None)
        if val is None and not meta["nullable"] and meta["required"]:
            if col == "obs_output_active" or col == "signal_available":
                val = False
            elif col in ["dropped_frames", "total_frames", "reconnect_count"]:
                val = 0
            elif col in ["current_profile", "stream_status"]:
                val = "unknown"
            else:
                val = ""
        if val is not None and meta["type"] in ["float", "integer"] and isinstance(val, (int, float)):
            if "< 0" in str(meta["valid_range"]) or ">= 0" in str(meta["valid_range"]):
                if val < 0: val = 0
        row[col] = val
    return row

def main():
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Telemetry Collector")
    parser.add_argument("--duration", type=int, help="Duration in seconds", default=None)
    parser.add_argument("--interface", type=str, help="Network Interface", default="auto")
    parser.add_argument("--target", type=str, help="Ping target", default="1.1.1.1")
    parser.add_argument("--interval", type=int, help="Sampling interval in seconds", default=1)
    parser.add_argument("--config", type=str, help="Config file path", default="config/telemetry_config.json")
    args = parser.parse_args()

    config = {}
    if Path(args.config).exists():
        with open(args.config, "r") as f:
            config = json.load(f)
    
    duration = args.duration
    interface = args.interface if args.interface != "auto" else config.get("network_interface", "auto")
    target = args.target if args.target != "1.1.1.1" else config.get("latency_target", "1.1.1.1")
    interval = args.interval if args.interval != 1 else config.get("sampling_interval_seconds", 1)
    latency_probe_interval = config.get("latency_probe_interval_seconds", 5)
    source = config.get("source", "system_network")

    schema_path = "data/telemetry/telemetry_schema.json"
    if not Path(schema_path).exists():
        logging.error("Telemetry schema not found!")
        return
    
    schema = validate_schema(schema_path)
    ordered_columns = list(schema.keys())
    
    session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    logging.info(f"Iniciando sesion de recoleccion: {session_id}")
    
    if interface == "auto":
        stats = psutil.net_io_counters(pernic=True)
        interface = list(stats.keys())[0]
        for nic, stat in stats.items():
            if stat.bytes_sent > 0 and stat.bytes_recv > 0 and nic != "lo":
                interface = nic
                break
    
    logging.info(f"Interfaz de red detectada/seleccionada: {interface}")
    
    net_stats_prev = psutil.net_io_counters(pernic=True).get(interface)
    if not net_stats_prev:
        logging.error(f"Interfaz {interface} no encontrada.")
        return
    
    time_prev = time.time()
    
    out_dir = Path(config.get("output_directory", "data/telemetry/raw"))
    out_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = out_dir / f"{session_id}.csv"
    meta_path = out_dir / f"{session_id}_metadata.json"
    
    collected_rows = []
    
    start_time_utc = datetime.datetime.utcnow().isoformat()
    
    logging.info("Recolectando datos. Presione Ctrl+C para detener.")
    
    latencies = []
    packet_loss_count = 0
    total_probes = 0
    
    errors = []
    
    last_ping_time = 0
    current_latency = None
    
    start_loop = time.time()
    
    try:
        while True:
            current_time = time.time()
            elapsed_total = current_time - start_loop
            if duration and elapsed_total >= duration:
                break
                
            loop_start = time.time()
            
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
            
            signal_available = upload_mbps > 0 or download_mbps > 0
            
            if time_curr - last_ping_time >= latency_probe_interval:
                total_probes += 1
                lat = get_ping_latency(target)
                last_ping_time = time_curr
                if lat is not None:
                    current_latency = lat
                    latencies.append(lat)
                    signal_available = True
                else:
                    packet_loss_count += 1
                    current_latency = None
                    errors.append(f"Ping failed at {datetime.datetime.utcnow().isoformat()}")
                    logging.warning("Perdida de conexion o error de ping detectado.")

            jitter_ms = None
            if len(latencies) > 1:
                jitter_ms = abs(latencies[-1] - latencies[-2])
            
            packet_loss_percent = (packet_loss_count / total_probes * 100) if total_probes > 0 else 0.0
            
            values = {
                "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                "session_id": session_id,
                "source": source,
                "upload_mbps": upload_mbps,
                "download_mbps": download_mbps,
                "latency_ms": current_latency,
                "jitter_ms": jitter_ms,
                "packet_loss_percent": packet_loss_percent,
                "signal_available": signal_available
            }
            
            row = create_row(schema, values)
            collected_rows.append(row)
            
            elapsed_work = time.time() - loop_start
            sleep_time = interval - elapsed_work
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        logging.info("Interrupcion por el usuario (Ctrl+C). Guardando datos...")
    except Exception as e:
        errors.append(str(e))
        logging.error(f"Error durante recoleccion: {e}")
        
    end_time_utc = datetime.datetime.utcnow().isoformat()
    duration_secs = time.time() - start_loop
    
    df = pd.DataFrame(collected_rows, columns=ordered_columns)
    df.to_csv(csv_path, index=False)
    logging.info(f"Guardado CSV en: {csv_path}")
    
    missing_by_col = df.isnull().sum().to_dict()
    
    avg_up = df["upload_mbps"].mean() if not df["upload_mbps"].isnull().all() else 0
    avg_down = df["download_mbps"].mean() if not df["download_mbps"].isnull().all() else 0
    avg_lat = df["latency_ms"].mean() if not df["latency_ms"].isnull().all() else 0
    avg_jit = df["jitter_ms"].mean() if not df["jitter_ms"].isnull().all() else 0
    
    meta_info = {
        "session_id": session_id,
        "start_time_utc": start_time_utc,
        "end_time_utc": end_time_utc,
        "duration_seconds": duration_secs,
        "sampling_interval_seconds": interval,
        "latency_target": target,
        "network_interface": interface,
        "operating_system": platform.system(),
        "python_version": sys.version,
        "rows_collected": len(df),
        "missing_values_by_column": missing_by_col,
        "errors": errors,
        "stopped_correctly": True
    }
    
    with open(meta_path, "w") as f:
        json.dump(meta_info, f, indent=4)
        
    logging.info("Finalizacion de recoleccion de telemetria.")
    logging.info(f"Filas recolectadas: {len(df)}")
    
    print("\n--- RESUMEN DE PRUEBA DE 60 SEGUNDOS ---")
    print(f"Archivo CSV generado: {csv_path}")
    print(f"Archivo de metadatos generado: {meta_path}")
    print(f"Cantidad de filas: {len(df)}")
    print(f"Duracion: {duration_secs:.2f} s")
    print(f"Interfaz utilizada: {interface}")
    print(f"Promedio de upload_mbps: {avg_up:.4f} Mbps")
    print(f"Promedio de download_mbps: {avg_down:.4f} Mbps")
    print(f"Promedio de latency_ms: {avg_lat:.2f} ms")
    print(f"Promedio de jitter_ms: {avg_jit:.2f} ms")
    print(f"Perdida de paquetes: {packet_loss_percent:.2f}%")
    print(f"Cantidad de valores nulos: {df.isnull().sum().sum()}")
    print(f"Errores encontrados: {len(errors)}")
    
if __name__ == "__main__":
    main()
