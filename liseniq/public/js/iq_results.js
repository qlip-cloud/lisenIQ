const ui = {
  preload: document.getElementById('results-preloaded'),
  grid: document.getElementById('results-grid'),
  empty: document.getElementById('results-empty'),
  name: document.getElementById('filter-name'),
  template: document.getElementById('filter-template'),
  pbi: document.getElementById('pbi-embed'),
  step2: document.getElementById('step2-pbi'),
  selectedName: document.getElementById('selected-name'),
  backBtn: document.getElementById('btn-back-step-2'),
  clearName: document.getElementById('filter-name-clear'),
  
  // Elementos del Modal
  reportModal: document.getElementById('report-choice-modal'),
  closeReportModal: document.getElementById('btn-close-report-modal'),
  btnAiqReport: document.getElementById('btn-aiq-report'),
  btnPbiReport: document.getElementById('btn-pbi-report'),
  btnDashboard: document.getElementById('btn-dashboard')
};

const state = {
  items: [],
  templates: [],
  allTemplates: [],
  debounce: null,
  embedConfig: null,
  pbiSdkReady: null,
  selectedDoc: null,
  selectedName: null,
  selectedCategory: null
};

// Validación de funcionalidades (features) para mostrar/ocultar elementos o activar flujos alternativos
function hasFeature(featureCode) {
  try {
      let featuresArray = [];
      if (typeof window.liseniqAppFeatures === 'string') {
          featuresArray = JSON.parse(window.liseniqAppFeatures || '[]');
      } else if (Array.isArray(window.liseniqAppFeatures)) {
          featuresArray = window.liseniqAppFeatures;
      }
      return featuresArray.includes(featureCode);
  } catch (e) {
      console.error("Error al procesar las funcionalidades de la suscripción:", e);
      return false;
  }
}

function initPreloaded() {
  if (!ui.preload) return;
  try {
    state.items = JSON.parse(ui.preload.dataset.surveys || '[]');
    state.templates = JSON.parse(ui.preload.dataset.templates || '[]');
    state.allTemplates = [...state.templates];
  } catch {
    state.items = [];
    state.templates = [];
    state.allTemplates = [];
  }
}

function fillTemplateSelect() {
  if (!ui.template) return;
  const previous = ui.template.value;
  ui.template.querySelectorAll('option:not([value=""])').forEach(o => o.remove());
  const source = state.allTemplates.length ? state.allTemplates : state.templates;
  source.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    ui.template.appendChild(opt);
  });
  if (previous && source.includes(previous)) {
    ui.template.value = previous;
  } else {
    ui.template.value = '';
  }
}

function card(item) {
  const el = document.createElement('div');
  el.className = 'result-card';
  const periodText = item.period ? frappe.utils.escape_html(item.period) : 'Libre';
  el.innerHTML = `
    <div class="status"><span class="dot"></span> Finalizada</div>
    <h5 class="title">${frappe.utils.escape_html(item.name)}</h5>
    <div class="meta">${periodText}</div>
    <div class="meta">${item.template ? frappe.utils.escape_html(item.template) : 'Sin plantilla'}</div>
    <div class="actions">
      <button type="button"
              class="btn btn-purple-main btn-sm btn-view-results"
              data-doc="${frappe.utils.escape_html(item.docname)}"
              data-name="${frappe.utils.escape_html(item.name)}"
              data-category="${frappe.utils.escape_html(item.category || '')}">
        Ver Resultados
      </button>
    </div>
  `;
  return el;
}

function render(list) {
  ui.grid.innerHTML = '';
  if (!list || list.length === 0) {
    ui.empty.classList.remove('d-none');
    return;
  }
  ui.empty.classList.add('d-none');
  const frag = document.createDocumentFragment();
  list.forEach(i => frag.appendChild(card(i)));
  ui.grid.appendChild(frag);
}

