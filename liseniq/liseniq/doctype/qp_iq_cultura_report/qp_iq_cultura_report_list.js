frappe.listview_settings['qp_IQ_Cultura_Report'] = {
	onload(listview) {

		listview.page.add_inner_button(__('Generar Informes'), () => {
			show_generate_reports_dialog();
		});
		listview.page.add_inner_button(__('Generar Informes (Batched)'), () => {
			show_cultura_batch_dialog();
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


function show_cultura_batch_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Generate Culture Report - Batch Processing'),
        fields: [
            {
                label: __('Survey'),
                fieldname: 'survey_id',
                fieldtype: 'Link',
                options: 'qp_IQ_Survey',
                reqd: 1,
                description: __('Selecciona la medición para generar los informes')
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
						},
            {
                fieldtype: 'Section Break',
                label: __('Configuración de Batch Processing')
            },
            {
                label: __('Batch Size'),
                fieldname: 'batch_size',
                fieldtype: 'Int',
                default: 1000,
                description: __('Respuestas a procesar por lote. Valor por defecto: 1000.')
            },
            {
                label: __('Modo de Procesamiento'),
                fieldname: 'processing_mode',
                fieldtype: 'Select',
                options: [
                    { label: __('Async (Background)'), value: 'async' },
                    { label: __('Sync (En Espera)'), value: 'sync' }
                ],
                default: 'async',
                description: __('Async: se procesa en segundo plano, Sync: el usuario espera hasta que se complete el proceso.')
            },
        ],
        primary_action_label: __('Start Generation'),
        primary_action(values) {
            if (!values.survey_id || !values.demographic_field) {
                frappe.msgprint(__('Please fill all required fields'));
                return;
            }
            dialog.hide();
            start_cultura_report_batch(values);
        }
    });
    dialog.show();
}


function start_cultura_report_batch(values) {
    frappe.call({
        method: 'liseniq.liseniq.helpers.report_batch_integration.start_cultura_report_generation',
        args: {
            survey_id: values.survey_id,
            demographic_field: values.demographic_field,
            batch_size: values.batch_size || 1000,
            async_mode: values.processing_mode === 'async'
        },
        freeze: true,
        freeze_message: __('Starting batch processing...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.msgprint({
                    title: __('Success'),
                    message: r.message.message,
                    indicator: 'green'
                });
                
                if (values.processing_mode === 'async') {
                    show_progress_modal(r.message.progress_name);
                } else {
                    setTimeout(() => {
                        frappe.msgprint(__('Report generation completed!'));
                    }, 2000);
                }
            } else if (r.message && r.message.status === 'skipped') {
                frappe.msgprint({
                    title: __('Skipped'),
                    message: r.message.message,
                    indicator: 'yellow'
                });
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message?.message || __('Failed to start batch processing'),
                    indicator: 'red'
                });
            }
        }
    });
}


function show_progress_modal(progress_name) {
    const progress_dialog = new frappe.ui.Dialog({
        title: __('Report Generation Progress'),
        static: true,
        primary_action_label: __('Close'),
        primary_action() {
            clearInterval(poll_interval);
            progress_dialog.hide();
        },
        fields: [
            {
                label: __('Status'),
                fieldname: 'batch_status',
                fieldtype: 'Data',
                read_only: 1
            },
            {
                label: __('Progress'),
                fieldname: 'progress_text',
                fieldtype: 'Data',
                read_only: 1
            },
            {
                fieldtype: 'Progress',
                fieldname: 'percentage'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'progress_details',
                html: ''
            },
            {
                label: __('Error Message'),
                fieldname: 'error_message',
                fieldtype: 'Text',
                read_only: 1,
                hidden: true
            }
        ]
    });
    
    progress_dialog.show();
    
    let poll_interval = setInterval(function() {
        frappe.call({
            method: 'liseniq.liseniq.helpers.report_batch_integration.get_progress_status',
            args: { progress_name: progress_name },
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    const msg = r.message;
                    
                    progress_dialog.set_values({
                        'batch_status': msg.batch_status,
                        'progress_text': `${msg.processed_responses} / ${msg.total_responses} responses`,
                        'percentage': msg.percentage
                    });
                    
                    const details_html = `
                        <div style="font-size: 12px; color: #666;">
                            <p><strong>Current Batch:</strong> ${msg.current_batch}</p>
                            <p><strong>Report Type:</strong> ${msg.report_type}</p>
                            <p><strong>Completion:</strong> ${msg.percentage.toFixed(1)}%</p>
                        </div>
                    `;
                    progress_dialog.set_values({ 'progress_details': details_html });
                    
                    if (msg.batch_status === 'completed') {
                        clearInterval(poll_interval);
                        frappe.msgprint({
                            title: __('Success'),
                            message: __('Report generation completed successfully!'),
                            indicator: 'green'
                        });
                        progress_dialog.hide();
                        cur_list.refresh(); 
                    } else if (msg.batch_status === 'failed') {
                        clearInterval(poll_interval);
                        progress_dialog.set_values({
                            'error_message': msg.error_message,
                            'batch_status': 'Failed'
                        });
                        progress_dialog.df_by_name.error_message.df.hidden = false;
                        progress_dialog.refresh();
                        frappe.msgprint({
                            title: __('Error'),
                            message: `Batch processing failed:\n${msg.error_message}`,
                            indicator: 'red'
                        });
                    }
                }
            },
            error: function() {
            }
        });
    }, 2000); 
}

function show_cultura_batch_dialog_from_list() {
    show_cultura_batch_dialog({ name: null });
}
