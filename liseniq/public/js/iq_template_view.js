document.addEventListener('DOMContentLoaded', function() {
    const btnCreateMeasurement = document.getElementById('btn-create-measurement');

    if (btnCreateMeasurement) {
        btnCreateMeasurement.addEventListener('click', function() {
            console.log('Botón "Crear Medición" pulsado. Acción no implementada.');
            
            if (typeof showGlobalNotification === 'function') {
                showGlobalNotification('Funcionalidad "Crear Medición" aún no implementada.', 'error', 3000);
            } else {
                alert('Funcionalidad "Crear Medición" aún no implementada.');
            }
        });
    }
});
