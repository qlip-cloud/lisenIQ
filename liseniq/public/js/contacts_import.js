import { Stepper } from './utils/stepper.js';

// Definición del componente de cabecera personalizado
class CustomHeader {
    init(params) {
        this.params = params;
        this.eGui = document.createElement('div');
        this.eGui.style.width = '100%';
        this.eGui.style.display = 'flex';
        this.eGui.style.alignItems = 'center';
        
        const initialValue = params.displayName || '';
        const borderStyle = initialValue ? '1px solid #ced4da' : '2px solid #fc8181';

        this.eGui.innerHTML = `
            <input type="text" 
                class="ag-custom-header-input"
                style="width: 100%; height: 28px; border-radius: 4px; border: ${borderStyle}; padding: 2px 6px; font-size: 12px;" 
                placeholder="Nombre..." 
                value="${initialValue}"/>
        `;
        
        this.input = this.eGui.querySelector('input');
        
        this.input.addEventListener('input', (e) => {
            const val = e.target.value;
            this.input.style.border = val ? '1px solid #ced4da' : '2px solid #fc8181';
            if (this.params.onNameChange) {
                this.params.onNameChange(val);
            }
        });

        // Evitar que el grid capture eventos de clic/arrastre sobre el input
        this.input.addEventListener('click', e => e.stopPropagation());
        this.input.addEventListener('mousedown', e => e.stopPropagation());
    }

    getGui() {
        return this.eGui;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('contacts-import-app')) return;

    frappe.call({
        method: 'liseniq.www.contacts.contacts_import.check_upload_status',
        callback: function(r) {
            if (r.message && r.message.active) {
                // Si hay una carga activa, redireccionar a la pantalla de contactos
                window.location.href = '/contacts';
            }
        }
    });

    const state = {
        currentStep: 1,
        file: null,
        headers: [],
        rows: [], 				                // Array de objetos
        errors: [], 			                // Errores de validación por fila
        existingMap: new Map(),                 // Mapa DNI Objeto Contacto completo
        processResult: null,
        mode: 'upload', 			            // 'upload' o 'edit'
        gridApi: null, 				            // referencia al API de Ag-Grid
        finalStats: { total: 0 },
        dataToProcess: null, 		            // Datos listos para enviar
        options: {                              // Opciones para dropdowns y headers
            document_types: [],
            languages: [],
            countries: [],
            genders: [],
            academic_levels: [],
            status: ['Activo', 'Inactivo'],
            demographic_headers: []             // Nombres de columnas demográficas existentes
        },
        newColumns: [],                         // { id: string, name: string }
        showOnlyErrors: false,
        showOnlyUpdating: false,                // Filtro para mostrar solo actualizaciones reales
        showDeleteList: false                   // Filtro para mostrar lista de eliminación
    };

    // Campos obligatorios para validación frontend
    const MANDATORY_FIELDS = [
        "Nombre", 
        "Apellido", 
        "Tipo de Documento", 
        "Número de Documento (DNI)", 
        "País", 
        "Idioma"
    ];

    const ui = {
        stepperContainer: 'import-stepper-container',
        step1: document.getElementById('step-1'),
        step2: document.getElementById('step-2'),
        step3: document.getElementById('step-3'),
        downloadBtn: document.getElementById('download-template'),
        fileInput: document.getElementById('file-input'),
        dropzone: document.getElementById('dropzone'),
        dropzoneFilename: document.getElementById('dropzone-filename'),
        btnCancel: document.getElementById('btn-cancel'),
        btnContinue: document.getElementById('btn-continue'),
        validationSummary: document.getElementById('validation-summary'),
        gridContainer: document.getElementById('myGrid'),
        btnBackToStep1: document.getElementById('btn-back-to-step1'),
        btnValidateContinue: document.getElementById('btn-validate-continue'),
        processResult: document.getElementById('process-result'),
        btnBackToStep2: document.getElementById('btn-back-to-step2'),
        btnFinish: document.getElementById('btn-finish'),
        optUpload: document.getElementById('opt-upload'),
        optEdit: document.getElementById('opt-edit'),
        uploadArea: document.getElementById('upload-area'),
        btnAddRow: document.getElementById('btn-add-row'),
        btnAddColumn: document.getElementById('btn-add-column')
    };

    if (ui.fileInput) ui.fileInput.value = '';
    if (ui.dropzoneFilename) ui.dropzoneFilename.textContent = '';
    state.file = null;

