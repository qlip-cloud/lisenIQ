import frappe
from frappe import _
import io, csv
from datetime import datetime
import re
import json
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

# Definición de columnas base (Orden lógico sugerido)
REQUIRED_COLUMNS = [
	"Nombre", "Apellido", "Tipo de Documento", "Número de Documento (DNI)",
	"País", "Idioma", "Estatus", "Género", 
	"Fecha de Nacimiento", "Nivel Académico", "Correo (Opcional)", 
	"Fecha de Ingreso"
]

# Campos que NO pueden estar vacíos para la validación estricta
MANDATORY_FIELDS = [
	"Nombre", 
	"Apellido", 
	"Tipo de Documento", 
	"Número de Documento (DNI)", 
	"País", 
	"Idioma"
]

# Lista fija de países LATAM
LATAM_COUNTRIES = [
	"Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica",
	"Cuba", "Dominican Republic", "Ecuador", "El Salvador", "Guatemala",
	"Honduras", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru",
	"Puerto Rico", "Uruguay", "Venezuela, Bolivarian Republic of"
]

def get_context(context):
	context.page_title = _("Carga masiva de Contactos")
	context.no_cache = 1
	context.no_breadcrumbs = True
	context.is_navbar_custom = True
	return context

def get_mapping_dicts():
	"""
	Retorna diccionarios para mapear ID -> Nombre (para exportar) 
	y Nombre -> ID (para importar).
	"""
	# Tipo de Documento: dt_name (Visible) <-> name (ID)
	doc_types = frappe.get_all("qp_IQ_DocumentType", fields=["name", "dt_name"])
	dt_id_to_name = {d.name: d.dt_name for d in doc_types}
	dt_name_to_id = {d.dt_name: d.name for d in doc_types}

	# Idioma: la_name (Visible) <-> name (ID)
	langs = frappe.get_all("qp_IQ_Language", fields=["name", "la_name"])
	lang_id_to_name = {d.name: d.la_name for d in langs}
	lang_name_to_id = {d.la_name: d.name for d in langs}

	# País: country_name (Visible) <-> name (ID)
	countries = frappe.get_all("Country", fields=["name", "country_name"])
	country_id_to_name = {d.name: d.country_name for d in countries}
	country_name_to_id = {d.country_name: d.name for d in countries}

	# Nivel Académico: al_title (Visible) <-> name (ID)
	academics = frappe.get_all("qp_IQ_AcademicLevel", fields=["name", "al_title"])
	academic_id_to_name = {d.name: d.al_title for d in academics}
	academic_name_to_id = {d.al_title: d.name for d in academics}

	return {
		"dt_export": dt_id_to_name, "dt_import": dt_name_to_id,
		"lang_export": lang_id_to_name, "lang_import": lang_name_to_id,
		"country_export": country_id_to_name, "country_import": country_name_to_id,
		"academic_export": academic_id_to_name, "academic_import": academic_name_to_id
	}

