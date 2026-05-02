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
    if (titleElement) {
        titleElement.textContent = surveyTitle;
    }

    if (typeof ApexCharts === 'undefined') {
        try {
            await loadApexCharts();
        } catch (e) {
            console.error("Fallo al cargar ApexCharts", e);
            return;
        }
    }

    // Parseamos los features del plan
    let appFeatures = [];
    try {
        appFeatures = typeof window.liseniqAppFeatures === 'string' ? JSON.parse(window.liseniqAppFeatures) : (window.liseniqAppFeatures || []);
    } catch(e) {
        console.error("Error parseando features de la app", e);
    }

    // Función auxiliar para ocultar secciones sin acceso en el DOM
    const hideSection = (containerId) => {
        const container = document.getElementById(containerId);
        if (container) {
            const card = container.closest('.chart-card');
            if (card) {
                card.style.display = 'none';
                const title = card.previousElementSibling;
                if (title && title.classList.contains('chart-section-title')) {
                    title.style.display = 'none'; // Oculta el título "Tipos de cultura" o "Dimensiones"
                }
            }
        }
    };

    // Inicializamos las secciones
    initTopBottomCards();

    // Gráfico de Tipo de Cultura: Requiere feature 'aiq_rep_cultura'
    if (appFeatures.includes('aiq_rep_cultura')) {
        initCultureChart(); 
    } else {
        hideSection('culture-chart-container');
    }

    // Gráfico de Dimensiones: Requiere feature 'aiq_rep_dimension'
    if (appFeatures.includes('aiq_rep_dimension')) {
        initDimensionChart();
    } else {
        hideSection('dimension-chart-container');
    }
});

