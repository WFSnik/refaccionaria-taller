# Refaccionaria · Taller e inventario

Sistema para una refaccionaria con taller mecánico: del cliente que llega con su vehículo hasta la factura, el cobro y la entrega, con el inventario conectado a cada paso.
Vende consumibles: filtros, aceites, líquidos, empaques, bujías, bandas y plumas (sin herramientas, espejos ni piezas de colisión). Las herramientas del módulo de Almacén son las del taller, para préstamo interno.
Django 5.2 + PostgreSQL 17.

## Módulos

Cliente, Mostrador, Ventas, Seguridad (SST), Almacén, Inventario, Proveedores y Contabilidad, según el diagrama de relaciones operativas del taller. El mapa con los pendientes de cada uno está en `/taller/`.

[docs/modulos.md](docs/modulos.md) explica cómo se conectan, los roles, los límites actuales y **cómo integrar el código de otra persona en un módulo**.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py cargar_demo_taller --usuario admin   # clientes y órdenes de ejemplo en cada etapa
.\.venv\Scripts\python.exe manage.py test                                 # todas las pruebas
```

## Flujo de inventario

- **Alta**: recibir producto → si no está registrado se da de alta ahí mismo, si ya existe se autocompletan sus datos → asignar ubicación → registrar → se actualiza el stock.
- **Baja**: seleccionar producto → si no hay stock suficiente la baja no se registra y, si falta en el total, se genera una alerta → motivo → se descuenta de la ubicación → se actualiza el stock.
- Si después del movimiento el stock queda en el **punto de reorden** o por debajo, se crea una alerta (una por producto) y se avisa a compras por correo. En desarrollo el correo se imprime en la consola del servidor.
- La alerta se cierra sola cuando una alta deja el stock por encima del punto de reorden.

## Correr en local

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Abre http://127.0.0.1:8000. El usuario `admin` y su contraseña están en `.env` (`ADMIN_USER` / `ADMIN_PASSWORD`).
Para crear más usuarios usa `/admin/` o `manage.py createsuperuser`.

## Otros comandos

```powershell
.\.venv\Scripts\python.exe manage.py test inventario                  # pruebas
.\.venv\Scripts\python.exe manage.py cargar_demo --usuario admin      # catálogo de ejemplo (solo en base vacía)
```

Los catálogos de categorías y marcas se administran en `/admin/`.

## Catálogo por vehículo y asistente

- **¿Qué lleva?** (`/vehiculos/`): se escribe el vehículo como lo dice el cliente («versa 2015», «cr-v 2018») o se elige marca, modelo y año. Muestra los filtros de aceite, aire, cabina y gasolina con su número Gonher, las equivalencias Fram y Wix y lo que hay en el anaquel. También se puede buscar por número de parte de cualquier marca (`/vehiculos/numero/`).
- **Asistente** (`/asistente/`): chat para clientes; no pide sesión. Con `ANTHROPIC_API_KEY` en `.env` conversa con Claude (modelo en `ASISTENTE_MODELO`), que solo contesta con lo que devuelven las búsquedas del catálogo y el inventario: no da números de memoria, no muestra ubicaciones ni costos y no toma pedidos. Sin key funciona en modo básico con mensajes simples.
- Lo que nadie supo contestar queda en **Sin respuesta** (`/vehiculos/pendientes/`): es la lista de datos por cargar.
- Un producto se une al catálogo por su **número de parte** (campo nuevo en el producto) y su marca.

### Fuentes de los datos (`catalogo/datos/`)

Este repositorio solo incluye una **muestra de 3 vehículos**: el catálogo completo no se publica porque es material de un tercero. Con esta muestra, el buscador y el asistente solo responden por esos vehículos. Para cargar más datos, reemplaza estos CSV por los tuyos con las mismas columnas. `catalogo/herramientas/extraer_pdf_gonher.py` genera un JSON a partir de tu copia del PDF; el paso de JSON a CSV no está automatizado.

| Archivo | Qué trae | Fuente |
|---|---|---|
| `gonher_aplicaciones_2026.csv` | Muestra: 3 vehículos, 14 aplicaciones | Catálogo de filtros Gonher 2026 (gonher.com.mx) |
| `equivalencias_gonher_2026.csv` | Muestra: 13 equivalencias Fram → Gonher | Tabla de equivalencias del mismo catálogo |
| `equivalencias_wix.csv` | Muestra: 4 equivalencias Wix, con URL de cada fuente | Tablas de referencias cruzadas de terceros. Las de una sola fuente se muestran «por confirmar» |

Este proyecto no está afiliado a Gonher, Fram ni Wix. Sus marcas pertenecen a sus dueños.

```powershell
.\.venv\Scripts\python.exe manage.py cargar_catalogo                          # carga o reemplaza el catálogo
.\.venv\Scripts\python.exe manage.py cargar_demo_catalogo --usuario admin     # 23 filtros de ejemplo con número de parte y stock
```
