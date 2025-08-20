export class Stepper {
    constructor(containerId, steps = []) {
        this.container = document.getElementById(containerId);
        this.steps = steps;
        this.currentStep = 1;

        if (!this.container) {
            console.error(`Stepper Error: No se encontró el contenedor con el ID "${containerId}".`);
        }
    }

    render() {
        if (!this.container) return;

        this.container.className = 'stepper-wrapper';
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

        this.stepperItems = this.container.querySelectorAll('.stepper-item');
        this.stepperLabels = this.container.querySelectorAll('.step-name');
        this.activeLine = this.container.querySelector(`#${activeLineId}`);
        
        this.update(this.currentStep);
    }

    update(stepNumber) {
        if (!this.stepperItems || !this.activeLine) {
            return;
        }
        
        this.currentStep = stepNumber;

        this.stepperItems.forEach(item => {
            const step = parseInt(item.dataset.step, 10);
            item.classList.remove('active', 'completed');
            if (step < this.currentStep) {
                item.classList.add('completed');
            } else if (step === this.currentStep) {
                item.classList.add('active');
            }
        });

        if (this.stepperLabels) {
            this.stepperLabels.forEach((label, index) => {
                label.classList.remove('active');
                if ((index + 1) === this.currentStep) {
                    label.classList.add('active');
                }
            });
        }

        const stepCount = this.steps.length - 1;
        const widthPercentage = stepCount > 0 ? ((this.currentStep - 1) / stepCount) * 100 : 0;
        this.activeLine.style.width = `${widthPercentage}%`;
    }
}