@frappe.whitelist(allow_guest=False)
def get_contacts_for_grid():
	try:
		user = frappe.session.user
		contact_info = frappe.db.get_value(
			"Contact", 
			{"user": user, "custom_is_liseniq_contact": 0}, 
			["name", "custom_company"], 
			as_dict=True
		)
		
		if not contact_info or not contact_info.custom_company:
			return {"rows": [], "max_demographics": 1}

		user_company = contact_info.custom_company
		
		contacts = frappe.get_all("Contact", 
			filters={
				"custom_company": user_company, 
				"custom_is_liseniq_contact": 1
			},
			fields=[
				"name", "first_name", "last_name", "gender", "custom_dob",
				"custom_country", "custom_document_type", "custom_document_number",
				"custom_academic_level", "custom_entry_date", "custom_status",
				"custom_language"
			],
			order_by="first_name asc"
		)

		maps = get_mapping_dicts()
		grid_rows = []
		max_demos = 1
		
		for c in contacts:
			email = frappe.db.get_value("Contact Email", {"parent": c.name, "is_primary": 1}, "email_id")
			
			demographics = frappe.get_all("qp_IQ_ContactAdditionalDetail", 
				filters={"parent": c.name},
				fields=["cad_tag", "cad_value"]
			)
			
			if len(demographics) > max_demos:
				max_demos = len(demographics)

			tipo_doc_label = maps["dt_export"].get(c.custom_document_type, c.custom_document_type)
			pais_label = maps["country_export"].get(c.custom_country, c.custom_country)
			idioma_label = maps["lang_export"].get(c.custom_language, c.custom_language)
			academic_label = maps["academic_export"].get(c.custom_academic_level, c.custom_academic_level)

			row = {
				"Nombre": c.first_name,
				"Apellido": c.last_name,
				"Tipo de Documento": tipo_doc_label or "",
				"Número de Documento (DNI)": c.custom_document_number,
				"País": pais_label or "",
				"Idioma": idioma_label or "",
				"Estatus": c.custom_status,
				"Género": c.gender,
				"Fecha de Nacimiento": str(c.custom_dob) if c.custom_dob else "",
				"Nivel Académico": academic_label or "",
				"Correo (Opcional)": email or "",
				"Fecha de Ingreso": str(c.custom_entry_date) if c.custom_entry_date else ""
			}
			
			for i, demo in enumerate(demographics):
				idx = i + 1
				row[f"Demográfico_{idx}"] = demo.cad_tag
				row[f"Dato_{idx}"] = demo.cad_value

			if not demographics:
				row["Demográfico_1"] = ""
				row["Dato_1"] = ""

			grid_rows.append(row)

		return {"rows": grid_rows, "max_demographics": max_demos}

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "FATAL ERROR: get_contacts_for_grid")
		return {"rows": [], "max_demographics": 1}

