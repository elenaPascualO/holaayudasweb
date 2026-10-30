# Índice que cubre las consultas de los sitemaps

**Estado:** implementada (30-oct-2026), pendiente de desplegar y verificar. Aprobada **sin esperar a la medición** (decisión de la usuaria). **El diseño cambió durante la implementación: son dos índices, no uno** (ver "Cambios respecto a la propuesta").

## Contexto

Tras `sitemaps-pregenerated`, los sitemaps se generan en segundo plano (al arrancar si tienen más de 24 h y tras cada `daily`) y se sirven desde disco. Generarlos ya no afecta a los usuarios, pero sigue siendo caro:

- `get_sitemap_closed_by_year()` agrupa ~600K filas por año y calcula `MAX(updated_at)`.
- `get_sitemap_open_*()` y `get_sitemap_closed_entries()` devuelven `numero_convocatoria` y `updated_at`, ordenados por `fecha_recepcion`.

El índice actual `idx_conv_sitemap (detail_fetched, fecha_fin_solicitud, fecha_recepcion)` sirve para filtrar, pero **no contiene `numero_convocatoria` ni `updated_at`**. Por eso SQLite tiene que ir a la tabla a por cada fila, y la tabla pesa varios GB porque las filas son anchas (columnas JSON y textos largos). Son lecturas aleatorias de disco por cientos de miles de filas, cada día.

## Objetivo

Que todas las consultas de los sitemaps se resuelvan **solo con un índice** (*covering index*), sin tocar la tabla, y reducir el tiempo de generación de minutos a segundos.

## Diseño

### Índice

```sql
CREATE INDEX IF NOT EXISTS idx_conv_sitemap_cover
    ON convocatorias(detail_fetched, fecha_fin_solicitud, fecha_recepcion,
                     numero_convocatoria, updated_at);
```

- Contiene todas las columnas que usan las 5 consultas `get_sitemap_*`: filtro, orden, agrupación y columnas devueltas.
- Tamaño estimado: ~659K × ~60 bytes ≈ **40–60 MB** en disco.
- Hace redundante `idx_conv_sitemap`, porque es un prefijo del nuevo. **No se borra en esta spec**: borrarlo es irreversible y no aporta casi nada. Se puede hacer más adelante.

### Cómo se crea sin romper el despliegue

Crear un índice sobre una tabla de varios GB **tarda minutos**. Si se hiciera en `init_convocatorias_db()`, que se ejecuta al arrancar **antes** de que la app responda, el healthcheck de Coolify (10 s de espera + 10 intentos cada 5 s) fallaría. El deploy se daría por fallido y el contenedor nuevo se mataría a mitad de la creación, en cada intento.

Por eso:

1. Nueva función `ensure_sitemap_index(db_path=None) -> bool` en `convocatorias_db.py`. Comprueba en `sqlite_master` si el índice existe; si no, lo crea y registra cuánto tardó. Devuelve si lo ha creado.
2. Se llama **en segundo plano al arrancar** (`asyncio.to_thread`), **antes** de la generación de sitemaps del arranque, dentro de la misma tarea. Así la primera generación ya usa el índice.
3. Mientras se crea, SQLite **bloquea las escrituras** (las lecturas siguen funcionando en WAL). Un sync que intentara escribir esperaría el `timeout` por defecto de `sqlite3` (5 s) y podría fallar con `database is locked`. El riesgo es bajo: el sync diario es a las 07:00 y la creación ocurre una sola vez, en el primer arranque. Si ocurriera, el sync falla, llega el email de alerta y se relanza.
4. Para nuevas instalaciones (BD vacía), el índice se crea igual, instantáneamente.

### Archivos

| Archivo | Cambio |
|---|---|
| `backend/services/convocatorias_db.py` | `ensure_sitemap_index()` |
| `backend/main.py` | Llamarla en segundo plano antes de generar sitemaps |
| `doc/OPERACIONES.md` | Log esperado en el primer arranque |

### Decisión: medir antes de implementar

El log de `sitemaps-pregenerated` dirá cuánto tarda la generación completa en producción (`Sitemaps generated: N files, M URLs in S s`):

- **Si tarda más de ~1 minuto**: implementar esta spec.
- **Si tarda unos segundos**: no compensa el riesgo de bloquear escrituras durante la creación, y la spec se archiva.

### Fuera de alcance

