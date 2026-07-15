"""
Verificación de preparación para la presentación.
Comprueba la existencia e integridad de todos los componentes
necesarios sin modificar ningún archivo.
"""
import os
import sys
import json
from pathlib import Path

def check(condition, message):
    """Imprime resultado de verificación."""
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {message}")
    return condition

def main():
    # Detectar raíz del proyecto
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    os.chdir(project_root)

    print("=" * 60)
    print("VERIFICACIÓN DE PREPARACIÓN PARA PRESENTACIÓN")
    print("=" * 60)
    
    all_passed = True
    
    # 1. Notebooks
    print("\n--- Notebooks ---")
    for nb in [
        "notebooks/01_carga_preparacion_dataset.ipynb",
        "notebooks/02_entrenamiento_modelos.ipynb",
        "notebooks/03_prediccion_nuevos_ejemplos.ipynb"
    ]:
        passed = check(Path(nb).exists(), f"Existe {nb}")
        all_passed = all_passed and passed
    
    # 2. Modelos congelados
    print("\n--- Modelos congelados ---")
    release_dir = Path("models/phase1_final_release")
    passed = check(release_dir.exists(), "Directorio phase1_final_release existe")
    all_passed = all_passed and passed
    
    for model_file in [
        "manifest.json",
        "model_metadata_phase1_final.json",
        "model_input_contract_v2.json",
        "modelo_reactivo_phase1_final.joblib",
        "modelo_predictivo_phase1_final.joblib",
        "preprocesador_reactivo_phase1_final.joblib",
        "preprocesador_predictivo_phase1_final.joblib"
    ]:
        fpath = release_dir / model_file
        passed = check(fpath.exists() and fpath.stat().st_size > 0, f"Existe {model_file}")
        all_passed = all_passed and passed
    
    # 3. Configuraciones de Fase 2
    print("\n--- Configuraciones ---")
    for cfg in [
        "config/data_collection_config.json",
        "config/shadow_agent_config.json",
        "config/telemetry_schema.json",
        "config/model_input_contract_v2.json"
    ]:
        passed = check(Path(cfg).exists(), f"Existe {cfg}")
        all_passed = all_passed and passed
    
    # 4. Scripts de recolección
    print("\n--- Scripts de recolección ---")
    for script in [
        "scripts/run_data_collection_session.py",
        "scripts/run_telemetry_collector.py",
        "scripts/verify_phase1_release.py",
        "scripts/label_session.py"
    ]:
        passed = check(Path(script).exists(), f"Existe {script}")
        all_passed = all_passed and passed
    
    # 5. Documentación
    print("\n--- Documentación ---")
    for doc in [
        "README.md",
        "docs/guia_demostracion.md",
        "docs/protocolo_recoleccion_fase2.md",
        "docs/reporte_avance_fase2.md",
        "docs/auditoria_paridad_features.md",
        "docs/validacion_shadow_mode.md"
    ]:
        passed = check(Path(doc).exists(), f"Existe {doc}")
        all_passed = all_passed and passed
    
    # 6. Archivos vacíos inesperados
    print("\n--- Archivos vacíos ---")
    allowed_empty = {"__init__.py", ".gitkeep", ".gitignore"}
    empty_found = []
    for root_dir, dirs, files in os.walk("."):
        # Saltar directorios de git y caché
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv"}]
        for fname in files:
            fpath = Path(root_dir) / fname
            if fpath.stat().st_size == 0 and fname not in allowed_empty:
                empty_found.append(str(fpath))
    
    passed = check(len(empty_found) == 0, f"Sin archivos vacíos inesperados ({len(empty_found)} encontrados)")
    if empty_found:
        for ef in empty_found:
            print(f"    → {ef}")
    all_passed = all_passed and passed
    
    # 7. Telemetría ignorada por Git
    print("\n--- Telemetría ignorada ---")
    telemetry_gitignore = Path("data/telemetry/.gitignore")
    passed = check(telemetry_gitignore.exists(), "data/telemetry/.gitignore existe")
    all_passed = all_passed and passed
    
    if telemetry_gitignore.exists():
        content = telemetry_gitignore.read_text(encoding="utf-8")
        for pattern in ["raw/", "events/", "metadata/", "predictions/"]:
            passed = check(pattern in content, f"Patrón '{pattern}' presente en telemetry .gitignore")
            all_passed = all_passed and passed
    
    # 8. Modelos automáticos desactivados
    print("\n--- Control automático ---")
    shadow_config_path = Path("config/shadow_agent_config.json")
    if shadow_config_path.exists():
        with open(shadow_config_path, "r", encoding="utf-8") as f:
            shadow_config = json.load(f)
        
        auto_control = shadow_config.get("automatic_control_enabled", shadow_config.get("auto_control", False))
        passed = check(not auto_control, "Control automático desactivado en shadow_agent_config")
        all_passed = all_passed and passed
    else:
        passed = check(False, "shadow_agent_config.json no encontrado")
        all_passed = all_passed and passed
    
    # 9. action_applied = none en configuración
    print("\n--- Acciones aplicadas ---")
    metadata_path = Path("models/model_metadata_phase1_final.json")
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        prod_ready = metadata.get("production_ready", True)
        passed = check(not prod_ready, "production_ready = false en metadatos")
        all_passed = all_passed and passed
    
    # 10. Credenciales en archivos versionados
    print("\n--- Seguridad ---")
    secrets_found = False
    
    # Solo revisar archivos que Git rastrea o que son candidatos a rastreo
    tracked_text_extensions = {".py", ".md", ".txt", ".csv", ".yml", ".yaml", ".toml", ".cfg", ".ini"}
    # Patrones seguros: nombres de variables, referencias a env vars, documentación
    safe_value_patterns = {
        "", "none", "null", "false", "true", "tu_contraseña_de_obs",
        "your_password", "example", "placeholder"
    }
    
    for root_dir, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", "data"}]
        for fname in files:
            fpath = Path(root_dir) / fname
            # Saltar .env, .env.example, archivos JSON, y el propio script de verificación
            if fname in {".env", ".env.example", "check_presentation_ready.py"} or fpath.suffix == ".json":
                continue
            if fpath.suffix.lower() in tracked_text_extensions:
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                    lines = text.split("\n")
                    for line in lines:
                        line_lower = line.lower().strip()
                        # Buscar asignaciones directas de credenciales (no nombres de variables)
                        if any(p in line_lower for p in ["password", "secret", "api_key"]):
                            # Ignorar comentarios, imports, prints, variable names, env references
                            if line_lower.startswith("#") or line_lower.startswith("//"):
                                continue
                            if "os.environ" in line or "os.getenv" in line or "dotenv" in line:
                                continue
                            if "import" in line_lower:
                                continue
                            if "self.password" in line_lower:
                                continue
                            if "password=self" in line_lower:
                                continue
                            # Verificar si hay un valor literal asignado
                            if "=" in line and not line_lower.startswith("obs_") and not line_lower.startswith("\"obs"):
                                parts = line.split("=", 1)
                                if len(parts) == 2:
                                    value = parts[1].strip().strip("'\"").lower()
                                    if value not in safe_value_patterns and not value.startswith("os.") and not value.startswith("$"):
                                        secrets_found = True
                except (OSError, UnicodeDecodeError):
                    pass
    
    passed = check(not secrets_found, "Sin credenciales detectadas en archivos de código")
    all_passed = all_passed and passed
    
    # Verificar que .env está en .gitignore
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        gi_content = gitignore_path.read_text(encoding="utf-8")
        passed = check(".env" in gi_content, ".env está en .gitignore")
        all_passed = all_passed and passed
    
    # Resultado final
    print("\n" + "=" * 60)
    if all_passed:
        print("PRESENTATION READY")
    else:
        print("PRESENTATION NOT READY — Revisar los items marcados como FAIL")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
