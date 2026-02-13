document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('register-form');
    const firstNameInput = document.getElementById('first_name');
    const lastNameInput = document.getElementById('last_name');
    const emailInput = document.getElementById('email');
    const companyInput = document.getElementById('company_name');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const termsCheckbox = document.getElementById('terms-and-conditions-checkbox');
    const errorElement = document.getElementById('general-error');
    const submitButton = document.getElementById('btn-submit');
    submitButton.disabled = true; // Deshabilitar el botón hasta que se complete la validación

    firstNameInput.addEventListener('blur', function() {
      const fistNameErrorElement = document.getElementById('first-name-error');
        if (this.value.trim() === '') {
            this.classList.add('input-error');
              showError(fistNameErrorElement, 'El nombre es obligatorio.');
        } else {
            this.classList.remove('input-error');
            fistNameErrorElement.style.display = 'none';
        }
        validateForm();
    });

    lastNameInput.addEventListener('blur', function() {
      const lastNameErrorElement = document.getElementById('last-name-error');
        if (this.value.trim() === '') {
            this.classList.add('input-error');
              showError(lastNameErrorElement, 'El apellido es obligatorio.');
        } else {
            this.classList.remove('input-error');
            lastNameErrorElement.style.display = 'none';
        }
        validateForm();
    });

    emailInput.addEventListener('blur', function() {
        const emailErrorElement = document.getElementById('email-error'); 
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailPattern.test(this.value.trim())) {
            this.classList.add('input-error');
              showError(emailErrorElement, 'Por favor, ingresa un correo electrónico válido.');
        } else {
            this.classList.remove('input-error');
            emailErrorElement.style.display = 'none';
        }
        validateForm();
    });

    companyInput.addEventListener('blur', function() {
        const companyErrorElement = document.getElementById('company-error');
        if (this.value.trim() === '') {
            this.classList.add('input-error');
              showError(companyErrorElement, 'El nombre de la empresa es obligatorio.');
        } else {
            this.classList.remove('input-error');
            companyErrorElement.style.display = 'none';
        }
        validateForm();
    });

    passwordInput.addEventListener('input', function() {
        const passwordErrorElement = document.getElementById('password-error');
        const regex = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/; // Al menos 8 caracteres, una letra y un número
        if (!regex.test(this.value)) {
            this.classList.add('input-error');
              showError(passwordErrorElement, 'La contraseña debe tener al menos 8 caracteres, incluyendo una letra y un número.');
        } else {
            this.classList.remove('input-error');
            passwordErrorElement.style.display = 'none';
        }
        validateForm();
    });

      passwordInput.addEventListener('blur', function() {
        const passwordErrorElement = document.getElementById('password-error');
        if (this.value.length < 8) {
            this.classList.add('input-error');
              showError(passwordErrorElement, 'La contraseña debe tener al menos 8 caracteres.');
        } else {
            this.classList.remove('input-error');
            passwordErrorElement.style.display = 'none';
        }
        validateForm();
    });

    confirmPasswordInput.addEventListener('blur', function() {
        const confirmPasswordErrorElement = document.getElementById('confirm-password-error');
        if (this.value !== passwordInput.value) {
            this.classList.add('input-error');
              showError(confirmPasswordErrorElement, 'Las contraseñas no coinciden.');
        } else {
            this.classList.remove('input-error');
            confirmPasswordErrorElement.style.display = 'none';
        }
        validateForm();
    });
    
    termsCheckbox.addEventListener('change', function() {
        validateForm();
    });

    // Funcionalidad para mostrar/ocultar contraseñas
    const passwordToggleIcons = document.querySelectorAll('.input-icon-div');
    
    passwordToggleIcons.forEach((iconDiv) => {
        iconDiv.addEventListener('click', function() {
            const passwordField = this.previousElementSibling;
            const visibilityIcon = this.querySelector('.material-symbols-outlined:nth-child(1)');
            const visibilityOffIcon = this.querySelector('.material-symbols-outlined:nth-child(2)');
            
            if (passwordField.type === 'password') {
                passwordField.type = 'text';
                visibilityIcon.style.display = 'none';
                visibilityOffIcon.style.display = 'block';
            } else {
                passwordField.type = 'password';
                visibilityIcon.style.display = 'block';
                visibilityOffIcon.style.display = 'none';
            }
        });
    });

    form.addEventListener('submit', function(event) {
        event.preventDefault();
        submitButton.disabled = true;
        submitButton.textContent = 'Registrando...';

        const formData = {
            first_name: firstNameInput.value.trim(),
            last_name: lastNameInput.value.trim(),
            email: emailInput.value.trim(),
            company_name: companyInput.value.trim(),
            password: passwordInput.value,
            accept_terms: termsCheckbox.checked
        };

        frappe.call({
            method: 'liseniq.www.iq-user-register.index.register_user',
            args: formData,
            callback: (r) => {
                if (r.message && r.message.status === 'success') {
                    // Registro exitoso - Mostrar mensaje y opción de volver
                    showSuccessMessage();
                } else if (r.message && r.message.status === 'error') {
                    // Error conocido del servidor
                    showError(errorElement, r.message.message || 'Ocurrió un error al procesar tu solicitud.');
                    submitButton.disabled = false;
                    submitButton.textContent = 'Registrar';
                } else {
                    // Respuesta inesperada
                    showError(errorElement, 'Ocurrió un error inesperado.');
                    submitButton.disabled = false;
                    submitButton.textContent = 'Registrar';
                }
            },
            error: (r) => {
                let message = 'Ocurrió un error inesperado.';
                
                // Intentar parsear _server_messages
                if (r._server_messages) {
                    try {
                        const messages = JSON.parse(r._server_messages);
                        if (messages && messages.length > 0) {
                            const firstMsg = JSON.parse(messages[0]);
                            message = firstMsg.message || message;
                        }
                    } catch (e) {
                        console.error('Error parsing server messages:', e);
                    }
                }
                
                // Si hay exc, intentar parsearlo
                if (r.exc && !r._server_messages) {
                    try {
                        const exc_obj = JSON.parse(r.exc);
                        if (exc_obj.message) {
                            message = exc_obj.message;
                        }
                    } catch (e) {
                        console.error('Error parsing exception:', e);
                    }
                }
                
                showError(errorElement, message);
                submitButton.disabled = false;
                submitButton.textContent = 'Registrar';
            }
        });
    });
    
    function showError(errorElement, message) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }

    function showSuccessMessage() {
        // Ocultar el formulario
        form.style.display = 'none';
        
        // Crear o mostrar el mensaje de éxito
        let successContainer = document.getElementById('success-message-container');
        if (!successContainer) {
            successContainer = document.createElement('div');
            successContainer.id = 'success-message-container';
            successContainer.style.cssText = 'text-align: center; padding: 40px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center;';
            
            const successIcon = document.createElement('div');
            successIcon.innerHTML = '<span class="material-symbols-outlined" style="font-size: 64px; color: #4CAF50;">check_circle</span>';
            
            const successTitle = document.createElement('h2');
            successTitle.textContent = '¡Registro exitoso!';
            successTitle.style.cssText = 'color: #4CAF50; margin: 20px 0;';
            
            const successMessage = document.createElement('p');
            successMessage.textContent = 'Se ha enviado un correo electrónico de confirmación a tu dirección de email.';
            successMessage.style.cssText = 'font-size: 16px; margin: 20px 0; color: #666;';
            
            const backButton = document.createElement('button');
            backButton.textContent = 'Volver al formulario';
            backButton.className = 'btn btn-primary';
            backButton.style.cssText = 'margin-top: 20px; padding: 10px 30px; cursor: pointer; color: #6c2fff !important; background: #fff !important; font-size: 18px !important; font-family: "Rubik", sans-serif !important; font-weight: 500 !important; border: 2px solid #6c2fff !important; border-radius: 8px !important; padding: 14px 48px !important; cursor: pointer !important; transition: background 0.2s !important; text-align: center !important;';
            backButton.onclick = resetForm;

            const loginButton = document.createElement('button');
            loginButton.textContent = 'Ir a Iniciar Sesión';
            loginButton.className = 'btn btn-secondary';
            loginButton.style.cssText = 'margin-top: 20px; margin-left: 10px; padding: 10px 30px; cursor: pointer; background: #6c2fff !important; color: #fff !important; font-size: 18px !important; font-family: "Rubik", sans-serif !important; font-weight: 500 !important; border: none !important; border-radius: 8px !important; padding: 14px 48px !important; cursor: pointer !important; transition: background 0.2s !important; text-align: center !important; display: inline-block !important;';
            loginButton.onclick = function() {
                window.location.href = '/login'; 
            };
            successContainer.appendChild(successIcon);
            successContainer.appendChild(successTitle);
            successContainer.appendChild(successMessage);
            successContainer.appendChild(backButton);
            successContainer.appendChild(loginButton);
            
            form.parentElement.insertBefore(successContainer, form);
        } else {
            successContainer.style.display = 'block';
        }
    }

    function resetForm() {
        // Limpiar todos los campos
        firstNameInput.value = '';
        lastNameInput.value = '';
        emailInput.value = '';
        companyInput.value = '';
        passwordInput.value = '';
        confirmPasswordInput.value = '';
        termsCheckbox.checked = false;
        
        // Remover errores
        document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
        document.querySelectorAll('[id$="-error"]').forEach(el => el.style.display = 'none');
        
        // Ocultar mensaje de éxito
        const successContainer = document.getElementById('success-message-container');
        if (successContainer) {
            successContainer.style.display = 'none';
        }
        
        // Mostrar formulario
        form.style.display = 'block';
        
        // Restablecer botón
        submitButton.disabled = true;
        submitButton.textContent = 'Registrar';
    }

    function validateForm() {
        const isFirstNameValid = firstNameInput.value.trim() !== '';
        const isLastNameValid = lastNameInput.value.trim() !== '';
        const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailInput.value.trim());
        const isCompanyValid = companyInput.value.trim() !== '';
        const isPasswordValid = passwordInput.value.length >= 8;
        const isConfirmPasswordValid = confirmPasswordInput.value === passwordInput.value && confirmPasswordInput.value !== '';
        const isTermsChecked = termsCheckbox.checked;

        const isFormValid = isFirstNameValid && isLastNameValid && isEmailValid && 
                           isCompanyValid && isPasswordValid && isConfirmPasswordValid && isTermsChecked;

        submitButton.disabled = !isFormValid;
    }

});