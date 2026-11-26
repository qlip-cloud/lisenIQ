// Módulo frontend de Gestión de Mejoras (Action Plans) - Listen AIQ

const API_BASE = "liseniq.www.iq-action-plan.index";
const DEBOUNCE_DELAY_MS = 300;
const DEFAULT_SCALE_MIN = 1;
const DEFAULT_SCALE_MAX = 5;
const NO_SCORE_MESSAGE =
    "No hay un resultado disponible para este elemento en la medición seleccionada. Elige otro alcance o verifica los resultados.";

const state = {
    activeView: "dashboard",
    company: "",
    kpis: {
        active_plans: 0,
        finished_plans: 0,
        achieved_goals: 0,
        pending_eval_goals: 0,
        pending_tasks: 0,
        overdue_tasks: 0,
        total_plans: 0,
    },
    items: [],
    filterOptions: {
        statuses: [],
        goal_statuses: [],
        categories: [],
        priorities: [],
        scope_types: [],
        task_statuses: [],
        responsibles: [],
        surveys: [],
        years: [],
    },
    filters: {
        search: "",
        status: "",
        goal_status: "",
        responsible: "",
        category: "",
        priority: "",
        origin_survey: "",
        year: "",
    },
    wizard: {
        step: 1,
        isEdit: false,
        planId: "",
        ap_status: "",
        ap_name: "",
        ap_category: "",
        ap_objective: "",
        ap_description: "",
        ap_priority: "",
        ap_responsible: "",
        ap_start_date: "",
        ap_target_date: "",
        ap_origin_survey: "",
        ap_scope_type: "Medición",
        ap_dimension: "",
        ap_dimension_label: "",
        ap_topic: "",
        ap_topic_label: "",
        ap_question: "",
        ap_question_label: "",
        ap_scope_label: "",
        has_valid_score: true,
        score_error_message: "",
        ap_initial_score: 0,
        ap_target_score: 4.5,
        ap_scale_min: DEFAULT_SCALE_MIN,
        ap_scale_max: DEFAULT_SCALE_MAX,
        tasks: [],
        scopeCatalog: {
            dimensions: [],
            topics: [],
            allTopics: [],
            questions: [],
            allQuestions: [],
        },
    },
    currentDetail: null,
};

