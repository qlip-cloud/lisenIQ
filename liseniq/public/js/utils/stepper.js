export class Stepper {
    constructor(containerId, steps = []) {
        this.container = document.getElementById(containerId);
        this.steps = steps;
        this.currentStep = 1;

        if (!this.container) {
            console.error(`Stepper Error: No se encontró el contenedor con el ID "${containerId}".`);
        }
    }

    // Genera el HTML del stepper y lo inserta en el contenedor.
    // Este método debe ser llamado una vez para inicializar el componente.
    render() {
        if (!this.container) return;

        this.container.className = 'stepper-wrapper';
        // Se usa un ID único para la línea activa para evitar conflictos si hay múltiples steppers en la misma página.
        const activeLineId = `stepper-active-line-${this.container.id}`;
        
        this.container.innerHTML = `
            <div class="stepper-track-container">
                <div class="stepper-line"></div>
                <div class="stepper-track-line-active" id="${activeLineId}"></div>
                ${this.steps.map((_, index) => `
                    <div class="stepper-item" data-step="${index + 1}">
                        <div class="step-counter"></div>
                    </div>
                `).join('')}
            </div>
            <div class="stepper-labels-container">
                ${this.steps.map(label => `<div class="step-name">${frappe.utils.escape_html(label)}</div>`).join('')}
            </div>
        `;

        // Guardar referencias a los elementos generados para un acceso más rápido en `update`.
        this.stepperItems = this.container.querySelectorAll('.stepper-item');
        this.stepperLabels = this.container.querySelectorAll('.step-name');
        this.activeLine = this.container.querySelector(`#${activeLineId}`);
        
        // Inicializar el estado visual al primer paso.
        this.update(this.currentStep);
    }

    // Actualiza el estado visual del stepper para reflejar el paso actual.
    update(stepNumber) {
        if (!this.stepperItems || !this.activeLine) {
            // No hacer nada si el stepper no ha sido renderizado.
            return;
        }
        
        this.currentStep = stepNumber;

        // 1. Actualiza los círculos de los pasos (items).
        this.stepperItems.forEach(item => {
            const step = parseInt(item.dataset.step, 10);
            item.classList.remove('active', 'completed');
            if (step < this.currentStep) {
                item.classList.add('completed');
            } else if (step === this.currentStep) {
                item.classList.add('active');
            }
        });

        // 2. Actualiza las etiquetas de texto de los pasos.
        if (this.stepperLabels) {
            this.stepperLabels.forEach((label, index) => {
                label.classList.remove('active');
                if ((index + 1) === this.currentStep) {
                    label.classList.add('active');
                }
            });
        }

        // 3. Actualiza la longitud de la línea de progreso activa.
        const stepCount = this.steps.length - 1;
        // Se calcula el porcentaje de ancho basado en el paso actual.
        const widthPercentage = stepCount > 0 ? ((this.currentStep - 1) / stepCount) * 100 : 0;
        this.activeLine.style.width = `${widthPercentage}%`;
    }
}
