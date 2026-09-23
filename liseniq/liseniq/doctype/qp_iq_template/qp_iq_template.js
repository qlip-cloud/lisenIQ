// Copyright (c) 2025, Mentum Group and contributors
// For license information, please see license.txt

frappe.ui.form.on('qp_IQ_Template', {
	
	setup: function(frm) {
		frm.set_query("tp_owner", function() {
			return {
				filters: {
					"custom_is_liseniq_contact": 0
				}
			};
		});
	},

	refresh: function(frm) {
		if (frm.doc.tp_owner) {
			frm.trigger('tp_owner');
		}
	}
});