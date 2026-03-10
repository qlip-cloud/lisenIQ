document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('identity-form');
    const docIdInput = document.getElementById('doc_id');
    const errorElement = document.getElementById('doc-id-error');
    const submitButton = document.getElementById('btn-submit');

    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (!token) {
        showError('No se encontró un token de encuesta válido en la URL.');
        if (submitButton) submitButton.disabled = true;
        if (docIdInput) docIdInput.disabled = true;
        return;
    }

    // Al cargar la página, verificamos si el token tiene información suficiente
    // para saltarnos el paso del DNI (ej. enlace personalizado de Liderazgo)
    frappe.call({
        method: 'liseniq.utils.api_survey.get_survey_route_for_public_link',
        args: {
            token: token,
            dni: ''
        },
        callback: (r) => {
            if (r.message) {
                if (r.message.error) {
                    showError(r.message.error);
                    if (submitButton) submitButton.disabled = true;
                    if (docIdInput) docIdInput.disabled = true;
                } else if (r.message.is_completed) {
                    showDashboardMessage(r.message.message);
                } else if (r.message.is_leadership && r.message.evaluations) {
                    // Es un token que ya identifica al evaluador, mostramos dashboard
                    showDashboard(r.message.evaluations, r.message.route);
                } else if (r.message.require_dni) {
                    // Requiere DNI, se mantiene el formulario visible para que el usuario proceda
                } else if (r.message.route && r.message.has_rid) {
                    // Es un enlace personalizado normal (no 360). Podemos saltarnos el formulario de DNI y redirigir
                    const surveyUrl = `${window.location.origin}/${r.message.route}?new=1&token=${token}`;
                    window.location.href = surveyUrl;
                }
            }
        },
        error: (r) => {
            let message = 'Ocurrió un error inesperado.';
            if (r.exc) {
                try {
                    const exc_obj = JSON.parse(r.exc);
                    if (exc_obj._server_messages) {
                        const msgs = JSON.parse(exc_obj._server_messages);
                        message = msgs[0].message || message;
                    }
                } catch (e) { }
            }
            // Si ocurre un error de expiración o similar en la carga inicial, lo mostramos
            showError(message);
            if (submitButton) submitButton.disabled = true;
            if (docIdInput) docIdInput.disabled = true;
        }
    });

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
                    if (r.message.error) {
                        handleError(r.message.error);
                    } else if (r.message.is_completed) {
                        showDashboardMessage(r.message.message);
                    } else if (r.message.is_leadership && r.message.evaluations) {
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
                        if (exc_obj._server_messages) {
                            const msgs = JSON.parse(exc_obj._server_messages);
                            message = msgs[0].message || message;
                        }
                    } catch (e) {}
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

    function showDashboardMessage(msg) {
        const formGroup = document.querySelector('.iq-register-form-group');
        const actionCenter = document.querySelector('.iq-register-form-action-center');
        const dashboardContainer = document.getElementById('dashboard-container');
        const listContainer = document.getElementById('evaluations-list');
        const mainTitle = document.querySelector('.iq-register-main-title');

        if (formGroup) formGroup.style.display = 'none';
        if (actionCenter) actionCenter.style.setProperty('display', 'none', 'important');
        if (submitButton) {
            submitButton.style.display = 'none';
        }
        hideError();

        if (mainTitle) {
            mainTitle.textContent = 'Medición Finalizada';
        }

        listContainer.innerHTML = `<div class="alert alert-success text-center" style="font-size: 15px; margin-top: 10px;">${msg}</div>`;
        dashboardContainer.style.display = 'block';
    }
});