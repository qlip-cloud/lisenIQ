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
                token: token
            },
            callback: (r) => {
                if (r.message && r.message.route) {
                    const surveyUrl = `${window.location.origin}/${r.message.route}?new=1&token=${token}`;
                    window.location.href = surveyUrl;
                } else {
                    showError(r.message || 'Ocurrió un error al procesar tu solicitud.');
                    submitButton.disabled = false;
                    submitButton.textContent = 'Iniciar';
                    localStorage.removeItem('liseniq_doc_id'); // Limpiar en caso de error
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
                showError(message);
                submitButton.disabled = false;
                submitButton.textContent = 'Iniciar';
                localStorage.removeItem('liseniq_doc_id'); // Limpiar en caso de error
            }
        });
    });

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
});
