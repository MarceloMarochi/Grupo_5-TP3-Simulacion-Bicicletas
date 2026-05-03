# Guía detallada del TP3 — Inventario de Bicicletas

Documento de estudio: explica el código línea por línea y prepara para la defensa oral.

---

## PARTE 1 — Cómo funciona el código

### 1.0 Arquitectura general

El proyecto está dividido en 3 archivos con responsabilidades claras:

```
main.py        → punto de entrada (5 líneas, no hace nada interesante)
gui.py         → interfaz Tkinter (recibe parámetros del usuario, dispara la simulación, muestra resultados)
simulador.py   → motor de simulación (Mersenne Twister + lógica del modelo)
```

La regla de oro es: **el simulador no sabe que existe la GUI**. Se puede correr `python simulador.py` y ver la simulación en consola sin tocar nada gráfico. Esto se llama **separación de responsabilidades** y es lo que permite testear la lógica sin tener que abrir ventanas. La GUI sólo *consume* lo que devuelve el motor.

El flujo de datos en una corrida es:

```
Usuario tipea en los Entry widgets
        ↓
gui._leer_parametros()  →  arma un objeto Parametros (dataclass)
        ↓
simulador.simular(p)    →  itera N semanas, devuelve un objeto Resultado
        ↓
gui._poblar_tabla(r) + gui._actualizar_resumen(r)  →  vuelca a la pantalla
```

---

### 1.1 simulador.py — Lógica de la simulación

#### 1.1.1 La lista `COLUMNAS`

Es la **única fuente de verdad** sobre qué columnas tiene el vector de estado y en qué orden. Tanto el simulador (que arma cada fila como una tupla) como la GUI (que arma el Treeview) la importan. Si querés agregar una columna nueva, la agregás acá una sola vez y todo se ajusta.

#### 1.1.2 Clase `DistribucionDiscreta`

Es el equivalente Python de las tablitas que el profe arma en Excel con columnas `Probab / Acum / Rand Min / Rand Max`. La idea: para muestrear de una distribución discreta, generamos un RND uniforme en [0, 1) y vemos en qué "tramo" cae.

Ejemplo con la demanda de bicicletas:

```
Demanda  Prob   Acumulada    RND Min    RND Max
   0     0.20    0.20         0.000      0.199
   1     0.45    0.65         0.200      0.649
   2     0.25    0.90         0.650      0.899
   3     0.10    1.00         0.900      0.999
```

Si el RND uniforme da `0.7423`, cae entre 0.65 y 0.90 → muestra de demanda = 2.

En el constructor se calcula la acumulada una sola vez (eficiente). El método `muestrear(rnd)` recorre la acumulada con un `for` y devuelve el primer valor cuyo límite supera al RND. Para 4 categorías un `for` es perfecto; si fueran cientos, convendría `bisect.bisect_left` (búsqueda binaria O(log n)).

La validación en el `__init__` (`abs(s - 1.0) > 1e-9`) atrapa errores de tipeo en las probabilidades — por ejemplo si alguien pone 0.20/0.40/0.25/0.10 en vez de 0.20/0.45/0.25/0.10.

El método `tabla()` no se usa en el simulador, queda disponible por si querés mostrar la tabla acumulada en algún panel auxiliar de la GUI.

#### 1.1.3 Dataclass `Parametros`

Un `@dataclass` es una manera concisa de definir una clase contenedora de datos. Reemplaza esto:

```python
class Parametros:
    def __init__(self, cantidad_pedido=5, punto_reorden=2, ...):
        self.cantidad_pedido = cantidad_pedido
        self.punto_reorden = punto_reorden
        ...
```

Por esto:

```python
@dataclass
class Parametros:
    cantidad_pedido: int = 5
    punto_reorden: int = 2
```

Notar `field(default_factory=lambda: [0,1,2,3])` en las listas: eso es porque en Python no se pueden poner listas como default directo de un dataclass (todas las instancias compartirían la misma lista, que es un bug clásico).

#### 1.1.4 Dataclass `Resultado`

Empaqueta todo lo que devuelve la simulación: las filas que se van a mostrar, la fila final (N), los acumuladores y métricas derivadas (`costo_promedio_por_semana`, `nivel_servicio`).

#### 1.1.5 Función `simular(p)` — el corazón

Voy paso por paso.

**Paso A — Inicialización del generador**