@frappe.whitelist(allow_guest=False)
def download_template():
	try:
		from openpyxl import Workbook
		from openpyxl.styles import Font
		
		data_result = get_contacts_for_grid()
		rows = data_result.get("rows", [])
		max_demos = data_result.get("max_demographics", 1)

		wb = Workbook()
		ws = wb.active
		ws.title = "Plantilla Contactos"

		ws_opts = wb.create_sheet("Opciones")
		ws_opts.sheet_state = 'hidden' 

		doc_types_list = [d.dt_name for d in frappe.get_all("qp_IQ_DocumentType", fields=["dt_name"], order_by="dt_name asc")]
		langs_list = [d.la_name for d in frappe.get_all("qp_IQ_Language", fields=["la_name"], order_by="la_name asc")]
		genders_list = [d.gender for d in frappe.get_all("Gender", fields=["gender"], order_by="gender asc")]
		countries_list = sorted([c for c in LATAM_COUNTRIES])
		status_list = ["Activo", "Inactivo"]
		academic_levels_list = [d.al_title for d in frappe.get_all("qp_IQ_AcademicLevel", fields=["al_title"], order_by="al_title asc")]

		lists_map = [
			(doc_types_list, "A"),    
			(countries_list, "B"),    
			(langs_list, "C"),        
			(genders_list, "D"),      
			(status_list, "E"),       
			(academic_levels_list, "F") 
		]

		for data_list, col_letter in lists_map:
			for idx, val in enumerate(data_list, start=1):
				ws_opts[f"{col_letter}{idx}"] = val

		headers = list(REQUIRED_COLUMNS)
		for i, range_val in enumerate(range(1, max_demos + 1)):
			headers.append(f"Demográfico_{range_val}")
			headers.append(f"Dato_{range_val}")
		
		ws.append(headers)
		for cell in ws[1]:
			cell.font = Font(bold=True)

		def create_dv(formula):
			dv = DataValidation(type="list", formula1=formula, allow_blank=True)
			return dv

		dv_doctype = create_dv(f"'Opciones'!$A$1:$A${len(doc_types_list) or 1}")
		dv_country = create_dv(f"'Opciones'!$B$1:$B${len(countries_list) or 1}")
		dv_lang    = create_dv(f"'Opciones'!$C$1:$C${len(langs_list) or 1}")
		dv_gender  = create_dv(f"'Opciones'!$D$1:$D${len(genders_list) or 1}")
		dv_status  = create_dv(f"'Opciones'!$E$1:$E${len(status_list) or 1}")
		dv_academic = create_dv(f"'Opciones'!$F$1:$F${len(academic_levels_list) or 1}")

		ws.add_data_validation(dv_doctype)
		ws.add_data_validation(dv_country)
		ws.add_data_validation(dv_lang)
		ws.add_data_validation(dv_gender)
		ws.add_data_validation(dv_status)
		ws.add_data_validation(dv_academic)

		col_map = {name: i+1 for i, name in enumerate(REQUIRED_COLUMNS)}
		start_row = 2
		end_row = 1000

		if "Tipo de Documento" in col_map: dv_doctype.add(f"{get_column_letter(col_map['Tipo de Documento'])}{start_row}:{get_column_letter(col_map['Tipo de Documento'])}{end_row}")
		if "País" in col_map: dv_country.add(f"{get_column_letter(col_map['País'])}{start_row}:{get_column_letter(col_map['País'])}{end_row}")
		if "Idioma" in col_map: dv_lang.add(f"{get_column_letter(col_map['Idioma'])}{start_row}:{get_column_letter(col_map['Idioma'])}{end_row}")
		if "Género" in col_map: dv_gender.add(f"{get_column_letter(col_map['Género'])}{start_row}:{get_column_letter(col_map['Género'])}{end_row}")
		if "Estatus" in col_map: dv_status.add(f"{get_column_letter(col_map['Estatus'])}{start_row}:{get_column_letter(col_map['Estatus'])}{end_row}")
		if "Nivel Académico" in col_map: dv_academic.add(f"{get_column_letter(col_map['Nivel Académico'])}{start_row}:{get_column_letter(col_map['Nivel Académico'])}{end_row}")

		for r_dict in rows:
			row_values = []
			for col in REQUIRED_COLUMNS:
				val = r_dict.get(col, "")
				row_values.append(val)
			for i in range(1, max_demos + 1):
				row_values.append(r_dict.get(f"Demográfico_{i}", ""))
				row_values.append(r_dict.get(f"Dato_{i}", ""))
			ws.append(row_values)

		output = io.BytesIO()
		wb.save(output)
		output.seek(0)
		
		timestamp = frappe.utils.now_datetime().strftime("%Y%m%d_%H%M")
		frappe.local.response['filename'] = f"Plantilla_Contactos_{timestamp}.xlsx"
		frappe.local.response["filecontent"] = output.read()
		frappe.local.response["type"] = "download"

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "FATAL ERROR: download_template")
		frappe.throw(_("No se pudo generar la plantilla: {0}").format(e))

def check_if_modified(contact_doc, data, status):
	"""
	Compara el documento actual con los nuevos datos para ver si hay cambios reales.
	"""
	def norm(val): return str(val).strip() if val is not None else ""
	def norm_date(val): return str(val) if val else None

	# 1. Campos directos
	if norm(contact_doc.first_name) != norm(data['firstName']): return True
	if norm(contact_doc.last_name) != norm(data['lastName']): return True
	if norm(contact_doc.custom_document_type) != norm(data['docType']): return True
	if norm(contact_doc.custom_country) != norm(data['country']): return True
	if norm(contact_doc.custom_language) != norm(data['language']): return True
	if norm(contact_doc.custom_academic_level) != norm(data['education']): return True
	if norm(contact_doc.gender) != norm(data['gender']): return True
	if norm(contact_doc.custom_status) != norm(status): return True

	# 2. Fechas
	if norm_date(contact_doc.custom_dob) != str(data['birthdate']) if data['birthdate'] else None: return True
	if norm_date(contact_doc.custom_entry_date) != str(data['entryDate']) if data['entryDate'] else None: return True

	# 3. Email
	current_email = frappe.db.get_value("Contact Email", {"parent": contact_doc.name, "is_primary": 1}, "email_id")
	if norm(current_email) != norm(data['email']): return True

	# 4. Demográficos
	current_demos = frappe.get_all("qp_IQ_ContactAdditionalDetail", filters={"parent": contact_doc.name}, fields=["cad_tag", "cad_value"])
	current_set = set((norm(d.cad_tag), norm(d.cad_value)) for d in current_demos)
	new_set = set((norm(d['type']), norm(d['value'])) for d in data['demographics'])
	
	if current_set != new_set: return True

	return False

