import frappe
from frappe import _
import io, csv
from datetime import datetime
import re
import json

REQUIRED_COLUMNS = [
	"Nombre", "Apellido", "Género", "Fecha de Nacimiento", "País Lenguaje",
	"Tipo de Documento", "Número de Documento (DNI)", "Nivel Académico",
	"Correo (Opcional)", "Compañía", "Fecha de Ingreso", "Estatus",
	"Nombre de Demográfico", "Valor de Demográfico"
]

def get_context(context):
	# Página simple para la carga masiva
	context.page_title = _("Carga masiva de Contactos")
	context.no_cache = 1
	context.no_breadcrumbs = True
	context.is_navbar_custom = True
	return context

@frappe.whitelist(allow_guest=False)
def get_contacts_for_grid():
	"""
	Obtiene los contactos existentes del usuario/compañía y los formatea
	como una lista de diccionarios plana, compatible con las columnas de la grid.
	"""
	try:
		# Obtener compañía del usuario logueado
		contact_info = frappe.db.get_value("Contact", {"user": frappe.session.user, "custom_is_liseniq_contact": 0}, ["name", "custom_company"], as_dict=True)
		
		if not contact_info or not contact_info.custom_company:
			return []

		user_company = contact_info.custom_company
		
		# Obtener contactos de la compañía (liseniq contacts)
		contacts = frappe.get_all("Contact", 
			filters={
				"custom_company": user_company, 
				"custom_is_liseniq_contact": 1
			},
			fields=[
				"name", "first_name", "last_name", "gender", "custom_dob",
				"custom_country", "custom_document_type", "custom_document_number",
				"custom_academic_level", "custom_entry_date", "custom_status"
			]
		)

		grid_rows = []
		
		for c in contacts:
			# Obtener email primario
			email = frappe.db.get_value("Contact Email", {"parent": c.name, "is_primary": 1}, "email_id")
			
			# Obtener demográficos (tomamos el primero si hay varios para simplificar la vista plana,
			# o podríamos generar múltiples filas si fuera necesario, pero para edición simple una fila por contacto es mejor)
			# Nota: Si se requiere editar múltiples demográficos, el usuario puede agregar filas duplicadas con distinto demográfico.
			demographics = frappe.get_all("qp_IQ_ContactAdditionalDetail", 
				filters={"parent": c.name},
				fields=["cad_tag", "cad_value"]
			)
			
			base_row = {
				"Nombre": c.first_name,
				"Apellido": c.last_name,
				"Género": c.gender,
				"Fecha de Nacimiento": str(c.custom_dob) if c.custom_dob else "",
				"País Lenguaje": c.custom_country,
				"Tipo de Documento": c.custom_document_type,
				"Número de Documento (DNI)": c.custom_document_number,
				"Nivel Académico": c.custom_academic_level,
				"Correo (Opcional)": email or "",
				"Fecha de Ingreso": str(c.custom_entry_date) if c.custom_entry_date else "",
				"Estatus": c.custom_status,
				"Nombre de Demográfico": "",
				"Valor de Demográfico": ""
			}
			
			if demographics:
				# Si hay demográficos, creamos una fila por cada uno (estilo CSV plano)
				# OJO: Esto puede duplicar visualmente al contacto.
				# Para la edición en línea simple, vamos a mostrar solo el primero en la misma fila,
				# y si hay más, añadimos filas.
				for i, demo in enumerate(demographics):
					if i == 0:
						row = base_row.copy()
						row["Nombre de Demográfico"] = demo.cad_tag
						row["Valor de Demográfico"] = demo.cad_value
						grid_rows.append(row)
					else:
						# Filas adicionales solo con la info clave y el demográfico
						row = base_row.copy()
						row["Nombre de Demográfico"] = demo.cad_tag
						row["Valor de Demográfico"] = demo.cad_value
						grid_rows.append(row)
			else:
				grid_rows.append(base_row)

		return grid_rows

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "contacts_import.get_contacts_for_grid")
		return []

