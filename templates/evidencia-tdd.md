# Evidencia TDD: {nombre del cambio}

> Registro de evidencia del ciclo Strict TDD por tarea.
> Generado automáticamente por `/fg-implement` al cerrar cada batch.
> Si el cambio requirió múltiples batches, las filas se mergean — **no se sobreescriben**.
> Fuente primaria para la validación TDD en `/fg-review`.

## Evidencia del ciclo TDD

| Tarea | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|-------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `path/test.ext` | Unit | ✅ 5/5 | ✅ Escrito | ✅ Pasó | ✅ 3 cases | ✅ Limpio |
| 1.2 | `path/test.ext` | Integration | N/A (new) | ✅ Escrito | ✅ Pasó | ➖ Single | ✅ Limpio |

<!--
Definición de columnas:
- Safety Net: tests pre-existentes corridos antes de modificar archivos. "N/A (new)" para archivos nuevos.
- RED:        test escrito primero, referencia código que no existe aún. Siempre "✅ Escrito".
- GREEN:      tests ejecutados y pasando después de la implementación mínima. "✅ Pasó".
- TRIANGULATE: test cases adicionales para forzar lógica real. "✅ N cases" o "➖ Single" si el spec tiene un solo scenario.
- REFACTOR:  código mejorado con tests aún pasando. "✅ Limpio" o "➖ None needed" si no hubo refactor necesario.
-->

## Resumen de tests

- **Total tests escritos**: {N}
- **Total tests pasando**: {N}
- **Layers usados**: Unit ({N}), Integration ({N}), E2E ({N})
- **Approval tests** (refactor): {N} o "Ninguno — no hubo tareas de refactor"
- **Funciones puras creadas**: {N}
