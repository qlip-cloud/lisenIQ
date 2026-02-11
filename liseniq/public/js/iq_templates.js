import { Stepper } from './utils/stepper.js';
import { QuestionBuilder } from './question_builder.js';

document.addEventListener('DOMContentLoaded', function () {

    if (!document.getElementById('template-stepper-container')) {
        return;
    }

    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');

    const btnStep1 = document.getElementById('btn-step-1');
    const btnBackStep2 = document.getElementById('btn-back-step-2');
    const btnStep2 = document.getElementById('btn-step-2');
    const btnBackStep3 = document.getElementById('btn-back-step-3');
    const btnSaveTemplate = document.getElementById('btn-save-template');
    
    const formStep1 = {
        name: document.getElementById('template_name_input'),
        category: document.getElementById('template_category_input'),
        description: document.getElementById('template_description_input'),
        image: document.getElementById('template_image_input'),
        isPrivate: document.getElementById('template_is_private_input'),
        isPublic: document.getElementById('template_is_public_input')
    };

    const wizardDataEl = document.getElementById('template-wizard-data');
    const userCompany = wizardDataEl ? wizardDataEl.dataset.userCompany : null;

    const templateNameBreadcrumb = document.getElementById('template_name_breadcrumb');
    const templateNameBreadcrumbRev = document.getElementById('template_name_breadcrumb_rev');
    
    const imageInput = document.getElementById('template_image_input');
    const fileNameDisplay = document.getElementById('file-name-display');

    const reviewElements = {
        name: document.getElementById('review_template_name'),
        description: document.getElementById('review_template_description'),
        category: document.getElementById('review_template_category'),
        questionsCount: document.getElementById('review_questions_count'),
        questionsList: document.getElementById('review-questions-list-review')
    };

    const templateStepper = new Stepper('template-stepper-container', ['Nombre', 'Preguntas', 'Revisión']);
    
    const questionBuilder = new QuestionBuilder((questions) => {
        if (btnStep2) btnStep2.disabled = questions.length === 0;
    });

    function showStep(stepNumber) {
        step1.classList.toggle('d-none', stepNumber !== 1);
        step2.classList.toggle('d-none', stepNumber !== 2);
        step3.classList.toggle('d-none', stepNumber !== 3);
        templateStepper.update(stepNumber);
    }
    
    const showValidationError = (fieldId, message) => {
        const field = document.getElementById(fieldId);
        if (!field) return;
        const errorElement = document.getElementById(`${fieldId.replace('_input', '_error')}`);
        field.classList.add('is-invalid');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
    };

    const clearValidationError = (fieldId) => {
        const field = document.getElementById(fieldId);
        if (!field) return;
        const errorElement = document.getElementById(`${field.id.replace('_input', '_error')}`);
        field.classList.remove('is-invalid');
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    };

    const validateStep1 = async () => {
        let isValid = true;
        const templateNameField = formStep1.name;

        step1.querySelectorAll('[data-required="true"]').forEach(field => clearValidationError(field.id));
        step1.querySelectorAll('[data-required="true"]').forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                showValidationError(field.id, 'Este campo es obligatorio.');
            }
        });

        if (isValid && templateNameField.value.trim()) {
            btnStep1.disabled = true;
            btnStep1.innerHTML = `<i class="fa fa-spinner fa-spin"></i> Validando...`;
            try {
                const response = await frappe.call({
                    method: 'liseniq.www.iq-templates.new_template.check_template_name',
                    args: { name: templateNameField.value.trim() }
                });

                if (response.message.exists) {
                    showValidationError(templateNameField.id, 'Ya existe una plantilla con este nombre.');
                    isValid = false;
                }
            } catch (error) {
                console.error("Error al validar el nombre de la plantilla:", error);
                showValidationError(templateNameField.id, 'No se pudo validar el nombre. Intente de nuevo.');
                isValid = false;
            } finally {
                btnStep1.disabled = false;
                btnStep1.textContent = 'Siguiente';
            }
        }

        return isValid;
    };

    function renderReviewStep() {
        reviewElements.name.textContent = formStep1.name.value.trim();
        reviewElements.description.textContent = formStep1.description.value.trim();
        const selectedCategoryOption = formStep1.category.options[formStep1.category.selectedIndex];
        reviewElements.category.textContent = selectedCategoryOption ? selectedCategoryOption.text : 'N/A';
        
        const questions = questionBuilder.getQuestions();
        reviewElements.questionsCount.textContent = questions.length;
        reviewElements.questionsList.innerHTML = '';

        if (questions.length === 0) {
            reviewElements.questionsList.innerHTML = `<div class="text-center text-muted p-4">No se han añadido preguntas a esta plantilla.</div>`;
        } else {
            questions.forEach((question, index) => {
                const questionReviewItem = document.createElement('div');
                questionReviewItem.className = 'review-question-item';
                
                const questionDisplayName = question.typeName || question.type;
                let optionsHtml = '';

                if (question.options && question.options.length > 0) {
                    optionsHtml = `<div class="review-question-options">
                        ${question.options.map(opt => {
                            if (typeof opt === 'object' && (opt.url || opt.text)) {
                                const url = opt.url ? `<img src="${frappe.utils.escape_html(opt.url)}" alt="" style="width:20px;height:20px;object-fit:contain;margin-right:6px;">` : '';
                                const text = opt.text || '';
                                return `<div class="review-question-option">${url}${frappe.utils.escape_html(text)}</div>`;
                            }
                            const optionText = (typeof opt === 'object' && opt.text) ? opt.text : opt;
                            return `<div class="review-question-option">${frappe.utils.escape_html(optionText)}</div>`;
                        }).join('')}
                    </div>`;
                }
                
                // Mostrar ambos enunciados si existen
                let statementsHtml = `<p class="review-question-text">${frappe.utils.escape_html(question.text)}</p>`;
                if (question.text_others) {
                    statementsHtml = `
                        <div class="mb-2">
                             <p class="review-question-text mb-1"><strong class="text-muted small">Yo:</strong> ${frappe.utils.escape_html(question.text)}</p>
                             <p class="review-question-text"><strong class="text-muted small">Otros:</strong> ${frappe.utils.escape_html(question.text_others)}</p>
                        </div>
                    `;
                }

                questionReviewItem.innerHTML = `
                    <div class="review-question-header">
                        <span class="review-question-number">${index + 1}</span>
                        ${statementsHtml}
                    </div>
                    <div class="review-question-details">
                        <span>Tipo: ${frappe.utils.escape_html(questionDisplayName)}</span>
                        <div>
                            <span class="review-question-tag">Tag: ${frappe.utils.escape_html(question.demographic || 'General')}</span>
                        </div>
                    </div>
                    ${optionsHtml}
                `;
                reviewElements.questionsList.appendChild(questionReviewItem);
            });
        }
    }

    async function handleSaveTemplate() {
        btnSaveTemplate.disabled = true;
        btnSaveTemplate.innerHTML = `<i class="fa fa-spinner fa-spin"></i> Creando...`;

        try {
            const questions = questionBuilder.getQuestions();
            const newQuestionNames = [];
            const manualQuestions = questions.filter(q => q.id.startsWith('manual-'));

            for (const q of manualQuestions) {
                const questionDoc = {
                    qn_statement: q.text,
                    qn_statement_others: q.text_others || null,
                    qn_type: q.type,
                    qn_category: formStep1.category.value,
                    qn_status: 'Activa',
                    qn_negative_statement: q.negative_statement || null,
                    qn_positive_statement: q.positive_statement || null,
                    qn_nps_min: q.nps_min,
                    qn_nps_max: q.nps_max,
                    qn_demographic: q.demographic,
                };
                if (q.options) {
                    if (q.typeName === 'Likert') {
                        questionDoc.qn_response_options = q.options.map(opt => ({
                            qo_option_text: opt.text,
                            qo_option_value: opt.value,
                            qo_url: opt.url
                        }));
                    } else if (q.typeName === 'Likert Visual') {
                        questionDoc.qn_response_options = q.options.map(opt => ({
                            qo_option_text: opt.text,
                            qo_option_value: opt.value,
                            qo_url: opt.url
                        }));
                    } else {
                        questionDoc.qn_response_options = q.options.map(opt => ({
                            qo_option_text: opt,
                            qo_option_value: opt
                        }));
                    }
                }
                
                const result = await frappe.call({
                    method: 'liseniq.www.iq-templates.index.create_question_from_template_wizard',
                    args: { question_data: JSON.stringify(questionDoc) }
                });
                
                if (result.message) {
                    newQuestionNames.push(result.message);
                }
            }

            const bankQuestionNames = questions.filter(q => !q.id.startsWith('manual-')).map(q => q.id);
            const allQuestionNames = [...newQuestionNames, ...bankQuestionNames];

            const isPrivate = formStep1.isPrivate?.checked;
            const hiddenPublic = document.getElementById('tp_is_public_value');
            const isPublic = formStep1.isPublic?.checked ? 1 : (hiddenPublic && hiddenPublic.value === '1' ? 1 : 0);

            const templateDoc = {
                doctype: 'qp_IQ_Template',
                tp_name: formStep1.name.value.trim(),
                tp_category: formStep1.category.value,
                tp_description: formStep1.description.value.trim(),
                tp_status: 'Borrador',
                tp_is_private: isPublic ? 0 : (isPrivate ? 1 : 0),
                tp_is_public: isPublic,
                tp_owner: frappe.session.user,
                custom_company: userCompany,
                tp_questions: allQuestionNames.map(q_name => ({ doctype: 'qp_IQ_TemplateQuestion', tq_question: q_name }))
            };

            const templateInsertResponse = await frappe.call({ method: 'frappe.client.insert', args: { doc: templateDoc } });
            const newTemplateName = templateInsertResponse.message.name;

            const imageFile = imageInput.files[0];
            if (imageFile) {
                const formData = new FormData();
                formData.append('file', imageFile, imageFile.name);
                formData.append('doctype', 'qp_IQ_Template');
                formData.append('docname', newTemplateName);
                formData.append('fieldname', 'tp_logo');
                formData.append('is_private', 0);
                formData.append('from_form', 1);

                const response = await fetch('/api/method/upload_file', {
                    method: 'POST',
                    headers: { 'Accept': 'application/json', 'X-Frappe-CSRF-Token': frappe.csrf_token },
                    body: formData,
                });
                const result = await response.json();
                if (!response.ok || result.exc) throw new Error(result._server_messages ? JSON.parse(result._server_messages)[0] : 'La subida del archivo falló.');
            }

            // Si la plantilla es pública, marcar sus preguntas como públicas
            if (isPublic) {
                await frappe.call({
                    method: 'liseniq.www.iq-templates.index.mark_template_questions_public',
                    args: { template_name: newTemplateName }
                });
            }

            showGlobalNotification('Se ha creado la Plantilla', 'success');
            setTimeout(() => { window.location.href = '/iq-templates'; }, 2000);

        } catch (err) {
            console.error("Error al guardar la plantilla:", err);
            showGlobalNotification('Ocurrio un error al crear la Plantilla, intente nuevamente.', 'error');
            btnSaveTemplate.disabled = false;
            btnSaveTemplate.textContent = 'Crear';
        }
    }

    function initializeEventListeners() {
        btnStep1?.addEventListener('click', async () => {
            if (await validateStep1()) {
                const templateName = formStep1.name.value.trim();
                templateNameBreadcrumb.textContent = templateName;
                if (templateNameBreadcrumbRev) templateNameBreadcrumbRev.textContent = templateName;
                
                // Configurar QuestionBuilder según categoría seleccionada
                const selectedCategoryOption = formStep1.category.options[formStep1.category.selectedIndex];
                const categoryText = selectedCategoryOption ? selectedCategoryOption.text.trim() : '';
                questionBuilder.setCategory(categoryText);

                showStep(2);
            }
        });

        btnBackStep2?.addEventListener('click', () => showStep(1));
        btnStep2?.addEventListener('click', () => { renderReviewStep(); showStep(3); });
        btnBackStep3?.addEventListener('click', () => showStep(2));
        btnSaveTemplate?.addEventListener('click', handleSaveTemplate);

        step1.querySelectorAll('[data-required="true"]').forEach(field => {
            field.addEventListener('input', () => clearValidationError(field.id));
        });

        imageInput?.addEventListener('change', () => {
            fileNameDisplay.textContent = imageInput.files.length > 0 ? imageInput.files[0].name : 'Adjuntar archivo';
            fileNameDisplay.classList.toggle('has-file', imageInput.files.length > 0);
        });
        
        const chkPrivate = formStep1.isPrivate;
        const chkPublic = formStep1.isPublic;
        const hiddenPublic = document.getElementById('tp_is_public_value');
        const privateWarning = document.getElementById('private_template_warning');

        const syncPublicFlag = () => {
            if (hiddenPublic) hiddenPublic.value = (chkPublic && chkPublic.checked) ? '1' : '0';
        };

        const togglePrivateWarning = () => {
            if (privateWarning) {
                if (!chkPrivate.checked) {
                    privateWarning.classList.remove('d-none');
                } else {
                    privateWarning.classList.add('d-none');
                }
            }
        };

        if (chkPublic) {
            chkPublic.addEventListener('change', () => {
                if (chkPublic.checked && chkPrivate) {
                    chkPrivate.checked = false;
                    togglePrivateWarning();
                }
                syncPublicFlag();
            });
        }
        if (chkPrivate) {
            chkPrivate.addEventListener('change', () => {
                if (chkPrivate.checked && chkPublic) chkPublic.checked = false;
                syncPublicFlag();
                togglePrivateWarning();
            });
        }
        
        syncPublicFlag();
        togglePrivateWarning(); // Inicializa el estado basado en el HTML por defecto
    }
    
    function init() {
        templateStepper.render();
        showStep(1);
        initializeEventListeners();
    }

    init();
});