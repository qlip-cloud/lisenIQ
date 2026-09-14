# Copyright (c) 2026, Mentum Group and contributors
# For license information, please see license.txt

import frappe
import json
import csv
import traceback
from frappe.model.document import Document
from frappe.utils.file_manager import get_file_path

class qp_IQ_HistoricMigration(Document):
    
    @frappe.whitelist()
    def trigger_migration(self):
        if self.hm_status != 'Pendiente':
            frappe.throw("El estado debe ser 'Pendiente' para ejecutar la migración.")
        
        if not self.hm_creator:
            frappe.throw("Debe seleccionar un Creador antes de iniciar.")
        
        self.db_set('hm_status', 'En Progreso')
        self.db_set('hm_error_log', '')
        frappe.db.commit()
        
        try:
            frappe.enqueue_doc(
                self.doctype,
                self.name,
                'process_migration',
                queue='long',
                timeout=3600,
                is_async=True
            )
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Error en trigger_migration - Migración {self.name}")
            raise e

    @frappe.whitelist()
    def cancel_migration(self):
        if self.hm_status == 'En Progreso':
            self.db_set('hm_status', 'Fallido')
            self.db_set('hm_error_log', 'Migración cancelada manualmente por el usuario.')
            frappe.db.commit()

    def process_migration(self):
        try:
            if not self.hm_file:
                raise Exception("No se adjuntó ningún archivo para procesar.")

            file_path = get_file_path(self.hm_file)
            rows = []
            headers = []
            file_extension = file_path.lower().split('.')[-1]

            if file_extension in ['xlsx', 'xls']:
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    sheet = wb.active
                    data_rows = list(sheet.iter_rows(values_only=True))
                    
                    if data_rows:
                        headers = [str(h).strip() if h is not None else '' for h in data_rows[0]]
                        for row_data in data_rows[1:]:
                            if any(cell is not None and str(cell).strip() != '' for cell in row_data):
                                row_dict = {}
                                for i, cell_value in enumerate(row_data):
                                    if i < len(headers) and headers[i]:
                                        row_dict[headers[i]] = str(cell_value).strip() if cell_value is not None else ''
                                rows.append(row_dict)
                except Exception as ex:
                    raise Exception(f"Error procesando Excel: {str(ex)}")

            elif file_extension == 'csv':
                try:
                    with open(file_path, mode='r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        headers = reader.fieldnames
                        rows = list(reader)
                except UnicodeDecodeError:
                    with open(file_path, mode='r', encoding='latin-1') as f:
                        reader = csv.DictReader(f)
                        headers = reader.fieldnames
                        rows = list(reader)
            else:
                raise Exception(f"Formato no soportado: .{file_extension}")
            
            if not rows or not headers:
                raise Exception("El archivo está vacío o no es procesable.")

            cultura_idx = -1
            for i, h in enumerate(headers):
                if h and h.strip() == 'Tipo de Cultura':
                    cultura_idx = i
                    break
                    
            if cultura_idx == -1:
                raise Exception("Columna 'Tipo de Cultura' obligatoria no encontrada.")

            demo_headers = [h for i, h in enumerate(headers) if i < cultura_idx and h and h.strip() != 'ID Interno']

            company = frappe.db.get_value('Contact', self.hm_creator, 'custom_company')
            if not company:
                raise Exception(f"El Contacto {self.hm_creator} no tiene compañía configurada (custom_company).")
                
            base_template_id = self.hm_template
            creator_contact = self.hm_creator
            
            # Validación de categoría para activar normalización de respuestas
            is_culture_template = False
            template_category = None
            
            if base_template_id:
                try:
                    template_category = frappe.db.get_value('qp_IQ_Template', base_template_id, 'tp_category')
                    if template_category:
                        qnc_mnemonico = frappe.db.get_value('qp_IQ_TemplateCategory', template_category, 'qnc_mnemonico')
                        if qnc_mnemonico and str(qnc_mnemonico).strip().lower() == 'template_culture':
                            is_culture_template = True
                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Error detectando categoría - Migración {self.name}")

            culture_normalization_map = {
                "-4": "1", "-4.0": "1",
                "-3": "1.5", "-3.0": "1.5",
                "-2": "2", "-2.0": "2",
                "-1": "2.5", "-1.0": "2.5",
                "0": "3", "0.0": "3",
                "1": "3.5", "1.0": "3.5",
                "2": "4", "2.0": "4",
                "3": "4.5", "3.0": "4.5",
                "4": "5", "4.0": "5"
            }

            grouped_contacts = {}
            unique_questions = set()

            for row in rows:
                raw_id = str(row.get('ID Interno', '')).strip()
                id_interno = raw_id.replace("ObjectId(", "").replace(")", "").strip()
                
                if not id_interno:
                    continue

                if id_interno not in grouped_contacts:
                    grouped_contacts[id_interno] = {
                        'static_fields': {
                            'shd_country': str(row.get('País', '')).strip(),
                            'shd_gender': str(row.get('Genero', '')).strip(),
                            'shd_academic_level': str(row.get('Nivel Académico', '')).strip(),
                            'shd_document_number': id_interno
                        },
                        'demographics': {h: str(row.get(h, '')).strip() for h in demo_headers if row.get(h) and str(row.get(h, '')).strip()},
                        'responses': {}
                    }
                
                cultura = str(row.get('Tipo de Cultura', '')).strip()
                dimension = str(row.get('Dimensión', '')).strip()
                atributo = str(row.get('Atributo', '')).strip()
                respuesta = str(row.get('Respuesta', '')).strip()

                if atributo:
                    unique_questions.add((cultura, dimension, atributo))
                    grouped_contacts[id_interno]['responses'][atributo] = respuesta

            def get_or_create_demographic(demo_name):
                if not demo_name: 
                    return None
                demo_name = str(demo_name).strip()
                if frappe.db.exists('qp_IQ_DemographicType', demo_name):
                    return demo_name
                try:
                    doc = frappe.get_doc({
                        'doctype': 'qp_IQ_DemographicType',
                        'dt_object_type': 'Contacto',
                        'name': demo_name,
                        'dt_name': demo_name,
                        'title': demo_name
                    })
                    meta = frappe.get_meta('qp_IQ_DemographicType')
                    if meta.has_field('custom_company'):
                        doc.custom_company = company
                    elif meta.has_field('dt_company'):
                        doc.dt_company = company
                    doc.flags.ignore_mandatory = True
                    doc.insert(ignore_permissions=True, set_name=demo_name)
                    return doc.name
                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Error creando demográfico {demo_name} - Migración {self.name}")
                    return demo_name

            question_map = {}
            new_questions_created = False
            existing_template_qs = {}

            if base_template_id:
                base_template = frappe.get_doc('qp_IQ_Template', base_template_id)
                for tq in base_template.tp_questions:
                    q_id = tq.get('question') or tq.get('tq_question') or tq.get('qn_question')
                    if q_id:
                        try:
                            stmt = frappe.db.get_value('qp_IQ_Question', q_id, 'qn_statement')
                            if stmt: 
                                existing_template_qs[stmt] = q_id
                        except Exception:
                            pass

            default_q_type = frappe.db.get_value('qp_IQ_QuestionType', None, 'name')

            for cultura, dimension, atributo in unique_questions:
                if base_template_id and atributo in existing_template_qs:
                    question_map[atributo] = existing_template_qs[atributo]
                    continue
                
                existing_q = frappe.db.exists('qp_IQ_Question', {
                    'qn_statement': atributo,
                    'qn_owner': company
                })

                if existing_q:
                    question_map[atributo] = existing_q
                else:
                    topic_id = get_or_create_demographic(cultura) if cultura else None
                    dim_id = get_or_create_demographic(dimension) if dimension else None
                    
                    new_q = frappe.get_doc({
                        'doctype': 'qp_IQ_Question',
                        'qn_statement': atributo,
                        'qn_owner': company,
                        'qp_topic': topic_id,
                        'qn_demographic': dim_id,
                        'qn_type': default_q_type,
                        'qn_creator': creator_contact
                    })
                    new_q.flags.ignore_mandatory = True
                    new_q.insert(ignore_permissions=True)
                    question_map[atributo] = new_q.name
                    new_questions_created = True

            clean_survey_id = str(self.hm_survey_id or self.name).replace("ObjectId(", "").replace(")", "").strip()

            if new_questions_created:
                template_name = f"Consolidado Migración - {clean_survey_id}"
                existing_tpl = frappe.db.exists('qp_IQ_Template', {'tp_name': template_name})
                
                if existing_tpl:
                    final_template_id = existing_tpl
                else:
                    new_tpl_data = {
                        'doctype': 'qp_IQ_Template',
                        'tp_name': template_name,
                        'custom_company': company,
                        'tp_status': 'Activa',
                        'tp_is_private': 1
                    }
                    if template_category:
                        new_tpl_data['tp_category'] = template_category

                    new_tpl = frappe.get_doc(new_tpl_data)
                    new_tpl.flags.ignore_mandatory = True
                    for q_id in question_map.values():
                        new_tpl.append('tp_questions', {
                            'question': q_id,
                            'tq_question': q_id,
                            'qn_question': q_id
                        })
                    new_tpl.insert(ignore_permissions=True)
                    final_template_id = new_tpl.name
            else:
                final_template_id = base_template_id

            status_doc_name = None
            for field in ['name', 'title', 'status_name', 'ss_name', 'ss_status', 'estado']:
                try:
                    status_doc_name = frappe.db.get_value('qp_IQ_SurveyStatus', {field: ['like', '%Finalizada%']}, 'name')
                    if status_doc_name:
                        break
                except Exception:
                    continue
            
            if not status_doc_name:
                fallback_status = frappe.db.get_list('qp_IQ_SurveyStatus', limit_page_length=1)
                status_doc_name = fallback_status[0].name if fallback_status else ''

            survey_name_label = f"Medición Migrada - {clean_survey_id}"
            existing_survey = frappe.db.exists('qp_IQ_Survey', {'su_name': survey_name_label})
            
            if existing_survey:
                real_survey_id = existing_survey
            else:
                new_survey = frappe.get_doc({
                    'doctype': 'qp_IQ_Survey',
                    'su_name': survey_name_label,
                    'su_owner': company,
                    'su_template': final_template_id,
                    'su_status': status_doc_name,
                    'su_type': 'Migración Histórica',
                    'su_start_date': frappe.utils.now_datetime(),
                    'su_end_date': frappe.utils.now_datetime(),
                    'su_in_history': 1
                })
                new_survey.flags.ignore_mandatory = True
                new_survey.insert(ignore_permissions=True)
                real_survey_id = new_survey.name

            processed_count = 0
            safe_company_name = str(company).replace(" ", "_").lower() if company else "company"
            
            for i, (id_interno, data) in enumerate(grouped_contacts.items(), start=1):
                # Validacion de interrupcion por usuario
                if i % 10 == 0:
                    current_status = frappe.db.get_value(self.doctype, self.name, 'hm_status')
                    if current_status != 'En Progreso':
                        return

                contact_name = f"{safe_company_name}_contacto_{i}"
                mapped_responses = {}
                
                for attr, resp in data['responses'].items():
                    q_id = question_map.get(attr)
                    if q_id:
                        clean_resp = str(resp).strip()
                        clean_resp = clean_resp.replace('−', '-').replace('–', '-')
                        
                        try:
                            val_float = float(clean_resp)
                            if val_float.is_integer():
                                clean_resp = str(int(val_float))
                        except ValueError:
                            pass

                        if is_culture_template:
                            clean_resp = culture_normalization_map.get(clean_resp, clean_resp)

                        mapped_responses[q_id] = clean_resp

                doc = frappe.get_doc({
                    "doctype": "qp_IQ_SurveyHistoricData",
                    "shd_survey_id": real_survey_id,
                    "shd_survey_name": survey_name_label,
                    "shd_contact_name": contact_name,
                    "shd_document_number": data['static_fields']['shd_document_number'],
                    "shd_country": data['static_fields']['shd_country'],
                    "shd_gender": data['static_fields']['shd_gender'],
                    "shd_academic_level": data['static_fields']['shd_academic_level'],
                    "shd_company": company,
                    "shd_measurement_response": json.dumps(mapped_responses, ensure_ascii=False)
                })
                
                for d_tag, d_val in data['demographics'].items():
                    d_type_id = get_or_create_demographic(d_tag)
                    doc.append("shd_demographics", {
                        "cdh_demographic_type": d_type_id,
                        "cdh_tag": d_tag,
                        "cdh_value": d_val
                    })
                    
                doc.flags.ignore_mandatory = True
                doc.insert(ignore_permissions=True)
                processed_count += 1

            self.db_set('hm_status', 'Completado')
            self.db_set('hm_processed_records', processed_count)
            self.db_set('hm_survey_id', real_survey_id)
            self.db_set('hm_error_log', 'Migración completada exitosamente.')
            if new_questions_created:
                 self.db_set('hm_template', final_template_id)
            
            frappe.db.commit()

        except Exception as e:
            frappe.db.rollback()
            error_trace = traceback.format_exc()
            frappe.log_error(frappe.get_traceback(), f"Error en process_migration - Migración {self.name}")
            
            self.db_set('hm_status', 'Fallido')
            self.db_set('hm_error_log', error_trace)
            frappe.db.commit()