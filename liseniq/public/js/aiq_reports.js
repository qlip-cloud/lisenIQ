document.addEventListener('DOMContentLoaded', async function() {
    const params = new URLSearchParams(window.location.search);
    const surveyName = params.get('survey_name');
    const surveyTitle = params.get('survey_title') || 'Reporte de Resultados';

    if (!surveyName) {
        if(window.frappe) {
            frappe.msgprint({
                title: 'Error',
                indicator: 'red',
                message: 'No se ha especificado ninguna medición para graficar.'
            });
        }
        return;
    }

    const titleElement = document.getElementById('report-survey-title');
    if (titleElement) titleElement.textContent = surveyTitle;

    // Cargamos de forma asíncrona las librerías comunes
    try {
        await Promise.all([loadApexCharts(), loadJsPDF(), loadHtml2Canvas()]);
    } catch (e) {
        console.error("Fallo al cargar librerías externas", e);
        return;
    }

    // Evento Global de Exportación (Todo el reporte)
    const btnExportFullPdf = document.getElementById('btn-export-full-pdf');
    if (btnExportFullPdf) {
        btnExportFullPdf.addEventListener('click', () => {
            exportFullPageToPDF(surveyName);
        });
    }

    // Enrutador de Categorías
    const config = window.aiqReportConfig || {};
    const mnemonic = config.mnemonic;

    if (mnemonic === 'template_culture') {
        try {
            // Importación dinámica del módulo específico
            const cultureModule = await import('/assets/liseniq/js/reports/report_culture.js');
            cultureModule.initCultureReport(config.data, surveyName);
        } catch (err) {
            console.error("Error al cargar el módulo del reporte de Cultura", err);
        }
    } 
    // Aquí puedes agregar en el futuro: else if (mnemonic === 'template_engagement') { ... }
});

// Carga dinámica de librerías
function loadJsPDF() {
    return new Promise((resolve, reject) => {
        if (window.jspdf) return resolve();
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

function loadApexCharts() {
    return new Promise((resolve, reject) => {
        if (window.ApexCharts) return resolve();
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/apexcharts';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

function loadHtml2Canvas() {
    return new Promise((resolve, reject) => {
        if (window.html2canvas) return resolve();
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Exportar TODO el reporte a un PDF multi-página, bloque por bloque
async function exportFullPageToPDF(surveyName) {
    const btnExport = document.getElementById('btn-export-full-pdf');
    const originalBtnText = btnExport ? btnExport.innerHTML : '';
    
    try {
        if (btnExport) btnExport.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Exportando...';

        const wrapper = document.querySelector('.aiq-reports-wrapper');
        
        // Guardar estilos originales y preparar para captura completa
        const originalHeight = wrapper.style.height;
        const originalOverflow = wrapper.style.overflowY;
        
        wrapper.style.height = 'auto';
        wrapper.style.overflowY = 'visible';
        
        // Ocultar botones que no deben salir en el PDF
        const buttonsToHide = document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple');
        buttonsToHide.forEach(btn => btn.style.display = 'none');

        // Inicializar jsPDF Libreria para generar PDF
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        
        const margin = 10;
        const maxPdfWidth = pdfWidth - (margin * 2);
        let currentY = margin;

        // Identificar todos los bloques principales hijos del wrapper
        // Filtramos scripts, estilos, elementos ocultos, o elementos sin altura (vacíos)
        const blocks = Array.from(wrapper.children).filter(child => {
            const style = window.getComputedStyle(child);
            return child.tagName !== 'SCRIPT' && 
                   child.tagName !== 'STYLE' && 
                   style.display !== 'none' &&
                   child.offsetHeight > 0 && 
                   child.offsetWidth > 0;
        });

        // Iterar sobre cada bloque, capturarlo y colocarlo en el PDF
        for (let i = 0; i < blocks.length; i++) {
            const block = blocks[i];

            // Capturar el bloque individual
            const canvas = await html2canvas(block, {
                scale: 2, 
                useCORS: true,
                logging: false,
                backgroundColor: '#ffffff'
            });

            // Si el canvas se generó con dimensión 0, saltamos este bloque
            if (canvas.width === 0 || canvas.height === 0) {
                console.warn('Bloque ignorado: Dimensiones del canvas son 0', block);
                continue;
            }

            const imgData = canvas.toDataURL('image/png');
            
            // Si por alguna razón la imagen generada es corrupta/vacía
            if (!imgData || imgData === 'data:,') {
                console.warn('Bloque ignorado: Data de imagen inválida', block);
                continue;
            }
            
            // Calcular dimensiones de la imagen para el PDF
            const pdfImgWidth = maxPdfWidth;
            const pdfImgHeight = (canvas.height * pdfImgWidth) / canvas.width;

            // Verificar si el bloque cabe en el espacio restante de la página actual
            if (currentY + pdfImgHeight > pageHeight - margin) {
                // Si no cabe, y no estamos al inicio de una página, forzamos salto
                if (currentY > margin) {
                    pdf.addPage();
                    currentY = margin;
                }
            }

            // Insertar la imagen. 
            if (pdfImgHeight <= pageHeight - (margin * 2)) {
                // El bloque cabe entero en la página actual
                pdf.addImage(imgData, 'PNG', margin, currentY, pdfImgWidth, pdfImgHeight);
                currentY += pdfImgHeight + (margin / 2); // Espaciado entre bloques
            } else {
                // El bloque es monolítico y gigante. Hay que cortarlo
                let heightLeft = pdfImgHeight;
                let position = currentY;

                pdf.addImage(imgData, 'PNG', margin, position, pdfImgWidth, pdfImgHeight);
                heightLeft -= (pageHeight - currentY);

                while (heightLeft > 0) {
                    pdf.addPage();
                    position -= pageHeight;
                    pdf.addImage(imgData, 'PNG', margin, position, pdfImgWidth, pdfImgHeight);
                    heightLeft -= pageHeight;
                }
                // Actualizar Y para el siguiente bloque después del bloque gigante
                currentY = position + pdfImgHeight + (margin / 2); 
            }
        }

        // Restaurar el DOM a su estado original
        wrapper.style.height = originalHeight;
        wrapper.style.overflowY = originalOverflow;
        buttonsToHide.forEach(btn => btn.style.display = '');
        if (btnExport) btnExport.innerHTML = originalBtnText;

        // Descargar el archivo
        pdf.save(`Reporte_${surveyName}.pdf`);

    } catch (err) {
        console.error('Error exportando reporte completo:', err);
        
        // Restaurar estado en caso de error
        const wrapper = document.querySelector('.aiq-reports-wrapper');
        if (wrapper) {
            wrapper.style.height = 'calc(100vh - 80px)';
            wrapper.style.overflowY = 'auto';
        }
        document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple')
            .forEach(btn => btn.style.display = '');
            
        if (btnExport) btnExport.innerHTML = originalBtnText;

        if (window.frappe) {
            frappe.msgprint('Ocurrió un error al intentar exportar el reporte.');
        }
    }
}