@frappe.whitelist(allow_guest=False)
def download_template():
	"""
	Genera y devuelve plantilla .xlsx con encabezados.
	"""
	try:
		from openpyxl import Workbook
		wb = Workbook()
		ws = wb.active
		ws.append(REQUIRED_COLUMNS)
		output = io.BytesIO()
		wb.save(output)
		output.seek(0)
		frappe.local.response['filename'] = "plantilla_contactos.xlsx"
		frappe.local.response["filecontent"] = output.read()
		frappe.local.response["type"] = "download"
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "contacts_import.download_template")
		frappe.throw(_("No se pudo generar la plantilla: {0}").format(e))

@frappe.whitelist(allow_guest=False)
def upload_contacts():
	"""
	Recibe archivo (.xlsx o .csv) en request.files['file'], valida y crea/actualiza contactos.
	Retorna resumen: creados, actualizados, errores.
	"""
	if not frappe.request:
		frappe.throw(_("No hay request disponible"))
	fileobj = frappe.local.request.files.get('file')
	if not fileobj:
		frappe.throw(_("No se envió ningún archivo"))

	filename = fileobj.filename or ""
	ext = filename.split('.')[-1].lower()

	# Leer filas
	rows = []
	try:
		if ext in ("xlsx", "xls"):
			from openpyxl import load_workbook
			wb = load_workbook(fileobj, read_only=True, data_only=True)
			ws = wb.active
			for r in ws.iter_rows(values_only=True):
				rows.append([None if v is None else str(v).strip() for v in r])
		elif ext == "csv":
			content = fileobj.read()
			if isinstance(content, bytes):
				content = content.decode('utf-8-sig')
			reader = csv.reader(io.StringIO(content))
			for r in reader:
				rows.append([None if v is None else v.strip() for v in r])
		else:
			frappe.throw(_("Tipo de archivo no soportado: {0}").format(ext))
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "contacts_import.upload_contacts.read")
		frappe.throw(_("Error al leer el archivo: {0}").format(e))

	if not rows or len(rows) < 1:
		frappe.throw(_("El archivo está vacío o no tiene filas"))

	headers = [h.strip() if h else "" for h in rows[0]]
	missing = [c for c in REQUIRED_COLUMNS if c not in headers]
	if missing:
		frappe.throw(_("Faltan columnas obligatorias: {0}").format(", ".join(missing)))

	idx = {h: i for i, h in enumerate(headers)}
	results = {"creados": 0, "actualizados": 0, "errores": []}

	# obtener compañía por defecto del usuario logueado (según estándar del módulo)
	user_company = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
	if not user_company:
		frappe.throw(_("No se pudo determinar la compañía del usuario logueado."))

	# importar funciones utilitarias del módulo de contactos existente
	try:
		from liseniq.www.contacts import index as contacts_index
	except Exception:
		contacts_index = None

	def get_cell(row, colname):
		i = idx.get(colname)
		return (row[i].strip() if i is not None and i < len(row) and row[i] is not None else "") if row else ""

	def parse_date(value):
		if not value:
			return None
		try:
			# intentar formato ISO o dd/mm/yyyy
			return frappe.utils.getdate(value)
		except Exception:
			try:
				return datetime.strptime(value, "%d/%m/%Y").date()
			except Exception:
				return None

	for i, r in enumerate(rows[1:], start=2):
		if not any(cell for cell in r):
			continue
		try:
			nombre = get_cell(r, "Nombre")
			apellido = get_cell(r, "Apellido")
			genero = get_cell(r, "Género")
			fecha_nac = parse_date(get_cell(r, "Fecha de Nacimiento"))
			pais_leng = get_cell(r, "País Lenguaje")
			tipo_doc = get_cell(r, "Tipo de Documento")
			numero_doc = get_cell(r, "Número de Documento (DNI)")
			nivel_acad = get_cell(r, "Nivel Académico")
			correo = get_cell(r, "Correo (Opcional)")
			# compañía en plantilla será ignorada y se usa la compañía del usuario logueado
			fecha_ingreso = parse_date(get_cell(r, "Fecha de Ingreso"))
			estatus = get_cell(r, "Estatus")
			nombre_demo = get_cell(r, "Nombre de Demográfico")
			valor_demo = get_cell(r, "Valor de Demográfico")

			# preparar payload compatible con _map_contact_data
			data = {
				"firstName": nombre,
				"lastName": apellido,
				"gender": genero,
				"birthdate": fecha_nac.isoformat() if fecha_nac else None,
				"country": pais_leng,
				"docType": tipo_doc,
				"docNumber": numero_doc,
				"education": nivel_acad,
				"email": correo,
				"entryDate": fecha_ingreso.isoformat() if fecha_ingreso else None,
				"custom_is_liseniq_contact": 1,
				"demographics": []
			}
			if nombre_demo and valor_demo:
				data["demographics"].append({"type": nombre_demo, "value": valor_demo})

			# buscar por documento + compañía del usuario
			contact_name = None
			if numero_doc:
				contact_name = frappe.db.get_value("Contact", {"custom_document_number": numero_doc, "custom_company": user_company}, "name")

			# si existe actualizar
			if contact_name:
				contact_doc = frappe.get_doc("Contact", contact_name)
				# reutilizar mapeo del módulo existente cuando esté disponible
				if contacts_index and hasattr(contacts_index, "_map_contact_data"):
					contacts_index._map_contact_data(contact_doc, data)
				else:
					# mapeo básico si util no disponible
					contact_doc.first_name = nombre or contact_doc.first_name
					contact_doc.last_name = apellido or contact_doc.last_name
					contact_doc.gender = genero or contact_doc.gender
					contact_doc.custom_dob = data.get("birthdate") or contact_doc.get("custom_dob")
					contact_doc.custom_country = pais_leng or contact_doc.get("custom_country")
					contact_doc.custom_language = pais_leng or contact_doc.get("custom_language")
					contact_doc.custom_academic_level = nivel_acad or contact_doc.get("custom_academic_level")
					if correo:
						# reemplazar email primario
						contact_doc.email_ids = []
						contact_doc.append("email_ids", {"email_id": correo, "is_primary": 1})
					contact_doc.custom_entry_date = data.get("entryDate") or contact_doc.get("custom_entry_date")
					contact_doc.custom_status = estatus or contact_doc.get("custom_status")
				contact_doc.save(ignore_permissions=True)
				results["actualizados"] += 1
			else:
				# crear nuevo contacto
				new_doc = frappe.new_doc("Contact")
				# valor por defecto
				new_doc.custom_status = estatus or "Activo"
				if contacts_index and hasattr(contacts_index, "_map_contact_data"):
					contacts_index._map_contact_data(new_doc, data)
				else:
					new_doc.first_name = nombre
					new_doc.last_name = apellido
					new_doc.gender = genero
					new_doc.custom_dob = data.get("birthdate")
					new_doc.custom_country = pais_leng
					new_doc.custom_language = pais_leng
					new_doc.custom_document_type = tipo_doc
					new_doc.custom_document_number = numero_doc
					new_doc.custom_academic_level = nivel_acad
					new_doc.custom_entry_date = data.get("entryDate")
					new_doc.custom_is_liseniq_contact = 1
					if correo:
						new_doc.append("email_ids", {"email_id": correo, "is_primary": 1})
					# demographics handled by _map_contact_data ideally
					if nombre_demo and valor_demo:
						if contacts_index and hasattr(contacts_index, "find_or_create_demographic_type"):
							dt_name = contacts_index.find_or_create_demographic_type(nombre_demo)
							if dt_name:
								new_doc.append("custom_additional_details", {
									"cad_demographic_type": dt_name,
									"cad_tag": nombre_demo,
									"cad_value": valor_demo
								})
				new_doc.insert(ignore_permissions=True)
				results["creados"] += 1
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "contacts_import.process_row")
			results["errores"].append({"fila": i, "error": str(e)})

	return results

