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
                header.innerHTML = `<h3 class="chart-section-title">${titleText}</h3><div class="chart-actions-group"></div>`;
                container.parentNode.insertBefore(header, container);
            }
            
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

function getExportBlocks(container) {
    let blocks = [];
    let currentHeader = null;
    const nodes = Array.from(container.children);
    
    for (let node of nodes) {
        if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE' || node.style.display === 'none') continue;
        
        // Mantener el encabezado principal intacto
        if (node.classList.contains('aiq-reports-header')) {
             blocks.push({ elements: [node], isIsolatedCard: false });
             continue;
        }

        const isHeader = node.classList.contains('chart-header-flex') || node.tagName.match(/^H[1-6]$/);
        
        if (isHeader) {
            // Si ya teníamos un header en memoria (ej. dos títulos seguidos), lo liberamos como bloque
            if (currentHeader) blocks.push({ elements: [currentHeader], isIsolatedCard: false });
            currentHeader = node;
        } else {
            // Si es el contenedor de Temas, separamos las tarjetas 1 a 1.
            if (node.classList.contains('topics-tables-container')) {
                const cards = Array.from(node.children);
                for (let i = 0; i < cards.length; i++) {
                    let group = [];
                    if (currentHeader) group.push(currentHeader); // Le pegamos el título general a cada tarjeta individual
                    group.push(cards[i]);
                    // Marcamos "isIsolatedCard" para que el motor asigne 1 página forzosa
                    blocks.push({ elements: group, isIsolatedCard: true }); 
                }
            } else {
                // Comportamiento normal para otras secciones (gráficos, top/bottom)
                let group = [];
                if (currentHeader) group.push(currentHeader);
                group.push(node);
                blocks.push({ elements: group, isIsolatedCard: false });
            }
            currentHeader = null;
        }
    }
    
    if (currentHeader) blocks.push({ elements: [currentHeader], isIsolatedCard: false });
    return blocks;
}

