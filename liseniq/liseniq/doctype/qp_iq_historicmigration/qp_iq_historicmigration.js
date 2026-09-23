// Copyright (c) 2026, Mentum Group and contributors
// For license information, please see license.txt

frappe.ui.form.on('qp_IQ_HistoricMigration', {
	
	setup: function(frm) {
		frm.set_query("hm_creator", function() {
			return {
				filters: {
					"custom_is_liseniq_contact": 0
				}
			};
		});
	},

	onload: function(frm) {
		if(frm.is_new()) {
			frm.set_value('hm_status', 'Pendiente');
		}
	},

	refresh: function(frm) {
		if (frm.doc.hm_status !== 'Pendiente') {
			frm.set_df_property('hm_file', 'read_only', 1);
			frm.set_df_property('hm_survey_id', 'read_only', 1);
			if (frm.fields_dict['hm_creator']) {
				frm.set_df_property('hm_creator', 'read_only', 1); 
			}
		}

		if (frm.doc.hm_status === 'En Progreso') {
			frm.dashboard.set_headline(__('La migración se está ejecutando en segundo plano. Esta página se actualizará automáticamente.'));
			
			frm.add_custom_button(__('Cancelar'), function() {
				frappe.confirm(__('¿Estás seguro de que deseas detener la migración?'), () => {
					frappe.call({
						method: 'cancel_migration',
						doc: frm.doc,
						callback: function(r) {
							if (!r.exc) {
								frm.reload_doc();
								frappe.show_alert({message:__('Se ha enviado la señal de cancelación al proceso.'), indicator:'orange'});
							}
						}
					});
				});
			}).addClass('btn-danger');

			setTimeout(() => {
				if (frm.doc.hm_status === 'En Progreso') {
					frm.reload_doc();
				}
			}, 5000);
		} else {
			frm.dashboard.clear_headline();
		}

		if (frm.doc.hm_status === 'Pendiente' && !frm.is_new()) {
			frm.add_custom_button(__('Ejecutar'), function() {
				
				let fieldname_contacto = 'hm_creator';

				if (!frm.doc[fieldname_contacto]) {
					frappe.msgprint({
						title: __('Validación de Creador'),
						message: __('Por favor, selecciona un Creador para asociar las preguntas antes de ejecutar.'),
						indicator: 'orange'
					});
					return;
				}

				let execute_backend = function() {
					frappe.call({
						method: 'trigger_migration',
						doc: frm.doc,
						callback: function(r) {
							if (!r.exc) {
								frm.reload_doc();
								frappe.show_alert({message:__('Migración iniciada en segundo plano.'), indicator:'green'});
							}
						}
					});
				};

				// Asegura persistencia de datos previos a la ejecución en BD
				if (frm.is_dirty()) {
					frm.save('Save', () => {
						execute_backend();
					}, () => {
						frappe.msgprint(__('Por favor, corrige los errores antes de continuar.'));
					});
				} else {
					execute_backend();
				}
				
			}).addClass('btn-primary');
		}

		if (frm.doc.hm_status === 'Fallido') {
			frm.add_custom_button(__('Reintentar Migración'), function() {
				frappe.confirm(__('¿Estás seguro que deseas reintentar la migración?'), () => {
					frappe.call({
						method: 'frappe.client.set_value',
						args: {
							doctype: frm.doc.doctype,
							name: frm.doc.name,
							fieldname: 'hm_status',
							value: 'Pendiente'
						},
						callback: function(r) {
							if (!r.exc) {
								frm.reload_doc();
								frappe.show_alert({
									message:__('Estado reiniciado. Por favor verifica tus archivos y presiona Ejecutar.'),
									indicator:'green'
								});
							}
						}
					});
				});
			}).addClass('btn-warning');
		}
	}
});