```python
rng = random.Random(p.semilla)
```

Crea una instancia local de `random.Random`. Internamente esa clase usa **Mersenne Twister (MT19937)**: el módulo C `_randommodule.c` de CPython lo implementa así. Si `p.semilla` es `None`, Python toma una semilla del sistema (`os.urandom`). Si es un entero, la corrida queda **reproducible**: la misma semilla genera exactamente la misma secuencia. Esto es vital para depurar y para que el profe pueda replicar tus resultados.

Por qué creo una instancia (`random.Random(...)`) en vez de usar `random.seed()` directamente: porque el módulo `random` del nivel global es un singleton compartido. Si la cátedra mañana mete varios simuladores en paralelo, cada uno con su propia semilla, vas a querer instancias separadas. Es la práctica recomendada por la propia documentación de Python.

**Paso B — Estado mínimo en memoria**

```python
inv_fin_prev = p.inventario_inicial
pedido_pendiente_prev = False
semana_arribo_prev = None
cantidad_pedida_pendiente = 0
```

El enunciado pide "trabajar en memoria con 2 filas". Lo cumplimos así: en vez de guardar la fila anterior completa, guardamos sólo lo mínimo que necesita la fila siguiente. Que es: el inventario al cierre, si hay un pedido en tránsito y para cuándo. Eso es 4 variables. Esto es más eficiente que guardar tuplas de 27 elementos y descartarlas.

**Paso C — Loop principal**

Itera de `semana = 1` hasta `N`. En cada iteración:

**Paso 1 — Arribo del pedido**

```python
if pedido_pendiente_prev and semana_arribo_prev == semana:
    llega_pedido = True
    r = rng.random()
    rnd_dano = round(r, 4)
    cant_danadas = dist_dano.muestrear(r)
    inv_post_arr = inv_fin_prev + (cantidad_pedida_pendiente - cant_danadas)
    pedido_pendiente_prev = False
```

Si había un pedido en tránsito y le tocaba llegar esta semana, lo recibimos. Sorteamos cuántas bicis vienen dañadas (0/1/2 con probabilidades 60/30/10). Las dañadas **no entran al inventario** porque "deben ser devueltas bajo garantía sin costo adicional" (textual del enunciado). Por eso `inv_post_arr = inv_fin_prev + Q - dañadas`.

Detalle sutil: el redondeo a 4 decimales con `round(r, 4)` es **sólo para mostrar**. El `r` original (con todos sus decimales) es el que usamos para muestrear. Esto es importante porque si redondeáramos antes de muestrear, los bordes de los tramos empezarían a comportarse mal.

**Paso 2 — Demanda**

```python
r = rng.random()
rnd_dem = round(r, 4)
demanda = dist_demanda.muestrear(r)
```

Igual que arriba pero con la distribución de demanda.

**Paso 3 — Atender demanda**

```python
vendido = min(inv_post_arr, demanda)
faltante = max(0, demanda - inv_post_arr)
inv_fin = inv_post_arr - vendido
```

Lost sales (no backorder): si la demanda excede el stock, el sobrante se pierde y se cobra costo de agotamiento por unidad. No queda como deuda para la próxima semana.

**Paso 4 — Decisión de reorden**

```python
if (inv_fin <= p.punto_reorden) and (not pedido_pendiente_prev):
    reordenar = True
    r = rng.random()
    lead = dist_lead.muestrear(r)
    sem_arribo = semana + lead
    pedido_pendiente_prev = True
```

Política `(s, Q)` clásica: si el stock al cierre cae en o por debajo del punto de reorden Y no hay un pedido ya en tránsito, pedimos Q unidades. La condición de "no hay pedido pendiente" es lo que evita que el sistema acumule pedidos infinitos cuando el stock está bajo varias semanas seguidas.

Convención del lead time: si pido en la semana 5 con `lead = 2`, el pedido llega al inicio de la semana 7 (no de la 6). Eso es lo que hace `sem_arribo = semana + lead`.

**Paso 5 — Costos**

```python
c_ten = inv_fin * p.costo_tenencia
c_ped = p.costo_pedido if reordenar else 0.0
c_fal = faltante * p.costo_agotamiento
```

- Tenencia: sobre el stock al cierre (no se contabiliza el pico post-arribo porque el "costo de tener bicis" se mide por lo que duerme en el depósito al final de la semana).
- Pedido: costo fijo por orden, $200 si pidió, 0 si no.
- Faltante: $50 por cada unidad que no pudimos atender.

