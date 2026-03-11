WEB_FORM_CLIENT_SCRIPT = """
let urlParamsGlobal = new URLSearchParams(window.location.search);
const uqFromUrl = urlParamsGlobal.get("uq") === "true";
const uqStored = sessionStorage.getItem("liseniq_uq_flag") === "true";
let uqFlag = uqFromUrl || uqStored;

// Variable global para almacenar el estado de anonimato
window.liseniq_is_anonymous_survey = false;
window.liseniq_is_leadership = false;

if (uqFlag && !uqFromUrl) {
  const loc = new URL(window.location.href);
  loc.searchParams.set("uq", "true");
  window.history.replaceState({}, "", loc.toString());
  urlParamsGlobal = new URLSearchParams(window.location.search);
}
if (uqFlag) {
  sessionStorage.setItem("liseniq_uq_flag", "true");
}

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

// Utilidad para decodificar JWT en el cliente
const parseJwt = function(token) {
    try {
        if (!token) return null;
        const base64Url = token.split('.')[1];
        if (!base64Url) return null;
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
};

// Ocultar navbars antes de que cargue el webform
frappe.web_form.before_load = () => {
  $("nav").hide();
  $(".navbar").hide();
};

frappe.web_form.after_load = () => {
  $(".page-header-actions-block").hide();
  $(".page-header").hide();
  $(".web-form-container").hide();
  $(".web-form-footer").hide();
  $("nav").hide();
  $("navbar").hide();
  
  $(".breadcrumb-container").hide();
  
  $(".frappe-control[data-fieldname='responses']").hide();
  $(".frappe-control[data-fieldname='response_json']").hide();
  $(".frappe-control[data-fieldname='user']").hide();
  $(".frappe-control[data-fieldname='survey']").hide();
  
  // Ocultar los campos de roles en el Web Form para encuestas ya existentes
  $(".frappe-control[data-fieldname='custom_evaluatee']").hide();
  $(".frappe-control[data-fieldname='custom_evaluator']").hide();
  
  $('.web-form-actions button[type="submit"]').hide();

  // Validar si ya hay respuestas guardadas en localStorage
  const surveyCacheKey = "liseniq_survey_cache_" + frappe.web_form.title;
  const cachedResponses = localStorage.getItem(surveyCacheKey);

  // Extraer parámetros
  const urlParams = urlParamsGlobal;
  const token = urlParams.get("token");
  const dni = localStorage.getItem("liseniq_doc_id");
  
  // Verificamos si el token es personalizado (tiene rid) para saltar validación de DNI
  const decodedToken = parseJwt(token);
  const hasRid = decodedToken && !!decodedToken.rid;

  frappe.call({
      method: "liseniq.utils.api_survey.get_survey_is_anonymous",
      args: { survey_name: frappe.web_form.title }
  }).then(r => {
      const is_anonymous = r.message;
      // Guardamos el estado globalmente para usarlo al enviar
      window.liseniq_is_anonymous_survey = !!is_anonymous;

      // Sanitización de URL en caso de encuesta anónima
      if (is_anonymous && token) {
          const cleanUrl = new URL(window.location.href);
          cleanUrl.searchParams.delete("token");
          window.history.replaceState({}, document.title, cleanUrl.toString());
          // Actualizamos los params globales sin el token
          urlParamsGlobal = new URLSearchParams(window.location.search);
      }

      // Agregamos la excepción "!hasRid" para no pedir DNI en enlaces directos de 360
      if (uqFlag && (!dni || String(dni).trim() === "") && !is_anonymous && !hasRid) {
          frappe.msgprint({
              title: __("Acceso denegado"),
              indicator: "red",
              message: __("Debe ingresar su DNI para continuar con la medición. Será redirigido al registro."),
          });
          setTimeout(() => {
              window.location.href = buildRegisterUrl(token, __("Debe ingresar su DNI para continuar con la medición."));
          }, 1200);
          return;
      }

      // Bloqueo base
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
            user: is_anonymous ? "Anonimo" : (token || "Anonimo"),
            token: is_anonymous ? null : token,
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
          if (res.require_dni && uqFlag && !is_anonymous && !hasRid) {
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
    // Si es anónima, no validamos DNI contra token
    if (window.liseniq_is_anonymous_survey) {
        localStorage.setItem("liseniq_doc_id", dni);
        return;
    }

    const token = urlParamsGlobal.get("token");
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
        // Si el backend indica redirección al registro
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
            localStorage.removeItem("liseniq_doc_id");
        } else if (res.valid_dni === false) {
            const error_msg = res.message || __("El DNI ingresado no se encuentra registrado como contacto.");
            $(dni_field.input).addClass('is-invalid');
            $(dni_field.wrapper).append(`<div class="invalid-feedback">${error_msg}</div>`);
            $submit_btn.prop('disabled', true);
            localStorage.removeItem("liseniq_doc_id");
            if (uqFlag) {
                setTimeout(() => { window.location.href = buildRegisterUrl(token, error_msg); }, 1200);
            }
        } else {
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
  
  const urlParams = urlParamsGlobal;
  const token = urlParams.get("token");
  const doc_id = localStorage.getItem("liseniq_doc_id");

  frappe
    .call({
      method: "liseniq.utils.api_survey.get_public_survey",
      args: {
        survey_name: frappe.web_form.title,
        token: token || null,
        dni: doc_id || null
      },
    })
    .then((r) => {
      build_survey(r.message);
      const survey = new Survey.Model(frappe.survey_json);
      survey.locale = "es";
      
      // Control de comportamiento según el tipo de medición
      if (r.message.is_leadership) {
          window.liseniq_is_leadership = true;
          survey.completedHtml = "<h4>" + __("Guardando respuesta y verificando evaluaciones pendientes...") + "</h4>";
      } else {
          survey.completedHtml = "<h4>" + __("Gracias por completar la encuesta.") + "</h4>";
      }
      
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
  
  // Sanitización del campo 'user' para evitar errores de longitud
  let user_for_db = "Anonimo";

  if (window.liseniq_is_anonymous_survey) {
      user_for_db = "Anonimo";
  } else if (doc_id) {
      user_for_db = doc_id;
  } else if (token) {
      if (token.length > 100) {
          user_for_db = "Anonimo";
      } else {
          user_for_db = token;
      }
  }

  // Doble verificación: si el backend espera anónimo, enviamos anónimo.
  frappe
    .call({
      method: "liseniq.utils.api_survey.validate_survey_link",
      args: {
        survey_name: frappe.web_form.title,
        user: window.liseniq_is_anonymous_survey ? "Anonimo" : (token || "Anonimo"),
        token: window.liseniq_is_anonymous_survey ? null : token,
        dni: doc_id || null,
        uq: uqFlag
      },
    })
    .then((r) => {
      const res = r.message || {};
      
      // Bloqueos de seguridad (También agregamos tolerancia al rid aquí)
      const decodedToken = parseJwt(token);
      const hasRid = decodedToken && !!decodedToken.rid;

      if (res.redirect_register) {
          const reg_token = res.register_token || token;
          window.location.href = buildRegisterUrl(reg_token, res.message);
          return;
      }
      if (res.require_dni && uqFlag && !window.liseniq_is_anonymous_survey && !hasRid) {
          window.location.href = buildRegisterUrl(token, res.message || __("Debe ingresar su DNI para continuar."));
          return;
      }
      if (res.allow === false) {
        show_completed_message(res.message || __("Esta encuesta ya fue completada. Gracias por tu participación."));
        window.saving = false;
        return;
      }

      const payload = Object.assign({}, data);
      if (token && !window.liseniq_is_anonymous_survey) {
        payload.__token = token;
      }

      let args = {
        doctype: frappe.web_form.doc_type,
        survey: frappe.web_form.title,
        response_json: JSON.stringify(payload),
        user: user_for_db
      };

      frappe.call({
        type: "POST",
        method: "frappe.website.doctype.web_form.web_form.accept",
        args: {
          web_form: frappe.web_form.name,
          data: args,
        },
        callback: (response) => {
          if (!response.exc) {
            localStorage.removeItem("liseniq_survey_cache_" + frappe.web_form.title);
            
            if (window.liseniq_is_leadership) {
                // Si es liderazgo 360, redirigimos al dashboard para continuar evaluando
                setTimeout(() => {
                    window.location.href = buildRegisterUrl(token);
                }, 2000);
            } else {
                localStorage.removeItem("liseniq_doc_id");
            }
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
nav, .navbar {
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

/* Estilos para Likert Visual (SurveyJS imagepicker) */
.sd-imagepicker, .sv-imagepicker {
    --iq-img-size: 32px;
}

/* Ocultar la imagen transparente de respaldo para no generar espacio vacío */
img[src*="R0lGODlhAQABAIAAAAAAAP"] {
    display: none !important;
}

/* Permitir que los contenedores de imagen se colapsen si no hay imagen (o si está oculta) */
.sd-imagepicker .sd-imagepicker__image,
.sv-imagepicker .sv_q_imgsel_image {
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    margin: 0 auto;
}

/* Imagen en versiones nuevas (sd-*) */
.sd-imagepicker .sd-imagepicker__item img,
.sd-imagepicker .sd-imagepicker__image img {
    width: auto !important;
    height: auto !important;
    max-width: var(--iq-img-size) !important;
    max-height: var(--iq-img-size) !important;
    object-fit: contain;
    display: block;
    margin: 0 auto;
    pointer-events: none; /* Que el clic pase al input padre */
}

/* Imagen en versiones legacy (sv-*) */
.sv-imagepicker .sv_q_imgsel img {
    width: auto !important;
    height: auto !important;
    max-width: var(--iq-img-size) !important;
    max-height: var(--iq-img-size) !important;
    object-fit: contain;
    display: block;
    margin: 0 auto;
    pointer-events: none;
}

/* Asegurar que el contenedor sea siempre clickeable */
.sd-imagepicker .sd-imagepicker__item,
.sv-imagepicker .sv_q_imgsel_item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 10px;
    text-align: center;
    border-radius: 8px;
    cursor: pointer !important;
    position: relative;
    transition: background-color 0.2s ease;
    min-height: 60px; /* Asegura un área de click aceptable aunque no haya imagen */
}

.sd-imagepicker .sd-imagepicker__item:hover,
.sv-imagepicker .sv_q_imgsel_item:hover {
    background-color: #f4f5f7;
}

/* Forzar el z-index y expansión del input real para garantizar la captura del clic */
.sd-imagepicker__item input[type="radio"],
.sd-imagepicker__item input[type="checkbox"],
.sv_q_imgsel_item input[type="radio"],
.sv_q_imgsel_item input[type="checkbox"] {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    height: 100% !important;
    opacity: 0 !important;
    z-index: 10 !important;
    cursor: pointer !important;
    margin: 0 !important;
}

/* Ajuste de tamaño y margen del texto */
.sd-imagepicker .sd-imagepicker__item .sd-imagepicker__item-text,
.sv-imagepicker .sv_q_imgsel_item span {
    font-size: 0.9rem;
    text-align: center;
    margin-top: 4px;
    pointer-events: none; /* Que el clic pase al input padre */
}

/* Centrar la etiqueta */
.sv-imagepicker .sv_q_imgsel_label {
    text-align: center !important;
    width: 100%;
}

/* Eliminar bordes y sombras nativas que interfieren con el diseño personalizado */
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

/* Hacer más ancha la visualización de números en la escala NPS */
.sd-rating__item, .sv_q_rating_item {
    min-width: 3.5rem !important;
}

/* Ajustar el tamaño y margen de los textos MIN y MAX en la escala NPS */
.sd-rating__min-text, 
.sd-rating__max-text,
.sv_q_rating_min_text, 
.sv_q_rating_max_text {
    font-size: 0.75rem !important;
    margin-bottom: 0.5rem !important;
    display: inline-block;
}

/* Estilos para selección - visual indicator */
.sv_qstn .sv_q_imgsel label > input:checked + div,
.sv_qstn .sv_q_imgsel_item.checked {
    background-color: #d1f0ea !important;
    border-radius: 8px;
}

/* Estilos para selección nueva (sd-*) */
.sd-imagepicker .sd-imagepicker__item--selected,
.sd-imagepicker .sd-imagepicker__item--checked {
    background-color: #d1f0ea !important;
    border-radius: 8px;
}

 /* Estilos para selección inline */
.sv_main .sv_p_root .sv_q .sv_q_checkbox_inline label > input:checked + span,
.sv_main .sv_p_root .sv_q .sv_q_radiogroup_inline label > input:checked + span {
    background-color: #d1f0ea !important;
}
"""