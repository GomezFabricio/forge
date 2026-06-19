# Simulaciones de uso de forge

Esta carpeta contiene **walkthroughs** de un dev usando forge en situaciones reales: qué escribe, cómo entra forge, qué pregunta y cuándo, qué artefactos quedan. Cada uno fue **verificado contra las skills y el código reales** de forge (cada paso se marcó como confirmado, corregido, o quitado si no tenía respaldo).

Sirven para entender cómo se comporta forge antes de adoptarlo. Para la explicación conceptual de cada subsistema está la sección ["Cómo funciona por dentro"](../guia-de-uso.md#11-cómo-funciona-por-dentro-referencia) de la guía de uso; para el paso a paso operativo, la [guía de uso](../guia-de-uso.md) completa.

## Los escenarios

Se mantienen en el repo **tres escenarios curados**, elegidos por ser los más representativos del arranque, el día a día y la defensa:

| # | Escenario | De qué se trata |
|---|---|---|
| 01 | [Greenfield sin documentación](01-greenfield-sin-docs.md) | Directorio vacío → `/fg-setup` bootstrap + Conversación de Visión → primer ciclo incremental. Cómo arranca un proyecto desde cero. |
| 08 | [Un bugfix en ceremonia Rápido](08-bugfix-rapido.md) | El flujo cotidiano más corto: salta `/fg-design`, pero `/fg-review` igual corre. |
| 10 | [Las capas de defensa en vivo](10-capas-defensa-en-vivo.md) | El guard frena un `git push --force`, el filtro PII redacta un secreto, y forge no entra para lo trivial. |

> Se analizaron en total **10 escenarios** (sumando greenfield con PRD, microservicio único, sistema de microservicios y sus límites, refactor de legacy, agregar un módulo, adoptar forge en un proyecto existente, y batching multi-sesión). Los siete restantes se dejaron fuera del repo como material de análisis point-in-time, para no cargar el producto con documentación derivada que tiende a desactualizarse. La fuente de verdad del comportamiento siempre es la skill.

---

*Estas simulaciones se generaron a partir de un análisis del código de forge en la rama `develop`. Si el comportamiento de una skill cambia, la simulación correspondiente puede quedar desactualizada — la fuente de verdad siempre es la skill.*
