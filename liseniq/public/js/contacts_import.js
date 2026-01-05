import { Stepper } from './utils/stepper.js';

document.addEventListener('DOMContentLoaded', function () {
	if (!document.getElementById('contacts-import-app')) return;

	const state = {
		currentStep: 1,
		file: null,
		headers: [],
		rows: [], // array of objects
		errors: [], // validation errors per row
		processResult: null,
		mode: 'upload', // 'upload' or 'edit'
		gridApi: null, // referencia al API de Ag-Grid
        demographicColsCount: 1 // Inicialmente 1 par de columnas de demográfico
	};

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

    // Definición base de columnas (estáticas)
    const getBaseColDefs = () => [
		{ 
            field: "Nombre", 
            headerName: "Nombre", 
            editable: true, 
            minWidth: 150, 
            pinned: 'left',
            wrapText: true,
            autoHeight: true,
			filter: true
        },
		{ 
            field: "Apellido", 
            headerName: "Apellido", 
            editable: true, 
            minWidth: 150, 
            pinned: 'left',
            wrapText: true,
            autoHeight: true,
			filter: true
        },
		{ 
			field: "Género", 
			headerName: "Género", 
			editable: true, 
			cellEditor: 'agSelectCellEditor', 
			cellEditorParams: { values: ['Masculino', 'Femenino', 'Otro', ''] } 
		},
		{ field: "Fecha de Nacimiento", headerName: "Fecha Nacimiento (YYYY-MM-DD)", editable: true, wrapText: true, autoHeight: true, filter: true },
		{ field: "País Lenguaje", headerName: "País/Lenguaje", editable: true },
		{ 
			field: "Tipo de Documento", 
			headerName: "Tipo Doc", 
			editable: true,
			cellEditor: 'agSelectCellEditor', 
			cellEditorParams: { values: ['CC', 'CE', 'TI', 'PAS', 'NIT', ''] }
		},
		{ field: "Número de Documento (DNI)", headerName: "Número Doc", editable: true, minWidth: 140, wrapText: true, autoHeight: true, filter: true },
		{ field: "Nivel Académico", headerName: "Nivel Académico", editable: true },
		{ field: "Correo Electrónico", headerName: "Correo", editable: true, minWidth: 200, wrapText: true, autoHeight: true },
		{ field: "Fecha de Ingreso", headerName: "Fecha Ingreso (YYYY-MM-DD)", editable: true },
		{ 
			field: "Estatus", 
			headerName: "Estatus", 
			editable: true,
			cellEditor: 'agSelectCellEditor', 
			cellEditorParams: { values: ['Activo', 'Inactivo'] }
		}
    ];

    // Función para generar todas las columnas incluyendo las dinámicas de demográficos
    function getAllColDefs() {
        const cols = getBaseColDefs();
        
        // Agregar columnas dinámicas según el contador en el estado con nomenclatura Demográfico_N / Dato_N
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

	function initAgGrid() {
		// Limpiar contenido previo si existe
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
				// params.api.sizeColumnsToFit(); // Desactivado para permitir scroll horizontal si hay muchas columnas
			}
		};

		// Crear la grid
		agGrid.createGrid(ui.gridContainer, gridOptions);

		// Mostrar botones de edición
		if (state.mode === 'edit') {
			ui.btnAddRow.style.display = 'inline-block';
            ui.btnAddDemo.style.display = 'inline-block';
			ui.validationSummary.textContent = "Edite los contactos existentes o agregue nuevos. Deslice a la derecha para ver más demográficos.";
			ui.btnValidateContinue.disabled = false;
		} else {
			ui.btnAddRow.style.display = 'none';
            ui.btnAddDemo.style.display = 'none'; // Opcional: permitir agregar demográficos también en carga masiva si se desea
		}
	}

	// Step 1 Actions
	
	// Toggle Upload vs Edit
	ui.optUpload.addEventListener('click', () => {
		setMode('upload');
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
				// Restaurar texto UI
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
                    // Detectar cuántas columnas de demográficos vienen
                    state.demographicColsCount = Math.max(1, r.message.max_demographics || 1);
					state.headers = getAllColDefs().map(c => c.field);
					state.errors = [];
					showStep(2);
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

	// Dropzone logic
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
		if (state.mode === 'upload' && !state.file) return;
		
		ui.btnContinue.disabled = true;
		ui.btnContinue.textContent = 'Validando...';
		const fd = new FormData();
		fd.append('file', state.file);
		
		fetch('/api/method/liseniq.www.contacts.contacts_import.validate_contacts', {
			method: 'POST',
			body: fd
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
            
            // Normalizar filas del archivo (mapear nombres viejos a nuevos)
            // Si el archivo trae "Nombre de Demográfico", lo movemos a "Demográfico_1"
            if (state.rows.length > 0) {
                state.rows.forEach(row => {
                    if (row["Nombre de Demográfico"] !== undefined) {
                        row["Demográfico_1"] = row["Nombre de Demográfico"];
                        delete row["Nombre de Demográfico"];
                    }
                    if (row["Valor de Demográfico"] !== undefined) {
                        row["Dato_1"] = row["Valor de Demográfico"];
                        delete row["Valor de Demográfico"];
                    }
                });
            }

            // Reiniciar contador de demográficos para archivo nuevo (asumimos 1 por defecto salvo que detectemos más en un futuro)
            state.demographicColsCount = 1; 

			if (state.errors.length > 0) {
				ui.validationSummary.innerHTML = `<strong>Advertencias:</strong> ${state.errors.length} fila(s) con incidencias. Revise en la tabla.`;
			} else {
				ui.validationSummary.textContent = 'Archivo validado. Puede realizar ajustes finales en la tabla.';
			}
			showStep(2);
		}).catch(err => {
			ui.btnContinue.disabled = false;
			ui.btnContinue.textContent = 'Continuar';
			alert('Error en la validación: ' + (err.message || err));
		});
	});

	// Botón Agregar Fila
	ui.btnAddRow.addEventListener('click', () => {
		if (state.gridApi) {
			const newRow = {};
			getAllColDefs().forEach(col => newRow[col.field] = "");
			newRow["Estatus"] = "Activo";
			state.gridApi.applyTransaction({ add: [newRow] });
		}
	});

    // Botón Agregar Demográfico (Nuevas columnas)
    ui.btnAddDemo.addEventListener('click', () => {
        if (!state.gridApi) return;
        
        state.demographicColsCount++;
        const newColDefs = getAllColDefs();
        state.gridApi.setGridOption('columnDefs', newColDefs);
    });

	ui.btnBackToStep1.addEventListener('click', () => {
		showStep(1);
	});

	ui.btnValidateContinue.addEventListener('click', () => {
		// Obtener datos del Grid
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

		const payload = JSON.stringify(gridData);
		ui.btnValidateContinue.disabled = true;
		ui.btnValidateContinue.textContent = 'Procesando...';
		
		fetch('/api/method/liseniq.www.contacts.contacts_import.upload_contacts_json', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ rows_json: payload })
		}).then(r => r.json()).then(res => {
			ui.btnValidateContinue.disabled = false;
			ui.btnValidateContinue.textContent = 'Confirmar y continuar';
			const data = res.message || res;
			state.processResult = data;
			renderProcessResult();
			showStep(3);
		}).catch(err => {
			ui.btnValidateContinue.disabled = false;
			ui.btnValidateContinue.textContent = 'Confirmar y continuar';
			alert('Error al procesar: ' + (err.message || err));
		});
	});

	function renderProcessResult() {
		const r = state.processResult || {};
		let html = `<div style="padding:12px;border:1px solid #eee;background:#fff;">`;
		html += `<strong>Resultados:</strong><br/>Contactos creados: ${r.creados || 0}<br/>Contactos actualizados: ${r.actualizados || 0}<br/>`;
		if (r.errores && r.errores.length) {
			html += `<br/><strong>Errores:</strong><ul>`;
			r.errores.forEach(err => {
				html += `<li>Fila ${err.fila}: ${err.error}</li>`;
			});
			html += `</ul>`;
		}
		html += `</div>`;
		ui.processResult.innerHTML = html;
	}

	ui.btnBackToStep2.addEventListener('click', () => {
		showStep(2);
	});

	ui.btnFinish.addEventListener('click', () => {
		window.location.href = '/contacts';
	});

	function updateStepUI() {
		showStep(state.currentStep || 1);
	}
});