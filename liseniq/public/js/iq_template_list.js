document.addEventListener('DOMContentLoaded', function() {
    const categoryCheckboxes = document.querySelectorAll('#category-filter-list input[type="checkbox"]');
    const templateCards = document.querySelectorAll('.template-card-wrapper');
    const createMeasurementButtons = document.querySelectorAll('.btn-create-measurement-from-template');

    function filterTemplates() {
        const selectedCategories = Array.from(categoryCheckboxes)
            .filter(checkbox => checkbox.checked)
            .map(checkbox => checkbox.value);

        templateCards.forEach(card => {
            const cardCategory = card.getAttribute('data-category');

            if (selectedCategories.length === 0 || selectedCategories.includes(cardCategory)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    categoryCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', filterTemplates);
    });

    createMeasurementButtons.forEach(button => {
        button.addEventListener('click', function() {
            const templateName = this.getAttribute('data-template-name');
            if (templateName) {
                window.location.href = `/measurement/new_measurement?template=${templateName}`;
            }
        });
    });
});
