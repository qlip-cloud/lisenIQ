document.addEventListener('DOMContentLoaded', function() {
    // =========================================================================
    // SELECTORES DEL DOM
    // =========================================================================
    const btnCreateMeasurement = document.getElementById('btn-create-measurement');

    // =========================================================================
    // ASIGNACIÓN DE EVENTOS
    // =========================================================================
    if (btnCreateMeasurement) {
        btnCreateMeasurement.addEventListener('click', function() {
            // Acción temporal: Muestra un mensaje en consola y una notificación.
            // La funcionalidad completa de "Crear Medición" aún no está implementada.
            console.log('Botón "Crear Medición" pulsado. Acción no implementada.');
            
            // Muestra una notificación al usuario si la función global está disponible.
            if (typeof showGlobalNotification === 'function') {
                showGlobalNotification('Funcionalidad "Crear Medición" aún no implementada.', 'error', 3000);
            } else {
                // Fallback a un alert simple si la función de notificación no está disponible.
                alert('Funcionalidad "Crear Medición" aún no implementada.');
            }
        });
    }
});
