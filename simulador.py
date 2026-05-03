"""
TP3 - Simulación de Montecarlo
Ejercicio: Inventario de Bicicletas (Grupo 5 / 15 / 18)

Motor de simulación. Usa MT19937 (Mersenne Twister) — el algoritmo por defecto
de la clase random.Random() de Python (cf. CPython _randommodule.c).

Política de inventario:
    - Cantidad a pedir Q (default 5)
    - Punto de reorden R (default 2)
    - Inventario inicial I0 (default 7)
    - Costos: tenencia ($30/u/sem), pedido ($200/orden), agotamiento ($50/u)
    - Demanda semanal: 0(20%), 1(45%), 2(25%), 3(10%)
    - Lead time: 1sem(30%), 2sem(40%), 3sem(30%)
    - Daños al recibir: 0 dañadas (60%), 1 dañada (30%), 2 dañadas (10%)

Convención: el pedido se realiza al final de la semana en que se cruza el
punto de reorden, y arriba al INICIO de la semana (semana_pedido + lead_time).
Los costos de tenencia se aplican sobre el stock al cierre de cada semana.

Requisitos del enunciado (grupo amarillo):
    - Trabajar en memoria con 2 filas → solo se mantiene fila previa y actual.
    - Soportar N >= 100.000 filas.
    - Guardar/mostrar i iteraciones desde la fila j, más la fila N (última).
    - Todos los acumuladores como columnas.
    - Variables marcadas en rojo en el enunciado son parámetros de entrada.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Definición de columnas del vector de estado (orden = orden de visualización)
# ---------------------------------------------------------------------------
COLUMNAS = [
    "Semana",
    "RND_Dem",       "Demanda",
    "Inv_Ini",       "Llega_Ped",
    "RND_Danadas",   "Danadas",
    "Inv_PostArr",
    "Vendido",       "Faltante",
    "Inv_Final",
    "Ordenar_Ped",
    "RND_Demora",    "Demora",   "Sem_Arribo",
    "Ped_Pend",
    "C_Mantenimiento", "C_Pedido", "C_Faltante", "C_Total_Sem",
    "Ac_Costo_Tot",  "Ac_Danadas",
]


# ---------------------------------------------------------------------------
# Distribución discreta empírica con tabla acumulada (estilo planilla del prof.)
# ---------------------------------------------------------------------------
class DistribucionDiscreta:
    """
    Mapea un RND uniforme [0,1) a un valor discreto usando la acumulada.
    Replica el patrón LOOKUP(rand, $D$min:$D$max, $A$min:$A$max) del Excel.
    """

    def __init__(self, valores, probabilidades):
        if len(valores) != len(probabilidades):
            raise ValueError("valores y probabilidades deben tener igual largo")
        s = sum(probabilidades)
        if abs(s - 1.0) > 1e-9:
            raise ValueError(f"Las probabilidades deben sumar 1.0 (suman {s})")
        self.valores = list(valores)
        self.probs = list(probabilidades)
        # Acumulada en el extremo superior de cada bin: rand < acum[i] -> valores[i]
        acum = 0.0
        self.acum = []
        for p in self.probs:
            acum += p
            self.acum.append(acum)

    def muestrear(self, rnd: float):
        for i, lim in enumerate(self.acum):
            if rnd < lim:
                return self.valores[i]
        return self.valores[-1]  # blindaje numérico para rnd ~ 1.0

    def tabla(self):
        """Devuelve filas (valor, prob, acum, rmin, rmax) para mostrar en GUI."""
        rows = []
        prev = 0.0
        for v, p, a in zip(self.valores, self.probs, self.acum):
            rows.append((v, p, a, prev, a - 1e-6))
            prev = a
        return rows


# ---------------------------------------------------------------------------
# Parámetros de la simulación (todo lo marcado en rojo en el enunciado)
# ---------------------------------------------------------------------------
@dataclass
class Parametros:
    # Política
    cantidad_pedido: int = 5
    punto_reorden: int = 2
    inventario_inicial: int = 7

    # Costos
    costo_tenencia: float = 30.0     # $/u/semana
    costo_pedido: float = 200.0      # $/orden
    costo_agotamiento: float = 50.0  # $/u faltante

    # Demanda semanal: P(D=0)=0.20, P(D=1)=0.45, P(D=2)=0.25, P(D=3)=0.10
    demanda_valores: list = field(default_factory=lambda: [0, 1, 2, 3])
    demanda_probs:   list = field(default_factory=lambda: [0.20, 0.45, 0.25, 0.10])

    # Lead time: 1sem(0.3), 2sem(0.4), 3sem(0.3)
    lead_valores: list = field(default_factory=lambda: [1, 2, 3])
    lead_probs:   list = field(default_factory=lambda: [0.30, 0.40, 0.30])

    # Daños: 0(60%), 1(30%), 2(10%)
    dano_valores: list = field(default_factory=lambda: [0, 1, 2])
    dano_probs:   list = field(default_factory=lambda: [0.60, 0.30, 0.10])

    # Control de simulación
    n_filas: int = 1000          # cantidad total de semanas a simular
    mostrar_desde_j: int = 1     # primera fila a guardar
    mostrar_cantidad_i: int = 50 # cuántas filas mostrar a partir de j
    semilla: Optional[int] = None  # None = aleatoria; int = reproducible


# ---------------------------------------------------------------------------
# Resultado de la simulación
# ---------------------------------------------------------------------------
@dataclass
class Resultado:
    filas_visibles: list           # lista de tuplas (1 por semana en rango)
    fila_final: tuple              # la última fila (N)
    parametros: Parametros
    costo_total: float = 0.0
    danadas_total: int = 0
    costo_promedio_por_semana: float = 0.0


# ---------------------------------------------------------------------------
# Núcleo de simulación
# ---------------------------------------------------------------------------
def simular(p: Parametros) -> Resultado:
    # MT19937 — la implementación interna de random.Random es Mersenne Twister.
    # Si el usuario fija semilla, la corrida es reproducible.
    rng = random.Random(p.semilla)

    dist_demanda = DistribucionDiscreta(p.demanda_valores, p.demanda_probs)
    dist_lead    = DistribucionDiscreta(p.lead_valores,    p.lead_probs)
    dist_dano    = DistribucionDiscreta(p.dano_valores,    p.dano_probs)

    # ---- Estado: trabajamos con 2 filas en memoria (previa y actual) ----
    # Guardamos los datos necesarios de la "fila previa" :
    inv_fin_prev: int = p.inventario_inicial  # arrastra al inicio de la próxima semana
    pedido_pendiente_prev: bool = False
    semana_arribo_prev: Optional[int] = None
    cantidad_pedida_pendiente: int = 0

    # Acumuladores
    ac_total = 0.0
    ac_danadas = 0

    # Rango de filas a guardar
    j = max(1, p.mostrar_desde_j)
    i = max(0, p.mostrar_cantidad_i)
    rango_fin = j + i  # exclusive
    visibles = []
    fila_final = None

    N = p.n_filas

    """ Acá dentro del for comenzamos a guardar en variables locales la información de la fila
     actual """
    for semana in range(1, N + 1):
        # ---- 1) Arribo del pedido (si corresponde) ----
        llega_pedido = False
        rnd_dano = ""
        cant_danadas = 0
        inv_post_arr = inv_fin_prev

        if pedido_pendiente_prev and semana_arribo_prev == semana:
            llega_pedido = True
            r = rng.random()
            rnd_dano = round(r, 4)
            cant_danadas = dist_dano.muestrear(r)
            inv_post_arr = inv_fin_prev + (cantidad_pedida_pendiente - cant_danadas)
            pedido_pendiente_prev = False
            cantidad_pedida_pendiente = 0
            semana_arribo_prev = None

        # ---- 2) Generar demanda de la semana ----
        r = rng.random()
        rnd_dem = round(r, 4)
        demanda = dist_demanda.muestrear(r)

        # ---- 3) Atender demanda ----
        vendido = min(inv_post_arr, demanda)
        faltante = max(0, demanda - inv_post_arr)
        inv_fin = inv_post_arr - vendido  # >= 0

        # ---- 4) Decisión de pedido (al final de la semana) ----
        reordenar = False
        rnd_lead = ""
        lead_t = ""
        sem_arribo = ""
        if (inv_fin <= p.punto_reorden) and (not pedido_pendiente_prev):
            reordenar = True
            r = rng.random()
            rnd_lead = round(r, 4)
            lead = dist_lead.muestrear(r)
            lead_t = lead
            sem_arribo = semana + lead
            pedido_pendiente_prev = True
            semana_arribo_prev = sem_arribo
            cantidad_pedida_pendiente = p.cantidad_pedido

        # ---- 5) Costos de la semana ----
        c_ten = inv_fin * p.costo_tenencia
        c_ped = p.costo_pedido if reordenar else 0.0
        c_fal = faltante * p.costo_agotamiento
        c_total_sem = c_ten + c_ped + c_fal

        ac_total += c_total_sem
        ac_danadas += cant_danadas

        # ---- 6) Construcción de fila (solo si está en rango o es la última) ----
        en_rango = (j <= semana < rango_fin)
        es_ultima = (semana == N)

        if en_rango or es_ultima:
            fila = (
                semana,
                rnd_dem, demanda,
                inv_fin_prev, "Sí" if llega_pedido else "No",
                rnd_dano, cant_danadas if llega_pedido else "",
                inv_post_arr,
                vendido, faltante,
                inv_fin,
                "Sí" if reordenar else "No",
                rnd_lead, lead_t, sem_arribo,
                "Sí" if pedido_pendiente_prev else "No",
                round(c_ten, 2), round(c_ped, 2),
                round(c_fal, 2), round(c_total_sem, 2),
                round(ac_total, 2), ac_danadas,
            )
            if en_rango:
                visibles.append(fila)
            if es_ultima:
                fila_final = fila

        # ---- 7) Avance de fila (solo conservamos lo mínimo) ----
        inv_fin_prev = inv_fin
        # pedido_pendiente_prev / semana_arribo_prev / cantidad_pedida_pendiente
        # ya quedaron actualizados arriba.

    res = Resultado(
        filas_visibles=visibles,
        fila_final=fila_final,
        parametros=p,
        costo_total=ac_total,
        danadas_total=ac_danadas,
    )
    res.costo_promedio_por_semana = ac_total / N if N else 0.0
    return res


# ---------------------------------------------------------------------------
# Auto-test si se ejecuta como script
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    p = Parametros(n_filas=10_000, mostrar_desde_j=1,
                   mostrar_cantidad_i=10, semilla=42)
    r = simular(p)
    print("Columnas:", COLUMNAS)
    print(f"\nPrimeras {len(r.filas_visibles)} filas:")
    for f in r.filas_visibles:
        print(f)
    print("\nFila N (última):", r.fila_final)
    print(f"\nCosto total acumulado:        ${r.costo_total:,.2f}")
    print(f"Costo promedio por semana:    ${r.costo_promedio_por_semana:,.2f}")
    print(f"Bicicletas dañadas:           {r.danadas_total}")