// Escapa caracteres HTML para prevenir XSS
function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Retrasa la ejecución de una función para entradas de búsqueda
function debounce(fn, delay = DEBOUNCE_DELAY_MS) {
    let timerId = null;
    return function (...args) {
        if (timerId) clearTimeout(timerId);
        timerId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Invoca métodos @frappe.whitelist() en index.py usando frappe.call
 * o fetch nativo como respaldo con token CSRF.
 */
async function callBackend(methodName, args = {}, httpMethod = "POST") {
    const fullMethod = `${API_BASE}.${methodName}`;
    if (window.frappe && typeof window.frappe.call === "function") {
        return new Promise((resolve, reject) => {
            window.frappe.call({
                method: fullMethod,
                args,
                type: httpMethod,
                callback: (r) => resolve(r && r.message !== undefined ? r.message : null),
                error: (err) => reject(err),
            });
        });
    }

    const headers = {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": (window.frappe && window.frappe.csrf_token) || "",
    };

    let url = `/api/method/${fullMethod}`;
    const fetchOpts = { method: httpMethod, headers, credentials: "same-origin" };
    if (httpMethod === "GET") {
        const qs = new URLSearchParams();
        Object.entries(args).forEach(([k, v]) => {
            qs.set(k, typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));
        });
        url += `?${qs.toString()}`;
    } else {
        fetchOpts.body = JSON.stringify(args);
    }

    const res = await fetch(url, fetchOpts);
    if (!res.ok) throw new Error(`Error HTTP ${res.status}`);
    const json = await res.json();
    return json.message;
}

// Muestra alerta en la barra de notificación global de Listen AIQ
function showNotification(message, type = "error") {
    const bar = document.getElementById("global-notification-bar");
    const msgSpan = document.getElementById("global-notification-message");
    if (bar) {
        if (msgSpan) msgSpan.textContent = message;
        else bar.textContent = message;
        bar.classList.remove("notification-success", "notification-error");
        bar.classList.add(type === "success" ? "notification-success" : "notification-error", "show");
        setTimeout(() => bar.classList.remove("show"), 4200);
    } else if (window.frappe && typeof window.frappe.show_alert === "function") {
        window.frappe.show_alert({ message, indicator: type === "success" ? "green" : "red" });
    }
}

// Lee el JSON precargado en el DOM por get_context
function loadPreloadedContext() {
    const preloadEl = document.getElementById("ap-preloaded-data");
    if (!preloadEl) return;

    state.company = preloadEl.dataset.company || "";

    try {
        const dashboard = JSON.parse(preloadEl.dataset.dashboard || "{}");
        if (dashboard.kpis) state.kpis = { ...state.kpis, ...dashboard.kpis };
        if (Array.isArray(dashboard.items)) state.items = dashboard.items;
    } catch (e) {
        console.error("[iq_action_plan] Error al parsear dashboard inicial:", e);
    }

    try {
        const opts = JSON.parse(preloadEl.dataset.filterOptions || "{}");
        state.filterOptions = { ...state.filterOptions, ...opts };
    } catch (e) {
        console.error("[iq_action_plan] Error al parsear filterOptions:", e);
    }
}

// Rellena un elemento <select> con strings u objetos {id, label}
function populateSelect(selectId, items, defaultLabel = null, preserveSelection = true) {
    const selectEl = document.getElementById(selectId);
    if (!selectEl) return;

    const currentVal = preserveSelection ? selectEl.value : "";
    const html = [];
    if (defaultLabel !== null) {
        html.push(`<option value="">${escapeHtml(defaultLabel)}</option>`);
    }

    if (Array.isArray(items)) {
        items.forEach((item) => {
            if (item && typeof item === "object") {
                html.push(
                    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label || item.id)}</option>`
                );
            } else if (item !== null && item !== undefined && String(item).trim() !== "") {
                html.push(`<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`);
            }
        });
    }

    selectEl.innerHTML = html.join("");
    if (currentVal && Array.from(selectEl.options).some((opt) => opt.value === currentVal)) {
        selectEl.value = currentVal;
    }
}

// Obtiene el ID de una opción del catálogo (compatible con string o {id, label})
function getOptionId(optionItem) {
    if (!optionItem) return "";
    if (typeof optionItem === "object") return optionItem.id || "";
    return String(optionItem);
}

// Resuelve el ID de categoría a partir de su name o qnc_category
function resolveCategoryValue(rawCategory) {
    if (!rawCategory) return "";
    const categories = state.filterOptions.categories || [];
    for (let i = 0; i < categories.length; i += 1) {
        const item = categories[i];
        if (item && typeof item === "object") {
            if (item.id === rawCategory || item.label === rawCategory) {
                return item.id;
            }
        } else if (item === rawCategory) {
            return String(item);
        }
    }
    return rawCategory;
}

// Obtiene la etiqueta legible (dt_title, qnc_category o qn_statement) de un catálogo a partir de su ID
function findLabelById(list, id) {
    if (!id) return "-";
    const match = (list || []).find((item) => {
        if (item && typeof item === "object") {
            return item.id === id || item.label === id;
        }
        return String(item) === String(id);
    });
    if (!match) return id;
    return typeof match === "object" ? match.label || match.id : String(match);
}

// Formatea un puntaje numérico a 2 decimales (ej. 4.19)
function formatScoreValue(val) {
    const num = Number(val ?? 0);
    if (Number.isNaN(num)) return "0.00";
    return num.toFixed(2);
}

// Inicializa las listas desplegables de filtros, asistente y detalle desde los catálogos del backend
function renderFilterCatalogs() {
    const opts = state.filterOptions;
    populateSelect("ap-filter-status", opts.statuses, "Todos");
    populateSelect("ap-filter-goal-status", opts.goal_statuses, "Todas");
    populateSelect("ap-filter-responsible", opts.responsibles, "Todos");
    populateSelect("ap-filter-category", opts.categories, "Todas");
    populateSelect("ap-filter-priority", opts.priorities, "Todas");
    populateSelect("ap-filter-survey", opts.surveys, "Todas");
    populateSelect("ap-filter-year", opts.years, "Todos");

    populateSelect("wiz-category", opts.categories, null);
    populateSelect("wiz-priority", opts.priorities, null);
    populateSelect("wiz-scope-type", opts.scope_types, null);
    populateSelect("wiz-responsible", opts.responsibles, "Seleccionar responsable...");
    populateSelect("wiz-survey", opts.surveys, "Seleccionar medición...");

    const detStatusItems = (opts.statuses || []).map((st) => {
        const id = getOptionId(st);
        const label = typeof st === "object" ? st.label || st.id : st;
        return { id, label: `Estado: ${label}` };
    });
    populateSelect("det-change-status", detStatusItems, null);
}

// Renderiza los contadores de las 6 tarjetas KPI
function renderKpis() {
    const k = state.kpis || {};
    const map = {
        "kpi-active-plans": k.active_plans ?? 0,
        "kpi-finished-plans": k.finished_plans ?? 0,
        "kpi-achieved-goals": k.achieved_goals ?? 0,
        "kpi-pending-eval-goals": k.pending_eval_goals ?? 0,
        "kpi-pending-tasks": k.pending_tasks ?? 0,
        "kpi-overdue-tasks": k.overdue_tasks ?? 0,
    };

    Object.entries(map).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = Number(val || 0).toLocaleString("es-ES");
    });

    document.querySelectorAll(".ap-kpi-card[data-kpi-filter]").forEach((card) => {
        const key = card.dataset.kpiFilter;
        const val = card.dataset.kpiValue;
        card.classList.toggle("ap-kpi-card--active", state.filters[key] === val);
    });
}

// Clases semánticas para píldoras de prioridad, estado y meta
function getPriorityPillClass(priority) {
    switch (priority) {
        case "Crítica":
        case "Alta":
            return "ap-pill-priority--high";
        case "Media":
            return "ap-pill-priority--medium";
        case "Baja":
        default:
            return "ap-pill-priority--low";
    }
}

function getStatusPillClass(status) {
    switch (status) {
        case "En ejecución":
            return "ap-pill-status--active";
        case "Finalizado":
            return "ap-pill-status--finished";
        case "Cancelado":
            return "ap-pill-status--cancelled";
        case "Borrador":
        default:
            return "ap-pill-status--draft";
    }
}

function getGoalPillClass(goalStatus) {
    switch (goalStatus) {
        case "Meta alcanzada":
            return "ap-pill-goal--achieved";
        case "Meta parcialmente alcanzada":
            return "ap-pill-goal--partial";
        case "Meta no alcanzada":
            return "ap-pill-goal--failed";
        case "Pendiente de evaluación":
        default:
            return "ap-pill-goal--pending";
    }
}

// Verifica si algún filtro tiene valor activo
function hasActiveFilters() {
    return Object.values(state.filters).some((v) => String(v || "").trim() !== "");
}

// Renderiza las filas de la tabla principal incluyendo la columna Alcance (Punto 7 / Sección 5.1)
function renderPlansTable() {
    const tbody = document.getElementById("ap-table-body");
    const tableContainer = document.getElementById("ap-table-container");
    const emptyState = document.getElementById("ap-empty-state");
    const emptyClearBtn = document.getElementById("btn-empty-clear-filters");
    const resetFiltersBtn = document.getElementById("btn-reset-filters");
    const counterEl = document.getElementById("ap-results-counter");

    if (!tbody || !tableContainer || !emptyState) return;

    const items = Array.isArray(state.items) ? state.items : [];
    const count = items.length;
    const activeFilters = hasActiveFilters();

    if (counterEl) {
        counterEl.textContent = count === 1 ? "1 resultado" : `${count} resultados`;
    }
    if (resetFiltersBtn) {
        resetFiltersBtn.classList.toggle("d-none", !activeFilters);
    }

    if (count === 0) {
        tbody.innerHTML = "";
        tableContainer.classList.add("d-none");
        emptyState.classList.remove("d-none");
        if (emptyClearBtn) emptyClearBtn.classList.toggle("d-none", !activeFilters);
        return;
    }

    emptyState.classList.add("d-none");
    tableContainer.classList.remove("d-none");

    tbody.innerHTML = items
        .map((plan) => {
            const docname = escapeHtml(plan.name);
            const planName = escapeHtml(plan.ap_name || plan.name);
            const surveyName = escapeHtml(plan.origin_survey_name || "-");
            const scopeType = escapeHtml(plan.ap_scope_type || "Medición");
            const scopeLabel = escapeHtml(plan.ap_scope_label || "-");
            const responsibleName = escapeHtml(plan.responsible_name || "-");
            const rawCategoryLabel =
                plan.category_name ||
                findLabelById(state.filterOptions.categories, plan.ap_category) ||
                plan.ap_category ||
                "-";
            const category = escapeHtml(rawCategoryLabel);
            const priority = escapeHtml(plan.ap_priority || "Media");
            const status = escapeHtml(plan.ap_status || "Borrador");
            const goalStatus = escapeHtml(plan.ap_goal_status || "Pendiente de evaluación");
            const pct = Math.max(0, Math.min(100, Math.round(Number(plan.ap_progress_pct || 0))));
            const targetDate = escapeHtml(plan.ap_target_date_formatted || "-");

            return `
                <tr class="ap-table-row" data-plan-name="${docname}" tabindex="0" role="button" aria-label="Abrir plan ${planName}">
                    <td class="ap-cell-plan">
                        <div class="ap-plan-primary">${planName}</div>
                        <div class="ap-plan-secondary">${surveyName}</div>
                    </td>
                    <td class="ap-cell-scope">
                        <div class="ap-scope-badge-type">${scopeType}</div>
                        <div class="ap-plan-secondary" title="${scopeLabel}">${scopeLabel}</div>
                    </td>
                    <td class="ap-cell-text">${responsibleName}</td>
                    <td class="ap-cell-text">${category}</td>
                    <td>
                        <span class="ap-pill-priority ${getPriorityPillClass(plan.ap_priority)}">${priority}</span>
                    </td>
                    <td>
                        <span class="ap-pill-status ${getStatusPillClass(plan.ap_status)}">
                            <span class="ap-status-dot"></span>${status}
                        </span>
                    </td>
                    <td>
                        <span class="ap-pill-goal ${getGoalPillClass(plan.ap_goal_status)}">${goalStatus}</span>
                    </td>
                    <td class="ap-cell-progress">
                        <div class="ap-inline-progress">
                            <div class="ap-inline-bar-track">
                                <div class="ap-inline-bar-fill" style="width: ${pct}%;"></div>
                            </div>
                            <span class="ap-inline-bar-pct">${pct}%</span>
                        </div>
                    </td>
                    <td class="ap-cell-date">${targetDate}</td>
                </tr>
            `;
        })
        .join("");
}

// Consulta KPIs y planes actualizados aplicando los filtros activos
async function fetchDashboardData() {
    const loader = document.getElementById("ap-loading-state");
    const tableContainer = document.getElementById("ap-table-container");
    if (loader) loader.classList.remove("d-none");
    if (tableContainer) tableContainer.classList.add("ap-table-loading");

    try {
        const data = await callBackend(
            "get_action_plans_dashboard",
            { filters: state.filters },
            "GET"
        );
        if (data) {
            if (data.kpis) state.kpis = { ...state.kpis, ...data.kpis };
            if (Array.isArray(data.items)) state.items = data.items;
            renderKpis();
            renderPlansTable();
        }
    } catch (err) {
        console.error("[iq_action_plan] Error filtrando planes:", err);
        showNotification("No fue posible actualizar el listado de planes.", "error");
    } finally {
        if (loader) loader.classList.add("d-none");
        if (tableContainer) tableContainer.classList.remove("ap-table-loading");
    }
}

// Limpia todos los filtros y recarga el listado
function resetAllFilters() {
    state.filters = {
        search: "",
        status: "",
        goal_status: "",
        responsible: "",
        category: "",
        priority: "",
        origin_survey: "",
        year: "",
    };

    const searchInput = document.getElementById("ap-filter-search");
    const clearBtn = document.getElementById("ap-search-clear");
    if (searchInput) searchInput.value = "";
    if (clearBtn) clearBtn.classList.add("d-none");

    [
        "ap-filter-status",
        "ap-filter-goal-status",
        "ap-filter-responsible",
        "ap-filter-category",
        "ap-filter-priority",
        "ap-filter-survey",
        "ap-filter-year",
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });

    fetchDashboardData();
}

// Alterna entre las vistas 'dashboard', 'wizard' y 'detail'
function switchView(viewName) {
    state.activeView = viewName;
    const views = {
        dashboard: document.getElementById("view-dashboard"),
        wizard: document.getElementById("view-wizard"),
        detail: document.getElementById("view-detail"),
    };

    Object.entries(views).forEach(([key, el]) => {
        if (el) el.classList.toggle("d-none", key !== viewName);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// Retorna la fecha actual en formato YYYY-MM-DD
function getTodayIso() {
    return new Date().toISOString().split("T")[0];
}

// Inicializa el Wizard en modo creación con estado inicial Borrador (Punto 1 / HU-01)
function openWizardForCreate() {
    const opts = state.filterOptions;
    const defaultCategory = getOptionId(opts.categories[0]);
    const defaultResp = opts.responsibles[0]?.id || "";
    const defaultSurvey = opts.surveys[0]?.id || "";
    const today = getTodayIso();

    state.wizard = {
        step: 1,
        isEdit: false,
        planId: "",
        ap_status: getOptionId((opts.statuses || [])[0]) || "Borrador",
        ap_name: "",
        ap_category: defaultCategory,
        ap_objective: "",
        ap_description: "",
        ap_priority: getOptionId((opts.priorities || []).find((pr) => getOptionId(pr) === "Media") || (opts.priorities || [])[0]) || "Media",
        ap_responsible: defaultResp,
        ap_start_date: today,
        ap_target_date: today,
        ap_origin_survey: defaultSurvey,
        ap_scope_type: getOptionId(opts.scope_types[0]) || "Medición",
        ap_dimension: "",
        ap_dimension_label: "",
        ap_topic: "",
        ap_topic_label: "",
        ap_question: "",
        ap_question_label: "",
        ap_scope_label: "",
        has_valid_score: true,
        score_error_message: "",
        ap_initial_score: 0,
        ap_target_score: 4.5,
        ap_scale_min: DEFAULT_SCALE_MIN,
        ap_scale_max: DEFAULT_SCALE_MAX,
        tasks: [
            {
                apt_title: "",
                apt_responsible: defaultResp,
                apt_due_date: today,
                apt_status: getOptionId(opts.task_statuses[0]) || "Pendiente",
            },
        ],
        scopeCatalog: {
            dimensions: [],
            topics: [],
            allTopics: [],
            questions: [],
            allQuestions: [],
        },
    };

    const titleEl = document.getElementById("wizard-main-title");
    const crumbEl = document.getElementById("wizard-breadcrumb-current");
    const submitLbl = document.getElementById("btn-wizard-submit-label");
    if (titleEl) titleEl.textContent = "Nuevo Plan de Mejora";
    if (crumbEl) crumbEl.textContent = "Nuevo Plan";
    if (submitLbl) submitLbl.textContent = "Crear Plan";

    syncWizardInputsFromState();
    if (defaultSurvey) {
        loadScopeCatalogForSurvey(defaultSurvey);
    } else {
        populateSelect("wiz-dimension", [], "Seleccionar dimensión...", false);
        populateSelect("wiz-topic", [], "Seleccionar tema...", false);
        populateSelect("wiz-question", [], "Selecciona pregunta", false);
    }
    setWizardStep(1);
    switchView("wizard");
}

// Inicializa el Wizard precargando un plan existente para edición
function openWizardForEdit(plan) {
    if (!plan) return;
    const defaultCategory = getOptionId(state.filterOptions.categories[0]);
    const resolvedCat = resolveCategoryValue(plan.ap_category) || defaultCategory;

    state.wizard = {
        step: 1,
        isEdit: true,
        planId: plan.name,
        ap_status: plan.ap_status || "Borrador",
        ap_name: plan.ap_name || "",
        ap_category: resolvedCat,
        ap_objective: plan.ap_objective || "",
        ap_description: plan.ap_description || "",
        ap_priority: plan.ap_priority || "Media",
        ap_responsible: plan.ap_responsible || "",
        ap_start_date: plan.ap_start_date || getTodayIso(),
        ap_target_date: plan.ap_target_date || getTodayIso(),
        ap_origin_survey: plan.ap_origin_survey || "",
        ap_scope_type: plan.ap_scope_type || "Medición",
        ap_dimension: plan.ap_dimension || "",
        ap_dimension_label: plan.dimension_label || "",
        ap_topic: plan.ap_topic || "",
        ap_topic_label: plan.topic_label || "",
        ap_question: plan.ap_question || "",
        ap_question_label: plan.question_label || "",
        ap_scope_label: plan.ap_scope_label || "",
        has_valid_score: true,
        score_error_message: "",
        ap_initial_score: Number(plan.ap_initial_score ?? 0),
        ap_target_score: Number(plan.ap_target_score ?? 4.5),
        ap_scale_min: Number(plan.ap_scale_min ?? DEFAULT_SCALE_MIN),
        ap_scale_max: Number(plan.ap_scale_max ?? DEFAULT_SCALE_MAX),
        tasks:
            Array.isArray(plan.tasks) && plan.tasks.length > 0
                ? plan.tasks.map((t) => ({
                      apt_title: t.apt_title || "",
                      apt_responsible: t.apt_responsible || plan.ap_responsible || "",
                      apt_due_date: t.apt_due_date || plan.ap_target_date || getTodayIso(),
                      apt_status: t.apt_status || "Pendiente",
                  }))
                : [],
        scopeCatalog: {
            dimensions: [],
            topics: [],
            allTopics: [],
            questions: [],
            allQuestions: [],
        },
    };

    const titleEl = document.getElementById("wizard-main-title");
    const crumbEl = document.getElementById("wizard-breadcrumb-current");
    const submitLbl = document.getElementById("btn-wizard-submit-label");
    if (titleEl) titleEl.textContent = "Editar Plan de Mejora";
    if (crumbEl) crumbEl.textContent = plan.ap_name || "Editar Plan";
    if (submitLbl) submitLbl.textContent = "Guardar Cambios";

    syncWizardInputsFromState();
    if (state.wizard.ap_origin_survey) {
        loadScopeCatalogForSurvey(state.wizard.ap_origin_survey);
    }
    setWizardStep(1);
    switchView("wizard");
}

// Sincroniza los campos del DOM con el estado actual del Wizard
function syncWizardInputsFromState() {
    const w = state.wizard;
    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val ?? "";
    };

    setVal("wiz-name", w.ap_name);
    setVal("wiz-category", w.ap_category);
    setVal("wiz-objective", w.ap_objective);
    setVal("wiz-description", w.ap_description);
    setVal("wiz-priority", w.ap_priority);
    setVal("wiz-responsible", w.ap_responsible);
    setVal("wiz-start-date", w.ap_start_date);
    setVal("wiz-target-date", w.ap_target_date);
    setVal("wiz-survey", w.ap_origin_survey);
    setVal("wiz-scope-type", w.ap_scope_type);
    setVal("wiz-target-score", w.ap_target_score);

    updateScopeSelectorsVisibility();
    renderWizardGoalPreview();
    renderWizardTasksTable();
}

// Habilita y muestra los selectores de Dimensión, Tema y Pregunta según el tipo de alcance (Sección 6)
function updateScopeSelectorsVisibility() {
    const scopeType = state.wizard.ap_scope_type;
    const rowDimTopic = document.getElementById("wiz-scope-dim-topic-row");
    const grpDim = document.getElementById("wiz-dimension-group");
    const grpTopic = document.getElementById("wiz-topic-group");
    const grpQuestion = document.getElementById("wiz-question-group");
    const topicReqMark = document.getElementById("wiz-topic-req");
    const dimSelect = document.getElementById("wiz-dimension");
    const topicSelect = document.getElementById("wiz-topic");
    const questionSelect = document.getElementById("wiz-question");

    const showDim = ["Dimensión", "Tema", "Pregunta"].includes(scopeType);
    const showTopic = ["Tema", "Pregunta"].includes(scopeType);
    const showQuestion = scopeType === "Pregunta";

    if (rowDimTopic) rowDimTopic.classList.toggle("d-none", !showDim);
    if (grpDim) grpDim.classList.toggle("d-none", !showDim);
    if (grpTopic) grpTopic.classList.toggle("d-none", !showTopic);
    if (grpQuestion) grpQuestion.classList.toggle("d-none", !showQuestion);

    if (topicReqMark) {
        topicReqMark.classList.toggle("d-none", scopeType !== "Tema");
    }

    if (dimSelect) dimSelect.disabled = !showDim;
    if (topicSelect) topicSelect.disabled = !showTopic;
    if (questionSelect) questionSelect.disabled = !showQuestion;
}

// Filtra los temas mostrados en #wiz-topic según la medición y la dimensión seleccionadas
function filterAndRenderTopicsSelect() {
    const w = state.wizard;
    const allTopics = w.scopeCatalog.allTopics || w.scopeCatalog.topics || [];

    let filteredTopics = allTopics;
    if (w.ap_dimension) {
        const byDim = allTopics.filter(
            (t) =>
                !Array.isArray(t.dimensions) ||
                t.dimensions.length === 0 ||
                t.dimensions.includes(w.ap_dimension)
        );
        filteredTopics = byDim.length > 0 ? byDim : allTopics;
    }
    w.scopeCatalog.topics = filteredTopics;

    const topicPlaceholder =
        w.ap_scope_type === "Pregunta"
            ? "Todos los temas / Sin tema..."
            : "Seleccionar tema...";

    populateSelect("wiz-topic", filteredTopics, topicPlaceholder, false);

    const topicEl = document.getElementById("wiz-topic");
    if (topicEl) {
        if (w.ap_topic && filteredTopics.some((t) => t.id === w.ap_topic)) {
            topicEl.value = w.ap_topic;
            w.ap_topic_label = findLabelById(allTopics, w.ap_topic);
        } else {
            if (w.ap_scope_type !== "Pregunta") {
                w.ap_topic = "";
                w.ap_topic_label = "";
            }
            topicEl.value = "";
        }
    }
}

// Filtra las preguntas mostradas en #wiz-question según la medición, Dimensión y Tema seleccionados
function filterAndRenderQuestionsSelect() {
    const w = state.wizard;
    const baseQuestions = w.scopeCatalog.allQuestions || w.scopeCatalog.questions || [];

    const filtered = baseQuestions.filter((q) => {
        const matchDim = !w.ap_dimension || q.dimension === w.ap_dimension;
        const matchTopic = !w.ap_topic || q.topic === w.ap_topic;
        return matchDim && matchTopic;
    });
    w.scopeCatalog.questions = filtered;

    populateSelect("wiz-question", filtered, "Selecciona pregunta", false);

    const questionEl = document.getElementById("wiz-question");
    if (questionEl) {
        if (w.ap_question && filtered.some((q) => q.id === w.ap_question)) {
            questionEl.value = w.ap_question;
            const qMatch = filtered.find((q) => q.id === w.ap_question);
            if (qMatch) {
                w.ap_question_label = qMatch.label || w.ap_question;
                if (!w.ap_topic && qMatch.topic) {
                    w.ap_topic = qMatch.topic;
                    w.ap_topic_label =
                        qMatch.topic_label ||
                        findLabelById(w.scopeCatalog.allTopics || [], qMatch.topic);
                }
            }
        } else {
            w.ap_question = "";
            w.ap_question_label = "";
            questionEl.value = "";
        }
    }
}

// Carga desde backend las dimensiones, temas y preguntas atados a la medición seleccionada
async function loadScopeCatalogForSurvey(surveyName) {
    const w = state.wizard;
    if (!surveyName) {
        w.scopeCatalog = {
            dimensions: [],
            topics: [],
            allTopics: [],
            questions: [],
            allQuestions: [],
        };
        populateSelect("wiz-dimension", [], "Seleccionar dimensión...", false);
        populateSelect("wiz-topic", [], "Seleccionar tema...", false);
        populateSelect("wiz-question", [], "Selecciona pregunta", false);
        return;
    }

    try {
        const res = await callBackend(
            "get_survey_scope_options",
            {
                survey_name: surveyName,
                scope_type: w.ap_scope_type,
                dimension: w.ap_dimension,
                topic: w.ap_topic,
            },
            "GET"
        );
        if (res) {
            const allTopics = res.all_topics || res.topics || [];
            const allQuestions = res.all_questions || res.questions || [];
            w.scopeCatalog = {
                dimensions: res.dimensions || [],
                topics: res.topics || allTopics,
                allTopics,
                questions: res.questions || allQuestions,
                allQuestions,
            };

            populateSelect("wiz-dimension", w.scopeCatalog.dimensions, "Seleccionar dimensión...", false);

            const dimEl = document.getElementById("wiz-dimension");
            if (dimEl) {
                if (w.ap_dimension && w.scopeCatalog.dimensions.some((d) => d.id === w.ap_dimension)) {
                    dimEl.value = w.ap_dimension;
                    w.ap_dimension_label = findLabelById(w.scopeCatalog.dimensions, w.ap_dimension);
                } else {
                    w.ap_dimension = "";
                    w.ap_dimension_label = "";
                    dimEl.value = "";
                }
            }

            filterAndRenderTopicsSelect();
            filterAndRenderQuestionsSelect();
        }
        await refreshWizardInitialScore();
    } catch (err) {
        console.error("[iq_action_plan] Error cargando alcance:", err);
    }
}

// Consulta en backend las preguntas y temas de la medición que cumplan con la Dimensión y Tema seleccionados
async function reloadFilteredQuestionsFromBackend() {
    const w = state.wizard;
    if (!w.ap_origin_survey) return;
    try {
        const res = await callBackend(
            "get_survey_scope_options",
            {
                survey_name: w.ap_origin_survey,
                scope_type: w.ap_scope_type,
                dimension: w.ap_dimension,
                topic: w.ap_topic,
            },
            "GET"
        );
        if (res) {
            if (Array.isArray(res.all_topics)) {
                w.scopeCatalog.allTopics = res.all_topics;
            }
            if (Array.isArray(res.topics)) {
                w.scopeCatalog.topics = res.topics;
            }
            if (Array.isArray(res.all_questions)) {
                w.scopeCatalog.allQuestions = res.all_questions;
            }
            if (Array.isArray(res.questions)) {
                w.scopeCatalog.questions = res.questions;
            }
            filterAndRenderQuestionsSelect();
        }
    } catch (err) {
        console.error("[iq_action_plan] Error filtrando preguntas:", err);
    }
}

// Consulta y valida el puntaje inicial oficial para el alcance seleccionado (Punto 6 / Sección 12)
async function refreshWizardInitialScore() {
    const w = state.wizard;
    if (!w.ap_origin_survey) return;
    try {
        const res = await callBackend(
            "get_scope_initial_score",
            {
                survey_name: w.ap_origin_survey,
                scope_type: w.ap_scope_type,
                dimension: w.ap_dimension,
                topic: w.ap_topic,
                question: w.ap_question,
            },
            "GET"
        );
        if (res) {
            w.has_valid_score = res.has_score !== false && res.initial_score !== null;
            w.score_error_message = res.message || "";
            w.ap_initial_score = Number(res.initial_score ?? 0);
            w.ap_scale_min = Number(res.scale_min ?? DEFAULT_SCALE_MIN);
            w.ap_scale_max = Number(res.scale_max ?? DEFAULT_SCALE_MAX);
            w.ap_scope_label = res.scope_label || "";

            // Si estamos creando un plan o la meta actual quedó fuera de la escala (1-5), sugerimos una meta válida
            const outOfBounds =
                Number.isNaN(w.ap_target_score) ||
                w.ap_target_score < w.ap_scale_min ||
                w.ap_target_score > w.ap_scale_max;
            if (w.has_valid_score && (!w.isEdit || outOfBounds)) {
                const suggested = Math.min(
                    w.ap_scale_max,
                    Number((w.ap_initial_score + 0.5).toFixed(2))
                );
                w.ap_target_score = Math.max(w.ap_scale_min, suggested);
            }

            if (res.dimension_label) {
                w.ap_dimension_label = res.dimension_label;
            }
            if (res.topic && !w.ap_topic && w.ap_scope_type === "Pregunta") {
                w.ap_topic = res.topic;
            }
            if (res.topic_label) {
                w.ap_topic_label = res.topic_label;
            }
            if (res.question_label) {
                w.ap_question_label = res.question_label;
            }
            renderWizardGoalPreview();
        }
    } catch (err) {
        w.has_valid_score = false;
        w.score_error_message = NO_SCORE_MESSAGE;
        console.error("[iq_action_plan] Error calculando puntaje inicial:", err);
    }
}

// Actualiza las tarjetas y barra de progreso del Paso 3 (Meta)
function renderWizardGoalPreview() {
    const w = state.wizard;
    const initial = Number(w.ap_initial_score || 0);
    const target = Number(w.ap_target_score || 0);
    const diff = Number((target - initial).toFixed(2));
    const scaleMin = Number(w.ap_scale_min ?? DEFAULT_SCALE_MIN);
    const scaleMax = Number(w.ap_scale_max ?? DEFAULT_SCALE_MAX);
    const scaleMid = Number(((scaleMin + scaleMax) / 2).toFixed(2));

    const initEl = document.getElementById("wiz-initial-score-display");
    const incEl = document.getElementById("wiz-increment-display");
    const scopeCapEl = document.getElementById("wiz-scope-caption");
    const scaleCapEl = document.getElementById("wiz-scale-caption");
    const rangeTextEl = document.getElementById("wiz-goal-range-text");
    const barFillEl = document.getElementById("wiz-goal-bar-fill");
    const targetInput = document.getElementById("wiz-target-score");

    if (targetInput) {
        targetInput.min = String(scaleMin);
        targetInput.max = String(scaleMax);
        targetInput.placeholder = formatScoreValue(scaleMax);
        if (document.activeElement !== targetInput) {
            targetInput.value = target;
        }
    }

    if (initEl) initEl.textContent = formatScoreValue(initial);
    if (incEl) {
        incEl.textContent = diff >= 0 ? `+${diff.toFixed(2)}` : `${diff.toFixed(2)}`;
        incEl.classList.toggle("ap-goal-big-num--green", diff >= 0);
    }
    if (scopeCapEl) {
        scopeCapEl.textContent = w.ap_scope_label || "Resultado de la medición seleccionada";
    }
    if (scaleCapEl) {
        scaleCapEl.textContent = `Puntaje objetivo (${scaleMin}-${scaleMax})`;
    }
    if (rangeTextEl) {
        rangeTextEl.innerHTML = `${formatScoreValue(initial)} &rarr; ${formatScoreValue(target)}`;
    }

    const span = scaleMax - scaleMin > 0 ? scaleMax - scaleMin : DEFAULT_SCALE_MAX - DEFAULT_SCALE_MIN;
    const pct = Math.max(0, Math.min(100, ((target - scaleMin) / span) * 100));
    if (barFillEl) barFillEl.style.width = `${pct}%`;

    const minLbl = document.getElementById("wiz-scale-min-label");
    const midLbl = document.getElementById("wiz-scale-mid-label");
    const maxLbl = document.getElementById("wiz-scale-max-label");
    if (minLbl) minLbl.textContent = scaleMin;
    if (midLbl) midLbl.textContent = scaleMid;
    if (maxLbl) maxLbl.textContent = scaleMax;
}

// Renderiza la tabla editable de acciones del Paso 4
function renderWizardTasksTable() {
    const tbody = document.getElementById("wiz-tasks-tbody");
    if (!tbody) return;

    const responsibles = state.filterOptions.responsibles || [];
    const statuses = state.filterOptions.task_statuses || [];

    tbody.innerHTML = state.wizard.tasks
        .map((task, idx) => {
            const respOptions = responsibles
                .map(
                    (r) =>
                        `<option value="${escapeHtml(r.id)}" ${
                            r.id === task.apt_responsible ? "selected" : ""
                        }>${escapeHtml(r.label)}</option>`
                )
                .join("");

            const statusOptions = statuses
                .map(
                    (st) =>
                        `<option value="${escapeHtml(st)}" ${
                            st === task.apt_status ? "selected" : ""
                        }>${escapeHtml(st)}</option>`
                )
                .join("");

            return `
                <tr data-task-index="${idx}">
                    <td>
                        <input
                            type="text"
                            class="ap-input-box ap-task-input-title"
                            data-idx="${idx}"
                            placeholder="Nombre de la acción"
                            value="${escapeHtml(task.apt_title)}">
                    </td>
                    <td>
                        <select class="ap-select-box ap-task-select-resp" data-idx="${idx}">
                            <option value="">Seleccionar...</option>
                            ${respOptions}
                        </select>
                    </td>
                    <td>
                        <input
                            type="date"
                            class="ap-input-box ap-task-input-date"
                            data-idx="${idx}"
                            value="${escapeHtml(task.apt_due_date)}">
                    </td>
                    <td>
                        <select class="ap-select-box ap-task-select-status" data-idx="${idx}">
                            ${statusOptions}
                        </select>
                    </td>
                    <td class="text-center">
                        <button
                            type="button"
                            class="ap-btn-icon-trash"
                            data-remove-idx="${idx}"
                            title="Eliminar acción"
                            aria-label="Eliminar acción">
                            <i class="fa fa-trash-o" aria-hidden="true"></i>
                        </button>
                    </td>
                </tr>
            `;
        })
        .join("");
}

// Resuelve el dt_title de la Dimensión seleccionada para el Paso 5 (Resumen)
function resolveSummaryDimensionLabel(w) {
    if (!w.ap_dimension) return "-";
    const fromDimCatalog = findLabelById(w.scopeCatalog.dimensions || [], w.ap_dimension);
    if (fromDimCatalog && fromDimCatalog !== "-" && fromDimCatalog !== w.ap_dimension) {
        return fromDimCatalog;
    }
    const allQuestions = w.scopeCatalog.allQuestions || w.scopeCatalog.questions || [];
    const qWithDim = allQuestions.find((q) => q.dimension === w.ap_dimension && q.dimension_label);
    if (qWithDim && qWithDim.dimension_label) {
        return qWithDim.dimension_label;
    }
    if (w.ap_dimension_label && w.ap_dimension_label !== w.ap_dimension) {
        return w.ap_dimension_label;
    }
    return fromDimCatalog || w.ap_dimension;
}

// Resuelve el dt_title del Tema seleccionado o inferido para el Paso 5 (Resumen), evitando mostrar el name
function resolveSummaryTopicLabel(w) {
    const allQuestions = w.scopeCatalog.allQuestions || w.scopeCatalog.questions || [];
    const selectedQuestion = allQuestions.find((q) => q.id === w.ap_question) || null;
    const topicId =
        w.ap_topic ||
        (w.ap_scope_type === "Pregunta" && selectedQuestion ? selectedQuestion.topic : "");

    if (!topicId) {
        return "No aplica / Sin tema";
    }

    const fromAllTopics = findLabelById(w.scopeCatalog.allTopics || [], topicId);
    if (fromAllTopics && fromAllTopics !== "-" && fromAllTopics !== topicId) {
        return fromAllTopics;
    }

    const fromTopics = findLabelById(w.scopeCatalog.topics || [], topicId);
    if (fromTopics && fromTopics !== "-" && fromTopics !== topicId) {
        return fromTopics;
    }

    if (selectedQuestion && selectedQuestion.topic === topicId && selectedQuestion.topic_label) {
        return selectedQuestion.topic_label;
    }

    const anyQuestionWithTopic = allQuestions.find((q) => q.topic === topicId && q.topic_label);
    if (anyQuestionWithTopic && anyQuestionWithTopic.topic_label) {
        return anyQuestionWithTopic.topic_label;
    }

    if (w.ap_topic_label && w.ap_topic_label !== topicId) {
        return w.ap_topic_label;
    }

    return fromAllTopics || fromTopics || topicId;
}

// Resuelve el qn_statement de la Pregunta seleccionada para el Paso 5 (Resumen)
function resolveSummaryQuestionLabel(w) {
    if (!w.ap_question) return "-";
    const allQuestions = w.scopeCatalog.allQuestions || w.scopeCatalog.questions || [];
    const fromAll = findLabelById(allQuestions, w.ap_question);
    if (fromAll && fromAll !== "-" && fromAll !== w.ap_question) {
        return fromAll;
    }
    if (w.ap_question_label && w.ap_question_label !== w.ap_question) {
        return w.ap_question_label;
    }
    return fromAll || w.ap_question;
}

// Rellena las 4 tarjetas de resumen en el Paso 5
function renderWizardSummary() {
    const w = state.wizard;
    const opts = state.filterOptions;

    const setTxt = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val || "-";
    };

    setTxt("sum-name", w.ap_name);
    setTxt("sum-objective", w.ap_objective);
    setTxt("sum-description", w.ap_description || "-");
    setTxt("sum-category", findLabelById(opts.categories, w.ap_category));
    setTxt("sum-priority", w.ap_priority);
    setTxt("sum-responsible", findLabelById(opts.responsibles, w.ap_responsible));
    setTxt("sum-dates", `${w.ap_start_date || "-"} → ${w.ap_target_date || "-"}`);

    setTxt("sum-survey", findLabelById(opts.surveys, w.ap_origin_survey));
    setTxt("sum-scope-type", w.ap_scope_type);
    setTxt("sum-dimension", resolveSummaryDimensionLabel(w));
    setTxt("sum-topic", resolveSummaryTopicLabel(w));
    setTxt("sum-question", resolveSummaryQuestionLabel(w));

    const showDim = ["Dimensión", "Tema", "Pregunta"].includes(w.ap_scope_type);
    const showTopic = ["Tema", "Pregunta"].includes(w.ap_scope_type);
    const showQuestion = w.ap_scope_type === "Pregunta";

    document.getElementById("sum-row-dimension")?.classList.toggle("d-none", !showDim);
    document.getElementById("sum-row-topic")?.classList.toggle("d-none", !showTopic);
    document.getElementById("sum-row-question")?.classList.toggle("d-none", !showQuestion);

    const diff = Number((Number(w.ap_target_score || 0) - Number(w.ap_initial_score || 0)).toFixed(2));
    setTxt("sum-initial-score", formatScoreValue(w.ap_initial_score));
    setTxt("sum-target-score", formatScoreValue(w.ap_target_score));
    setTxt("sum-increment-score", diff >= 0 ? `+${diff.toFixed(2)}` : `${diff.toFixed(2)}`);

    const tasksHeading = document.getElementById("sum-tasks-heading");
    const tasksListEl = document.getElementById("sum-tasks-list");
    const validTasks = w.tasks.filter((t) => (t.apt_title || "").trim() !== "");

    if (tasksHeading) {
        tasksHeading.textContent = `ACCIONES (${validTasks.length})`;
    }

    if (tasksListEl) {
        if (validTasks.length === 0) {
            tasksListEl.innerHTML = `<p class="text-muted small mb-0">Sin acciones registradas.</p>`;
        } else {
            tasksListEl.innerHTML = validTasks
                .map((t) => {
                    const title = escapeHtml((t.apt_title || "").trim());
                    const resp = escapeHtml(findLabelById(opts.responsibles, t.apt_responsible));
                    const due = escapeHtml(t.apt_due_date || "Sin fecha");
                    const st = escapeHtml(t.apt_status || "Pendiente");
                    return `
                        <div class="ap-summary-task-item">
                            <div>
                                <div class="ap-summary-task-name">${title}</div>
                                <div class="ap-summary-task-meta">${resp} · ${due}</div>
                            </div>
                            <span class="ap-pill-goal ap-pill-goal--pending">${st}</span>
                        </div>
                    `;
                })
                .join("");
        }
    }
}

// Guarda en state.wizard los valores de los inputs del paso actual
function captureCurrentStepInputs() {
    const w = state.wizard;
    const getVal = (id) => (document.getElementById(id)?.value || "").trim();

    if (w.step === 1) {
        w.ap_name = getVal("wiz-name");
        w.ap_category = getVal("wiz-category");
        w.ap_objective = getVal("wiz-objective");
        w.ap_description = getVal("wiz-description");
        w.ap_priority = getVal("wiz-priority");
        w.ap_responsible = getVal("wiz-responsible");
        w.ap_start_date = getVal("wiz-start-date");
        w.ap_target_date = getVal("wiz-target-date");
    } else if (w.step === 2) {
        w.ap_origin_survey = getVal("wiz-survey");
        w.ap_scope_type = getVal("wiz-scope-type") || "Medición";
        w.ap_dimension = getVal("wiz-dimension");
        w.ap_topic = getVal("wiz-topic");
        w.ap_question = getVal("wiz-question");

        if (w.ap_dimension) {
            w.ap_dimension_label = resolveSummaryDimensionLabel(w);
        }
        if (w.ap_topic) {
            w.ap_topic_label = resolveSummaryTopicLabel(w);
        }

        if (w.ap_scope_type === "Pregunta" && w.ap_question) {
            const allQuestions = w.scopeCatalog.allQuestions || w.scopeCatalog.questions || [];
            const qObj = allQuestions.find((q) => q.id === w.ap_question);
            if (qObj) {
                w.ap_question_label = qObj.label || w.ap_question;
                if (!w.ap_topic && qObj.topic) {
                    w.ap_topic = qObj.topic;
                    w.ap_topic_label =
                        qObj.topic_label ||
                        findLabelById(w.scopeCatalog.allTopics || [], qObj.topic);
                }
                if (!w.ap_dimension && qObj.dimension) {
                    w.ap_dimension = qObj.dimension;
                    w.ap_dimension_label =
                        qObj.dimension_label ||
                        findLabelById(w.scopeCatalog.dimensions || [], qObj.dimension);
                }
            }
        }
    } else if (w.step === 3) {
        w.ap_target_score = Number(document.getElementById("wiz-target-score")?.value || 0);
    }
}

/**
 * Valida los campos obligatorios de cada paso del Wizard incluyendo:
 * - Sección 6: Tema solo obligatorio cuando el alcance es Tema.
 * - Punto 3 (Sección 8 y HU-04): Validación completa de acciones y advertencia si fecha compromiso < fecha inicio.
 */
function validateWizardStep(step) {
    captureCurrentStepInputs();
    const w = state.wizard;

    if (step === 1) {
        if (!w.ap_name) {
            showNotification("Ingresa el nombre del plan.", "error");
            return false;
        }
        if (!w.ap_category) {
            showNotification("Selecciona una categoría para el plan.", "error");
            return false;
        }
        if (!w.ap_objective) {
            showNotification("Ingresa el objetivo del plan.", "error");
            return false;
        }
        if (!w.ap_responsible) {
            showNotification("Selecciona un responsable para el plan.", "error");
            return false;
        }
        if (!w.ap_start_date || !w.ap_target_date) {
            showNotification("Ingresa las fechas de inicio y objetivo.", "error");
            return false;
        }
    } else if (step === 2) {
        if (!w.ap_origin_survey) {
            showNotification("Selecciona la medición de origen.", "error");
            return false;
        }
        if (["Dimensión", "Tema", "Pregunta"].includes(w.ap_scope_type) && !w.ap_dimension) {
            showNotification("Selecciona una dimensión.", "error");
            return false;
        }
        if (w.ap_scope_type === "Tema" && !w.ap_topic) {
            showNotification("Selecciona un tema.", "error");
            return false;
        }
        if (w.ap_scope_type === "Pregunta" && !w.ap_question) {
            showNotification("Selecciona una pregunta.", "error");
            return false;
        }
    } else if (step === 3) {
        const min = Number(w.ap_scale_min ?? DEFAULT_SCALE_MIN);
        const max = Number(w.ap_scale_max ?? DEFAULT_SCALE_MAX);
        if (Number.isNaN(w.ap_target_score) || w.ap_target_score < min || w.ap_target_score > max) {
            showNotification(`El puntaje objetivo debe estar entre ${min} y ${max}.`, "error");
            return false;
        }
    } else if (step === 4) {
        for (let i = 0; i < w.tasks.length; i += 1) {
            const t = w.tasks[i];
            const title = (t.apt_title || "").trim();
            const resp = (t.apt_responsible || "").trim();
            const due = (t.apt_due_date || "").trim();
            const st = (t.apt_status || "").trim();

            if (!title || !resp || !due || !st) {
                showNotification(
                    `Completa nombre, responsable, fecha compromiso y estado en la acción #${i + 1} (o elimina la fila si no la necesitas).`,
                    "error"
                );
                return false;
            }

            if (w.ap_start_date && due < w.ap_start_date) {
                const proceed = window.confirm(
                    `Advertencia: La fecha compromiso de la acción "${title}" (${due}) es anterior a la fecha de inicio del plan (${w.ap_start_date}). ¿Deseas continuar de todos modos?`
                );
                if (!proceed) return false;
            }
        }
    }
    return true;
}

