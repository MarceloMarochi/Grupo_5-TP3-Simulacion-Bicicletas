# TP3 — Simulación de Montecarlo · Inventario de Bicicletas

**Materia:** Simulación · 4K3 · 2026
**Ejercicio asignado:** *Inventario de Bicicletas* (grupos 5 / 15 / 18)
**Modo:** Grupo amarillo → aplicativo con GUI parametrizable.

---

## Cómo correr

Requisitos: **Python 3.8 o superior** (Windows/macOS traen `tkinter` por defecto; en Linux puede necesitarse `sudo apt install python3-tk`).

```bash
cd TP3
python main.py
```

Se abre la ventana con el panel de parámetros a la izquierda y la tabla a la derecha. Apretar **Simular ▶**.

> No se requieren librerías externas (todo es stdlib: `random`, `dataclasses`, `tkinter`).

---

## Generador de números aleatorios

Se usa `random.Random()` de la biblioteca estándar de Python, cuya implementación interna es **Mersenne Twister (MT19937)** — el mismo algoritmo que la cátedra recomienda. Período `2^19937 - 1`. Si se ingresa una **semilla** entera la corrida es reproducible; si el campo queda vacío, la semilla se obtiene del sistema.

---

## Modelo

La firma "El Rey de la Bicicleta" maneja un único producto. Cada semana el simulador recorre estos pasos:

1. **Arribo del pedido** (si hay uno pendiente y le toca llegar esta semana). Al recibirlo se sortea el daño:
   - 60 % de las veces no hay daños.
   - 30 % de las veces llega una unidad dañada (se devuelve al proveedor sin costo).
   - 10 % de las veces llegan dos unidades dañadas.
2. **Demanda semanal**: 0 (20 %), 1 (45 %), 2 (25 %), 3 (10 %).
3. **Atención de la demanda**: lo que se puede del stock; el remanente queda como faltante (lost sales).
4. **Decisión de reorden**: si el stock al cierre quedó ≤ punto de reorden y no hay pedido pendiente, se realiza un pedido de Q unidades. El lead time es 1 sem (30 %), 2 sem (40 %) o 3 sem (30 %).
5. **Costos** de la semana: tenencia = `inv_fin × $30`, pedido = `$200` si se pidió, faltante = `unidades_faltantes × $50`.

> **Convención**: los pedidos arriban al **inicio** de la semana (`semana_pedido + lead_time`), siguiendo la nota del enunciado.

---

## Parámetros (los que están **rojos** en el enunciado son ingresables)

| Categoría | Variable | Default |
|---|---|---|
| Política | Cantidad a pedir Q | 5 |
| | Punto de reorden R | 2 |
| | Inventario inicial | 7 |
| Costos | Tenencia ($/u/sem) | 30 |
| | Pedido ($/orden) | 200 |
| | Agotamiento ($/u) | 50 |
| Demanda | P(D=0..3) | 0.20 / 0.45 / 0.25 / 0.10 |
| Lead time | P(L=1..3) | 0.30 / 0.40 / 0.30 |
| Daños | P(0/1/2 dañadas) | 0.60 / 0.30 / 0.10 |
| Control | N (filas a simular) | 1000 |
| | j (mostrar desde fila) | 1 |
| | i (cantidad a mostrar) | 50 |
| | Semilla (vacío = aleatoria) | — |

La aplicación valida que cada distribución sume 1.0 y que `N > 0` antes de correr.

---

## Vector de estado (columnas que aparecen en la grilla)

| Columna | Significado |
|---|---|
| `Semana` | Nº de semana (1..N) |
| `RND_Dem` / `Demanda` | Aleatorio uniforme y demanda muestreada |
| `Inv_Ini` | Stock al inicio de la semana (antes del posible arribo) |
| `Llega_Ped` | Sí/No — arriba un pedido esta semana |
| `RND_Dano` / `Danadas` | Aleatorio y cantidad de bicis dañadas (sólo si llegó pedido) |
| `Inv_PostArr` | Stock luego del arribo |
| `Vendido` / `Faltante` | Demanda atendida y demanda no satisfecha |
| `Inv_Fin` | Stock al cierre de la semana |
| `Reordenar` | Sí/No — si se hizo pedido al cierre |
| `RND_Lead` / `Lead_T` / `Sem_Arribo` | Aleatorio, lead time muestreado y semana de arribo |
| `Ped_Pend` | Sí/No — hay un pedido en tránsito al cierre |
| `C_Tenencia` / `C_Pedido` / `C_Faltante` / `C_Total_Sem` | Costos de la semana |
| `Ac_Tenencia` / `Ac_Pedido` / `Ac_Faltante` / `Ac_Costo_Tot` | Acumulados de costos |
| `Ac_Demanda` / `Ac_Faltante_U` / `Ac_Danadas` | Acumuladores de unidades |

La fila `N` (última) se resalta en amarillo. Si `N` no cae en el rango `[j, j+i)` se muestra de todas formas al final, separada por una fila de puntos suspensivos.

---

## Cumplimiento de los requisitos del documento de Consideraciones

| Requisito | Cumplimiento |
|---|---|
| Interfaz gráfica (no consola) | Tkinter + ttk |
| Scroll horizontal y vertical | Scrollbars en ambos ejes |
| Sin paginación | `ttk.Treeview` muestra todas las filas en continuo |
| Sin parpadeo al scrollear | Treeview es nativo (renderizado por OS) |
| Selección persistente al scrollear | Treeview mantiene la selección |
| Encabezados fijos | `show="headings"` los deja siempre visibles |
| Copiar/pegar a Excel | `Ctrl+C` copia las filas seleccionadas con tabuladores |
| Variables rojas como parámetros | Panel izquierdo |
| Trabajo con 2 filas en memoria | El simulador sólo arrastra `inv_fin_prev` + estado del pedido pendiente |
| Soporte N ≥ 100.000 | Probado: N = 100.000 corre en ~0.3 s |
| Mostrar `i` filas desde `j` + fila `N` | Implementado |
| Acumuladores como columnas | 7 columnas `Ac_*` |

---

## Estructura del proyecto

```
TP3/
├── main.py        # entry point — sólo lanza la GUI
├── gui.py         # ventana, panel de parámetros, Treeview, resumen
├── simulador.py   # motor MT19937, distribuciones, lógica del modelo
└── README.md      # este archivo
```

El motor (`simulador.py`) es independiente de la GUI: se puede correr standalone con `python simulador.py` para una prueba rápida en consola.

---

## Notas de validación

Con semilla 42 y N = 100.000:

- Costo promedio por semana ≈ **$131**
- Nivel de servicio ≈ **90.8 %**
- Bicicletas dañadas totales ≈ 12.800

Las frecuencias empíricas de demanda en 100.000 muestras coinciden con las teóricas dentro del 0.2 % en cada categoría.
# Grupo_5-TP3-Simulacion-Bicicletas
