# Módulos del taller

El sistema sigue el *Diagrama de relaciones operativas del taller mecánico*. Cada módulo es una app de Django con sus modelos, pantallas y reglas.

| Módulo del diagrama | App | Ruta | Rol | Qué hace |
|---|---|---|---|---|
| Cliente | `clientes` | `/clientes/` | Mostrador, Ventas | Clientes y sus vehículos |
| Mostrador | `mostrador` | `/mostrador/` | Mostrador | Recepción, síntomas, orden de trabajo (OT) y entrega del vehículo |
| Ventas | `ventas` | `/ventas/` | Ventas | Diagnóstico inicial, presupuesto y autorización |
| Seguridad (SST) | `sst` | `/seguridad/` | Seguridad | Protocolos e inspecciones, reportes de riesgo, EPP y liberación de órdenes |
| Almacén | `almacen` | `/almacen/` | Almacén | Consulta de existencia, solicitudes de piezas, entregas y préstamo de herramientas |
| Inventario | `inventario` | `/` | Cualquier usuario | Stock, altas y bajas, alertas de reorden y auditorías |
| Proveedores | `proveedores` | `/compras/` | Compras | Directorio, solicitudes de material, órdenes de compra y recepción |
| Contabilidad | `contabilidad` | `/contabilidad/` | Contabilidad | Facturas, cobros y costos operacionales |

`taller` es la pieza común: roles, mapa del flujo (`/taller/`) y datos de ejemplo.

## El recorrido de una orden

```
Recibida → Presupuesto enviado → Autorizada → En reparación → Terminada → Facturada → Entregada
                  ↓                  ↓
              Rechazada          Cancelada
```

| Paso | Módulo | Efecto en otros módulos |
|---|---|---|
| Emitir la OT | Mostrador | Aparece en la bandeja de Ventas |
| Autorizar el presupuesto | Ventas | Crea una solicitud de pieza por cada refacción |
| Liberar la orden | Seguridad | Exige confirmar los protocolos y permite entregar piezas |
| Entregar una pieza | Almacén | Baja en Inventario con el folio de la OT; puede generar alerta de reorden |
| Pedir un faltante o atender una alerta | Almacén, Proveedores | Crea una solicitud de material para Compras |
| Recibir una orden de compra | Proveedores | Alta en Inventario y gasto en Contabilidad |
| Entregar EPP con costo | Seguridad | Gasto en Contabilidad |
| Emitir factura | Contabilidad | Cobra la mano de obra autorizada y solo las piezas entregadas |
| Registrar el pago completo | Contabilidad | Permite que Mostrador entregue el vehículo |

## Integrar el código de un compañero

Los módulos solo se hablan por las funciones de `services.py` (y `contabilidad/gastos.py`) y por las relaciones entre modelos. Mientras el módulo nuevo conserve lo de esta tabla, el resto no cambia:

| App | Funciones que usan otros módulos | Modelos y datos que usan otros módulos |
|---|---|---|
| `clientes` | — | `VehiculoCliente` (con `cliente`), `Cliente` (`nombre`, `rfc`, `telefono`) |
| `mostrador` | `emitir_orden`, `cambiar_estado`, `entregar_vehiculo` | `OrdenTrabajo` (`folio`, `estado`, `cliente`, `vehiculo`, `Estado`) |
| `ventas` | `autorizar`, `terminar_orden`, `lineas_a_facturar`, `obtener_presupuesto`, `enviar_presupuesto` | `Presupuesto`, `LineaPresupuesto` |
| `almacen` | `crear_solicitudes`, `cancelar_solicitudes`, `hay_pendientes`, `entregado_por_linea` | `SolicitudPieza` (`related_name="solicitudes"` en la orden) |
| `proveedores` | `solicitar_material` | `SolicitudMaterial`, `OrdenCompra`, `Proveedor` |
| `contabilidad` | `registrar_gasto`, `emitir_factura` | `Factura` (`related_name="facturas"`, estado `PAGADA`) |
| `sst` | `liberar_orden` | `Incidente` (`cerrado`) |
| `inventario` | `registrar_alta`, `registrar_baja`, `contexto_correo` | `Producto`, `Ubicacion`, `Existencia`, `Movimiento`, `AlertaReorden` |

Los nombres de ruta `app:nombre` que usan el menú y las plantillas de otros módulos también deben conservarse o actualizarse.

**Según lo que llegue:**

1. **Código en Django:** reemplazar la carpeta de la app y sus plantillas, ajustar lo que falte de la tabla y correr `manage.py makemigrations` y `manage.py test`. Si el modelo cambió y la base ya tiene datos, hay que planear la migración antes de borrar nada.
2. **Otro lenguaje o framework (PHP, Node, etc.):** no se puede pegar directo. O se traduce a una app de Django con la misma interfaz, o se deja como servicio aparte y se conecta por una API.
3. **Solo pantallas o diseño:** se pasan a las plantillas de `templates/<app>/`, sin tocar `services.py`.

`taller/tests.py` recorre el flujo completo: si pasa después de cambiar un módulo, la integración sigue bien.

## Roles

Los grupos se crean con las migraciones y se asignan a cada usuario en `/admin/`. Un superusuario entra a todo; un usuario sin grupo solo ve Inventario, Consulta y el mapa del flujo. El menú oculta lo que el rol no puede abrir y, si entra por la URL, recibe un 403.

## Límites actuales

- **La factura es un comprobante interno:** no es un CFDI ni se timbra ante el SAT. Para factura real hace falta un PAC.
- **Los precios se capturan sin IVA** y se les suma `IVA_TASA` (16 % por defecto). Los precios de ejemplo de `cargar_demo` se tratan igual.
- **La orden de compra usa el costo actual del producto**; todavía no se captura el costo real de cada compra.
- **Las normas de los protocolos de ejemplo son orientativas:** un responsable de seguridad debe revisar cuáles aplican al taller.
- **Los datos de `cargar_demo_taller` son inventados.**
