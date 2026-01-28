import { Stepper } from './utils/stepper.js';
import { QuestionBuilder } from './question_builder.js';

class MeasurementCreator {
    constructor() {
        this.ui = {
            stepperContainer: document.getElementById('measurement-stepper-container'),
            steps: {
                step1: document.getElementById('step-1-form'),
                step2: document.getElementById('step-2-form'),
                step3: document.getElementById('step-3-form'),
                step4: document.getElementById('step-4-form'),
                step5: document.getElementById('step-5-form'),
            },
            navButtons: {
                next1: document.getElementById('btn-next-step-1'),
                back2: document.getElementById('btn-back-step-2'),
                next2: document.getElementById('btn-next-step-2'),
                back3: document.getElementById('btn-back-step-3'),
                next3: document.getElementById('btn-next-step-3'),
                back4: document.getElementById('btn-back-step-4'),
                next4: document.getElementById('btn-next-step-4'),
                back5: document.getElementById('btn-back-step-5'),
                next5: document.getElementById('btn-next-step-5'),
            },
            step1Form: {
                name: document.getElementById('measurement-name'),
                startDate: document.getElementById('measurement-start-date'),
                endDate: document.getElementById('measurement-end-date'),
                timezone: document.getElementById('measurement-timezone'),
            },
            contactsStep: {
                surveyTypeSelect: document.getElementById('survey-type-select'),
                responseTypeSelect: document.getElementById('response-type-select'),
                selectedContactsSection: document.getElementById('selected-contacts-section'),
                sendAllContactsCheck: document.getElementById('send-all-contacts-check'),
                filterSectionContainer: document.querySelector('.contacts-filter-section'),
                fieldTypeSelect: document.getElementById('field-type-select'),
                availableCategories: document.getElementById('available-categories'),
                selectedCategories: document.getElementById('selected-categories'),
                arrow: document.querySelector('.categories-arrow'),
                contactCountNumber: document.getElementById('contact-count-number'),
                viewContactsBtn: document.getElementById('view-contacts-btn'),
            },
            personalizationStep: {
                typeButtons: {
                    invitation: document.getElementById('email-type-invitation-btn'),
                    reminder: document.getElementById('email-type-reminder-btn'),
                },
                subject: document.getElementById('email-subject'),
                body: document.getElementById('email-body'),
                useDefaultCheck: document.getElementById('email-use-default-template'),
                customizationFields: document.getElementById('email-customization-fields'),
            },
            reviewStep: {
                measurementName: document.getElementById('review-measurement-name'),
                surveyType: document.getElementById('review-survey-type'),
                responseType: document.getElementById('review-response-type'),
                questionsCount: document.getElementById('review-questions-count'),
                contactCount: document.getElementById('review-contact-count'),
                questionsList: document.getElementById('review-questions-list'),
                viewContactsBtn: document.getElementById('review-view-contacts-btn'),
                sendRemindersCheck: document.getElementById('send-reminders-check'),
                remindersSection: document.getElementById('reminders-section'),
                reminderFrequency: document.getElementById('reminder-frequency'),
                reminderMax: document.getElementById('reminder-max'),
            },
            contactsModal: {
                modal: document.getElementById('view-contacts-modal'),
                closeBtn: document.getElementById('btn-close-contacts-modal'),
                tableHead: document.querySelector('#view-contacts-modal thead'),
                tableBody: document.getElementById('selected-contacts-table-body'),
            },
            breadcrumbs: document.querySelectorAll('.measurement-name-breadcrumb'),
        };

        this.state = {
            currentStep: 1,
            isEditMode: false,
            docName: null,
            contactCountDebounceTimer: null,
            currentEmailType: 'invitation',
            measurementData: {
                name: '',
                startDate: '',
                endDate: '',
                timezone: 'America/Bogota',
                questions: [],
                contacts: {
                    surveyType: 'all',
                    responseType: 'anonymous',
                    sendToAll: false,
                    filters: [],
                    list: [],
                    headers: []
                },
                emailCustomization: {
                    invitation_subject: '',
                    invitation_body: '',
                    reminder_subject: '',
                    reminder_body: ''
                }
            },
            wasUsingDefault: false
        };
        
        if (this.ui.stepperContainer) {
            this.stepper = new Stepper('measurement-stepper-container', ['Nombre', 'Preguntas', 'Participantes', 'Personalización', 'Revisión']);
            this.questionBuilder = new QuestionBuilder((questions) => {
                this.state.measurementData.questions = questions;
                this.ui.navButtons.next2.disabled = questions.length === 0;
            });
            this.initializeEventListeners();
            this.initializeDefaults();
            this.loadPreloadedQuestions();
            this.loadMeasurementForEdit();
            this.stepper.render();
            this.showStep(1);
            if (!this.state.isEditMode) {
                this.updateContactCount();
            }
        }
    }

    initializeDefaults() {
        this.initWysiwygEditor();
        this.setEmailType('invitation');
    }

    loadPreloadedQuestions() {
        const dataEl = document.getElementById('preloaded-questions-data');
        if (!dataEl) return;

        const questionsJson = dataEl.dataset.questions;
        if (questionsJson && questionsJson !== '[]') {
            try {
                const preloadedQuestions = JSON.parse(questionsJson);
                if (Array.isArray(preloadedQuestions)) {
                    this.questionBuilder.setQuestions(preloadedQuestions);
                }
            } catch (e) {
                console.error("Error al parsear las preguntas precargadas:", e);
            }
        }
    }

