WEB_FORM_CLIENT_SCRIPT = """
const urlParamsGlobal = new URLSearchParams(window.location.search);
const uqFlag = urlParamsGlobal.get("uq") === "true";

const buildRegisterUrl = function(token, msg) {
  let url = "/iq-register";
  if (token) {
    url += "?token=" + token;
  }
  if (uqFlag) {
    url += token ? "&uq=true" : "?uq=true";
  }
  if (msg) {
    const encodedMsg = encodeURIComponent(msg);
    url += (url.includes("?") ? "&" : "?") + "error_msg=" + encodedMsg;
  }
  return url;
};

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
  
  $('.web-form-actions button[type="submit"]').hide();

  // Validar si ya hay respuestas guardadas en localStorage
  const surveyCacheKey = "liseniq_survey_cache_" + frappe.web_form.title;
  const cachedResponses = localStorage.getItem(surveyCacheKey);

  // Validar si la encuesta ya fue respondida
  const urlParams = urlParamsGlobal;
  const token = urlParams.get("token");
  const dni = localStorage.getItem("liseniq_doc_id");
  const register_url = buildRegisterUrl(token);

  frappe.call({
      method: "liseniq.utils.api_survey.get_survey_is_anonymous",
      args: { survey_name: frappe.web_form.title }
  }).then(r => {
      const is_anonymous = r.message;

      if (!is_anonymous && !dni && !token) {
          frappe.msgprint({
              title: __("Acceso denegado"),
              indicator: "red",
              message: __("Debe identificarse para responder la encuesta. Será redirigido a la página de registro."),
          });
          setTimeout(() => {
              const register_url = "/iq-register" + (token ? "?token=" + token : "");
              window.location.href = register_url;
          }, 3000);
          return;
      }

      frappe
        .call({
          method: "liseniq.utils.api_survey.validate_survey_link",
          args: {
            survey_name: frappe.web_form.title,
            user: token || "Anonimo",
            token: token,
            dni: dni || null,
            uq: uqFlag
          },
        })
        .then((r) => {
          const res = r.message || {};
          if (res.redirect_register) {
              const reg_token = res.register_token || token;
              const register_url = buildRegisterUrl(reg_token, res.message);
              window.location.href = register_url;
              return;
          }
          if (res.require_dni && uqFlag) {
              window.location.href = buildRegisterUrl(token, res.message || __("Debe ingresar su DNI para continuar."));
              return;
          }
          if (res.allow === false) {
            show_completed_message(res.message || __("Esta encuesta ya fue completada. Gracias por tu participación."));
            // Limpiar cache si ya fue respondida
            localStorage.removeItem(surveyCacheKey);
            localStorage.removeItem("liseniq_doc_id");
            return;
          }
    
          $('.web-form-actions button[type="submit"]').show();
          load_survey(frappe.web_form.title, cachedResponses);
        });
  });
};

frappe.ready(function() {
  $('<style>.survey-completed { pointer-events: none; opacity: 0.7; }</style>').appendTo('head');
  
  const dni_field = frappe.web_form.fields_dict.custom_document_number;
  if (dni_field) {
    $(dni_field.input).on('blur', function() {
      validate_dni_on_input(this.value);
    });
  }

  // Eliminar dni y cache al cerrar navegador
  window.addEventListener("unload", function() {
    localStorage.removeItem("liseniq_doc_id");
    localStorage.removeItem("liseniq_survey_cache_" + frappe.web_form.title);
  });
});

const validate_dni_on_input = function(dni) {
    if (!dni) {
        return;
    }

    const token = urlParamsGlobal.get("token");
    const register_url = buildRegisterUrl(token);
    frappe.call({
        method: "liseniq.utils.api_survey.validate_survey_link",
        args: {
            survey_name: frappe.web_form.title,
            dni: dni,
            token: token || null,
            uq: uqFlag
        },
    }).then((r) => {
        const res = r.message || {};
        // Si el backend indica redirección al registro, hacerlo con el token público proporcionado
        if (res.redirect_register) {
            const reg_token = res.register_token || token;
            const register_url = buildRegisterUrl(reg_token, res.message || __("El DNI ingresado no se encuentra registrado como contacto."));
            window.location.href = register_url;
            return;
        }

        const dni_field = frappe.web_form.fields_dict.custom_document_number;
        const $submit_btn = $('.web-form-actions button[type="submit"]');

        $(dni_field.input).removeClass('is-invalid');
        $(dni_field.wrapper).find('.invalid-feedback').remove();

        if (res.allow === false) {
            const error_msg = res.message || __("Esta encuesta ya fue completada.");
            $(dni_field.input).addClass('is-invalid');
            $(dni_field.wrapper).append(`<div class="invalid-feedback">${error_msg}</div>`);
            $submit_btn.prop('disabled', true);
            // El DNI no es válido para esta encuesta; eliminarlo del storage
            localStorage.removeItem("liseniq_doc_id");
        } else if (res.valid_dni === false) {
            const error_msg = res.message || __("El DNI ingresado no se encuentra registrado como contacto.");
            $(dni_field.input).addClass('is-invalid');
            $(dni_field.wrapper).append(`<div class="invalid-feedback">${error_msg}</div>`);
            $submit_btn.prop('disabled', true);
            // El DNI no es válido; eliminarlo del storage
            localStorage.removeItem("liseniq_doc_id");
            if (uqFlag) {
                setTimeout(() => { window.location.href = buildRegisterUrl(token, error_msg); }, 1200);
            }
        } else {
            // DNI válido: persistirlo para futuras validaciones y envío
            localStorage.setItem("liseniq_doc_id", dni);
            $submit_btn.prop('disabled', false);
        }
    });
};

const show_completed_message = function (msg) {
  $(".web-form-container").toggle(false);
  const $wrap = $(".page_content");
  $wrap.empty();
  $('<div class="alert alert-info" role="alert"></div>')
    .text(msg || "Esta encuesta ya fue completada. Gracias por tu participación.")
    .appendTo($wrap);
};

const load_survey = function (survey_name, cachedResponses) {
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
      survey.locale = "es";
      survey.completedHtml = "<h4>" + __("Gracias por completar la encuesta.") + "</h4>";
      survey.applyTheme(frappe.theme_json);

      // Precargar respuestas si existen en cache
      if (cachedResponses) {
        try {
          survey.data = JSON.parse(cachedResponses);
        } catch (e) {}
      }

      survey.onValueChanged.add((sender, options) => {
        // Guardar respuestas en cache cada vez que cambie una respuesta
        localStorage.setItem(
          "liseniq_survey_cache_" + frappe.web_form.title,
          JSON.stringify(sender.data)
        );
      });

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
  
  const urlParams = urlParamsGlobal;
  const token = urlParams.get("token");
  const doc_id = localStorage.getItem("liseniq_doc_id");
  const register_url = buildRegisterUrl(token);

  frappe
    .call({
      method: "liseniq.utils.api_survey.validate_survey_link",
      args: {
        survey_name: frappe.web_form.title,
        user: token || "Anonimo",
        token: token,
        dni: doc_id || null,
        uq: uqFlag
      },
    })
    .then((r) => {
      const res = r.message || {};
      if (res.redirect_register) {
          const reg_token = res.register_token || token;
          window.location.href = buildRegisterUrl(reg_token, res.message);
          return;
      }
      if (res.require_dni && uqFlag) {
          window.location.href = buildRegisterUrl(token, res.message || __("Debe ingresar su DNI para continuar."));
          return;
      }
      if (res.allow === false) {
        show_completed_message(res.message || __("Esta encuesta ya fue completada. Gracias por tu participación."));
        window.saving = false;
        return;
      }

      const payload = Object.assign({}, data);
      if (token) {
        payload.__token = token;
      }

      let args = {
        doctype: frappe.web_form.doc_type,
        survey: frappe.web_form.title,
        response_json: JSON.stringify(payload),
        user: doc_id || token || "Anonimo"
      };
      // console.log(args);
      frappe.call({
        type: "POST",
        method: "frappe.website.doctype.web_form.web_form.accept",
        args: {
          web_form: frappe.web_form.name,
          data: args,
        },
        callback: (response) => {
          if (!response.exc) {
            // console.log(response.message);
            // Limpiar cache y dni solo cuando se ha guardado exitosamente en el servidor.
            localStorage.removeItem("liseniq_survey_cache_" + frappe.web_form.title);
            localStorage.removeItem("liseniq_doc_id");
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

/* Ocultar elementos innecesarios */
.navbar {
    display: none !important;
}

/* Ocultar título de la página */
.page-head {
    display: none !important;
}

/* Ajustar padding superior */
.web-form-container, .page-container {
    padding-top: 15px !important;
}

/* --- Estilos para Likert Visual (SurveyJS imagepicker) --- */
.sd-imagepicker, .sv-imagepicker {
    --iq-img-size: 32px;
}
/* Imagen en versiones nuevas (sd-*) */
.sd-imagepicker .sd-imagepicker__item img,
.sd-imagepicker .sd-imagepicker__image,
.sd-imagepicker .sd-imagepicker__image img {
    width: var(--iq-img-size) !important;
    height: var(--iq-img-size) !important;
    max-width: var(--iq-img-size) !important;
    max-height: var(--iq-img-size) !important;
    object-fit: contain;
    display: block;
    margin: 0 auto;
}
/* Imagen en versiones legacy (sv-*) */
.sv-imagepicker .sv_q_imgsel img,
.sv-imagepicker .sv_q_imgsel .sv_q_imgsel_image {
    width: var(--iq-img-size) !important;
    height: var(--iq-img-size) !important;
    max-width: var(--iq-img-size) !important;
    max-height: var(--iq-img-size) !important;
    object-fit: contain;
    display: block;
    margin: 0 auto;
}

/* Centrado de ícono y texto */
.sd-imagepicker .sd-imagepicker__item,
.sv-imagepicker .sv_q_imgsel_item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 6px;
    text-align: center;
}

/* Ajuste de tamaño y margen del texto */
.sd-imagepicker .sd-imagepicker__item .sd-imagepicker__item-text,
.sv-imagepicker .sv_q_imgsel_item span {
    font-size: 0.9rem;
    text-align: center;
    margin-top: 4px;
}

/* Centrar la etiqueta */
.sv-imagepicker .sv_q_imgsel_label {
    text-align: center !important;
}

/* Eliminar bordes y sombras */
.sv_qstn .sv_q_imgsel label>div {
    border: none !important;
    box-shadow: none !important;
}

.sd-imagepicker .sd-imagepicker__item {
    border: none !important;
    box-shadow: none !important;
}

/* Centrar opciones inline */
.sv_main .sv_p_root .sv_q .sv_q_checkbox_inline,
.sv_main .sv_p_root .sv_q .sv_q_radiogroup_inline,
.sv_main .sv_p_root .sv_q .sv_q_imagepicker_inline {
    text-align: center !important;
}

/* Estilos para selección */
.sv_qstn .sv_q_imgsel label > input:checked + div {
    background-color: #d1f0ea !important;
}

/* Estilos para selección nueva (sd-*) */
.sd-imagepicker .sd-imagepicker__item--selected,
.sd-imagepicker .sd-imagepicker__item--checked {
    background-color: #d1f0ea !important;
}
 /* Estilos para selección inline */
.sv_main .sv_p_root .sv_q .sv_q_checkbox_inline label > input:checked + span,
.sv_main .sv_p_root .sv_q .sv_q_radiogroup_inline label > input:checked + span {
    background-color: #d1f0ea !important;
}
"""