    const stepper = new Stepper(ui.stepperContainer, ['Cargar/Seleccionar', 'Validar y Editar', 'Procesar']);
    stepper.render();
    updateStepUI();

    //Obtener opciones para dropdowns y columnas demográficas
    fetchOptions();

    function fetchOptions() {
        frappe.call({
            method: 'liseniq.www.contacts.contacts_import.get_grid_options',
            callback: function(r) {
                if(r.message) {
                    // Actualizamos el estado con las opciones recibidas
                    state.options = { ...state.options, ...r.message };
                    
                    // Si el grid ya existe, forzamos la actualización de las definiciones
                    if (state.gridApi) {
                        const newDefs = getAllColDefs();
                        state.gridApi.setGridOption('columnDefs', newDefs);
                        state.gridApi.redrawRows();
                    }
                }
            }
        });
    }

    // Definición base de columnas (estáticas)
    const getBaseColDefs = () => [
        {
            headerName: "#",
            maxWidth: 60,
            minWidth: 50,
            pinned: "left",
            valueGetter: "node.rowIndex + 1",
            editable: false,
            sortable: false, // No ordenable porque siempre debe ser secuencial visualmente
            filter: false,
            resizable: false,
            cellStyle: { 
                'text-align': 'center', 
                'background-color': '#f8f9fa', 
                'color': '#737373',
                'font-weight': '600'
            }
        },
        { 
            field: "Nombre", 
            headerName: "Nombre (Obligatorio)", 
            editable: true, 
            minWidth: 150, 
            pinned: 'left',
            wrapText: true,
            autoHeight: true,
            filter: true,
            cellStyle: params => !params.value ? {backgroundColor: '#ffe6e6'} : null
        },
        { 
            field: "Apellido", 
            headerName: "Apellido (Obligatorio)", 
            editable: true, 
            minWidth: 150, 
            pinned: 'left',
            wrapText: true,
            autoHeight: true,
            filter: true,
            cellStyle: params => !params.value ? {backgroundColor: '#ffe6e6'} : null
        },
        { 
            field: "Tipo de Documento", 
            headerName: "Tipo Doc (Obligatorio)", 
            editable: true,
            minWidth: 180,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: {
                values: state.options.document_types || []
            },
            cellStyle: params => !params.value ? {backgroundColor: '#ffe6e6'} : null
        },
        { 
            field: "Número de Documento (DNI)", 
            headerName: "Número Doc (Obligatorio)", 
            editable: true, 
            minWidth: 140, 
            wrapText: true, 
            autoHeight: true, 
            filter: true,
            cellStyle: params => !params.value ? {backgroundColor: '#ffe6e6'} : null
        },
        { 
            field: "País", 
            headerName: "País (Obligatorio)", 
            editable: true,
            minWidth: 150,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: {
                values: state.options.countries || []
            },
            cellStyle: params => !params.value ? {backgroundColor: '#ffe6e6'} : null
        },
        { 
            field: "Idioma", 
            headerName: "Idioma (Obligatorio)", 
            editable: true,
            minWidth: 120,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: {
                values: state.options.languages || []
            },
            cellStyle: params => !params.value ? {backgroundColor: '#ffe6e6'} : null
        },
        { 
            field: "Estatus", 
            headerName: "Estatus", 
            editable: true,
            minWidth: 100,
            cellEditor: 'agSelectCellEditor', 
            cellEditorParams: { values: state.options.status }
        },
        { 
            field: "Género", 
            headerName: "Género", 
            editable: true, 
            minWidth: 120,
            cellEditor: 'agSelectCellEditor', 
            cellEditorParams: { values: state.options.genders || [] } 
        },
        { field: "Fecha de Nacimiento", headerName: "Fecha Nacimiento (YYYY-MM-DD)", editable: true, wrapText: true, autoHeight: true, filter: true },
        { 
            field: "Nivel Académico", 
            headerName: "Nivel Académico", 
            editable: true,
            minWidth: 150,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: {
                values: state.options.academic_levels || []
            }
        },
        { field: "Correo (Opcional)", headerName: "Correo", editable: true, minWidth: 200, wrapText: true, autoHeight: true },
        { field: "Fecha de Ingreso", headerName: "Fecha Ingreso (YYYY-MM-DD)", editable: true }
    ];

