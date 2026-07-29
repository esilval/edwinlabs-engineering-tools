# Constitución del proyecto

| Campo | Valor    |
| ----- | -------- |
| Fecha | {{DATE}} |

> Reglas que ninguna spec, plan o tarea puede violar. Si una regla aquí impide
> algo que hace falta, se cambia la regla explícitamente, no se ignora.

## Principios

1. _Principio breve y accionable._
2. _..._

## Estándares de código

- **Lenguajes y versiones:** _..._
- **Formato y linting:** _herramienta y comando_
- **Estructura de directorios:** _..._

## Pruebas

- _Qué exige una prueba antes de dar una tarea por hecha._
- _Umbral de cobertura, si aplica._

## Seguridad y datos

- _Manejo de secretos, PII, permisos._

## Límites

- _Dependencias que no se añaden sin discusión._
- _Cambios que siempre requieren aprobación humana explícita._

## Comprobación

Cómo se hace cumplir cada regla de arriba. Una regla sin fila aquí depende de
que alguien se acuerde, y eso hay que saberlo.

| Regla | Nivel | Mecanismo | Suelo actual |
| ----- | ----- | --------- | ------------ |
| _formato del código_ | mecánica | hook de calidad del plugin | — |
| _..._ | mecánica | _pendiente de automatizar_ | _valor de hoy_ |
| _..._ | revisable | revisión del diff | — |
| _..._ | juicio | criterio humano | — |

Niveles: **mecánica** (un script la comprueba), **revisable** (requiere leer el
diff y juzgar), **juicio** (la decide una persona caso por caso).

La columna de suelo existe para el ratchet: si el repositorio hoy no cumple un
umbral, se registra lo que hay y solo se permite que suba. Un umbral inalcanzable
termina desactivado, y eso desacredita a todas las demás comprobaciones.
