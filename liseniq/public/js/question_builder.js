const OPTIONS_BASED_TYPES = ['Selección Múltiple', 'Likert'];
const BIPOLAR_SCALE_TYPES = [];
const NPS_SCALE_TYPES = ['NPS'];
const LIKERT_TYPE_NAME = 'Likert';
const DEFAULT_LIKERT_OPTIONS = [
    'Totalmente en desacuerdo',
    'En desacuerdo',
    'Ni acuerdo ni desacuerdo',
    'De acuerdo',
    'Totalmente de acuerdo'
];

export class QuestionBuilder {
    constructor(onQuestionsUpdate) {
        this.questions = [];
        this.bankState = {
            questions: [],
            demographics: [],
            selectedIds: new Set(),
            activeDemographic: null,
            searchKeyword: ''
        };
        this.searchDebounceTimer = null;
        this.demographicDebounceTimer = null;
        this.onQuestionsUpdate = onQuestionsUpdate;

        this.ui = this._mapUI();
        this._initializeEventListeners();
        this.renderQuestions();
        this.resetAddQuestionForm();
    }

    _mapUI() {
        return {
            buttons: {
                openQuestionBank: document.getElementById('btn-open-question-bank'),
                addQuestion: document.getElementById('btn-add-question'),
                addOption: document.getElementById('btn-add-option'),
            },
            questionForm: {
                text: document.getElementById('new_question_text'),
                type: document.getElementById('new_question_type'),
                demographic: document.getElementById('new_question_demographic'),
                demographicResults: document.querySelector('#new_question_demographic + .autocomplete-results'),
                optionsSection: document.getElementById('options-based-section'),
                optionsContainer: document.getElementById('options-container'),
                bipolarSection: document.getElementById('bipolar-scale-section'),
                negativeStatement: document.getElementById('negative_statement_input'),
                positiveStatement: document.getElementById('positive_statement_input'),
                npsSection: document.getElementById('nps-scale-section'),
                npsMin: document.getElementById('nps_min_input'),
                npsMax: document.getElementById('nps_max_input'),
                listContainer: document.getElementById('questions-list'),
            },
            bankModal: {
                modal: document.getElementById('question-bank-modal'),
                closeBtn: document.getElementById('btn-close-modal'),
                categoryList: document.getElementById('bank-category-filter-list'),
                searchInput: document.getElementById('bank-search-input'),
                questionsContainer: document.getElementById('bank-questions-container'),
                selectedContainer: document.getElementById('modal-selected-questions-container'),
                addSelectedBtn: document.getElementById('btn-add-selected-questions'),
            }
        };
    }

