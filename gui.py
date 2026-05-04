"""
TP3 - GUI con Tkinter + ttk.Treeview.

Cumple los requisitos del documento de Consideraciones:
    - Interfaz gráfica (no modo caracter).
    - Scroll horizontal y vertical.
    - Sin paginación (todas las filas una debajo de otra).
    - Sin parpadeo al hacer scroll (Treeview es nativo).
    - Encabezados de columna fijos al hacer scroll vertical.
    - Selección de fila persistente al desplazarse.
    - Soporta copiar/pegar a Excel (Ctrl+C copia las filas seleccionadas).

Y los del enunciado del TP3 (grupo amarillo):
    - Permite ingresar todas las variables marcadas en rojo como parámetros.
    - Muestra los parámetros una vez ejecutada la simulación.
    - Soporta N >= 100.000.
    - Trabaja en memoria con 2 filas (lo hace el simulador).
    - Muestra i iteraciones desde la fila j + la fila N (última).
    - Todos los acumuladores aparecen como columnas.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from simulador import COLUMNAS, Parametros, simular


# Anchos por columna (caracteres aprox.)
ANCHOS = {
    "Semana": 70,
    "RND_Dem": 75, "Demanda": 70,
    "Inv_Ini": 70, "Llega_Ped": 75,
    "RND_Danadas": 90, "Danadas": 70,
    "Inv_PostArr": 85,
    "Vendido": 70, "Faltante": 70,
    "Inv_Final": 75, "Ordenar_Ped": 85,
    "RND_Demora": 85, "Demora": 65, "Sem_Arribo": 85,
    "Ped_Pend": 75,
    "C_Mantenimiento": 110, "C_Pedido": 80, "C_Faltante": 90, "C_Total_Sem": 95,
    "Ac_Costo_Tot": 110, "Ac_Danadas": 95,
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TP3 — Simulación Montecarlo · Inventario de Bicicletas")
        self.geometry("1480x820")
        self.minsize(1100, 650)

        # Estilos: fila pintada al seleccionarla (queda visible al scrollear)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=22, font=("Consolas", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", "#1e6fff")],
                  foreground=[("selected", "white")])

        self._construir_layout()
        self._ultimo_resultado = None

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------
    def _construir_layout(self):
        # Contenedor izquierdo con scroll vertical
        sidebar_outer = ttk.Frame(self)
        sidebar_outer.pack(side="left", fill="y")

        _vsb_sidebar = ttk.Scrollbar(sidebar_outer, orient="vertical")
        _vsb_sidebar.pack(side="right", fill="y")

        _canvas_sidebar = tk.Canvas(
            sidebar_outer, highlightthickness=0, yscrollcommand=_vsb_sidebar.set
        )
        _canvas_sidebar.pack(side="left", fill="both", expand=True)
        _vsb_sidebar.config(command=_canvas_sidebar.yview)

        izq = ttk.Frame(_canvas_sidebar, padding=10)
        _cw = _canvas_sidebar.create_window((0, 0), window=izq, anchor="nw")

        def _sync_scroll(event=None):
            _canvas_sidebar.configure(scrollregion=_canvas_sidebar.bbox("all"))

        def _sync_width(event):
            _canvas_sidebar.itemconfig(_cw, width=event.width)

        izq.bind("<Configure>", _sync_scroll)
        _canvas_sidebar.bind("<Configure>", _sync_width)

        def _on_mousewheel(event):
            _canvas_sidebar.yview_scroll(int(-1 * (event.delta / 120)), "units")

        _canvas_sidebar.bind("<Enter>", lambda e: _canvas_sidebar.bind_all("<MouseWheel>", _on_mousewheel))
        _canvas_sidebar.bind("<Leave>", lambda e: _canvas_sidebar.unbind_all("<MouseWheel>"))

        ttk.Label(izq, text="PARÁMETROS", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Separator(izq, orient="horizontal").pack(fill="x", pady=(2, 8))

        self.entries = {}

        def add_grupo(titulo):
            f = ttk.LabelFrame(izq, text=titulo, padding=8)
            f.pack(fill="x", pady=4)
            return f

        # --- Política ---
        f = add_grupo("Política de inventario")
        self._add_entry(f, "Cantidad a pedir (Q)", "cantidad_pedido", "5")
        self._add_entry(f, "Punto de Reposición (R)", "punto_reorden", "2")
        self._add_entry(f, "Inventario inicial",   "inventario_inicial", "7")

        # --- Costos ---
        f = add_grupo("Costos")
        self._add_entry(f, "Mantenimiento ($/u/sem)", "costo_tenencia", "30")
        self._add_entry(f, "Pedido ($/orden)",     "costo_pedido", "200")
        self._add_entry(f, "Faltante ($/u)",        "costo_agotamiento", "50")

        # --- Distribuciones ---
        f = add_grupo("Demanda semanal — P(D=v)")
        self._add_entry(f, "P(D=0)", "p_dem_0", "0.20")
        self._add_entry(f, "P(D=1)", "p_dem_1", "0.45")
        self._add_entry(f, "P(D=2)", "p_dem_2", "0.25")
        self._add_entry(f, "P(D=3)", "p_dem_3", "0.10")

        f = add_grupo("Demora (semanas)")
        self._add_entry(f, "P(S=1)", "p_lead_1", "0.30")
        self._add_entry(f, "P(S=2)", "p_lead_2", "0.40")
        self._add_entry(f, "P(S=3)", "p_lead_3", "0.30")

        f = add_grupo("Daños al recibir pedido")
        self._add_entry(f, "P(0 dañadas)", "p_dano_0", "0.60")
        self._add_entry(f, "P(1 dañada)",  "p_dano_1", "0.30")
        self._add_entry(f, "P(2 dañadas)", "p_dano_2", "0.10")

        # --- Control ---
        f = add_grupo("Control de simulación")
        self._add_entry(f, "N (filas a simular)",         "n_filas", "1000")
        self._add_entry(f, "j (mostrar desde fila)",      "mostrar_desde_j", "1")
        self._add_entry(f, "i (cantidad a mostrar)",      "mostrar_cantidad_i", "50")
        self._add_entry(f, "Semilla (vacío = aleatoria)", "semilla", "")

        ttk.Button(izq, text="Simular ▶", command=self._on_simular).pack(
            fill="x", pady=(10, 4))
        ttk.Button(izq, text="Limpiar", command=self._on_limpiar).pack(fill="x")

        # ----- Frame derecha: tabla + resumen -----
        der = ttk.Frame(self, padding=(0, 10, 10, 10))
        der.pack(side="right", fill="both", expand=True)

        # Resumen arriba
        self.lbl_resumen = ttk.Label(
            der, text="Esperando simulación…",
            font=("Consolas", 10), justify="left", anchor="w"
        )
        self.lbl_resumen.pack(fill="x", pady=(0, 6))

        # Frame de tabla con scrollbars
        tabla_frame = ttk.Frame(der)
        tabla_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            tabla_frame,
            columns=COLUMNAS,
            show="headings",
            selectmode="extended",
        )
        for col in COLUMNAS:
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=ANCHOS.get(col, 80),
                             anchor="center", stretch=False)

        vsb = ttk.Scrollbar(tabla_frame, orient="vertical",
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(tabla_frame, orient="horizontal",
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tabla_frame.rowconfigure(0, weight=1)
        tabla_frame.columnconfigure(0, weight=1)

        # Tag para resaltar la fila final (N)
        self.tree.tag_configure("final", background="#fff3bf")

        # Ctrl+C → copiar al portapapeles en formato tabular (se pega en Excel)
        self.tree.bind("<Control-c>", self._copiar_seleccion)
        self.tree.bind("<Control-C>", self._copiar_seleccion)

    def _add_entry(self, parent, label, key, default):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=label, width=22).pack(side="left")
        e = ttk.Entry(row, width=10)
        e.insert(0, default)
        e.pack(side="right")
        self.entries[key] = e

    # ------------------------------------------------------------------
    # ACCIONES
    # ------------------------------------------------------------------
    def _leer_parametros(self) -> Parametros:
        e = self.entries
        def to_int(k):   return int(e[k].get().strip())
        def to_float(k): return float(e[k].get().strip().replace(",", "."))

        p_dem  = [to_float(f"p_dem_{i}")  for i in range(4)]
        p_lead = [to_float(f"p_lead_{i}") for i in (1, 2, 3)]
        p_dano = [to_float(f"p_dano_{i}") for i in range(3)]

        sem_raw = e["semilla"].get().strip()
        semilla = int(sem_raw) if sem_raw else None

        p = Parametros(
            cantidad_pedido=to_int("cantidad_pedido"),
            punto_reorden=to_int("punto_reorden"),
            inventario_inicial=to_int("inventario_inicial"),
            costo_tenencia=to_float("costo_tenencia"),
            costo_pedido=to_float("costo_pedido"),
            costo_agotamiento=to_float("costo_agotamiento"),
            demanda_valores=[0, 1, 2, 3], demanda_probs=p_dem,
            lead_valores=[1, 2, 3],       lead_probs=p_lead,
            dano_valores=[0, 1, 2],       dano_probs=p_dano,
            n_filas=to_int("n_filas"),
            mostrar_desde_j=to_int("mostrar_desde_j"),
            mostrar_cantidad_i=to_int("mostrar_cantidad_i"),
            semilla=semilla,
        )
        return p

    def _on_simular(self):
        try:
            p = self._leer_parametros()
        except (ValueError, KeyError) as ex:
            messagebox.showerror("Parámetro inválido",
                                 f"Revisá los parámetros: {ex}")
            return

        # Validaciones rápidas
        for nombre, vec in (("Demanda", p.demanda_probs),
                            ("Lead time", p.lead_probs),
                            ("Daños", p.dano_probs)):
            s = sum(vec)
            if abs(s - 1.0) > 1e-6:
                messagebox.showerror(
                    "Distribución inválida",
                    f"Las probabilidades de {nombre} suman {s:.4f}, deben sumar 1.")
                return
        if p.n_filas <= 0:
            messagebox.showerror("Parámetro inválido", "N debe ser > 0")
            return

        # Cursor reloj durante la simulación
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            r = simular(p)
        except Exception as ex:
            self.config(cursor="")
            messagebox.showerror("Error en simulación", str(ex))
            return
        self.config(cursor="")

        self._ultimo_resultado = r
        self._poblar_tabla(r)
        self._actualizar_resumen(r)

    def _on_limpiar(self):
        self.tree.delete(*self.tree.get_children())
        self.lbl_resumen.config(text="Esperando simulación…")

    def _poblar_tabla(self, r):
        # Limpio
        self.tree.delete(*self.tree.get_children())

        # Inserción en bloque (rápido)
        for fila in r.filas_visibles:
            self.tree.insert("", "end", values=fila)

        # Si la última fila no estaba en el rango, la inserto al final con tag
        ultima_en_rango = (
            r.filas_visibles
            and r.filas_visibles[-1][0] == r.fila_final[0]
        )
        if not ultima_en_rango and r.fila_final is not None:
            # Separador visual
            self.tree.insert("", "end",
                             values=tuple("..." for _ in COLUMNAS))
            self.tree.insert("", "end", values=r.fila_final, tags=("final",))
        elif ultima_en_rango:
            # Re-tag de la última fila visible
            children = self.tree.get_children()
            if children:
                self.tree.item(children[-1], tags=("final",))

    def _actualizar_resumen(self, r):
        p = r.parametros
        sem_str = "aleatoria" if p.semilla is None else str(p.semilla)
        txt = (
            f"PARÁMETROS USADOS:  Q={p.cantidad_pedido}  R={p.punto_reorden}  "
            f"I0={p.inventario_inicial}  |  Costos: ten=${p.costo_tenencia:g} "
            f"ped=${p.costo_pedido:g} fal=${p.costo_agotamiento:g}  |  "
            f"N={p.n_filas:,}  mostrar i={p.mostrar_cantidad_i} desde j={p.mostrar_desde_j}  "
            f"|  Semilla: {sem_str}\n"
            f"RESULTADOS:  Costo total = ${r.costo_total:,.2f}   "
            f"Promedio costo/sem = ${r.costo_promedio_por_semana:,.2f}   "
            f"Total bicis dañadas = {r.danadas_total:,}"
        )
        self.lbl_resumen.config(text=txt)

    def _copiar_seleccion(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        lineas = ["\t".join(COLUMNAS)]
        for iid in sel:
            vals = self.tree.item(iid, "values")
            lineas.append("\t".join(str(v) for v in vals))
        texto = "\n".join(lineas)
        self.clipboard_clear()
        self.clipboard_append(texto)


def lanzar():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    lanzar()
