frappe.listview_settings['qp_IQ_Cultura_Report'] = {
	onload(listview) {

		listview.page.add_inner_button(__('Generar Informes'), () => {
			show_generate_reports_dialog();
		});

	}
};
function show_generate_reports_dialog() {
	const dialog = new frappe.ui.Dialog({
		title: __('Generar Informes de Cultura'),
		fields: [
			{
				fieldname: 'survey',
				fieldtype: 'Link',
				options: 'qp_IQ_Survey',
				label: __('Medición'),
				required: 1,

			},
			{
				fieldname: 'demographic_field',
				fieldtype: 'Link',
				options: 'qp_IQ_DemographicType',
        filters: {
          'dt_object_type': 'Contacto'
        },
				label: __('Campo Demográfico'),
				description: __('Ej: custom_area, custom_department, custom_division'),
				required: 1,
				placeholder: __('custom_area'),
			}
		],
		primary_action_label: __('Generar'),
		primary_action(values) {
			if (!values.survey || !values.demographic_field) {
				frappe.msgprint(__('Por favor completa todos los campos'));
				return;
			}

			frappe.call({
				method: 'liseniq.liseniq.doctype.qp_iq_cultura_report.qp_iq_cultura_report.generate_cultura_reports',
				args: {
					survey_id: values.survey,
					demographic_field: values.demographic_field
				},
				callback: function(r) {
					if (r.message) {
						frappe.msgprint({
							title: __('Éxito'),
							message: r.message,
							indicator: 'green'
						});
						dialog.hide();
						cur_list.refresh();
					} else {
						frappe.msgprint({
							title: __('Error'),
							message: __('No se generaron los informes'),
							indicator: 'red'
						});
            console.error('Error al generar informes:', r);
					}
				},
				error: function(r) {
					frappe.msgprint({
						title: __('Error'),
						message: __('Ocurrió un error al generar los informes'),
						indicator: 'red'
					});
				}
			});
		}
	});

	dialog.show();
}