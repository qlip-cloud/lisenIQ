# Manual de Arquitectura e Implementación: Sistema Multicompañía por Contacto (App `ListenAIQ`)

Este manual contiene la especificación funcional completa y el desglose de la arquitectura técnica para el sistema de acceso multicompañía implementado en la aplicación personalizada `ListenAIQ` sobre **Frappe Framework v13**.

---

## PARTE 1: Documentación Funcional (Modelo de Negocio y Experiencia de Usuario)

El sistema multicompañía de `ListenAIQ` está diseñado para permitir que un único usuario de la plataforma (asociado a un registro `Contact`) interactúe de forma aislada y segura con múltiples empresas sin necesidad de duplicar credenciales de acceso (correos electrónicos) ni de utilizar entornos separados.

### 1.1 Flujos de Experiencia de Usuario (UX)

#### A. Flujo de Autenticación e Ingreso Automatizado

* **Caso de Empresa Única:** Si el usuario autenticado posee relación con una sola compañía en la plataforma, el sistema omite cualquier paso intermedio. El backend inicializa automáticamente las variables de sesión para esa empresa y el usuario es redirigido directamente al tablero principal (`/iq-home`).
* **Caso de Múltiples Empresas:** Si el usuario está asignado a dos o más compañías, el sistema intercepta el flujo normal de navegación de la página de inicio. El usuario es redirigido obligatoriamente a la pantalla de selección (`/iq-home/select_company`), donde se le presentan tarjetas visuales con los logotipos y nombres de las empresas a las que está autorizado a entrar. No se permite el acceso a ninguna otra sección del portal hasta que el usuario elija explícitamente un entorno de trabajo.

#### B. Intercambio Dinámico de Entorno (Company Switcher)

* Un usuario con acceso a múltiples empresas no necesita cerrar sesión para cambiar de contexto. El sistema expone un botón denominado **"Cambiar de Empresa"** dentro del menú desplegable del avatar en la barra de navegación superior.
* Al activar esta opción, se renderiza un modal interactivo en pantalla que despliega las opciones disponibles. Al seleccionar una nueva empresa, el entorno de trabajo realiza un cambio en caliente en el backend y refresca la interfaz del portal web (`/iq-home`) reflejando inmediatamente los nuevos datos.

### 1.2 Reglas de Negocio Fundamentales

#### A. Principio de No Persistencia y Seguridad Rigurosa

* **Prohibición de Caché Permanente:** La selección de la empresa activa **nunca debe guardarse de forma fija en la base de datos, cookies persistentes o localStorage**. La configuración del entorno vive únicamente mientras dure la sesión web del usuario.
* **Forzado de Selección por Entrada:** Cada vez que el usuario cierra su sesión de manera voluntaria, o bien cuando el token de sesión expira por inactividad, la configuración se destruye. En el siguiente inicio de sesión, el sistema obligará de nuevo al usuario a elegir a qué empresa desea ingresar. Esto mitiga errores operacionales donde un administrador realiza cambios en una organización creyendo que se encuentra en otra.

#### B. Aislamiento Absoluto de Datos (Multi-Tenant a Nivel de Aplicación)

* Una vez seleccionada la empresa activa, toda la data expuesta en el portal queda restringida al identificador de dicha organización. Esto incluye:
* El listado de mediciones y encuestas (`qp_IQ_Survey`), filtrado por el campo propietario (`su_owner`).
* Los contadores del tablero (encuestas completadas, pendientes y porcentajes de avance).
* Los reportes descargables (ZIP de informes de liderazgo, reportes de seguimiento 360 y archivos Excel/CSV de resultados).
* Los planes de suscripción activos y el set de características funcionales (`App Features`) disponibles para el usuario en esa sesión.



#### C. Excepción del Rol de Administrador

* Los usuarios que cuenten con el rol nativo `Administrator` dentro de Frappe evaden completamente las redirecciones del portal web cliente y son transferidos de forma directa al escritorio estándar de la plataforma (`/app`), garantizando la continuidad de las tareas de soporte global y desarrollo.

### 1.3 Procedimiento Operativo: Asignación de una Nueva Empresa a un Usuario

Para que un usuario pueda visualizar e interactuar con una nueva organización en su portal web (ya sea mediante el flujo de entrada inicial o a través del *Company Switcher*), un administrador del sistema debe asociar formalmente la empresa a su registro de contacto.

