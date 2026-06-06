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
                callback: function (r) {
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
                error: function (r) {
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
                reqd: 1,
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
            }
        ],

        primary_action_label: __('Start Generation'),

        primary_action(values) {
            if (!values.survey_id || !values.demographic_field) {
                frappe.msgprint(__('Please fill all required fields'));
                return;
            }

            start_cultura_report_batch(values);
            dialog.hide();
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
            async_mode: true
        },

        freeze: true,
        freeze_message: __('Starting batch processing...'),

        callback: function (r) {

            if (r.message && r.message.status === 'success') {

                frappe.msgprint({
                    title: __('Proceso iniciado'),
                    indicator: 'green',
                    message: __(
                        'La generación de reportes inició correctamente.<br><br>' +
                        'Puedes consultar el progreso en <b>qp_IQ_ReportProgress</b>.'
                    )
                });

                cur_list.refresh();

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


function show_cultura_batch_dialog_from_list() {
    show_cultura_batch_dialog({ name: null });
}