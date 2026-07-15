import sys
from pathlib import Path
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.obs_telemetry_collector import OBSTelemetryCollector

def main():
    print("Iniciando prueba de conexión con OBS en modo solo lectura...")
    collector = OBSTelemetryCollector()
    
    # Confirmar lectura limpia y no control
    assert getattr(collector, 'read_only', True), "Modo solo lectura no esta activo!"
    
    if collector.connect():
        print("Conexión Exitosa con OBS WebSocket.")
        try:
            version_info = collector.client.get_version()
            obs_version = getattr(version_info, 'obs_version', 'Desconocida')
            ws_version = getattr(version_info, 'obs_web_socket_version', 'Desconocida')
            print(f"Versión de OBS: {obs_version}")
            print(f"Versión de OBS WebSocket: {ws_version}")
            
            # Obtener métricas para prueba
            metrics = collector.get_metrics()
            print("\nMétricas de lectura obtenidas:")
            print(f"- FPS actuales: {metrics['fps']}")
            print(f"- Dropped frames: {metrics['dropped_frames']}")
            print(f"- Total frames: {metrics['total_frames']}")
            
            estado_salida = "Activa" if metrics['output_active'] else "Inactiva"
            print(f"- Estado de salida: {estado_salida}")
            
            if metrics['output_active']:
                # Simulamos espera para probar el calculo de bitrate
                print("\nEsperando 2 segundos para calcular bitrate...")
                time.sleep(2.0)
                metrics2 = collector.get_metrics()
                print(f"- Bitrate calculado: {metrics2['bitrate_kbps']} kbps")
            else:
                print("\nLa salida no está activa. No se puede calcular bitrate (es null).")
                
            print("\nModo de operación: SOLO LECTURA COMPROBADO.")
        except Exception as e:
            print(f"Error obteniendo datos: {e}")
    else:
        print("Conexión fallida. OBS no está disponible o las credenciales son incorrectas.")
        print("Asegúrate de que OBS esté abierto, el servidor WebSocket habilitado y las credenciales en .env sean correctas.")

if __name__ == "__main__":
    main()
