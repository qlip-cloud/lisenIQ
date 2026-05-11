let cultureChartInstance = null;
let dimensionChartInstance = null;
let cultureChartType = 'bar'; 
let dimensionChartType = 'bar'; 

document.addEventListener('DOMContentLoaded', async function() {
    const params = new URLSearchParams(window.location.search);
    const surveyName = params.get('survey_name');
    const surveyTitle = params.get('survey_title') || 'Reporte de Resultados';

    if (!surveyName) {
        frappe.msgprint({
            title: 'Error',
            indicator: 'red',
            message: 'No se ha especificado ninguna medición para graficar.'
        });
        return;
    }

    const titleElement = document.getElementById('report-survey-title');
    if (titleElement) titleElement.textContent = surveyTitle;

    // Cargamos de forma asíncrona los gráficos, pdf y html2canvas para la captura completa
    try {
        await Promise.all([loadApexCharts(), loadJsPDF(), loadHtml2Canvas()]);
    } catch (e) {
        console.error("Fallo al cargar librerías externas", e);
        return;
    }

    let appFeatures = [];
    try {
        appFeatures = typeof window.liseniqAppFeatures === 'string' ? JSON.parse(window.liseniqAppFeatures) : (window.liseniqAppFeatures || []);
    } catch(e) {
        console.error("Error parseando features", e);
    }

    const hideSection = (headerId, cardId) => {
        const header = document.getElementById(headerId);
        if (header) header.style.display = 'none';
        const card = document.getElementById(cardId);
        if (card) card.style.display = 'none';
    };

    // Inicializamos la sección de top 10 y bottom 10
    initTopBottomCards();

    // Evento de Exportación Global (Todo el reporte)
    const btnExportFullPdf = document.getElementById('btn-export-full-pdf');
    if (btnExportFullPdf) {
        btnExportFullPdf.addEventListener('click', () => {
            exportFullPageToPDF(surveyName);
        });
    }

    // Gráfico de Cultura
    if (appFeatures.includes('aiq_rep_cultura')) {
        renderCultureChart(cultureChartType);
        
        // Evento de botón Alternador (Toggle)
        const btnCulture = document.getElementById('btn-toggle-culture');
        if (btnCulture) {
            btnCulture.addEventListener('click', function() {
                cultureChartType = cultureChartType === 'bar' ? 'pie' : 'bar';
                const icon = cultureChartType === 'bar' ? 'fa-pie-chart' : 'fa-bar-chart';
                const tooltipText = cultureChartType === 'bar' ? 'Ver Gráfico de Torta' : 'Ver Gráfico de Barras';
                
                this.title = tooltipText;
                this.innerHTML = `<i class="fa ${icon}" aria-hidden="true"></i>`;
                
                renderCultureChart(cultureChartType);
            });
        }

        // Eventos de Exportación individuales
        const btnExpImgCulture = document.getElementById('btn-export-culture-img');
        if (btnExpImgCulture) {
            btnExpImgCulture.addEventListener('click', () => {
                exportChart(cultureChartInstance, `Reporte_Cultura_${surveyName}`, 'img');
            });
        }
        const btnExpPdfCulture = document.getElementById('btn-export-culture-pdf');
        if (btnExpPdfCulture) {
            btnExpPdfCulture.addEventListener('click', () => {
                exportChart(cultureChartInstance, `Reporte_Cultura_${surveyName}`, 'pdf');
            });
        }
    } else {
        hideSection('culture-header-container', 'culture-card-container');
    }

    // Gráfico de Dimensiones
    if (appFeatures.includes('aiq_rep_dimension')) {
        renderDimensionChart(dimensionChartType);
        
        // Evento de botón Alternador (Toggle)
        const btnDimension = document.getElementById('btn-toggle-dimension');
        if (btnDimension) {
            btnDimension.addEventListener('click', function() {
                dimensionChartType = dimensionChartType === 'bar' ? 'pie' : 'bar';
                const icon = dimensionChartType === 'bar' ? 'fa-pie-chart' : 'fa-bar-chart';
                const tooltipText = dimensionChartType === 'bar' ? 'Ver Gráfico de Torta' : 'Ver Gráfico de Barras';
                
                this.title = tooltipText;
                this.innerHTML = `<i class="fa ${icon}" aria-hidden="true"></i>`;
                
                renderDimensionChart(dimensionChartType);
            });
        }

        // Eventos de Exportación Individuales
        const btnExpImgDimension = document.getElementById('btn-export-dimension-img');
        if (btnExpImgDimension) {
            btnExpImgDimension.addEventListener('click', () => {
                exportChart(dimensionChartInstance, `Reporte_Dimensiones_${surveyName}`, 'img');
            });
        }
        const btnExpPdfDimension = document.getElementById('btn-export-dimension-pdf');
        if (btnExpPdfDimension) {
            btnExpPdfDimension.addEventListener('click', () => {
                exportChart(dimensionChartInstance, `Reporte_Dimensiones_${surveyName}`, 'pdf');
            });
        }
    } else {
        hideSection('dimension-header-container', 'dimension-card-container');
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

// Exportar TODO el reporte a un PDF multi-página
async function exportFullPageToPDF(surveyName) {
    try {
        const wrapper = document.querySelector('.aiq-reports-wrapper');
        
        // Guardar estilos originales para restaurarlos luego
        const originalHeight = wrapper.style.height;
        const originalOverflow = wrapper.style.overflowY;
        
        // Cambiar temporalmente para capturar el contenido completo sin scroll
        wrapper.style.height = 'auto';
        wrapper.style.overflowY = 'visible';
        
        // Ocultar botones temporalmente para limpiar la captura
        const buttonsToHide = document.querySelectorAll('.chart-actions-group, #btn-export-full-pdf, .btn-outline-purple');
        buttonsToHide.forEach(btn => btn.style.display = 'none');

        const canvas = await html2canvas(wrapper, {
            scale: 2, 
            useCORS: true,
            logging: false,
            backgroundColor: '#ffffff'
        });

        // Restaurar estilos y botones
        wrapper.style.height = originalHeight;
        wrapper.style.overflowY = originalOverflow;
        buttonsToHide.forEach(btn => btn.style.display = '');

        const imgData = canvas.toDataURL('image/png');
        const { jsPDF } = window.jspdf;
        
        // Crear PDF A4 formato Portrait (Vertical)
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        
        // Calculamos la altura total de la imagen en escala PDF
        const imgHeight = (canvas.height * pdfWidth) / canvas.width;
        let heightLeft = imgHeight;
        let position = 0;

        // Añadir primera página
        pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight);
        heightLeft -= pageHeight;

        // Añadir páginas extras si el reporte es largo
        while (heightLeft > 0) {
            position = position - pageHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, imgHeight);
            heightLeft -= pageHeight;
        }

        pdf.save(`Reporte_Completo_${surveyName}.pdf`);

    } catch (err) {
        console.error('Error exportando reporte completo:', err);
        if (window.frappe) {
            frappe.msgprint('Ocurrió un error al intentar exportar el reporte.');
        }
    }
}

// Función para Exportar Gráficos Individuales
async function exportChart(chartInstance, fileName, format) {
    if (!chartInstance) return;
    
    try {
        const { imgURI } = await chartInstance.dataURI();
        
        if (format === 'img') {
            const link = document.createElement('a');
            link.href = imgURI;
            link.download = `${fileName}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } 
        else if (format === 'pdf') {
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
            
            const margin = 15;
            const pdfWidth = 297 - (margin * 2);
            const pdfHeight = 210 - (margin * 2);
            
            const imgProps = pdf.getImageProperties(imgURI);
            const ratio = imgProps.width / imgProps.height;
            
            let drawWidth = pdfWidth;
            let drawHeight = pdfWidth / ratio;
            
            if (drawHeight > pdfHeight) {
                drawHeight = pdfHeight;
                drawWidth = pdfHeight * ratio;
            }
            
            const x = margin + (pdfWidth - drawWidth) / 2;
            const y = margin + (pdfHeight - drawHeight) / 2;
            
            pdf.addImage(imgURI, 'PNG', x, y, drawWidth, drawHeight);
            pdf.save(`${fileName}.pdf`);
        }
    } catch (error) {
        console.error("Error exportando el gráfico:", error);
    }
}

function parseBackendData(rawData) {
    let data = [];
    try {
        let dataStr = rawData || "[]";
        if (typeof dataStr === 'string') {
            let decodedStr = dataStr.replace(/&#34;/g, '"').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
            if (decodedStr.trim() === "" || decodedStr === '""' || decodedStr === "''") decodedStr = "[]";
            let parsed = JSON.parse(decodedStr);
            if (typeof parsed === 'string') parsed = JSON.parse(parsed);
            if (Array.isArray(parsed)) data = parsed;
        } else if (Array.isArray(rawData)) {
            data = rawData;
        }
    } catch (e) {
        console.error("Error parseando datos", e);
    }
    return data;
}

// Logica de las tarjetas Top 10 y Bottom 10
function initTopBottomCards() {
    const topContainer = document.getElementById('top-10-list');
    const bottomContainer = document.getElementById('bottom-10-list');
    if (!topContainer || !bottomContainer) return;

    // Utilizamos la nueva data 'topBottomData'
    let data = parseBackendData(window.topBottomData || window.dimensionChartData);
    if (!data || data.length === 0) return;

    let ascendingData = [...data].sort((a, b) => a.score - b.score);
    let bottom10 = ascendingData.slice(0, 10);
    let descendingData = [...data].sort((a, b) => b.score - a.score);
    let top10 = descendingData.slice(0, 10);

    const renderRows = (items, container, colorClass) => {
        container.innerHTML = items.map(item => {
            const percentage = Math.min(100, Math.max(0, (item.score / 5) * 100));
            return `
                <div class="tb-row">
                    <div class="tb-topic">${item.topic || 'N/A'}</div>
                    <div class="tb-question">${item.question || 'N/A'}</div>
                    <div class="tb-score-wrapper">
                        <div class="tb-score-bar-bg">
                            <div class="tb-score-bar-fill ${colorClass}" style="width: ${percentage}%"></div>
                        </div>
                        <div class="tb-score-value">${item.score.toFixed(2)}</div>
                    </div>
                </div>`;
        }).join('');
    };

    renderRows(top10, topContainer, 'fill-green');
    renderRows(bottom10, bottomContainer, 'fill-orange');
}

// Función Renderizadora: Gráfico de Cultura
function renderCultureChart(type) {
    const chartContainer = document.getElementById('culture-chart-container');
    if (!chartContainer) return;

    let data = parseBackendData(window.cultureChartData);
    const categories = data.map(item => item.topic || 'N/A');
    const scores = data.map(item => item.score || 0);
    const colorsArr = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'];

    if (cultureChartInstance) cultureChartInstance.destroy();

    let options = {};
    if (type === 'bar') {
        options = {
            series: [{ name: 'Puntaje Promedio', data: scores }],
            chart: { type: 'bar', height: '100%', toolbar: { show: false }, fontFamily: 'inherit' },
            colors: colorsArr,
            plotOptions: { 
                bar: { 
                    horizontal: false, 
                    columnWidth: '45%', 
                    borderRadius: 4, 
                    distributed: true,
                    dataLabels: {
                        position: 'center'
                    }
                } 
            },
            dataLabels: { 
                enabled: true,
                formatter: function (val, opts) {
                    return val.toFixed(2);
                },
                style: {
                    fontSize: '13px',
                    fontWeight: 700,
                    colors: ["#ffffff"]
                },
                dropShadow: {
                    enabled: true,
                    top: 1,
                    left: 1,
                    blur: 1,
                    color: '#000',
                    opacity: 0.45
                },
                background: {
                    enabled: false
                }
            },
            legend: { show: false },
            xaxis: {
                categories: categories,
                labels: {
                    formatter: function (value) {
                        if (typeof value !== 'string') return value;
                        const maxLength = 15;       
                        const words = value.split(' ');
                        let lines = [];
                        let currentLine = '';
                        words.forEach(word => {
                            if ((currentLine + word).length > maxLength) {
                                if (currentLine.trim()) lines.push(currentLine.trim());
                                currentLine = word + ' ';
                            } else {
                                currentLine += word + ' ';
                            }
                        });
                        if (currentLine.trim()) lines.push(currentLine.trim());
                        return lines; 
                    },
                    style: { colors: '#4b5563', fontSize: '11px', fontWeight: 500 }
                }
            },
            yaxis: { 
                max: function(max) { return max * 1.15; },
                labels: { formatter: function (val) { return val.toFixed(2); }, style: { colors: '#6b7280', fontWeight: 500 } } 
            },
            grid: { borderColor: '#f3f4f6', strokeDashArray: 4 },
            title: { text: 'Puntaje por tipo de cultura', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
            subtitle: { text: 'Promedio de respuestas (escala 1 a 5)', align: 'left', margin: 30, style: { fontSize: '13px', color: '#6b7280' } },
            tooltip: {
                custom: function({series, seriesIndex, dataPointIndex, w}) {
                    const score = series[seriesIndex][dataPointIndex];
                    const category = categories[dataPointIndex]; 
                    const color = w.config.colors[dataPointIndex % w.config.colors.length];
                    return buildCustomTooltip(category, null, score, color);
                }
            }
        };
    } else {
        options = {
            series: scores,
            labels: categories,
            chart: { type: 'pie', height: '100%', toolbar: { show: false }, fontFamily: 'inherit' },
            colors: colorsArr,
            dataLabels: {
                enabled: true,
                formatter: function (val, opts) {
                    return opts.w.config.series[opts.seriesIndex].toFixed(2);
                },
                style: { fontSize: '14px', fontFamily: 'inherit', fontWeight: 700 }
            },
            legend: { position: 'bottom' },
            title: { text: 'Puntaje por tipo de cultura', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
            subtitle: { text: 'Representación proporcional del promedio (escala 1 a 5)', align: 'left', margin: 30, style: { fontSize: '13px', color: '#6b7280' } },
            tooltip: {
                custom: function({series, seriesIndex, w}) {
                    const score = series[seriesIndex];
                    const category = w.config.labels[seriesIndex];
                    const color = w.config.colors[seriesIndex % w.config.colors.length];
                    return buildCustomTooltip(category, null, score, color);
                }
            }
        };
    }

    cultureChartInstance = new ApexCharts(chartContainer, options);
    cultureChartInstance.render();
}

// Función Renderizadora: Gráfico de Dimensiones
function renderDimensionChart(type) {
    const chartContainer = document.getElementById('dimension-chart-container');
    if (!chartContainer) return;

    let data = parseBackendData(window.dimensionChartData);
    const categories = data.map(item => item.culture || 'N/A');
    const scores = data.map(item => item.score || 0);
    const colorsArr = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4'];

    let globalScore = 0;
    const metricElements = document.querySelectorAll('.metric-value');
    if (metricElements && metricElements.length > 0) {
        const scoreText = metricElements[0].textContent.replace(',', '.').replace(/[^0-9.]/g, '');
        globalScore = parseFloat(scoreText) || 0;
    }

    if (dimensionChartInstance) dimensionChartInstance.destroy();

    let options = {};
    if (type === 'bar') {
        options = {
            series: [{ name: 'Puntaje Promedio', data: scores }],
            chart: { type: 'bar', height: '100%', toolbar: { show: false }, fontFamily: 'inherit' },
            colors: colorsArr,
            plotOptions: { 
                bar: { 
                    horizontal: false, 
                    columnWidth: '45%', 
                    borderRadius: 4, 
                    distributed: true,
                    dataLabels: {
                        position: 'center'
                    }
                } 
            },
            dataLabels: { 
                enabled: true,
                formatter: function (val, opts) {
                    return val.toFixed(2);
                },
                style: {
                    fontSize: '13px',
                    fontWeight: 700,
                    colors: ["#ffffff"]
                },
                dropShadow: {
                    enabled: true,
                    top: 1,
                    left: 1,
                    blur: 1,
                    color: '#000',
                    opacity: 0.45
                },
                background: {
                    enabled: false
                }
            },
            legend: { show: false },
            annotations: {
                yaxis: [{
                    y: globalScore.toFixed(2),
                    borderColor: '#ea580c',
                    strokeDashArray: 4,
                    borderWidth: 1.5,
                    label: {
                        borderColor: 'transparent',
                        style: { color: '#ea580c', background: 'transparent', fontSize: '12px', fontWeight: 600 },
                        text: `Promedio ${globalScore.toFixed(2)}`,
                        position: 'right', offsetX: 0, offsetY: -8
                    }
                }]
            },
            xaxis: {
                categories: categories,
                labels: {
                    formatter: function (value) {
                        if (typeof value !== 'string') return value;
                        const maxLength = 15;
                        const words = value.split(' ');
                        let lines = [];
                        let currentLine = '';
                        words.forEach(word => {
                            if ((currentLine + word).length > maxLength) {
                                if (currentLine.trim()) lines.push(currentLine.trim());
                                currentLine = word + ' ';
                            } else {
                                currentLine += word + ' ';
                            }
                        });
                        if (currentLine.trim()) lines.push(currentLine.trim());
                        return lines; 
                    },
                    style: { colors: '#4b5563', fontSize: '11px', fontWeight: 500 }
                }
            },
            yaxis: { 
                max: function(max) { return max * 1.15; },
                labels: { formatter: function (val) { return val.toFixed(1); }, style: { colors: '#6b7280', fontWeight: 500 } } 
            },
            grid: { borderColor: '#f3f4f6', strokeDashArray: 4 },
            title: { text: 'Puntaje por dimensión', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
            subtitle: { text: `De menor a mayor — línea de referencia en promedio global (${globalScore.toFixed(2)})`, align: 'left', margin: 30, style: { fontSize: '13px', color: '#6b7280' } },
            tooltip: {
                custom: function({series, seriesIndex, dataPointIndex, w}) {
                    const score = series[seriesIndex][dataPointIndex];
                    const category = categories[dataPointIndex]; 
                    const color = w.config.colors[dataPointIndex % w.config.colors.length];
                    return buildCustomTooltip(category, null, score, color);
                }
            }
        };
    } else {
        options = {
            series: scores,
            labels: categories,
            chart: { type: 'pie', height: '100%', toolbar: { show: false }, fontFamily: 'inherit' },
            colors: colorsArr,
            dataLabels: {
                enabled: true,
                formatter: function (val, opts) {
                    return opts.w.config.series[opts.seriesIndex].toFixed(2);
                },
                style: { fontSize: '14px', fontFamily: 'inherit', fontWeight: 700 }
            },
            legend: { position: 'bottom' },
            title: { text: 'Puntaje por dimensión', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
            subtitle: { text: 'Representación proporcional del promedio (escala 1 a 5)', align: 'left', margin: 30, style: { fontSize: '13px', color: '#6b7280' } },
            tooltip: {
                custom: function({series, seriesIndex, w}) {
                    const score = series[seriesIndex];
                    const category = w.config.labels[seriesIndex]; 
                    const color = w.config.colors[seriesIndex % w.config.colors.length];
                    return buildCustomTooltip(category, null, score, color);
                }
            }
        };
    }

    dimensionChartInstance = new ApexCharts(chartContainer, options);
    dimensionChartInstance.render();
}

function buildCustomTooltip(category, questionText, score, color) {
    let questionHtml = questionText ? `
        <div style="font-size: 13px; color: #1f2937; margin-bottom: 8px; line-height: 1.4;">
            ${questionText}
        </div>` : '';

    return `
        <div style="padding: 12px; max-width: 320px; white-space: normal; background: #ffffff;">
            <div style="font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 4px;">
                ${category}
            </div>
            ${questionHtml}
            <div style="font-size: 14px; font-weight: 700; color: ${color};">
                ${score.toFixed(2)} puntos
            </div>
        </div>
    `;
}