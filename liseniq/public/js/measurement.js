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
            },
            navButtons: {
                next1: document.getElementById('btn-next-step-1'),
                back2: document.getElementById('btn-back-step-2'),
                next2: document.getElementById('btn-next-step-2'),
                back3: document.getElementById('btn-back-step-3'),
                next3: document.getElementById('btn-next-step-3'),
                back4: document.getElementById('btn-back-step-4'),
                next4: document.getElementById('btn-next-step-4'),
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
            contactCountDebounceTimer: null,
            measurementData: {
                name: '',
                startDate: '',
                endDate: '',
                timezone: 'America/Caracas',
                questions: [],
                contacts: {
                    surveyType: 'all',
                    responseType: 'anonymous',
                    sendToAll: false,
                    filters: [],
                    list: [],
                    headers: []
                }
            }
        };
        
        if (this.ui.stepperContainer) {
            this.stepper = new Stepper('measurement-stepper-container', ['Nombre', 'Preguntas', 'Participantes', 'Revisión']);
            this.questionBuilder = new QuestionBuilder((questions) => {
                this.state.measurementData.questions = questions;
                this.ui.navButtons.next2.disabled = questions.length === 0;
            });
            this.initializeEventListeners();
            this.initializeDefaults();
            this.loadPreloadedQuestions();
            this.stepper.render();
            this.showStep(1);
            this.updateContactCount();
        }
    }

    initializeDefaults() {
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
    }

    initializeEventListeners() {
        const { navButtons, contactsStep, step1Form, contactsModal, reviewStep } = this.ui;

        navButtons.next1?.addEventListener('click', () => {
            if (this.validateStep1()) {
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
                this.renderReviewStep();
                this.showStep(4);
            }
        });
        navButtons.back4?.addEventListener('click', () => this.showStep(3));
        navButtons.next4?.addEventListener('click', () => this.saveMeasurement());
        
        contactsStep.surveyTypeSelect?.addEventListener('change', () => this.handleSurveyTypeChange());
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
    
        contactsStep.viewContactsBtn?.addEventListener('click', () => this.showContactsModal());
        reviewStep.viewContactsBtn?.addEventListener('click', () => this.showContactsModal());
        contactsModal.closeBtn?.addEventListener('click', () => this.hideContactsModal());
        contactsModal.modal?.addEventListener('click', (e) => {
            if (e.target === contactsModal.modal) this.hideContactsModal();
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

    validateStep1() {
        let isValid = true;
        const { name, startDate, endDate, timezone } = this.ui.step1Form;
        
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
        
        if (timezone && timezone.dataset.required === 'true' && !timezone.value) {
            isValid = false;
            this.showValidationError(timezone, 'Este campo es obligatorio.');
        }

        if (startDate.value && endDate.value && endDate.value < startDate.value) {
            isValid = false;
            this.showValidationError(endDate, 'La fecha de finalización no puede ser anterior a la fecha de inicio.');
        }

        return isValid;
    }
    
    validateStep3() {
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
        this.state.measurementData.contacts.list = [];
        this.state.measurementData.contacts.headers = [];

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
            }
        } catch (error) {
            console.error("Error al filtrar contactos:", error);
            contactCountNumber.textContent = 'Error';
        }
    }

    renderReviewStep() {
        const { measurementName, surveyType, responseType, questionsCount, contactCount, questionsList } = this.ui.reviewStep;
        const { surveyTypeSelect, responseTypeSelect } = this.ui.contactsStep;

        measurementName.textContent = this.state.measurementData.name;
        surveyType.textContent = surveyTypeSelect.options[surveyTypeSelect.selectedIndex].text;
        responseType.textContent = responseTypeSelect.options[responseTypeSelect.selectedIndex].text;
        questionsCount.textContent = this.state.measurementData.questions.length;
        contactCount.textContent = this.state.measurementData.contacts.list.length;

        questionsList.innerHTML = '';
        if (this.state.measurementData.questions.length === 0) {
            questionsList.innerHTML = `<div class="text-center text-muted p-4">No se han añadido preguntas.</div>`;
        } else {
            this.state.measurementData.questions.forEach((q, i) => questionsList.appendChild(this.createReviewQuestionItem(q, i)));
        }
    }

    async saveMeasurement() {
        const { navButtons, reviewStep, contactsStep, step1Form } = this.ui;
        const saveButton = navButtons.next4;

        saveButton.disabled = true;
        saveButton.innerHTML = `<i class="fa fa-spinner fa-spin"> </i> Enviando...`;

        const measurementPayload = {
            name: this.state.measurementData.name,
            startDate: step1Form.startDate.value,
            endDate: step1Form.endDate.value,
            timezone: step1Form.timezone.value,
            questions: this.state.measurementData.questions,
            contacts: {
                surveyType: contactsStep.surveyTypeSelect.value,
                responseType: contactsStep.responseTypeSelect.value,
                list: this.state.measurementData.contacts.list 
            }
        };

        if (reviewStep.sendRemindersCheck.checked) {
            measurementPayload.reminders = {
                frequency: reviewStep.reminderFrequency.value,
                max: reviewStep.reminderMax.value,
            };
        }

        try {
            const response = await frappe.call({
                method: 'liseniq.www.measurement.new_measurement.save_measurement',
                args: { data: JSON.stringify(measurementPayload) }
            });

            if (response.message && response.message.status === 'success') {
                showGlobalNotification(response.message.message, 'success');
                setTimeout(() => window.location.href = `/iq-home`, 2000);
            } else {
                throw new Error(response.message.message || 'Ocurrió un error al guardar la medición.');
            }
        } catch (error) {
            console.error("Error al guardar la medición:", error);
            showGlobalNotification(error.message, 'error');
            saveButton.disabled = false;
            saveButton.textContent = 'Enviar';
        }
    }

    createReviewQuestionItem(question, index) {
        const item = document.createElement('div');
        item.className = 'review-question-item';
        const displayName = question.typeName || question.type;
        let optionsHtml = '';

        if (question.options && question.options.length > 0) {
            optionsHtml = `<div class="review-question-options">${question.options.map(opt => `<div class="review-question-option">${frappe.utils.escape_html(opt)}</div>`).join('')}</div>`;
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

        if (headers && headers.length > 0) {
            const headerRow = tableHead.insertRow();
            headers.forEach(h => {
                const th = document.createElement('th');
                th.textContent = frappe.utils.escape_html(h);
                headerRow.appendChild(th);
            });
        }

        if (contacts && contacts.length > 0) {
            contacts.forEach(c => {
                const row = tableBody.insertRow();
                headers.forEach(h => {
                    const cell = row.insertCell();
                    cell.textContent = frappe.utils.escape_html(c[h] || 'N/A');
                });
            });
        } else {
            tableBody.innerHTML = `<tr><td colspan="${headers.length || 1}" class="text-center text-muted p-4">No hay contactos que coincidan.</td></tr>`;
        }
        
        modal.classList.remove('d-none');
    }

    hideContactsModal() {
        this.ui.contactsModal.modal.classList.add('d-none');
    }

    getContrastColor(hex) {
        if (!hex) return '#000';
        const r = parseInt(hex.substr(1, 2), 16), g = parseInt(hex.substr(3, 2), 16), b = parseInt(hex.substr(5, 2), 16);
        return ((r * 299) + (g * 587) + (b * 114)) / 1000 >= 128 ? '#000' : '#fff';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('measurement-stepper-container')) {
        new MeasurementCreator();
    }
});
