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
    
    // Descargar resultados finales (sin modal)
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.download-results-btn');
        if (!btn) return;

        const url = btn.getAttribute('data-url');
        if (!url) return;

        window.location.href = url;
    });
    
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.download-follow-up-btn');
        if (!btn) return;

        const url = btn.getAttribute('data-url');
        if (!url) return;

        document.getElementById('downloadReportUrl').value = url;
        
        loadDemographics();
        
        document.getElementById('downloadReportModal').style.display = 'flex';
    });
    
    function loadDemographics() {
        frappe.call({
            method: 'liseniq.utils.export.get_demographics',
            callback: function(r) {
                if (r.message) {
                    const select1 = document.getElementById('demographic1');
                    const select2 = document.getElementById('demographic2');
                    
                    // Limpiar opciones existentes excepto la primera
                    select1.innerHTML = '<option value="">-- Selecciona un demográfico --</option>';
                    select2.innerHTML = '<option value="">-- Selecciona un demográfico --</option>';
                    
                    // Agregar las opciones de demográficos
                    r.message.forEach(function(demo) {
                        const option1 = document.createElement('option');
                        option1.value = demo.name;
                        option1.textContent = demo.dt_title || demo.name;
                        select1.appendChild(option1);
                        
                        const option2 = document.createElement('option');
                        option2.value = demo.name;
                        option2.textContent = demo.dt_title || demo.name;
                        select2.appendChild(option2);
                    });
                }
            }
        });
    }
    
    document.getElementById('closeDownloadReportModal').addEventListener('click', function() {
        document.getElementById('downloadReportModal').style.display = 'none';
    });
    
    document.getElementById('btnCancelDownload').addEventListener('click', function() {
        document.getElementById('downloadReportModal').style.display = 'none';
    });
    
    document.getElementById('downloadReportModal').addEventListener('click', function(e) {
        if (e.target.id === 'downloadReportModal') {
            document.getElementById('downloadReportModal').style.display = 'none';
        }
    });
    
    document.getElementById('btnDownloadReport').addEventListener('click', function() {
        const demographic1 = document.getElementById('demographic1').value;
        const demographic2 = document.getElementById('demographic2').value;
        
        if (!demographic1 && !demographic2) {
            frappe.msgprint({
                title: 'Atención',
                indicator: 'orange',
                message: 'Por favor selecciona al menos un demográfico para descargar el reporte.'
            });
            return;
        }
        
        let baseUrl = document.getElementById('downloadReportUrl').value;
        
        if (demographic1) {
            baseUrl += '&demographic1=' + encodeURIComponent(demographic1);
        }
        if (demographic2) {
            baseUrl += '&demographic2=' + encodeURIComponent(demographic2);
        }
        
        document.getElementById('downloadReportModal').style.display = 'none';
        
        window.location.href = baseUrl;
    });

    // Enviar recordatorios manualmente desde el FE
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-reminders');
        if (!btn) return;

        const surveyName = btn.getAttribute('data-survey');
        if (!surveyName) return;

        frappe.confirm(
            '¿Estás seguro de que deseas enviar un recordatorio a todos los participantes que aún no han respondido?',
            function() {
                frappe.call({
                    method: 'liseniq.tasks.send_survey_reminders',
                    args: {
                        survey_name: surveyName
                    },
                    freeze: true,
                    freeze_message: 'Enviando recordatorios...',
                    callback: function(r) {
                        if (r.message && r.message.status === 'success') {
                            frappe.msgprint({
                                title: '¡Éxito!',
                                indicator: 'green',
                                message: `Recordatorios enviados exitosamente.<br><b>Enviados:</b> ${r.message.sent}<br><b>Errores/Omitidos:</b> ${r.message.errores}`
                            });
                        } else if (r.message && r.message.status === 'error') {
                            frappe.msgprint({
                                title: 'Error',
                                indicator: 'red',
                                message: r.message.message || 'Ocurrió un error al enviar los recordatorios.'
                            });
                        }
                    }
                });
            }
        );
    });
});