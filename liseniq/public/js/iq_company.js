document.addEventListener("DOMContentLoaded", () => {
    const frmCompany = document.getElementById('frm-create-company');
    const btnSubmit = document.getElementById('btn-submit-company');

    // Variables para el archivo del logo
    let logoData = null;
    let logoName = null;

    const logoInput = document.getElementById('co_logo');
    const logoPreview = document.getElementById('logo-preview');
    
    // Lógica para previsualizar y convertir imagen a Base64
    if (logoInput) {
        logoInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            const nameDisplay = document.getElementById('co_logo-name-display');
            
            if (file) {
                logoName = file.name;
                
                // Actualizar el texto del label
                if (nameDisplay) {
                    nameDisplay.textContent = file.name;
                    nameDisplay.classList.add('has-file');
                }
                
                const reader = new FileReader();
                reader.onload = function(event) {
                    logoData = event.target.result;
                    logoPreview.style.display = 'block';
                    logoPreview.querySelector('img').src = logoData;
                };
                reader.readAsDataURL(file);
            } else {
                logoData = null;
                logoName = null;
                
                // Resetear el texto del label
                if (nameDisplay) {
                    nameDisplay.textContent = 'Adjuntar archivo';
                    nameDisplay.classList.remove('has-file');
                }
                
                logoPreview.style.display = 'none';
            }
        });
    }

    // Funciones de validación
    const showValidationError = (fieldId, message) => {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${fieldId}-error`);
        if (field) field.classList.add('is-invalid');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('d-none');
        }
    };

    const clearValidationError = (fieldId) => {
        const field = document.getElementById(fieldId);
        const errorElement = document.getElementById(`${fieldId}-error`);
        if (field) field.classList.remove('is-invalid');
        if (errorElement) {
            errorElement.classList.add('d-none');
        }
    };

    const clearAllValidations = () => {
        const fields = [
            'co_name', 'co_type_id', 'co_tax_id', 
            'co_admin_name', 'co_admin_email', 
            'co_id_document_type', 'co_id_document', 
            'co_accept_terms', 'co_accept_privacy_policy'
        ];
        fields.forEach(fieldId => clearValidationError(fieldId));
    };

    // Limpiar el error cuando el usuario empiece a escribir o seleccione algo nuevo
    const fieldsToListen = [
        'co_name', 'co_type_id', 'co_tax_id', 
        'co_admin_name', 'co_admin_email', 
        'co_id_document_type', 'co_id_document',
        'co_accept_terms', 'co_accept_privacy_policy'
    ];
    
    fieldsToListen.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', () => clearValidationError(fieldId));
            field.addEventListener('change', () => clearValidationError(fieldId));
        }
    });

    const validateForm = () => {
        let isValid = true;
        clearAllValidations();

        // Validar campos obligatorios de texto y select
        const requiredFields = [
            'co_name', 'co_type_id', 'co_tax_id', 
            'co_admin_name', 'co_admin_email', 
            'co_id_document_type', 'co_id_document'
        ];
        
        requiredFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field && (!field.value || !field.value.trim())) {
                showValidationError(fieldId, 'Este campo es obligatorio.');
                isValid = false;
            }
        });

        // Validar formato de correo
        const emailField = document.getElementById('co_admin_email');
        if (emailField && emailField.value.trim()) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(emailField.value.trim())) {
                showValidationError('co_admin_email', 'Por favor, introduce un formato de correo electrónico válido.');
                isValid = false;
            }
        }

        // Validar acuerdos legales
        const terms = document.getElementById('co_accept_terms');
        if (terms && !terms.checked) {
            showValidationError('co_accept_terms', 'Debes aceptar los Términos y Condiciones.');
            isValid = false;
        }

        const privacy = document.getElementById('co_accept_privacy_policy');
        if (privacy && !privacy.checked) {
            showValidationError('co_accept_privacy_policy', 'Debes aceptar las Políticas de Privacidad.');
            isValid = false;
        }

        return isValid;
    };

    if (frmCompany) {
        frmCompany.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Ejecutar validaciones
            if (!validateForm()) {
                showGlobalNotification("Por favor corrige los errores resaltados en el formulario.", "error");
                // Hacemos scroll al inicio para que el usuario vea los errores
                const scrollContainer = document.querySelector('.form-scroll-container');
                if (scrollContainer) scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
                return;
            }
            
            // 2. Recolectar datos
            const payload = {
                co_name: document.getElementById('co_name').value.trim(),
                co_type_id: document.getElementById('co_type_id').value,
                co_tax_id: document.getElementById('co_tax_id').value.trim(),
                co_sector: document.getElementById('co_sector').value,
                co_country: document.getElementById('co_country').value,
                co_headquarters: document.getElementById('co_headquarters').value.trim(),
                co_address: document.getElementById('co_address').value.trim(),
                co_company_size: document.getElementById('co_company_size').value,
                
                co_admin_name: document.getElementById('co_admin_name').value.trim(),
                co_id_document_type: document.getElementById('co_id_document_type').value, 
                co_id_document: document.getElementById('co_id_document').value.trim(),
                co_admin_phone: document.getElementById('co_admin_phone').value.trim(),
                co_admin_email: document.getElementById('co_admin_email').value.trim(),
                
                co_accept_terms: document.getElementById('co_accept_terms').checked ? 1 : 0,
                co_accept_privacy_policy: document.getElementById('co_accept_privacy_policy').checked ? 1 : 0,

                // Enviamos los datos del logo al Backend
                co_logo_data: logoData,
                co_logo_name: logoName
            };

            // UI de carga
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<i class="fa fa-spinner fa-spin mr-2"></i> Guardando...';

            // Llamada al Backend (Creará la Compañía y el Customer)
            frappe.call({
                method: 'liseniq.www.iq-config.new_company.create_new_company',
                args: {
                    data: JSON.stringify(payload)
                },
                callback: function(r) {
                    // Restaurar botón
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = '<i class="fa fa-save mr-2"></i> Guardar Compañía';
                    
                    if (!r.exc && r.message && r.message.status === 'success') {
                        showGlobalNotification(r.message.message, "success");
                        frmCompany.reset();
                        
                        // Reset visual del logo
                        const nameDisplay = document.getElementById('co_logo-name-display');
                        if(nameDisplay) {
                            nameDisplay.textContent = 'Adjuntar archivo';
                            nameDisplay.classList.remove('has-file');
                        }
                        if(logoPreview) logoPreview.style.display = 'none';

                        // Redirigir al home tras creación exitosa
                        setTimeout(() => {
                            window.location.href = "/iq-home";
                        }, 1500);
                    } else {
                        showGlobalNotification("Hubo un problema procesando la solicitud.", "error");
                    }
                },
                error: function(err) {
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = '<i class="fa fa-save mr-2"></i> Guardar Compañía';
                    showGlobalNotification("Error de conexión al crear compañía y cliente.", "error");
                }
            });
        });
    }
});

// Función centralizada para mostrar alertas globales de la app
function showGlobalNotification(message, type) {
    const notificationBar = document.getElementById('global-notification-bar');
    const notificationMessage = document.getElementById('global-notification-message');
    
    if (notificationBar && notificationMessage) {
        notificationBar.className = ''; // Limpiar clases
        notificationBar.classList.add('show', type === 'success' ? 'notification-success' : 'notification-error');
        notificationMessage.textContent = message;
        
        // Auto ocultar tras 3 segundos
        setTimeout(() => {
            notificationBar.classList.remove('show');
        }, 3500);
    } else {
        // Fallback básico
        alert(message);
    }
}