def update_contact_fields(contact_doc, data, status):
	"""Actualiza los campos del documento en memoria y guarda."""
	contact_doc.first_name = data['firstName']
	contact_doc.last_name = data['lastName']
	contact_doc.custom_document_type = data['docType']
	contact_doc.custom_country = data['country']
	contact_doc.custom_language = data['language']
	contact_doc.custom_academic_level = data['education']
	contact_doc.gender = data['gender']
	contact_doc.custom_dob = data['birthdate']
	contact_doc.custom_entry_date = data['entryDate']
	contact_doc.custom_status = status
	
	contact_doc.save(ignore_permissions=True)
	
	new_email = (data.get('email') or "").strip()
	if new_email:
		exists = False
		for email_row in contact_doc.email_ids:
			if email_row.is_primary:
				email_row.email_id = new_email
				exists = True
				break
		if not exists:
			contact_doc.append("email_ids", {"email_id": new_email, "is_primary": 1})
		contact_doc.save(ignore_permissions=True)
	
	frappe.db.sql("DELETE FROM `tabqp_IQ_ContactAdditionalDetail` WHERE parent = %s", contact_doc.name)
	for d in data['demographics']:
		if d['type'] and d['value']:
			child = contact_doc.append("custom_contact_additional_detail", {})
			child.cad_tag = d['type']
			child.cad_value = d['value']
	
	contact_doc.save(ignore_permissions=True)

