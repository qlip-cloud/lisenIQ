# Integración Power BI y Resultados de Encuestas - ListenAIQ

Este módulo maneja la visualización de resultados de encuestas (mediciones) a través de un portal web en Frappe y la incrustación segura de reportes de Microsoft Power BI con aislamiento de datos multicompañía (Row-Level Security dinámico mediante filtros frontend).

## Arquitectura de Archivos

* `index.py`: Controlador del portal web (`www/resultados/`). Maneja la lógica de negocio, validación de sesiones, aislamiento de datos por compañía del usuario y enrutamiento hacia la configuración correcta de Power BI.
* `power_bi_util.py`: Módulo de integración (`utils/`) con las APIs de Microsoft Entra ID (Azure AD) y Power BI REST API. Maneja autenticación, caché de tokens y construcción del esquema de filtros para el visor.

## Lógica Principal

### 1. Aislamiento Multicompañía (Data Isolation)
El sistema requiere que el usuario esté autenticado (no se permite acceso a *Guest*). Utiliza el DocType `Contact` para determinar la empresa del usuario actual leyendo el campo `custom_company`. 

> **Nota Importante sobre Identificadores:** En esta implementación, el campo `custom_company` almacena el **ID interno (campo `name` de la base de datos de Frappe)** que corresponde a un hash alfanumérico (por ejemplo, `bc8fe85b33`), y **no** el nombre comercial o legible de la empresa.
    
Todas las consultas SQL (`_get_finalized_surveys`) inyectan esta variable para garantizar que el usuario solo pueda ver las encuestas donde `su_owner` coincide con el ID de su compañía. La página tiene el caché deshabilitado (`context.no_cache = 1`) para evitar filtraciones de estado o persistencia incorrecta entre sesiones, forzando la solicitud limpia de la empresa en cada entrada.

### 2. Enrutamiento de Tableros (Mnemónicos)
El sistema soporta múltiples tableros de Power BI dinámicamente. Al consultar la configuración del Embed, el sistema verifica la categoría de la plantilla de la encuesta:
* La categoría contiene **"Cultura"** → Utiliza configuración `PBICU`.
* La categoría contiene **"Engagement"** → Utiliza configuración `PBIEN`.

Estas configuraciones se almacenan y desencriptan de forma segura desde el DocType personalizado `qp_IQ_PBI`.

### 3. Autenticación y Caché (Power BI Utils)
* **Flujo de Auth:** Se utiliza el flujo *Client Credentials* para obtener el Access Token del Tenant. Soporta la librería `msal` por defecto, con un fallback a HTTP puro (`requests`).
* **Caché:** Los *Access Tokens* y *Embed Tokens* se guardan en Redis (`frappe.cache()`) utilizando una clave compuesta que incluye el Workspace, Report ID y el Mnemónico, optimizando la latencia y reduciendo el consumo de la API de Microsoft.

### 4. Inyección de Filtros (RLS Dinámico)
Para que el usuario visualice únicamente la información de su organización dentro de los reportes incrustados de Power BI, se construye un esquema `basicFilter` que se envía al frontend. 

El código filtra sobre dos tablas en el modelo de datos de Power BI:
1.  Tabla: `report` → Columna: `company_name`
2.  Tabla: `evaluations_compare` → Columna: `company_name`

**IMPORTANTE:** Dado que Frappe envía el ID/hash alfanumérico de la compañía (`bc8fe85b33`), el modelo de datos en Power BI debe estar parametrizado para que la columna `company_name` en ambas tablas contenga dichos hashes en lugar del nombre de texto comercial, logrando así una coincidencia exacta.

```json
{
  "$schema": "[http://powerbi.com/product/schema#basicFilter](http://powerbi.com/product/schema#basicFilter)",
  "target": {
    "table": "NOMBRE_TABLA",
    "column": "company_name"
  },
  "operator": "In",
  "values": ["ID_ALFANUMERICO_COMPAÑIA"]
}