async function exportFullPageToPDF(surveyName, surveyTitle) {
    const btnExport = document.getElementById('btn-export-full-pdf');
    const originalBtnText = btnExport ? btnExport.innerHTML : '';
    
    // Variables para guardar y restaurar el estilo original del Grid
    const topicContainers = document.querySelectorAll('.topics-tables-container');
    const originalGridStyles = [];
    
    try {
        if (btnExport) btnExport.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Procesando PDF...';

        const wrapper = document.querySelector('.aiq-reports-wrapper');
        const originalHeight = wrapper.style.height;
        const originalOverflow = wrapper.style.overflowY;
        
        // Liberar el scroll del contenedor principal
        wrapper.style.height = 'auto';
        wrapper.style.overflowY = 'visible';
        
        // Forzar 1 sola columna en el contenedor de Temas para que las tarjetas tomen el 100% del ancho (Mejor lectura en PDF)
        topicContainers.forEach(c => {
            originalGridStyles.push({ el: c, gridTemplateColumns: c.style.gridTemplateColumns });
            c.style.gridTemplateColumns = '1fr'; 
        });
        
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
        
        // Obtenemos los bloques ya separados (Cada tabla de tema ahora es un bloque independiente)
        const blocksInfo = getExportBlocks(wrapper);

        const canvasOpts = { 
            scale: 2, 
            useCORS: true, 
            logging: false, 
            backgroundColor: '#ffffff',
            onclone: (clonedDoc) => {
                const svgs = clonedDoc.querySelectorAll('.apexcharts-svg');
                svgs.forEach(svg => { svg.setAttribute('width', '100%'); });
            }
        };

        for (let i = 0; i < blocksInfo.length; i++) {
            const blockInfo = blocksInfo[i];
            const elements = blockInfo.elements;
            let blockImages = [];
            
            // Si el bloque exige aislamiento (1 carta de Tema), forzamos salto de página ANTES de pintarla
            if (blockInfo.isIsolatedCard && currentY > margin) {
                pdf.addPage();
                currentY = margin;
            }
            
            for (let el of elements) {
                await new Promise(resolve => setTimeout(resolve, 50)); // Respiración del procesador
                
                const canvas = await html2canvas(el, canvasOpts);
                if (canvas.width === 0 || canvas.height === 0) continue;
                
                const imgData = canvas.toDataURL('image/jpeg', 0.95);
                const pdfImgHeight = (canvas.height * maxPdfWidth) / canvas.width;
                
                blockImages.push({ 
                    imgData, 
                    width: maxPdfWidth, 
                    height: pdfImgHeight, 
                    isHeader: el.classList.contains('chart-header-flex') || el.tagName.match(/^H[1-6]$/) 
                });
                
                canvas.width = 0; // Garbage collection forzada
            }
            
            if (blockImages.length === 0) continue;

            let totalOriginalHeight = blockImages.reduce((sum, img) => sum + img.height, 0);
            let totalGaps = blockImages.reduce((sum, img, idx) => sum + (idx < blockImages.length - 1 ? (img.isHeader ? 2 : 8) : 0), 0);
            
            // Si el bloque (Título + Gráfico) en su tamaño original no cabe, saltar hoja
            if (currentY + totalOriginalHeight + totalGaps > maxPageHeight + margin) {
                if (currentY > margin) {
                    pdf.addPage();
                    currentY = margin;
                }
            }

            // Calcular cuánto espacio queda realmente en la página activa
            let availableSpace = (maxPageHeight + margin) - currentY;
            
            // Si incluso estando solos en una página la tabla gigante no cabe, la encogemos (Zoom Out)
            let needsScaling = (totalOriginalHeight + totalGaps > availableSpace);
            let scaleRatio = 1;
            
            if (needsScaling) {
                let nonHeaderOriginalHeight = blockImages.filter(img => !img.isHeader).reduce((sum, img) => sum + img.height, 0);
                let headerOriginalHeight = blockImages.filter(img => img.isHeader).reduce((sum, img) => sum + img.height, 0);
                
                let targetNonHeaderHeight = availableSpace - headerOriginalHeight - totalGaps;
                if (targetNonHeaderHeight > 0 && nonHeaderOriginalHeight > 0) {
                    scaleRatio = targetNonHeaderHeight / nonHeaderOriginalHeight;
                }
            }

            for (let imgObj of blockImages) {
                let renderWidth = imgObj.width;
                let renderHeight = imgObj.height;
                
                // Solo escalar el contenido (gráficos/tablas gigantes), dejar el texto del título intacto
                if (needsScaling && !imgObj.isHeader && scaleRatio < 1) {
                    renderHeight = renderHeight * scaleRatio;
                    renderWidth = renderWidth * scaleRatio;
                }
                
                let xOffset = margin;
                if (renderWidth < maxPdfWidth) {
                    xOffset = margin + ((maxPdfWidth - renderWidth) / 2); // Centrado horizontal
                }
                
                pdf.addImage(imgObj.imgData, 'JPEG', xOffset, currentY, renderWidth, renderHeight);
                currentY += renderHeight + (imgObj.isHeader ? 2 : 8); 
            }
            
            // Si acabamos de procesar una carta aislada (Tema), obligamos a que lo próximo vaya en OTRA página.
            if (blockInfo.isIsolatedCard) {
                currentY = maxPageHeight + margin + 1; 
            } else {
                currentY += 8; 
            }
        }

        // Restaurar estado visual original de la pantalla
        topicContainers.forEach((c, idx) => {
            c.style.gridTemplateColumns = originalGridStyles[idx].gridTemplateColumns;
        });
        wrapper.style.height = originalHeight;
        wrapper.style.overflowY = originalOverflow;
        buttonsToHide.forEach(btn => btn.style.display = '');
        if (btnExport) btnExport.innerHTML = originalBtnText;

        const cleanTitle = (surveyTitle || surveyName || 'Resultados').replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        pdf.save(`Reporte_${cleanTitle}.pdf`);

    } catch (err) {
        console.error('Error construyendo PDF:', err);
        
        // Restauración segura en caso de fallo
        const wrapper = document.querySelector('.aiq-reports-wrapper');
        if (wrapper) {
            wrapper.style.height = 'calc(100vh - 80px)';
            wrapper.style.overflowY = 'auto';
        }
        
        const topicContainersErr = document.querySelectorAll('.topics-tables-container');
        topicContainersErr.forEach(c => c.style.gridTemplateColumns = ''); 
        
        document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple')
            .forEach(btn => btn.style.display = '');
            
        if (btnExport) btnExport.innerHTML = originalBtnText;
        if (window.frappe) frappe.msgprint('Ocurrió un error al construir el PDF.');
    }
}