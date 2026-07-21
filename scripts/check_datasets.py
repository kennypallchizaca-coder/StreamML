import pandas as pd
from pathlib import Path

# Paths
base_dir = Path(r"c:\Users\kenny\OneDrive\Documents\STREAM-AI\Adaptive-Streaming-ai")
rtr_dir = base_dir / "data" / "raw" / "reactive"
ghent_dir = base_dir / "data" / "raw" / "predictive"

print("--- RTR-NetzTest ---")
rtr_files = list(rtr_dir.glob("*.csv"))
if rtr_files:
    rtr_file = rtr_files[0]
    print(f"Archivo: {rtr_file.name}")
    print(f"Tamaño: {rtr_file.stat().st_size / (1024*1024):.2f} MB")
    df_rtr = pd.read_csv(rtr_file, sep=';', low_memory=False)
    if len(df_rtr.columns) == 1:
        df_rtr = pd.read_csv(rtr_file, sep=',', low_memory=False)
    print(f"Dimensiones: {df_rtr.shape}")
    print("Columnas reales:")
    print(list(df_rtr.columns))
    
    expected_cols = ["upload_kbit", "download_kbit", "ping_ms", "network_type", "time_utc"]
    for col in expected_cols:
        print(f"¿Existe {col}?: {col in df_rtr.columns}")
else:
    print("No se encontró archivo CSV para RTR-NetzTest.")

print("\n--- Ghent 4G/LTE ---")
ghent_files = list(ghent_dir.glob("report_*.log"))
print(f"Cantidad de archivos report_*.log: {len(ghent_files)}")
if ghent_files:
    ghent_file = ghent_files[0]
    print(f"Archivo de ejemplo: {ghent_file.name}")
    print(f"Tamaño: {ghent_file.stat().st_size / 1024:.2f} KB")
    df_ghent = pd.read_csv(ghent_file, sep=r'\s+', header=None)
    df_ghent.columns = ["timestamp_ms", "elapsed_ms", "latitude", "longitude", "bytes_received", "interval_ms"]
    print(f"Dimensiones: {df_ghent.shape}")
    
    duracion = df_ghent['elapsed_ms'].max() / 1000
    print(f"Duración de la sesión: {duracion} segundos")
    frecuencia = df_ghent['interval_ms'].mean()
    print(f"Frecuencia aproximada de medición: {frecuencia} ms")
