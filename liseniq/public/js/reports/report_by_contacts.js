// Función de entrada para inicializar los gráficos de demográficos de contacto
export function initContactsReport(contactDemographicsData, surveyName = 'Encuesta') {
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
        const isFixed = payload.is_fixed || false;

        if (!data || data.length === 0) return;

        const cardId = `contact-chart-card-${index}`;
        const chartId = `contact-chart-${index}`;
        
        // Formatear título asegurando compatibilidad con los gráficos fijos
        const titleText = `Puntaje por ${demoCategory.toLowerCase()}`;
        
        // Crear la tarjeta para cada categoría demográfica con su respectivo gráfico y BOTONES DE EXPORTACIÓN
        const cardHtml = `
            <div id="${cardId}">
                <div class="chart-header-flex" style="margin-top: 0; padding-left: 0; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h3 class="chart-section-title" style="margin-bottom: 0;">${titleText}</h3>
                    <div class="chart-actions-group">
                        <button id="btn-export-img-${chartId}" class="btn btn-outline-secondary btn-sm" title="Exportar a Imagen">
                            <i class="fa fa-image" aria-hidden="true"></i>
                        </button>
                        <button id="btn-export-pdf-${chartId}" class="btn btn-outline-secondary btn-sm" title="Exportar a PDF">
                            <i class="fa fa-file-pdf-o" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
                <div class="chart-card" style="margin-bottom: 0;">
                    <div id="${chartId}" class="chart-wrapper" style="min-height: 380px;"></div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', cardHtml);

        const chartInstance = renderContactChart(chartId, demoCategory, data, categoryColor, isFixed);

        // Lógica de los botones de exportación para este gráfico específico
        const btnImg = document.getElementById(`btn-export-img-${chartId}`);
        if (btnImg) {
            btnImg.addEventListener('click', () => {
                const cleanCategory = demoCategory.replace(/\s+/g, '_');
                exportChart(chartInstance, `Reporte_Contactos_${cleanCategory}_${surveyName}`, 'img');
            });
        }
        
        const btnPdf = document.getElementById(`btn-export-pdf-${chartId}`);
        if (btnPdf) {
            btnPdf.addEventListener('click', () => {
                const cleanCategory = demoCategory.replace(/\s+/g, '_');
                exportChart(chartInstance, `Reporte_Contactos_${cleanCategory}_${surveyName}`, 'pdf');
            });
        }
    });
}

function renderContactChart(containerId, categoryName, data, dtColor, isFixed) {
    const categories = data.map(item => item.value || 'N/A');
    const scores = data.map(item => item.score || 0);
    
    let isDistributed = false;
    let colorsArray = [];

    // Cálculo de Altura Dinámica: 35px por cada barra para evitar que se aplasten.
    // Mínimo será 380px para mantener estética en gráficos de pocos datos.
    const calculatedHeight = Math.max(380, categories.length * 35);

    // Lógica para asignar colores dinámicamente
    if (dtColor === 'DYNAMIC') {
        isDistributed = true;
        colorsArray = scores.map(score => {
            // El umbral se establece cercano a 2.7 basado en la imagen de referencia
            return score >= 2.7 ? '#26a374' : '#e05a33'; 
        });
    } else {
        // Asignar el color dinámicamente según lo traído de la base de datos
        let colorToUse = '#7c3aed';
        let c = dtColor ? String(dtColor).trim().toLowerCase() : "";
        
        if (c && c !== 'none' && c !== 'null') {
            if (/^[0-9a-f]{6}$/i.test(c)) {
                colorToUse = '#' + dtColor.trim();
            } else {
                colorToUse = dtColor;
            }
        }
        colorsArray = [colorToUse];
    }

    const options = {
        series: [{ name: 'Puntaje Promedio', data: scores }],
        chart: { 
            type: 'bar', 
            height: calculatedHeight,
            toolbar: { show: false }, 
            fontFamily: 'inherit',
            parentHeightOffset: 0
        },
        colors: colorsArray,
        plotOptions: { 
            bar: { 
                horizontal: true, 
                barHeight: '65%',
                borderRadius: 4, 
                distributed: isDistributed,
                dataLabels: { position: 'center' }
            } 
        },
        dataLabels: { 
            enabled: true,
            formatter: function (val) { return val.toFixed(2); },
            style: { fontSize: '10px', fontWeight: 600, colors: ["#ffffff"] },
            dropShadow: { enabled: true, top: 1, left: 1, blur: 1, color: '#000', opacity: 0.6 }
        },
        legend: { show: false },
        xaxis: {
            categories: categories, 
            max: function(max) { return max > 5 ? max : 5; }, 
            labels: { 
                formatter: function (val) { 
                    if(typeof val === 'number' || !isNaN(val)) {
                        return Number(val).toFixed(2).replace('.', ',');
                    }
                    return val;
                },
                style: { colors: '#6b7280', fontSize: '11px', fontWeight: 600 }
            } 
        },
        yaxis: {
            labels: {
                style: { colors: '#4b5563', fontSize: '11px', fontWeight: 500 },
                maxWidth: 160 
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
                const toolTipColor = isDistributed ? colorsArray[dataPointIndex] : colorsArray[0];
                
                return `
                    <div style="padding: 12px; background: #ffffff;">
                        <div style="font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; margin-bottom: 4px;">
                            ${categoryName}
                        </div>
                        <div style="font-size: 13px; color: #1f2937; margin-bottom: 8px;">
                            ${category}
                        </div>
                        <div style="font-size: 14px; font-weight: 700; color: ${toolTipColor};">
                            ${score.toFixed(2)}
                        </div>
                    </div>
                `;
            }
        }
    };

    const chart = new ApexCharts(document.getElementById(containerId), options);
    chart.render();
    
    // Devolver la instancia del gráfico para poder exportarla
    return chart;
}

// Lógica reutilizable para la exportación que servirá a todos los gráficos de contactos
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