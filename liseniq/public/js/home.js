document.addEventListener('DOMContentLoaded', function() {
    const filterButton = document.querySelector('.filter-button');

    function initializeEventListeners() {
        if (filterButton) {
            filterButton.addEventListener('click', () => {
                if (typeof showGlobalNotification === 'function') {
                    showGlobalNotification('La funcionalidad de filtrado estará disponible próximamente.', 'error', 3000);
                } else {
                    console.log('Funcionalidad de filtrado no implementada.');
                }
            });
        }
    }

    initializeEventListeners();
});
