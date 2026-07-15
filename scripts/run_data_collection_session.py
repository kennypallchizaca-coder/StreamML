import os
import sys
import csv
import time
import json
import argparse
import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.session_data_collector import SessionDataCollector

def ensure_dirs():
    base = Path('data/telemetry')
    for d in ['raw', 'metadata', 'events']:
        (base / d).mkdir(parents=True, exist_ok=True)

def run_session(duration: int, profile: str, condition: str):
    ensure_dirs()
    
    collector = SessionDataCollector()
    collector.connect()
    
    # Wait for initial metrics
    time.sleep(1)
    
    session_id = collector.session_id
    raw_path = Path(f'data/telemetry/raw/{session_id}_telemetry.csv')
    metadata_path = Path(f'data/telemetry/metadata/{session_id}_metadata.json')
    events_path = Path(f'data/telemetry/events/{session_id}_events.json')
    
    # Initialize empty events array
    with open(events_path, 'w', encoding='utf-8') as f:
        json.dump([], f)
        
    start_time = datetime.datetime.now(datetime.timezone.utc)
    
    with open(raw_path, 'w', newline='', encoding='utf-8') as fcsv:
        writer = None
        samples_collected = 0
        timestamp_errors = 0
        
        while True:
            now = datetime.datetime.now(datetime.timezone.utc)
            if (now - start_time).total_seconds() >= duration:
                break
                
            sample = collector.collect_sample(profile_name=profile, condition=condition)
            if sample is None or not sample.get('timestamp_utc'):
                print("Error: No se pudo generar timestamp. Saltando muestra.")
                timestamp_errors += 1
                time.sleep(1.0)
                continue
            
            if not writer:
                writer = csv.DictWriter(fcsv, fieldnames=list(sample.keys()))
                writer.writeheader()
                
            writer.writerow(sample)
            fcsv.flush()
            samples_collected += 1
            
            print(f"[{samples_collected}/{duration}] profile={sample['current_profile_name']} "
                  f"bitrate={sample['obs_bitrate_kbps']} "
                  f"fps={sample['fps']} "
                  f"frames={sample['total_frames']}")
                  
            time.sleep(1.0)
            
    collector.disconnect()
    end_time = datetime.datetime.now(datetime.timezone.utc)
    
    # Validate CSV
    invalid_rows = 0
    bitrate_warmup_samples = 0
    bitrate_reset_samples = 0
    
    if raw_path.exists():
        with open(raw_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            last_elapsed = -1.0
            for row in reader:
                valid = True
                if not row.get('timestamp_utc'):
                    valid = False
                if not row.get('session_id'):
                    valid = False
                
                try:
                    elapsed = float(row.get('elapsed_seconds', -1))
                    if elapsed <= last_elapsed:
                        valid = False
                    last_elapsed = elapsed
                except ValueError:
                    valid = False
                    
                if row.get('action_applied') != 'none':
                    valid = False
                
                # Check bitrate & fps are numeric or empty string
                for col in ['obs_bitrate_kbps', 'fps']:
                    val = row.get(col)
                    if val != '' and val is not None:
                        try:
                            float(val)
                        except ValueError:
                            valid = False

                if row.get('bitrate_status') == 'warmup':
                    bitrate_warmup_samples += 1
                if row.get('bitrate_status') == 'reset':
                    bitrate_reset_samples += 1
                    
                if not valid:
                    invalid_rows += 1
    
    validation_status = 'valid' if invalid_rows == 0 else 'invalid'

    metadata = {
        "session_id": session_id,
        "requested_duration": duration,
        "actual_duration": (end_time - start_time).total_seconds(),
        "profile": profile,
        "experimental_condition": condition,
        "sampling_frequency_hz": 1.0,
        "obs_version": "unknown", # To be extracted if available, otherwise unknown
        "schema_version": collector.config.get("schema_version", "2.0"),
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "samples_recorded": samples_collected,
        "interruptions": 0,
        "mediamtx_status": "active", # Assuming active if network traffic flows
        "models_executed": False,
        "invalid_rows": invalid_rows,
        "bitrate_warmup_samples": bitrate_warmup_samples,
        "bitrate_reset_samples": bitrate_reset_samples,
        "timestamp_errors": timestamp_errors,
        "validation_status": validation_status
    }
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4)
        
    print(f"\n--- RESUMEN SESIÓN DE RECOLECCIÓN ---")
    print(f"Sesión completada: {session_id}")
    print(f"Muestras: {samples_collected}")
    print(f"Metadata guardada en: {metadata_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=int, default=180)
    parser.add_argument('--profile', type=str, choices=['low', 'medium', 'high'], default='high')
    parser.add_argument('--condition', type=str, choices=['stable', 'bandwidth_reduction', 'high_latency', 'signal_loss', 'recovery', 'custom'], default='stable')
    args = parser.parse_args()
    
    run_session(args.duration, args.profile, args.condition)
