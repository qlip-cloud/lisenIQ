let notificationTimeout;

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('app-sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');
    const closeBtn = document.getElementById('sidebar-close-btn');
    const overlay = document.getElementById('sidebar-overlay');

    const measurementModal = document.getElementById('create-measurement-modal');
    const openModalBtn = document.getElementById('btn-open-create-measurement-modal');
    const closeModalBtn = document.getElementById('btn-close-measurement-modal');
    const createBlankMeasurementBtn = document.getElementById('btn-blank-measurement');

    function toggleSidebar() {
        if (sidebar && overlay) {
            sidebar.classList.toggle('sidebar-visible');
            overlay.classList.toggle('active');
        }
    }

    function openMeasurementModal() {
        if (measurementModal) measurementModal.classList.remove('d-none');
    }

    function closeMeasurementModal() {
        if (measurementModal) measurementModal.classList.add('d-none');
    }

    if (toggleBtn) toggleBtn.addEventListener('click', toggleSidebar);
    if (closeBtn) closeBtn.addEventListener('click', toggleSidebar);
    if (overlay) overlay.addEventListener('click', toggleSidebar);

    if (openModalBtn) openModalBtn.addEventListener('click', openMeasurementModal);
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeMeasurementModal);
    if (measurementModal) {
        measurementModal.addEventListener('click', (e) => {
            if (e.target === measurementModal) {
                closeMeasurementModal();
            }
        });
    }

    if (createBlankMeasurementBtn) {
        createBlankMeasurementBtn.addEventListener('click', () => {
            window.location.href = '/measurement/new_measurement';
        });
    }
});

function showGlobalNotification(message, type, duration = 5000) {
    const notificationBar = document.getElementById('global-notification-bar');
    const notificationMessage = document.getElementById('global-notification-message');

    if (!notificationBar || !notificationMessage) {
        console.error('Elementos de la barra de notificación no encontrados en el DOM.');
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
