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

    // Inicializar observador para inyectar botones dinámicamente
    observeAndInjectButtons();

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
            // Importación dinámica del módulo específico de Cultura
            const cultureModule = await import('/assets/liseniq/js/reports/report_culture.js');
            cultureModule.initCultureReport(config.data, surveyName);
        } catch (err) {
            console.error("Error al cargar el módulo del reporte de Cultura", err);
        }
    } else if (mnemonic === 'template_engagement') {
        try {
            // Importación dinámica del módulo específico de Engagement
            const engagementModule = await import('/assets/liseniq/js/reports/report_by_engagement.js');
            engagementModule.initEngagementReport(config.data, surveyName);
        } catch (err) {
            console.error("Error al cargar el módulo del reporte de Engagement", err);
        }
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
// Lógica de inyección y exportación de secciones individuales
// Observa el DOM en caso de que los módulos carguen los grids dinámicamente 
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
        
        // Se capturan ambos elementos separados para evitar alterar el DOM 
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
        
        // Obtener el ID de medición desde la URL
        const params = new URLSearchParams(window.location.search);
        const surveyId = params.get('survey_name') || 'ID_Desconocido';
        
        // Obtener y formatear el título de la sección
        let sectionTitle = header.querySelector('.chart-section-title')?.innerText || 'Seccion';
        sectionTitle = sectionTitle.trim().replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        
        // Armar el nombre final del archivo
        const fileName = `Reporte_${sectionTitle}_${surveyId}`;
        
        if (type === 'img') {
            // Exportar a JPG con calidad máxima
            const imgData = combinedCanvas.toDataURL('image/jpeg', 1.0);
            const link = document.createElement('a');
            link.download = `${fileName}.jpg`;
            link.href = imgData;
            link.click();
        } else if (type === 'pdf') {
            // Se mantiene PNG internamente para evitar compresión en el PDF
            const imgData = combinedCanvas.toDataURL('image/png');
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', 'a4');
            const pdfWidth = pdf.internal.pageSize.getWidth();
            const margin = 10;
            const maxPdfWidth = pdfWidth - (margin * 2);
            
            let pdfImgWidth = maxPdfWidth;
            let pdfImgHeight = (combinedCanvas.height * pdfImgWidth) / combinedCanvas.width;
            
            // Escalar si excede el alto de la página individual
            if (pdfImgHeight > pdf.internal.pageSize.getHeight() - (margin * 2)) {
                const ratio = (pdf.internal.pageSize.getHeight() - (margin * 2)) / pdfImgHeight;
                pdfImgHeight = pdfImgHeight * ratio;
                pdfImgWidth = pdfImgWidth * ratio;
            }
            
            pdf.addImage(imgData, 'PNG', margin, margin, pdfImgWidth, pdfImgHeight);
            pdf.save(`${fileName}.pdf`);
        }
    } catch(e) {
        console.error('Error al exportar seccion:', e);
        if (window.frappe) frappe.msgprint('Error al exportar la sección.');
    } finally {
        if (actionsGroup) actionsGroup.style.display = '';
    }
}

// Lógica rediseñada para exportación total (previene cortes de gráficos)
// Recorre recursivamente para agrupar dinámicamente títulos con sus gráficos
function getExportBlocks(container) {
    let blocks = [];
    const nodes = Array.from(container.children);
    let currentGroup = [];
    
    for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        const style = window.getComputedStyle(node);
        
        if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE' || style.display === 'none' || node.offsetHeight === 0) {
            continue;
        }
        
        // Bloques que no debemos fragmentar por dentro
        const keepTogetherClasses = ['metrics-container', 'top-bottom-container', 'topics-tables-container', 'contacts-charts-grid', 'chart-card'];
        const isKeepTogether = keepTogetherClasses.some(c => node.classList.contains(c));
        
        // Si es un div wrapper de includes sin clase semántica, evaluamos sus hijos
        if (!isKeepTogether && node.tagName === 'DIV' && !node.classList.contains('chart-header-flex') && !node.classList.contains('aiq-reports-header')) {
            const hasSubBlocks = node.querySelector('.chart-card, .metric-card, .tb-card, .chart-header-flex, .top-bottom-container, .topics-tables-container');
            if (hasSubBlocks) {
                if (currentGroup.length > 0) {
                    blocks.push({ elements: currentGroup });
                    currentGroup = [];
                }
                blocks.push(...getExportBlocks(node));
                continue;
            }
        }

        // Agrupar TODOS los títulos consecutivos con su correspondiente contenedor de contenido
        const isHeader = node.classList.contains('chart-header-flex') || node.tagName.match(/^H[1-6]$/);

        if (isHeader) {
            currentGroup.push(node);
        } else {
            currentGroup.push(node); // Conectar contenido principal al grupo de headers
            blocks.push({ elements: currentGroup }); // Cerrar el bloque completo
            currentGroup = [];
        }
    }
    
    // Anexar cualquier grupo huérfano al final del DOM
    if (currentGroup.length > 0) {
        blocks.push({ elements: currentGroup });
    }
    
    return blocks;
}

