---
name: constitution
description: Crea o actualiza specs/constitution.md, las reglas invariantes del proyecto que ninguna spec o plan puede violar. Primera fase del flujo SDD.
disable-model-invocation: true
---

# Fase 0 — Constitución

Establece las reglas que gobiernan todo el trabajo posterior en este repositorio.

Argumento del usuario (puede estar vacío): `$ARGUMENTS`

## Procedimiento

1. Comprueba si ya existe `specs/constitution.md`.
   - Si existe, léelo y trata esta invocación como una **revisión**: muestra al
     usuario lo que hay y pregunta qué quiere cambiar. No lo reescribas entero.
   - Si no existe, crea el directorio `specs/` y copia la plantilla de
     `${CLAUDE_PLUGIN_ROOT}/templates/constitution.md` a `specs/constitution.md`.

2. Antes de rellenarla, **inspecciona el repositorio** para no inventar reglas:
   lenguajes y versiones reales, gestor de paquetes, configuración de linter y
   formateador, framework de pruebas, estructura de directorios, CI si la hay.
   Deriva los estándares de lo que ya existe.

3. Rellena la plantilla. Reglas de redacción:
   - Cada principio debe ser accionable y comprobable. «Escribir código limpio»
     no sirve; «ninguna función pública sin tipo de retorno explícito» sí.
   - Si no puedes justificar una regla con algo que viste en el repo o que el
     usuario te dijo, no la inventes: déjala como pregunta.

4. **Clasifica cada regla** por cómo se hace cumplir, y dilo al usuario:

   - **Mecánica** — un linter o un script puede comprobarla (formato, cobertura,
     dirección de dependencias, secretos). Escríbela en la constitución, pero
     márcala en la sección «Comprobación» como candidata a automatizar. Una
     regla mecánica que solo vive en prosa se cumple más o menos; la misma en un
     hook se cumple siempre.
   - **Revisable** — requiere leer el diff y juzgar (¿es correcta esta
     abstracción?). La constitución es su sitio definitivo.
   - **De juicio** — la decide una persona caso por caso. Anótala como
     principio, no como regla.

   Ver `docs/standards-roadmap.md` en el plugin para qué reglas mecánicas
   conviene automatizar y en qué orden.

5. No declares un estándar que el repositorio hoy no cumple. Si la cobertura
   está en el 40%, exigir el 90% deja el proyecto en rojo permanente y acaba con
   la comprobación desactivada, lo que desacredita a todas las demás. Registra
   el valor actual como suelo y súbelo después.

6. Presenta al usuario un resumen de las reglas propuestas y **espera su
   confirmación** antes de darla por buena. La constitución restringe todo lo
   que venga después; una regla incorrecta es cara.

## Al terminar

Indica que el siguiente paso es `/sdd:specify <descripción de la feature>`.