#### Pasos para la Configuración en el Escritorio (Desk)

1. **Acceso al Registro del Usuario:**
* Ingrese al escritorio estándar de Frappe (`/app`).
* Navegue al listado del DocType **Contact** (Contacto) y seleccione el registro correspondiente al usuario al que desea otorgarle acceso.


2. **Ubicación de la Sección de Organizaciones:**
* Desplácese hacia abajo en el formulario del contacto hasta localizar la sección titulada **Empresas Asociadas**.


3. **Inserción de la Nueva Relación (Fila en Tabla Hija):**
* Haga clic en el botón **"Add Row"** (Agregar fila) dentro de la tabla interactiva de **Empresas Asociadas** (`qp_IQ_ContactCompany`).
* **Columna `Empresa` (`cc_company`):** Haga clic en el campo de tipo *Link* y seleccione el ID o nombre de la organización (`qp_IQ_Company`) a la cual se le otorgará el acceso.
* **Columna `Perfil de Rol` (`cc_role_profile`):** Seleccione el perfil de permisos del portal (`qp_IQ_PortalRole`) que este usuario desempeñará específicamente *dentro de esa empresa*. *(Recuerde que este modelo permite que el usuario sea "Administrador" en la Empresa A, pero únicamente "Lector" en la Empresa B)*.
* **Columna `Por Defecto` (`cc_is_default`):** Marque esta casilla únicamente si desea que esta organización sea el entorno prioritario cargado por defecto en automatizaciones en segundo plano.


4. **Almacenamiento y Persistencia:**
* Haga clic en el botón **Guardar** (*Save*) en la esquina superior derecha del formulario del Contacto.



#### Impacto Inmediato en la Experiencia (Hot-Reload)

* **Si el usuario estaba en una sesión activa:** Al hacer clic en el botón **"Cambiar de Empresa"** de la barra de navegación, el modal asíncrono invocará a la API del servidor (`get_user_companies`), la cual leerá instantáneamente la nueva fila de la tabla hija y renderizará la tarjeta visual de la nueva empresa sin necesidad de que el usuario cierre e inicie sesión de nuevo.
* **Si el usuario inicia sesión desde cero:** Si previamente pertenecía a una sola empresa y ahora se le ha agregado esta segunda, el sistema dejará de redirigirlo automáticamente a `/iq-home` y lo interceptará de manera obligatoria en la pantalla de selección (`/iq-home/select_company`) para que elija el entorno de trabajo de su preferencia.

---

## PARTE 2: Documentación Técnica (Para el Equipo de Ingeniería de Software)

### 2.1 Modelo de Datos y Relaciones (Esquema de Base de Datos)

La arquitectura de datos utiliza el DocType nativo `Contact` de Frappe como entidad pivot y añade una relación de muchos a muchos ($M:N$) mediante una tabla hija personalizada (`Table` field).

```
  ┌─────────────────┐          ┌──────────────────────────┐          ┌──────────────────┐
  │     Contact     │ 1 ─── N  │   qp_IQ_ContactCompany   │ N ─── 1  │  qp_IQ_Company   │
  │     (DocType)   │          │      (Child Table)       │          │    (DocType)     │
  └─────────────────┘          └──────────────────────────┘          └──────────────────┘
                               ├── cc_company (Link)                 └── co_name
                               └── cc_role_profile (Link)            └── co_logo

```

#### DocType Tabla Hija: `qp_IQ_ContactCompany`

Campos clave incluidos dentro de la estructura de la tabla hija anidada en `Contact`:

* `cc_company` (Link, obligatorio): Llave foránea que apunta al DocType personalizado de la empresa (`qp_IQ_Company`).
* `cc_role_profile` (Link, opcional): Llave foránea que apunta al perfil de roles del portal (`qp_IQ_PortalRole`). Permite granular los permisos de un mismo usuario de forma diferenciada según la empresa en la que trabaje (ej: puede ser "Editor" en la Empresa A y "Lector" en la Empresa B).
* `cc_is_default` (Check): Flag utilizado para predefinir un entorno prioritario si fuese requerido en automatizaciones de fondo.

---

### 2.2 Gestión de Estado Volátil en Memoria (Sesión Redis)

Para garantizar la regla de negocio de no persistencia, el estado de la empresa activa se almacena exclusivamente en el diccionario temporal de la sesión del usuario administrado por Frappe a través de su capa de Redis.