**Paso 6 — Construcción de fila**

Sólo se construye la tupla si la semana cae en el rango `[j, j+i)` o si es la última (N). Así es como respetamos "trabajar con 2 filas en memoria": no acumulamos las 100.000 filas, sólo las que se van a mostrar.

**Paso 7 — Avance**

```python
inv_fin_prev = inv_fin
```

El estado de la fila se "condensa" en el `inv_fin` y las variables del pedido pendiente, que ya quedaron actualizadas en el paso 4. La iteración siguiente las consume.

**Paso D — Métricas finales**

```python
res.costo_promedio_por_semana = ac_total / N
res.nivel_servicio = (ac_demanda - ac_falta_u) / ac_demanda
```

El nivel de servicio es la fracción de demanda total que efectivamente atendiste. Es la métrica clave de calidad del servicio en problemas de inventario.

#### 1.1.6 Bloque `if __name__ == "__main__"`

Permite ejecutar `python simulador.py` directamente para una prueba rápida en consola, sin abrir la GUI. Útil para debug.

---

### 1.2 gui.py — Frontend

#### 1.2.1 Constante `ANCHOS`

Diccionario con el ancho en píxeles de cada columna. Los valores fueron tuneados a ojo para que los headers se lean cómodos. Es un detalle de UX, no de lógica.

#### 1.2.2 Clase `App(tk.Tk)`

`tk.Tk` es la ventana principal de Tkinter. Heredamos de ella para que `App` *sea* la ventana, en vez de tener una variable `self.window` aparte. Es el patrón estándar.

**Estilos en el `__init__`**

```python
style.theme_use("clam")
style.configure("Treeview", rowheight=22, font=("Consolas", 9))
style.map("Treeview",
          background=[("selected", "#1e6fff")],
          foreground=[("selected", "white")])
```

- `theme_use("clam")` da un look más moderno (el default de Windows es feo).
- `font=("Consolas", 9)` es monoespaciada → los números se alinean visualmente.
- `style.map` asigna los colores cuando una fila está seleccionada (azul + texto blanco). Como el Treeview persiste la selección al hacer scroll, esto cumple el requisito "se pueda seleccionar (pintar) una fila y que al desplazarse no se pierda la selección".

**Layout: dos paneles con `pack`**

```python
izq.pack(side="left", fill="y")
der.pack(side="right", fill="both", expand=True)
```

El panel izquierdo ocupa sólo lo que necesita en X y se estira en Y. El derecho se queda con todo el espacio restante. Es un layout clásico master-detail.

**Helper `_add_entry`**

Cada fila de parámetro consiste en un `Label` (etiqueta a la izquierda) y un `Entry` (caja de texto a la derecha). Para no copiar/pegar 16 veces el mismo bloque, ese par lo arma `_add_entry` y guarda el `Entry` en `self.entries[clave]` para poder leerlo después.

**Treeview con scrollbars**

```python
self.tree = ttk.Treeview(tabla_frame, columns=COLUMNAS, show="headings", selectmode="extended")
```

- `show="headings"` oculta la columna #0 nativa del árbol (que normalmente sería para íconos jerárquicos) y deja sólo las columnas de datos. Eso hace que los **headers queden fijos** arriba, cumpliendo el requisito "los encabezados queden visibles cuando se haga scroll vertical".
- `selectmode="extended"` permite seleccionar varias filas con Shift/Ctrl.
- Las dos `Scrollbar` (vertical y horizontal) están conectadas con `yscrollcommand`/`xscrollcommand` de un lado y con `command=tree.yview`/`tree.xview` del otro. Eso hace que se sincronicen.
- Uso `grid` dentro del frame de la tabla porque permite poner las dos scrollbars exactamente al lado y abajo. Si usara `pack` se complica.

Treeview es nativo del sistema (lo dibuja el OS, no Tkinter). Por eso **no parpadea al scrollear**: el SO ya optimiza el redraw.

**Tag `final`**

```python
self.tree.tag_configure("final", background="#fff3bf")
```

Cualquier ítem insertado con `tags=("final",)` se pinta amarillo claro. Lo uso para resaltar la fila N (última simulada).

**Atajo Ctrl+C**

