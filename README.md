# TP3 — Simulación de Montecarlo · Inventario de Bicicletas

**Materia:** Simulación · 4K3 · 2026  
**Grupo 5** · Ejercicio: *Inventario de Bicicletas*

## Cómo correr

Requiere Python 3.8+. No necesita librerías externas.

```bash
python main.py
```

## Parámetros

| Categoría | Variable | Default |
|---|---|---|
| Política | Cantidad a pedir (Q) | 5 |
| | Punto de Reposición (R) | 2 |
| | Inventario inicial | 7 |
| Costos | Mantenimiento ($/u/sem) | 30 |
| | Pedido ($/orden) | 200 |
| | Faltante ($/u) | 50 |
| Demanda | P(D=0..3) | 0.20 / 0.45 / 0.25 / 0.10 |
| Demora | P(S=1..3) | 0.30 / 0.40 / 0.30 |
| Daños | P(0/1/2 dañadas) | 0.60 / 0.30 / 0.10 |
| Control | N (filas a simular) | 1000 |
| | j (mostrar desde fila) | 1 |
| | i (cantidad a mostrar) | 50 |
| | Semilla (vacío = aleatoria) | — |

## Columnas de la tabla

| Columna | Significado |
|---|---|
| `Semana` | Nº de semana (1..N) |
| `RND_Dem` / `Demanda` | Aleatorio y demanda muestreada |
| `Inv_Ini` / `Llega_Ped` | Stock inicial y si llegó pedido |
| `RND_Danadas` / `Danadas` | Aleatorio y bicis dañadas al recibir |
| `Inv_PostArr` | Stock tras el arribo |
| `Vendido` / `Faltante` | Demanda atendida y no satisfecha |
| `Inv_Final` | Stock al cierre |
| `Ordenar_Ped` | Si se hizo pedido al cierre |
| `RND_Demora` / `Demora` / `Sem_Arribo` | Aleatorio, demora muestreada y semana de arribo |
| `Ped_Pend` | Si hay pedido en tránsito |
| `C_Mantenimiento` / `C_Pedido` / `C_Faltante` / `C_Total_Sem` | Costos de la semana |
| `Ac_Costo_Tot` / `Ac_Danadas` | Acumuladores finales |

La fila N se resalta en amarillo. Si no cae en el rango `[j, j+i)` se muestra al final separada por `...`.

## Estructura

```
TP3/
├── main.py       # entry point
├── gui.py        # interfaz gráfica (Tkinter)
└── simulador.py  # motor de simulación (MT19937)
```
