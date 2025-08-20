document.addEventListener('DOMContentLoaded', function() {
    // Selectores de los elementos del DOM
    const categoryCheckboxes = document.querySelectorAll('#category-filter-list input[type="checkbox"]');
    const templateCards = document.querySelectorAll('.template-card-wrapper');
    const createMeasurementButtons = document.querySelectorAll('.btn-create-measurement-from-template');

    // Filtra las tarjetas de plantillas basándose en las categorías seleccionadas.
    function filterTemplates() {
        // 1. Obtener los IDs de las categorías seleccionadas
        const selectedCategories = Array.from(categoryCheckboxes)
            .filter(checkbox => checkbox.checked)
            .map(checkbox => checkbox.value);

        // 2. Iterar sobre cada tarjeta de plantilla para decidir si se muestra u oculta
        templateCards.forEach(card => {
            const cardCategory = card.getAttribute('data-category');

            // 3. Lógica de visibilidad:
            // - Si no hay ninguna categoría seleccionada, se muestran todas las tarjetas.
            // - Si hay categorías seleccionadas, se muestra la tarjeta solo si su
            //   categoría está incluida en la lista de seleccionadas.
            if (selectedCategories.length === 0 || selectedCategories.includes(cardCategory)) {
                card.style.display = ''; // Muestra la tarjeta
            } else {
                card.style.display = 'none'; // Oculta la tarjeta
            }
        });
    }

    // Añade un event listener a cada checkbox de categoría
    categoryCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', filterTemplates);
    });

    // Añade un event listener a cada botón "Crear Medición"
    createMeasurementButtons.forEach(button => {
        button.addEventListener('click', function() {
            const templateName = this.getAttribute('data-template-name');
            if (templateName) {
                // Redirige al wizard de creación de mediciones con el ID de la plantilla
                window.location.href = `/measurement/new_measurement?template=${templateName}`;
            }
        });
    });
});
