document.addEventListener('DOMContentLoaded', function() {
    const btnCreateMeasurement = document.getElementById('btn-create-measurement');

    if (btnCreateMeasurement) {
        btnCreateMeasurement.addEventListener('click', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const templateName = urlParams.get('name');
            if (templateName) {
                window.location.href = `/measurement/new_measurement?template=${encodeURIComponent(templateName)}`;
            } else {
                console.error('No se pudo encontrar el nombre de la plantilla en la URL.');
                if (typeof showGlobalNotification === 'function') {
                    showGlobalNotification('Error: No se pudo identificar la plantilla actual.', 'error');
                } else {
                    showGlobalNotification('Error: No se pudo identificar la plantilla actual.', 'error');
                }
            }
        });
    }
});
