document.addEventListener('DOMContentLoaded', function() {
    
    // Validacion de funcionalidades (features) para mostrar/ocultar elementos o activar flujos alternativos
    function hasFeature(featureCode) {
        try {
            // Convertimos el string de la variable global a un Arreglo real
            const featuresArray = JSON.parse(window.liseniqAppFeatures || '[]');
            return featuresArray.includes(featureCode);
        } catch (e) {
            console.error("Error al procesar las funcionalidades de la suscripción:", e);
            return false;
        }
    }

    // (Opcional) Ocultar visualmente botones bloqueados al cargar la página
    document.querySelectorAll('[data-feature]').forEach(el => {
        const requiredFeature = el.getAttribute('data-feature');
        if (requiredFeature && !hasFeature(requiredFeature)) {
            el.style.opacity = '0.5';
            el.setAttribute('title', `Requiere un plan superior. Tu plan actual: ${window.liseniqSubscriptionPlan || 'Básico'}`);
        }
    });

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
        const btn = e.target.closest('.survey-dashboard-btn');
        if (!btn) return;

        const surveyName = btn.getAttribute('data-survey');
        if (!surveyName) return;

        const category = btn.getAttribute('data-category');
        console.log('Survey category:', category);
        if (category === 'Cultura') {
            window.open('/cultura-dashboard?survey=' + encodeURIComponent(surveyName), '_blank');
            return;
        }

        if (category === 'Engagement') {
            window.open('/engagement-dashboard?survey=' + encodeURIComponent(surveyName), '_blank');
            return;
        }
        
        // Default behavior for other categories
        window.open('/engagement-dashboard?survey=' + encodeURIComponent(surveyName), '_blank');
    });
    
    // Descargar reporte de seguimiento mediciones 360
     document.addEventListener('click', function(e) {
        const btn = e.target.closest('.download-follow-up-360-btn');
        if (!btn) return;

        const url = btn.getAttribute('data-url');
        if (!url) return;

        window.location.href = url;
    });

    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.download-leadership-reports-zip-btn');
        if (!btn) return;

        const surveyName = btn.getAttribute('data-survey');
        if (!surveyName) return;

        exportarInformes(surveyName, btn);
    });

    async function exportarInformes(surveyName, btn) {
        if (btn.classList.contains('loading')) return;
        btn.classList.add('loading');
        const originalIcon = btn.innerText;
        btn.innerText = 'hourglass_empty';
        btn.title = 'Generando ZIP...';

        try {
            const res1 = await fetch(
                `/api/method/liseniq.utils.export.export_leadership_reports_zip`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Frappe-CSRF-Token': frappe.csrf_token,
                    },
                    body: JSON.stringify({ survey_name: surveyName }),
                }
            );
            const data1 = await res1.json();
            const jobId = data1?.message?.job_id;
            const cacheKey = data1?.message?.cache_key;

            if (!jobId) throw new Error('No se recibió job_id del servidor.');

            frappe.msgprint({ message: 'Generando informes en background...', indicator: 'blue' });

            await new Promise((resolve, reject) => {
                const interval = setInterval(async () => {
                    try {
                        const res2 = await fetch(
                            `/api/method/liseniq.utils.export.get_export_job_status?job_id=${encodeURIComponent(jobId)}&cache_key=${encodeURIComponent(cacheKey)}`, //  pasar cache_key
                            { headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token } }
                        );
                        const data2 = await res2.json();
                        const status = data2?.message?.status;

                        if (status === 'finished') {
                            clearInterval(interval);
                            frappe.msgprint({ message: ' ZIP listo, descargando...', indicator: 'green' });

                            const downloadUrl = `/api/method/liseniq.utils.export.download_export_file?cache_key=${encodeURIComponent(cacheKey)}`;
                            const a = document.createElement('a');
                            a.href = downloadUrl;
                            a.download = '';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);

                            resolve();
                        }
                        else if (status === 'failed') {
                            clearInterval(interval);
                            frappe.msgprint({ title: 'Error al generar ZIP', message: data2.message.error, indicator: 'red' });
                            reject(new Error(data2.message.error));
                        }
                    } catch (err) {
                        clearInterval(interval);
                        reject(err);
                    }
                }, 4000);
            });

        } catch (err) {
            console.error('exportarInformes error:', err);
            frappe.msgprint({ message: 'Error: ' + err.message, indicator: 'red' });
        } finally {
            btn.classList.remove('loading');
            btn.innerText = originalIcon;
            btn.title = 'Descargar informes PDF';
        }
    }
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.download-follow-up-btn');
        if (!btn) return;

        const url = btn.getAttribute('data-url');
        if (!url) return;

        document.getElementById('downloadReportUrl').value = url;
        
        var survey = btn.getAttribute('data-survey');
        loadDemographics(survey);
        
        document.getElementById('downloadReportModal').style.display = 'flex';
    });
    
    function loadDemographics(survey) {
        frappe.call({
            method: 'liseniq.utils.export.get_demographics',
            args: {
                survey: survey
            },
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