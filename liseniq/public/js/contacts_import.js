import { Stepper } from './utils/stepper.js';

document.addEventListener('DOMContentLoaded', function () {
	if (!document.getElementById('contacts-import-app')) return;

	const state = {
		currentStep: 1,
		file: null,
		headers: [],
		rows: [], 				// Array de objetos
		errors: [], 			// Errores de validación por fila
		processResult: null,
		mode: 'upload', 			// 'upload' o 'edit'
		gridApi: null, 				// referencia al API de Ag-Grid
        demographicColsCount: 1, 	// Inicialmente 1 par de columnas demográficas
        finalStats: { total: 0 },
        dataToProcess: null, 		// Datos listos para enviar
        options: {                  // Opciones para dropdowns (inicializadas vacías)
            document_types: [],
            languages: [],
            countries: [],
            genders: [],
            academic_levels: [],
            status: ['Activo', 'Inactivo']
        }
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
        btnAddDemo: document.getElementById('btn-add-demo')
	};

	const stepper = new Stepper(ui.stepperContainer, ['Cargar/Seleccionar', 'Validar y Editar', 'Procesar']);
	stepper.render();
	updateStepUI();

    // Inicializar: Obtener opciones para dropdowns
    fetchOptions();

    function fetchOptions() {
        frappe.call({
            method: 'liseniq.www.contacts.contacts_import.get_grid_options',
            callback: function(r) {
                if(r.message) {
                    // Actualizamos el estado con las opciones recibidas
                    state.options = { ...state.options, ...r.message };

                    if (state.gridApi) {
                        const newDefs = getAllColDefs();
                        state.gridApi.setGridOption('columnDefs', newDefs);
                        // Redibujar filas para asegurar consistencia visual
                        state.gridApi.redrawRows();
                    }
                }
            }
        });
    }

    // Definición base de columnas (estáticas) con Dropdowns
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
        for (let i = 1; i <= state.demographicColsCount; i++) {
            cols.push({ 
                field: `Demográfico_${i}`, 
                headerName: `Demográfico_${i}`, 
                editable: true,
                cellStyle: { 'backgroundColor': '#f9f9ff' }
            });
            cols.push({ 
                field: `Dato_${i}`, 
                headerName: `Dato_${i}`, 
                editable: true,
                cellStyle: { 'backgroundColor': '#f9f9ff' }
            });
        }
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

        state.gridApi.forEachNode((node, index) => {
             const row = node.data;
             const missing = [];
             MANDATORY_FIELDS.forEach(field => {
                if (!row[field] || row[field].toString().trim() === "") {
                    missing.push(field);
                }
            });

            if (missing.length > 0) {
                hasErrors = true;
                errorCount++;
                if (validationErrors.length < 5) { // Limitar errores visuales a 5
                     validationErrors.push({ row: index + 1, missing: missing });
                }
            }
        });

        // 1. Control del botón Continuar
        ui.btnValidateContinue.disabled = hasErrors;

        // 2. Actualizar resumen visual
        if (hasErrors) {
            let summaryHtml = `
                <div class="alert alert-danger" style="background-color: #fff5f5; border: 1px solid #fc8181; color: #c53030; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                    <strong>Validación incompleta:</strong> Se detectaron campos obligatorios sin completar.<br>
                    <ul>
            `;
            validationErrors.forEach(e => {
                summaryHtml += `<li>Fila ${e.row}: Faltan [${e.missing.join(', ')}]</li>`;
            });
            if (errorCount > 5) {
                summaryHtml += `<li>... y ${errorCount - 5} filas más.</li>`;
            }
            summaryHtml += `</ul></div>`;
            ui.validationSummary.innerHTML = summaryHtml;
        } else {
             ui.validationSummary.innerHTML = `
             <div class="alert alert-success" style="background-color: #f0fff4; border: 1px solid #68d391; color: #276749; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <i class="fa fa-check-circle"></i> Validación exitosa.
             </div>`;
        }
        
        // 3. Refrescar celdas para actualizar estilos
        state.gridApi.refreshCells({ force: true });
    }

	function initAgGrid() {
		ui.gridContainer.innerHTML = '';
		const colDefs = getAllColDefs();

		const gridOptions = {
			rowData: state.rows,
			columnDefs: colDefs,
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
                setTimeout(validateRealTime, 0); // Validar cambios de modelo
            }
		};

		agGrid.createGrid(ui.gridContainer, gridOptions);

		if (state.mode === 'edit') {
			ui.btnAddRow.style.display = 'inline-block';
            ui.btnAddDemo.style.display = 'inline-block';
		} else {
			ui.btnAddRow.style.display = 'inline-block';
            ui.btnAddDemo.style.display = 'inline-block'; 
		}
	}

	// Handlers de Paso 1
	ui.optUpload.addEventListener('click', () => {
		setMode('upload');
		if (ui.fileInput) {
			ui.fileInput.click();
		}
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
			ui.uploadArea.style.display = 'block';
		} else {
			ui.optEdit.classList.add('selected');
			ui.optUpload.classList.remove('selected');
		}
	}

	function fetchExistingContacts() {
		ui.optEdit.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Cargando...';
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
				
				if (r.message) {
					state.rows = r.message.rows || [];
                    state.demographicColsCount = Math.max(1, r.message.max_demographics || 1);
					state.headers = getAllColDefs().map(c => c.field);
					state.errors = [];
					ui.btnContinue.disabled = false;
				} else {
					frappe.msgprint('No se pudieron cargar los contactos.');
				}
			}
		});
	}

	ui.downloadBtn.addEventListener('click', (e) => {
		e.preventDefault();
		window.location = '/api/method/liseniq.www.contacts.contacts_import.download_template';
	});

	// Lógica de Dropzone
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
            if (!state.rows || state.rows.length === 0) {
                 alert("No hay datos cargados. Por favor intente recargar la página.");
                 return;
            }
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
            
            // Detectar columnas de demográficos para configurar el grid
            let maxDemoIndex = 1;
            if (state.headers && state.headers.length > 0) {
                state.headers.forEach(h => {
                    if (h && h.startsWith('Demográfico_')) {
                        const parts = h.split('_');
                        if (parts.length === 2) {
                            const idx = parseInt(parts[1]);
                            if (!isNaN(idx) && idx > maxDemoIndex) {
                                maxDemoIndex = idx;
                            }
                        }
                    }
                });
            }
            state.demographicColsCount = maxDemoIndex;

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

    ui.btnAddDemo.addEventListener('click', () => {
        if (!state.gridApi) return;
        state.demographicColsCount++;
        const newColDefs = getAllColDefs();
        state.gridApi.setGridOption('columnDefs', newColDefs);
    });

	ui.btnBackToStep1.addEventListener('click', () => {
		showStep(1);
	});

    // Acción del botón "Confirmar y Continuar" del Paso 2
	ui.btnValidateContinue.addEventListener('click', () => {
		let gridData = [];
		if (state.gridApi) {
			state.gridApi.forEachNode(node => {
				gridData.push(node.data);
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

    // Acción del botón "Finalizar" del Paso 3
	ui.btnFinish.addEventListener('click', () => {
        ui.btnFinish.disabled = true;
        ui.btnFinish.textContent = 'Iniciando...';
        
        fetch('/api/method/liseniq.www.contacts.contacts_import.upload_contacts_json', {
			method: 'POST',
			headers: { 
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': frappe.csrf_token || window.csrf_token
            },
			body: JSON.stringify({ rows_json: state.dataToProcess })
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