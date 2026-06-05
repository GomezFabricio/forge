# Exploración: {nombre del cambio}

> Mapa del cambio. Generado por `/fg-explore` a partir de los MCP tools de CodeGraph.
> Audiencia: ingeniero trabajando en el cambio, reviewer técnico, y el portero de `/fg-plan`.
>
> **Artefacto reutilizable**: `/fg-design` lo usa como fuente primaria antes de re-consultar CodeGraph.
> Re-correr `/fg-explore` actualiza este mapa (con confirmación del dev).

<!-- sección 1: área del cambio -->
## 1. Área del cambio

<!--
Resumen semántico del área que toca el cambio.
Fuente: mcp__codegraph__codegraph_explore — exploración semántica de la descripción del cambio.

Incluir:
- Módulos y subsistemas principales involucrados.
- Descripción del dominio afectado en 2-4 oraciones.
- Si CodeGraph no está disponible: "[sin datos — CodeGraph no disponible]".
-->

[sin datos — CodeGraph no disponible]

<!-- sección 2: archivos afectados reales -->
## 2. Archivos afectados reales

<!--
Paths concretos con marca nuevo / modificado / eliminado.
Fuente: mcp__codegraph__codegraph_files + mcp__codegraph__codegraph_search + mcp__codegraph__codegraph_node.
NO usar grep textual — usar el grafo estructural ya indexado.

Formato:
- path/al/archivo.ext            (nuevo | modificado | eliminado)
- breve nota si el rol del archivo no es obvio

Si CodeGraph no está disponible: "[sin datos — CodeGraph no disponible]".
-->

[sin datos — CodeGraph no disponible]

<!-- sección 3: consumidores / blast radius -->
## 3. Consumidores / blast radius

<!--
Quién llama o depende de lo que se va a tocar.
Fuente: mcp__codegraph__codegraph_callers + mcp__codegraph__codegraph_impact.

Incluir:
- Lista de consumidores directos de los símbolos afectados.
- Estimación del blast radius transitivo (cuántos módulos se ven impactados indirectamente).
- Tabla o lista con: símbolo afectado → consumidores directos → nivel de impacto.

Si mcp__codegraph__codegraph_callers o mcp__codegraph__codegraph_impact falla:
"[no disponible — error en mcp__codegraph__codegraph_callers]"
Si CodeGraph no está indexado: "[sin datos — CodeGraph no disponible]".
-->

[sin datos — CodeGraph no disponible]

<!-- sección 4: acoplamientos no obvios / dependencias ocultas -->
## 4. Acoplamientos no obvios / dependencias ocultas

<!--
Dependencias que el análisis inicial no contemplaba — el criterio de "modo exposición".
Fuente: mcp__codegraph__codegraph_callers + mcp__codegraph__codegraph_impact + mcp__codegraph__codegraph_callees.

Criterio de detección:
- Un símbolo tiene consumidores via _callers/_impact que NO estaban en el alcance inicial del README.
- Un archivo parece no afectado por nombre pero sí por dependencia estructural.
- Módulos transversales (config, logging, auth) que aparecen en el blast radius.

Documentar cada dependencia oculta encontrada:
- Símbolo/módulo no contemplado → razón por la que sí está afectado.

Si no se detectan acoplamientos ocultos: "Ninguno detectado con el nivel actual de análisis."
Si CodeGraph no está disponible: "[sin datos — CodeGraph no disponible]".
-->

[sin datos — CodeGraph no disponible]

<!-- sección 5: señales fuertes -->
## 5. Señales fuertes (para el portero)

<!--
Bloque estructurado consumido por el portero de /fg-plan (paso 0.5b) para decidir el nivel de ceremonia.
Los 4 campos son obligatorios — bajo degradación, usar los valores conservadores indicados.
-->

<!-- señales_fuertes: inicio -->
```yaml
consumidores: 0          # entero — número de consumidores directos detectados por _callers/_impact; 0 si CodeGraph no disponible
blast_radius: desconocido  # chico | mediano | grande | desconocido (cuando CodeGraph no disponible)
toca_transversales: false  # true | false — si el cambio toca módulos de uso transversal (config, auth, logging, etc.)
nivel_sugerido: completo   # rapido | completo — conservador cuando hay duda o CodeGraph no disponible
```
<!-- señales_fuertes: fin -->

<!--
Criterios para blast_radius:
- chico:    ≤ 3 consumidores directos y ningún módulo transversal
- mediano:  4-10 consumidores directos o 1 módulo transversal
- grande:   > 10 consumidores directos o ≥ 2 módulos transversales o impacto transitivo amplio

Criterios para nivel_sugerido:
- rapido:   blast_radius=chico AND toca_transversales=false AND consumidores ≤ 3
- completo: cualquier otra combinación, o CodeGraph no disponible (conservador)
-->

<!-- sección 6: resumen de riesgo -->
## 6. Resumen de riesgo

<!--
Síntesis breve del riesgo técnico detectado en esta exploración.
Combinar los hallazgos de las secciones 3, 4, y 5.

Incluir:
- Nivel de riesgo general: bajo | medio | alto.
- 2-4 oraciones explicando el principal factor de riesgo (o la ausencia de riesgos).
- Si hay dependencias ocultas de sección 4, mencionarlas.
- Si CodeGraph no está disponible: aclarar que el riesgo es desconocido y recomendar nivel "completo".

Ejemplo:
"Riesgo medio. El cambio toca el módulo de autenticación (transversal), con 6 consumidores
directos detectados. No se encontraron dependencias ocultas. Se recomienda nivel completo."
-->

[sin datos — CodeGraph no disponible]
