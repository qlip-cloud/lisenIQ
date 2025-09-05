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
  
  load_survey(frappe.web_form.title);
};

frappe.ready(function() {
  $('<style>.survey-completed { pointer-events: none; opacity: 0.7; }</style>').appendTo('head');
});

const load_survey = function (survey_name) {
  $(".web-form-container").toggle(false);
  $('<div id="surveyElement"></div>').appendTo($(".page_content"));
  frappe
    .call({
      method: "frappe.client.get",
      args: {
        doctype: "Survey",
        name: frappe.web_form.title,
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
  
  const currentDate = frappe.datetime.nowdate();
  
  let args = {
    doctype: frappe.web_form.doc_type,
    response_json: JSON.stringify(data),
    user: currentDate
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
        frappe.show_alert(__("Your response has been submitted successfully."));
      }
    },
    always: function () {
      window.saving = false;
    },
  });
};
"""