#### Variables de Sesión Inyectadas:

1. `frappe.session.data.get("ListenAIQ_active_company")`: Contiene el ID único de la empresa con la que el usuario opera en el ciclo actual de su sesión.
2. `frappe.session.data.get("ListenAIQ_active_role_profile")`: Almacena el perfil de permisos asignado específicamente a esa relación empresa-contacto.
3. `frappe.session.data.get("ListenAIQ_company_name")`: Almacena el nombre de despliegue comercial para optimizar las llamadas del frontend y no sobrecargar la base de datos con lecturas repetitivas en cada renderizado de página.

---

### 2.3 Análisis de Lógica de Controladores y Servidor (Python)

#### A. Intercepción y Redirección en la Página de Inicio (`index.py`)

Al cargar la ruta principal `/iq-home`, el controlador verifica estrictamente el estado de la sesión antes de procesar cualquier métrica o consulta ORM:

```python
user = frappe.session.user

if "Administrator" not in frappe.get_roles(user):
    # Lectura estricta de la sesión actual en memoria volatil
    active_company = frappe.session.data.get("ListenAIQ_active_company")
    
    # Si no existe variable de entorno activa, se evalúan las relaciones
    if not active_company:
        contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
        if contact_name:
            companies = frappe.get_all(
                "qp_IQ_ContactCompany", 
                filters={"parent": contact_name, "parenttype": "Contact"}, 
                fields=["cc_company"]
            )
            
            # Condición de bifurcación de flujos
            if len(companies) > 1:
                # El usuario posee múltiples opciones; se le detiene e interrumpe la petición
                frappe.local.flags.redirect_location = "/iq-home/select_company"
                raise frappe.Redirect
            elif len(companies) == 1:
                # Caso de empresa única: Se inicializa la sesión de forma transparente
                active_company = companies[0].cc_company
                frappe.session.data["ListenAIQ_active_company"] = active_company
                if hasattr(frappe.local, "session_obj") and frappe.local.session_obj:
                    frappe.local.session_obj.update()

    if active_company:
        user_company = active_company

```

#### B. Inicialización Segura del Entorno de Trabajo (`login_util.py`)

Cuando el usuario selecciona una empresa desde la interfaz web, se invoca el método expuesto por la API del servidor `set_active_company`:

```python
@frappe.whitelist()
def set_active_company(company_id):
    user = frappe.session.user
    if user == "Guest":
        return "/login"
    
    if "Administrator" in frappe.get_roles(user):
        return "/app"

    contact_name = frappe.db.get_value("Contact", {"user": user}, "name")
    
    # Verificación estricta de seguridad: Confirmar que el contacto realmente posee acceso al ID provisto
    relation = frappe.get_all("qp_IQ_ContactCompany", filters={
        "parent": contact_name,
        "parenttype": "Contact",
        "cc_company": company_id
    }, fields=["name", "cc_role_profile"])

    if not relation:
        frappe.throw(_("No tienes permisos para acceder a esta compañía."))

    # Inyección de estado en la sesión volatil de Redis
    frappe.session.data["ListenAIQ_active_company"] = company_id
    frappe.session.data["ListenAIQ_active_role_profile"] = relation[0].cc_role_profile
    
    # Invalidación del caché del nombre previo de la compañía
    frappe.session.data["ListenAIQ_company_name"] = None

    # Sincronización forzada del objeto de sesión local de Frappe
    if hasattr(frappe.local, "session_obj") and frappe.local.session_obj:
        frappe.local.session_obj.update()

    return "/iq-home"

```

---

### 2.4 Control del Frontend e Invocaciones Asíncronas (JavaScript)

La comunicación y actualización visual se gestiona en el cliente utilizando peticiones asíncronas combinadas con el API nativo `frappe.call`.

#### A. Invocación y Construcción del Modal Dinámico

Dentro de `ListenAIQ_base.js`, el botón de cambio de empresa evalúa el listado de organizaciones permitidas para el usuario y genera la interfaz en caliente:

