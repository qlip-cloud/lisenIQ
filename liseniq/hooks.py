# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "liseniq"
app_title = "Liseniq"
app_publisher = "Mentum Group"
app_description = "LisenIQ"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "adolfo.hernandez@mentum.group"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/liseniq/css/liseniq_base.css"
app_include_js = "/assets/liseniq/js/liseniq_base.js"

# include js, css files in header of web template
# web_include_css = "/assets/liseniq/css/liseniq.css"
# web_include_js = "/assets/liseniq/js/liseniq.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "liseniq/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# Carga de CSS y JS para páginas específicas
# ---------------------------------------------

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
home_page = "home"

get_website_user_home_page = "liseniq.liseniq.uses_cases.login.redirects.get_home_page"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "liseniq.install.before_install"
# after_install = "liseniq.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "liseniq.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# on_login hook
on_login = "liseniq.liseniq.uses_cases.login.redirects.handle_login_redirect"

# Inicializa variables de sesión al crearla
on_session_creation = "liseniq.utils.login_util.set_company_name_on_session_creation"

doc_events = {
	"Survey Response": {
		"before_insert": "liseniq.utils.survey_response.process_survey_response"
	},
	"qp_IQ_Survey": {
		"on_update": "liseniq.utils.api_survey.generate_public_link_for_survey_hook"
	},
	"User": {
		"after_insert": "liseniq.utils.user_hooks.link_company_after_b2c"
	},
	"Contact": {
		"after_insert": "liseniq.utils.user_hooks.link_contact_after_create"
	}
}

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/2 * * * *": [
			"liseniq.tasks.launch_pending_surveys",
			"liseniq.tasks.update_finished_surveys"
		],
		"0 9 * * *": [
			"liseniq.tasks.send_survey_reminders"
		],
		"30 1 * * *": [
			"liseniq.utils.historical_loader.scheduled_archive_finished_surveys"
		]
	},
	# "hourly": [
	# 	"liseniq.tasks.send_survey_reminders"
	# ],
# 	"daily": [
# 		"liseniq.tasks.daily"
# 	],
# 	"hourly": [
# 		"liseniq.tasks.hourly"
# 	],
# 	"weekly": [
# 		"liseniq.tasks.weekly"
# 	],
# 	"monthly": [
# 		"liseniq.tasks.monthly"
# 	]
}

# Testing
# -------

# before_tests = "liseniq.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "liseniq.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "liseniq.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"liseniq.auth.validate"
# ]

# website_redirects = [
#     {"source": "/login", "target": "/login-qlip"},
# ]

# Contexto Global y Reglas de Enrutamiento del Portal Web
# ----------------------------------------------------

website_context = {
	"*": "liseniq.utils.global_website_context"
}

# Función para inyectar contexto global en páginas del portal
update_website_context = "liseniq.utils.login_util.global_website_context"


page_css = {
    # "iq_templates/index": "public/css/iq_templates.css",
}

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [
			["dt", "in", ["User", "Contact"]]
		]
	},
	{
		"doctype": "qp_IQ_RecipientStatus",
		"filters": [
			["rs_status", "in", ["Not Sent", "Sent", "Responded"]]
		]
	},
]