    loadMeasurementForEdit() {
        const dataEl = document.getElementById('measurement-data');
        if (!dataEl || !dataEl.dataset.measurement || dataEl.dataset.measurement === 'null') return;

        try {
            const data = JSON.parse(dataEl.dataset.measurement);
            const urlParams = new URLSearchParams(window.location.search);
            this.state.isEditMode = true;
            this.state.docName = urlParams.get('name');

            this.ui.step1Form.name.value = data.name || '';
            if (data.startDate) this.ui.step1Form.startDate.value = String(data.startDate).slice(0, 16);
            if (data.endDate) this.ui.step1Form.endDate.value = String(data.endDate).slice(0, 16);
            if (data.timezone) this.ui.step1Form.timezone.value = data.timezone;

            this.state.measurementData.name = data.name || '';
            this.state.measurementData.startDate = this.ui.step1Form.startDate.value;
            this.state.measurementData.endDate = this.ui.step1Form.endDate.value;
            this.state.measurementData.timezone = this.ui.step1Form.timezone.value;
            this.updateBreadcrumbs();

            // Preguntas (visualización)
            if (data.questions) {
                this.questionBuilder.setQuestions(data.questions);
            }
            if (this.questionBuilder.setEditMode) {
                this.questionBuilder.setEditMode(true);
            } else if (this.questionBuilder.setReadOnly) {
                this.questionBuilder.setReadOnly(true);
            }

            // Participantes
            if (data.contacts) {
                const { surveyTypeSelect, responseTypeSelect, selectedContactsSection, contactCountNumber /*, viewContactsBtn*/ } = this.ui.contactsStep;
                if (surveyTypeSelect) surveyTypeSelect.value = data.contacts.surveyType || 'all';
                if (responseTypeSelect) responseTypeSelect.value = data.contacts.responseType || 'anonymous';
                
                if (surveyTypeSelect && surveyTypeSelect.value === 'selected') {
                    selectedContactsSection?.classList.remove('d-none');
                }

                this.state.measurementData.contacts.headers = Array.isArray(data.contacts.headers) && data.contacts.headers.length > 0
                    ? data.contacts.headers
                    : ['Nombre'];
                this.state.measurementData.contacts.list = Array.isArray(data.contacts.list)
                    ? data.contacts.list
                    : [];

                if (contactCountNumber) {
                    const safeCount = this.state.measurementData.contacts.list.length;
                    contactCountNumber.textContent = String(safeCount);
                }
                // viewContactsBtn?.classList.add('d-none'); 
            }

            // Recordatorios
            if (data.reminders && data.reminders.send) {
                this.ui.reviewStep.sendRemindersCheck.checked = true;
                this.ui.reviewStep.remindersSection.classList.remove('d-none');
                if (data.reminders.frequency) this.ui.reviewStep.reminderFrequency.value = data.reminders.frequency;
                if (data.reminders.max) this.ui.reviewStep.reminderMax.value = data.reminders.max;
            } else {
                this.ui.reviewStep.sendRemindersCheck.checked = false;
                this.ui.reviewStep.remindersSection.classList.add('d-none');
            }

            // Personalización de correo (asunto/cuerpo)
            if (data.su_invitation_subject || data.su_invitation_body || data.su_reminder_subject || data.su_reminder_body) {
                this.state.measurementData.emailCustomization = {
                    invitation_subject: data.su_invitation_subject || '',
                    invitation_body: data.su_invitation_body || '',
                    reminder_subject: data.su_reminder_subject || '',
                    reminder_body: data.su_reminder_body || ''
                };
                const useDefault = !!data.su_default_notif && String(data.su_default_notif) !== '0';
                this.ui.personalizationStep.useDefaultCheck.checked = useDefault;
                this.state.wasUsingDefault = useDefault;
                this.applyEmailCustomizationToggle();
                this.setEmailType('invitation');
                this.initWysiwygEditor(true, () => {
                    this.syncEmailFieldsFromState();
                });
            }

            // Bloquear campos no editables
            this.disableNonEditableFields();

            // Cambiar texto del botón final
            if (this.ui.navButtons.next5) this.ui.navButtons.next5.textContent = 'Guardar Cambios';
        } catch (e) {
            console.error("Error al cargar datos de la medición para editar:", e);
            showGlobalNotification("No se pudieron cargar los datos de la medición.", "error");
        }
    }

    disableNonEditableFields() {
        const step2 = this.ui.steps.step2;
        if (step2) {
            step2.querySelectorAll('input, textarea, select, button').forEach(el => {
                if (!['btn-back-step-2', 'btn-next-step-2'].includes(el.id)) {
                    el.disabled = true;
                }
            });
        }

        const { surveyTypeSelect, responseTypeSelect, sendAllContactsCheck, fieldTypeSelect, availableCategories, selectedCategories } = this.ui.contactsStep;
        [surveyTypeSelect, responseTypeSelect, /* sendAllContactsCheck, */ /* fieldTypeSelect */].forEach(el => el && (el.disabled = true));

        /*
        [availableCategories, selectedCategories].forEach(box => {
            if (box) box.style.pointerEvents = 'none';
        });
        */
    }