```python
self.tree.bind("<Control-c>", self._copiar_seleccion)
```

`_copiar_seleccion` arma un texto con tabs entre columnas y newlines entre filas, y lo pone en el portapapeles con `clipboard_append`. Excel reconoce ese formato como tabla cuando pegás. Cumple el requisito "permita copiar y pegar en Excel".

#### 1.2.3 `_leer_parametros`

Lee todos los `Entry` del panel izquierdo y construye el `Parametros`. El detalle interesante es:

```python
def to_float(k):
    return float(e[k].get().strip().replace(",", "."))
```

Acepta tanto `0.5` como `0,5` (los argentinos típicamente escriben con coma decimal). Pequeño detalle de UX que evita errores molestos.

```python
sem_raw = e["semilla"].get().strip()
semilla = int(sem_raw) if sem_raw else None
```

Si el campo de semilla está vacío, queda `None` → cada corrida es distinta. Si tiene un entero, queda reproducible.

#### 1.2.4 `_on_simular` — Orquestación

1. Lee parámetros (con try/except por si el usuario tipea cualquier cosa).
2. Valida que las distribuciones sumen 1.
3. Cambia el cursor a reloj (`config(cursor="watch")`) para indicar que está trabajando.
4. Llama a `simular(p)`.
5. Vuelca filas al Treeview y arma el resumen.

El `messagebox.showerror` es el cuadro de diálogo nativo del sistema con icono rojo.

#### 1.2.5 `_poblar_tabla`

```python
self.tree.delete(*self.tree.get_children())
for fila in r.filas_visibles:
    self.tree.insert("", "end", values=fila)
```

Borra todo lo viejo, mete las filas nuevas. Si la última fila (N) no cae dentro del rango `[j, j+i)`, la inserta al final separada por una fila de puntos suspensivos, para que siempre se vea cuál fue el cierre.

#### 1.2.6 `_actualizar_resumen`

Construye un texto multi-línea con todos los parámetros usados (cumple "los parámetros ingresados se puedan visualizar luego de realizar la simulación") y los resultados clave: costo total, costo promedio, nivel de servicio, desglose. Lo asigna al `Label` superior.

#### 1.2.7 Función `lanzar()`

```python
def lanzar():
    app = App()
    app.mainloop()
```

`mainloop()` es el evento loop de Tkinter: bloquea, escucha eventos del sistema (clics, teclas), y los despacha a los handlers. Mientras esto corre, la GUI vive.

---

### 1.3 main.py

5 líneas. Importa `lanzar` de `gui` y la ejecuta. Existe sólo porque es convencional tener un punto de entrada llamado `main.py` separado de la lógica.

---

## PARTE 2 — Posibles preguntas en la defensa

Las agrupé por tema. Por cada pregunta, anoté la respuesta corta y, cuando vale la pena, una explicación más larga para anticipar repreguntas.

### A. Sobre Montecarlo en general

**1. ¿Qué es la simulación de Montecarlo?**
Es una técnica para resolver problemas con incertidumbre generando muchas realizaciones aleatorias del sistema y analizando el agregado. Funciona porque la **ley de los grandes números**: el promedio empírico de N realizaciones converge al valor esperado teórico cuando N → ∞.

**2. ¿Por qué usás Montecarlo en este problema y no una solución analítica?**
Porque el sistema tiene tres fuentes de aleatoriedad acopladas (demanda, lead time, daños) y reglas de decisión (umbral de reorden, lost sales) que rompen la linealidad. Una solución cerrada para `E[costo total]` existiría pero requeriría modelar una cadena de Markov con estados (inventario, pedido pendiente, semanas hasta arribo) que se vuelve inmanejable. Montecarlo da el mismo número con mucho menos esfuerzo.

**3. ¿Cuál es la precisión de tu estimación con N = 1000? ¿Y con N = 100.000?**
El error estándar de la media empírica decrece como `1/√N`. Si con N = 1000 tenés un error del 3 %, con N = 100.000 lo bajás a ~0.3 % (10× más muestras → √10 ≈ 3.16× más precisión). Por eso conviene N grande.

**4. ¿Cómo medirías un intervalo de confianza para el costo promedio?**
Correría la simulación M veces (cada vez con semilla distinta), tomaría la media y desvío estándar de esos M costos promedio, y aplicaría un intervalo `media ± 1.96 × desvío/√M` para 95 % de confianza. En el código actual no lo hago, pero es la extensión natural.