// Activa un paso del Wizard actualizando los nodos del stepper y botones inferiores
function setWizardStep(stepNumber) {
    state.wizard.step = stepNumber;

    document.querySelectorAll(".ap-step-node").forEach((node) => {
        const s = Number(node.dataset.stepIndicator);
        const circle = node.querySelector(".ap-step-circle");
        node.classList.remove("active", "completed");

        if (s < stepNumber) {
            node.classList.add("completed");
            if (circle) circle.innerHTML = `<i class="fa fa-check" aria-hidden="true"></i>`;
        } else if (s === stepNumber) {
            node.classList.add("active");
            if (circle) circle.innerHTML = `<span class="ap-step-num">${s}</span>`;
        } else {
            if (circle) circle.innerHTML = `<span class="ap-step-num">${s}</span>`;
        }
    });

    document.querySelectorAll(".ap-wizard-pane").forEach((pane) => {
        const p = Number(pane.dataset.stepPane);
        pane.classList.toggle("d-none", p !== stepNumber);
    });

    if (stepNumber === 3) renderWizardGoalPreview();
    else if (stepNumber === 4) renderWizardTasksTable();
    else if (stepNumber === 5) renderWizardSummary();

    const prevBtn = document.getElementById("btn-wizard-prev");
    const nextBtn = document.getElementById("btn-wizard-next");
    const submitBtn = document.getElementById("btn-wizard-submit");

    if (prevBtn) prevBtn.disabled = stepNumber === 1;
    if (nextBtn) nextBtn.classList.toggle("d-none", stepNumber === 5);
    if (submitBtn) submitBtn.classList.toggle("d-none", stepNumber !== 5);
}

