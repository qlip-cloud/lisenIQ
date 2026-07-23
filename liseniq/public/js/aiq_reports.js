document.addEventListener('DOMContentLoaded', async function() {
    const params = new URLSearchParams(window.location.search);
    const surveyName = params.get('survey_name');
    
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
            exportFullPageToPDF(surveyName, finalSurveyTitle);
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
        
        // Obtener el Título de medición
        const titleEl = document.getElementById('report-survey-title');
        const rawTitle = titleEl ? titleEl.innerText.trim() : 'Reporte';
        const cleanTitle = rawTitle.replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        
        // Obtener y formatear el título de la sección
        let sectionTitle = header.querySelector('.chart-section-title')?.innerText || 'Seccion';
        sectionTitle = sectionTitle.trim().replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        
        // Armar el nombre final del archivo
        const fileName = `Reporte_${sectionTitle}_${cleanTitle}`;
        
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

// Extrae de forma plana todas las páginas que componen el PDF
function getExportPages(container) {
    const pages = [];
    let activeHeaders = [];

    function traverse(node) {
        if (node.nodeType !== 1) return;
        
        // Ignorar scripts, estilos y nodos ocultos/invisibles
        const style = window.getComputedStyle(node);
        if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE' || style.display === 'none' || style.opacity === '0' || node.offsetHeight === 0) {
            return;
        }

        //Headers (Título principal de página y títulos de sección)
        const isHeader = node.classList.contains('aiq-reports-header') || 
                         node.classList.contains('chart-header-flex') || 
                         node.tagName.match(/^H[1-6]$/);
        
        if (isHeader) {
            activeHeaders.push(node);
            return; // Se guarda en memoria para inyectarlo al próximo contenido visual
        }

        // ontenedores de Grillas que deben separarse
        // Si hay una grilla de tablas top/bottom o múltiples gráficos, los separamos y copiamos el título
        const isGridToSplit = node.classList.contains('top-bottom-container') || 
                              node.classList.contains('topics-tables-container') || 
                              node.classList.contains('contacts-charts-grid');
        
        if (isGridToSplit) {
            const children = Array.from(node.children).filter(c => c.nodeType === 1);
            children.forEach(child => {
                // Cada elemento interno se va a una página distinta pero comparte el título de sección
                pages.push({ headers: [...activeHeaders], content: child });
            });
            activeHeaders = []; // Se consumen los headers para no repetirlos luego
            return;
        }

        // Contenedores Individuales que requieren una página completa
        const isSinglePageItem = node.classList.contains('metrics-container') || 
                                 node.classList.contains('chart-card') || 
                                 node.classList.contains('tb-card');

        if (isSinglePageItem) {
            pages.push({ headers: [...activeHeaders], content: node });
            activeHeaders = []; // Se consumen los headers
            return;
        }

        // Si es un contenedor de agrupamiento genérico (ej. un Include div), buscamos dentro
        const children = Array.from(node.children);
        if (children.length > 0) {
            children.forEach(child => traverse(child));
        }
    }

    // Iniciamos la búsqueda recursiva a partir del contenedor envolvente
    Array.from(container.children).forEach(child => traverse(child));
    
    // Por si quedó algún título huérfano sin contenido
    if (activeHeaders.length > 0) {
        pages.push({ headers: [...activeHeaders], content: null });
    }
    
    return pages;
}

// Exportar TODO el reporte asignando forzosamente 1 página a cada gráfico/tabla
async function exportFullPageToPDF(surveyName, surveyTitle) {
    const btnExport = document.getElementById('btn-export-full-pdf');
    const originalBtnText = btnExport ? btnExport.innerHTML : '';
    
    try {
        if (btnExport) btnExport.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Exportando...';

        // Pequeña pausa para permitir que el navegador renderice el estado de "Exportando..." 
        // y no congele la UI inmediatamente.
        await new Promise(resolve => setTimeout(resolve, 50));

        const wrapper = document.querySelector('.aiq-reports-wrapper');
        const originalHeight = wrapper.style.height;
        const originalOverflow = wrapper.style.overflowY;
        
        // Desbloquear restricciones de altura para que html2canvas pinte todo
        wrapper.style.height = 'auto';
        wrapper.style.overflowY = 'visible';
        
        // Ocultamos TODOS los botones visuales para que no ensucien el reporte
        const buttonsToHide = document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple, .btn-export-section-pdf, .btn-export-section-img');
        buttonsToHide.forEach(btn => btn.style.display = 'none');

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        
        const margin = 10;
        const maxPdfWidth = pdfWidth - (margin * 2);

        // Obtenemos todos los componentes ordenados en páginas separadas con sus respectivos títulos
        const pagesInfo = getExportPages(wrapper);

        let isFirstPage = true;

        for (let i = 0; i < pagesInfo.length; i++) {
            // Liberar el hilo principal periódicamente (Yielding) para evitar que el navegador
            // bloquee la UI o arroje alertas de "Página no responde".
            await new Promise(resolve => setTimeout(resolve, 50));
            
            const pageInfo = pagesInfo[i];
            
            // A partir del segundo componente forzamos siempre un salto de página
            if (!isFirstPage) {
                pdf.addPage();
            }
            isFirstPage = false;
            
            let currentY = margin;

            // Dibujar los Headers / Títulos asignados a esta página
            for (let header of pageInfo.headers) {
                const headerCanvas = await html2canvas(header, { scale: 2, useCORS: true, logging: false, backgroundColor: '#ffffff' });
                if (headerCanvas.width > 0 && headerCanvas.height > 0) {
                    const imgData = headerCanvas.toDataURL('image/png');
                    const pdfImgHeight = (headerCanvas.height * maxPdfWidth) / headerCanvas.width;
                    pdf.addImage(imgData, 'PNG', margin, currentY, maxPdfWidth, pdfImgHeight);
                    currentY += pdfImgHeight + 3; // Margen bajo el título
                }
                
                // Forzar limpieza de memoria del canvas utilizado
                headerCanvas.width = 0;
                headerCanvas.height = 0;
            }

            // Dibujar el Contenedor/Gráfico principal de esta página
            if (pageInfo.content) {
                const contentCanvas = await html2canvas(pageInfo.content, { scale: 2, useCORS: true, logging: false, backgroundColor: '#ffffff' });
                if (contentCanvas.width > 0 && contentCanvas.height > 0) {
                    const imgData = contentCanvas.toDataURL('image/png');
                    const pdfImgHeight = (contentCanvas.height * maxPdfWidth) / contentCanvas.width;
                    
                    // Verificamos si, a pesar de estar en una página nueva, el elemento sobrepasa el límite vertical (Ej: una tabla gigante)
                    if (currentY + pdfImgHeight > pageHeight - margin) {
                        
                        // Si el contenido POR SÍ SOLO es más grande que una página entera
                        if (pdfImgHeight > pageHeight - (margin * 2)) {
                            let heightLeft = pdfImgHeight;
                            let position = currentY;

                            pdf.addImage(imgData, 'PNG', margin, position, maxPdfWidth, pdfImgHeight);
                            heightLeft -= (pageHeight - currentY);

                            // Agregar las páginas extra necesarias para terminar de renderizar el elemento gigante
                            while (heightLeft > 0) {
                                pdf.addPage();
                                position -= pageHeight; // offset negativo para desplazar la imagen hacia arriba
                                pdf.addImage(imgData, 'PNG', margin, position, maxPdfWidth, pdfImgHeight);
                                heightLeft -= pageHeight;
                            }
                        } else {
                            // El contenido cabe en una página, pero debido al Header superior se desbordó un poco.
                            // Solución: Lo encogemos de forma proporcional para que encaje perfecto en el espacio que queda.
                            const availableHeight = pageHeight - currentY - margin;
                            const ratio = availableHeight / pdfImgHeight;
                            const newWidth = maxPdfWidth * ratio;
                            const newHeight = pdfImgHeight * ratio;
                            
                            // Centramos horizontalmente el gráfico redimensionado
                            const xOffset = margin + (maxPdfWidth - newWidth) / 2;
                            pdf.addImage(imgData, 'PNG', xOffset, currentY, newWidth, newHeight);
                        }
                    } else {
                        // El componente entra perfectamente en la hoja junto a su título
                        pdf.addImage(imgData, 'PNG', margin, currentY, maxPdfWidth, pdfImgHeight);
                    }
                }
                
                // Forzar limpieza de memoria del canvas utilizado para evitar Out of Memory
                contentCanvas.width = 0;
                contentCanvas.height = 0;
            }
        }

        // Devolvemos la UI a su estado normal
        wrapper.style.height = originalHeight;
        wrapper.style.overflowY = originalOverflow;
        buttonsToHide.forEach(btn => btn.style.display = '');
        if (btnExport) btnExport.innerHTML = originalBtnText;

        // Limpiar y formatear el título real para usarlo como nombre de archivo
        const safeTitle = (surveyTitle || surveyName || 'Resultados').replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');

        // Iniciar descarga
        pdf.save(`Reporte_${safeTitle}.pdf`);

    } catch (err) {
        console.error('Error exportando reporte completo:', err);
        
        // Restaurar estado en caso de error crítico
        const wrapper = document.querySelector('.aiq-reports-wrapper');
        if (wrapper) {
            wrapper.style.height = 'calc(100vh - 80px)';
            wrapper.style.overflowY = 'auto';
        }
        document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple, .btn-export-section-pdf, .btn-export-section-img')
            .forEach(btn => btn.style.display = '');
            
        if (btnExport) btnExport.innerHTML = originalBtnText;

        if (window.frappe) {
            frappe.msgprint('Ocurrió un error al intentar exportar el reporte.');
        }
    }
}