    _initializeEventListeners() {
        const { buttons, questionForm, bankModal } = this.ui;

        buttons.openQuestionBank?.addEventListener('click', () => this.openModal());
        bankModal.closeBtn?.addEventListener('click', () => this.closeModal());
        bankModal.modal?.addEventListener('click', (e) => { if (e.target === bankModal.modal) this.closeModal(); });
        bankModal.addSelectedBtn?.addEventListener('click', () => this.addSelectedQuestions());

        bankModal.searchInput?.addEventListener('input', (e) => {
            clearTimeout(this.searchDebounceTimer);
            this.searchDebounceTimer = setTimeout(() => {
                this.bankState.searchKeyword = e.target.value.trim();
                this.fetchBankData();
            }, 300);
        });

        bankModal.categoryList?.addEventListener('click', (e) => {
            const target = e.target.closest('.category-filter-item');
            if (!target) return;
            
            const activeElement = bankModal.categoryList.querySelector('.active');
            if (activeElement) activeElement.classList.remove('active');
            
            target.classList.add('active');
            this.bankState.activeDemographic = target.dataset.demographicId;
            this.fetchBankData();
        });

        bankModal.questionsContainer?.addEventListener('click', (e) => {
            const addIcon = e.target.closest('.add-icon');
            if (!addIcon) return;
            const card = addIcon.closest('.bank-question-card');
            if (!card) return;

            const questionId = card.getAttribute('data-id');
            if (this.bankState.selectedIds.has(questionId)) {
                this.bankState.selectedIds.delete(questionId);
            } else {
                this.bankState.selectedIds.add(questionId);
            }
            this.renderBankQuestions();
            this.renderModalSelectedQuestions();
        });

        buttons.addQuestion?.addEventListener('click', () => this.addManualQuestion());
        questionForm.listContainer?.addEventListener('click', (e) => this.handleQuestionListActions(e));
        questionForm.text?.addEventListener('input', () => this._clearValidationError(questionForm.text));
        questionForm.type?.addEventListener('change', () => this.handleQuestionTypeChange());
        buttons.addOption?.addEventListener('click', () => this.addOptionRow());
        questionForm.optionsContainer?.addEventListener('click', (e) => this.handleOptionsActions(e));

        questionForm.demographic?.addEventListener('input', () => this.onDemographicInput());
        questionForm.demographicResults?.addEventListener('click', (e) => this.onDemographicSelect(e));
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.form-group')) {
                if(questionForm.demographicResults) questionForm.demographicResults.style.display = 'none';
            }
        });
    }

    getQuestions() {
        return this.questions;
    }

    setQuestions(initialQuestions) {
        this.questions = initialQuestions || [];
        this.renderQuestions();
    }

    renderQuestions() {
        const { listContainer } = this.ui.questionForm;
        if (!listContainer) return;
        listContainer.innerHTML = ''; 

        if (this.questions.length === 0) {
            listContainer.innerHTML = `<div class="text-center text-muted p-5">Aún no has agregado ninguna pregunta.</div>`;
        } else {
            this.questions.forEach((question, index) => {
                const questionCard = this._createQuestionCard(question, index);
                listContainer.appendChild(questionCard);
            });
        }
        
        if (this.onQuestionsUpdate) {
            this.onQuestionsUpdate(this.questions);
        }
    }
    
    _createQuestionCard(question, index) {
        const questionCard = document.createElement('div');
        questionCard.className = 'question-item'; 
        questionCard.setAttribute('data-index', index); 

        const questionDisplayName = question.typeName || question.type;
        let additionalInfoHtml = '';

        if (OPTIONS_BASED_TYPES.includes(questionDisplayName) && Array.isArray(question.options) && question.options.length > 0) {
            additionalInfoHtml = `<div class="question-item-options-list">
                ${question.options.map(opt => `<div class="question-option-item">${frappe.utils.escape_html(opt)}</div>`).join('')}
            </div>`;
        }
        
        if (NPS_SCALE_TYPES.includes(questionDisplayName)) {
            additionalInfoHtml = `<div class="question-nps-scale">
                <p><strong>Escala:</strong> de ${frappe.utils.escape_html(question.nps_min)} a ${frappe.utils.escape_html(question.nps_max)}</p>
            </div>`;
        }
        
        questionCard.innerHTML = `
            <div class="question-item-header">
                <div class="question-item-main">
                    <div class="question-item-number">${index + 1}</div>
                    <div class="question-item-content">
                        <p class="question-item-text">${frappe.utils.escape_html(question.text)}</p>
                        <p class="question-item-type">Tipo: ${frappe.utils.escape_html(questionDisplayName)}</p>
                    </div>
                </div>
                <div class="question-item-actions">
                    <div class="action-icons">
                        <i class="fa fa-trash-o delete-question" title="Eliminar pregunta"></i>
                    </div>
                    <div class="question-item-tags">
                        <span>Tag: ${frappe.utils.escape_html(question.demographic || 'General')}</span>

                    </div>
                </div>
            </div>
            ${additionalInfoHtml}
        `;
        return questionCard;
    }

    async fetchBankData() {
        this.ui.bankModal.questionsContainer.innerHTML = `<div class="text-center p-5"><i class="fa fa-spinner fa-spin"></i> Cargando...</div>`;
        try {
            const response = await frappe.call({
                method: 'liseniq.www.iq-templates.index.get_bank_data',
                args: {
                    keyword: this.bankState.searchKeyword,
                    demographic: this.bankState.activeDemographic
                }
            });
            
            if (response.message) {
                this.bankState.questions = response.message.questions;
                if (this.bankState.demographics.length === 0) {
                    this.bankState.demographics = response.message.demographics;
                    this.renderBankDemographics();
                }
                this.renderBankQuestions();
            }
        } catch (error) {
            console.error("Error fetching question bank data:", error);
            this.ui.bankModal.questionsContainer.innerHTML = `<div class="text-center text-muted p-5">Error al cargar las preguntas.</div>`;
        }
    }

    openModal() {
        this.bankState.selectedIds.clear();
        this.bankState.activeDemographic = null;
        this.bankState.searchKeyword = '';
        this.ui.bankModal.searchInput.value = '';
        this.fetchBankData();
        this.renderModalSelectedQuestions();
        this.ui.bankModal.modal.classList.remove('d-none');
    }

    closeModal() {
        this.ui.bankModal.modal.classList.add('d-none');
    }
    
    renderBankDemographics() {
        const { categoryList } = this.ui.bankModal;
        if (!categoryList) return;
        categoryList.innerHTML = '';
        
        const allDemographicsItem = document.createElement('li');
        allDemographicsItem.className = 'category-filter-item active';
        allDemographicsItem.textContent = 'Todos los Temas';
        allDemographicsItem.setAttribute('data-demographic-id', '');
        categoryList.appendChild(allDemographicsItem);

        this.bankState.demographics.forEach(demo => {
            const item = document.createElement('li');
            item.className = 'category-filter-item';
            item.textContent = demo.dt_title;
            item.setAttribute('data-demographic-id', demo.name);
            categoryList.appendChild(item);
        });
    }

    renderBankQuestions() {
        const { questionsContainer } = this.ui.bankModal;
        if (!questionsContainer) return;
        questionsContainer.innerHTML = '';

        if (this.bankState.questions.length === 0) {
            questionsContainer.innerHTML = `<div class="empty-state">No se encontraron preguntas con los filtros actuales.</div>`;
            return;
        }
        
        this.bankState.questions.forEach(q => {
            const isSelected = this.bankState.selectedIds.has(q.name);
            const card = document.createElement('div');
            card.className = 'bank-question-card';
            card.setAttribute('data-id', q.name);

            let optionsPreviewHtml = '';
            if (q.type_name === 'Selección Múltiple' && Array.isArray(q.options) && q.options.length > 0) {
                optionsPreviewHtml = `
                    <div class="options-preview">
                        <strong>Opciones de respuesta</strong>
                        ${q.options.map(opt => `<div>- ${frappe.utils.escape_html(opt)}</div>`).join('')}
                    </div>`;
            }

            card.innerHTML = `
                <div class="bank-question-card-main">
                    <div class="add-icon ${isSelected ? 'selected' : ''}" title="${isSelected ? 'Quitar' : 'Agregar'}">
                        <i class="fa ${isSelected ? 'fa-check' : 'fa-plus'}"></i>
                    </div>
                    <div class="card-content">
                        <p class="question-text">${frappe.utils.escape_html(q.text)}</p>
                    </div>
                </div>
                ${optionsPreviewHtml}
                <div class="question-details">
                    <span class="category-tag">• Tag: ${frappe.utils.escape_html(q.demographic_name)}</span>
                    <span>Tipo: ${frappe.utils.escape_html(q.type_name)}</span>
                </div>
            `;
            questionsContainer.appendChild(card);
        });
    }

    renderModalSelectedQuestions() {
        const { selectedContainer, addSelectedBtn } = this.ui.bankModal;
        if (!selectedContainer) return;
        selectedContainer.innerHTML = '';
        
        const selectedQuestions = [];
        this.bankState.selectedIds.forEach(id => {
            const question = this.bankState.questions.find(q => q.name === id);
            if(question) selectedQuestions.push(question);
        });

        if (selectedQuestions.length === 0) {
            selectedContainer.innerHTML = `<div class="empty-state"><p>Aún no has seleccionado ninguna pregunta.</p></div>`;
            addSelectedBtn.disabled = true;
        } else {
            selectedQuestions.forEach((q, index) => {
                const item = document.createElement('div');
                item.className = 'selected-question-item';
                item.innerHTML = `
                    <div class="item-number">${index + 1}</div>
                    <div class="item-content">
                        <p class="item-text">${frappe.utils.escape_html(q.text)}</p>
                        <div class="item-details">
                            <span class="category-tag-selected">• ${frappe.utils.escape_html(q.demographic_name)}</span>
                            <span>${frappe.utils.escape_html(q.type_name)}</span>
                        </div>
                    </div>
                `;
                selectedContainer.appendChild(item);
            });
            addSelectedBtn.disabled = false;
        }
    }
    
    addSelectedQuestions() {
        this.bankState.selectedIds.forEach(id => {
            if (!this.questions.some(mainQ => mainQ.id === id)) {
                const questionToAdd = this.bankState.questions.find(q => q.name === id);
                if (questionToAdd) {
                    this.questions.push({ 
                        id: questionToAdd.name,
                        text: questionToAdd.text,
                        type: questionToAdd.qn_type,
                        typeName: questionToAdd.type_name,
                        category_name: questionToAdd.category_name,
                        demographic: questionToAdd.demographic_name,
                        options: questionToAdd.options || []
                    });
                }
            }
        });
        this.renderQuestions();
        this.closeModal();
    }

    resetAddQuestionForm() {
        const qf = this.ui.questionForm;
        qf.text.value = '';
        qf.type.value = '';
        qf.demographic.value = '';
        
        this._setEditableOptions();
        
        if(qf.negativeStatement) qf.negativeStatement.value = '';
        if(qf.positiveStatement) qf.positiveStatement.value = '';
        if(qf.npsMin) qf.npsMin.value = '';
        if(qf.npsMax) qf.npsMax.value = '';

        if(qf.optionsSection) qf.optionsSection.classList.add('d-none');
        if(qf.bipolarSection) qf.bipolarSection.classList.add('d-none');
        if(qf.npsSection) qf.npsSection.classList.add('d-none');
        
        [qf.text, qf.type, qf.demographic, qf.negativeStatement, qf.positiveStatement, qf.npsMin, qf.npsMax].forEach(field => this._clearValidationError(field));
    }

    validateQuestionForm() {
        let isValid = true;
        const qf = this.ui.questionForm;
        const selectedOption = qf.type.options[qf.type.selectedIndex];
        const questionTypeName = selectedOption ? selectedOption.text.trim() : '';

        [qf.text, qf.type, qf.negativeStatement, qf.positiveStatement, qf.npsMin, qf.npsMax].forEach(field => this._clearValidationError(field));

        if (!qf.text.value.trim()) {
            this._showValidationError(qf.text, 'Este campo es requerido.');
            isValid = false;
        }
        if (!qf.type.value) {
            this._showValidationError(qf.type, 'Este campo es requerido.');
            isValid = false;
        }

        if (NPS_SCALE_TYPES.includes(questionTypeName)) {
            const min = parseInt(qf.npsMin.value, 10);
            const max = parseInt(qf.npsMax.value, 10);
            if (isNaN(min) || min < 1) {
                this._showValidationError(qf.npsMin, 'El valor mínimo debe ser 1 o mayor.');
                isValid = false;
            }
            if (isNaN(max) || max !== 10) {
                this._showValidationError(qf.npsMax, 'El valor máximo debe ser 10.');
                isValid = false;
            }
            if (!isNaN(min) && !isNaN(max) && min >= max) {
                this._showValidationError(qf.npsMax, 'El valor máximo debe ser mayor que el mínimo.');
                isValid = false;
            }
        }

        if (OPTIONS_BASED_TYPES.includes(questionTypeName) && questionTypeName !== LIKERT_TYPE_NAME) {
            const options = Array.from(qf.optionsContainer.querySelectorAll('.option-input')).map(input => input.value.trim()).filter(Boolean);
            if (options.length < 1) {
                showGlobalNotification('Debes agregar al menos 1 opción de respuesta.', 'error', 3000);
                isValid = false;
            }
        }

        return isValid;
    }

    updateOptionNumbers() {
        if (this.ui.questionForm.optionsContainer) {
            this.ui.questionForm.optionsContainer.querySelectorAll('.option-input-row').forEach((row, index) => {
                const numberElement = row.querySelector('.option-number');
                if (numberElement) numberElement.textContent = index + 1;
            });
        }
    }

    addOptionRow() {
        const { optionsContainer } = this.ui.questionForm;
        if (!optionsContainer) return;
        const newRow = document.createElement('div');
        newRow.className = 'option-input-row';
        newRow.innerHTML = `<span class="option-number"></span><input type="text" class="form-control option-input" placeholder="Escribe tu opción aqui"><i class="fa fa-trash-o text-danger delete-option" style="cursor: pointer;"></i>`;
        optionsContainer.appendChild(newRow);
        this.updateOptionNumbers();
    }
    
    addManualQuestion() {
        if (!this.validateQuestionForm()) return;

        const qf = this.ui.questionForm;
        const questionTypeOption = qf.type.options[qf.type.selectedIndex];
        const questionTypeName = questionTypeOption ? questionTypeOption.text.trim() : '';
        
        const newQuestion = { 
            id: `manual-${Date.now()}`, 
            text: qf.text.value.trim(), 
            type: qf.type.value, 
            typeName: questionTypeName, 
            demographic: qf.demographic.value.trim(),
            category_name: 'Manual' 
        };

        if (questionTypeName === LIKERT_TYPE_NAME) {
            newQuestion.options = DEFAULT_LIKERT_OPTIONS;
        } else if (OPTIONS_BASED_TYPES.includes(questionTypeName)) {
            newQuestion.options = Array.from(qf.optionsContainer.querySelectorAll('.option-input')).map(input => input.value.trim()).filter(Boolean);
        }

        if (NPS_SCALE_TYPES.includes(questionTypeName)) {
            newQuestion.nps_min = qf.npsMin.value;
            newQuestion.nps_max = qf.npsMax.value;
        }

        this.questions.push(newQuestion);
        this.renderQuestions();
        this.resetAddQuestionForm();
    }

    handleQuestionListActions(e) {
        const questionItem = e.target.closest('.question-item');
        if (!questionItem) return;
        const index = parseInt(questionItem.getAttribute('data-index'), 10);
        if (e.target.classList.contains('delete-question')) {
            this.questions.splice(index, 1);
            this.renderQuestions();
        }
    }

    handleQuestionTypeChange() {
        const qf = this.ui.questionForm;
        if (qf.type.value) this._clearValidationError(qf.type);
        
        const selectedOption = qf.type.options[qf.type.selectedIndex];
        const questionTypeName = selectedOption ? selectedOption.text.trim() : '';

        if (questionTypeName === LIKERT_TYPE_NAME) {
            this._setLikertOptions();
        } else {
            this._setEditableOptions();
        }

        if (qf.optionsSection) qf.optionsSection.classList.toggle('d-none', !OPTIONS_BASED_TYPES.includes(questionTypeName));
        if (qf.bipolarSection) qf.bipolarSection.classList.toggle('d-none', !BIPOLAR_SCALE_TYPES.includes(questionTypeName));
        if (qf.npsSection) qf.npsSection.classList.toggle('d-none', !NPS_SCALE_TYPES.includes(questionTypeName));
    }

    handleOptionsActions(e) {
        if (e.target.classList.contains('delete-option')) {
            const { optionsContainer } = this.ui.questionForm;
            if (optionsContainer.querySelectorAll('.option-input-row').length > 1) {
                e.target.closest('.option-input-row').remove();
                this.updateOptionNumbers();
            } else {
                showGlobalNotification('Debe haber al menos una opción.', 'error', 3000);
            }
        }
    }

    onDemographicInput() {
        const { demographic, demographicResults } = this.ui.questionForm;
        const searchTerm = demographic.value.trim();

        clearTimeout(this.demographicDebounceTimer);
        this.demographicDebounceTimer = setTimeout(() => {
            if (searchTerm.length > 1) {
                frappe.call({
                    method: 'liseniq.www.iq-templates.index.get_demographic_suggestions_for_questions',
                    args: { search_term: searchTerm },
                    callback: (r) => {
                        demographicResults.innerHTML = '';
                        if (r.message && r.message.length > 0) {
                            r.message.forEach(item => {
                                const div = document.createElement('div');
                                div.className = 'autocomplete-item';
                                div.textContent = item.dt_title;
                                demographicResults.appendChild(div);
                            });
                            demographicResults.style.display = 'block';
                        } else {
                            demographicResults.style.display = 'none';
                        }
                    }
                });
            } else {
                demographicResults.style.display = 'none';
            }
        }, 300);
    }

    onDemographicSelect(e) {
        const { demographic, demographicResults } = this.ui.questionForm;
        if (e.target.classList.contains('autocomplete-item')) {
            demographic.value = e.target.textContent;
            demographicResults.style.display = 'none';
        }
    }
    
    _setLikertOptions() {
        const { optionsContainer } = this.ui.questionForm;
        const { addOption } = this.ui.buttons;
        if (!optionsContainer) return;
        
        optionsContainer.innerHTML = '';
        DEFAULT_LIKERT_OPTIONS.forEach((text, index) => {
            const row = document.createElement('div');
            row.className = 'option-input-row is-readonly';
            row.innerHTML = `<span class="option-number">${index + 1}</span><input type="text" class="form-control option-input" value="${frappe.utils.escape_html(text)}" readonly>`;
            optionsContainer.appendChild(row);
        });
        
        if (addOption) addOption.classList.add('d-none');
    }

    _setEditableOptions() {
        const { optionsContainer } = this.ui.questionForm;
        const { addOption } = this.ui.buttons;
        if (!optionsContainer) return;

        optionsContainer.innerHTML = `<div class="option-input-row"><span class="option-number">1</span><input type="text" class="form-control option-input" placeholder="Escribe tu opción aqui"><i class="fa fa-trash-o text-danger delete-option" style="cursor: pointer;"></i></div>`;
        this.updateOptionNumbers();

        if (addOption) addOption.classList.remove('d-none');
    }

    _showValidationError(field, message) {
        if (!field) return;
        field.classList.add('is-invalid');
        const errorElement = document.getElementById(`${field.id}_error`);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
    }

    _clearValidationError(field) {
        if (!field) return;
        field.classList.remove('is-invalid');
        const errorElement = document.getElementById(`${field.id}_error`);
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    }
}