    showStep(stepNumber) {
        this.state.currentStep = stepNumber;
        Object.values(this.ui.steps).forEach(stepEl => stepEl.classList.add('d-none'));
        if (this.ui.steps[`step${stepNumber}`]) {
            this.ui.steps[`step${stepNumber}`].classList.remove('d-none');
        }
        this.stepper.update(stepNumber);

        if (stepNumber === 2) {
            this.ui.navButtons.next2.disabled = this.state.measurementData.questions.length === 0;
        }
        if (stepNumber === 3 && this.state.isEditMode) {
            const { surveyTypeSelect, selectedContactsSection } = this.ui.contactsStep;
            if (surveyTypeSelect && surveyTypeSelect.value === 'selected') {
                selectedContactsSection?.classList.remove('d-none');
            }
        }
        if (stepNumber === 4) {
            this.initWysiwygEditor(true, () => {
                if (this.state.isEditMode) this.setEmailType('invitation');
                this.syncEmailFieldsFromState();
                this.applyEmailCustomizationToggle();
                this.updateStep4NextButton();
            });
        }
    }

    initializeEventListeners() {
        const { navButtons, contactsStep, step1Form, contactsModal, reviewStep, personalizationStep } = this.ui;

        navButtons.next1?.addEventListener('click', async () => {
            if (await this.validateStep1()) {
                this.state.measurementData.name = step1Form.name.value.trim();
                this.updateBreadcrumbs();
                this.showStep(2);
            }
        });
        navButtons.back2?.addEventListener('click', () => this.showStep(1));
        navButtons.next2?.addEventListener('click', () => this.showStep(3));
        navButtons.back3?.addEventListener('click', () => this.showStep(2));
        navButtons.next3?.addEventListener('click', () => {
            if (this.validateStep3()) {
                this.showStep(4);
            }
        });
        navButtons.back4?.addEventListener('click', () => this.showStep(3));
        navButtons.next4?.addEventListener('click', () => {
            // Guarda cambios de personalización y pasa a revisión
            this.syncEmailStateFromFields();
            if (!this.validateEmailCustomization()) return; // Validar antes de continuar
            this.renderReviewStep();
            this.showStep(5);
        });
        navButtons.back5?.addEventListener('click', () => this.showStep(4));
        navButtons.next5?.addEventListener('click', () => this.saveMeasurement());

        // Personalización
        personalizationStep.typeButtons.invitation?.addEventListener('click', () => {
            this.setEmailType('invitation');
            this.syncEmailFieldsFromState();
            this.updateStep4NextButton();
        });
        personalizationStep.typeButtons.reminder?.addEventListener('click', () => {
            this.setEmailType('reminder');
            this.syncEmailFieldsFromState();
            this.updateStep4NextButton();
        });
        personalizationStep.subject?.addEventListener('input', () => {
            this.syncEmailStateFromFields();
            this.updateStep4NextButton();
        });
        personalizationStep.body?.addEventListener('input', () => {
            this.syncEmailStateFromFields();
            this.updateStep4NextButton();
        });

        personalizationStep.useDefaultCheck?.addEventListener('change', () => {
            const wasDefault = this.state.wasUsingDefault;
            const nowDefault = personalizationStep.useDefaultCheck.checked;
            this.applyEmailCustomizationToggle();
            if (wasDefault && !nowDefault) {
                this.setEmailType('invitation');
                this.syncEmailFieldsFromState();
            }
            this.state.wasUsingDefault = nowDefault;
            this.updateStep4NextButton();
        });

        // Listeners que deben funcionar en ambos modos (creación y edición)
        contactsStep.sendAllContactsCheck?.addEventListener('change', () => this.handleSendAllCheckChange());
        contactsStep.fieldTypeSelect?.addEventListener('change', () => this.handleFieldTypeChange());

        const triggerUpdate = () => {
            clearTimeout(this.state.contactCountDebounceTimer);
            this.state.contactCountDebounceTimer = setTimeout(() => this.updateContactCount(), 400);
        };

        contactsStep.availableCategories?.addEventListener('click', (e) => {
            this.moveCategoryItem(e.target, contactsStep.availableCategories, contactsStep.selectedCategories);
            triggerUpdate();
        });
        contactsStep.selectedCategories?.addEventListener('click', (e) => {
            this.moveCategoryItem(e.target, contactsStep.selectedCategories, contactsStep.availableCategories);
            triggerUpdate();
        });

        // Solo habilitar listeners de participantes en modo creación
        if (!this.state.isEditMode) {
            contactsStep.surveyTypeSelect?.addEventListener('change', () => this.handleSurveyTypeChange());
        }
    
        contactsStep.viewContactsBtn?.addEventListener('click', () => this.showContactsModal());
        reviewStep.viewContactsBtn?.addEventListener('click', () => this.showContactsModal());
        contactsModal.closeBtn?.addEventListener('click', () => this.hideContactsModal());
        contactsModal.modal?.addEventListener('click', (e) => {
            if (e.target === contactsModal.modal) this.hideContactsModal();
        });

        // Delegación: eliminar contacto (solo modo edición)
        contactsModal.tableBody?.addEventListener('click', async (e) => {
            const btn = e.target.closest('.btn-delete-contact');
            if (!btn) return;
            if (!this.state.isEditMode) return;

            const contactName = btn.dataset.contactName;
            const displayName = btn.dataset.displayName || contactName;
            const confirmed = window.confirm(`¿Desea eliminar el contacto "${displayName}" de esta medición?` +
                `\nSi el contacto respondió, también se eliminará su respuesta asociada a esta medición.`);
            if (!confirmed) return;

            const originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<i class="fa fa-spinner fa-spin"></i>`;

            try {
                await this.deleteContactFromMeasurement(contactName);
                // Actualizar estado y UI localmente
                this.state.measurementData.contacts.list = this.state.measurementData.contacts.list.filter(c => c.name !== contactName);
                this.updateContactsCountersUI();
                this.showContactsModal(); // re-render modal
                showGlobalNotification('Contacto eliminado correctamente.', 'success');
            } catch (err) {
                console.error(err);
                showGlobalNotification(err.message || 'No se pudo eliminar el contacto.', 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });

        reviewStep.sendRemindersCheck?.addEventListener('change', (e) => {
            reviewStep.remindersSection.classList.toggle('d-none', !e.target.checked);
        });

        Object.values(step1Form).forEach(field => {
            field?.addEventListener('input', () => this.clearValidationError(field));
        });
    }

    updateBreadcrumbs() {
        this.ui.breadcrumbs.forEach(bc => {
            bc.textContent = this.state.measurementData.name || 'Nueva Medición';
        });
    }

    async validateStep1() {
        let isValid = true;
        const { name, startDate, endDate, timezone } = this.ui.step1Form;
        const { next1 } = this.ui.navButtons;
        
        [name, startDate, timezone].forEach(field => this.clearValidationError(field));
        this.clearValidationError(endDate);

        if (name && name.dataset.required === 'true' && !name.value.trim()) {
            isValid = false;
            this.showValidationError(name, 'Este campo es obligatorio.');
        }
        if (name && name.value.trim().length > 75) {
            isValid = false;
            this.showValidationError(name, 'El nombre no puede exceder los 75 caracteres.');
        }
        if (startDate && startDate.dataset.required === 'true' && !startDate.value) {
            isValid = false;
            this.showValidationError(startDate, 'Este campo es obligatorio.');
        }
        
        // Validar que la fecha de inicio no sea anterior al día actual
        if (startDate && startDate.value) {
            const selectedDate = new Date(startDate.value);
            const now = new Date();
            // Normalizamos las fechas al inicio del día (00:00:00) para permitir la fecha actual
            const selectedDay = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate());
            const currentDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());

            if (selectedDay < currentDay) {
                isValid = false;
                this.showValidationError(startDate, 'La fecha de inicio no puede ser anterior al día actual.');
            }
        }

        if (timezone && timezone.dataset.required === 'true' && !timezone.value) {
            isValid = false;
            this.showValidationError(timezone, 'Este campo es obligatorio.');
        }
        if (startDate.value && endDate.value && endDate.value < startDate.value) {
            isValid = false;
            this.showValidationError(endDate, 'La fecha de finalización no puede ser anterior a la fecha de inicio.');
        }

        // Evitar nombres repetidos en la empresa
        if (isValid && name.value.trim()) {
            next1.disabled = true;
            next1.innerHTML = `<i class="fa fa-spinner fa-spin"></i> Validando...`;
            try {
                const args = { name: name.value.trim() };
                if (this.state.isEditMode) {
                    args.exclude_doc = this.state.docName;
                }
                const response = await frappe.call({
                    method: 'liseniq.www.measurement.new_measurement.check_measurement_name',
                    args
                });
                if (response.message && response.message.exists) {
                    const msg = this.state.isEditMode
                        ? 'Ya existe una medición con este nombre en tu empresa.'
                        : 'Ya existe una medición con este nombre.';
                    this.showValidationError(name, msg);
                    isValid = false;
                }
            } catch (error) {
                console.error("Error al validar el nombre de la medición:", error);
                this.showValidationError(name, 'No se pudo validar el nombre. Intente de nuevo.');
                isValid = false;
            } finally {
                next1.disabled = false;
                next1.textContent = 'Siguiente';
            }
        }

        return isValid;
    }
    
    validateStep3() {
        if (this.state.isEditMode) return true;
        const { surveyTypeSelect } = this.ui.contactsStep;
        const { list: contactsList } = this.state.measurementData.contacts;

        if (surveyTypeSelect.value === 'selected' && contactsList.length === 0) {
            showGlobalNotification('Debe seleccionar al menos un participante para continuar.', 'error');
            return false;
        }
        return true;
    }

    showValidationError(field, message) {
        if (!field) return;
        const errorElement = document.getElementById(`${field.id}-error`);
        field.classList.add('is-invalid');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
    }

    clearValidationError(field) {
        if (!field) return;
        const errorElement = document.getElementById(`${field.id}-error`);
        field.classList.remove('is-invalid');
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    }

    handleSurveyTypeChange() {
        const { surveyTypeSelect, selectedContactsSection } = this.ui.contactsStep;
        if (surveyTypeSelect.value === 'selected') {
            selectedContactsSection.classList.remove('d-none');
        } else {
            selectedContactsSection.classList.add('d-none');
        }
        this.updateContactCount();
    }

    handleSendAllCheckChange() {
        const { sendAllContactsCheck, filterSectionContainer } = this.ui.contactsStep;
        filterSectionContainer.classList.toggle('d-none', sendAllContactsCheck.checked);
        this.updateContactCount();
    }

    async handleFieldTypeChange() {
        const { fieldTypeSelect, availableCategories } = this.ui.contactsStep;
        const demographicType = fieldTypeSelect.value;

        availableCategories.innerHTML = '';
        if (!demographicType) return;
        availableCategories.innerHTML = `<div><i class="fa fa-spinner fa-spin"></i> Cargando...</div>`;

        try {
            const response = await frappe.call({
                method: 'liseniq.www.measurement.new_measurement.get_demographic_values_for_contacts',
                args: { demographic_type: demographicType }
            });
            availableCategories.innerHTML = '';
            const data = response.message;
            if (data && data.values && data.values.length > 0) {
                data.values.forEach(value => {
                    if (value) {
                        const item = document.createElement('div');
                        item.className = 'category-item';
                        item.textContent = value;
                        item.dataset.value = value;
                        item.dataset.type = demographicType;
                        if (data.color) item.dataset.color = data.color;
                        availableCategories.appendChild(item);
                    }
                });
            } else {
                availableCategories.innerHTML = '<div class="text-muted small p-2">No hay valores disponibles.</div>';
            }
        } catch (error) {
            console.error("Error al cargar valores demográficos:", error);
            availableCategories.innerHTML = '<div class="text-danger small p-2">Error al cargar datos.</div>';
        }
    }
    
    moveCategoryItem(item, from, to) {
        if (item.classList.contains('category-item')) {
            from.removeChild(item);
            to.appendChild(item);
            if (to.id === 'selected-categories' && item.dataset.color) {
                item.style.backgroundColor = item.dataset.color;
                item.style.color = this.getContrastColor(item.dataset.color);
            } else {
                item.style.backgroundColor = '';
                item.style.color = '';
            }
        }
    }

    async updateContactCount() {
        const { sendAllContactsCheck, selectedCategories, contactCountNumber } = this.ui.contactsStep;
        
        contactCountNumber.innerHTML = `<i class="fa fa-spinner fa-spin"></i>`;
        
        if (!this.state.isEditMode) {
            this.state.measurementData.contacts.list = [];
            this.state.measurementData.contacts.headers = [];
        }

        let filters = [];
        if (this.ui.contactsStep.surveyTypeSelect.value === 'selected' && !sendAllContactsCheck.checked) {
            const selectedItems = Array.from(selectedCategories.children);
            const groupedFilters = selectedItems.reduce((acc, item) => {
                const type = item.dataset.type;
                if (type) {
                    if (!acc[type]) acc[type] = [];
                    acc[type].push(item.dataset.value);
                }
                return acc;
            }, {});
            filters = Object.keys(groupedFilters).map(type => ({
                demographic_type: type,
                values: groupedFilters[type]
            }));
        }

        try {
            const response = await frappe.call({
                method: 'liseniq.www.measurement.new_measurement.get_filtered_contacts_count',
                args: { filters: JSON.stringify(filters) }
            });
            if (response.message) {
                contactCountNumber.textContent = response.message.count;
                this.state.measurementData.contacts.list = response.message.contacts;
                this.state.measurementData.contacts.headers = response.message.headers;
            } else {
                contactCountNumber.textContent = '0';
                this.state.measurementData.contacts.list = [];
                this.state.measurementData.contacts.headers = ['Nombre'];
            }
        } catch (error) {
            console.error("Error al filtrar contactos:", error);
            contactCountNumber.textContent = 'Error';
        }
    }

    // Inicializa el editor WYSIWYG (TinyMCE) para el cuerpo del correo
    initWysiwygEditor(force = false, onReady = null) {
        const textareaId = 'email-body';
        const el = document.getElementById(textareaId);
        if (!el) return;
        const already = window.tinymce && window.tinymce.get(textareaId);
        if (already && !force) {
            this.editorReady = true;
            if (onReady) onReady(already);
            return;
        }
        if (window.tinymce) {
            try { window.tinymce.get(textareaId)?.remove(); } catch(_) {}
            window.tinymce.init({
                selector: `#${textareaId}`,
                menubar: false,
                statusbar: true,
                branding: false,
                plugins: 'link lists autoresize',
                toolbar: 'undo redo | bold italic underline | bullist numlist | link removeformat',
                autoresize_bottom_margin: 24,
                min_height: 360,
                content_style: 'body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto; font-size:14px;}',
                setup: (editor) => {
                    editor.on('init', () => {
                        this.editorReady = true;
                        if (onReady) onReady(editor);
                    });
                    editor.on('change input keyup undo redo', () => {
                        this.syncEmailStateFromFields();
                        this.updateStep4NextButton();
                    });
                }
            });
        }
    }

    setEmailType(type) {
        this.state.currentEmailType = type === 'reminder' ? 'reminder' : 'invitation';
        const { invitation, reminder } = this.ui.personalizationStep.typeButtons;
        if (!invitation || !reminder) return;

        // Limpiar clases anteriores
        invitation.classList.remove('email-type-active');
        reminder.classList.remove('email-type-active');

        if (this.state.currentEmailType === 'invitation') {
            invitation.classList.add('email-type-active');
        } else {
            reminder.classList.add('email-type-active');
        }
    }

    // Función para ocultar/mostrar los campos de personalización
    applyEmailCustomizationToggle() {
        const { customizationFields, useDefaultCheck } = this.ui.personalizationStep;
        if (!customizationFields || !useDefaultCheck) return;
        const useDefault = useDefaultCheck.checked;
        customizationFields.style.display = useDefault ? 'none' : '';
    }

    syncEmailFieldsFromState() {
        if (this.ui.personalizationStep.useDefaultCheck?.checked) {
            this.applyEmailCustomizationToggle();
            return;
        }
        const ec = this.state.measurementData.emailCustomization;
        const { subject, body } = this.ui.personalizationStep;
        const applyContent = () => {
            const editor = window.tinymce?.get('email-body');
            if (this.state.currentEmailType === 'invitation') {
                subject.value = ec.invitation_subject || '';
                editor ? editor.setContent(ec.invitation_body || '') : (body.value = ec.invitation_body || '');
            } else {
                subject.value = ec.reminder_subject || '';
                editor ? editor.setContent(ec.reminder_body || '') : (body.value = ec.reminder_body || '');
            }
            this.applyEmailCustomizationToggle();
        };
        if (!this.editorReady) {
            setTimeout(() => applyContent(), 120);
        } else {
            applyContent();
        }
    }

    syncEmailStateFromFields() {
        // Si se usa plantilla por defecto, no almacenar cambios
        if (this.ui.personalizationStep.useDefaultCheck?.checked) return;
        const { subject, body } = this.ui.personalizationStep;
        const ec = this.state.measurementData.emailCustomization;
        const editor = window.tinymce?.get('email-body');
        const content = editor ? editor.getContent() : (body?.value || '');

        if (this.state.currentEmailType === 'invitation') {
            ec.invitation_subject = subject.value || '';
            ec.invitation_body = content || '';
        } else {
            ec.reminder_subject = subject.value || '';
            ec.reminder_body = content || '';
        }
    }

    // Control dinámico del botón, habilitar o deshabilitar según validez
    updateStep4NextButton() {
        const btn = this.ui.navButtons.next4;
        if (!btn) return;
        const useDefault = !!this.ui.personalizationStep.useDefaultCheck?.checked;
        if (useDefault) {
            btn.disabled = false;
            return;
        }
        const ec = this.state.measurementData.emailCustomization;
        const valid =
            (ec.invitation_subject || '').trim() &&
            (ec.invitation_body || '').trim() &&
            (ec.reminder_subject || '').trim() &&
            (ec.reminder_body || '').trim();
        btn.disabled = !valid;
    }

    async saveMeasurement() {
        const { navButtons, reviewStep, contactsStep, step1Form } = this.ui;
        const saveButton = navButtons.next5;

        saveButton.disabled = true;
        saveButton.innerHTML = this.state.isEditMode
            ? `<i class="fa fa-spinner fa-spin"> </i> Guardando...`
            : `<i class="fa fa-spinner fa-spin"> </i> Enviando...`;

        // Si usa plantilla por defecto, no enviar personalización
        const useDefault = !!this.ui.personalizationStep.useDefaultCheck?.checked;
        const emailCustomization = useDefault ? {} : {
            invitation_subject: this.state.measurementData.emailCustomization.invitation_subject,
            invitation_body: this.state.measurementData.emailCustomization.invitation_body,
            reminder_subject: this.state.measurementData.emailCustomization.reminder_subject,
            reminder_body: this.state.measurementData.emailCustomization.reminder_body
        };

        const reminders = reviewStep.sendRemindersCheck?.checked ? {
            frequency: reviewStep.reminderFrequency?.value,
            max: reviewStep.reminderMax?.value
        } : undefined;

        const basePayload = {
            name: this.state.measurementData.name,
            startDate: step1Form.startDate.value,
            endDate: step1Form.endDate.value,
            email_customization: emailCustomization,
            email_use_default: useDefault,
            ...(reminders ? { reminders } : {})
        };

        const measurementPayload = this.state.isEditMode
            ? { 
                ...basePayload, 
                is_edit_mode: true, 
                doc_name: this.state.docName,
                contacts: {
                    surveyType: this.ui.contactsStep.surveyTypeSelect?.value || 'selected',
                    responseType: this.ui.contactsStep.responseTypeSelect?.value || 'identified',
                    list: this.state.measurementData.contacts.list
                }
            }
            : {
                ...basePayload,
                timezone: step1Form.timezone.value,
                questions: this.state.measurementData.questions,
                contacts: {
                    surveyType: contactsStep.surveyTypeSelect.value,
                    responseType: contactsStep.responseTypeSelect.value,
                    list: this.state.measurementData.contacts.list 
                }
            };

        try {
            const response = await frappe.call({
                method: 'liseniq.www.measurement.new_measurement.save_measurement',
                args: { data: JSON.stringify(measurementPayload) }
            });

            if (response.message && response.message.status === 'success') {
                showGlobalNotification(response.message.message, 'success');
                setTimeout(() => window.location.href = `/iq-home`, 1500);
            } else {
                throw new Error(response.message.message || 'Ocurrió un error al guardar la medición.');
            }
        } catch (error) {
            console.error("Error al guardar la medición:", error);
            showGlobalNotification(error.message, 'error');
            saveButton.disabled = false;
            saveButton.textContent = this.state.isEditMode ? 'Guardar Cambios' : 'Enviar';
        }
    }

    renderReviewStep() {
        const { measurementName, surveyType, responseType, questionsCount, contactCount, questionsList, viewContactsBtn } = this.ui.reviewStep;
        const { surveyTypeSelect, responseTypeSelect } = this.ui.contactsStep;

        measurementName.textContent = this.state.measurementData.name;

        if (this.state.isEditMode) {
            const dataEl = document.getElementById('measurement-data');
            const data = dataEl && dataEl.dataset.measurement ? JSON.parse(dataEl.dataset.measurement) : null;
            surveyType.textContent = data?.contacts?.surveyType === 'selected' ? 'Contactos Cargados Previamente' : 'Público Externo';
            responseType.textContent = data?.contacts?.responseType === 'anonymous' ? 'Anónima' : 'No Anónima';
            questionsCount.textContent = (data?.questions || []).length;

            const listLen = this.state.measurementData.contacts.list?.length || 0;
            contactCount.textContent = listLen;
            if (viewContactsBtn) viewContactsBtn.style.display = listLen > 0 ? 'inline-block' : 'none';
        } else {
            surveyType.textContent = surveyTypeSelect.options[surveyTypeSelect.selectedIndex].text;
            responseType.textContent = responseTypeSelect.options[responseTypeSelect.selectedIndex].text;
            questionsCount.textContent = this.state.measurementData.questions.length;
            contactCount.textContent = this.state.measurementData.contacts.list.length;
            this.ui.reviewStep.viewContactsBtn.style.display = 'inline-block';
        }

        questionsList.innerHTML = '';
        const questions = this.state.isEditMode
            ? (JSON.parse(document.getElementById('measurement-data')?.dataset?.measurement || '{}').questions || [])
            : this.state.measurementData.questions;

        if (questions.length === 0) {
            questionsList.innerHTML = `<div class="text-center text-muted p-4">No se han añadido preguntas.</div>`;
        } else {
            questions.forEach((q, i) => questionsList.appendChild(this.createReviewQuestionItem(q, i)));
        }
    }

    createReviewQuestionItem(question, index) {
        const item = document.createElement('div');
        item.className = 'review-question-item';
        const displayName = question.typeName || question.type;
        let optionsHtml = '';

        if (question.options && question.options.length > 0) {
            optionsHtml = `<div class="review-question-options">${question.options.map(opt => {
                const optionText = (typeof opt === 'object' && opt.text) ? opt.text : opt;
                return `<div class="review-question-option">${frappe.utils.escape_html(optionText)}</div>`;
            }).join('')}</div>`;
        }

        item.innerHTML = `
            <div class="review-question-header">
                <span class="review-question-number">${index + 1}</span>
                <p class="review-question-text">${frappe.utils.escape_html(question.text)}</p>
            </div>
            <div class="review-question-details">
                <span>Tipo: ${frappe.utils.escape_html(displayName)}</span>
                <div><span class="review-question-tag">Tag: ${frappe.utils.escape_html(question.demographic || 'General')}</span></div>
            </div>
            ${optionsHtml}`;
        return item;
    }

    showContactsModal() {
        const { modal, tableHead, tableBody } = this.ui.contactsModal;
        const { headers, list: contacts } = this.state.measurementData.contacts;

        tableHead.innerHTML = '';
        tableBody.innerHTML = '';

        // Encabezados dinámicos
        if (headers && headers.length > 0) {
            const headerRow = tableHead.insertRow();
            headers.forEach(h => {
                const th = document.createElement('th');
                th.textContent = frappe.utils.escape_html(h);
                headerRow.appendChild(th);
            });
            // Agregar columna de acciones en modo edición
            if (this.state.isEditMode) {
                const th = document.createElement('th');
                th.textContent = 'Acciones';
                headerRow.appendChild(th);
            }
        }

        // Filas con datos
        if (contacts && contacts.length > 0) {
            contacts.forEach(c => {
                const row = tableBody.insertRow();
                (headers || ['Nombre']).forEach(h => {
                    const cell = row.insertCell();
                    cell.textContent = frappe.utils.escape_html(c[h] || 'N/A');
                });

                // Celda de acciones (solo modo edición)
                if (this.state.isEditMode) {
                    const cell = row.insertCell();
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn btn-link text-danger btn-delete-contact';
                    btn.dataset.contactName = c.name; // name es el ID interno del Contact
                    btn.dataset.displayName = c['Nombre'] || '';
                    btn.innerHTML = `<i class="fa fa-trash"></i> Eliminar`;
                    cell.appendChild(btn);
                }
            });
        } else {
            tableBody.innerHTML = `<tr><td colspan="${(headers?.length || 1) + (this.state.isEditMode ? 1 : 0)}" class="text-center text-muted p-4">No hay contactos que coincidan.</td></tr>`;
        }
        
        modal.classList.remove('d-none');
    }

    hideContactsModal() {
        this.ui.contactsModal.modal.classList.add('d-none');
    }

    async deleteContactFromMeasurement(contactName) {
        try {
            const response = await frappe.call({
                method: 'liseniq.www.measurement.new_measurement.delete_measurement_contacts',
                args: {
                    survey_name: this.state.docName,
                    contact_names: JSON.stringify([contactName])
                }
            });
            const msg = response.message || {};
            if (msg.status !== 'success') {
                throw new Error(msg.message || 'No se pudo eliminar el contacto.');
            }
            return msg;
        } catch (error) {
            throw error;
        }
    }

    updateContactsCountersUI() {
        // Actualizar contador en Paso 3
        const { contactCountNumber, viewContactsBtn } = this.ui.contactsStep;
        const count = this.state.measurementData.contacts.list.length;
        if (contactCountNumber) contactCountNumber.textContent = String(count);
        if (viewContactsBtn) viewContactsBtn.style.display = count > 0 ? 'inline-block' : 'none';

        // Actualizar contador en Revisión
        const { contactCount, viewContactsBtn: reviewViewBtn } = this.ui.reviewStep;
        if (contactCount) contactCount.textContent = String(count);
        if (reviewViewBtn && this.state.isEditMode) {
            reviewViewBtn.style.display = count > 0 ? 'inline-block' : 'none';
        }
    }

    getContrastColor(hex) {
        if (!hex) return '#000';
        const r = parseInt(hex.substr(1, 2), 16), g = parseInt(hex.substr(3, 2), 16), b = parseInt(hex.substr(5, 2), 16);
        return ((r * 299) + (g * 587) + (b * 114)) / 1000 >= 128 ? '#000' : '#fff';
    }

    validateEmailCustomization() {
        // Si se usa plantilla por defecto, no validar
        const useDefault = !!this.ui.personalizationStep.useDefaultCheck?.checked;
        if (useDefault) return true;

        // Validar que ambos tipos (invitación y recordatorio) tengan asunto y cuerpo
        const ec = this.state.measurementData.emailCustomization;

        const invSubject = (ec.invitation_subject || '').trim();
        const invBody = (ec.invitation_body || '').trim();
        const remSubject = (ec.reminder_subject || '').trim();
        const remBody = (ec.reminder_body || '').trim();

        // Utilidades para mostrar error de campo
        const showFieldError = (inputEl, msgIdSuffix, message) => {
            if (!inputEl) return;
            inputEl.classList.add('is-invalid');
            const errEl = document.getElementById(`${inputEl.id}-error`) || (() => {
                const small = document.createElement('small');
                small.id = `${inputEl.id}-error`;
                small.className = 'form-error-message';
                inputEl.parentElement?.appendChild(small);
                return small;
            })();
            errEl.textContent = message;
            errEl.classList.remove('d-none');
        };
        const clearFieldError = (inputEl) => {
            if (!inputEl) return;
            inputEl.classList.remove('is-invalid');
            const errEl = document.getElementById(`${inputEl.id}-error`);
            if (errEl) errEl.classList.add('d-none');
        };

        // Limpiar errores previos
        clearFieldError(this.ui.personalizationStep.subject);
        // cuerpo validado vía editor o textarea
        const editor = window.tinymce?.get('email-body');
        const bodyEl = this.ui.personalizationStep.body;
        if (bodyEl) {
            bodyEl.classList.remove('is-invalid');
            const errEl = document.getElementById('email-body-error');
            if (errEl) errEl.classList.add('d-none');
        }

        let isValid = true;

        // Validar invitación
        if (!invSubject) {
            // activar UI invitación para que el usuario vea dónde corregir
            this.setEmailType('invitation');
            this.syncEmailFieldsFromState();
            showFieldError(this.ui.personalizationStep.subject, 'email-subject-error', 'El asunto de invitación es obligatorio.');
            isValid = false;
        }
        if (!invBody) {
            this.setEmailType('invitation');
            this.syncEmailFieldsFromState();
            if (editor) {
                // marcar visualmente mediante borde del contenedor (textarea no visible)
                const iframe = editor.getContainer();
                iframe.style.boxShadow = '0 0 0 1px #dc3545';
            } else {
                bodyEl && showFieldError(bodyEl, 'email-body-error', 'El cuerpo de invitación es obligatorio.');
            }
            isValid = false;
        }

        // Validar recordatorio
        if (!remSubject || !remBody) {
            // activar UI recordatorio si falta alguno de sus campos
            this.setEmailType('reminder');
            this.syncEmailFieldsFromState();
        }
        if (!remSubject) {
            showFieldError(this.ui.personalizationStep.subject, 'email-subject-error', 'El asunto de recordatorio es obligatorio.');
            isValid = false;
        }
        if (!remBody) {
            if (editor) {
                const iframe = editor.getContainer();
                iframe.style.boxShadow = '0 0 0 1px #dc3545';
            } else {
                bodyEl && showFieldError(bodyEl, 'email-body-error', 'El cuerpo de recordatorio es obligatorio.');
            }
            isValid = false;
        }

        // Quitar resaltado del editor si todo está OK
        if (isValid && editor) {
            const iframe = editor.getContainer();
            iframe.style.boxShadow = '';
        }

        if (!isValid) {
            showGlobalNotification('Completa los campos de asunto y cuerpo para invitación y recordatorio.', 'error');
        }
        return isValid;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('measurement-stepper-container')) {
        new MeasurementCreator();
    }
});