def process_contacts_background(rows, user):
	"""
	Procesa los contactos en segundo plano.
	"""
	results = {"creados": 0, "actualizados": 0, "ignorados": 0, "errores": []}
	
	try:
		contact_info = frappe.db.get_value("Contact", {"user": user, "custom_is_liseniq_contact": 0}, ["name", "custom_company"], as_dict=True)
		if not contact_info or not contact_info.custom_company:
			frappe.log_error("No se pudo determinar la compañía del usuario", "Process Contacts Error")
			return

		user_company = contact_info.custom_company
		
		# Obtener mapas
		maps = get_mapping_dicts()
		dt_map = maps["dt_import"]
		country_map = maps["country_import"]
		lang_map = maps["lang_import"]
		academic_map = maps["academic_import"]

		def parse_date(value):
			if not value: return None
			try: return frappe.utils.getdate(value)
			except:
				try: return datetime.strptime(value, "%d/%m/%Y").date()
				except: return None

		for i, r in enumerate(rows, start=1):
			try:
				tipo_doc_raw = (r.get("Tipo de Documento") or "").strip()
				tipo_doc_id = dt_map.get(tipo_doc_raw, tipo_doc_raw)
				pais_raw = (r.get("País") or "").strip()
				pais_id = country_map.get(pais_raw, pais_raw)
				idioma_raw = (r.get("Idioma") or "").strip()
				idioma_id = lang_map.get(idioma_raw, idioma_raw)
				nivel_acad_raw = (r.get("Nivel Académico") or "").strip()
				nivel_acad_id = academic_map.get(nivel_acad_raw, nivel_acad_raw)
				
				nombre = (r.get("Nombre") or "").strip()
				apellido = (r.get("Apellido") or "").strip()
				numero_doc = (r.get("Número de Documento (DNI)") or "").strip()
				estatus = (r.get("Estatus") or "").strip()
				correo = (r.get("Correo (Opcional)") or "").strip()
				
				fecha_nac = parse_date(r.get("Fecha de Nacimiento"))
				fecha_ing = parse_date(r.get("Fecha de Ingreso"))
				
				# VALIDACIÓN FINAL DE BACKEND (Seguridad adicional)
				missing = []
				if not nombre: missing.append("Nombre")
				if not apellido: missing.append("Apellido")
				if not tipo_doc_id: missing.append("Tipo de Documento")
				if not numero_doc: missing.append("Número de Documento")
				if not pais_id: missing.append("País")
				if not idioma_id: missing.append("Idioma")
				
				if missing:
					raise Exception(f"Campos obligatorios faltantes: {', '.join(missing)}")

				data = {
					"firstName": nombre,
					"lastName": apellido,
					"docNumber": numero_doc,
					"docType": tipo_doc_id,
					"country": pais_id,
					"language": idioma_id,
					"email": correo,
					"gender": (r.get("Género") or "").strip(),
					"education": nivel_acad_id,
					"birthdate": fecha_nac,
					"entryDate": fecha_ing,
					"demographics": []
				}
				
				# Recolectar demográficos
				for key, val in r.items():
					if key.startswith("Demográfico_"):
						idx = key.split("_")[1]
						val_key = f"Dato_{idx}"
						d_val = (r.get(val_key) or "").strip()
						val_clean = (val or "").strip()
						if val_clean and d_val:
							data["demographics"].append({"type": val_clean, "value": d_val})

				contact_name = None
				if numero_doc:
					contact_name = frappe.db.get_value("Contact", {"custom_document_number": numero_doc, "custom_company": user_company}, "name")

				if contact_name:
					contact_doc = frappe.get_doc("Contact", contact_name)
					if check_if_modified(contact_doc, data, estatus or contact_doc.custom_status):
						update_contact_fields(contact_doc, data, estatus or contact_doc.custom_status)
						results["actualizados"] += 1
					else:
						results["ignorados"] += 1
				else:
					new_doc = frappe.new_doc("Contact")
					new_doc.first_name = nombre
					new_doc.last_name = apellido
					new_doc.custom_company = user_company
					new_doc.custom_document_number = numero_doc
					new_doc.custom_document_type = tipo_doc_id
					new_doc.custom_country = pais_id
					new_doc.custom_language = idioma_id
					new_doc.custom_academic_level = nivel_acad_id
					new_doc.custom_status = estatus or "Activo"
					new_doc.custom_is_liseniq_contact = 1
					
					new_doc.custom_dob = data['birthdate']
					new_doc.custom_entry_date = data['entryDate']
					new_doc.gender = data['gender']

					if correo:
						new_doc.append("email_ids", {"email_id": correo, "is_primary": 1})
					
					for d in data['demographics']:
						child = new_doc.append("custom_contact_additional_detail", {})
						child.cad_tag = d['type']
						child.cad_value = d['value']
						
					new_doc.insert(ignore_permissions=True)
					results["creados"] += 1

			except Exception as e:
				# Log error específico para trazabilidad
				frappe.log_error(frappe.get_traceback(), f"Error procesando fila {i} en carga masiva")
				results["errores"].append({"fila": i, "error": str(e)})

		# Notificar al usuario al finalizar
		msg = f"""
			<b>Carga masiva finalizada</b><br>
			Creados: {results['creados']}<br>
			Actualizados: {results['actualizados']}<br>
			Sin cambios: {results['ignorados']}<br>
			Errores: {len(results['errores'])}
		"""
		frappe.publish_realtime('msgprint', msg, user=user)

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "FATAL ERROR: process_contacts_background")
		frappe.publish_realtime('msgprint', f"Error fatal en carga de contactos en segundo plano: {str(e)}", user=user)