```javascript
// Captura del evento de clic en el Company Switcher
if (switchCompanyBtn) {
    switchCompanyBtn.addEventListener('click', function(e) {
        e.preventDefault();
        if (userMenu) userMenu.classList.add('d-none');

        // Consulta asíncrona al backend para obtener las empresas del contacto autenticado
        frappe.call({
            method: 'ListenAIQ.utils.login_util.get_user_companies',
            callback: function(r) {
                if (r.message && r.message.length > 1) {
                    let htmlContent = '';
                    
                    r.message.forEach(company => {
                        let logoHtml = company.logo && company.logo !== '/assets/ListenAIQ/images/default-company-logo.png' 
                            ? `<img src="${company.logo}" alt="${company.company_name}" style="max-width:45px; max-height:45px; object-fit:contain; margin-bottom: 1rem;">`
                            : `<svg ...></svg>`; // Icono genérico SVG

                        htmlContent += `
                            <div class="modal-choice-card" onclick="selectActiveCompany('${company.company_id}')" style="width: 100%; height: 180px;">
                                ${logoHtml}
                                <span style="font-weight: 600;">${company.company_name}</span>
                            </div>
                        `;
                    });

                    // Inyección segura del contenedor del modal en el DOM del documento
                    const existingModal = document.getElementById('company-switcher-modal');
                    if (existingModal) existingModal.remove();

                    let modalHtml = `
                    <div id="company-switcher-modal" class="choice-modal-overlay">
                        <div class="choice-modal-content" style="max-width: 500px;">
                            ...
                            <div class="company-switcher-grid">${htmlContent}</div>
                        </div>
                    </div>`;
                    
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                }
            }
        });
    });
}

```

#### B. Ejecución de la Conmutación de Entorno

Al hacer clic en una tarjeta de empresa, la función global `selectActiveCompany` congela la pantalla y despacha la instrucción al servidor:

```javascript
window.selectActiveCompany = function(companyId) {
    frappe.call({
        method: "ListenAIQ.utils.login_util.set_active_company",
        args: { company_id: companyId },
        freeze: true,
        freeze_message: "Cargando entorno de trabajo...",
        callback: function(r) {
            if (r.message) {
                // Redirección limpia al home con las variables de sesión ya actualizadas en backend
                window.location.href = r.message;
            }
        }
    });
};

```

---

### 2.5 Buenas Prácticas y Prevención de Errores Críticos de Desarrollo

#### A. Mitigación de Errores de Tipo de Datos (`AttributeError`) al iterar Tablas Hijas

Un error común en Frappe v13 al manipular arreglos de registros de tablas hijas ocurre cuando se intenta interactuar con las filas tratándolas de forma errónea como objetos de tipo `string` o diccionarios nativos sin envolver, arrojando excepciones tales como:
`AttributeError: 'str' object has no attribute 'cc_company'`.

* **Causa del Error:** Esto sucede típicamente cuando la consulta ORM retorna una lista plana de strings en lugar de un diccionario de campos, o bien cuando en bucles de tipo `for` se extrae el índice o el nombre en lugar del registro completo.
* **Solución Defensiva Implementada:** Al consultar o iterar sobre listas devueltas por `frappe.get_all` o `frappe.get_list`, el desarrollador debe asegurarse de tipar correctamente los campos en el argumento `fields` e interactuar con los elementos mediante la nomenclatura de llaves seguras (`.get()`) o garantizando que los registros se procesen como instancias de tipo `_dict` de Frappe:

```python
# Muestra de consulta y consumo seguro de datos de tablas hijas en Python
companies = frappe.get_all(
    "qp_IQ_ContactCompany",
    filters={"parent": contact_name, "parenttype": "Contact"},
    fields=["cc_company"] # Forzado explícito de campo estructurado en diccionario
)

for row in companies:
    # Forma INCORRECTA que genera riesgos si la fila muta a string: row.cc_company
    # Forma CORRECTA y segura de extracción defensiva:
    active_company_id = row.get("cc_company") 
    if active_company_id:
        # Ejecutar lógica de negocio a salvo de AttributeErrors
        pass

```

#### B. Carga Combinada de Características de la Aplicación (`App Features`)

Al cambiar de compañía, el backend no solo modifica el aislamiento de los datos básicos, sino que reconstruye en tiempo real el licenciamiento funcional permitido. El método `global_website_context` fusiona dinámicamente las características del plan de la empresa activa (`qp_IQ_AppPlan`) junto con las extensiones del perfil de rol (`qp_IQ_PortalRoleFeature`), empaquetando todo en un JSON plano que el frontend consume de forma inmediata:

```python
# Eliminación preventiva de duplicados funcionales entre el Plan y el Perfil del usuario
context.app_features = list(set(context.app_features))
context.app_features_json = json.dumps(context.app_features)

```