    // Función para generar todas las columnas incluyendo las dinámicas de demográficos
    function getAllColDefs() {
        const cols = getBaseColDefs();
        const stdFields = cols.map(c => c.field);
        
        if (state.options.demographic_headers && state.options.demographic_headers.length > 0) {
            state.options.demographic_headers.forEach(header => {
                if (!stdFields.includes(header)) {
                    cols.push({
                        field: header,
                        headerName: header,
                        editable: true,
                        minWidth: 130,
                        cellStyle: { 'backgroundColor': '#f9f9ff' }
                    });
                }
            });
        }
        
        if (state.headers && state.headers.length > 0) {
            const currentFields = cols.map(c => c.field);
            state.headers.forEach(h => {
                if (!currentFields.includes(h)) {
                    cols.push({
                        field: h,
                        headerName: h,
                        editable: true,
                        minWidth: 130,
                        cellStyle: { 'backgroundColor': '#f9f9ff' }
                    });
                }
            });
        }

        state.newColumns.forEach(col => {
            cols.push({
                field: col.id,
                headerName: col.name,
                headerComponent: 'customHeader',
                headerComponentParams: {
                    displayName: col.name,
                    onNameChange: (newName) => {
                        col.name = newName;
                        validateRealTime(); // Revalidar al cambiar nombre
                    }
                },
                editable: true,
                minWidth: 160,
                cellStyle: { 'backgroundColor': '#e6f7ff' }
            });
        });

        return cols;
    }

    // helpers
    function showStep(n) {
        state.currentStep = n;
        ui.step1.classList.toggle('d-none', n !== 1);
        ui.step2.classList.toggle('d-none', n !== 2);
        ui.step3.classList.toggle('d-none', n !== 3);
        stepper.update(n);

        if (n === 2) {
            setTimeout(() => initAgGrid(), 100);
        }
    }
    
    // Función auxiliar para comparar si una fila tiene cambios reales respecto al existente
    function isRowDifferent(row, existing) {
        // Normalizar valores para comparación
        const norm = (v) => (v === null || v === undefined) ? '' : String(v).trim();
        
        // Obtenemos todas las claves presentes en ambos objetos
        const allKeys = new Set([...Object.keys(row), ...Object.keys(existing)]);
        
        for (let key of allKeys) {
            // Ignorar campos internos o metadatos
            if (key.startsWith('_') || key === 'row_id') continue;
            
            const valRow = norm(row[key]);
            const valExisting = norm(existing[key]);
            
            if (valRow !== valExisting) {
                return true;
            }
        }
        return false;
    }

