// Importamos la función de inicialización del reporte de contactos para poder llamarla desde este archivo (report_by_engagement.js)
import { initContactsReport } from './report_by_contacts.js';

let engagementChartInstance = null;
let dimensionChartInstance = null;
let engagementIndexChartInstance = null;
let engagementChartType = 'bar'; 
let dimensionChartType = 'bar'; 

// Función de entrada que es llamada por el orquestador
export function initEngagementReport(dataConfig, surveyName) {
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

    // Procesar la data inyectada desde el backend para este reporte
    const engagementData = parseBackendData(dataConfig.engagement_chart_data);
    const dimensionData = parseBackendData(dataConfig.dimension_chart_data);
    const groupedDimensionData = parseBackendData(dataConfig.grouped_dimension_chart_data);
    const topicQuestionsData = parseBackendData(dataConfig.topic_questions_data);
    const engagementIndexData = parseBackendData(dataConfig.engagement_index_chart_data);

    // Inicializamos la sección de top 10 y bottom 10
    initTopBottomCards(dimensionData);

    // Inicializamos las tablas desglosadas por tema
    initTopicsTables(topicQuestionsData);

    // Renderizar Gráfico de Engagement
    if (appFeatures.includes('aiq_rep_engagement')) {
        renderEngagementChart(engagementChartType, engagementData);
        
        const btnEngagement = document.getElementById('btn-toggle-engagement');
        if (btnEngagement) {
            btnEngagement.addEventListener('click', function() {
                engagementChartType = engagementChartType === 'bar' ? 'pie' : 'bar';
                const icon = engagementChartType === 'bar' ? 'fa-pie-chart' : 'fa-bar-chart';
                const tooltipText = engagementChartType === 'bar' ? 'Ver Gráfico de Torta' : 'Ver Gráfico de Barras';
                
                this.title = tooltipText;
                this.innerHTML = `<i class="fa ${icon}" aria-hidden="true"></i>`;
                
                renderEngagementChart(engagementChartType, engagementData);
            });
        }

        const btnExpImgEngagement = document.getElementById('btn-export-engagement-img');
        if (btnExpImgEngagement) {
            btnExpImgEngagement.addEventListener('click', () => {
                exportChart(engagementChartInstance, `Reporte_Engagement_${surveyName}`, 'img');
            });
        }
        const btnExpPdfEngagement = document.getElementById('btn-export-engagement-pdf');
        if (btnExpPdfEngagement) {
            btnExpPdfEngagement.addEventListener('click', () => {
                exportChart(engagementChartInstance, `Reporte_Engagement_${surveyName}`, 'pdf');
            });
        }
    } else {
        renderEngagementChart(engagementChartType, engagementData);
        const btnExpImgEngagement = document.getElementById('btn-export-engagement-img');
        if (btnExpImgEngagement) btnExpImgEngagement.addEventListener('click', () => exportChart(engagementChartInstance, `Reporte_Engagement_${surveyName}`, 'img'));
        const btnExpPdfEngagement = document.getElementById('btn-export-engagement-pdf');
        if (btnExpPdfEngagement) btnExpPdfEngagement.addEventListener('click', () => exportChart(engagementChartInstance, `Reporte_Engagement_${surveyName}`, 'pdf'));
    }

    // Renderizar Gráfico de Dimensiones
    if (appFeatures.includes('aiq_rep_dimension') || true) {
        renderDimensionChart(dimensionChartType, groupedDimensionData);
        
        const btnDimension = document.getElementById('btn-toggle-dimension');
        if (btnDimension) {
            btnDimension.addEventListener('click', function() {
                dimensionChartType = dimensionChartType === 'bar' ? 'pie' : 'bar';
                const icon = dimensionChartType === 'bar' ? 'fa-pie-chart' : 'fa-bar-chart';
                const tooltipText = dimensionChartType === 'bar' ? 'Ver Gráfico de Torta' : 'Ver Gráfico de Barras';
                
                this.title = tooltipText;
                this.innerHTML = `<i class="fa ${icon}" aria-hidden="true"></i>`;
                
                renderDimensionChart(dimensionChartType, groupedDimensionData);
            });
        }

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

    // Renderizar Gráfico de Índice de Engagement
    if (engagementIndexData && engagementIndexData.length > 0) {
        renderEngagementIndexChart(engagementIndexData);
        
        const btnExpImgEI = document.getElementById('btn-export-eng-index-img');
        if (btnExpImgEI) {
            btnExpImgEI.addEventListener('click', () => {
                exportChart(engagementIndexChartInstance, `Reporte_Indice_Engagement_${surveyName}`, 'img');
            });
        }
        const btnExpPdfEI = document.getElementById('btn-export-eng-index-pdf');
        if (btnExpPdfEI) {
            btnExpPdfEI.addEventListener('click', () => {
                exportChart(engagementIndexChartInstance, `Reporte_Indice_Engagement_${surveyName}`, 'pdf');
            });
        }
    } else {
        hideSection('engagement-index-header-container', 'engagement-index-card-container');
    }

    // Inicializamos los gráficos de contactos
    if (window.contactDemographicsData) {
        initContactsReport(window.contactDemographicsData);
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

// Inicializar las tarjetas de top 10 y bottom 10 utilizando la data de preguntas agrupada por dimensión (dimensionData)
function initTopBottomCards(data) {
    const topContainer = document.getElementById('top-10-list');
    const bottomContainer = document.getElementById('bottom-10-list');
    if (!topContainer || !bottomContainer) return;

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

// Inicializar y agrupar las tablas de preguntas por cada tema de manera dinámica
function initTopicsTables(data) {
    const container = document.getElementById('topics-tables-container');
    if (!container) return;
    if (!data || data.length === 0) return;

    // Agrupamos las preguntas por su topic
    const grouped = {};
    data.forEach(item => {
        const topic = item.topic || 'Sin Tema';
        if (!grouped[topic]) grouped[topic] = [];
        grouped[topic].push(item);
    });

    let html = '';
    // Ordenamos los temas alfabéticamente para mantener consistencia visual
    const sortedTopics = Object.keys(grouped).sort();

    sortedTopics.forEach(topic => {
        const items = grouped[topic];
        // Ordenar las preguntas dentro de cada tema de mayor a menor puntaje
        items.sort((a, b) => b.score - a.score);

        const rowsHtml = items.map(item => {
            const percentage = Math.min(100, Math.max(0, (item.score / 5) * 100));
            
            // Asignación de color según el tema
            let c = item.color ? String(item.color).trim().toLowerCase() : "";
            let hexColor = '#7c3aed';
            if (c && c !== 'none' && c !== 'null') {
                hexColor = /^[0-9a-f]{6}$/i.test(c) ? '#' + c : c;
            }

            return `
                <div class="tb-row">
                    <div class="tb-topic">${item.dimension || 'Sin Dimensión'}</div>
                    <div class="tb-question">${item.question}</div>
                    <div class="tb-score-wrapper">
                        <div class="tb-score-bar-bg">
                            <div class="tb-score-bar-fill" style="width: ${percentage}%; background-color: ${hexColor};"></div>
                        </div>
                        <div class="tb-score-value">${item.score.toFixed(2)}</div>
                    </div>
                </div>`;
        }).join('');

        html += `
            <div class="tb-card">
                <h4 class="tb-header-title">${topic}</h4>
                <div class="tb-table-header">
                    <span>Dimensión</span>
                    <span>Pregunta</span>
                    <span style="text-align: right;">Puntaje</span>
                </div>
                <div>
                    ${rowsHtml}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Renderizar el grafico de engagement utilizando la data agrupada por topic (engagementData)
function renderEngagementChart(type, data) {
    const chartContainer = document.getElementById('engagement-chart-container');
    if (!chartContainer) return;

    const categories = data.map(item => item.topic || 'N/A');
    const scores = data.map(item => item.score || 0);
    
    // Asignar el color dinámicamente
    const colorsArr = data.map(item => {
        let c = item.color ? String(item.color).trim().toLowerCase() : "";
        if (!c || c === 'none' || c === 'null') return '#7c3aed';
        
        // Agregamos el '#' automáticamente en caso de que en la BD solo hayan puesto el código hex
        if (/^[0-9a-f]{6}$/i.test(c)) return '#' + item.color.trim();
        
        return item.color;
    });

    if (engagementChartInstance) engagementChartInstance.destroy();

    let options = {};
    if (type === 'bar') {
        options = {
            series: [{ name: 'Puntaje Promedio', data: scores }],
            chart: { type: 'bar', height: '100%', toolbar: { show: false }, fontFamily: 'inherit' },
            colors: colorsArr,
            plotOptions: { 
                bar: { 
                    horizontal: false, columnWidth: '45%', borderRadius: 4, distributed: true,
                    dataLabels: { position: 'center' }
                } 
            },
            dataLabels: { 
                enabled: true,
                formatter: function (val) { return val.toFixed(2); },
                style: { fontSize: '13px', fontWeight: 700, colors: ["#ffffff"] },
                dropShadow: { enabled: true, top: 1, left: 1, blur: 1, color: '#000', opacity: 0.45 }
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
            title: { text: 'Puntaje por tipo de Cultura', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
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
                formatter: function (val, opts) { return opts.w.config.series[opts.seriesIndex].toFixed(2); },
                style: { fontSize: '14px', fontFamily: 'inherit', fontWeight: 700 }
            },
            legend: { position: 'bottom' },
            title: { text: 'Puntaje por tipo de Cultura', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
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

    engagementChartInstance = new ApexCharts(chartContainer, options);
    engagementChartInstance.render();
}

// Renderizar el grafico de dimensiones utilizando la data agrupada por dimensión (groupedDimensionData)
function renderDimensionChart(type, data) {
    const chartContainer = document.getElementById('dimension-chart-container');
    if (!chartContainer) return;

    // Utilizamos solo las categorías agrupadas (sin preguntas individuales)
    const categories = data.map(item => item.engagement || 'N/A'); 
    const scores = data.map(item => item.score || 0);

    // Asignar el color dinámicamente
    const colorsArr = data.map(item => {
        let c = item.color ? String(item.color).trim().toLowerCase() : "";
        if (!c || c === 'none' || c === 'null') return '#7c3aed';
        
        if (/^[0-9a-f]{6}$/i.test(c)) return '#' + item.color.trim();
        
        return item.color;
    });

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
                    horizontal: false, columnWidth: '45%', borderRadius: 4, distributed: true,
                    dataLabels: { position: 'center' }
                } 
            },
            dataLabels: { 
                enabled: true,
                formatter: function (val) { return val.toFixed(2); },
                style: { fontSize: '13px', fontWeight: 700, colors: ["#ffffff"] },
                dropShadow: { enabled: true, top: 1, left: 1, blur: 1, color: '#000', opacity: 0.45 }
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
                formatter: function (val, opts) { return opts.w.config.series[opts.seriesIndex].toFixed(2); },
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

// Renderizar el gráfico especial del Índice de Engagement
function renderEngagementIndexChart(data) {
    const chartContainer = document.getElementById('engagement-index-chart-container');
    if (!chartContainer) return;

    const categories = data.map(item => item.question || 'N/A');
    const scores = data.map(item => item.score || 0);

    const colorsArr = data.map(item => {
        let c = item.color ? String(item.color).trim().toLowerCase() : "";
        if (!c || c === 'none' || c === 'null') return '#10b981';
        
        if (/^[0-9a-f]{6}$/i.test(c)) return '#' + item.color.trim();
        return item.color;
    });

    if (engagementIndexChartInstance) engagementIndexChartInstance.destroy();

    const options = {
        series: [{ name: 'Puntaje Promedio', data: scores }],
        chart: { type: 'bar', height: '100%', minHeight: 350, toolbar: { show: false }, fontFamily: 'inherit' },
        colors: colorsArr,
        plotOptions: { 
            bar: { 
                horizontal: false, columnWidth: '45%', borderRadius: 4, distributed: true,
                dataLabels: { position: 'center' }
            } 
        },
        dataLabels: { 
            enabled: true,
            formatter: function (val) { return val.toFixed(2); },
            style: { fontSize: '13px', fontWeight: 700, colors: ["#ffffff"] },
            dropShadow: { enabled: true, top: 1, left: 1, blur: 1, color: '#000', opacity: 0.45 }
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
        title: { text: 'Índice de Engagement', align: 'left', style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' } },
        subtitle: { text: 'Desglose del comportamiento del Índice de Engagement', align: 'left', margin: 30, style: { fontSize: '13px', color: '#6b7280' } },
        tooltip: {
            custom: function({series, seriesIndex, dataPointIndex, w}) {
                const score = series[seriesIndex][dataPointIndex];
                const category = categories[dataPointIndex]; 
                const color = w.config.colors[dataPointIndex % w.config.colors.length];
                return buildCustomTooltip('Pregunta Clave', category, score, color);
            }
        }
    };

    engagementIndexChartInstance = new ApexCharts(chartContainer, options);
    engagementIndexChartInstance.render();
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
                ${score.toFixed(2)}
            </div>
        </div>
    `;
}

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
        } else if (format === 'pdf') {
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