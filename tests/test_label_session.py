import json
import pytest
from pathlib import Path
from scripts.label_session import add_label

def test_add_label(tmp_path, monkeypatch):
    def mock_path(path_str):
        p = tmp_path / Path(path_str).name
        return p
        
    monkeypatch.setattr('scripts.label_session.Path', mock_path)
    
    session_id = 'test-session-123'
    
    # Simular metadata para evitar "fuera de sesion"
    metadata_path = tmp_path / f'{session_id}_metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump({
            "start_time_utc": "2026-07-14T10:00:00Z",
            "end_time_utc": "2026-07-14T11:00:00Z"
        }, f)
    
    # 1. Agregar uno valido
    add_label(session_id, 'freeze', '2026-07-14T10:10:00Z', '2026-07-14T10:10:10Z', 'high', 'Test', False)
    
    events_path = tmp_path / f'{session_id}_events.json'
    assert events_path.exists()
    
    with open(events_path, 'r', encoding='utf-8') as f:
        events = json.load(f)
    assert len(events) == 1
    
    # 2. Intervalos invalidos (start >= end)
    with pytest.raises(SystemExit):
        add_label(session_id, 'freeze', '2026-07-14T10:15:10Z', '2026-07-14T10:15:00Z', 'high', '', False)
        
    # 3. Fuera de la sesion
    with pytest.raises(SystemExit):
        add_label(session_id, 'freeze', '2026-07-14T09:59:00Z', '2026-07-14T10:00:10Z', 'high', '', False)

    # 4. Duplicado exacto
    with pytest.raises(SystemExit):
        add_label(session_id, 'freeze', '2026-07-14T10:10:00Z', '2026-07-14T10:10:10Z', 'high', 'Test', False)

    # 5. Superpuesto sin flag o diferente label
    with pytest.raises(SystemExit):
        # Mismo label sin allow_overlap
        add_label(session_id, 'freeze', '2026-07-14T10:10:05Z', '2026-07-14T10:10:15Z', 'high', '', False)
        
    with pytest.raises(SystemExit):
        # Diferente label con allow_overlap (no permitido)
        add_label(session_id, 'stable', '2026-07-14T10:10:05Z', '2026-07-14T10:10:15Z', 'none', '', True)
        
    # 6. Superpuesto correcto (mismo label con allow_overlap)
    add_label(session_id, 'freeze', '2026-07-14T10:10:05Z', '2026-07-14T10:10:15Z', 'high', '', True)
    
    with open(events_path, 'r', encoding='utf-8') as f:
        events2 = json.load(f)
    assert len(events2) == 2
