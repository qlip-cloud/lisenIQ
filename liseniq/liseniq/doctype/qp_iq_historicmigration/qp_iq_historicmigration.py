# Copyright (c) 2026, Mentum Group and contributors
# For license information, please see license.txt

import frappe
import json
import csv
import traceback
import time
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
        self.db_set('hm_duration', '')
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
        start_time = time.time()
        try:
            if not self.hm_file:
                raise Exception("No se adjuntó ningún archivo para procesar.")

            file_path = get_file_path(self.hm_file)
            
            # Obtenemos datos preliminares para dinamizar el mapeo de columnas del archivo
            company = frappe.db.get_value('Contact', self.hm_creator, 'custom_company')
            if not company:
                raise Exception(f"El Contacto {self.hm_creator} no tiene compañía configurada (custom_company).")
                
            base_template_id = self.hm_template
            creator_contact = self.hm_creator
            
            # Validación de categoría para bifurcación (Ej. Cultura vs Engagement)
            is_culture_template = False
            is_engagement_template = False
            template_category = None
            
            if base_template_id:
                try:
                    template_category = frappe.db.get_value('qp_IQ_Template', base_template_id, 'tp_category')
                    if template_category:
                        qnc_mnemonico = frappe.db.get_value('qp_IQ_TemplateCategory', template_category, 'qnc_mnemonico')
                        if qnc_mnemonico:
                            mnemonico_str = str(qnc_mnemonico).strip().lower()
                            if mnemonico_str == 'template_culture':
                                is_culture_template = True
                            elif mnemonico_str == 'template_engagement':
                                is_engagement_template = True
                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Error detectando categoría - Migración {self.name}")

            rows = []
            headers = []
            file_extension = file_path.lower().split('.')[-1]

            if file_extension in ['xlsx', 'xls']:
                try:
                    import openpyxl
                    # read_only=True para procesamiento en generador sin saturación de RAM
                    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
                    
                    # Selección dinámica de hoja: 'Cuestionario' o la primera por defecto
                    target_sheet = None
                    for sheet_name in wb.sheetnames:
                        if str(sheet_name).strip().lower() == 'cuestionario':
                            target_sheet = wb[sheet_name]
                            break
                    
                    if target_sheet is None:
                        # Fallback a la primera hoja disponible si no se encuentra 'Cuestionario'
                        first_sheet_name = wb.sheetnames[0] if wb.sheetnames else None
                        target_sheet = wb[first_sheet_name] if first_sheet_name else wb.active
                        
                    data_rows = list(target_sheet.iter_rows(values_only=True))
                    
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

            pivot_idx = -1
            pivot_col_name = ''
            
            expected_pivots_raw = []
            if is_culture_template:
                # Pivote de cultura: Tema -> Dimensión -> Pregunta
                expected_pivots_raw = ['tema', 'dimension', 'dimension',  'cultura']
            elif is_engagement_template:
                # Pivote de engagement: Dimensión -> Atributo -> Pregunta
                expected_pivots_raw = ['dimensión', 'dimension', 'atributo', 'pregunta']
            
            # Fallback a columnas comunes genéricas
            expected_pivots_raw.extend(['tema', 'tipo de cultura', 'tipo de engagement', 'engagement', 'categoría', 'categoria', 'factor', 'dimensión', 'dimension'])
            expected_pivots = list(dict.fromkeys(expected_pivots_raw))
            
            # Columnas delimitadoras de fallback si no hay categoría principal en el archivo
            fallback_delimiters = ['dimensión', 'dimension', 'atributo', 'pregunta']
            
            for i, h in enumerate(headers):
                if h:
                    # Limpiamos espacios dobles y normalizamos a minúsculas
                    clean_h = " ".join(str(h).strip().lower().split())
                    if clean_h in expected_pivots:
                        pivot_idx = i
                        pivot_col_name = str(h).strip()
                        break
                        
            # Si no se encontró columna de categoría, buscamos delimitadores secundarios (ej. arranca en Dimensión)
            if pivot_idx == -1:
                for i, h in enumerate(headers):
                    if h:
                        clean_h = " ".join(str(h).strip().lower().split())
                        if clean_h in fallback_delimiters:
                            pivot_idx = i
                            break

            if pivot_idx == -1:
                display_options = [title.title() for title in (expected_pivots + fallback_delimiters)]
                raise Exception(f"No se pudo identificar la columna pivote (límite de demográficos). Asegúrese de incluir al menos una de estas columnas: {', '.join(display_options)}")

            demo_headers = [h for i, h in enumerate(headers) if i < pivot_idx and h and h.strip() != 'ID Interno']

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
                
                topic_val = ''
                dimension = ''
                statement = ''
                
                if is_engagement_template:
                    # Jerarquía Engagement: Dimensión -> Atributo -> Pregunta
                    topic_val = str(row.get('Dimensión', row.get('Dimension', ''))).strip()
                    dimension = str(row.get('Atributo', '')).strip()
                    statement = str(row.get('Pregunta', '')).strip()
                    
                    # Fallback por si la estructura está incompleta
                    if not statement:
                        statement = dimension
                        dimension = ''
                else:
                    # Jerarquía Cultura: Tema -> Dimensión -> Atributo
                    topic_val = str(row.get(pivot_col_name, '')).strip() if pivot_col_name else ''
                    dimension = str(row.get('Dimensión', row.get('Dimension', ''))).strip()
                    statement = str(row.get('Atributo', '')).strip()
                    
                    # Fallback por si la estructura está incompleta
                    if not statement:
                        statement = str(row.get('Pregunta', '')).strip()
                        
                respuesta = str(row.get('Respuesta', '')).strip()

                if statement:
                    unique_questions.add((topic_val, dimension, statement))
                    grouped_contacts[id_interno]['responses'][statement] = respuesta

            # Optimización de caché para demográficos
            demographics_list = frappe.db.get_all('qp_IQ_DemographicType', fields=['name', 'dt_title'])
            demographic_cache = {d.dt_title: d.name for d in demographics_list if d.dt_title}

            # Evitar fallos si dt_title está vacío
            for d in demographics_list:
                if d.name not in demographic_cache:
                    demographic_cache[d.name] = d.name

            def get_or_create_demographic(demo_name):
                if not demo_name: 
                    return None
                demo_name = str(demo_name).strip()
                
                # Buscar en caché por dt_title
                if demo_name in demographic_cache:
                    return demographic_cache[demo_name]
                
                # Buscar en base de datos si fue creado sin caché activo
                existing = frappe.db.exists('qp_IQ_DemographicType', {'dt_title': demo_name})
                if existing:
                    demographic_cache[demo_name] = existing
                    return existing

                try:
                    doc = frappe.get_doc({
                        'doctype': 'qp_IQ_DemographicType',
                        'dt_title': demo_name,
                        'dt_object_type': 'Contacto',
                        'dt_creator_company': company
                    })
                    
                    doc.flags.ignore_mandatory = True
                    doc.insert(ignore_permissions=True)
                    
                    demographic_cache[demo_name] = doc.name # Añadir al caché
                    return doc.name
                except Exception:
                    frappe.log_error(frappe.get_traceback(), f"Error creando demográfico {demo_name} - Migración {self.name}")
                    return demo_name

            question_map = {}
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

            default_q_type = frappe.db.get_value('qp_IQ_QuestionType', {'qnt_mnemonico': 'scale_likert'}, 'name')
            if not default_q_type:
                default_q_type = frappe.db.get_value('qp_IQ_QuestionType', None, 'name')

            # Si es medición de Engagement, se garantiza el tipo de pregunta Likert
            final_q_type = default_q_type
            if is_engagement_template:
                likert_type = frappe.db.get_value('qp_IQ_QuestionType', {'qnt_mnemonico': 'scale_likert'}, 'name')
                if likert_type:
                    final_q_type = likert_type

            # Optimización de caché para preguntas existentes de la compañía
            company_questions = frappe.db.get_all('qp_IQ_Question', filters={'qn_owner': company}, fields=['name', 'qn_statement'])
            question_cache = {q.qn_statement: q.name for q in company_questions if q.qn_statement}

            for topic_val, dimension, statement in unique_questions:
                if base_template_id and statement in existing_template_qs:
                    question_map[statement] = existing_template_qs[statement]
                    continue
                
                # Búsqueda en el caché de memoria en lugar de llamadas a la base de datos
                if statement in question_cache:
                    question_map[statement] = question_cache[statement]
                else:
                    topic_id = get_or_create_demographic(topic_val) if topic_val else None
                    dim_id = get_or_create_demographic(dimension) if dimension else None
                    
                    new_q = frappe.get_doc({
                        'doctype': 'qp_IQ_Question',
                        'qn_statement': statement,
                        'qn_owner': company,
                        'qp_topic': topic_id,
                        'qn_demographic': dim_id,
                        'qn_type': final_q_type,
                        'qn_creator': creator_contact
                    })
                    new_q.flags.ignore_mandatory = True
                    new_q.insert(ignore_permissions=True)
                    
                    question_map[statement] = new_q.name
                    question_cache[statement] = new_q.name

            clean_survey_id = str(self.hm_survey_id or self.name).replace("ObjectId(", "").replace(")", "").strip()

            # Forzar el uso de la plantilla original sin generar nuevas plantillas
            final_template_id = base_template_id

            status_doc_name = None
            # Consultar por el estado 'Finalizada' en qp_IQ_SurveyStatus
            for field in ['se_status', 'name']:
                try:
                    status_doc_name = frappe.db.get_value('qp_IQ_SurveyStatus', {field: ['like', '%Finalizada%']}, 'name')
                    if status_doc_name:
                        break
                except Exception:
                    continue
            
            if not status_doc_name:
                fallback_status = frappe.db.get_list('qp_IQ_SurveyStatus', limit_page_length=1)
                status_doc_name = fallback_status[0].name if fallback_status else 'Finalizada'

            survey_name_label = f"Medición Migrada - {clean_survey_id}"
            
            # Creación en qp_IQ_Survey
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
            
            # Garantizar que no quede en Draft si el documento admite envios/submissions
            try:
                if new_survey.meta.is_submittable:
                    new_survey.submit()
            except Exception:
                pass
                
            real_survey_id = new_survey.name

            # Creación directa en DocType Survey
            new_core_survey = frappe.get_doc({
                'doctype': 'Survey',
                'name': survey_name_label,
                'title': survey_name_label,
                'sub_title': f'Migración Histórica generada para {company}',
                'custom_iq_survey': real_survey_id
            })
            new_core_survey.flags.ignore_mandatory = True
            new_core_survey.insert(ignore_permissions=True)
            
            try:
                if new_core_survey.meta.is_submittable:
                    new_core_survey.submit()
            except Exception:
                pass

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
                
                for stmt, resp in data['responses'].items():
                    q_id = question_map.get(stmt)
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

                # Creación de registro en qp_IQ_SurveyHistoricData
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
                    # Crear o recuperar demográfico y obtener su ID
                    d_type_id = get_or_create_demographic(d_tag)

                    doc.append("shd_demographics", {
                        "cdh_demographic_type": d_type_id,
                        "cdh_tag": d_tag,
                        "cdh_value": d_val
                    })
                    
                doc.flags.ignore_mandatory = True
                doc.insert(ignore_permissions=True)
                processed_count += 1
                
                # Transacción segura cada 500 registros 
                # Para evitar saturación de memoria y asegurar persistencia
                if processed_count % 500 == 0:
                    frappe.db.commit()

            self.db_set('hm_status', 'Completado')
            self.db_set('hm_processed_records', processed_count)
            self.db_set('hm_survey_id', real_survey_id)
            self.db_set('hm_error_log', 'Migración completada exitosamente.')

        except Exception as e:
            frappe.db.rollback()
            error_trace = traceback.format_exc()
            frappe.log_error(frappe.get_traceback(), f"Error en process_migration - Migración {self.name}")
            
            self.db_set('hm_status', 'Fallido')
            self.db_set('hm_error_log', error_trace)

        finally:
            # Registro de duración de la migración
            end_time = time.time()
            duration_seconds = int(end_time - start_time)
            mins, secs = divmod(duration_seconds, 60)
            formatted_duration = f"{mins}m {secs}s"
            
            self.db_set('hm_duration', formatted_duration)
            frappe.db.commit()