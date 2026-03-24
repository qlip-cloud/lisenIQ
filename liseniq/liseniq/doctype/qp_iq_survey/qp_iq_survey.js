// Copyright (c) 2025, Mentum Group and contributors
// For license information, please see license.txt

frappe.ui.form.on('qp_IQ_Survey', {
	// refresh: function(frm) {

	// },
	su_manual_reminders_btn: function(frm) {
		frappe.confirm(
			'¿Estás seguro de que deseas enviar un recordatorio a todos los participantes que aún no han respondido?',
			function() {
				frappe.call({
					method: 'liseniq.tasks.send_survey_reminders',
					args: {
						survey_name: frm.doc.name
					},
					freeze: true,
					freeze_message: 'Enviando recordatorios...',
					callback: function(r) {
						if (r.message && r.message.status === 'success') {
							frappe.msgprint({
								title: '¡Éxito!',
								indicator: 'green',
								message: `Recordatorios enviados exitosamente.<br><b>Enviados:</b> ${r.message.sent}<br><b>Errores/Omitidos:</b> ${r.message.errores}`
							});
						} else if (r.message && r.message.status === 'error') {
							frappe.msgprint({
								title: 'Error',
								indicator: 'red',
								message: r.message.message || 'Ocurrió un error al enviar los recordatorios.'
							});
						}
					}
				});
			}
		);
	}
});