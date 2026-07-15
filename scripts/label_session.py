import json
import argparse
import sys
from pathlib import Path
import datetime

def parse_iso(dt_str):
    try:
        return datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Formato de fecha inválido: {dt_str}")

def add_label(session_id, label, start_utc, end_utc, severity, notes, allow_overlap):
    start_dt = parse_iso(start_utc)
    end_dt = parse_iso(end_utc)
    
    if start_dt >= end_dt:
        print("Error: start_utc debe ser anterior a end_utc.")
        sys.exit(1)
        
    metadata_path = Path(f'data/telemetry/metadata/{session_id}_metadata.json')
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            sess_start = parse_iso(metadata.get('start_time_utc', start_utc))
            sess_end = parse_iso(metadata.get('end_time_utc', end_utc))
            
            if start_dt < sess_start or end_dt > sess_end:
                print("Error: El evento cae fuera del intervalo definido en metadata de la sesión.")
                sys.exit(1)

    events_path = Path(f'data/telemetry/events/{session_id}_events.json')
    if not events_path.exists():
        events = []
    else:
        with open(events_path, 'r', encoding='utf-8') as f:
            events = json.load(f)
            
    # Validaciones contra eventos existentes
    for ev in events:
        ev_start = parse_iso(ev['event_start_utc'])
        ev_end = parse_iso(ev['event_end_utc'])
        
        # Exact duplicate
        if ev['event_label'] == label and ev['event_start_utc'] == start_utc and ev['event_end_utc'] == end_utc:
            print("Error: Evento duplicado detectado.")
            sys.exit(1)
            
        # Overlap
        if start_dt < ev_end and end_dt > ev_start:
            if not allow_overlap:
                print("Error: Superposición de eventos detectada. Usa --allow-overlap si es intencional.")
                sys.exit(1)
            if ev['event_label'] != label:
                print(f"Error: Superposición con evento de distinta etiqueta ('{ev['event_label']}').")
                sys.exit(1)
            
    event = {
        "session_id": session_id,
        "event_start_utc": start_utc,
        "event_end_utc": end_utc,
        "event_label": label,
        "severity": severity,
        "notes": notes
    }
    
    events.append(event)
    events.sort(key=lambda x: x['event_start_utc'])
    
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with open(events_path, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=4, ensure_ascii=False)
        
    print(f"Evento '{label}' añadido a la sesión {session_id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--session_id', required=True)
    parser.add_argument('--label', choices=['stable', 'degraded', 'freeze', 'reconnecting', 'disconnected', 'recovered', 'unknown'], required=True)
    parser.add_argument('--start_utc', required=True)
    parser.add_argument('--end_utc', required=True)
    parser.add_argument('--severity', required=True)
    parser.add_argument('--notes', default='')
    parser.add_argument('--allow-overlap', action='store_true')
    args = parser.parse_args()
    
    add_label(args.session_id, args.label, args.start_utc, args.end_utc, args.severity, args.notes, args.allow_overlap)
