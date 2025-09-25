WEB_FORM_CLIENT_SCRIPT = """
frappe.web_form.after_load = () => {
  $(".page-header-actions-block").hide();
  $(".page-header").hide();
  $(".web-form-container").hide();
  $(".web-form-footer").hide();
  
  $(".breadcrumb-container").hide();
  
  $(".frappe-control[data-fieldname='responses']").hide();
  $(".frappe-control[data-fieldname='response_json']").hide();
  $(".frappe-control[data-fieldname='user']").hide();
  $(".frappe-control[data-fieldname='survey']").hide();
  
  // Validación: si el link ya fue utilizado, mostrar mensaje y no cargar la encuesta
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get("token");

  if (!token) {
    show_completed_message(__("El enlace a la encuesta no es válido o ha expirado."));
    return;
  }

  frappe
    .call({
      method: "liseniq.utils.api_survey.validate_survey_link",
      args: {
        survey_name: frappe.web_form.title,
        user: token || "Anonimo",
        token: token,
      },
    })
    .then((r) => {
      const res = r.message || {};
      if (res.allow === false) {
        show_completed_message(res.message || __("Esta encuesta ya fue completada. Gracias por tu participación."));
        return;
      }
      load_survey(frappe.web_form.title);
    });
};

frappe.ready(function() {
  $('<style>.survey-completed { pointer-events: none; opacity: 0.7; }</style>').appendTo('head');
});

const show_completed_message = function (msg) {
  $(".web-form-container").toggle(false);
  const $wrap = $(".page_content");
  $wrap.empty();
  $('<div class="alert alert-info" role="alert"></div>')
    .text(msg || "Esta encuesta ya fue completada. Gracias por tu participación.")
    .appendTo($wrap);
};

const load_survey = function (survey_name) {
  $(".web-form-container").toggle(false);
  $('<div id="surveyElement"></div>').appendTo($(".page_content"));
  frappe
    .call({
      method: "liseniq.utils.api_survey.get_public_survey",
      args: {
        survey_name: frappe.web_form.title,
      },
    })
    .then((r) => {
      build_survey(r.message);
      const survey = new Survey.Model(frappe.survey_json);
      survey.applyTheme(frappe.theme_json);
      survey.onComplete.add((sender, options) => {
        submit_response(sender.getAllValues());
        
        $(".web-form-footer").hide();
        
        $("#surveyElement").addClass("survey-completed");
      });
      $("#surveyElement").Survey({ model: survey });
    });
};

const build_survey = function (data) {
  frappe.survey_json = JSON.parse(data.survey_json.replaceAll("\\n", ""));
  frappe.theme_json = data.theme_json
    ? JSON.parse(data.theme_json)
    : {
        themeName: "plain",
        colorPalette: "dark",
        isPanelless: true,
      };
};

const submit_response = function (data) {
  window.saving = true;
  frappe.form_dirty = false;
  
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get("token");

  // Validación antes de enviar: bloquear si ya fue respondida
  frappe
    .call({
      method: "liseniq.utils.api_survey.validate_survey_link",
      args: {
        survey_name: frappe.web_form.title,
        user: token || "Anonimo",
        token: token,
      },
    })
    .then((r) => {
      const res = r.message || {};
      if (res.allow === false) {
        show_completed_message(res.message || __("Esta encuesta ya fue completada. Gracias por tu participación."));
        window.saving = false;
        return;
      }

      // Adjuntar el token dentro del JSON de respuestas para que el backend lo procese
      const payload = Object.assign({}, data);
      if (token) {
        payload.__token = token;
      }

      let args = {
        doctype: frappe.web_form.doc_type,
        survey: frappe.web_form.title,
        response_json: JSON.stringify(payload)
      };
      console.log(args);
      frappe.call({
        type: "POST",
        method: "frappe.website.doctype.web_form.web_form.accept",
        args: {
          web_form: frappe.web_form.name,
          data: args,
        },
        callback: (response) => {
          if (!response.exc) {
            console.log(response.message);
          }
        },
        always: function () {
          window.saving = false;
        },
      });
    });
};
"""

WEB_FORM_CUSTOM_CSS = """
.navbar {
    display: none !important;
}

.page-head {
    display: none !important;
}

.web-form-container, .page-container {
    padding-top: 15px !important;
}
"""
