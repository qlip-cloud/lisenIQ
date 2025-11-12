const ui = {
  preload: document.getElementById('results-preloaded'),
  grid: document.getElementById('results-grid'),
  empty: document.getElementById('results-empty'),
  name: document.getElementById('filter-name'),
  template: document.getElementById('filter-template'),
};

const state = { items: [], templates: [], debounce: null };

function initPreloaded() {
  if (!ui.preload) return;
  try {
    state.items = JSON.parse(ui.preload.dataset.surveys || '[]');
    state.templates = JSON.parse(ui.preload.dataset.templates || '[]');
  } catch {
    state.items = [];
    state.templates = [];
  }
}

function fillTemplateSelect() {
  if (!ui.template) return;
  ui.template.querySelectorAll('option:not([value=""])').forEach(o => o.remove());
  state.templates.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    ui.template.appendChild(opt);
  });
}

function card(item) {
  const el = document.createElement('div');
  el.className = 'result-card';
  const periodText = item.period ? frappe.utils.escape_html(item.period) : 'Libre';
  el.innerHTML = `
    <div class="status"><span class="dot"></span> Finalizada</div>
    <h5 class="title">${frappe.utils.escape_html(item.name)}</h5>
    <div class="meta"></i> ${periodText}</div>
    <div class="meta">${item.template ? frappe.utils.escape_html(item.template) : 'Sin plantilla'}</div>
    <div class="actions">
      <a href="/iq-measurement?name=${encodeURIComponent(item.docname)}" class="btn btn-purple-main btn-sm">Ver Resultados</a>
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
    state.templates = msg.templates || [];
    fillTemplateSelect();
    render(state.items);
  } catch (e) {
    console.error(e);
    render([]);
  }
}

function initEvents() {
  ui.name?.addEventListener('input', () => {
    clearTimeout(state.debounce);
    state.debounce = setTimeout(fetchFiltered, 350);
  });
  ui.template?.addEventListener('change', fetchFiltered);
}

(function boot() {
  if (!ui.grid) return;
  initPreloaded();
  fillTemplateSelect();
  render(state.items);
  initEvents();
})();
