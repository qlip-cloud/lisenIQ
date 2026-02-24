const OPTIONS_BASED_TYPES = ['Selección Múltiple', 'Likert', 'Casilla de verificación'];
const BIPOLAR_SCALE_TYPES = [];
const NPS_SCALE_TYPES = ['NPS'];
const LIKERT_TYPE_NAME = 'Likert';
const LIKERT_VISUAL_TYPE_NAME = 'Likert Visual';
const CHECKBOX_TYPE_NAME = 'Casilla de verificación';
const LIKERT_ICON_MAP = {
    5: "/files/aiq - totalmente de acuerdo.png",
    4: "/files/aiq - de acuerdo.png",
    3: "/files/aiq - ni de acuerdo ni desacuerdo.png",
    2: "/files/aiq - desacuerdo.png",
    1: "/files/aiq - totalmente desacuerdo.png",
};
const DEFAULT_LIKERT_OPTIONS = [
    { text: 'Totalmente de acuerdo', value: 5 },
    { text: 'De acuerdo', value: 4 },
    { text: 'Ni acuerdo ni desacuerdo', value: 3 },
    { text: 'En desacuerdo', value: 2 },
    { text: 'Totalmente en desacuerdo', value: 1 },
];

const getLikertIconUrl = (val) => LIKERT_ICON_MAP[Number(val)] || '';

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
        this.isReadOnly = false;
        
        // Estado para Liderazgo
        this.isLeadershipMode = false;
        this.currentCategoryName = '';

        this.ui = this._mapUI();
        this._initializeEventListeners();
        this.renderQuestions();

        if (this.ui.questionForm && this.ui.questionForm.text) {
            this.resetAddQuestionForm();
        }
    }

    setCategory(categoryName) {
        this.currentCategoryName = categoryName;
        this.isLeadershipMode = (categoryName && categoryName.trim() === 'Liderazgo');
        this._updateUIForCategory();
    }

    _updateUIForCategory() {
        const { questionForm } = this.ui;
        const textLabel = document.querySelector('label[for="new_question_text"]');
        
        if (this.isLeadershipMode) {
            // Mostrar campo extra y cambiar labels
            if (questionForm.leadershipContainer) {
                questionForm.leadershipContainer.classList.remove('d-none');
            }
            if (textLabel) textLabel.textContent = "Texto de la Pregunta / Enunciado Autoevaluación (Evaluado)";
            if (questionForm.text) questionForm.text.placeholder = "Ej: Fomento el desarrollo de mi equipo...";
        } else {
            // Ocultar campo extra y revertir labels
            if (questionForm.leadershipContainer) {
                questionForm.leadershipContainer.classList.add('d-none');
            }
            if (textLabel) textLabel.textContent = "Texto de la Pregunta / Enunciado Principal";
            if (questionForm.text) questionForm.text.placeholder = "";
        }
    }

    // Permite que el contenedor externo active modo edición como solo lectura
    setEditMode(isEditMode) {
        this.isReadOnly = !!isEditMode;
        this._applyReadOnlyUI();
        this.renderQuestions();
    }

    // Alias compatible por si se llama setReadOnly
    setReadOnly(flag) {
        this.isReadOnly = !!flag;
        this._applyReadOnlyUI();
        this.renderQuestions();
    }

    _applyReadOnlyUI() {
        const { buttons, questionForm, bankModal } = this.ui;

        [buttons.openQuestionBank, buttons.addQuestion, buttons.addOption].forEach(btn => {
            if (btn) btn.disabled = this.isReadOnly;
        });

        if (this.isReadOnly) {
            if (questionForm.demographicResults) questionForm.demographicResults.style.display = 'none';
        }

        if (questionForm.listContainer) {
        }

        if (this.isReadOnly && bankModal?.modal) {
            bankModal.modal.classList.add('d-none');
        }
    }

    _mapUI() {
        return {
            buttons: {
                openQuestionBank: document.getElementById('btn-open-question-bank'),
                addQuestion: document.getElementById('btn-add-question'),
                addOption: document.getElementById('btn-add-option'),
                addVisualOption: document.getElementById('btn-add-visual-option'),
            },
            questionForm: {
                text: document.getElementById('new_question_text'),
                textOthers: document.getElementById('new_question_text_others'), 
                leadershipContainer: document.getElementById('leadership-statement-container'),

                type: document.getElementById('new_question_type'),
                demographic: document.getElementById('new_question_demographic'),
                demographicResults: document.querySelector('#new_question_demographic + .autocomplete-results'),
                optionsSection: document.getElementById('options-based-section'),
                optionsContainer: document.getElementById('options-container'),
                visualOptionsSection: document.getElementById('visual-options-section'),
                visualOptionsContainer: document.getElementById('visual-options-container'),
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

        buttons.openQuestionBank?.addEventListener('click', () => {
            if (this.isReadOnly) return;
            this.openModal();
        });
        bankModal.closeBtn?.addEventListener('click', () => this.closeModal());
        bankModal.modal?.addEventListener('click', (e) => { if (e.target === bankModal.modal) this.closeModal(); });
        bankModal.addSelectedBtn?.addEventListener('click', () => {
            if (this.isReadOnly) return;
            this.addSelectedQuestions();
        });

        bankModal.searchInput?.addEventListener('input', (e) => {
            if (this.isReadOnly) return;
            clearTimeout(this.searchDebounceTimer);
            this.searchDebounceTimer = setTimeout(() => {
                this.bankState.searchKeyword = e.target.value.trim();
                this.fetchBankData();
            }, 300);
        });

        bankModal.categoryList?.addEventListener('click', (e) => {
            if (this.isReadOnly) return;
            const target = e.target.closest('.category-filter-item');
            if (!target) return;
            
            const activeElement = bankModal.categoryList.querySelector('.active');
            if (activeElement) activeElement.classList.remove('active');
            
            target.classList.add('active');
            this.bankState.activeDemographic = target.dataset.demographicId;
            this.fetchBankData();
        });

        bankModal.questionsContainer?.addEventListener('click', (e) => {
            if (this.isReadOnly) return;
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

        buttons.addQuestion?.addEventListener('click', () => {
            if (this.isReadOnly) return;
            this.addManualQuestion();
        });
        questionForm.listContainer?.addEventListener('click', (e) => this.handleQuestionListActions(e));
        
        // Limpiar errores en inputs de texto
        questionForm.text?.addEventListener('input', () => this._clearValidationError(questionForm.text));
        questionForm.textOthers?.addEventListener('input', () => this._clearValidationError(questionForm.textOthers));

        questionForm.type?.addEventListener('change', () => this.handleQuestionTypeChange());
        buttons.addOption?.addEventListener('click', () => {
            if (this.isReadOnly) return;
            this.addOptionRow();
        });
        questionForm.optionsContainer?.addEventListener('click', (e) => this.handleOptionsActions(e));

        // Eventos para Likert Visual
        buttons.addVisualOption?.addEventListener('click', () => {
            if (this.isReadOnly) return;
            this.addVisualOptionRow();
        });
        questionForm.visualOptionsContainer?.addEventListener('click', (e) => this.handleVisualOptionsActions(e));
        questionForm.visualOptionsContainer?.addEventListener('change', async (e) => {
            if (this.isReadOnly) return;
            const fileInput = e.target.closest('.visual-option-file');
            if (!fileInput) return;
            const row = e.target.closest('.visual-option-input-row');
            const file = fileInput.files && fileInput.files[0];
            if (!file || !row) return;

            try {
                this._setVisualUploadingState(row, true);
                const fileUrl = await this._uploadVisualOptionFile(file);
                const hiddenUrl = row.querySelector('.visual-option-url-input');
                const preview = row.querySelector('.visual-file-preview');
                const img = preview?.querySelector('img');
                const nameSpan = preview?.querySelector('.file-name');
                if (hiddenUrl) hiddenUrl.value = fileUrl || '';
                if (img) img.src = fileUrl || '';
                if (nameSpan) nameSpan.textContent = file.name;
                if (preview) preview.classList.toggle('d-none', !fileUrl);
            } catch (err) {
                console.error('Error al subir la imagen de la opción:', err);
                showGlobalNotification('No se pudo subir la imagen. Intenta nuevamente.', 'error', 4000);
                // Limpia selección en caso de error
                fileInput.value = '';
            } finally {
                this._setVisualUploadingState(row, false);
            }
        });

        questionForm.demographic?.addEventListener('input', () => {
            if (this.isReadOnly) return;
            this.onDemographicInput();
        });
        questionForm.demographicResults?.addEventListener('click', (e) => {
            if (this.isReadOnly) return;
            this.onDemographicSelect(e);
        });
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.form-group')) {
                if(this.ui.questionForm.demographicResults) this.ui.questionForm.demographicResults.style.display = 'none';
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

        if (Array.isArray(question.options) && question.options.length > 0) {
            if (questionDisplayName === LIKERT_VISUAL_TYPE_NAME || questionDisplayName === LIKERT_TYPE_NAME) {
                additionalInfoHtml = `<div class="question-item-options-list">
                    ${question.options.map(opt => {
                        const text = (typeof opt === 'object') ? (opt.text || '') : String(opt || '');
                        const url = (typeof opt === 'object') ? (opt.url || '') : '';
                        return `<div class="question-option-item">
                            ${url ? `<img src="${frappe.utils.escape_html(url)}" alt="" style="width:20px;height:20px;object-fit:contain;margin-right:6px;">` : ''}
                            ${frappe.utils.escape_html(text)}
                        </div>`;
                    }).join('')}
                </div>`;
            } else if (OPTIONS_BASED_TYPES.includes(questionDisplayName)) {
                let optionsItemsHtml = question.options.map(opt => {
                    const optionText = (typeof opt === 'object' && opt.text) ? opt.text : opt;
                    return `<div class="question-option-item">${frappe.utils.escape_html(optionText)}</div>`;
                }).join('');
                
                if (questionDisplayName === CHECKBOX_TYPE_NAME) {
                    if (question.qp_others) optionsItemsHtml += `<div class="question-option-item" style="font-style:italic;">Otros</div>`;
                    if (question.qp_none_above) optionsItemsHtml += `<div class="question-option-item" style="font-style:italic;">Ninguna de las anteriores</div>`;
                }

                additionalInfoHtml = `<div class="question-item-options-list">
                    ${optionsItemsHtml}
                </div>`;
            }
        }
        
        if (NPS_SCALE_TYPES.includes(questionDisplayName)) {
            const npsMin = (question.nps_min ?? question.npsMin ?? 1);
            const npsMax = (question.nps_max ?? question.npsMax ?? 10);
            additionalInfoHtml = `<div class="question-nps-scale">
                <p><strong>Escala:</strong> de ${frappe.utils.escape_html(npsMin)} a ${frappe.utils.escape_html(npsMax)}</p>
            </div>`;
        }

        // Mostrar ambos enunciados si es Liderazgo
        let statementsHtml = `<p class="question-item-text">${frappe.utils.escape_html(question.text)}</p>`;
        if (question.text_others) {
            statementsHtml = `
                <div class="mb-2">
                    <p class="question-item-text mb-1"><strong class="text-muted" style="font-size:0.8em">Yo:</strong> ${frappe.utils.escape_html(question.text)}</p>
                    <p class="question-item-text"><strong class="text-muted" style="font-size:0.8em">Otros:</strong> ${frappe.utils.escape_html(question.text_others)}</p>
                </div>
            `;
        }
        
        questionCard.innerHTML = `
            <div class="question-item-header">
                <div class="question-item-main">
                    <div class="question-item-number">${index + 1}</div>
                    <div class="question-item-content">
                        ${statementsHtml}
                        <p class="question-item-type">Tipo: ${frappe.utils.escape_html(questionDisplayName)}</p>
                    </div>
                </div>
                <div class="question-item-actions">
                    <div class="action-icons">
                        ${this.isReadOnly ? '' : '<i class="fa fa-trash-o delete-question" title="Eliminar pregunta"></i>'}
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
        if (this.isReadOnly) return;
        this.ui.bankModal.questionsContainer.innerHTML = `<div class="text-center p-5"><i class="fa fa-spinner fa-spin"></i> Cargando...</div>`;
        try {
            const response = await frappe.call({
                method: 'liseniq.www.iq-templates.index.get_bank_data',
                args: {
                    keyword: this.bankState.searchKeyword,
                    demographic: this.bankState.activeDemographic,
                    template_category: this.currentCategoryName // Pasar la categoría actual para filtro Liderazgo
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
        if (this.isReadOnly) return;
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
        allDemographicsItem.textContent = 'Todos los temas';
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
            // Preview para Selección Múltiple y Casilla de verificación (texto plano)
            if ((q.type_name === 'Selección Múltiple' || q.type_name === CHECKBOX_TYPE_NAME) && Array.isArray(q.options) && q.options.length > 0) {
                let optionsListHtml = q.options.map(opt => `<div>- ${frappe.utils.escape_html(opt)}</div>`).join('');
                if (q.type_name === CHECKBOX_TYPE_NAME) {
                    if (q.qp_others) optionsListHtml += `<div>- <em>Otros</em></div>`;
                    if (q.qp_none_above) optionsListHtml += `<div>- <em>Ninguna de las anteriores</em></div>`;
                }
                optionsPreviewHtml = `
                    <div class="options-preview">
                        <strong>Opciones de respuesta</strong>
                        ${optionsListHtml}
                    </div>`;
            }
            // Preview para Likert (preferir opciones con url del backend; fallback a íconos por defecto)
            else if (q.type_name === LIKERT_TYPE_NAME) {
                const hasBackendOptions = Array.isArray(q.options) && q.options.length > 0;
                const list = hasBackendOptions
                    ? q.options
                    : DEFAULT_LIKERT_OPTIONS.map(({ text, value }) => ({ text, value, url: getLikertIconUrl(value) }));
                optionsPreviewHtml = `
                    <div class="options-preview">
                        <strong>Opciones de respuesta</strong>
                        ${list.map(opt => {
                            const safeUrl = frappe.utils.escape_html((opt && opt.url) ? opt.url : '');
                            const safeText = frappe.utils.escape_html((opt && opt.text) ? opt.text : '');
                            return `<div>
                                ${opt && opt.url ? `<img src="${safeUrl}" alt="" style="width:20px;height:20px;object-fit:contain;margin-right:6px;vertical-align:middle;">` : ''}
                                ${safeText}
                            </div>`;
                        }).join('')}
                    </div>`;
            }
            // Preview para Likert Visual (usar url por opción)
            else if (q.type_name === LIKERT_VISUAL_TYPE_NAME && Array.isArray(q.options) && q.options.length > 0) {
                optionsPreviewHtml = `
                    <div class="options-preview">
                        <strong>Opciones de respuesta</strong>
                        ${q.options.map(opt => {
                            const text = (opt && typeof opt === 'object') ? (opt.text || '') : String(opt || '');
                            const url = (opt && typeof opt === 'object') ? (opt.url || '') : '';
                            const safeUrl = frappe.utils.escape_html(url || '');
                            const safeText = frappe.utils.escape_html(text);
                            return `<div>
                                ${url ? `<img src="${safeUrl}" alt="" style="width:20px;height:20px;object-fit:contain;margin-right:6px;vertical-align:middle;">` : ''}
                                ${safeText}
                            </div>`;
                        }).join('')}
                    </div>`;
            }

            // Renderizado condicional del texto de la pregunta
            let questionTextHtml = `<p class="question-text">${frappe.utils.escape_html(q.text)}</p>`;
            
            // Si es liderazgo y tiene texto para otros, mostrar ambos
            if (this.isLeadershipMode && q.text_others) {
                 questionTextHtml = `
                    <div class="mb-1">
                        <strong class="text-muted small">Yo:</strong> <span class="question-text" style="font-size:0.85rem">${frappe.utils.escape_html(q.text)}</span>
                    </div>
                    <div>
                        <strong class="text-muted small">Otros:</strong> <span class="question-text small" style="font-size:0.85rem">${frappe.utils.escape_html(q.text_others)}</span>
                    </div>
                 `;
            }

            card.innerHTML = `
                <div class="bank-question-card-main">
                    <div class="add-icon ${isSelected ? 'selected' : ''}" title="${isSelected ? 'Quitar' : 'Agregar'}">
                        <i class="fa ${isSelected ? 'fa-check' : 'fa-check'}"></i>
                    </div>
                    <div class="card-content">
                        ${questionTextHtml}
                    </div>
                </div>
                ${optionsPreviewHtml}
                <div class="question-details">
                    <span class="category-tag">• Tag: ${frappe.utils.escape_html(q.demographic_name || 'General')}</span>
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
                
                // Texto de pregunta seleccionada
                let itemTextHtml = `<p class="item-text">${frappe.utils.escape_html(q.text)}</p>`;
                if (this.isLeadershipMode && q.text_others) {
                     itemTextHtml = `
                        <div class="item-text mb-2">
                            <div><strong class="text-muted small">Yo:</strong> ${frappe.utils.escape_html(q.text)}</div>
                            <div><strong class="text-muted small">Otros:</strong> ${frappe.utils.escape_html(q.text_others)}</div>
                        </div>
                     `;
                }

                item.innerHTML = `
                    <div class="item-number">${index + 1}</div>
                    <div class="item-content">
                        ${itemTextHtml}
                        <div class="item-details">
                            <span class="category-tag-selected">• ${frappe.utils.escape_html(q.demographic_name || 'General')}</span>
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
        if (this.isReadOnly) return;
        this.bankState.selectedIds.forEach(id => {
            if (!this.questions.some(mainQ => mainQ.id === id)) {
                const questionToAdd = this.bankState.questions.find(q => q.name === id);
                if (questionToAdd) {
                    let options = questionToAdd.options || [];
                    if (questionToAdd.type_name === LIKERT_TYPE_NAME) {
                        if (!Array.isArray(options) || options.length === 0) {
                            options = DEFAULT_LIKERT_OPTIONS.map(opt => ({
                                text: opt.text, value: opt.value, url: getLikertIconUrl(opt.value)
                            }));
                        }
                    }
                    this.questions.push({ 
                        id: questionToAdd.name,
                        text: questionToAdd.text,
                        text_others: questionToAdd.text_others,
                        type: questionToAdd.qn_type,
                        typeName: questionToAdd.type_name,
                        category_name: questionToAdd.category_name,
                        demographic: questionToAdd.demographic_name,
                        options: options,
                        qp_others: questionToAdd.qp_others || 0,
                        qp_none_above: questionToAdd.qp_none_above || 0
                    });
                }
            }
        });
        this.renderQuestions();
        this.closeModal();
    }

    resetAddQuestionForm() {
        const qf = this.ui.questionForm;

        if (!qf || !qf.text) return;

        qf.text.value = '';
        if (qf.textOthers) qf.textOthers.value = ''; // Resetear campo otros
        if (qf.type) qf.type.value = '';
        if (qf.demographic) qf.demographic.value = '';
        
        this._setEditableOptions();
        
        if (qf.negativeStatement) qf.negativeStatement.value = '';
        if (qf.positiveStatement) qf.positiveStatement.value = '';
        if (qf.npsMin) qf.npsMin.value = '';
        if (qf.npsMax) qf.npsMax.value = '';

        if (qf.optionsSection) qf.optionsSection.classList.add('d-none');
        if (qf.visualOptionsSection) {
            qf.visualOptionsSection.classList.add('d-none');
            if (qf.visualOptionsContainer) qf.visualOptionsContainer.innerHTML = `
                <div class="visual-option-input-row">
                    <span class="option-number">1</span>
                    <input type="text" class="form-control visual-option-value" placeholder="Valor (ej: 5)">
                    <input type="text" class="form-control visual-option-text" placeholder="Texto (ej: Excelente)">
                    <div class="visual-file-cell">
                        <input type="file" accept="image/*" class="visual-option-file">
                        <input type="hidden" class="visual-option-url-input" value="">
                        <div class="visual-file-preview d-none">
                            <img src="" alt="previsualización">
                            <span class="file-name small text-muted"></span>
                        </div>
                    </div>
                    <i class="fa fa-trash-o text-danger delete-visual-option" style="cursor: pointer;"></i>
                </div>`;
        }
        if (qf.bipolarSection) qf.bipolarSection.classList.add('d-none');
        if (qf.npsSection) qf.npsSection.classList.add('d-none');
        
        // Limpiar checkboxes extra si existen
        let togglesContainer = document.getElementById('checkbox-extra-toggles');
        if (togglesContainer) {
            togglesContainer.innerHTML = '';
            togglesContainer.classList.add('d-none');
        }

        [qf.text, qf.textOthers, qf.type, qf.demographic, qf.negativeStatement, qf.positiveStatement, qf.npsMin, qf.npsMax]
            .filter(Boolean)
            .forEach(field => this._clearValidationError(field));
    }

    validateQuestionForm() {
        if (this.isReadOnly) return false;
        let isValid = true;
        const qf = this.ui.questionForm;
        const selectedOption = qf.type.options[qf.type.selectedIndex];
        const questionTypeName = selectedOption ? selectedOption.text.trim() : '';

        [qf.text, qf.textOthers, qf.type, qf.negativeStatement, qf.positiveStatement, qf.npsMin, qf.npsMax].forEach(field => this._clearValidationError(field));

        if (!qf.text.value.trim()) {
            this._showValidationError(qf.text, 'Este campo es requerido.');
            isValid = false;
        }

        // Validación condicional para Liderazgo
        if (this.isLeadershipMode && qf.textOthers && !qf.textOthers.value.trim()) {
             this._showValidationError(qf.textOthers, 'Este campo es requerido para evaluaciones de Liderazgo.');
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

        // Validación para Likert Visual
        if (questionTypeName === LIKERT_VISUAL_TYPE_NAME) {
            const rows = Array.from(qf.visualOptionsContainer?.querySelectorAll('.visual-option-input-row') || []);
            const parsed = rows.map(row => ({
                value: row.querySelector('.visual-option-value')?.value.trim(),
                text: row.querySelector('.visual-option-text')?.value.trim(),
                url: row.querySelector('.visual-option-url-input')?.value.trim(),
            }));
            if (parsed.length < 1) {
                showGlobalNotification('Debes agregar al menos 1 opción visual.', 'error', 3000);
                isValid = false;
            }
            parsed.forEach((opt, i) => {
                if (!opt.value || !opt.text) {
                    showGlobalNotification(`La pregunta #${i + 1} debe incluir Valor y Texto.`, 'error', 3000);
                    isValid = false;
                }
            });
        }

        // Validación para opciones de texto (excluye Likert y Likert Visual)
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
        if (this.isReadOnly) return;
        const { optionsContainer } = this.ui.questionForm;
        if (!optionsContainer) return;
        const newRow = document.createElement('div');
        newRow.className = 'option-input-row';
        newRow.innerHTML = `<span class="option-number"></span><input type="text" class="form-control option-input" placeholder="Escribe tu opción aqui"><i class="fa fa-trash-o text-danger delete-option" style="cursor: pointer;"></i>`;
        optionsContainer.appendChild(newRow);
        this.updateOptionNumbers();
    }
    
    addManualQuestion() {
        if (this.isReadOnly) return;
        const qf = this.ui.questionForm;
        const questionTypeOption = qf.type.options[qf.type.selectedIndex];
        const questionTypeName = questionTypeOption ? questionTypeOption.text.trim() : '';

        if (!this.validateQuestionForm()) return;

        const newQuestion = { 
            id: `manual-${Date.now()}`, 
            text: qf.text.value.trim(), 
            text_others: this.isLeadershipMode && qf.textOthers ? qf.textOthers.value.trim() : null,
            type: qf.type.value, 
            typeName: questionTypeName, 
            demographic: qf.demographic.value.trim(),
            category_name: this.isLeadershipMode ? 'Liderazgo' : 'Manual' 
        };

        if (questionTypeName === LIKERT_TYPE_NAME) {
            newQuestion.options = DEFAULT_LIKERT_OPTIONS.map(opt => ({
                text: opt.text, value: opt.value, url: getLikertIconUrl(opt.value)
            }));
        } else if (OPTIONS_BASED_TYPES.includes(questionTypeName)) {
            newQuestion.options = Array.from(qf.optionsContainer.querySelectorAll('.option-input'))
                .map(input => input.value.trim()).filter(Boolean);
        } else if (questionTypeName === LIKERT_VISUAL_TYPE_NAME) {
            const rows = Array.from(qf.visualOptionsContainer?.querySelectorAll('.visual-option-input-row') || []);
            newQuestion.options = rows.map(row => ({
                value: row.querySelector('.visual-option-value')?.value.trim(),
                text: row.querySelector('.visual-option-text')?.value.trim(),
                url: row.querySelector('.visual-option-url-input')?.value.trim(),
            })).filter(opt => opt.value && opt.text);
        }

        if (NPS_SCALE_TYPES.includes(questionTypeName)) {
            newQuestion.nps_min = qf.npsMin.value;
            newQuestion.nps_max = qf.npsMax.value;
        }

        if (questionTypeName === CHECKBOX_TYPE_NAME) {
            newQuestion.qp_others = document.getElementById('chk_qp_others')?.checked ? 1 : 0;
            newQuestion.qp_none_above = document.getElementById('chk_qp_none_above')?.checked ? 1 : 0;
        }

        this.questions.push(newQuestion);
        this.renderQuestions();
        this.resetAddQuestionForm();
    }

    handleQuestionListActions(e) {
        if (this.isReadOnly) return;
        const questionItem = e.target.closest('.question-item');
        if (!questionItem) return;
        const index = parseInt(questionItem.getAttribute('data-index'), 10);
        if (e.target.classList.contains('delete-question')) {
            this.questions.splice(index, 1);
            this.renderQuestions();
        }
    }

    handleQuestionTypeChange() {
        if (this.isReadOnly) return;
        const qf = this.ui.questionForm;
        if (qf.type.value) this._clearValidationError(qf.type);
        
        const selectedOption = qf.type.options[qf.type.selectedIndex];
        const questionTypeName = selectedOption ? selectedOption.text.trim() : '';

        if (questionTypeName === LIKERT_TYPE_NAME) {
            this._setLikertOptions();
        } else if (OPTIONS_BASED_TYPES.includes(questionTypeName)) {
            this._setEditableOptions(questionTypeName);
        }

        if (qf.optionsSection) qf.optionsSection.classList.toggle('d-none', !OPTIONS_BASED_TYPES.includes(questionTypeName));
        if (qf.visualOptionsSection) qf.visualOptionsSection.classList.toggle('d-none', questionTypeName !== LIKERT_VISUAL_TYPE_NAME);
        if (qf.bipolarSection) qf.bipolarSection.classList.toggle('d-none', !BIPOLAR_SCALE_TYPES.includes(questionTypeName));
        if (qf.npsSection) qf.npsSection.classList.toggle('d-none', !NPS_SCALE_TYPES.includes(questionTypeName));
    }

    // Opciones de texto estándar
    handleOptionsActions(e) {
        if (this.isReadOnly) return;
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

    // Opciones Likert Visual
    addVisualOptionRow() {
        const { visualOptionsContainer } = this.ui.questionForm;
        if (!visualOptionsContainer) return;
        const row = document.createElement('div');
        row.className = 'visual-option-input-row';
        row.innerHTML = `
            <span class="option-number"></span>
            <input type="text" class="form-control visual-option-value" placeholder="Valor (ej: 4)">
            <input type="text" class="form-control visual-option-text" placeholder="Texto (ej: Bueno)">
            <div class="visual-file-cell">
                <input type="file" accept="image/*" class="visual-option-file">
                <input type="hidden" class="visual-option-url-input" value="">
                <div class="visual-file-preview d-none">
                    <img src="" alt="previsualización">
                    <span class="file-name small text-muted"></span>
                </div>
            </div>
            <i class="fa fa-trash-o text-danger delete-visual-option" style="cursor: pointer;"></i>`;
        visualOptionsContainer.appendChild(row);
        this.updateVisualOptionNumbers();
    }

    updateVisualOptionNumbers() {
        const { visualOptionsContainer } = this.ui.questionForm;
        if (!visualOptionsContainer) return;
        visualOptionsContainer.querySelectorAll('.visual-option-input-row').forEach((row, idx) => {
            const num = row.querySelector('.option-number');
            if (num) num.textContent = idx + 1;
        });
    }

    handleVisualOptionsActions(e) {
        if (this.isReadOnly) return;
        if (e.target.classList.contains('delete-visual-option')) {
            const { visualOptionsContainer } = this.ui.questionForm;
            const rows = visualOptionsContainer.querySelectorAll('.visual-option-input-row');
            if (rows.length > 1) {
                e.target.closest('.visual-option-input-row')?.remove();
                this.updateVisualOptionNumbers();
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
        DEFAULT_LIKERT_OPTIONS.forEach((opt, index) => {
            const row = document.createElement('div');
            row.className = 'option-input-row is-readonly';
            const iconUrl = frappe.utils.escape_html(getLikertIconUrl(opt.value));
            const text = frappe.utils.escape_html(opt.text);
            row.innerHTML = `
                <span class="option-number">${index + 1}</span>
                <div class="likert-option-display" style="display:flex;align-items:center;gap:8px;width:100%;">
                    <img src="${iconUrl}" alt="" style="width:20px;height:20px;object-fit:contain;">
                    <input type="text" class="form-control option-input" value="${text}" readonly data-value="${opt.value}">
                </div>
            `;
            optionsContainer.appendChild(row);
        });
        if (addOption) addOption.classList.add('d-none');
    }

    _setEditableOptions(questionTypeName) {
        const { optionsContainer, optionsSection } = this.ui.questionForm;
        const { addOption } = this.ui.buttons;
        if (!optionsContainer) return;

        optionsContainer.innerHTML = `<div class="option-input-row"><span class="option-number">1</span><input type="text" class="form-control option-input" placeholder="Escribe tu opción aqui"><i class="fa fa-trash-o text-danger delete-option" style="cursor: pointer;"></i></div>`;
        this.updateOptionNumbers();

        // Control dinámico de Checkbox Extra Options
        let togglesContainer = document.getElementById('checkbox-extra-toggles');
        if (!togglesContainer) {
            togglesContainer = document.createElement('div');
            togglesContainer.id = 'checkbox-extra-toggles';
            optionsSection.appendChild(togglesContainer);
        }

        if (questionTypeName === CHECKBOX_TYPE_NAME) {
            togglesContainer.innerHTML = `
                <div class="checkbox-extra-options mt-3 p-3" style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px;">
                    <div class="form-check mb-2">
                        <input type="checkbox" class="form-check-input" id="chk_qp_others">
                        <label class="form-check-label" for="chk_qp_others" style="font-size:0.85rem; font-weight:500;">Habilitar opción "Otros"</label>
                    </div>
                    <div class="form-check">
                        <input type="checkbox" class="form-check-input" id="chk_qp_none_above">
                        <label class="form-check-label" for="chk_qp_none_above" style="font-size:0.85rem; font-weight:500;">Habilitar opción "Ninguna de las anteriores"</label>
                    </div>
                </div>
            `;
            togglesContainer.classList.remove('d-none');
        } else {
            togglesContainer.innerHTML = '';
            togglesContainer.classList.add('d-none');
        }

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

    // Sube archivo y devuelve file_url
    async _uploadVisualOptionFile(file) {
        const formData = new FormData();
        formData.append('file', file, file.name);
        formData.append('is_private', 0);
        formData.append('from_form', 1);

        const res = await fetch('/api/method/upload_file', {
            method: 'POST',
            headers: { 'Accept': 'application/json', 'X-Frappe-CSRF-Token': frappe.csrf_token },
            body: formData
        });
        const json = await res.json();
        if (!res.ok || json.exc) {
            const msg = json._server_messages ? JSON.parse(json._server_messages)[0] : 'Error al subir archivo';
            throw new Error(msg);
        }

        const fileUrl = (json.message && (json.message.file_url || json.message.file_url)) || (json.message && json.message.file_url);
        return fileUrl || (json.message && json.message.file) || '';
    }

    _setVisualUploadingState(row, uploading) {
        const inputs = row.querySelectorAll('input');
        inputs.forEach(inp => inp.disabled = uploading);
        row.classList.toggle('is-uploading', uploading);
    }
}