---
structural: false
estado: planeado
---

# {YYYY-MM}-{tipo}-{nombre}

> Portada del cambio. Audiencia: humano no-técnico, dev nuevo al proyecto, o vos mismo dentro de seis meses.
> Para el detalle técnico, ver `diseño.md` (enfoque y arquitectura), `tareas.md` (checklist) y `decisiones.md` (decisiones técnicas) en esta misma carpeta.

## Qué

<!--
Generado por /fg-plan.
1-2 párrafos describiendo qué problema resuelve este cambio.
Lenguaje claro, sin jerga innecesaria. Pensar en alguien que abre este archivo sin contexto previo.
-->

## Por qué

<!--
Generado por /fg-plan.
Contexto que motivó el cambio: pedido del usuario, bug detectado, deuda técnica, decisión de producto.
Si hay un ticket o conversación, mencionarlo brevemente.
-->

## Alcance

<!--
Generado por /fg-plan.
Qué entra explícitamente en este cambio y qué queda afuera.
Listar lo que NO entra ayuda tanto como listar lo que SÍ entra — evita scope creep.

Ejemplo:
- Entra: endpoint POST /login con validación de credenciales.
- Entra: hashing seguro de password con bcrypt.
- NO entra: recuperación de contraseña (será otro cambio).
- NO entra: integración con OAuth (será otro cambio).
-->

## Restricciones

<!--
Generado por /fg-plan.
Limitaciones técnicas, de tiempo, de dependencias con otros equipos.

Ejemplos:
- Compatible con BD existente (Postgres 14), no migrar a versión nueva.
- Tiene que coexistir con el sistema legacy de sesiones por cookie.
- Fecha tope: necesario antes del release del 30 de mayo.
-->

## Estado

<!--
Actualizado automáticamente por /fg-design, /fg-implement, /fg-review.
Valores posibles: planeado | diseñado | implementando | implementado | cerrado
-->

planeado

## Cierre

<!--
Generado por /fg-review al cerrar el cambio.
Esta sección queda vacía hasta que /fg-review la complete.

Va a incluir:
- Resumen de lo que quedó hecho (scope final).
- Diferimientos: lo que se decidió mover a otros cambios.
- Resultado de cada role invocado (code-reviewer, security-reviewer, etc.).
- Resumen TDD: tests pasados, assertion quality, coverage.
- Si es estructural, indicación de si se corrió /fg-update-arch.
-->
