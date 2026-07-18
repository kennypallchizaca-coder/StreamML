# Replay reproducible del controlador

**Fuente:** escenario demostrativo determinista (sintético; no es evidencia de campo)

> Este resultado es un proxy de ingeniería. No sustituye una prueba física de QoE con teléfono, OBS y una red degradada.

| Estrategia | Score proxy | Interrupción | Respaldo | Cambios de perfil |
|---|---:|---:|---:|---:|
| Perfil fijo | 58.83 | 65.0 s | 0.0 s | 0 |
| Solo reactivo | 91.94 | 5.0 s | 0.0 s | 4 |
| Reactivo + predictivo + agente | 92.53 | 3.0 s | 12.0 s | 4 |

El sistema completo mejora **33.70 puntos** sobre el perfil fijo en este replay.

## Eventos del agente

- t=40s · `reduce` · high → medium · `reactive_capacity_reduction` · El modelo reactivo recomienda menor capacidad.
- t=50s · `reduce` · medium → low · `predictive_risk` · Riesgo predictivo de degradación; reducción preventiva.
- t=83s · `switch_to_backup` · low → low · `signal_loss_confirmed` · Pérdida total confirmada; activación automática del video de respaldo.
- t=84s · `maintain_backup` · low → low · `backup_held_signal_absent` · La señal principal continúa ausente; se mantiene el respaldo.
- t=85s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=86s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=87s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=88s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=89s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=90s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=91s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=92s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=93s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=94s · `maintain_backup` · low → low · `recovery_hysteresis` · Señal recuperada; esperando estabilidad antes de restaurar el vivo.
- t=95s · `restore_live` · low → low · `live_signal_stable` · Señal principal estable; restauración automática del vivo.
- t=100s · `increase` · low → medium · `upgrade_stability_confirmed` · Estabilidad confirmada; aumento de un nivel.
- t=134s · `increase` · medium → high · `upgrade_stability_confirmed` · Estabilidad confirmada; aumento de un nivel.
