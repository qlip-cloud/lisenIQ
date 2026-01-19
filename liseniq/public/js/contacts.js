import { Stepper } from './utils/stepper.js';

document.addEventListener('DOMContentLoaded', function () {

    // Verificación inicial
    if (!document.getElementById('contacts-list-view')) return;

    let uploadCheckInterval = null;

    const appState = {
        isEditMode: false,
        currentContactName: null,
        demographicTypes: JSON.parse(document.getElementById('demographic-data').textContent),
        debounceTimer: null,

        contacts: (() => {
            try {
                const raw = document.getElementById('contacts-data')?.textContent || '[]';
                const list = JSON.parse(raw) || [];
                return list.map(normalizeContact);
            } catch {
                return [];
            }
        })(),
        filteredContacts: [],
        totalRegistered: 0,
        filters: { dni: '', name: '', email: '' },
        pagination: {
            pageSize: 10,
            currentPage: 1
        }
    };

    const ui = {
        listView: document.getElementById('contacts-list-view'),
        createView: document.getElementById('contacts-create-view'),
        tableBody: document.querySelector('.contacts-table tbody'),
        stepperContainer: 'contact-stepper-container',
        mainTitle: document.querySelectorAll('.page-main-title'),
        modeText: document.querySelectorAll('.form-mode-text'),
        forms: {
            step1: document.getElementById('step-1-form'),
            step2: document.getElementById('step-2-form'),
            step3: document.getElementById('step-3-form')
        },
        buttons: {
            newContact: document.getElementById('btn-new-contact'),
            nextStep1: document.getElementById('btn-next-step-1'),
            backStep2: document.getElementById('btn-back-step-2'),
            nextStep2: document.getElementById('btn-next-step-2'),
            backStep3: document.getElementById('btn-back-step-3'),
            save: document.getElementById('btn-save-contact'),
            addDemographic: document.getElementById('btn-add-demographic'),
            closeModal: document.getElementById('btn-close-modal'),
            manualContact: document.getElementById('btn-manual-contact'),
            prevPage: document.getElementById('contacts-prev-page'),
            nextPage: document.getElementById('contacts-next-page')
        },
        modal: document.getElementById('create-contact-modal'),
        demographicsTbody: document.getElementById('demographics-tbody'),
        selectAllCheckbox: document.getElementById('select-all-contacts'),
        pageInfo: document.getElementById('contacts-page-info'),
        summary: document.getElementById('contacts-summary'),
        filters: {
            dni: document.getElementById('filter-dni'),
            name: document.getElementById('filter-name'),
            email: document.getElementById('filter-email')
        }
    };

    const stepper = new Stepper(ui.stepperContainer, ['Datos Básicos', 'Datos Opcionales', 'Datos Demográficos']);

    // Monitor de estado de carga masiva
    function monitorUploadStatus() {
        // Solo ejecutar si estamos en la vista de lista
        if (ui.listView.classList.contains('d-none')) return;

        frappe.call({
            method: 'liseniq.www.contacts.contacts_import.check_upload_status',
            callback: function(r) {
                const notificationBar = document.getElementById('global-notification-bar');
                
                if (r.message) {
                    const { active, status, processed, total, success, error } = r.message;
                    
                    if (active) {
                        // Calcular porcentaje (0 a 100)
                        const percent = total > 0 ? (processed / total) * 100 : 0;

                    // Bloquear botón de creación
                        if (ui.buttons.newContact) {
                            ui.buttons.newContact.disabled = true;
                            ui.buttons.newContact.title = "Carga masiva en proceso";
                            ui.buttons.newContact.style.opacity = '0.6';
                        ui.buttons.newContact.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Procesando...';
                        }

                    // Actualizar barra de progreso visual (Variable CSS)
                        if (notificationBar) {
                            notificationBar.style.setProperty('--progress', `${percent}%`);
                        }

                    // Mostrar notificación persistente
                    // const msg = `Carga en Proceso (${status})... Registros: ${processed} de ${total}`;
                    const msg = `Carga en Proceso, Registros: ${processed} de ${total}`;
                        showGlobalNotification(msg, 'info', 60000); 

                    } else {
                        // Si finalizó y el botón estaba bloqueado, restaurar y mostrar resumen
                        if (ui.buttons.newContact && ui.buttons.newContact.disabled) {
                            ui.buttons.newContact.disabled = false;
                            ui.buttons.newContact.title = "";
                            ui.buttons.newContact.style.opacity = '1';
                            ui.buttons.newContact.innerHTML = 'Nuevo Contacto';
                            
                            // Completar la barra al 100% antes de cerrar
                            if (notificationBar) notificationBar.style.setProperty('--progress', '100%');
                            
                            // Mensaje Final con detalle
                            const msg = `Carga finalizada (${status})\n\n✅ Exitosos: ${success}\n❌ Fallidos: ${error}`;
                            
                            // Determinar tipo de notificación (si hubo fallos críticos o mixtos)
                            const notifType = (status === 'Fallido' || (error > 0 && success === 0)) ? 'error' : 'success';
                            
                            showGlobalNotification(msg, notifType, 10000); // 10 segundos para leer el resumen
                            
                            // Recargar la tabla para mostrar los nuevos datos
                            setTimeout(() => location.reload(), 2000);
                        }
                    }
                }
            }
        });
    }

    const showView = (view) => {
        ui.listView.classList.toggle('d-none', view !== 'list');
        ui.createView.classList.toggle('d-none', view !== 'form');
    };

    const showFormStep = (step) => {
        Object.values(ui.forms).forEach(form => form.classList.add('d-none'));
        ui.forms[`step${step}`].classList.remove('d-none');
        stepper.update(step);
    };

    const updateFormUI = (mode) => {
        const isEdit = mode === 'edit';
        const title = isEdit ? 'Editar Contacto' : 'Nuevo Contacto';
        const buttonText = isEdit ? 'Actualizar' : 'Crear';

        appState.isEditMode = isEdit;
        ui.mainTitle.forEach(el => el.textContent = title);
        ui.modeText.forEach(el => el.textContent = title);
        ui.buttons.save.textContent = buttonText;
    };
    
    // Filtro de contactos
    const parseFilterValue = (val) => {
        const v = (val || '').trim();
        if (v.length >= 2 && v.startsWith('"') && v.endsWith('"')) {
            return { term: v.slice(1, -1).trim(), exact: true };
        }
        return { term: v, exact: false };
    };

    const matchText = (haystack, needle, exact) => {
        const h = (haystack || '').toLowerCase();
        const n = (needle || '').toLowerCase();
        if (!n) return true;
        return exact ? h === n : h.includes(n);
    };

    const applyFilters = () => {
        const dniFilter = parseFilterValue(appState.filters.dni);
        const nameFilter = parseFilterValue(appState.filters.name);
        const emailFilter = parseFilterValue(appState.filters.email);

        appState.filteredContacts = appState.contacts.filter(c => {
            const dniOk = matchText(c.docNumber, dniFilter.term, dniFilter.exact);
            const fullName = `${c.firstName || ''} ${c.lastName || ''}`.trim();
            let nameOk = true;
            if (nameFilter.term) {
                if (nameFilter.exact) {
                    nameOk = matchText(fullName, nameFilter.term, true)
                        || matchText(c.firstName, nameFilter.term, true)
                        || matchText(c.lastName, nameFilter.term, true);
                } else {
                    nameOk = matchText(fullName, nameFilter.term, false)
                        || matchText(c.firstName, nameFilter.term, false)
                        || matchText(c.lastName, nameFilter.term, false);
                }
            }
            const emailOk = matchText(c.email, emailFilter.term, emailFilter.exact);

            return dniOk && nameOk && emailOk;
        });

        appState.pagination.currentPage = 1;
    };

    const updateSummary = (visibleCount) => {
        const total = appState.totalRegistered;
        ui.summary.textContent = `Mostrando ${visibleCount} de ${total} contactos`;
    };

    const stepperRenderAndInitState = () => {
        appState.totalRegistered = appState.contacts.length;
        appState.filteredContacts = [...appState.contacts];
        updateSummary(0);
    };

    const showFormForCreate = () => {
        appState.currentContactName = null;
        updateFormUI('create');
        resetCreateForm();
        showView('form');
        showFormStep(1);
    };

    const setupFormForCreate = () => {
        showFormForCreate();
    };

    const setupFormForEdit = (contactData) => {
        appState.currentContactName = contactData.name;
        updateFormUI('edit');
        resetCreateForm();
        populateForm(contactData);
        showView('form');
        showFormStep(1);
    };

    const resetCreateForm = () => {
        const form = ui.createView.querySelector('form');
        if (form) form.reset();
        clearAllValidations();
        ui.demographicsTbody.innerHTML = '';
        addDemographicRow();
        const countrySelect = document.getElementById('contact-country');
        if (countrySelect) countrySelect.value = countrySelect.dataset.defaultCountry || '';
    };

    const populateForm = (data) => {
        const formatDate = (dateStr) => dateStr ? new Date(dateStr).toISOString().split('T')[0] : '';

        document.getElementById('contact-firstname').value = data.firstName || '';
        document.getElementById('contact-lastname').value = data.lastName || '';
        document.getElementById('contact-doc-type').value = data.docType || '';
        document.getElementById('contact-doc-number').value = data.docNumber || '';
        document.getElementById('contact-country').value = data.country || '';
        document.getElementById('contact-language').value = data.language || '';
        document.getElementById('contact-email').value = data.email || '';
        document.getElementById('contact-gender').value = data.gender || '';
        document.getElementById('contact-birthdate').value = formatDate(data.birthdate);
        document.getElementById('contact-education').value = data.education || '';
        document.getElementById('contact-entrydate').value = formatDate(data.entryDate);

        ui.demographicsTbody.innerHTML = '';
        if (data.demographics && data.demographics.length > 0) {
            data.demographics.forEach(demo => addDemographicRow(demo.type, demo.value));
        } else {
            addDemographicRow();
        }
    };

    const addDemographicRow = (type = '', value = '') => {
        const newRow = ui.demographicsTbody.insertRow();
        newRow.innerHTML = `
            <td style="position: relative;">
                <input type="text" class="form-control demographic-type-input" placeholder="Seleccionar o crear..." autocomplete="off" value="${type}">
                <div class="autocomplete-results"></div>
            </td>
            <td><input type="text" class="form-control" placeholder="Añadir valor..." value="${value}"></td>
            <td class="action-cell"><i class="fa fa-trash-o delete-row" title="Eliminar fila"></i></td>
        `;
    };

    function normalizeContact(c) {
        return {
            name: c.name,
            docNumber: c.dni || c.docNumber || c.custom_document_number || '',
            firstName: c.first_name || c.firstName || '',
            lastName: c.last_name || c.lastName || '',
            country: c.country || c.custom_country || '',
            email: c.email || '',
            language: c.language || c.custom_language || '',
            status: c.status || c.custom_status || ''
        };
    }
    
    function getTotalPages() {
        const size = appState.pagination.pageSize;
        return Math.max(1, Math.ceil((appState.filteredContacts.length || 0) / size) || 1);
    }

    function renderContactsTable() {
        const size = appState.pagination.pageSize;
        const totalPages = getTotalPages();
        if (appState.pagination.currentPage > totalPages) {
            appState.pagination.currentPage = totalPages;
        }
        const start = (appState.pagination.currentPage - 1) * size;
        const slice = appState.filteredContacts.slice(start, start + size);

        if (slice.length === 0) {
            ui.tableBody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center p-5">No se encontraron contactos.</td>
                </tr>
            `;
        } else {
            ui.tableBody.innerHTML = slice.map(getContactRowHTML).join('');
        }

        updatePaginationControls();
        updateSelectAllCheckboxState();
        updateSummary(slice.length);
    }

    function updatePaginationControls() {
        const totalPages = getTotalPages();
        ui.pageInfo.textContent = `Página ${appState.pagination.currentPage} de ${totalPages}`;
        if (ui.buttons.prevPage) ui.buttons.prevPage.disabled = appState.pagination.currentPage <= 1;
        if (ui.buttons.nextPage) ui.buttons.nextPage.disabled = appState.pagination.currentPage >= totalPages;
    }

    function goToPage(page) {
        const total = getTotalPages();
        appState.pagination.currentPage = Math.min(Math.max(1, page), total);
        renderContactsTable();
    }

    const getContactRowHTML = (contact) => {
        const statusHTML = contact.status ? `<span class="status-badge status-${contact.status.toLowerCase()}">${contact.status}</span>` : '';
        return `
            <tr data-name="${contact.name}">
                <td class="contact-checkbox-cell"><input type="checkbox" class="contact-checkbox" data-name="${contact.name}"></td>
                <td>${contact.docNumber || ''}</td>
                <td>${contact.firstName || ''}</td>
                <td>${contact.lastName || ''}</td>
                <td>${contact.country || ''}</td>
                <td>${contact.email || ''}</td>
                <td>${contact.language || ''}</td>
                <td>${statusHTML}</td>
                <td class="contact-actions">
                    <i class="fa fa-pencil-square-o edit-contact-btn" title="Editar Contacto"></i>
                    <i class="fa fa-trash-o delete-contact-btn" title="Eliminar Contacto"></i>
                </td>
            </tr>
        `;
    };

    const updateContactInList = (contact) => {
        const normalized = normalizeContact(contact);
        const idx = appState.contacts.findIndex(c => c.name === normalized.name);
        if (idx !== -1) {
            appState.contacts[idx] = normalized;
        }
        appState.totalRegistered = appState.contacts.length;
        applyFilters();
        renderContactsTable();
    };

    const addContactToList = (contact) => {
        const normalized = normalizeContact(contact);
        appState.contacts.unshift(normalized);
        appState.totalRegistered = appState.contacts.length;
        applyFilters();
        appState.pagination.currentPage = 1;
        renderContactsTable();
    };

    const removeContactFromList = (contactName) => {
        appState.contacts = appState.contacts.filter(c => c.name !== contactName);
        appState.totalRegistered = appState.contacts.length;
        applyFilters();
        renderContactsTable();
    };

    const getContactFormData = () => {
        const demographics = [];
        ui.demographicsTbody.querySelectorAll('tr').forEach(row => {
            const typeInput = row.querySelector('.demographic-type-input');
            const valueInput = row.querySelector('input[type="text"]:not(.demographic-type-input)');
            
            if (typeInput && valueInput && typeInput.value.trim() && valueInput.value.trim()) {
                demographics.push({ type: typeInput.value.trim(), value: valueInput.value.trim() });
            }
        });

        return {
            firstName: document.getElementById('contact-firstname').value.trim(),
            lastName: document.getElementById('contact-lastname').value.trim(),
            docType: document.getElementById('contact-doc-type').value,
            docNumber: document.getElementById('contact-doc-number').value.trim(),
            email: document.getElementById('contact-email').value.trim(),
            country: document.getElementById('contact-country').value,
            language: document.getElementById('contact-language').value,
            gender: document.getElementById('contact-gender').value,
            birthdate: document.getElementById('contact-birthdate').value,
            education: document.getElementById('contact-education').value,
            entryDate: document.getElementById('contact-entrydate').value,
            demographics: demographics,
            custom_is_liseniq_contact: true
        };
    };

    const updateSelectAllCheckboxState = () => {
        const allCheckboxes = ui.tableBody.querySelectorAll('.contact-checkbox');
        const checkedCount = Array.from(allCheckboxes).filter(cb => cb.checked).length;
        
        if (allCheckboxes.length > 0) {
            ui.selectAllCheckbox.checked = checkedCount === allCheckboxes.length;
            ui.selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < allCheckboxes.length;
        } else {
            ui.selectAllCheckbox.checked = false;
            ui.selectAllCheckbox.indeterminate = false;
        }
    };

    const showValidationError = (fieldId, message) => {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${field.id}-error`);
        field.classList.add('is-invalid');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
    };

    const clearValidationError = (fieldId) => {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${field.id}-error`);
        field.classList.remove('is-invalid');
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    };

    const clearAllValidations = () => {
        ui.forms.step1.querySelectorAll('[data-required="true"]').forEach(field => {
            clearValidationError(field.id);
        });
        clearValidationError('contact-email');
    };

    const validateStep1 = () => {
        let isValid = true;
        clearAllValidations();

        const requiredFields = ui.forms.step1.querySelectorAll('[data-required="true"]');
        const nameRegex = /^[a-zA-Z\sñÑáéíóúÁÉÍÓÚüÜ]+$/;
        
        requiredFields.forEach(field => {
            const value = field.value.trim();
            if (!value) {
                isValid = false;
                showValidationError(field.id, 'Este campo es obligatorio.');
            } else {
                if (field.id === 'contact-firstname' || field.id === 'contact-lastname') {
                    if (!nameRegex.test(value)) {
                        isValid = false;
                        showValidationError(field.id, 'Este campo solo debe contener letras y espacios.');
                    }
                }
            }
        });

        return isValid;
    };

    const validateStep2 = () => {
        let isValid = true;
        clearValidationError('contact-email');
        const emailField = document.getElementById('contact-email');
        const emailValue = emailField.value.trim();
        
        if (emailValue) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(emailValue)) {
                isValid = false;
                showValidationError('contact-email', 'Por favor, introduce un formato de correo electrónico válido.');
            }
        }
        return isValid;
    };

    const handleSave = () => {
        const contactData = getContactFormData();
        const method = appState.isEditMode ? 'update_contact' : 'create_contact';
        const args = appState.isEditMode ? { contact_name: appState.currentContactName, contact_data: JSON.stringify(contactData) } : { contact_data: JSON.stringify(contactData) };

        frappe.call({
            method: `liseniq.www.contacts.index.${method}`,
            args: args,
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    if (appState.isEditMode) {
                        updateContactInList(r.message.updated_contact);
                    } else {
                        addContactToList(r.message.new_contact);
                    }
                    showView('list');
                    showGlobalNotification(`Contacto ${appState.isEditMode ? 'actualizado' : 'creado'} correctamente.`, 'success');
                } else {
                    showGlobalNotification(`Error: ${r.message.message || 'Ocurrió un error inesperado.'}`, 'error');
                }
            },
            error: (r) => {
                console.error(`Error al ${appState.isEditMode ? 'actualizar' : 'crear'} el contacto:`, r);
                showGlobalNotification('Ocurrió un error inesperado en el servidor.', 'error');
            }
        });
    };

    const handleDelete = (contactName, rowElement) => {
        frappe.confirm(
            '¿Estás seguro de que quieres eliminar este contacto?',
            () => { 
                frappe.call({
                    method: 'liseniq.www.contacts.index.delete_contact',
                    args: { contact_name: contactName },
                    callback: (r) => {
                        if (r.message && r.message.status === 'success') {
                            removeContactFromList(contactName);
                            showGlobalNotification('Contacto eliminado correctamente.', 'success');
                        } else {
                            showGlobalNotification(`Error al eliminar: ${r.message.message || 'Ocurrió un error inesperado.'}`, 'error');
                        }
                    },
                    error: (r) => {
                        console.error('Error al eliminar el contacto:', r);
                        showGlobalNotification('Ocurrió un error inesperado en el servidor al eliminar.', 'error');
                    }
                });
            }
        );
    };

    const handleEdit = (contactName) => {
        frappe.call({
            method: 'liseniq.www.contacts.index.get_contact_details',
            args: { contact_name: contactName },
            callback: (r) => {
                if (r.message) {
                    setupFormForEdit(r.message);
                }
            }
        });
    };

    const fetchDemographicSuggestions = (searchTerm, resultsContainer) => {
        frappe.call({
            method: 'liseniq.www.contacts.index.get_demographic_suggestions',
            args: { search_term: searchTerm },
            callback: (r) => {
                resultsContainer.innerHTML = '';
                if (r.message && r.message.length > 0) {
                    r.message.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'autocomplete-item';
                        div.textContent = item.dt_title;
                        resultsContainer.appendChild(div);
                    });
                    resultsContainer.style.display = 'block';
                } else {
                    resultsContainer.style.display = 'none';
                }
            }
        });
    };

    function initializeEventListeners() {
        ui.buttons.newContact?.addEventListener('click', () => { ui.modal.classList.remove('d-none'); });
        ui.buttons.closeModal?.addEventListener('click', () => { ui.modal.classList.add('d-none'); });
        ui.modal?.addEventListener('click', (e) => { if (e.target === ui.modal) ui.modal.classList.add('d-none'); });

        // Redireccionar a flujo de carga masiva cuando el usuario selecciona Carga masiva
        const templateBtn = document.getElementById('btn-template-contact');
        if (templateBtn) {
            templateBtn.addEventListener('click', () => {
                // cerrar modal actual y redirigir a la vista de importación
                ui.modal.classList.add('d-none');
                window.location.href = '/contacts/contacts_import';
            });
        }

        ui.buttons.manualContact?.addEventListener('click', () => {
            ui.modal.classList.add('d-none');
            setTimeout(setupFormForCreate, 150);
        });

        const onFilterChange = () => {
            appState.filters = {
                dni: ui.filters.dni.value,
                name: ui.filters.name.value,
                email: ui.filters.email.value
            };
            applyFilters();
            renderContactsTable();
        };
        ui.filters.dni?.addEventListener('input', onFilterChange);
        ui.filters.name?.addEventListener('input', onFilterChange);
        ui.filters.email?.addEventListener('input', onFilterChange);

        ui.buttons.save?.addEventListener('click', handleSave);
        ui.buttons.addDemographic?.addEventListener('click', () => addDemographicRow());
        
        ui.tableBody?.addEventListener('click', (e) => {
            const target = e.target;
            const row = target.closest('tr');
            if (!row) return;
            const contactName = row.dataset.name;

            if (target.classList.contains('edit-contact-btn')) handleEdit(contactName);
            else if (target.classList.contains('delete-contact-btn')) handleDelete(contactName, row);
            else if (target.classList.contains('contact-checkbox')) updateSelectAllCheckboxState();
        });

        ui.demographicsTbody.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-row')) {
                if (ui.demographicsTbody.rows.length > 1) {
                    e.target.closest('tr').remove();
                } else {
                    showGlobalNotification('Debe haber al menos un dato demográfico.', 'error');
                }
            }
        });

        ui.demographicsTbody.addEventListener('input', (e) => {
            if (e.target.classList.contains('demographic-type-input')) {
                const input = e.target;
                const resultsContainer = input.nextElementSibling;
                const searchTerm = input.value.trim();

                clearTimeout(appState.debounceTimer);
                appState.debounceTimer = setTimeout(() => {
                    if (searchTerm.length > 1) {
                        fetchDemographicSuggestions(searchTerm, resultsContainer);
                    } else {
                        resultsContainer.style.display = 'none';
                    }
                }, 300);
            }
        });

        ui.demographicsTbody.addEventListener('click', (e) => {
            if (e.target.classList.contains('autocomplete-item')) {
                const input = e.target.parentElement.previousElementSibling;
                input.value = e.target.textContent;
                e.target.parentElement.style.display = 'none';
            }
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.demographic-type-input')) {
                document.querySelectorAll('.autocomplete-results').forEach(el => el.style.display = 'none');
            }
        });

        ui.selectAllCheckbox?.addEventListener('change', (e) => {
            ui.tableBody.querySelectorAll('.contact-checkbox').forEach(cb => {
                cb.checked = e.target.checked;
            });
            updateSelectAllCheckboxState();
        });

        ui.buttons.nextStep1?.addEventListener('click', () => {
            if (validateStep1()) {
                showFormStep(2);
            }
        });
        
        ui.buttons.nextStep2?.addEventListener('click', () => {
            if (validateStep2()) {
                showFormStep(3);
            }
        });
        ui.buttons.backStep2?.addEventListener('click', () => showFormStep(1));
        ui.buttons.backStep3?.addEventListener('click', () => showFormStep(2));

        ui.forms.step1.querySelectorAll('[data-required="true"]').forEach(field => {
            field.addEventListener('input', () => clearValidationError(field.id));
        });

        document.getElementById('contact-email').addEventListener('input', () => clearValidationError('contact-email'));

        const sanitizeNameInput = (e) => {
            e.target.value = e.target.value.replace(/[^a-zA-Z\sñÑáéíóúÁÉÍÓÚüÜ]/g, '');
        };

        document.getElementById('contact-firstname').addEventListener('input', sanitizeNameInput);
        document.getElementById('contact-lastname').addEventListener('input', sanitizeNameInput);

        ui.buttons.prevPage?.addEventListener('click', () => goToPage(appState.pagination.currentPage - 1));
        ui.buttons.nextPage?.addEventListener('click', () => goToPage(appState.pagination.currentPage + 1));
    }
    
    function init() {
        stepper.render();
        stepperRenderAndInitState();
        applyFilters();
        showView('list');
        initializeEventListeners();
        renderContactsTable();
        
        // Iniciar monitor de carga
        monitorUploadStatus();
        if (uploadCheckInterval) clearInterval(uploadCheckInterval);
        uploadCheckInterval = setInterval(monitorUploadStatus, 5000);
    }

    init();
});