    // Función de Validación en Tiempo Real
    function validateRealTime() {
        if (!state.gridApi) return;

        let hasErrors = false;
        let errorCount = 0;
        const validationErrors = [];
        
        // Contadores para el resumen
        let newCount = 0;
        let updateCount = 0;
        let unchangedCount = 0;

        // Conjuntos para verificar duplicados
        const seenDNIs = new Set();
        const duplicateDNIsInFile = new Set();
        const seenEmails = new Set();
        const duplicateEmailsInFile = new Set();
        
        // Detección de duplicados internos
        state.gridApi.forEachNode((node) => {
            const row = node.data;
            
            // DNI Duplicado
            const dni = (row['Número de Documento (DNI)'] || '').toString().trim();
            if (dni) {
                if (seenDNIs.has(dni)) duplicateDNIsInFile.add(dni);
                else seenDNIs.add(dni);
            }

            // Correo Duplicado
            const email = (row['Correo (Opcional)'] || '').toString().trim().toLowerCase();
            if (email) {
                if (seenEmails.has(email)) duplicateEmailsInFile.add(email);
                else seenEmails.add(email);
            }
        });

        // Mapas de validación de opciones
        const validationMaps = {
            "Tipo de Documento": state.options.document_types,
            "País": state.options.countries,
            "Idioma": state.options.languages,
            "Estatus": state.options.status,
            "Género": state.options.genders,
            "Nivel Académico": state.options.academic_levels
        };

        // Validar Nombres de Columnas Nuevas
        const invalidColNames = state.newColumns.filter(c => !c.name || c.name.trim() === '');
        if (invalidColNames.length > 0) {
            hasErrors = true;
            validationErrors.push({ row: 'Cabecera', missing: ['Nombre de columna(s) nuevo demográfico vacío'] });
        }

        // Validar Densidad de Columnas Nuevas (Al menos 1 valor)
        const newColCounts = {};
        state.newColumns.forEach(c => newColCounts[c.id] = 0);

        state.gridApi.forEachNode((node, index) => {
            const row = node.data;
            const missing = [];
            const invalidValues = [];
            const rowErrors = [];
            
            // Validar Campos Obligatorios Estándar
            MANDATORY_FIELDS.forEach(field => {
                if (!row[field] || row[field].toString().trim() === "") {
                    missing.push(field);
                }
            });

            // Validar Listas
            Object.keys(validationMaps).forEach(field => {
                const val = (row[field] || '').toString().trim();
                const validOptions = validationMaps[field] || [];
                if (val && validOptions.length > 0 && !validOptions.includes(val)) {
                    invalidValues.push(`${val} no es válido en ${field}`);
                }
            });

            const dni = (row['Número de Documento (DNI)'] || '').toString().trim();
            let isUpdate = false;
            let isUnchanged = false;

            if (dni) {
                // Validación de Formato DNI
                const dniRegex = /^[a-zA-Z0-9]+$/;
                if (!dniRegex.test(dni)) {
                    rowErrors.push(`DNI contiene caracteres inválidos (solo letras y números)`);
                }

                // Duplicado en DB y Detección de Cambios
                if (state.existingMap.has(dni)) {
                    const existingData = state.existingMap.get(dni);
                    // Comparar para ver si hay cambios reales
                    if (isRowDifferent(row, existingData)) {
                        updateCount++;
                        isUpdate = true;
                    } else {
                        unchangedCount++;
                        isUnchanged = true;
                    }
                } else {
                    newCount++;
                }

                // Duplicado en Archivo
                if (duplicateDNIsInFile.has(dni)) {
                    rowErrors.push(`DNI ${dni} duplicado en el archivo`);
                }
            }

            // Marcar estado de la fila para filtros
            node.data._isUpdate = isUpdate;
            node.data._isUnchanged = isUnchanged;

            // Validación de Correos Duplicados
            const email = (row['Correo (Opcional)'] || '').toString().trim().toLowerCase();
            if (email && duplicateEmailsInFile.has(email)) {
                rowErrors.push(`Correo ${email} duplicado en el archivo`);
            }

            // Contar valores para columnas nuevas
            state.newColumns.forEach(c => {
                if (row[c.id] && row[c.id].toString().trim() !== "") {
                    newColCounts[c.id]++;
                }
            });

            // Consolidar errores de fila
            if (missing.length > 0) rowErrors.push("Faltan: " + missing.join(', '));
            if (invalidValues.length > 0) rowErrors.push(invalidValues.join(', '));

            // Marcar estado interno de error
            const rowHasError = rowErrors.length > 0;
            node.data._hasError = rowHasError;

            if (rowHasError) {
                hasErrors = true;
                errorCount++;
                validationErrors.push({ row: node.rowIndex + 1, missing: rowErrors });
            }
        });

        // Verificar si alguna columna nueva está vacía
        state.newColumns.forEach(c => {
            if (newColCounts[c.id] === 0) {
                hasErrors = true;
                validationErrors.push({ row: 'Columna', missing: [`La columna nueva '${c.name || 'Sin Nombre'}' debe tener al menos un valor.`] });
            }
        });

        // Cálculo de registros a eliminar
        let deletedContacts = [];
        if (state.existingMap.size > 0) {
            // Filtramos los contactos que no están en el archivo
            // Iteramos sobre el mapa de existentes
            for (const [dni, contactData] of state.existingMap) {
                if (!seenDNIs.has(dni)) {
                    deletedContacts.push(contactData);
                }
            }
        }
        const deleteCount = deletedContacts.length;

        if (errorCount === 0 && state.showOnlyErrors) {
            state.showOnlyErrors = false;
            state.gridApi.onFilterChanged();
        }

        if (updateCount === 0 && state.showOnlyUpdating) {
             state.showOnlyUpdating = false;
             state.gridApi.onFilterChanged();
        }


        // Control del botón Continuar
        ui.btnValidateContinue.disabled = hasErrors;

        // Actualizar resumen visual con conteo detallado
        let summaryHtml = '';
        
        const errorFilterClass = state.showOnlyErrors ? 'active-filter' : '';
        const errorFilterText = state.showOnlyErrors ? 'Mostrar Todos' : 'Con Errores';
        const errorDisplay = errorCount > 0 ? 'block' : 'none';

        // Estilos para el botón de eliminar
        const deleteFilterClass = state.showDeleteList ? 'active-filter' : '';
        const deleteDisplay = deleteCount > 0 ? 'block' : 'none';

        // Estilos para el botón de actualizar
        const isUpdateActive = state.showOnlyUpdating;
        const updateStyle = isUpdateActive 
            ? 'border: 2px solid #856404; background-color: #ffeeba !important; font-weight: 600; box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);' 
            : 'background-color: #fff3cd; border-color: #ffeeba;';
        const updateDisplay = updateCount > 0 ? 'block' : 'none';
        
        // Bloque de "Sin Cambios" para dar feedback completo
        const unchangedDisplay = unchangedCount > 0 ? 'block' : 'none';

        summaryHtml += `
            <div style="display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap;">
                <div class="alert alert-info" style="flex: 1; margin: 0; text-align: center; min-width: 140px;">
                    <strong>${newCount}</strong><br>Crear Nuevos
                </div>
                
                <div id="btn-toggle-updating" class="alert alert-warning" title="Click para filtrar actualizaciones reales" style="flex: 1; margin: 0; text-align: center; color: #856404; cursor: pointer; transition: all 0.2s ease; ${updateStyle} display: ${updateDisplay}; min-width: 140px;">
                    <strong>${updateCount}</strong><br>${isUpdateActive ? 'Mostrar Todos' : 'Actualizar'}
                </div>

                <div class="alert alert-light" style="flex: 1; margin: 0; text-align: center; color: #6c757d; background-color: #f8f9fa; border-color: #f8f9fa; display: ${unchangedDisplay}; min-width: 140px;">
                    <strong>${unchangedCount}</strong><br>Sin Cambios
                </div>

                <div id="btn-toggle-deleted" class="alert alert-secondary alert-delete-clickable ${deleteFilterClass}" style="flex: 1; margin: 0; text-align: center; color: #383d41; background-color: #e2e3e5; border-color: #d6d8db; display: ${deleteDisplay}; min-width: 140px;">
                    <strong>${deleteCount}</strong><br>Eliminar
                </div>
                
                <div id="btn-toggle-errors" class="alert alert-danger alert-error-clickable ${errorFilterClass}" title="Click para filtrar errores" style="flex: 1; margin: 0; text-align: center; display: ${errorDisplay}; min-width: 140px;">
                    <strong>${errorCount}</strong><br>${errorFilterText}
                </div>
            </div>
        `;

        // Sección de lista de eliminados
        if (state.showDeleteList && deleteCount > 0) {
             summaryHtml += `
                <div class="alert alert-secondary" style="background-color: #f1f3f5; border: 1px solid #d6d8db; color: #383d41; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                    <strong>Contactos que serán eliminados:</strong><br>
                    <ul class="deleted-contacts-list" style="margin-top: 0.5rem; padding-left: 1.2rem;">
            `;
            deletedContacts.forEach(c => {
                // Adaptamos las claves a las que devuelve el nuevo backend
                const nombre = c['Nombre'] || '';
                const apellido = c['Apellido'] || '';
                const dni = c['Número de Documento (DNI)'] || '';
                const email = c['Correo (Opcional)'] || 'Sin correo';
                
                summaryHtml += `<li style="margin-bottom: 6px;">
                    <strong>${nombre} ${apellido}</strong><br>
                    <small style="color: #666;">DNI: ${dni} | Email: ${email}</small>
                </li>`;
            });
            summaryHtml += `</ul></div>`;
        }

        if (hasErrors) {
            summaryHtml += `
                <div class="alert alert-danger" style="background-color: #fff5f5; border: 1px solid #fc8181; color: #c53030; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                    <strong>Errores de validación detectados:</strong><br>
                    <ul>
            `;
            validationErrors.forEach(e => {
                summaryHtml += `<li>${typeof e.row === 'number' ? 'Fila ' + e.row : e.row}: ${e.missing.join(' | ')}</li>`;
            });
            summaryHtml += `</ul></div>`;
        } else if (!hasErrors && !state.showDeleteList) {
             summaryHtml += `
            <div class="alert alert-success" style="background-color: #f0fff4; border: 1px solid #68d391; color: #276749; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <i class="fa fa-check-circle"></i> Todos los datos son válidos. Listo para procesar.
            </div>`;
        }
        
        ui.validationSummary.innerHTML = summaryHtml;
        
        // Listeners para botones interactivos
        const toggleBtn = document.getElementById('btn-toggle-errors');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                state.showOnlyErrors = !state.showOnlyErrors;
                if (state.showOnlyErrors) {
                    state.showOnlyUpdating = false;
                }
                state.gridApi.onFilterChanged(); 
                validateRealTime(); 
            });
        }
        
        const deleteBtn = document.getElementById('btn-toggle-deleted');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                state.showDeleteList = !state.showDeleteList;
                validateRealTime(); // Re-renderizar para mostrar/ocultar lista
            });
        }

        const updateBtn = document.getElementById('btn-toggle-updating');
        if (updateBtn) {
            updateBtn.addEventListener('click', () => {
                state.showOnlyUpdating = !state.showOnlyUpdating;
                if (state.showOnlyUpdating) {
                    state.showOnlyErrors = false;
                }
                state.gridApi.onFilterChanged();
                validateRealTime();
            });
        }
        
        state.gridApi.redrawRows();
    }

    function initAgGrid() {
        ui.gridContainer.innerHTML = '';
        const colDefs = getAllColDefs();

        const gridOptions = {
            rowData: state.rows,
            columnDefs: colDefs,
            components: {
                customHeader: CustomHeader
            },
            defaultColDef: {
                flex: 1,
                minWidth: 120,
                resizable: true,
            },
            pagination: true,
            paginationPageSize: 20,
            theme: "legacy",
            rowSelection: { mode: 'multiRow' },
            
            // Regla para estilizar filas con error
            rowClassRules: {
                'row-error-highlight': (params) => {
                    return params.data && params.data._hasError;
                }
            },
            
            // Lógica de Filtro Externo
            isExternalFilterPresent: () => {
                return state.showOnlyErrors || state.showOnlyUpdating;
            },
            doesExternalFilterPass: (node) => {
                if (state.showOnlyErrors) {
                    return node.data && node.data._hasError;
                }
                if (state.showOnlyUpdating) {
                    // Filtrar solo los que están marcados como actualización real
                    return node.data && node.data._isUpdate;
                }
                return true;
            },

            onGridReady: (params) => {
                state.gridApi = params.api;
                validateRealTime(); // Validar al cargar
            },
            onCellValueChanged: (params) => {
                validateRealTime(); // Validar al editar
            },
            onModelUpdated: () => {
                // Útil para cuando cambian filas, aunque validateRealTime maneja la mayoría
            }
        };

        agGrid.createGrid(ui.gridContainer, gridOptions);
        
        ui.btnAddRow.style.display = 'inline-block';
        ui.btnAddColumn.style.display = 'inline-block';
    }

    // Handlers de Paso 1
    ui.optUpload.addEventListener('click', () => {
        state.file = null;
        if (ui.fileInput) ui.fileInput.value = '';
        if (ui.dropzoneFilename) ui.dropzoneFilename.textContent = '';
        state.showOnlyErrors = false;
        state.showOnlyUpdating = false;
        state.showDeleteList = false;
        
        setMode('upload');
        if (ui.fileInput) ui.fileInput.click(); 
    });

    ui.optEdit.addEventListener('click', () => {
        setMode('edit');
        fetchExistingContacts();
    });

    function setMode(m) {
        state.mode = m;
        if (m === 'upload') {
            ui.optUpload.classList.add('selected');
            ui.optEdit.classList.remove('selected');
            ui.btnContinue.disabled = !state.file;
        } else {
            ui.optEdit.classList.add('selected');
            ui.optUpload.classList.remove('selected');
        }
        ui.uploadArea.style.display = 'block';
    }

    function fetchExistingContacts() {
        ui.optEdit.innerHTML = `
            <div style="padding:18px; text-align:center;">
                <i class="fa fa-spinner fa-spin" style="font-size:24px;color:#7B24FF;"></i>
                <div style="margin-top:8px;color:#7B24FF;">Cargando contactos...</div>
            </div>`;
        ui.optEdit.style.pointerEvents = 'none';

        ui.btnContinue.disabled = true;
        ui.btnContinue.textContent = 'Cargando...';

        frappe.call({
            method: 'liseniq.www.contacts.contacts_import.get_contacts_for_grid',
            callback: function(r) {
                ui.optEdit.innerHTML = `
                    <div style="display:flex;align-items:center;gap:12px;padding:18px;">
                        <i class="fa fa-desktop" style="font-size:18px;color:#7B24FF;"></i>
                        <div>
                            <div style="font-weight:600;">Editar en línea</div>
                            <div style="color:#737373;font-size:0.85rem;">Editar existentes o crear nuevos</div>
                        </div>
                    </div>`;
                ui.optEdit.style.pointerEvents = 'auto';
                
                ui.btnContinue.textContent = 'Continuar';
                
                if (r.message) {
                    state.rows = r.message.rows || [];
                    if (r.message.demographic_headers) {
                        state.options.demographic_headers = r.message.demographic_headers;
                    }
                    state.errors = [];
                    state.existingMap = new Map();
                    (r.message.rows || []).forEach(row => {
                        const dni = (row['Número de Documento (DNI)'] || '').toString().trim();
                        if (dni) {
                            state.existingMap.set(dni, row);
                        }
                    });
                    
                    state.showOnlyErrors = false;
                    state.showOnlyUpdating = false;
                    state.showDeleteList = false;
                } else {
                    state.rows = [];
                }
                ui.btnContinue.disabled = false;
                showStep(2);
            },
            error: function(r) {
                ui.optEdit.innerHTML = `
                    <div style="display:flex;align-items:center;gap:12px;padding:18px;">
                        <i class="fa fa-desktop" style="font-size:18px;color:#7B24FF;"></i>
                        <div>
                            <div style="font-weight:600;">Editar en línea</div>
                            <div style="color:#737373;font-size:0.85rem;">Editar existentes o crear nuevos</div>
                        </div>
                    </div>`;
                ui.optEdit.style.pointerEvents = 'auto';
                
                state.rows = [];
                ui.btnContinue.textContent = 'Continuar';
                ui.btnContinue.disabled = false;
                showStep(2);
            }
        });
    }

    ui.downloadBtn.addEventListener('click', (e) => {
        e.preventDefault();
        window.location = '/api/method/liseniq.www.contacts.contacts_import.download_template';
    });

    ui.dropzone.addEventListener('click', () => ui.fileInput.click());
    ui.dropzone.addEventListener('dragover', (e) => { e.preventDefault(); ui.dropzone.classList.add('dragover'); });
    ui.dropzone.addEventListener('dragleave', (e) => { e.preventDefault(); ui.dropzone.classList.remove('dragover'); });
    ui.dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        ui.dropzone.classList.remove('dragover');
        const f = (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) || null;
        handleFileSelect(f);
    });

    ui.fileInput.addEventListener('change', function () {
        handleFileSelect(this.files[0]);
    });

    function handleFileSelect(f) {
        if (!f) return;
        const ext = f.name.split('.').pop().toLowerCase();
        if (!['xlsx','xls','csv'].includes(ext)) {
            alert('Tipo de archivo no permitido. Use .xlsx o .csv');
            ui.fileInput.value = '';
            return;
        }
        state.file = f;
        ui.dropzoneFilename.textContent = `${f.name} · ${Math.round(f.size/1024)} KB`;
        ui.btnContinue.disabled = false;
    }

    ui.btnCancel.addEventListener('click', () => { window.location.href = '/contacts'; });

    ui.btnContinue.addEventListener('click', () => {
        if (state.mode === 'edit') {
            state.rows = state.rows || [];
            showStep(2);
            return;
        }

        if (state.mode === 'upload' && !state.file) {
            alert("Por favor seleccione un archivo para cargar.");
            return;
        }
        
        ui.btnContinue.disabled = true;
        ui.btnContinue.textContent = 'Validando...';
        const fd = new FormData();
        fd.append('file', state.file);
        
        fetch('/api/method/liseniq.www.contacts.contacts_import.validate_contacts', {
            method: 'POST',
            body: fd,
            headers: {
                'X-Frappe-CSRF-Token': frappe.csrf_token || window.csrf_token
            }
        }).then(r => r.json()).then(res => {
            ui.btnContinue.disabled = false;
            ui.btnContinue.textContent = 'Continuar';
            const data = res.message || res;
            if (!data.ok) {
                alert(data.error || 'Error de validación');
                return;
            }
            state.headers = data.headers || [];
            state.rows = data.rows || [];
            state.errors = data.errors || [];
            state.showOnlyErrors = false;
            state.showOnlyUpdating = false;
            state.showDeleteList = false;
            
            // Guardamos los contactos existentes completos con el retun del backend 'existing_grid_rows'
            state.existingMap = new Map();
            (data.existing_grid_rows || []).forEach(row => {
                 const dni = (row['Número de Documento (DNI)'] || '').toString().trim();
                 if (dni) {
                     state.existingMap.set(dni, row);
                 }
            });
            
            if (data.valid_options) {
                state.options = { ...state.options, ...data.valid_options };
            }
            
            showStep(2);

        }).catch(err => {
            ui.btnContinue.disabled = false;
            ui.btnContinue.textContent = 'Continuar';
            alert('Error en la validación: ' + (err.message || err));
        });
    });

    ui.btnAddRow.addEventListener('click', () => {
        if (state.gridApi) {
            const newRow = {};
            getAllColDefs().forEach(col => newRow[col.field] = "");
            newRow["Estatus"] = "Activo";
            state.gridApi.applyTransaction({ add: [newRow] });
        }
    });

    ui.btnAddColumn.addEventListener('click', () => {
        const id = `new_col_${Date.now()}`;
        state.newColumns.push({ id: id, name: '' });

        if (state.gridApi) {
            state.gridApi.setGridOption('columnDefs', getAllColDefs());
            setTimeout(() => {
                validateRealTime();
                state.gridApi.ensureColumnVisible(id);
            }, 100);
        }
    });

    ui.btnBackToStep1.addEventListener('click', () => {
        showStep(1);
    });

    ui.btnValidateContinue.addEventListener('click', () => {
        let gridData = [];
        const seenDNIs = new Set(); 

        if (state.gridApi) {
            state.gridApi.forEachNode(node => {
                let row = { ...node.data };
                delete row._hasError; 
                delete row._isUpdate;
                delete row._isUnchanged;

                const dni = (row['Número de Documento (DNI)'] || '').toString().trim();
                if (dni) {
                    seenDNIs.add(dni);
                }

                state.newColumns.forEach(c => {
                    if (row[c.id]) {
                        row[c.name] = row[c.id];
                        delete row[c.id]; 
                    }
                });
                gridData.push(row);
            });
        } else {
            gridData = state.rows;
            gridData.forEach(r => {
                const dni = (r['Número de Documento (DNI)'] || '').toString().trim();
                if (dni) seenDNIs.add(dni);
            });
        }

        if (gridData.length === 0) {
            alert("No hay datos para procesar.");
            return;
        }

        let deleteCount = 0;
        if (state.existingMap.size > 0) {
            for (const dni of state.existingMap.keys()) {
                if (!seenDNIs.has(dni)) {
                    deleteCount++;
                }
            }
        }

        const proceed = () => {
            state.finalStats.total = gridData.length;
            state.dataToProcess = JSON.stringify(gridData);

            ui.btnFinish.disabled = false;
            ui.btnFinish.textContent = 'Finalizar';
            ui.btnBackToStep2.style.display = 'inline-block';
            
            renderProcessResult();
            showStep(3);
        };

        if (deleteCount > 0) {
            frappe.confirm(
                `Atención: Se han detectado <b>${deleteCount}</b> contactos que no están en el archivo y serán <b>eliminados</b> (archivados).<br><br>¿Desea continuar con el proceso?`,
                () => {
                    proceed();
                }
            );
        } else {
            proceed();
        }
    });

    function renderProcessResult() {
        const now = new Date();
        const dateStr = now.toLocaleDateString() + ' ' + now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        let html = `<div class="import-results-card">`;
        html += `
            <div class="result-header">
                <div class="result-date"><i class="fa fa-calendar-o"></i> Fecha de carga: ${dateStr}</div>
            </div>
        `;
        const totalRows = state.finalStats.total || 0;
        html += `<div class="result-stats-container">`;
        html += `
            <div class="result-stat-item">
                <div class="stat-value">${totalRows}</div>
                <div class="stat-label">Registros a procesar</div>
            </div>
        `;
        html += `</div>`; 
        html += `
            <div class="ready-message" style="padding: 1.5rem;">
                <i class="fa fa-clock-o"></i> El proceso será iniciado en segundo plano al presionar el botón <strong>Finalizar</strong>.<br>
                <span style="font-size:0.85rem; font-weight:400; color:#666;">
                    Recibirá una notificación en el sistema cuando la carga finalice con el detalle de registros creados y actualizados.
                </span>
            </div>
        `;
        html += `</div>`;
        ui.processResult.innerHTML = html;
    }

    ui.btnFinish.addEventListener('click', () => {
        ui.btnFinish.disabled = true;
        ui.btnFinish.textContent = 'Iniciando...';
        
        const payload = { rows_json: state.dataToProcess };
        if (state.file && state.file.name) {
            payload.file_name = state.file.name;
        }

        fetch('/api/method/liseniq.www.contacts.contacts_import.upload_contacts_json', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': frappe.csrf_token || window.csrf_token
            },
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(res => {
            window.location.href = '/contacts';
        }).catch(err => {
            ui.btnFinish.disabled = false;
            ui.btnFinish.textContent = 'Finalizar';
            alert('Error al iniciar el proceso: ' + (err.message || err));
        });
    });

    ui.btnBackToStep2.addEventListener('click', () => {
        showStep(2);
    });

    function updateStepUI() {
        showStep(state.currentStep || 1);
    }
});