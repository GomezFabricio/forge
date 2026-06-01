# Decisiones técnicas: {nombre del cambio}

> Registro append-only de decisiones técnicas del cambio.
> **NUNCA sobrescribir este archivo** — solo agregar entradas al final.
> Generado inicialmente por `/fg-design`; ampliado por `/fg-implement` cuando surgen decisiones durante el código.

## Decisiones técnicas

<!--
Formato: una entrada por decisión. Agregar SIEMPRE al final — nunca editar ni borrar entradas anteriores.

- YYYY-MM-DD: <qué se decidió> porque <razón>.

Ejemplo:
- 2026-05-26: Usamos bcrypt sobre argon2. Razón: bcrypt ya está en el proyecto y satisface
  el threat model interno; argon2 traería dependencia nueva sin beneficio claro acá.
- 2026-05-26: El endpoint devuelve 401 (no 403) cuando las credenciales son inválidas.
  Razón: convención REST estándar — 401 es "no autenticado", 403 es "autenticado pero sin permiso".
- 2026-05-27 (durante /fg-implement): Decidimos usar una tabla `users` separada en vez de extender
  la existente `accounts`. Razón: durante la implementación quedó claro que el modelo de `accounts`
  mezcla conceptos que vamos a querer separar más adelante.
-->