### B. Sobre Mersenne Twister

**5. ¿Qué generador de números aleatorios usás?**
**Mersenne Twister con período 2¹⁹⁹³⁷ − 1** (variante MT19937). Es el algoritmo por defecto de la clase `random.Random` en Python — la implementación está en C dentro de CPython, en `_randommodule.c`. La cátedra lo recomienda explícitamente.

**6. ¿Por qué se llama "Mersenne"?**
Por los **primos de Mersenne**: números primos de la forma 2ᵖ − 1. El período del generador es exactamente uno de esos primos, 2¹⁹⁹³⁷ − 1.

**7. ¿Qué propiedades tiene MT19937?**
Período enormemente largo (2¹⁹⁹³⁷ − 1, aproximadamente 10⁶⁰⁰¹), buena equidistribución hasta dimensión 623, pasa la mayoría de los tests estadísticos (Diehard, TestU01 SmallCrush). **Limitación**: no es criptográficamente seguro — si observás 624 valores consecutivos podés predecir todos los siguientes. No es un problema acá porque no estamos haciendo criptografía.

**8. ¿Y si te piden usar otro generador, qué cambiaría?**
Cambiar `rng = random.Random(p.semilla)` por `rng = numpy.random.default_rng(p.semilla)` (que usa PCG64) y reemplazar `rng.random()` por `rng.random()`. La interfaz es prácticamente idéntica. Para usar congruencial lineal lo implementaría a mano: `x_{n+1} = (a·x_n + c) mod m` con `a = 1103515245, c = 12345, m = 2³¹` (los valores de glibc) — es un ejercicio típico.

**9. ¿Por qué usás `random.Random()` en vez de `random.seed()` global?**
Para poder tener generadores independientes si el día de mañana hay simulaciones en paralelo, o si el usuario abre dos simulaciones simultáneas. Es la práctica recomendada por la documentación oficial.

### C. Sobre el modelo

**10. ¿Cómo modelás la demanda no atendida? ¿Lost sales o backorder?**
**Lost sales**: si la demanda excede el stock, lo que falta se pierde y se cobra costo de agotamiento por unidad. No queda como deuda para la próxima semana. Si fuera backorder, debería arrastrar `faltante_acumulado` y restarlo del próximo arribo.

**11. ¿Cuándo arriba un pedido?**
Al **inicio** de la semana `semana_pedido + lead_time`. Si pido al cierre de la semana 5 con lead = 2, al inicio de la semana 7 ya tengo las bicis disponibles para atender la demanda de esa misma semana 7. Sigue la nota explícita del enunciado.

**12. ¿Qué pasa si dos pedidos se solapan?**
No puede pasar en este modelo: la condición `not pedido_pendiente_prev` antes de pedir garantiza que sólo hay un pedido en tránsito a la vez. Es la política `(s, Q)` con un único pedido pendiente.

**13. ¿Cuándo se cobra el costo de tenencia?**
Sobre el `inv_fin` (stock al cierre de cada semana). No sobre el pico post-arribo. Es la convención más común en modelos de inventario semanales.

**14. ¿Cómo tratás las bicicletas dañadas?**
"Deben ser devueltas bajo garantía al proveedor sin costo adicional" (enunciado textual). No entran al inventario ni se contabilizan en el costo de pedido. Sólo aparecen en el acumulador `Ac_Danadas` para reportar.

**15. ¿La política `Q=5, R=2` es óptima?**
No necesariamente. En la corrida con semilla 999 y N=10.000, los costos promedio fueron: Q=3 → $133, Q=5 → $131, Q=8 → $156, Q=10 → $177. Q=5 es bueno pero podría existir otro óptimo si sintonizamos R también. Para encontrarlo correría una grilla `(Q, R)` y elegiría el par con menor costo promedio.

**16. ¿Por qué la fórmula `inv_post_arr = inv_fin_prev + (Q - dañadas)`?**
Porque al inicio de la semana ingreso `Q` unidades pedidas, pero `dañadas` se devuelven inmediatamente al proveedor → no entran al inventario.

### D. Sobre la implementación Python

**17. ¿Por qué dataclass en vez de una clase normal?**
Menos boilerplate. `@dataclass` autogenera `__init__`, `__repr__` y `__eq__`. Para un objeto que es básicamente un contenedor de datos, es más limpio.