// Envía el formulario completo del Wizard al backend creando el plan en estado Borrador (Punto 1 / HU-01)
async function submitWizardPlan() {
    captureCurrentStepInputs();
    const w = state.wizard;

    const validTasks = w.tasks.filter((t) => (t.apt_title || "").trim() !== "");
    const payload = {
        name: w.isEdit ? w.planId : "",
        ap_name: w.ap_name,
        ap_category: resolveCategoryValue(w.ap_category),
        ap_priority: w.ap_priority,
        ap_responsible: w.ap_responsible,
        ap_start_date: w.ap_start_date,
        ap_target_date: w.ap_target_date,
        ap_objective: w.ap_objective,
        ap_description: w.ap_description,
        ap_origin_survey: w.ap_origin_survey,
        ap_scope_type: w.ap_scope_type,
        ap_dimension: w.ap_dimension,
        ap_topic: w.ap_topic,
        ap_question: w.ap_question,
        ap_scope_label: w.ap_scope_label,
        ap_initial_score: w.ap_initial_score,
        ap_target_score: w.ap_target_score,
        ap_scale_min: w.ap_scale_min,
        ap_scale_max: w.ap_scale_max,
        ap_status: w.isEdit ? w.ap_status || "Borrador" : "Borrador",
        tasks: validTasks,
    };

    try {
        const res = await callBackend("save_action_plan", { payload }, "POST");
        if (res && res.dashboard) {
            state.kpis = { ...state.kpis, ...res.dashboard.kpis };
            state.items = res.dashboard.items || [];
            renderKpis();
            renderPlansTable();
        } else {
            await fetchDashboardData();
        }
        showNotification(
            w.isEdit ? "Plan actualizado correctamente." : "Plan de mejora creado en estado Borrador.",
            "success"
        );
        switchView("dashboard");
    } catch (err) {
        console.error("[iq_action_plan] Error al guardar el plan:", err);
        showNotification("Error al guardar el plan. Verifica los campos obligatorios.", "error");
    }
}

