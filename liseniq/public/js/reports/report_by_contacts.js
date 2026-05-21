// Función de entrada para inicializar los gráficos de demográficos de contacto
export function initContactsReport(contactDemographicsData) {
    const container = document.getElementById('contacts-charts-container');
    const header = document.getElementById('contacts-demographics-header');
    
    if (!container) return;

    let parsedData = {};
    try {
        let dataStr = contactDemographicsData || "{}";
        if (typeof dataStr === 'string') {
            let decodedStr = dataStr.replace(/&#34;/g, '"').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
            if (decodedStr.trim() === "" || decodedStr === '""' || decodedStr === "''") decodedStr = "{}";
            
            let tempParsed = JSON.parse(decodedStr);
            parsedData = typeof tempParsed === 'string' ? JSON.parse(tempParsed) : tempParsed;
        } else {
            parsedData = dataStr;
        }
    } catch(e) {
        console.error("Error parseando data de contactos:", e);
    }

    if (!parsedData || Object.keys(parsedData).length === 0) {
        if(header) header.style.display = 'none';
        container.style.display = 'none';
        return;
    }

    if(header) header.style.display = 'flex'; 

    container.className = 'contacts-charts-grid'; 
    container.style.display = 'grid'; 
    
    container.innerHTML = '';
    
    Object.keys(parsedData).forEach((demoCategory, index) => {
        const payload = parsedData[demoCategory];
        
        const data = Array.isArray(payload) ? payload : payload.data;
        const categoryColor = payload.color || '';

        if (!data || data.length === 0) return;

        const cardId = `contact-chart-card-${index}`;
        const chartId = `contact-chart-${index}`;
        
        // Crear la tarjeta para cada categoría demográfica con su respectivo gráfico
        const cardHtml = `
            <div id="${cardId}">
                <div class="chart-header-flex" style="margin-top: 0; padding-left: 0;">
                    <h3 class="chart-section-title">Puntaje por ${demoCategory.toLowerCase()}</h3>
                </div>
                <div class="chart-card" style="margin-bottom: 0;">
                    <div id="${chartId}" class="chart-wrapper" style="height: 380px;"></div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', cardHtml);

        renderContactChart(chartId, demoCategory, data, categoryColor);
    });
}

function renderContactChart(containerId, categoryName, data, dtColor) {
    const categories = data.map(item => item.value || 'N/A');
    const scores = data.map(item => item.score || 0);
    
    // Asignar el color dinámicamente
    let colorToUse = '#7c3aed';
    let c = dtColor ? String(dtColor).trim().toLowerCase() : "";
    
    if (c && c !== 'none' && c !== 'null') {
        if (/^[0-9a-f]{6}$/i.test(c)) {
            colorToUse = '#' + dtColor.trim();
        } else {
            colorToUse = dtColor;
        }
    }

    const options = {
        series: [{ name: 'Puntaje Promedio', data: scores }],
        chart: { 
            type: 'bar', 
            height: '100%', 
            toolbar: { show: false }, 
            fontFamily: 'inherit',
            parentHeightOffset: 0
        },
        colors: [colorToUse],
        plotOptions: { 
            bar: { 
                horizontal: false, 
                columnWidth: '55%',
                borderRadius: 4, 
                distributed: false,
                dataLabels: { position: 'center' } // Se ajusta la posición al centro
            } 
        },
        dataLabels: { 
            enabled: true, // Se habilitan las etiquetas
            formatter: function (val) { return val.toFixed(2); },
            style: { fontSize: '13px', fontWeight: 700, colors: ["#ffffff"] },
            dropShadow: { enabled: true, top: 1, left: 1, blur: 1, color: '#000', opacity: 0.45 }
        },
        legend: { show: false },
        xaxis: {
            categories: categories,
            labels: { 
                style: { colors: '#4b5563', fontSize: '11px', fontWeight: 500 },
                trim: true,
                hideOverlappingLabels: false,
                rotate: -45
            } 
        },
        yaxis: {
            max: function(max) { return max > 5 ? max : 5; }, 
            labels: {
                // Forzamos 2 decimales para el Eje Y
                formatter: function (val) { return val.toFixed(2).replace('.', ','); }, 
                style: { colors: '#6b7280', fontSize: '11px', fontWeight: 600 }
            }
        },
        grid: { 
            borderColor: '#f3f4f6', 
            strokeDashArray: 0,
            padding: { bottom: 15, left: 10, right: 10 }
        },
        tooltip: {
            custom: function({series, seriesIndex, dataPointIndex, w}) {
                const score = series[seriesIndex][dataPointIndex];
                const category = categories[dataPointIndex]; 
                
                return `
                    <div style="padding: 12px; background: #ffffff;">
                        <div style="font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 4px;">
                            ${categoryName}
                        </div>
                        <div style="font-size: 13px; color: #1f2937; margin-bottom: 8px;">
                            ${category}
                        </div>
                        <div style="font-size: 14px; font-weight: 700; color: ${colorToUse};">
                            ${score.toFixed(2)}
                        </div>
                    </div>
                `;
            }
        }
    };

    const chart = new ApexCharts(document.getElementById(containerId), options);
    chart.render();
}