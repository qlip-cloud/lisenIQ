document.addEventListener('DOMContentLoaded', async function() {
    const params = new URLSearchParams(window.location.search);
    const surveyName = params.get('survey_name');
    
    // Obtenemos el título real directamente del DOM
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

    // Cargamos dom-to-image-more
    try {
        await Promise.all([loadApexCharts(), loadJsPDF(), loadDomToImage()]);
    } catch (e) {
        console.error("Fallo al cargar librerías externas", e);
        return;
    }

    observeAndInjectButtons();

    // Evento Global de Exportación
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
            const cultureModule = await import('/assets/liseniq/js/reports/report_culture.js');
            cultureModule.initCultureReport(config.data, surveyName);
        } catch (err) {
            console.error("Error al cargar el módulo del reporte de Cultura", err);
        }
    } else if (mnemonic === 'template_engagement') {
        try {
            const engagementModule = await import('/assets/liseniq/js/reports/report_by_engagement.js');
            engagementModule.initEngagementReport(config.data, surveyName);
        } catch (err) {
            console.error("Error al cargar el módulo del reporte de Engagement", err);
        }
    }
});

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

function loadDomToImage() {
    return new Promise((resolve, reject) => {
        if (window.domtoimage) return resolve();
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/dom-to-image-more/3.1.6/dom-to-image-more.min.js';
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
                
                header.innerHTML = `
                    <h3 class="chart-section-title">${titleText}</h3>
                    <div class="chart-actions-group"></div>
                `;
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

async function captureElement(element) {
    if (!element) return null;
    try {
        const opts = { 
            quality: 0.95, 
            bgcolor: '#ffffff', 
            scale: 2,
            style: { margin: '0', transform: 'scale(1)', transformOrigin: 'top left' }
        };
        const dataUrl = await domtoimage.toJpeg(element, opts);
        const rect = element.getBoundingClientRect();
        return { imgData: dataUrl, width: rect.width, height: rect.height };
    } catch (err) {
        console.warn("Error capturando elemento", element, err);
        return null;
    }
}

async function exportSingleSection(container, header, type) {
    const actionsGroup = header.querySelector('.chart-actions-group');
    if (actionsGroup) actionsGroup.style.display = 'none';
    
    try {
        const headerData = await captureElement(header);
        const containerData = await captureElement(container);
        
        if (!headerData || !containerData) throw new Error("Fallo en captura de imagen");
        
        // Obtener ID
        const params = new URLSearchParams(window.location.search);
        const surveyId = params.get('survey_name') || 'ID_Desconocido';
        let sectionTitle = header.querySelector('.chart-section-title')?.innerText || 'Seccion';
        sectionTitle = sectionTitle.trim().replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        const fileName = `Reporte_${sectionTitle}_${surveyId}`;
        
        if (type === 'pdf') {
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('p', 'mm', 'a4');
            const maxW = pdf.internal.pageSize.getWidth() - 20;
            const pageH = pdf.internal.pageSize.getHeight();
            
            let currentY = 10;
            
            // Draw Header
            let hPdfH = (headerData.height * maxW) / headerData.width;
            pdf.addImage(headerData.imgData, 'JPEG', 10, currentY, maxW, hPdfH);
            currentY += hPdfH + 5;
            
            // Draw Container
            let cPdfH = (containerData.height * maxW) / containerData.width;
            let cPdfW = maxW;
            
            // Escalar si no cabe
            if (cPdfH > pageH - currentY - 10) {
                const ratio = (pageH - currentY - 10) / cPdfH;
                cPdfH *= ratio;
                cPdfW *= ratio;
            }
            
            // Centrar si fue escalado
            let xPos = 10 + (maxW - cPdfW) / 2;
            pdf.addImage(containerData.imgData, 'JPEG', xPos, currentY, cPdfW, cPdfH);
            pdf.save(`${fileName}.pdf`);
        } else {
             const link = document.createElement('a');
             link.download = `${fileName}.jpg`;
             link.href = containerData.imgData; 
             link.click();
        }

    } catch(e) {
        console.error('Error al exportar seccion:', e);
        if (window.frappe) frappe.msgprint('Error al exportar la sección.');
    } finally {
        if (actionsGroup) actionsGroup.style.display = '';
    }
}

function buildExportJobs(wrapper) {
    let jobs = [];
    let currentHeader = null;

    function processNodes(nodes) {
        Array.from(nodes).forEach(node => {
            if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE' || node.style.display === 'none') return;

            if (node.classList.contains('aiq-reports-header')) {
                jobs.push({ type: 'header', el: node });
            }
            else if (node.classList.contains('chart-header-flex') || node.tagName.match(/^H[1-6]$/)) {
                currentHeader = node; 
            }
            else if (node.classList.contains('top-bottom-container') || node.classList.contains('topics-tables-container')) {
                const cards = Array.from(node.querySelectorAll('.tb-card'));
                cards.forEach((card) => {
                    jobs.push({ 
                        type: 'isolated_card', 
                        header: currentHeader, 
                        el: card 
                    });
                });
                currentHeader = null; 
            }
            else if (node.classList.contains('metrics-container') || node.classList.contains('chart-card') || node.classList.contains('contacts-charts-grid')) {
                jobs.push({ type: 'block', header: currentHeader, el: node });
                currentHeader = null;
            }
            else if (node.tagName === 'DIV' && node.children.length > 0 && !node.classList.contains('tb-row')) {
                processNodes(node.children);
            }
        });
    }

    processNodes(wrapper.children);
    return jobs;
}

async function exportFullPageToPDF(surveyName, surveyTitle) {
    const btnExport = document.getElementById('btn-export-full-pdf');
    const originalBtnText = btnExport ? btnExport.innerHTML : '';
    
    // Guardamos la posición de scroll actual y subimos
    const prevScrollY = window.scrollY;
    window.scrollTo(0, 0);

    try {
        if (btnExport) btnExport.innerHTML = `<i class="fa fa-spinner fa-spin"></i> Exportando...`;

        const wrapper = document.querySelector('.aiq-reports-wrapper');
        const originalHeight = wrapper.style.height;
        const originalOverflow = wrapper.style.overflowY;
        
        wrapper.style.height = 'auto';
        wrapper.style.overflowY = 'visible';
        
        const buttonsToHide = document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple');
        buttonsToHide.forEach(btn => btn.style.display = 'none');

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');
        const margin = 10;
        const maxW = pdf.internal.pageSize.getWidth() - (margin * 2);
        const pageH = pdf.internal.pageSize.getHeight();
        let currentY = margin;

        const jobs = buildExportJobs(wrapper);

        function addImg(data) {
            if (!data) return;
            let pdfW = maxW;
            let pdfH = (data.height * maxW) / data.width;

            if (pdfH > pageH - currentY - margin) {
                const ratio = (pageH - currentY - margin) / pdfH;
                pdfH *= ratio;
                pdfW *= ratio;
            }
            
            let xPos = margin + (maxW - pdfW) / 2;
            pdf.addImage(data.imgData, 'JPEG', xPos, currentY, pdfW, pdfH);
            currentY += pdfH + 5;
        }

        for (let i = 0; i < jobs.length; i++) {
            const job = jobs[i];
            
            if (job.type === 'header') {
                const data = await captureElement(job.el);
                addImg(data);
            } 
            else if (job.type === 'block') {
                let headerData = job.header ? await captureElement(job.header) : null;
                const blockData = await captureElement(job.el);

                let totalH = blockData ? (blockData.height * maxW) / blockData.width : 0;
                if (headerData) totalH += (headerData.height * maxW) / headerData.width;

                if (currentY + totalH > pageH - margin && currentY > margin) {
                    pdf.addPage();
                    currentY = margin;
                }

                if (headerData) addImg(headerData);
                if (blockData) addImg(blockData);
                currentY += 5; 
            }
            else if (job.type === 'isolated_card') {
                if (currentY > margin) {
                    pdf.addPage();
                    currentY = margin;
                }

                const origGridCol = job.el.style.gridColumn;
                job.el.style.gridColumn = '1 / -1'; 

                let headerData = job.header ? await captureElement(job.header) : null;
                const cardData = await captureElement(job.el);

                job.el.style.gridColumn = origGridCol;

                if (headerData) addImg(headerData);
                if (cardData) addImg(cardData);

                if (i < jobs.length - 1) {
                    pdf.addPage();
                    currentY = margin;
                }
            }
        }

        wrapper.style.height = originalHeight;
        wrapper.style.overflowY = originalOverflow;
        buttonsToHide.forEach(btn => btn.style.display = '');
        if (btnExport) btnExport.innerHTML = originalBtnText;
        window.scrollTo(0, prevScrollY);

        const cleanTitle = surveyTitle.replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, '_');
        pdf.save(`${cleanTitle}.pdf`);

    } catch (err) {
        console.error('Error exportando reporte completo:', err);
        
        const wrapper = document.querySelector('.aiq-reports-wrapper');
        if (wrapper) {
            wrapper.style.height = 'calc(100vh - 80px)';
            wrapper.style.overflowY = 'auto';
        }
        document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple')
            .forEach(btn => btn.style.display = '');
            
        if (btnExport) btnExport.innerHTML = originalBtnText;
        window.scrollTo(0, prevScrollY);

        if (window.frappe) {
            frappe.msgprint('Ocurrió un error al intentar exportar el reporte.');
        }
    }
}