async function fetchFiltered() {
  const name = ui.name.value.trim();
  const template = ui.template.value.trim();
  try {
    const r = await frappe.call({
      method: 'liseniq.www.iq-results.index.get_finalized_surveys',
      args: { name, template }
    });
    const msg = r.message || {};
    state.items = msg.items || [];
    fillTemplateSelect();
    render(state.items);
  } catch (e) {
    console.error(e);
    render([]);
  }
}

async function fetchEmbedConfig(params = {}) {
  const r = await frappe.call({
    method: 'liseniq.www.iq-results.index.get_power_bi_embed_config',
    args: params
  });
  const cfg = r && r.message ? r.message : null;
  if (cfg) state.embedConfig = cfg;
  return cfg;
}

function initEvents() {
  ui.name?.addEventListener('input', () => {
    clearTimeout(state.debounce);
    state.debounce = setTimeout(fetchFiltered, 350);
  });
  
  ui.template?.addEventListener('change', fetchFiltered);
  
  ui.grid?.addEventListener('click', e => {
    const btn = e.target.closest('.btn-view-results');
    if (!btn) return;
    openReportModal(btn.dataset.doc, btn.dataset.name, btn.dataset.category);
  });
  
  ui.backBtn?.addEventListener('click', backToResults);
  
  ui.clearName?.addEventListener('click', () => {
    if (!ui.name) return;
    if (ui.name.value === '') return;
    ui.name.value = '';
    fetchFiltered();
    ui.name.focus();
  });

  // Eventos del Modal
  ui.closeReportModal?.addEventListener('click', closeReportModal);
  
  ui.reportModal?.addEventListener('click', e => {
    if(e.target === ui.reportModal) closeReportModal();
  });

  ui.btnAiqReport?.addEventListener('click', () => {
    if(ui.btnAiqReport.classList.contains('disabled')) return;
    goToAiqReport();
  });

  ui.btnPbiReport?.addEventListener('click', () => {
    if(ui.btnPbiReport.classList.contains('disabled')) return;
    goToPbiReport();
  });

  ui.btnDashboard?.addEventListener('click', () => {
    if(ui.btnDashboard.classList.contains('disabled')) return;
    goToDashboard();
  });
}

function backToResults() {
  const step1Card = ui.grid?.closest('.card');
  if (step1Card) step1Card.classList.remove('d-none');
  ui.step2?.classList.add('d-none');
}

// Modal de selección de reporte (AIQ vs PowerBI)
function openReportModal(doc, name, category) {
  state.selectedDoc = doc;
  state.selectedName = name;
  state.selectedCategory = category;

  const hasAiq = hasFeature('aiq_reports');
  const hasPbi = hasFeature('bi_reports');

  // Configuración de la tarjeta AIQ
  const aiqLabel = ui.btnAiqReport.querySelector('.upgrade-label');
  if (hasAiq) {
      ui.btnAiqReport.classList.remove('disabled');
      aiqLabel.classList.add('d-none');
  } else {
      ui.btnAiqReport.classList.add('disabled');
      aiqLabel.classList.remove('d-none');
  }

  // Configuración de la tarjeta PBI
  const pbiLabel = ui.btnPbiReport.querySelector('.upgrade-label');
  if (hasPbi) {
      ui.btnPbiReport.classList.remove('disabled');
      pbiLabel.classList.add('d-none');
  } else {
      ui.btnPbiReport.classList.add('disabled');
      pbiLabel.classList.remove('d-none');
  }

  ui.reportModal?.classList.remove('d-none');
}

function closeReportModal() {
  ui.reportModal?.classList.add('d-none');
  state.selectedDoc = null;
  state.selectedName = null;
  state.selectedCategory = null;
}

// Navegación a Listen AIQ
function goToAiqReport() {
  if(!state.selectedDoc) return;
  window.location.href = `/iq-results/aiq_reports?survey_name=${encodeURIComponent(state.selectedDoc)}&survey_title=${encodeURIComponent(state.selectedName)}`;
}

