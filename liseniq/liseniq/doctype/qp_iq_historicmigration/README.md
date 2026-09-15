# Migración Histórica de Mediciones - ListenAIQ

Este documento detalla el proceso para cargar archivos de migraciones históricas de mediciones (encuestas) en el sistema Frappe, así como la estructura requerida del archivo y un resumen técnico del flujo de procesamiento backend.

---

## 1. Preparación del Archivo

El sistema soporta archivos en formato **CSV** (codificación UTF-8 preferiblemente) y **Excel (.xlsx)**.

### Estructura de Columnas
El sistema es dinámico en la lectura de cabeceras, por lo que el orden exacto de algunas columnas puede variar, pero debe cumplir con las siguientes reglas:

1. **Columnas Obligatorias:**
   * `ID Interno`: Identificador único del contacto (ej. ObjectId de MongoDB). El sistema lo buscará por su nombre sin importar la posición en la que se encuentre.
   * `Tipo de Cultura`: Esta columna actúa como un **pivote**.
   * `Dimensión`: Dimensión evaluada en la pregunta.
   * `Atributo`: El texto o enunciado de la pregunta.
   * `Respuesta`: El valor de la respuesta otorgada por el contacto.

2. **Columnas Demográficas Dinámicas:**
   * **Cualquier columna** que se encuentre ubicada **antes** de la columna `Tipo de Cultura` (y que no sea `ID Interno`) será considerada automáticamente como un campo demográfico (ej. `País`, `Genero`, `Nivel Académico`, `Área`, etc.).

3. **Columnas Estáticas de Contacto (Opcionales):**
   * `País`, `Genero`, `Nivel Académico`. Si están presentes antes del pivote, se mapean a los campos fijos del historial y se agregan a la tabla de demográficos.

### Ejemplo de Estructura Válida

| País | Área | ID Interno | Tipo de Cultura | Dimensión | Atributo | Respuesta |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Colombia | Ventas | 68b0a86695... | Cultura Innovadora | Liderazgo | ¿Mi líder me apoya? | 4 |

*(En este ejemplo, "País" y "Área" serán tomados como demográficos al estar antes de "Tipo de Cultura").*

---

## 2. Proceso de Carga en la Interfaz (Frappe)

1. Ingresa al módulo correspondiente y crea un nuevo documento de **Historic Migration** (`qp_IQ_HistoricMigration`).
2. **Seleccionar Creador (`hm_creator`):** Selecciona el contacto responsable. Este contacto debe pertenecer a una compañía (`custom_company`), la cual será heredada para el proceso. El sistema filtrará contactos que no pertenezcan internamente a ListenAIQ (`custom_is_liseniq_contact = 0`).
3. **Seleccionar Plantilla Base (`hm_template`):** Define la plantilla que servirá como base. Si el archivo contiene nuevas preguntas, se creará una nueva plantilla clonada a partir de esta.
4. **Adjuntar Archivo (`hm_file`):** Sube el archivo `.csv` o `.xlsx`.
5. **Guardar y Ejecutar:** Guarda el documento. Aparecerá un botón de **Ejecutar**. Al presionarlo, el proceso se enviará a segundo plano (background worker) y la pantalla se refrescará automáticamente.

---

## 3. Detalles Técnicos del Flujo (Backend)

El proceso se ejecuta de manera asíncrona para prevenir tiempos de espera agotados (Timeouts) en archivos grandes. A continuación, los hitos clave del procesamiento:

### 3.1. Normalización de Datos (Cultura)
Si la plantilla base seleccionada pertenece a la categoría `template_culture`, el sistema activará una bandera de normalización. Las respuestas que vengan en la columna `Respuesta` se mapearán al estándar ListenAIQ antes de ser guardadas:
* `-4` ➔ `1`
* `-2` ➔ `2`
* `0`  ➔ `3`
* `2`  ➔ `4`
* `4`  ➔ `5`

### 3.2. Creación de Preguntas y Plantillas
* El sistema compila todas las preguntas (`Atributo`) únicas en el archivo.
* Busca si la pregunta ya existe para la compañía. De no existir, la crea en `qp_IQ_Question` asignándole el tipo de pregunta `scale_likert` (consultado de forma dinámica).
* Si se crean preguntas nuevas, el sistema genera una **nueva plantilla privada** (`Consolidado Migración - [ID]`) que incluye las preguntas de la plantilla base y las nuevas.

### 3.3. Persistencia de Datos
* **Aislamiento del Contacto:** Para evitar colisiones y contaminación del maestro, **NO** se hacen inserciones en el DocType `Contact`.
* Todos los registros se vuelcan exclusivamente en el DocType **`qp_IQ_SurveyHistoricData`**.
* El `ID Interno` es sanitizado, eliminando prefijos como `ObjectId(...)` antes de guardarse en `shd_document_number`.

### 3.4. Manejo de Errores y Logs
* En caso de fallo crítico en el worker, se ejecuta un `frappe.db.rollback()`.
* El error se captura de manera estándar usando `frappe.log_error(frappe.get_traceback(), "Error en process_migration - Migración [ID]")` para que quede reflejado en el Error Log nativo del framework.
* El estado de la migración cambia a `Fallido` y se habilita el botón para reintentar una vez corregido el archivo.