// Exportar TODO el reporte a un PDF multi-página, bloque por bloque
async function exportFullPageToPDF(surveyName) {
    const btnExport = document.getElementById('btn-export-full-pdf');
    const originalBtnText = btnExport ? btnExport.innerHTML : '';
    
    try {
        if (btnExport) btnExport.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Exportando...';

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
        let currentY = margin;

        const blocksInfo = getExportBlocks(wrapper);

        for (let i = 0; i < blocksInfo.length; i++) {
            const blockInfo = blocksInfo[i];
            const elements = blockInfo.elements;
            
            const capturedImages = [];
            let totalHeightInPdf = 0;
            
            // Capturar elementos del grupo
            for (let el of elements) {
                const canvas = await html2canvas(el, { scale: 2, useCORS: true, logging: false, backgroundColor: '#ffffff' });
                if (canvas.width === 0 || canvas.height === 0) continue;
                
                const imgData = canvas.toDataURL('image/png');
                if (!imgData || imgData === 'data:,') continue;
                
                const pdfImgHeight = (canvas.height * maxPdfWidth) / canvas.width;
                
                capturedImages.push({ imgData, pdfImgWidth: maxPdfWidth, pdfImgHeight });
                totalHeightInPdf += pdfImgHeight;
            }
            
            if (capturedImages.length === 0) continue;

            //  Comprobar Salto de Página agrupado
            // Si el bloque de (Título + Gráfico) es mayor al espacio restante, los bajamos JUNTOS a una nueva pág
            if (currentY + totalHeightInPdf > pageHeight - margin) {
                if (currentY > margin) {
                    pdf.addPage();
                    currentY = margin;
                }
            }

            //  Dibujar
            for (let imgObj of capturedImages) {
                if (imgObj.pdfImgHeight > pageHeight - (margin * 2)) {
                    // Solo aplica recorte ciego si el propio elemento único es más alto que una página A4 completa
                    let heightLeft = imgObj.pdfImgHeight;
                    let position = currentY;

                    pdf.addImage(imgObj.imgData, 'PNG', margin, position, imgObj.pdfImgWidth, imgObj.pdfImgHeight);
                    heightLeft -= (pageHeight - currentY);

                    while (heightLeft > 0) {
                        pdf.addPage();
                        position -= pageHeight;
                        pdf.addImage(imgObj.imgData, 'PNG', margin, position, imgObj.pdfImgWidth, imgObj.pdfImgHeight);
                        heightLeft -= pageHeight;
                    }
                    currentY = position + imgObj.pdfImgHeight + (margin / 2); 
                } else {
                    // Por si un grupo era más alto que la página
                    if (currentY + imgObj.pdfImgHeight > pageHeight - margin) {
                        pdf.addPage();
                        currentY = margin;
                    }
                    pdf.addImage(imgObj.imgData, 'PNG', margin, currentY, imgObj.pdfImgWidth, imgObj.pdfImgHeight);
                    currentY += imgObj.pdfImgHeight + 1; // Espacio entre elementos del mismo grupo
                }
            }
            currentY += (margin / 1.5); // Espacio semántico entre diferentes grupos (Ej: un chart vs otro)
        }

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