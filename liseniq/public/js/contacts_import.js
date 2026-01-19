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
        rows: [], 				// Array de objetos
        errors: [], 			// Errores de validación por fila
        processResult: null,
        mode: 'upload', 			// 'upload' o 'edit'
        gridApi: null, 				// referencia al API de Ag-Grid
        finalStats: { total: 0 },
        dataToProcess: null, 		// Datos listos para enviar
        options: {                  // Opciones para dropdowns y headers
            document_types: [],
            languages: [],
            countries: [],
            genders: [],
            academic_levels: [],
            status: ['Activo', 'Inactivo'],
            demographic_headers: [] // Nombres de columnas demográficas existentes
        },
        newColumns: [] // { id: string, name: string }
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

    // Función de Validación en Tiempo Real
    function validateRealTime() {
        if (!state.gridApi) return;

        let hasErrors = false;
        let errorCount = 0;
        const validationErrors = [];

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
            
            // Validar Campos Obligatorios Estándar
            MANDATORY_FIELDS.forEach(field => {
                if (!row[field] || row[field].toString().trim() === "") {
                    missing.push(field);
                }
            });

            // Contar valores para columnas nuevas
            state.newColumns.forEach(c => {
                if (row[c.id] && row[c.id].toString().trim() !== "") {
                    newColCounts[c.id]++;
                }
            });

            if (missing.length > 0) {
                hasErrors = true;
                errorCount++;
                if (validationErrors.length < 5) { 
                    validationErrors.push({ row: index + 1, missing: missing });
                }
            }
        });

        // Verificar si alguna columna nueva está totalmente vacía
        state.newColumns.forEach(c => {
            if (newColCounts[c.id] === 0) {
                hasErrors = true;
                validationErrors.push({ row: 'Columna', missing: [`La columna nueva '${c.name || 'Sin Nombre'}' debe tener al menos un valor.`] });
            }
        });

        // 1. Control del botón Continuar
        ui.btnValidateContinue.disabled = hasErrors;

        // 2. Actualizar resumen visual
        if (hasErrors) {
            let summaryHtml = `
                <div class="alert alert-danger" style="background-color: #fff5f5; border: 1px solid #fc8181; color: #c53030; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                    <strong>Validación incompleta:</strong><br>
                    <ul>
            `;
            validationErrors.forEach(e => {
                summaryHtml += `<li>${typeof e.row === 'number' ? 'Fila ' + e.row : e.row}: ${e.missing.join(', ')}</li>`;
            });
            if (errorCount > 5) {
                summaryHtml += `<li>... y ${errorCount - 5} filas más con errores.</li>`;
            }
            summaryHtml += `</ul></div>`;
            ui.validationSummary.innerHTML = summaryHtml;
        } else {
            ui.validationSummary.innerHTML = `
            <div class="alert alert-success" style="background-color: #f0fff4; border: 1px solid #68d391; color: #276749; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <i class="fa fa-check-circle"></i> Validación exitosa.
            </div>`;
        }
        
        state.gridApi.refreshCells({ force: true });
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
            rowSelection: 'multiple',
            onGridReady: (params) => {
                state.gridApi = params.api;
                validateRealTime(); // Validar al cargar
            },
            onCellValueChanged: (params) => {
                validateRealTime(); // Validar al editar
            },
            onModelUpdated: () => {
                setTimeout(validateRealTime, 0); 
            }
        };

        agGrid.createGrid(ui.gridContainer, gridOptions);
        
        ui.btnAddRow.style.display = 'inline-block';
        ui.btnAddColumn.style.display = 'inline-block';
    }

    // Handlers de Paso 1
    ui.optUpload.addEventListener('click', () => {
        // Limpiar archivo anterior si existe
        state.file = null;
        if (ui.fileInput) ui.fileInput.value = '';
        if (ui.dropzoneFilename) ui.dropzoneFilename.textContent = '';
        
        // Cambiar modo y deshabilitar continuar hasta que se elija nuevo archivo
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

    // Agregar columna vacía para que el usuario la nombre
    ui.btnAddColumn.addEventListener('click', () => {
        const id = `new_col_${Date.now()}`;
        state.newColumns.push({ id: id, name: '' });

        if (state.gridApi) {
            state.gridApi.setGridOption('columnDefs', getAllColDefs());
            // Validar que tenga nombre
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
        if (state.gridApi) {
            state.gridApi.forEachNode(node => {
                let row = { ...node.data };

                // Mapear IDs temporales a nombres reales para el backend
                state.newColumns.forEach(c => {
                    if (row[c.id]) {
                        row[c.name] = row[c.id];
                        delete row[c.id]; // Limpiar ID temporal
                    }
                });
                gridData.push(row);
            });
        } else {
            gridData = state.rows;
        }

        if (gridData.length === 0) {
            alert("No hay datos para procesar.");
            return;
        }

        state.finalStats.total = gridData.length;
        state.dataToProcess = JSON.stringify(gridData);

        ui.btnFinish.disabled = false;
        ui.btnFinish.textContent = 'Finalizar';
        ui.btnBackToStep2.style.display = 'inline-block';
        
        renderProcessResult();
        showStep(3);
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
            // El backend devuelve status queued y mensaje
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