@frappe.whitelist(allow_guest=False)
def validate_contacts():
	"""
	Recibe archivo (.xlsx/.csv) en request.files['file'], parsea y valida las filas.
	No modifica la base de datos. Retorna headers, filas (lista de dict) y errores por fila.
	"""
	if not frappe.request:
		frappe.throw(_("No hay request disponible"))
	fileobj = frappe.local.request.files.get('file')
	if not fileobj:
		frappe.throw(_("No se envió ningún archivo"))

	filename = fileobj.filename or ""
	ext = filename.split('.')[-1].lower()

	# Leer filas (igual que upload_contacts, pero sólo parseo)
	rows = []
	try:
		if ext in ("xlsx", "xls"):
			from openpyxl import load_workbook
			wb = load_workbook(fileobj, read_only=True, data_only=True)
			ws = wb.active
			for r in ws.iter_rows(values_only=True):
				rows.append([None if v is None else str(v).strip() for v in r])
		elif ext == "csv":
			content = fileobj.read()
			if isinstance(content, bytes):
				content = content.decode('utf-8-sig')
			reader = csv.reader(io.StringIO(content))
			for r in reader:
				rows.append([None if v is None else v.strip() for v in r])
		else:
			frappe.throw(_("Tipo de archivo no soportado: {0}").format(ext))
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "contacts_import.validate_contacts.read")
		frappe.throw(_("Error al leer el archivo: {0}").format(e))

	if not rows or len(rows) < 1:
		frappe.throw(_("El archivo está vacío o no tiene filas"))

	headers = [h.strip() if h else "" for h in rows[0]]
	missing = [c for c in REQUIRED_COLUMNS if c not in headers]
	if missing:
		return {"ok": False, "error": _("Faltan columnas obligatorias: {0}").format(", ".join(missing))}

	idx = {h: i for i, h in enumerate(headers)}
	parsed = []
	errors = []

	email_regex = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

	def get_cell(row, colname):
		i = idx.get(colname)
		return (row[i].strip() if i is not None and i < len(row) and row[i] is not None else "") if row else ""

	def try_parse_date(value):
		if not value:
			return None
		try:
			return frappe.utils.getdate(value)
		except Exception:
			try:
				return datetime.strptime(value, "%d/%m/%Y").date()
			except Exception:
				return None

	for i, r in enumerate(rows[1:], start=2):
		# skip empty
		if not any(cell for cell in r):
			continue
		row_dict = {h: (r[idx[h]] if idx.get(h) is not None and idx[h] < len(r) and r[idx[h]] is not None else "") for h in headers}
		row_errors = []
		# validaciones básicas por fila
		if not (row_dict.get("Nombre") or "").strip():
			row_errors.append("Nombre faltante")
		if not (row_dict.get("Apellido") or "").strip():
			row_errors.append("Apellido faltante")
		if not (row_dict.get("Número de Documento (DNI)") or "").strip():
			row_errors.append("Número de Documento (DNI) faltante")
		# correo opcional validación
		correo = (row_dict.get("Correo (Opcional)") or "").strip()
		if correo and not email_regex.match(correo):
			row_errors.append("Formato de correo inválido")
		# fecha validación
		fn = try_parse_date(row_dict.get("Fecha de Nacimiento"))
		fi = try_parse_date(row_dict.get("Fecha de Ingreso"))
		if row_dict.get("Fecha de Nacimiento") and not fn:
			row_errors.append("Fecha de Nacimiento inválida (esperado ISO o dd/mm/yyyy)")
		if row_dict.get("Fecha de Ingreso") and not fi:
			row_errors.append("Fecha de Ingreso inválida (esperado ISO o dd/mm/yyyy)")

		parsed.append(row_dict)
		if row_errors:
			errors.append({"fila": i, "errores": row_errors})

	return {"ok": True, "headers": headers, "rows": parsed, "errors": errors}