@frappe.whitelist(allow_guest=False)
def upload_contacts():
	if not frappe.request: frappe.throw(_("No hay request disponible"))
	fileobj = frappe.local.request.files.get('file')
	if not fileobj: frappe.throw(_("No se envió ningún archivo"))

	filename = fileobj.filename or ""
	ext = filename.split('.')[-1].lower()
	rows = []
	try:
		if ext in ("xlsx", "xls"):
			from openpyxl import load_workbook
			wb = load_workbook(fileobj, read_only=True, data_only=True)
			if "Plantilla Contactos" in wb.sheetnames: ws = wb["Plantilla Contactos"]
			else: ws = wb.active
			for r in ws.iter_rows(values_only=True):
				rows.append([None if v is None else str(v).strip() for v in r])
		elif ext == "csv":
			content = fileobj.read()
			if isinstance(content, bytes): content = content.decode('utf-8-sig')
			reader = csv.reader(io.StringIO(content))
			for r in reader:
				rows.append([None if v is None else v.strip() for v in r])
		else: frappe.throw(_("Tipo de archivo no soportado"))
	except Exception as e: frappe.throw(_("Error al leer archivo: {0}").format(e))

	if not rows or len(rows) < 1: frappe.throw(_("Archivo vacío"))

	headers = [h.strip() if h else "" for h in rows[0]]
	idx = {h: i for i, h in enumerate(headers)}
	
	if "Nombre" not in idx or "Apellido" not in idx:
		frappe.throw(_("Faltan columnas obligatorias (Nombre, Apellido)"))

	# Convertir a lista de diccionarios para el worker
	def get_val(r, col):
		if col not in idx: return ""
		i = idx[col]
		return str(r[i]).strip() if i < len(r) and r[i] else ""
	
	rows_dicts = []
	for i, r in enumerate(rows[1:], start=2):
		if not any(cell for cell in r): continue
		row_dict = {}
		for h in headers:
			row_dict[h] = get_val(r, h)
		rows_dicts.append(row_dict)

	# Encolar proceso ASÍNCRONO
	frappe.enqueue(
		method=process_contacts_background,
		queue='long',
		timeout=3600,
		rows=rows_dicts,
		user=frappe.session.user
	)
	
	# Retornar conteo inmediato
	return {"message": {"total_rows": len(rows_dicts), "queued": True}, "status": "queued"}


@frappe.whitelist(allow_guest=False)
def validate_contacts():
	if not frappe.request: frappe.throw(_("No hay request disponible"))
	fileobj = frappe.local.request.files.get('file')
	if not fileobj: frappe.throw(_("Error de validación: No se detectó ningún archivo adjunto. Si está en modo 'Editar en línea', esto no debería ocurrir."))

	filename = fileobj.filename or ""
	ext = filename.split('.')[-1].lower()
	rows = []
	try:
		if ext in ("xlsx", "xls"):
			from openpyxl import load_workbook
			wb = load_workbook(fileobj, read_only=True, data_only=True)
			if "Plantilla Contactos" in wb.sheetnames: ws = wb["Plantilla Contactos"]
			else: ws = wb.active
			for r in ws.iter_rows(values_only=True):
				rows.append([None if v is None else str(v).strip() for v in r])
		elif ext == "csv":
			content = fileobj.read()
			if isinstance(content, bytes): content = content.decode('utf-8-sig')
			reader = csv.reader(io.StringIO(content))
			for r in reader:
				rows.append([None if v is None else v.strip() for v in r])
	except Exception as e: return {"ok": False, "error": f"Error leyendo archivo: {str(e)}"}

	if not rows: return {"ok": False, "error": "El archivo está vacío"}

	headers = [h.strip() if h else "" for h in rows[0]]
	idx = {h: i for i, h in enumerate(headers)}
	parsed = []
	errors = []

	def get_val(r, col):
		if col not in idx: return ""
		i = idx[col]
		return str(r[i]).strip() if i < len(r) and r[i] else ""
	
	for i, r in enumerate(rows[1:], start=2):
		if not any(cell for cell in r): continue
		row_dict = {}
		for h in headers:
			val = get_val(r, h)
			row_dict[h] = val
		
		# VALIDACIÓN ESTRICTA
		# Se revisa que todos los campos mandatorios tengan valor
		row_errors = []
		for field in MANDATORY_FIELDS:
			if not row_dict.get(field):
				row_errors.append(field)

		parsed.append(row_dict)
		if row_errors: 
			errors.append({"fila": i, "errores": row_errors})

	return {"ok": True, "headers": headers, "rows": parsed, "errors": errors}

@frappe.whitelist(allow_guest=False)
def upload_contacts_json(rows_json):
	import json as _json
	try: rows = _json.loads(rows_json)
	except: frappe.throw(_("JSON inválido"))

	# Encolar proceso ASÍNCRONO
	frappe.enqueue(
		method=process_contacts_background,
		queue='long',
		timeout=3600,
		rows=rows,
		user=frappe.session.user
	)
	
	# Retornar conteo inmediato
	return {"message": {"total_rows": len(rows), "queued": True}, "status": "queued"}