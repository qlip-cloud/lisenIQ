document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('identity-form');
    const docIdInput = document.getElementById('doc_id');
    const errorElement = document.getElementById('doc-id-error');
    const submitButton = document.getElementById('btn-submit');

    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (!token) {
        showError('No se encontró un token de encuesta válido en la URL.');
        submitButton.disabled = true;
        docIdInput.disabled = true;
        return;
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const docId = docIdInput.value.trim();

        if (!validateInput(docId)) {
            return;
        }

        submitButton.disabled = true;
        submitButton.textContent = 'Procesando...';

        // Guardar el doc_id en localStorage
        localStorage.setItem('liseniq_doc_id', docId);

        frappe.call({
            method: 'liseniq.utils.api_survey.get_survey_route_for_public_link',
            args: {
                token: token,
                dni: docId
            },
            callback: (r) => {
                if (r.message) {
                    if (r.message.is_leadership) {
                        // Renderiza el dashboard en la misma vista
                        showDashboard(r.message.evaluations, r.message.route);
                    } else if (r.message.route) {
                        // Redirección directa convencional
                        const surveyUrl = `${window.location.origin}/${r.message.route}?new=1&token=${token}`;
                        window.location.href = surveyUrl;
                    } else {
                        handleError('Ruta de encuesta no encontrada.');
                    }
                } else {
                    handleError(r.message || 'Ocurrió un error al procesar tu solicitud.');
                }
            },
            error: (r) => {
                let message = 'Ocurrió un error inesperado.';
                if (r.exc) {
                    try {
                        const exc_obj = JSON.parse(r.exc);
                        message = exc_obj[0] || message;
                    } catch (e) {
                        // Fallback for non-JSON error
                    }
                }
                handleError(message);
            }
        });
    });

    function handleError(msg) {
        showError(msg);
        submitButton.disabled = false;
        submitButton.textContent = 'Iniciar';
        localStorage.removeItem('liseniq_doc_id');
    }

    function validateInput(docId) {
        if (!docId) {
            showError('Por favor, ingresa tu documento de identidad.');
            return false;
        }
        if (!/^[a-zA-Z0-9]{1,20}$/.test(docId)) {
            showError('El documento solo puede contener letras y números (máximo 20 caracteres).');
            return false;
        }
        hideError();
        return true;
    }

    function showError(message) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        docIdInput.classList.add('is-invalid');
    }

    function hideError() {
        errorElement.style.display = 'none';
        docIdInput.classList.remove('is-invalid');
    }

    function showDashboard(evaluations, route) {
        const formGroup = document.querySelector('.iq-register-form-group');
        const actionCenter = document.querySelector('.iq-register-form-action-center');
        const dashboardContainer = document.getElementById('dashboard-container');
        const listContainer = document.getElementById('evaluations-list');
        const mainTitle = document.querySelector('.iq-register-main-title');

        // Ocultar la sección del formulario inicial
        if (formGroup) formGroup.style.display = 'none';
        if (actionCenter) actionCenter.style.setProperty('display', 'none', 'important');
        
        // Restablecer el botón y ocultarlo por seguridad
        if (submitButton) {
            submitButton.style.display = 'none';
            submitButton.disabled = false;
            submitButton.textContent = 'Iniciar';
        }
        
        hideError();

        if (mainTitle) {
            mainTitle.textContent = 'Tus Evaluaciones Pendientes';
        }

        // Poblar la lista de evaluaciones dinámicamente
        listContainer.innerHTML = '';
        evaluations.forEach(ev => {
            const card = document.createElement('div');
            card.className = 'evaluation-card';
            card.innerHTML = `
                <div class="evaluation-info">
                    <span class="evaluation-role">${ev.is_auto ? 'Autoevaluación' : (ev.role || 'Evaluación')}</span>
                    <span class="evaluation-name">${ev.is_auto ? `Tú mismo (${ev.evaluatee_name})` : ev.evaluatee_name}</span>
                </div>
                <div class="evaluation-action">
                    Evaluar <span style="font-size: 18px; line-height: 1; padding-bottom: 2px;">&rarr;</span>
                </div>
            `;
            card.addEventListener('click', () => {
                // Navegar usando el token específico (rid) de esta evaluación
                const surveyUrl = `${window.location.origin}/${route}?new=1&token=${ev.token}`;
                window.location.href = surveyUrl;
            });
            listContainer.appendChild(card);
        });

        // Mostrar contenedor
        dashboardContainer.style.display = 'block';
    }
});