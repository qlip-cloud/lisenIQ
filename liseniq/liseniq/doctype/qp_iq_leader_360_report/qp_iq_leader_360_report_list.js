frappe.listview_settings['qp_IQ_Leader_360_Report'] = {
    onload(listview) {

        listview.page.add_inner_button(__('Generar Informes (Batched)'), () => {
            show_iq360_batch_dialog();
        });
    }
};


function show_iq360_batch_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Generate Report - Batch Processing'),
        fields: [
            {
                label: __('Survey'),
                fieldname: 'survey_id',
                fieldtype: 'Link',
                options: 'qp_IQ_Survey',
                filters: {
                    'su_is_leadership': 1
                },
                reqd: 1,
                description: __('Selecciona la medición para generar los informes')
            },
            {
                label: __('Batch Size'),
                fieldname: 'batch_size',
                fieldtype: 'Int',
                default: 10000,
                description: __('Respuestas a procesar por lote. Valor por defecto: 10000.')
            }
        ],

        primary_action_label: __('Start Generation'),

        primary_action(values) {
            if (!values.survey_id) {
                frappe.msgprint(__('Please fill all required fields'));
                return;
            }

            start_iq360_report_batch(values);
            dialog.hide();
        }
    });

    dialog.show();
}


function start_iq360_report_batch(values) {
    frappe.call({
        method: 'liseniq.liseniq.helpers.report_batch_integration.start_iq360_report_generation',

        args: {
            survey_id: values.survey_id,
            batch_size: values.batch_size || 10000,
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


function show_iq360_batch_dialog_from_list() {
    show_iq360_batch_dialog({ name: null });
}