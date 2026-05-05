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

    // Cargamos de forma asíncrona tanto los gráficos como la librería PDF
    try {
        await Promise.all([loadApexCharts(), loadJsPDF()]);
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
                
                // Actualizamos el Tooltip y el Icono del botón
                this.title = tooltipText;
                this.innerHTML = `<i class="fa ${icon}" aria-hidden="true"></i>`;
                
                renderCultureChart(cultureChartType);
            });
        }

        // Eventos de Exportación
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
                
                // Actualizamos el Tooltip y el Icono del botón
                this.title = tooltipText;
                this.innerHTML = `<i class="fa ${icon}" aria-hidden="true"></i>`;
                
                renderDimensionChart(dimensionChartType);
            });
        }

        // Eventos de Exportación
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

// Función para cargar jsPDF
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

// Función para Exportar Gráficos (Imagen o PDF)
async function exportChart(chartInstance, fileName, format) {
    if (!chartInstance) return;
    
    try {
        // Obtenemos la imagen base64 que genera internamente ApexCharts
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
            // Creación de un PDF en formato A4 Horizontal
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
            
            const margin = 15;
            const pdfWidth = 297 - (margin * 2);
            const pdfHeight = 210 - (margin * 2);
            
            // Calculamos las proporciones para no deformar el gráfico
            const imgProps = pdf.getImageProperties(imgURI);
            const ratio = imgProps.width / imgProps.height;
            
            let drawWidth = pdfWidth;
            let drawHeight = pdfWidth / ratio;
            
            // Si la imagen es muy alta, la ajustamos al alto máximo en vez del ancho
            if (drawHeight > pdfHeight) {
                drawHeight = pdfHeight;
                drawWidth = pdfHeight * ratio;
            }
            
            // Centramos la imagen en el documento
            const x = margin + (pdfWidth - drawWidth) / 2;
            const y = margin + (pdfHeight - drawHeight) / 2;
            
            pdf.addImage(imgURI, 'PNG', x, y, drawWidth, drawHeight);
            pdf.save(`${fileName}.pdf`);
        }
    } catch (error) {
        console.error("Error exportando el gráfico:", error);
        if (window.frappe) {
            frappe.msgprint({ title: 'Error', indicator: 'red', message: 'Ocurrió un error al intentar exportar el gráfico.' });
        }
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

    let data = parseBackendData(window.dimensionChartData);
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
                    <div class="tb-question">${item.question}</div>
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
            plotOptions: { bar: { horizontal: false, columnWidth: '45%', borderRadius: 4, distributed: true } },
            dataLabels: { enabled: false },
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
            yaxis: { labels: { formatter: function (val) { return val.toFixed(2); }, style: { colors: '#6b7280', fontWeight: 500 } } },
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
    const questions = data.map(item => item.question || 'Sin pregunta');
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
            plotOptions: { bar: { horizontal: false, columnWidth: '45%', borderRadius: 4, distributed: true } },
            dataLabels: { enabled: false },
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
            yaxis: { labels: { formatter: function (val) { return val.toFixed(1); }, style: { colors: '#6b7280', fontWeight: 500 } } },
            grid: { borderColor: '#f3f4f6', strokeDashArray: 4 },
            title: { text: 'Puntaje por dimensión', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
            subtitle: { text: `De menor a mayor — línea de referencia en promedio global (${globalScore.toFixed(2)})`, align: 'left', margin: 30, style: { fontSize: '13px', color: '#6b7280' } },
            tooltip: {
                custom: function({series, seriesIndex, dataPointIndex, w}) {
                    const score = series[seriesIndex][dataPointIndex];
                    const questionText = questions[dataPointIndex]; 
                    const category = categories[dataPointIndex]; 
                    const color = w.config.colors[dataPointIndex % w.config.colors.length];
                    return buildCustomTooltip(category, questionText, score, color);
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
                    const questionText = questions[seriesIndex]; 
                    const category = w.config.labels[seriesIndex]; 
                    const color = w.config.colors[seriesIndex % w.config.colors.length];
                    return buildCustomTooltip(category, questionText, score, color);
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