**18. ¿Qué hace `field(default_factory=lambda: [...])` ?**
Es la manera de tener listas como default en un dataclass. No se puede poner `valores: list = [0,1,2,3]` directamente porque todas las instancias compartirían **la misma** lista (mutable default argument bug — un clásico de Python). El `default_factory` crea una lista nueva por instancia.

**19. ¿Por qué redondeás los RND a 4 decimales?**
Sólo para mostrarlos en la tabla. El valor original (con todos los decimales que da Python, ~17 dígitos en double) es el que se usa para muestrear la distribución. Redondear antes de muestrear introduciría sesgo en los bordes.

**20. Si la lista de columnas tiene 27 elementos, ¿no es lento construir tuplas tan grandes?**
No. Crear una tupla de 27 elementos en Python es del orden de microsegundos. El cuello de botella real, si lo hubiera, sería el `print` o el `tree.insert`, no la tupla. Y en la versión actual sólo construyo la tupla cuando la fila va a mostrarse — la mayoría de las semanas no la armo.

**21. ¿Qué complejidad tiene el algoritmo?**
**O(N)** en tiempo (un loop sobre las semanas) y **O(i)** en memoria (sólo guardamos las `i` filas a mostrar más constantes). Por eso N=100.000 corre en ~0.3 s sin que la memoria se dispare.

**22. ¿Por qué `min` y `max` para vendido/faltante?**
`min(inv, demanda)` es lo que se vende (limitado por lo que tengo o lo que piden, lo que sea menor). `max(0, demanda - inv)` blinda contra negativos: si la demanda es menor al inventario, `demanda - inv` es negativo, y queremos faltante = 0.

### E. Sobre la GUI

**23. ¿Por qué Tkinter y no PyQt?**
Tkinter viene **incluido** en la instalación estándar de Python (Windows y macOS). Cero instalaciones para el profe. PyQt es más lindo pero requiere `pip install` y tiene licencia GPL/comercial.

**24. ¿Cómo cumplís "que la pantalla no parpadee al scrollear"?**
Usando `ttk.Treeview`, que es un widget **nativo del sistema operativo**: el OS decide cómo redibujarlo, con doble buffering automático. Si hubiera implementado la tabla a mano con un `Canvas` y `for i, fila in enumerate(...): canvas.create_text(...)`, ahí sí parpadearía.

**25. ¿Cómo se mantienen los headers fijos al scrollear?**
El Treeview separa internamente el header del cuerpo. El header está en una región diferente del widget que no se afecta por el `yview` del cuerpo. Es comportamiento por default cuando usás `show="headings"`.

**26. ¿Por qué el panel de parámetros está a la izquierda y no arriba?**
Convención de aplicaciones de simulación: parámetros a la izquierda (controles), output a la derecha (datos). Maximiza el espacio horizontal para la tabla, que es donde van las 27 columnas. Si los parámetros estuvieran arriba ocuparían 200px verticales que no podría usar la tabla.

**27. Si N = 100.000, ¿no querés mostrar las 100.000 filas?**
No. Tkinter Treeview puede mostrarlas, pero (a) es lento de cargar (~10 s), (b) es inútil para el usuario que no va a leer 100k filas. Por eso el enunciado pide `i` filas desde `j` + la fila final. Eso muestra el comportamiento al inicio, en una ventana arbitraria, y al final.

**28. ¿Qué pasa si tipean "abc" en un parámetro numérico?**
El `int(...)` o `float(...)` levanta `ValueError`. Lo capturo en `_on_simular` con un `try/except` y muestro un `messagebox.showerror` con un mensaje legible. El usuario corrige y reintenta.

### F. Validación y verificación

**29. ¿Cómo verificás que el simulador es correcto?**
Cuatro frentes:
1. **Distribuciones empíricas**: muestreé 100.000 demandas y obtuve frecuencias dentro del 0.2 % de las teóricas (0.20/0.45/0.25/0.10).
2. **Invariantes**: en una corrida de 50.000 semanas, verifico que `vendido + faltante = demanda`, `inv_fin = inv_post_arr - vendido`, `inventario ≥ 0` siempre. Cero errores.
3. **Acumuladores**: el `Ac_Costo_Tot` de la fila N coincide con `r.costo_total` retornado.
4. **Reproducibilidad**: dos corridas con la misma semilla dan el mismo costo total.

