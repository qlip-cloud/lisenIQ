document.addEventListener('DOMContentLoaded', function() {
    const filterButton = document.querySelector('.filter-button');
    const filterDropdown = document.getElementById('filter-dropdown');
    const filterArrow = document.querySelector('.filter-arrow');

    function initializeEventListeners() {
        if (filterButton && filterDropdown) {
            filterButton.addEventListener('click', (e) => {
                e.stopPropagation();
                const isHidden = filterDropdown.classList.toggle('d-none');
                if (filterArrow) {
                    filterArrow.classList.toggle('fa-chevron-up', !isHidden);
                    filterArrow.classList.toggle('fa-chevron-down', isHidden);
                }
            });
        }

        document.addEventListener('click', (e) => {
            if (filterDropdown && !filterDropdown.classList.contains('d-none') && !filterButton.contains(e.target)) {
                filterDropdown.classList.add('d-none');
                if (filterArrow) {
                    filterArrow.classList.remove('fa-chevron-up');
                    filterArrow.classList.add('fa-chevron-down');
                }
            }
        });
    }

    initializeEventListeners();
    document.addEventListener('click', function(e) {
    const btn = e.target.closest('.download-results-btn');
    if (!btn) return;

    const url = btn.getAttribute('data-url');
    if (!url) return;

    window.location.href = url;
});
});