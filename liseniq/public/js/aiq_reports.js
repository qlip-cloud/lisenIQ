document.addEventListener('DOMContentLoaded', async function() {
    const params = new URLSearchParams(window.location.search);
    const surveyName = params.get('survey_name');
    
    // Obtenemos el título real directamente del DOM renderizado por el Backend
    const titleElement = document.getElementById('report-survey-title');
    const finalSurveyTitle = titleElement ? titleElement.innerText.trim() : 'Reporte';

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

    // Cargamos de forma asíncrona las librerías necesarias
    try {
        await Promise.all([loadApexCharts(), loadJsPDF(), loadHtml2Canvas()]);
    } catch (e) {
        console.error("Fallo al cargar librerías externas", e);
        return;
    }

    observeAndInjectButtons();

    // Evento de Exportación del Reporte Completo (Motor jsPDF Avanzado)
    const btnExportFullPdf = document.getElementById('btn-export-full-pdf');
    if (btnExportFullPdf) {
        btnExportFullPdf.addEventListener('click', () => {
            exportFullPageToPDF(surveyName, finalSurveyTitle);
        });
    }

    // Enrutador de Categorías
    const config = window.aiqReportConfig || {};
    const mnemonic = config.mnemonic;

    if (mnemonic === 'template_culture') {
        try {
            import('/assets/liseniq/js/reports/report_culture.js').then(m => m.initCultureReport(config.data, surveyName));
        } catch (err) { console.error(err); }
    } else if (mnemonic === 'template_engagement') {
        try {
            import('/assets/liseniq/js/reports/report_by_engagement.js').then(m => m.initEngagementReport(config.data, surveyName));
        } catch (err) { console.error(err); }
    }
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

// Inyección de botones individuales
function observeAndInjectButtons() {
    const wrapper = document.querySelector('.aiq-reports-wrapper');
    if (!wrapper) return;
    injectSectionExportButtons();
    const observer = new MutationObserver(() => injectSectionExportButtons());
    observer.observe(wrapper, { childList: true, subtree: true });
}

function injectSectionExportButtons() {
    const sections = ['.metrics-container', '.top-bottom-container', '.topics-tables-container'];
    
    sections.forEach(selector => {
        document.querySelectorAll(selector).forEach(container => {
            if (container.dataset.buttonsInjected) return;
            
            let header = container.previousElementSibling;
            let hasHeader = header && header.classList.contains('chart-header-flex');
            let isExistingHeaderTag = header && header.tagName && header.tagName.match(/^H[1-6]$/);
            
            if (isExistingHeaderTag) {
                const flexWrapper = document.createElement('div');
                flexWrapper.className = 'chart-header-flex';
                
                const title = document.createElement(header.tagName);
                title.className = 'chart-section-title';
                title.innerHTML = header.innerHTML;
                
                flexWrapper.innerHTML = `<div class="chart-actions-group"></div>`;
                flexWrapper.insertBefore(title, flexWrapper.firstChild);
                
                header.parentNode.replaceChild(flexWrapper, header);
                header = flexWrapper;
            } else if (!hasHeader) {
                header = document.createElement('div');
                header.className = 'chart-header-flex';
                let titleText = 'Sección';
                if (selector === '.top-bottom-container') titleText = 'Top / Bottom 10';
                else if (selector === '.topics-tables-container') titleText = 'Análisis por Temas';
                
                header.innerHTML = `
                    <h3 class="chart-section-title">${titleText}</h3>
                    <div class="chart-actions-group"></div>
                `;
                container.parentNode.insertBefore(header, container);
            }
            
            // Inyectar botones si no existen
            const actionsGroup = header.querySelector('.chart-actions-group');
            if (actionsGroup && !actionsGroup.querySelector('.btn-export-section-pdf')) {
                const btnPdf = document.createElement('button');
                btnPdf.className = 'btn btn-export-section-pdf';
                btnPdf.title = 'Exportar a PDF';
                btnPdf.innerHTML = '<i class="fa fa-file-pdf-o"></i>';
                btnPdf.onclick = () => exportSingleSection(container, header, 'pdf');
                
                const btnImg = document.createElement('button');
                btnImg.className = 'btn btn-export-section-img';
                btnImg.title = 'Exportar a Imagen';
                btnImg.innerHTML = '<i class="fa fa-image"></i>';
                btnImg.onclick = () => exportSingleSection(container, header, 'img');
                
                actionsGroup.appendChild(btnImg);
                actionsGroup.appendChild(btnPdf);
            }
            container.dataset.buttonsInjected = "true";
        });
    });
}

async function exportSingleSection(container, header, type) {
    const actionsGroup = header.querySelector('.chart-actions-group');
    if (actionsGroup) actionsGroup.style.display = 'none';
    
    try {
        const opts = { scale: 2, useCORS: true, logging: false, backgroundColor: '#ffffff' };
        
        const headerCanvas = await html2canvas(header, opts);
        const containerCanvas = await html2canvas(container, opts);
        
        const combinedCanvas = document.createElement('canvas');
        combinedCanvas.width = Math.max(headerCanvas.width, containerCanvas.width);
        combinedCanvas.height = headerCanvas.height + containerCanvas.height;
        
        const ctx = combinedCanvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, combinedCanvas.width, combinedCanvas.height);
        
        ctx.drawImage(headerCanvas, 0, 0);
        ctx.drawImage(containerCanvas, 0, headerCanvas.height);
        
        const titleEl = document.getElementById('report-survey-title');
        const rawTitle = titleEl ? titleEl.innerText.trim() : 'Reporte';
        const cleanTitle = rawTitle.replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        
        let sectionTitle = header.querySelector('.chart-section-title')?.innerText || 'Seccion';
        sectionTitle = sectionTitle.trim().replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        const fileName = `Reporte_${sectionTitle}_${cleanTitle}`;
        
        if (type === 'img') {
            const link = document.createElement('a');
            link.download = `${fileName}.jpg`;
            link.href = combinedCanvas.toDataURL('image/jpeg', 1.0);
            link.click();
        } else if (type === 'pdf') {
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const margin = 10;
            const maxPdfWidth = pdfWidth - (margin * 2);
            
            let pdfImgWidth = maxPdfWidth;
            let pdfImgHeight = (combinedCanvas.height * pdfImgWidth) / combinedCanvas.width;
            
            if (pdfImgHeight > pdf.internal.pageSize.getHeight() - (margin * 2)) {
                const ratio = (pdf.internal.pageSize.getHeight() - (margin * 2)) / pdfImgHeight;
                pdfImgHeight = pdfImgHeight * ratio;
                pdfImgWidth = pdfImgWidth * ratio;
            }
            
            pdf.addImage(combinedCanvas.toDataURL('image/png'), 'PNG', margin, margin, pdfImgWidth, pdfImgHeight);
            pdf.save(`${fileName}.pdf`);
        }
        
        // Limpiar memoria
        headerCanvas.width = 0;
        containerCanvas.width = 0;
        combinedCanvas.width = 0;
        
    } catch(e) {
        console.error('Error al exportar seccion:', e);
        if (window.frappe) frappe.msgprint('Error al exportar la sección.');
    } finally {
        if (actionsGroup) actionsGroup.style.display = '';
    }
}

// Lógica de aislamiento para exportación completa
function getExportBlocks(container) {
    let blocks = [];
    let currentGroup = [];
    const nodes = Array.from(container.children);
    
    for (let node of nodes) {
        if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE' || node.style.display === 'none') continue;
        
        // Mantener el encabezado principal solo
        if (node.classList.contains('aiq-reports-header')) {
             blocks.push({ elements: [node] });
             continue;
        }

        const isHeader = node.classList.contains('chart-header-flex') || node.tagName.match(/^H[1-6]$/);
        
        if (isHeader) {
            if (currentGroup.length > 0) {
                 blocks.push({ elements: currentGroup });
                 currentGroup = [];
            }
            currentGroup.push(node);
        } else {
            currentGroup.push(node);
            blocks.push({ elements: currentGroup });
            currentGroup = [];
        }
    }
    if (currentGroup.length > 0) blocks.push({ elements: currentGroup });
    return blocks;
}

// Motor jsPDF de construcción de PDF completo con paginación inteligente
async function exportFullPageToPDF(surveyName, surveyTitle) {
    const btnExport = document.getElementById('btn-export-full-pdf');
    const originalBtnText = btnExport ? btnExport.innerHTML : '';
    
    try {
        if (btnExport) btnExport.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Procesando PDF...';

        const wrapper = document.querySelector('.aiq-reports-wrapper');
        const originalHeight = wrapper.style.height;
        const originalOverflow = wrapper.style.overflowY;
        
        wrapper.style.height = 'auto';
        wrapper.style.overflowY = 'visible';
        
        const buttonsToHide = document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple');
        buttonsToHide.forEach(btn => btn.style.display = 'none');

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        
        const margin = 10;
        const maxPdfWidth = pdfWidth - (margin * 2);
        const maxPageHeight = pageHeight - (margin * 2);
        
        let currentY = margin;
        const blocksInfo = getExportBlocks(wrapper);

        // Opciones optimizadas de captura (Renderiza mejor los gráficos ApexCharts)
        const canvasOpts = { 
            scale: 2, 
            useCORS: true, 
            logging: false, 
            backgroundColor: '#ffffff',
            onclone: (clonedDoc) => {
                // Forzar que los gráficos SVG se dibujen al ancho completo antes del render
                const svgs = clonedDoc.querySelectorAll('.apexcharts-svg');
                svgs.forEach(svg => { svg.setAttribute('width', '100%'); });
            }
        };

        for (let i = 0; i < blocksInfo.length; i++) {
            const elements = blocksInfo[i].elements;
            let blockImages = [];
            let totalHeightInPdf = 0;
            
            for (let el of elements) {
                // Pausa crítica para evitar que se congele el navegador
                await new Promise(resolve => setTimeout(resolve, 50));
                
                const canvas = await html2canvas(el, canvasOpts);
                if (canvas.width === 0 || canvas.height === 0) continue;
                
                const imgData = canvas.toDataURL('image/jpeg', 0.95);
                const pdfImgHeight = (canvas.height * maxPdfWidth) / canvas.width;
                
                blockImages.push({ imgData, width: maxPdfWidth, height: pdfImgHeight, isHeader: el.classList.contains('chart-header-flex') });
                totalHeightInPdf += pdfImgHeight;
                
                canvas.width = 0; // Liberar memoria RAM
            }
            
            if (blockImages.length === 0) continue;

            // Lógica de Paginación Inteligente
            // Si el bloque actual (Ej: Titulo + Gráfico) no cabe en el espacio restante, saltar de página
            if (currentY + totalHeightInPdf > maxPageHeight && currentY > margin) {
                pdf.addPage();
                currentY = margin;
            }

            for (let imgObj of blockImages) {
                let renderWidth = imgObj.width;
                let renderHeight = imgObj.height;
                let xOffset = margin;
                
                // Si un componente individual es más gigante que la página, lo encoge.
                if (renderHeight > maxPageHeight) {
                    const ratio = maxPageHeight / renderHeight;
                    renderHeight = renderHeight * ratio;
                    renderWidth = renderWidth * ratio;
                    xOffset = margin + ((maxPdfWidth - renderWidth) / 2); // Centrar horizontalmente
                    
                    // Como el elemento es tan grande, forzamos página nueva para él solo (si no estamos al inicio)
                    if (currentY > margin && !imgObj.isHeader) {
                        pdf.addPage();
                        currentY = margin;
                    }
                } else if (currentY + renderHeight > maxPageHeight) {
                    // Prevenir desbordamiento de componentes secundarios del mismo bloque
                    pdf.addPage();
                    currentY = margin;
                }
                
                pdf.addImage(imgObj.imgData, 'JPEG', xOffset, currentY, renderWidth, renderHeight);
                
                // Añadir un pequeño margen debajo de cada componente
                currentY += renderHeight + (imgObj.isHeader ? 2 : 8); 
            }
        }

        // Restaurar estado visual
        wrapper.style.height = originalHeight;
        wrapper.style.overflowY = originalOverflow;
        buttonsToHide.forEach(btn => btn.style.display = '');
        if (btnExport) btnExport.innerHTML = originalBtnText;

        // Descargar usando el Título Real
        const cleanTitle = (surveyTitle || surveyName || 'Resultados').replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        pdf.save(`Reporte_${cleanTitle}.pdf`);

    } catch (err) {
        console.error('Error exportando reporte completo:', err);
        
        // Restaurar estado en caso de error crítico
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