// Consulta y abre la vista de detalle de un plan específico
async function openPlanDetail(planName) {
    if (!planName) return;
    try {
        const res = await callBackend("get_action_plan_detail", { name: planName }, "GET");
        if (res && res.plan) {
            state.currentDetail = res;
            renderPlanDetailView(res.plan, res.compatible_surveys || []);
            switchView("detail");
        }
    } catch (err) {
        console.error("[iq_action_plan] Error abriendo detalle:", err);
        showNotification("No fue posible cargar el detalle del plan.", "error");
    }
}

// Renderiza los datos, tareas y métricas completas de evaluación de impacto en Detalle (Punto 4 / Sección 9 y 12)
function renderPlanDetailView(plan, compatibleSurveys) {
    const setTxt = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val ?? "-";
    };

    setTxt("detail-breadcrumb-current", plan.ap_name || plan.name);
    setTxt("det-plan-name", plan.ap_name || plan.name);
    setTxt(
        "det-plan-subtitle",
        `${plan.origin_survey_name || "-"} · Responsable: ${plan.responsible_name || "-"}`
    );

    const statusBadge = document.getElementById("det-status-badge");
    if (statusBadge) {
        statusBadge.className = `ap-pill-status ${getStatusPillClass(plan.ap_status)}`;
        statusBadge.innerHTML = `<span class="ap-status-dot"></span>${escapeHtml(plan.ap_status)}`;
    }

    const prioBadge = document.getElementById("det-priority-badge");
    if (prioBadge) {
        prioBadge.className = `ap-pill-priority ${getPriorityPillClass(plan.ap_priority)}`;
        prioBadge.textContent = `Prioridad ${plan.ap_priority}`;
    }

    const catBadge = document.getElementById("det-category-badge");
    if (catBadge) {
        catBadge.className = "ap-pill-category";
        catBadge.textContent =
            plan.category_name ||
            findLabelById(state.filterOptions.categories, plan.ap_category) ||
            plan.ap_category ||
            "-";
    }

    const statusSelect = document.getElementById("det-change-status");
    if (statusSelect) statusSelect.value = plan.ap_status;

    setTxt("det-objective", plan.ap_objective);
    setTxt("det-description", plan.ap_description || "-");
    setTxt("det-survey", plan.origin_survey_name);
    setTxt("det-scope", `${plan.ap_scope_type}: ${plan.ap_scope_label || "-"}`);
    setTxt("det-responsible", plan.responsible_name);
    setTxt("det-dates", `${plan.ap_start_date_formatted} → ${plan.ap_target_date_formatted}`);

    const goalBadge = document.getElementById("det-goal-badge");
    if (goalBadge) {
        goalBadge.className = `ap-pill-goal ${getGoalPillClass(plan.ap_goal_status)}`;
        goalBadge.textContent = plan.ap_goal_status;
    }

    setTxt("det-initial-score", formatScoreValue(plan.ap_initial_score));
    setTxt("det-target-score", formatScoreValue(plan.ap_target_score));
    setTxt(
        "det-posterior-score",
        plan.ap_posterior_score !== null && plan.ap_posterior_score !== undefined
            ? formatScoreValue(plan.ap_posterior_score)
            : "-"
    );

    const varScore = plan.ap_observed_variation;
    setTxt(
        "det-variation-score",
        varScore !== null && varScore !== undefined
            ? varScore >= 0
                ? `+${Number(varScore).toFixed(2)}`
                : `${Number(varScore).toFixed(2)}`
            : "-"
    );

    const diffScore = plan.ap_goal_difference;
    setTxt(
        "det-goal-diff-score",
        diffScore !== null && diffScore !== undefined
            ? diffScore >= 0
                ? `+${Number(diffScore).toFixed(2)}`
                : `${Number(diffScore).toFixed(2)}`
            : "-"
    );

    const rawAchPct = plan.ap_goal_achievement_pct;
    const visualAchPct =
        rawAchPct !== null && rawAchPct !== undefined
            ? Math.max(0, Math.min(100, Math.round(Number(rawAchPct))))
            : 0;
    setTxt(
        "det-goal-achievement-pct",
        rawAchPct !== null && rawAchPct !== undefined ? `${Number(rawAchPct).toFixed(1)}%` : "Sin evaluar"
    );
    const achBar = document.getElementById("det-goal-achievement-bar");
    if (achBar) achBar.style.width = `${visualAchPct}%`;

    const hasCompatible = Array.isArray(compatibleSurveys) && compatibleSurveys.length > 0;
    populateSelect(
        "det-comparison-survey",
        compatibleSurveys,
        hasCompatible
            ? "Seleccionar medición compatible..."
            : "Sin mediciones compatibles disponibles"
    );
    const compSelect = document.getElementById("det-comparison-survey");
    const evalBtn = document.getElementById("btn-evaluate-impact");
    const noCompatibleMsg = document.getElementById("det-no-compatible-msg");

    if (compSelect) {
        compSelect.disabled = !hasCompatible;
        if (plan.ap_comparison_survey && hasCompatible) {
            compSelect.value = plan.ap_comparison_survey;
        }
    }
    if (evalBtn) evalBtn.disabled = !hasCompatible;
    if (noCompatibleMsg) noCompatibleMsg.classList.toggle("d-none", hasCompatible);

    const pct = Math.round(Number(plan.ap_progress_pct || 0));
    setTxt(
        "det-tasks-summary-text",
        `${plan.ap_completed_tasks || 0} de ${plan.ap_total_tasks || 0} acciones finalizadas (${
            plan.ap_overdue_tasks || 0
        } vencidas)`
    );
    setTxt("det-tasks-progress-pct", `${pct}%`);
    const bar = document.getElementById("det-tasks-progress-bar");
    if (bar) bar.style.width = `${pct}%`;

    const isClosed = ["Finalizado", "Cancelado"].includes(plan.ap_status);
    const tbody = document.getElementById("det-tasks-tbody");
    if (tbody) {
        const tasks = plan.tasks || [];
        if (tasks.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">Este plan aún no tiene acciones registradas.</td></tr>`;
        } else {
            tbody.innerHTML = tasks
                .map((t) => {
                    const statusOpts = (state.filterOptions.task_statuses || [])
                        .map((st) => {
                            const stVal = getOptionId(st);
                            const stLbl = typeof st === "object" ? st.label || st.id : st;
                            return `<option value="${escapeHtml(stVal)}" ${
                                stVal === t.apt_status ? "selected" : ""
                            }>${escapeHtml(stLbl)}</option>`;
                        })
                        .join("");
                    return `
                        <tr>
                            <td class="ap-cell-plan">
                                <div class="ap-plan-primary">${escapeHtml(t.apt_title)}</div>
                            </td>
                            <td class="ap-cell-text">${escapeHtml(t.responsible_name)}</td>
                            <td class="ap-cell-date">${escapeHtml(t.apt_due_date_formatted)}</td>
                            <td>
                                <select
                                    class="ap-select-box ap-detail-task-status"
                                    data-task-name="${escapeHtml(t.name)}"
                                    ${isClosed ? "disabled" : ""}>
                                    ${statusOpts}
                                </select>
                            </td>
                        </tr>
                    `;
                })
                .join("");
        }
    }
}

