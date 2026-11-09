# Plan de mejoras

Estado actual (v1, 27 sep 2026): altas y bajas con asistente, stock por ubicación, alertas de reorden con correo a compras, tablero, catálogo de ejemplo y 15 pruebas.

Tamaño estimado: **S** = horas, **M** = 1–2 días, **L** = 3+ días.

## Fase 1 · Dejarlo listo para usarse en la tienda

| Mejora | Por qué | Tamaño |
|---|---|---|
| Envío real de correos (SMTP) | Hoy el aviso a compras solo se imprime en la consola. | S |
| Revisar y ajustar la vista en celular | Los estilos existen pero no se han visto en un teléfono. | S |
| ~~Roles por módulo~~ | Hecho (nov 2026): grupos Mostrador, Ventas, Almacén, Compras, Contabilidad y Seguridad. | — |
| Restringir Inventario por rol | Hoy cualquier usuario con sesión registra altas y bajas o edita precios y puntos de reorden. | S |
| Instalarlo en una PC de la tienda y abrirlo desde la red local | Hoy solo corre en esta laptop. Servidor Waitress, `DEBUG` apagado y archivos estáticos con versión para evitar caché viejo. | M |
| Respaldo diario automático de PostgreSQL | Si se daña el disco se pierde el inventario. Tarea programada con `pg_dump` y copia fuera del equipo. | S |

## Fase 2 · Inventario a la medida de filtros y lubricantes

| Mejora | Por qué | Tamaño |
|---|---|---|
| ~~Aplicaciones por vehículo (marca, modelo, año, motor)~~ | Hecho (oct 2026): catálogo Gonher 2026, buscador `/vehiculos/` y asistente `/asistente/`. | — |
| ~~Equivalencias entre marcas~~ | Hecho: Fram desde la tabla oficial de Gonher; Wix solo 7, de fuentes web. | — |
| Más equivalencias Wix y otras marcas | Hoy Wix tiene 7 números. Conseguir la tabla con el proveedor o el catálogo de Wix/MANN. | S |
| Aceite recomendado por vehículo (viscosidad y litros) | El catálogo Gonher solo trae filtros; el asistente hoy manda esas preguntas a mostrador. | M |
| Lotes y caducidad | Aceites, anticongelantes y líquido de frenos caducan. Registrar el lote al dar la alta, sacar primero lo que vence antes y avisar lo que está por caducar. | M |
| Traspasos entre ubicaciones | Hoy mover mercancía de bodega a mostrador requiere una baja y una alta. | S |
| ~~Conteo físico (inventario cíclico)~~ | Hecho (nov 2026): auditorías por ubicación en `/auditorias/`. | — |
| Etiquetas con código de barras | Imprimir etiquetas para productos o anaqueles sin código. | S |
| Escanear con la cámara del celular | Dar entrada desde el almacén sin lector de códigos. | M |

## Fase 3 · Compras y decisiones

| Mejora | Por qué | Tamaño |
|---|---|---|
| ~~Proveedores y órdenes de compra desde las alertas~~ | Hecho (nov 2026): módulo de Proveedores en `/compras/`. | — |
| Costo real en cada orden de compra | Hoy la orden toma el costo actual del producto. | S |
| Factura electrónica (CFDI) | Hoy la factura es un comprobante interno. Requiere contratar un PAC. | L |
| Punto de reorden sugerido por consumo | Hoy es un número fijo. Calcularlo con las salidas de las últimas semanas y el tiempo de entrega del proveedor. | M |
| Reportes: rotación, productos sin movimiento, valor por categoría | Saber qué se vende y qué dinero está parado en el anaquel. | M |
| Exportar a Excel | Para contabilidad y para enviar pedidos. | S |

## Fase técnica (en paralelo)

| Mejora | Por qué | Tamaño |
|---|---|---|
| Pruebas automáticas en GitHub Actions | Que cada cambio subido corra las pruebas solo. | S |
| Linter (Ruff) | Mantener el código uniforme. | S |
| Pruebas de navegador con Playwright | Cubrir el asistente de altas y bajas de punta a punta. | M |
| Bitácora de cambios en productos | Saber quién cambió un precio o un punto de reorden. | S |

## Fuera de alcance por ahora

- Punto de venta de mostrador y cortes de caja. Las ventas del taller ya generan sus bajas al entregar las piezas; la venta directa sin orden de trabajo sigue haciéndose como baja manual.
