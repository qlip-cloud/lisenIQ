document.addEventListener('DOMContentLoaded', () => {
    // Referencias a los elementos del DOM
    const btnManageCompanies = document.getElementById('btn-manage-companies');
    const manageCompanyModal = document.getElementById('manage-company-modal');
    const btnCloseCompanyModal = document.getElementById('btn-close-company-modal');
    
    // Botones internos del modal
    const btnCreateCompany = document.getElementById('btn-create-company');
    const btnEditCompany = document.getElementById('btn-edit-company');

    // Función para abrir el modal
    const openModal = () => {
        if (manageCompanyModal) {
            manageCompanyModal.classList.remove('d-none');
            // Prevenir el scroll de la página de fondo
            document.body.style.overflow = 'hidden';
        }
    };

    // Función para cerrar el modal
    const closeModal = () => {
        if (manageCompanyModal) {
            manageCompanyModal.classList.add('d-none');
            // Restaurar el scroll de la página
            document.body.style.overflow = '';
        }
    };

    // Eventos para abrir y cerrar
    if (btnManageCompanies) {
        btnManageCompanies.addEventListener('click', openModal);
    }

    if (btnCloseCompanyModal) {
        btnCloseCompanyModal.addEventListener('click', closeModal);
    }

    // Cerrar el modal al hacer clic en el overlay exterior
    if (manageCompanyModal) {
        manageCompanyModal.addEventListener('click', (e) => {
            if (e.target === manageCompanyModal) {
                closeModal();
            }
        });
    }

    // Lógica para Crear Compañía (Redirección al HTML de nueva compañía)
    if (btnCreateCompany) {
        btnCreateCompany.addEventListener('click', () => {
            // Se actualiza la ruta de redirección
            window.location.href = '/iq-config/new_company';
        });
    }

    // Lógica para Editar Compañía
    if (btnEditCompany) {
        btnEditCompany.addEventListener('click', () => {
            console.log('Opción de editar compañía en desarrollo.');
        });
    }
});