// Registra todos los listeners de eventos de las 3 vistas
function bindEvents() {
    const searchInput = document.getElementById("ap-filter-search");
    const clearSearchBtn = document.getElementById("ap-search-clear");
    const debouncedSearch = debounce((val) => {
        state.filters.search = val.trim();
        fetchDashboardData();
    }, DEBOUNCE_DELAY_MS);

    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            const val = e.target.value || "";
            if (clearSearchBtn) clearSearchBtn.classList.toggle("d-none", val.length === 0);
            debouncedSearch(val);
        });
    }

    if (clearSearchBtn && searchInput) {
        clearSearchBtn.addEventListener("click", () => {
            searchInput.value = "";
            clearSearchBtn.classList.add("d-none");
            state.filters.search = "";
            fetchDashboardData();
        });
    }

    const filterMap = {
        "ap-filter-status": "status",
        "ap-filter-goal-status": "goal_status",
        "ap-filter-responsible": "responsible",
        "ap-filter-category": "category",
        "ap-filter-priority": "priority",
        "ap-filter-survey": "origin_survey",
        "ap-filter-year": "year",
    };

    Object.entries(filterMap).forEach(([id, key]) => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("change", (e) => {
                state.filters[key] = e.target.value || "";
                fetchDashboardData();
            });
        }
    });

    document.querySelectorAll(".ap-kpi-card[data-kpi-filter]").forEach((card) => {
        card.addEventListener("click", () => {
            const key = card.dataset.kpiFilter;
            const val = card.dataset.kpiValue;
            const nextVal = state.filters[key] === val ? "" : val;
            state.filters[key] = nextVal;

            if (key === "status") {
                const sEl = document.getElementById("ap-filter-status");
                if (sEl) sEl.value = nextVal;
            } else if (key === "goal_status") {
                const gEl = document.getElementById("ap-filter-goal-status");
                if (gEl) gEl.value = nextVal;
            }
            fetchDashboardData();
        });
    });

    document.getElementById("btn-reset-filters")?.addEventListener("click", resetAllFilters);
    document.getElementById("btn-empty-clear-filters")?.addEventListener("click", resetAllFilters);
    document.getElementById("btn-new-action-plan")?.addEventListener("click", openWizardForCreate);
    document.getElementById("btn-empty-new-plan")?.addEventListener("click", openWizardForCreate);

    const tbody = document.getElementById("ap-table-body");
    if (tbody) {
        tbody.addEventListener("click", (e) => {
            const row = e.target.closest(".ap-table-row");
            if (row && row.dataset.planName) openPlanDetail(row.dataset.planName);
        });
    }

    document.getElementById("btn-wizard-cancel")?.addEventListener("click", () => switchView("dashboard"));
    document.getElementById("wizard-breadcrumb-back")?.addEventListener("click", (e) => {
        e.preventDefault();
        switchView("dashboard");
    });

    document.getElementById("btn-wizard-prev")?.addEventListener("click", () => {
        captureCurrentStepInputs();
        if (state.wizard.step > 1) setWizardStep(state.wizard.step - 1);
    });

    // Punto 6 (Sección 6 y 12): Bloquear avance al Paso 3 si no existe puntaje disponible para el alcance elegido
    document.getElementById("btn-wizard-next")?.addEventListener("click", async () => {
        if (!validateWizardStep(state.wizard.step)) return;
        if (state.wizard.step === 2) {
            await refreshWizardInitialScore();
            if (!state.wizard.has_valid_score) {
                showNotification(state.wizard.score_error_message || NO_SCORE_MESSAGE, "error");
                return;
            }
        }
        if (state.wizard.step < 5) setWizardStep(state.wizard.step + 1);
    });

    document.getElementById("btn-wizard-submit")?.addEventListener("click", submitWizardPlan);

    // Sección 6: Al cambiar la medición se reinician Dimensión, Tema y Pregunta y se cargan los atados a esa medición
    document.getElementById("wiz-survey")?.addEventListener("change", (e) => {
        const w = state.wizard;
        w.ap_origin_survey = e.target.value || "";
        w.ap_dimension = "";
        w.ap_dimension_label = "";
        w.ap_topic = "";
        w.ap_topic_label = "";
        w.ap_question = "";
        w.ap_question_label = "";
        loadScopeCatalogForSurvey(w.ap_origin_survey);
    });

    // Sección 6: Al cambiar tipo de alcance se reinician los selectores dependientes
    document.getElementById("wiz-scope-type")?.addEventListener("change", (e) => {
        const w = state.wizard;
        w.ap_scope_type = e.target.value || "Medición";
        w.ap_dimension = "";
        w.ap_dimension_label = "";
        w.ap_topic = "";
        w.ap_topic_label = "";
        w.ap_question = "";
        w.ap_question_label = "";

        const dimEl = document.getElementById("wiz-dimension");
        if (dimEl) dimEl.value = "";

        filterAndRenderTopicsSelect();
        filterAndRenderQuestionsSelect();
        updateScopeSelectorsVisibility();
        if (w.ap_scope_type === "Pregunta") {
            reloadFilteredQuestionsFromBackend();
        }
        refreshWizardInitialScore();
    });

    // Sección 6: Al cambiar Dimensión se reinician Tema y Pregunta y se filtran por la dimensión elegida
    document.getElementById("wiz-dimension")?.addEventListener("change", async (e) => {
        const w = state.wizard;
        w.ap_dimension = e.target.value || "";
        w.ap_dimension_label = w.ap_dimension
            ? findLabelById(w.scopeCatalog.dimensions || [], w.ap_dimension)
            : "";
        w.ap_topic = "";
        w.ap_topic_label = "";
        w.ap_question = "";
        w.ap_question_label = "";

        filterAndRenderTopicsSelect();
        filterAndRenderQuestionsSelect();

        if (w.ap_scope_type === "Pregunta") {
            await reloadFilteredQuestionsFromBackend();
        }
        refreshWizardInitialScore();
    });

    // Sección 6: Al cambiar Tema se reinicia Pregunta y se actualiza su etiqueta dt_title
    document.getElementById("wiz-topic")?.addEventListener("change", async (e) => {
        const w = state.wizard;
        w.ap_topic = e.target.value || "";
        w.ap_topic_label = w.ap_topic
            ? findLabelById(w.scopeCatalog.allTopics || w.scopeCatalog.topics || [], w.ap_topic)
            : "";
        w.ap_question = "";
        w.ap_question_label = "";

        filterAndRenderQuestionsSelect();

        if (w.ap_scope_type === "Pregunta") {
            await reloadFilteredQuestionsFromBackend();
        }
        refreshWizardInitialScore();
    });

    // Al seleccionar una pregunta se sincroniza su tema (dt_title) cuando aplica
    document.getElementById("wiz-question")?.addEventListener("change", (e) => {
        const w = state.wizard;
        w.ap_question = e.target.value || "";
        const allQuestions = w.scopeCatalog.allQuestions || w.scopeCatalog.questions || [];
        const qObj = allQuestions.find((q) => q.id === w.ap_question);
        if (qObj) {
            w.ap_question_label = qObj.label || w.ap_question;
            if (!w.ap_topic && qObj.topic) {
                w.ap_topic = qObj.topic;
                w.ap_topic_label =
                    qObj.topic_label ||
                    findLabelById(w.scopeCatalog.allTopics || [], qObj.topic);
            } else if (w.ap_topic && qObj.topic_label) {
                w.ap_topic_label = qObj.topic_label;
            }
            if (!w.ap_dimension && qObj.dimension) {
                w.ap_dimension = qObj.dimension;
                w.ap_dimension_label =
                    qObj.dimension_label ||
                    findLabelById(w.scopeCatalog.dimensions || [], qObj.dimension);
            }
        } else {
            w.ap_question_label = "";
        }
        refreshWizardInitialScore();
    });

    document.getElementById("wiz-target-score")?.addEventListener("input", (e) => {
        state.wizard.ap_target_score = Number(e.target.value || 0);
        renderWizardGoalPreview();
    });

    document.getElementById("btn-add-task-row")?.addEventListener("click", () => {
        state.wizard.tasks.push({
            apt_title: "",
            apt_responsible: state.wizard.ap_responsible || "",
            apt_due_date: state.wizard.ap_target_date || getTodayIso(),
            apt_status: getOptionId((state.filterOptions.task_statuses || [])[0]) || "Pendiente",
        });
        renderWizardTasksTable();
    });

    const wizTasksTbody = document.getElementById("wiz-tasks-tbody");
    if (wizTasksTbody) {
        wizTasksTbody.addEventListener("input", (e) => {
            const idx = Number(e.target.dataset.idx);
            if (Number.isNaN(idx) || !state.wizard.tasks[idx]) return;
            if (e.target.classList.contains("ap-task-input-title")) {
                state.wizard.tasks[idx].apt_title = e.target.value;
            } else if (e.target.classList.contains("ap-task-input-date")) {
                state.wizard.tasks[idx].apt_due_date = e.target.value;
            }
        });

        wizTasksTbody.addEventListener("change", (e) => {
            const idx = Number(e.target.dataset.idx);
            if (Number.isNaN(idx) || !state.wizard.tasks[idx]) return;
            if (e.target.classList.contains("ap-task-select-resp")) {
                state.wizard.tasks[idx].apt_responsible = e.target.value;
            } else if (e.target.classList.contains("ap-task-select-status")) {
                state.wizard.tasks[idx].apt_status = e.target.value;
            }
        });

        // Punto 5: Confirmar antes de eliminar una fila de acción con datos
        wizTasksTbody.addEventListener("click", (e) => {
            const btn = e.target.closest("[data-remove-idx]");
            if (!btn) return;
            const idx = Number(btn.dataset.removeIdx);
            const rowTask = state.wizard.tasks[idx];
            if (rowTask && (rowTask.apt_title || "").trim() !== "") {
                const confirmed = window.confirm("¿Deseas eliminar esta acción del plan?");
                if (!confirmed) return;
            }
            state.wizard.tasks.splice(idx, 1);
            renderWizardTasksTable();
        });
    }

    document.getElementById("detail-breadcrumb-back")?.addEventListener("click", (e) => {
        e.preventDefault();
        fetchDashboardData();
        switchView("dashboard");
    });

    document.getElementById("btn-detail-edit")?.addEventListener("click", () => {
        if (state.currentDetail && state.currentDetail.plan) {
            openWizardForEdit(state.currentDetail.plan);
        }
    });

    // Punto 5 (Sección 12): Confirmar antes de cancelar un plan
    document.getElementById("det-change-status")?.addEventListener("change", async (e) => {
        const plan = state.currentDetail?.plan;
        if (!plan) return;
        const nextStatus = e.target.value;

        if (nextStatus === "Cancelado") {
            const confirmed = window.confirm(
                "¿Estás seguro de que deseas cancelar este plan de acción? Una vez cancelado, sus acciones quedarán bloqueadas para edición."
            );
            if (!confirmed) {
                e.target.value = plan.ap_status;
                return;
            }
        }

        try {
            const updated = await callBackend(
                "update_plan_status",
                { plan_name: plan.name, new_status: nextStatus },
                "POST"
            );
            if (updated && updated.plan) {
                state.currentDetail = updated;
                renderPlanDetailView(updated.plan, updated.compatible_surveys || []);
                showNotification("Estado del plan actualizado.", "success");
            }
        } catch (err) {
            e.target.value = plan.ap_status;
            showNotification("No fue posible cambiar el estado del plan.", "error");
        }
    });

    document.getElementById("det-tasks-tbody")?.addEventListener("change", async (e) => {
        if (!e.target.classList.contains("ap-detail-task-status")) return;
        const plan = state.currentDetail?.plan;
        const taskName = e.target.dataset.taskName;
        if (!plan || !taskName) return;
        try {
            const updated = await callBackend(
                "update_task_status",
                { plan_name: plan.name, task_name: taskName, new_status: e.target.value },
                "POST"
            );
            if (updated && updated.plan) {
                state.currentDetail = updated;
                renderPlanDetailView(updated.plan, updated.compatible_surveys || []);
                showNotification("Estado de la acción actualizado.", "success");
            }
        } catch (err) {
            showNotification("No se pudo actualizar la acción.", "error");
        }
    });

    document.getElementById("btn-evaluate-impact")?.addEventListener("click", async () => {
        const plan = state.currentDetail?.plan;
        const compSurvey = document.getElementById("det-comparison-survey")?.value;
        if (!plan || !compSurvey) {
            showNotification("Aún no hay una medición compatible disponible para evaluar la meta.", "error");
            return;
        }
        try {
            const updated = await callBackend(
                "evaluate_plan_impact",
                { plan_name: plan.name, comparison_survey: compSurvey },
                "POST"
            );
            if (updated && updated.plan) {
                state.currentDetail = updated;
                renderPlanDetailView(updated.plan, updated.compatible_surveys || []);
                showNotification("Evaluación de impacto completada.", "success");
            }
        } catch (err) {
            showNotification("No fue posible evaluar la meta con la medición seleccionada.", "error");
        }
    });
}

// Punto de entrada al cargar el DOM
function initActionPlanApp() {
    loadPreloadedContext();
    renderFilterCatalogs();
    renderKpis();
    renderPlansTable();
    bindEvents();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initActionPlanApp);
} else {
    initActionPlanApp();
}