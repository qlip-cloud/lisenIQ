import { Stepper } from './utils/stepper.js';

document.addEventListener('DOMContentLoaded', function () {
	if (!document.getElementById('contacts-import-app')) return;

	const state = {
		currentStep: 1,
		file: null,
		headers: [],
		rows: [], // array of objects {header: value}
		errors: [], // validation errors per row
		processResult: null
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
		previewContainer: document.getElementById('preview-table-container'),
		btnBackToStep1: document.getElementById('btn-back-to-step1'),
		btnValidateContinue: document.getElementById('btn-validate-continue'),
		processResult: document.getElementById('process-result'),
		btnBackToStep2: document.getElementById('btn-back-to-step2'),
		btnFinish: document.getElementById('btn-finish')
	};

	const stepper = new Stepper(ui.stepperContainer, ['Cargar Plantilla', 'Validar Datos', 'Creación']);
	stepper.render();
	updateStepUI();

	// helpers
	function showStep(n) {
		state.currentStep = n;
		ui.step1.classList.toggle('d-none', n !== 1);
		ui.step2.classList.toggle('d-none', n !== 2);
		ui.step3.classList.toggle('d-none', n !== 3);
		stepper.update(n);
	}

	function resetPreview() {
		ui.previewContainer.innerHTML = '';
		ui.validationSummary.textContent = '';
		ui.btnValidateContinue.disabled = true;
		state.rows = [];
		state.errors = [];
	}

	// Step 1 actions
	ui.downloadBtn.addEventListener('click', (e) => {
		e.preventDefault();
		window.location = '/api/method/liseniq.www.contacts.contacts_import.download_template';
	});

	// dropzone click & drag/drop
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
		if (!state.file) return;
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
			renderPreview();
			showStep(2);
		}).catch(err => {
			ui.btnContinue.disabled = false;
			ui.btnContinue.textContent = 'Continuar';
			alert('Error en la validación: ' + (err.message || err));
		});
	});

	// Step 2 render / editing
	function renderPreview() {
		resetPreview();
		const rows = state.rows || [];
		if (!rows.length) {
			ui.validationSummary.textContent = 'No se encontraron filas para procesar.';
			return;
		}
		// mostrar errores resumidos
		if (state.errors && state.errors.length) {
			ui.validationSummary.innerHTML = `<strong>Advertencias:</strong> ${state.errors.length} fila(s) con incidencias. Revise antes de continuar.`;
		} else {
			ui.validationSummary.textContent = 'Archivo validado correctamente. Puede corregir valores y continuar.';
		}
		// construir tabla editable
		const table = document.createElement('table');
		table.className = 'table';
		const thead = document.createElement('thead');
		const thr = document.createElement('tr');
		state.headers.forEach(h => {
			const th = document.createElement('th');
			th.textContent = h;
			thr.appendChild(th);
		});
		thead.appendChild(thr);
		table.appendChild(thead);

		const tbody = document.createElement('tbody');
		rows.forEach((r, idx) => {
			const tr = document.createElement('tr');
			state.headers.forEach(h => {
				const td = document.createElement('td');
				td.contentEditable = true;
				td.dataset.col = h;
				td.dataset.row = idx;
				td.textContent = r[h] || '';
				tr.appendChild(td);
			});
			// marcar si fila tiene error
			if (state.errors.find(e => e.fila === idx + 2)) {
				tr.style.backgroundColor = '#fff4e5';
			}
			tbody.appendChild(tr);
		});
		table.appendChild(tbody);
		ui.previewContainer.appendChild(table);

		// habilitar continuar (el usuario podrá corregir)
		ui.btnValidateContinue.disabled = false;

		// escuchar cambios en tabla para actualizar state.rows
		table.addEventListener('input', (e) => {
			const td = e.target.closest('td');
			if (!td) return;
			const r = parseInt(td.dataset.row, 10);
			const c = td.dataset.col;
			state.rows[r][c] = td.textContent.trim();
		});
	}

	ui.btnBackToStep1.addEventListener('click', () => {
		showStep(1);
	});

	ui.btnValidateContinue.addEventListener('click', () => {
		// preparar payload JSON con filas corregidas
		const payload = JSON.stringify(state.rows || []);
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

	// Step 3 render resultado
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
		// finalizar flujo: redirigir a lista de contactos
		window.location.href = '/contacts';
	});

	function updateStepUI() {
		showStep(state.currentStep || 1);
	}
});
