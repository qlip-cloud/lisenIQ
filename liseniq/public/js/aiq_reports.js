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

    // Inicializamos el gráfico de Cultura
    initCultureChart(); 
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

function initCultureChart() {
    const chartContainer = document.getElementById('culture-chart-container');
    if (!chartContainer) return;

    let data = [];
    try {
        let rawData = window.cultureChartData || "[]";
        
        if (typeof rawData === 'string') {
            let decodedStr = rawData.replace(/&#34;/g, '"').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
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
        console.error("Error al parsear los datos del gráfico:", e, window.cultureChartData);
        data = []; 
    }
    
    // Extraemos las categorías (demográfico), la pregunta (enunciado largo) y puntajes
    const categories = data.map(item => item.culture || 'N/A');
    const questions = data.map(item => item.question || 'Sin pregunta');
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
        xaxis: {
            categories: categories,
            labels: {
                rotate: 0,                      // Forzamos a que el texto esté totalmente derecho (sin inclinación)
                rotateAlways: false,
                trim: false,                    // Evitamos que recorte las palabras con "..."
                maxHeight: 120,                 // Damos más espacio vertical si hay muchas líneas
                formatter: function (value) {
                    if (typeof value !== 'string') return value;
                    
                    const maxLength = 15;       // Límite de caracteres por fila (ajustable si el texto sigue siendo muy largo)
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
                    
                    // Al devolver un arreglo, ApexCharts crea múltiples líneas de texto
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
            // Tooltip personalizado HTML al hacer hover
            custom: function({series, seriesIndex, dataPointIndex, w}) {
                const score = series[seriesIndex][dataPointIndex];
                const questionText = questions[dataPointIndex]; 
                
                // Usamos el arreglo de categorías original para que no salga con los cortes de línea
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