- Borrar `idx_conv_sitemap`.
- Cambiar las consultas (por ejemplo, quitar el `substr` del `GROUP BY`).

## Cambios respecto a la propuesta (descubiertos con los tests)

El test de `EXPLAIN QUERY PLAN` mostró que **un solo índice no basta**, porque SQLite elige el camino de acceso según lo que filtra u ordena cada consulta:

1. Con el índice propuesto `(detail_fetched, fecha_fin_solicitud, fecha_recepcion, …)`, `open_entries` y `closed_entries` preferían `idx_conv_detail_fecha`, que ya viene ordenado por `fecha_recepcion`, y **volvían a la tabla fila a fila**. Para `open_entries` eso implica recorrer filas de toda la tabla hasta reunir las abiertas. Probablemente es la causa de los 8–25 s que se veían en `sitemap-grants-open-*.xml`.
2. Con un índice encabezado por `fecha_recepcion`, era `closed_by_year` la que seguía usando `idx_conv_sitemap` e iba a la tabla a por `updated_at`.

Se comparó sistemáticamente "solo A", "solo B" y "A+B", con y sin estadísticas del planificador (`ANALYZE`) y con distintas proporciones de abiertas. **Solo A+B consigue que las 5 consultas sean index-only sin estadísticas**:

| Índice | Columnas | Lo usan |
|---|---|---|
| `idx_conv_sitemap_cover` | `detail_fetched, fecha_recepcion, fecha_fin_solicitud, numero_convocatoria, updated_at` | `open_entries`, `closed_entries` |
| `idx_conv_sitemap_fin_cover` | `detail_fetched, fecha_fin_solicitud, fecha_recepcion, numero_convocatoria, updated_at` | `closed_by_year`, `open_max_updated` |

`open_count` ya era index-only con un índice existente.

- **Sin `ANALYZE`, que es el caso de producción porque la app nunca lo ejecuta**: las 5 consultas son index-only. El test lo comprueba y además verifica que no existe `sqlite_stat1`.
- **Si alguien ejecutara `ANALYZE` a mano**, `closed_entries` volvería a usar `idx_conv_detail_fecha` con acceso a tabla, limitado al rango de un año (~40K filas). Aceptable. **No ejecutar `ANALYZE` sin revisar los planes.**
- Coste: dos índices de ~40–60 MB y dos creaciones de varios minutos en el primer arranque.
- Las consultas pasan a constantes de módulo (`SITEMAP_*_SQL` en `convocatorias_db.py`) para poder analizarlas en los tests. Mismo SQL.

## Tests

En `backend/tests/test_sitemaps.py`:

| Test | Comprueba |
|---|---|
| `test_ensure_sitemap_index_creates_index` | En una BD sin el índice, lo crea y devuelve `True`; existe en `sqlite_master` |
| `test_ensure_sitemap_index_idempotent` | La segunda llamada devuelve `False` y no falla |
| `test_sitemap_queries_use_covering_index` | Sin `ANALYZE` (como en producción), `EXPLAIN QUERY PLAN` de las 5 consultas solo muestra accesos `USING COVERING INDEX` (nunca a la tabla) |
| `test_generation_unchanged_with_index` | Con el índice creado, `generate_all` produce exactamente los mismos archivos que sin él |

El test **no** ejecuta `ANALYZE` (la primera versión sí lo hacía y no reflejaba producción).

**Criterio de aceptación:** toda la suite en verde.

**Resultado (30-oct-2026):** antes de implementar fallaban los 4 (la función no existía); el test de planes falló dos veces más y reveló los problemas de diseño descritos arriba. Final: 19 passed en `test_sitemaps.py`; suite de backend 403 passed; frontend 91 passed.

## Verificación en producción

1. Primer arranque: logs `Created index idx_conv_sitemap_cover in S s` y `Created index idx_conv_sitemap_fin_cover in S s`, y después `Sitemaps generated: … in S s` con un tiempo mucho menor que el medido antes.
2. Arranques siguientes: no vuelve a crearlo.
3. `sqlite3` no está en la imagen, así que se comprueba con Python:
   ```sh
   python3 -c "import sqlite3; c=sqlite3.connect('/app/data/convocatorias.db'); print(c.execute(\"SELECT name FROM sqlite_master WHERE name LIKE 'idx_conv_sitemap%'\").fetchall())"
   ```
