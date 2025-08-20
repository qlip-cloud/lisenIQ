let notificationTimeout;

document.addEventListener('DOMContentLoaded', function() {
    // =========================================================================
    // SELECTORES DEL DOM
    // =========================================================================
    const sidebar = document.getElementById('app-sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');
    const closeBtn = document.getElementById('sidebar-close-btn');
    const overlay = document.getElementById('sidebar-overlay');

    const measurementModal = document.getElementById('create-measurement-modal');
    const openModalBtn = document.getElementById('btn-open-create-measurement-modal');
    const closeModalBtn = document.getElementById('btn-close-measurement-modal');
    const createBlankMeasurementBtn = document.getElementById('btn-blank-measurement');

    // =========================================================================
    // FUNCIONES
    // =========================================================================

    // Alterna la visibilidad del sidebar y la superposición
    function toggleSidebar() {
        if (sidebar && overlay) {
            sidebar.classList.toggle('sidebar-visible');
            overlay.classList.toggle('active');
        }
    }

    // Abre el modal de creación de medición
    function openMeasurementModal() {
        if (measurementModal) measurementModal.classList.remove('d-none');
    }

    // Cierra el modal de creación de medición
    function closeMeasurementModal() {
        if (measurementModal) measurementModal.classList.add('d-none');
    }

    // =========================================================================
    // ASIGNACIÓN DE EVENTOS
    // =========================================================================

    if (toggleBtn) toggleBtn.addEventListener('click', toggleSidebar);
    if (closeBtn) closeBtn.addEventListener('click', toggleSidebar);
    if (overlay) overlay.addEventListener('click', toggleSidebar);

    // Eventos para el modal de Medición
    if (openModalBtn) openModalBtn.addEventListener('click', openMeasurementModal);
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeMeasurementModal);
    if (measurementModal) {
        // Cierra el modal si se hace clic fuera de su contenido
        measurementModal.addEventListener('click', (e) => {
            if (e.target === measurementModal) {
                closeMeasurementModal();
            }
        });
    }

    // Redirecciona para crear una nueva medición en blanco
    if (createBlankMeasurementBtn) {
        createBlankMeasurementBtn.addEventListener('click', () => {
            window.location.href = '/measurement/new_measurement';
        });
    }
});

// Muestra una barra de notificación global en la parte superior del contenido.
function showGlobalNotification(message, type, duration = 5000) {
    const notificationBar = document.getElementById('global-notification-bar');
    const notificationMessage = document.getElementById('global-notification-message');

    if (!notificationBar || !notificationMessage) {
        console.error('Elementos de la barra de notificación no encontrados en el DOM.');
        // Fallback a alert si los elementos de notificación no están presentes
        alert(message); 
        return;
    }

    clearTimeout(notificationTimeout);
    notificationMessage.textContent = message;
    notificationBar.classList.remove('notification-success', 'notification-error');
    if (type === 'success') {
        notificationBar.classList.add('notification-success');
    } else if (type === 'error') {
        notificationBar.classList.add('notification-error');
    }

    notificationBar.classList.add('show');
    notificationTimeout = setTimeout(() => {
        notificationBar.classList.remove('show');
    }, duration);
}