@frappe.whitelist(allow_guest=False)
def upload_contacts_json(rows_json):
	"""
	Recibe JSON con una lista de filas (cada fila es dict header->value).
	Procesa creación/actualización de Contact usando la lógica existente.
	"""
	try:
		import json as _json
		rows = _json.loads(rows_json)
	except Exception:
		frappe.throw(_("Payload inválido"))

	results = {"creados": 0, "actualizados": 0, "errores": []}

	# obtener compañía por defecto del usuario logueado
	user_company = frappe.db.get_value("Contact", {"user": frappe.session.user}, "custom_company")
	if not user_company:
		frappe.throw(_("No se pudo determinar la compañía del usuario logueado."))

	# importar utilidades del módulo existente
	try:
		from liseniq.www.contacts import index as contacts_index
	except Exception:
		contacts_index = None

	def parse_date(value):
		if not value:
			return None
		try:
			return frappe.utils.getdate(value)
		except Exception:
			try:
				return datetime.strptime(value, "%d/%m/%Y").date()
			except Exception:
				return None

	for i, r in enumerate(rows, start=1):
		try:
			nombre = (r.get("Nombre") or "").strip()
			apellido = (r.get("Apellido") or "").strip()
			genero = (r.get("Género") or "").strip()
			fecha_nac = parse_date(r.get("Fecha de Nacimiento"))
			pais_leng = (r.get("País Lenguaje") or "").strip()
			tipo_doc = (r.get("Tipo de Documento") or "").strip()
			numero_doc = (r.get("Número de Documento (DNI)") or "").strip()
			nivel_acad = (r.get("Nivel Académico") or "").strip()
			correo = (r.get("Correo (Opcional)") or "").strip()
			fecha_ingreso = parse_date(r.get("Fecha de Ingreso"))
			estatus = (r.get("Estatus") or "").strip()
			nombre_demo = (r.get("Nombre de Demográfico") or "").strip()
			valor_demo = (r.get("Valor de Demográfico") or "").strip()

			data = {
				"firstName": nombre,
				"lastName": apellido,
				"gender": genero,
				"birthdate": fecha_nac.isoformat() if fecha_nac else None,
				"country": pais_leng,
				"docType": tipo_doc,
				"docNumber": numero_doc,
				"education": nivel_acad,
				"email": correo,
				"entryDate": fecha_ingreso.isoformat() if fecha_ingreso else None,
				"custom_is_liseniq_contact": 1,
				"demographics": []
			}
			if nombre_demo and valor_demo:
				data["demographics"].append({"type": nombre_demo, "value": valor_demo})

			contact_name = None
			if numero_doc:
				contact_name = frappe.db.get_value("Contact", {"custom_document_number": numero_doc, "custom_company": user_company}, "name")

			if contact_name:
				contact_doc = frappe.get_doc("Contact", contact_name)
				if contacts_index and hasattr(contacts_index, "_map_contact_data"):
					contacts_index._map_contact_data(contact_doc, data)
				else:
					contact_doc.first_name = nombre or contact_doc.first_name
					contact_doc.last_name = apellido or contact_doc.last_name
					contact_doc.gender = genero or contact_doc.gender
					contact_doc.custom_dob = data.get("birthdate") or contact_doc.get("custom_dob")
					contact_doc.custom_country = pais_leng or contact_doc.get("custom_country")
					contact_doc.custom_language = pais_leng or contact_doc.get("custom_language")
					contact_doc.custom_academic_level = nivel_acad or contact_doc.get("custom_academic_level")
					if correo:
						contact_doc.email_ids = []
						contact_doc.append("email_ids", {"email_id": correo, "is_primary": 1})
					contact_doc.custom_entry_date = data.get("entryDate") or contact_doc.get("custom_entry_date")
					contact_doc.custom_status = estatus or contact_doc.get("custom_status")
				contact_doc.save(ignore_permissions=True)
				results["actualizados"] += 1
			else:
				new_doc = frappe.new_doc("Contact")
				new_doc.custom_status = estatus or "Activo"
				if contacts_index and hasattr(contacts_index, "_map_contact_data"):
					contacts_index._map_contact_data(new_doc, data)
				else:
					new_doc.first_name = nombre
					new_doc.last_name = apellido
					new_doc.gender = genero
					new_doc.custom_dob = data.get("birthdate")
					new_doc.custom_country = pais_leng
					new_doc.custom_language = pais_leng
					new_doc.custom_document_type = tipo_doc
					new_doc.custom_document_number = numero_doc
					new_doc.custom_academic_level = nivel_acad
					new_doc.custom_entry_date = data.get("entryDate")
					new_doc.custom_is_liseniq_contact = 1
					if correo:
						new_doc.append("email_ids", {"email_id": correo, "is_primary": 1})
					if nombre_demo and valor_demo:
						if contacts_index and hasattr(contacts_index, "find_or_create_demographic_type"):
							dt_name = contacts_index.find_or_create_demographic_type(nombre_demo)
							if dt_name:
								new_doc.append("custom_additional_details", {
									"cad_demographic_type": dt_name,
									"cad_tag": nombre_demo,
									"cad_value": valor_demo
								})
				new_doc.insert(ignore_permissions=True)
				results["creados"] += 1
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), "contacts_import.upload_contacts_json.process_row")
			results["errores"].append({"fila": i, "error": str(e)})

	return results