// Renderizado y Navegación a PowerBI
async function goToPbiReport() {
  if(!state.selectedDoc) return;
  const doc = state.selectedDoc;
  
  closeReportModal();

  const step1Card = ui.grid?.closest('.card');
  if (step1Card) step1Card.classList.add('d-none');
  
  if (ui.step2?.classList.contains('d-none')) ui.step2.classList.remove('d-none');
  
  try {
    await ensurePowerBISDK();
    await fetchEmbedConfig({ survey_docname: doc });
    embedPowerBI();
  } catch (e) {
    console.error('Error al mostrar resultados / embebido PBI', e);
  }
}

async function goToDashboard() {
  if (!state.selectedDoc) return;

  const surveyName = state.selectedDoc;
  const surveyTitle = state.selectedName || '';
  const category = (state.selectedCategory || '').toLowerCase();
  const dashboardPath = category.includes('cultura') ? '/cultura-dashboard' : '/engagement-dashboard';

  const params = new URLSearchParams({
    survey: surveyName,
    survey_name: surveyName,
    survey_title: surveyTitle
  });

  window.open(`${dashboardPath}?${params.toString()}`, '_blank');
  closeReportModal();
}
// Configuración y funciones de embebido de Power BI
function ensurePowerBISDK() {
  if (window.powerbi && window['powerbi-client']) {
    return Promise.resolve();
  }
  if (state.pbiSdkReady) return state.pbiSdkReady;
  state.pbiSdkReady = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/powerbi-client@2.23.1/dist/powerbi.min.js';
    s.async = true;
    s.onload = () => resolve();
    s.onerror = (e) => reject(e);
    document.head.appendChild(s);
  });
  return state.pbiSdkReady;
}

function embedPowerBI() {
  try {
    if (!ui.pbi || !state.embedConfig) return;
    if (!window.powerbi || !window['powerbi-client']) return;
    const models = window['powerbi-client'].models;
    const config = {
      type: 'report',
      id: state.embedConfig.reportId,
      embedUrl: state.embedConfig.embedUrl,
      accessToken: state.embedConfig.embedToken,
      tokenType: models.TokenType.Embed,
      permissions: models.Permissions.Read,
      settings: {
        panes: { filters: { visible: false }, pageNavigation: { visible: true } },
        layoutType: models.LayoutType.Responsive,
        background: models.BackgroundType.Transparent
      }
    };
    if (state.embedConfig.filters && Array.isArray(state.embedConfig.filters)) {
      config.filters = state.embedConfig.filters;
    }

    console.log("Configuración enviada a Power BI:", config);

    if (window.powerbi.find(ui.pbi)) {
      window.powerbi.reset(ui.pbi);
    }
    const report = window.powerbi.embed(ui.pbi, config);

    report.on('loaded', async () => {
        try {
            const appliedFilters = await report.getFilters();
            console.log("🔍 Filtros aplicados en el reporte PBI ya cargado:", appliedFilters);
        } catch (err) {
            console.error("No se pudo obtener la lista de filtros aplicados", err);
        }
    });

    report.off('tokenExpired');
    report.on('tokenExpired', async () => {
      try {
        const fresh = await fetchEmbedConfig({
          report_id: state.embedConfig.reportId,
          workspace_id: state.embedConfig.groupId
        });
        if (fresh && fresh.embedToken) {
          await report.setAccessToken(fresh.embedToken);
          state.embedConfig = fresh;
        }
      } catch (err) {
        console.error('Power BI token refresh error', err);
      }
    });
  } catch (e) {
    console.error('Power BI embed error', e);
  }
}

(function boot() {
  if (!ui.grid) return;

  initPreloaded();
  const params = new URLSearchParams(window.location.search);
  const preName = params.get('name');
  if (preName && ui.name) {
    ui.name.value = decodeURIComponent(preName);
  }
  fillTemplateSelect();
  if (preName) {
    fetchFiltered();
  } else {
    render(state.items);
  }
  initEvents();
})();