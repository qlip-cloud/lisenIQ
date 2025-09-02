import { Stepper } from './utils/stepper.js';

document.addEventListener('DOMContentLoaded', function () {

    if (!document.getElementById('contacts-list-view')) return;

    const appState = {
        isEditMode: false,
        currentContactName: null,
        demographicTypes: JSON.parse(document.getElementById('demographic-data').textContent),
        debounceTimer: null
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
            manualContact: document.getElementById('btn-manual-contact')
        },
        modal: document.getElementById('create-contact-modal'),
        demographicsTbody: document.getElementById('demographics-tbody'),
        selectAllCheckbox: document.getElementById('select-all-contacts')
    };

    const stepper = new Stepper(ui.stepperContainer, ['Datos Básicos', 'Datos Opcionales', 'Datos Demográficos']);

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
    
    const setupFormForCreate = () => {
        appState.currentContactName = null;
        updateFormUI('create');
        resetCreateForm();
        showView('form');
        showFormStep(1);
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
    
    const updateContactInTable = (contact) => {
        const row = ui.tableBody.querySelector(`tr[data-name="${contact.name}"]`);
        if (row) row.innerHTML = getContactRowHTML(contact);
    };

    const addContactToTable = (contact) => {
        const noContactsRow = ui.tableBody.querySelector('td[colspan="9"]');
        if (noContactsRow) noContactsRow.parentElement.remove();
        
        const newRow = ui.tableBody.insertRow(0);
        newRow.setAttribute('data-name', contact.name);
        newRow.innerHTML = getContactRowHTML(contact);
    };

    const getContactRowHTML = (contact) => {
        const statusHTML = contact.status ? `<span class="status-badge status-${contact.status.toLowerCase()}">${contact.status}</span>` : '';
        return `
            <td class="contact-checkbox-cell"><input type="checkbox" class="contact-checkbox" data-name="${contact.name}"></td>
            <td>${contact.custom_document_number || ''}</td>
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
        `;
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
            demographics: demographics
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
                        updateContactInTable(r.message.updated_contact);
                    } else {
                        addContactToTable(r.message.new_contact);
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
                            rowElement.remove();
                            updateSelectAllCheckboxState();
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
        ui.buttons.manualContact?.addEventListener('click', () => {
            ui.modal.classList.add('d-none');
            setTimeout(setupFormForCreate, 150);
        });
        
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
    }
    
    function init() {
        stepper.render();
        showView('list');
        initializeEventListeners();
        updateSelectAllCheckboxState();
    }

    init();
});
