const initIqConfig = () => {
    // Variables de Estado de Notificaciones
    let currentCompany = null;
    let selectedEmail = null;

    const openModal = (modalElement) => {
        if (modalElement) {
            modalElement.classList.remove('d-none');
            document.body.style.overflow = 'hidden';
        }
    };

    const closeModal = (modalElement) => {
        if (modalElement) {
            modalElement.classList.add('d-none');
            document.body.style.overflow = '';
        }
    };

    const showModalMessage = (message, type) => {
        const notificationsMessageBox = document.getElementById('notifications-message-box');
        if(notificationsMessageBox) {
            notificationsMessageBox.className = `mt-3 alert-message ${type}`;
            notificationsMessageBox.textContent = message;
            notificationsMessageBox.classList.remove('d-none');
            
            setTimeout(() => {
                notificationsMessageBox.classList.add('d-none');
            }, 3500);
        }
    };

    // Al usar 'delegación' recuperamos los elementos del DOM en tiempo real cuando ocurre el clic.
    if (!window.iqConfigEventsBound) {
        document.addEventListener('click', (e) => {
            // Tarjeta Notificaciones
            if (e.target.closest('#btn-notifications')) {
                const modal = document.getElementById('notifications-modal');
                if (modal) {
                    openModal(modal);
                    loadEmailAccounts(); 
                }
                return;
            }

            // Tarjeta Gestión de Compañías
            if (e.target.closest('#btn-manage-companies')) {
                const modal = document.getElementById('manage-company-modal');
                if (modal) openModal(modal);
                return;
            }

            // Acciones del Modal de Compañías
            if (e.target.closest('#btn-create-company')) {
                window.location.href = '/iq-config/new_company';
                return;
            }
            if (e.target.closest('#btn-edit-company')) {
                console.log('Opción de editar compañía en desarrollo.');
                return;
            }
            if (e.target.closest('#btn-close-company-modal') || e.target.id === 'manage-company-modal') {
                closeModal(document.getElementById('manage-company-modal'));
                return;
            }

            // Acciones del Modal de Notificaciones
            if (e.target.closest('#btn-close-notifications-modal') || e.target.closest('#btn-cancel-notifications') || e.target.id === 'notifications-modal') {
                closeModal(document.getElementById('notifications-modal'));
                return;
            }

            // 5. Selección y Autoguardado de Notificaciones al cambiar el Radio
            const emailOption = e.target.closest('.email-option');
            if (emailOption) {
                const radio = emailOption.querySelector('.email-option-radio');
                if (!radio) return;
                
                const newEmail = radio.value;
                // Si la compañía no cargó o si estamos haciendo clic en el que ya está seleccionado, ignorar.
                if (!currentCompany || newEmail === selectedEmail) return; 

                // Actualizar visualmente la UI de inmediato
                document.querySelectorAll('.email-option').forEach(el => el.classList.remove('selected'));
                emailOption.classList.add('selected');
                radio.checked = true;
                selectedEmail = newEmail;
                
                // Mostrar estado de carga "Autoguardando"
                const indicator = emailOption.querySelector('.saving-indicator');
                if(indicator) indicator.classList.remove('d-none');
                emailOption.classList.add('is-saving'); // Deshabilita clics

                // Realizar llamada al Backend para guardar
                frappe.call({
                    method: 'liseniq.www.iq-config.index.save_notification_email',
                    args: {
                        company: currentCompany,
                        email_account: selectedEmail
                    },
                    callback: function(r) {
                        // Ocultar carga
                        if(indicator) indicator.classList.add('d-none');
                        emailOption.classList.remove('is-saving');

                        if (r.message && r.message.status === 'success') {
                            showModalMessage(r.message.message, 'success');
                            // Cerrar modal automáticamente después del éxito
                            setTimeout(() => {
                                closeModal(document.getElementById('notifications-modal'));
                                const msgBox = document.getElementById('notifications-message-box');
                                if(msgBox) msgBox.classList.add('d-none');
                            }, 1500);
                        } else {
                            showModalMessage(r.message ? r.message.message : 'Error guardando configuración.', 'error');
                        }
                    },
                    error: function(err) {
                        if(indicator) indicator.classList.add('d-none');
                        emailOption.classList.remove('is-saving');
                        showModalMessage('Error de conexión al servidor.', 'error');
                    }
                });
                return;
            }
        });
        
        window.iqConfigEventsBound = true;
    }

    const loadEmailAccounts = () => {
        const emailListContainer = document.getElementById('email-list-container');
        const btnSaveNotifications = document.getElementById('btn-save-notifications');
        
        if(emailListContainer) {
            emailListContainer.innerHTML = '<div class="text-center py-4"><i class="fa fa-spinner fa-spin fa-2x text-muted"></i></div>';
        }
        if(btnSaveNotifications) btnSaveNotifications.disabled = true;
        
        selectedEmail = null;
        
        frappe.call({
            method: 'liseniq.www.iq-config.index.get_email_accounts',
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    currentCompany = r.message.company;
                    renderEmailList(r.message.data, r.message.current);
                } else {
                    const errorMsg = r.message ? r.message.message : 'No se pudo obtener la lista de correos.';
                    if(emailListContainer) emailListContainer.innerHTML = `<div class="alert alert-warning m-0 text-center">${errorMsg}</div>`;
                }
            },
            error: function(err) {
                if(emailListContainer) emailListContainer.innerHTML = `<div class="alert alert-danger m-0 text-center">Ocurrió un error en la conexión.</div>`;
            }
        });
    };

    const renderEmailList = (emails, currentSelectedValue) => {
        const emailListContainer = document.getElementById('email-list-container');
        if(!emailListContainer) return;

        if (!emails || emails.length === 0) {
            emailListContainer.innerHTML = '<div class="alert alert-info text-center m-0">No se encontraron cuentas de correo configuradas en el sistema.</div>';
            return;
        }

        let html = '';
        emails.forEach(email => {
            const isSelected = (currentSelectedValue === email.name);
            if (isSelected) {
                selectedEmail = email.name;
            }

            // Ya no usamos onclick inline, todo se maneja por delegación
            html += `
                <div class="email-option ${isSelected ? 'selected' : ''}" data-email="${email.name}">
                    <input type="radio" name="notification_email" class="email-option-radio" value="${email.name}" ${isSelected ? 'checked' : ''} style="pointer-events: none;">
                    <div class="email-details">
                        <span class="email-name">${email.email_account_name}</span>
                        <span class="email-address">${email.email_id}</span>
                    </div>
                    <div class="saving-indicator d-none">
                        <i class="fa fa-spinner fa-spin" style="color: var(--brand-primary, #7B24FF);"></i>
                    </div>
                </div>
            `;
        });
        
        emailListContainer.innerHTML = html;
    };
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initIqConfig);
} else {
    initIqConfig();
}