function loadApexCharts() {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/apexcharts';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Función centralizada para limpiar los datos del backend
function parseBackendData(rawData) {
    let data = [];
    try {
        let dataStr = rawData || "[]";
        if (typeof dataStr === 'string') {
            let decodedStr = dataStr.replace(/&#34;/g, '"').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
            if (decodedStr.trim() === "" || decodedStr === '""' || decodedStr === "''") {
                decodedStr = "[]";
            }
            let parsed = JSON.parse(decodedStr);
            if (typeof parsed === 'string') {
                parsed = JSON.parse(parsed);
            }
            if (Array.isArray(parsed)) {
                data = parsed;
            }
        } else if (Array.isArray(rawData)) {
            data = rawData;
        }
    } catch (e) {
        console.error("Error al parsear los datos del gráfico:", e, rawData);
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

    // Clonamos la data para no afectar los gráficos
    // Ordenamos de menor a mayor para Bottom 10
    let ascendingData = [...data].sort((a, b) => a.score - b.score);
    let bottom10 = ascendingData.slice(0, 10);

    // Ordenamos de mayor a menor para Top 10
    let descendingData = [...data].sort((a, b) => b.score - a.score);
    let top10 = descendingData.slice(0, 10);

    // Función auxiliar para renderizar cada lista
    const renderRows = (items, container, colorClass) => {
        container.innerHTML = items.map(item => {
            // El score va de 1 a 5, calculamos el porcentaje para rellenar la barra
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
                </div>
            `;
        }).join('');
    };

    renderRows(top10, topContainer, 'fill-green');
    renderRows(bottom10, bottomContainer, 'fill-orange');
}

// Logica de grafico tipo de cultura/tema (nivel 3)
function initCultureChart() {
    const chartContainer = document.getElementById('culture-chart-container');
    if (!chartContainer) return;

    let data = parseBackendData(window.cultureChartData);
    
    // Extraemos las categorías (texto del topic) y puntajes
    const categories = data.map(item => item.topic || 'N/A');
    const scores = data.map(item => item.score || 0);

    const options = {
        series: [{
            name: 'Puntaje Promedio',
            data: scores
        }],
        chart: {
            type: 'bar',
            height: '100%',
            toolbar: { show: false },
            fontFamily: 'inherit'
        },
        colors: ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'],
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '45%',
                borderRadius: 4,
                borderRadiusApplication: 'end',
                distributed: true
            },
        },
        dataLabels: {
            enabled: false
        },
        legend: {
            show: false
        },
        xaxis: {
            categories: categories,
            labels: {
                rotate: 0,                      
                rotateAlways: false,
                trim: false,                    
                maxHeight: 120,                 
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
            labels: {
                formatter: function (value) {
                    return value.toFixed(2);
                },
                style: { colors: '#6b7280', fontWeight: 500 }
            }
        },
        grid: {
            borderColor: '#f3f4f6',
            strokeDashArray: 4,
        },
        title: {
            text: 'Puntaje por tipo de cultura',
            align: 'left',
            style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' }
        },
        subtitle: {
            text: 'Promedio de respuestas (escala 1 a 5)',
            align: 'left',
            margin: 30,
            style: { fontSize: '13px', color: '#6b7280' }
        },
        tooltip: {
            custom: function({series, seriesIndex, dataPointIndex, w}) {
                const score = series[seriesIndex][dataPointIndex];
                const category = categories[dataPointIndex]; 
                const colors = w.config.colors;
                const color = colors[dataPointIndex % colors.length];

                return `
                    <div style="padding: 12px; max-width: 320px; white-space: normal; background: #ffffff;">
                        <div style="font-size: 13px; font-weight: 700; color: #1f2937; margin-bottom: 8px; text-transform: uppercase;">
                            ${category}
                        </div>
                        <div style="font-size: 14px; font-weight: 700; color: ${color};">
                            ${score.toFixed(2)} puntos
                        </div>
                    </div>
                `;
            }
        }
    };

    const chart = new ApexCharts(chartContainer, options);
    chart.render();
}

// Logica de grafico de dimensiones (nivel 2)
function initDimensionChart() {
    const chartContainer = document.getElementById('dimension-chart-container');
    if (!chartContainer) return;

    let data = parseBackendData(window.dimensionChartData);
    
    // Extraemos las categorías (demográfico), la pregunta (enunciado largo) y puntajes
    const categories = data.map(item => item.culture || 'N/A');
    const questions = data.map(item => item.question || 'Sin pregunta');
    const scores = data.map(item => item.score || 0);

    // Extraer puntaje global del DOM (primera tarjeta de métrica) de forma segura
    let globalScore = 0;
    const metricElements = document.querySelectorAll('.metric-value');
    if (metricElements && metricElements.length > 0) {
        // Limpiamos el texto por si hay comas o caracteres invisibles y extraemos el número
        const scoreText = metricElements[0].textContent.replace(',', '.').replace(/[^0-9.]/g, '');
        globalScore = parseFloat(scoreText) || 0;
    }

    const options = {
        series: [{
            name: 'Puntaje Promedio',
            data: scores
        }],
        chart: {
            type: 'bar',
            height: '100%',
            toolbar: { show: false },
            fontFamily: 'inherit'
        },
        colors: ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4'],
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '45%',
                borderRadius: 4,
                borderRadiusApplication: 'end',
                distributed: true
            },
        },
        dataLabels: {
            enabled: false
        },
        legend: {
            show: false
        },
        // Añadimos la línea de anotación para el promedio global
        annotations: {
            yaxis: [{
                y: globalScore.toFixed(2),
                borderColor: '#ea580c', // Color naranja similar al de la imagen
                strokeDashArray: 4,
                borderWidth: 1.5,
                label: {
                    borderColor: 'transparent',
                    style: {
                        color: '#ea580c',
                        background: 'transparent',
                        fontSize: '12px',
                        fontWeight: 600
                    },
                    text: `Promedio ${globalScore.toFixed(2)}`,
                    position: 'right',
                    offsetX: 0,
                    offsetY: -8,
                    
                },
                
            }]
        },
        xaxis: {
            categories: categories,
            labels: {
                rotate: 0,
                rotateAlways: false,
                trim: false,
                maxHeight: 120,
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
            labels: {
                formatter: function (value) {
                    return value.toFixed(1);
                },
                style: { colors: '#6b7280', fontWeight: 500 }
            }
        },
        grid: {
            borderColor: '#f3f4f6',
            strokeDashArray: 4,
        },
        title: {
            text: 'Puntaje por dimensión',
            align: 'left',
            style: { fontSize: '16px', fontWeight: '700', color: '#1f2937' }
        },
        subtitle: {
            // Actualizamos el subtitulo dinámicamente con el promedio
            text: `De menor a mayor — línea de referencia en promedio global (${globalScore.toFixed(2)})`,
            align: 'left',
            margin: 30,
            style: { fontSize: '13px', color: '#6b7280' }
        },
        tooltip: {
            custom: function({series, seriesIndex, dataPointIndex, w}) {
                const score = series[seriesIndex][dataPointIndex];
                const questionText = questions[dataPointIndex]; 
                const category = categories[dataPointIndex]; 
                
                const colors = w.config.colors;
                const color = colors[dataPointIndex % colors.length];

                return `
                    <div style="padding: 12px; max-width: 320px; white-space: normal; background: #ffffff;">
                        <div style="font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 4px;">
                            ${category}
                        </div>
                        <div style="font-size: 13px; color: #1f2937; margin-bottom: 8px; line-height: 1.4;">
                            ${questionText}
                        </div>
                        <div style="font-size: 14px; font-weight: 700; color: ${color};">
                            ${score.toFixed(2)} puntos
                        </div>
                    </div>
                `;
            }
        }
    };

    const chart = new ApexCharts(chartContainer, options);
    chart.render();
}