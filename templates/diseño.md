# Diseño técnico: {nombre del cambio}

> Documento técnico estable. Generado por `/fg-design` a partir del `README.md` del cambio.
> Audiencia: ingeniero trabajando en el cambio o reviewer técnico.
> La portada conceptual para humano no-técnico está en `README.md` en esta misma carpeta.
>
> **Inmutable después de `/fg-design`**: este archivo NO se modifica durante `/fg-implement`.
> Las decisiones que surjan durante el código se registran en `decisiones.md` (append-only).

## Enfoque

<!--
Generado por /fg-design.
Estrategia general del cambio. 2-4 párrafos.

Incluir:
- Approach técnico de alto nivel (qué se va a hacer, no cómo línea por línea).
- Librerías o tools que se usan y por qué (atado a lo que ya existe en el proyecto).
- Patrones que se siguen (referencia a módulos existentes que sirven de espejo).

Ejemplo:
"Agregar un módulo `auth/` independiente con un servicio de login y otro de hashing.
Usamos bcrypt (ya está en el proyecto) sobre argon2. El endpoint sigue el patrón
de `users/` para mantener consistencia con el resto de la API."
-->

## Arquitectura

<!--
Generado por /fg-design.
Cómo el cambio se integra con el sistema existente.

Incluir cuando aplica:
- Diagrama mermaid si el cambio cruza varios módulos.
- Contratos de interfaz (signatures, schemas de endpoints, payloads).
- Diagrama de secuencia para flujos no triviales.

Si el cambio es chico y se integra de forma obvia, decirlo en una línea y avanzar.
-->

## Archivos afectados

<!--
Generado por /fg-design con información de CodeGraph.
NO inventar — usar el grafo estructural ya indexado.

Formato:
- path/al/archivo.ext            (nuevo | modificado | eliminado)
- breve nota si vale la pena

Ejemplo:
- src/auth/login.py              (nuevo)
- src/auth/hashing.py            (nuevo)
- src/api/routes.py              (modificado) — registra el endpoint nuevo
- tests/auth/test_login.py       (nuevo)
- tests/auth/test_hashing.py     (nuevo)
- migrations/004_users.sql       (nuevo)
-->