**30. ¿Cómo sabés que la GUI muestra lo que el simulador calcula?**
Porque la GUI no transforma los datos — sólo los rendea. La fila que aparece en el Treeview es exactamente la tupla que armó `simular()`. Si comparás visualmente la última fila de la GUI con el `print(r.fila_final)` de la consola, deberían coincidir.

### G. Diseño y eficiencia

**31. ¿Qué cambiarías si tuvieras que correr N = 10 millones?**
Tres cosas:
1. Reescribir el loop interno con NumPy: pre-generar los arrays de RND con `rng.random(N)` y vectorizar las operaciones. Eso debería bajar de minutos a segundos.
2. Si la GUI es opcional, quitarla y correr headless.
3. Si quiero seguir reportando filas visibles, las muestreo cada `N/1000` para mantener el output manejable.

**32. ¿Tu programa es thread-safe?**
No, ni hace falta. Tkinter no es thread-safe (su mainloop es single-threaded), y la simulación es bloqueante. Si quisiera no congelar la GUI durante una corrida grande, movería `simular()` a un `threading.Thread` y la GUI se actualizaría con `root.after(...)` cuando termine.

**33. ¿Cómo extenderías el modelo a múltiples productos?**
Cambio el estado de un escalar a un dict `inv = {producto_a: 7, producto_b: 3, ...}` y el loop muestrearía demanda por producto. La política de pedido se vuelve por-producto. Las distribuciones serían un dict de `DistribucionDiscreta` por producto. Es lineal en cambios.

**34. ¿Y si la demanda no fuera independiente entre semanas (correlacionada)?**
Reemplazaría el muestreo IID por una cadena de Markov: en vez de `dist_demanda.muestrear(rnd)`, sería `matriz_transicion[demanda_anterior].muestrear(rnd)`. El estado mínimo en memoria crecería en una variable más.

### H. Trampas frecuentes

**35. "El profe te va a preguntar si esto realmente es Montecarlo o sólo simulación discreta"**
Montecarlo es **un caso particular** de simulación: aquella que usa muestreo aleatorio para estimar cantidades. Sí, esto es Montecarlo. La distinción más fina sería: simulación de **eventos discretos** (donde el reloj salta al próximo evento — ej. cola de banco con tiempos de llegada exponenciales) vs simulación con **tiempo discreto fijo** (avanza semana a semana, lo que hace acá). Ambas pueden ser Montecarlo si el origen de la incertidumbre es aleatorio.

**36. "¿No te conviene avanzar por eventos en vez de por semana?"**
En este problema no, porque la unidad natural del modelo es la semana (la demanda se especifica como demanda semanal, los costos son semanales). Un avance por eventos sería más eficiente si los eventos fueran raros (ej. fallas de máquina cada N días) — acá hay un evento cada semana garantizado, así que el `for semana in range(N)` es la forma natural.

**37. "¿Por qué no usás `numpy.random` directamente?"**
Porque la cátedra recomendó MT19937 y `random.Random()` ya lo implementa, sin agregar dependencias externas. NumPy también ofrece MT19937 (`numpy.random.MT19937`) y daría exactamente la misma secuencia con la misma semilla — pero requiere `pip install numpy`. Para este TP no agrega valor.

**38. "Tu nivel de servicio da ~91 %. ¿Es bueno?"**
Para un nivel de servicio "objetivo" del 95 % en retail, está por debajo. Significa que tu política `Q=5, R=2` deja al cliente sin atender el 9 % de las veces que vino con demanda. Si la empresa quiere subir ese número, debe subir R (pedir antes) o bien aceptar que más stock significa más costo de tenencia. Es un trade-off típico.

---

## Tips para la defensa

- Llevá impreso el código (3 archivos, ~25 páginas) por si te piden señalar algo.
- Tené en mente los **3 números clave**: ~$131 costo promedio/semana, ~91 % nivel de servicio, ~12.800 dañadas en 100k semanas. Si los memorizás, suena natural.
- Si te preguntan algo que no sabés: "no lo verifiqué pero esperaría que..." es mejor que inventar. La cátedra valora la honestidad.
- Si te piden modificar algo en vivo (cambiar R, agregar una columna), conocé los 3 puntos donde tocar: `Parametros` (default), GUI (Entry), `simular` (lógica).
