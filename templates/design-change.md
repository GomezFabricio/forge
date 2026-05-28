# Diseño técnico: {nombre del cambio}

> Documento técnico vivo. Crece durante `/fg-design` (estructura inicial) e `/fg-implement` (decisiones que surgen + tareas tachadas).
> Audiencia: ingeniero trabajando en el cambio o reviewer técnico.
> La portada conceptual para humano no-técnico está en `README.md` en esta misma carpeta.

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

## Checklist de tareas

<!--
Generado por /fg-design. Tachado durante /fg-implement.

Reglas:
- Cada tarea debe ser ejecutable en una pasada de TDD (RED → GREEN → TRIANGULATE → REFACTOR).
- Granularidad útil: ni demasiado fino (1 línea), ni demasiado grueso (todo el cambio).
- Cada tarea describe un comportamiento testeable.
- Orden lógico: dependencias primero, integración al final.

Ejemplo:
- [ ] Schema de tabla users con migración SQL
- [ ] Función pura de hashing de password (bcrypt)
- [ ] Función pura de validación de credenciales
- [ ] Endpoint POST /login (happy path)
- [ ] Endpoint POST /login: manejo de credenciales inválidas (401)
- [ ] Endpoint POST /login: manejo de usuario ya autenticado
- [ ] Integration test del flujo completo
-->

- [ ] Tarea 1
- [ ] Tarea 2

## Decisiones técnicas

<!--
Generado por /fg-design (decisiones iniciales) y actualizado por /fg-implement (decisiones que surgen).

Formato: una entrada por decisión.
- YYYY-MM-DD: <qué se decidió> porque <razón>.

Ejemplo:
- 2026-05-26: Usamos bcrypt sobre argon2. Razón: bcrypt ya está en el proyecto y satisface el threat model interno; argon2 traería dependencia nueva sin beneficio claro acá.
- 2026-05-26: El endpoint devuelve 401 (no 403) cuando las credenciales son inválidas. Razón: convención REST estándar — 401 es "no autenticado", 403 es "autenticado pero sin permiso".
- 2026-05-27 (durante /fg-implement): Decidimos usar una tabla `users` separada en vez de extender la existente `accounts`. Razón: durante la implementación quedó claro que el modelo de `accounts` mezcla conceptos que vamos a querer separar más adelante.
-->
