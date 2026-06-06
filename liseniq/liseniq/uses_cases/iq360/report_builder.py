import json

import frappe
from collections import defaultdict
from liseniq.liseniq.uses_cases.iq360.selectors import  get_all_responses_for_survey, get_survey_questions, get_question_text_and_category, get_leader_evaluators
from liseniq.liseniq.uses_cases.iq360.calculations import normalize_responses, average, std_dev, _round2
"""
qp_IQ_LeaderReport- DocType to store the report for each leader based on the survey responses. 
Fields:
- Líder evaluado (leader_name): Data
- Nombre de la medición (survey_name): Data
- Total de respuestas (total_responses): Int
- Total de evaluadores (total_evaluators): Int 
- Total de evaluadores pares
- Total de evaluadores líderes
- Total de evaluadores colaboradores
  Este campo se calcula usando qp_IQ_SurveyRecipient para contar el número de evaluadores únicos que evaluaron al líder.
- Puntaje general (overall_score): Float
  Este campo se calcula promediando los puntajes de todas las respuestas del líder, incluyendo las respuestas de autoevaluación. El cálculo del puntaje general se realiza tomando en cuenta la escala de evaluación definida en la encuesta y promediando los puntajes asignados a cada respuesta.
- Puntaje colaboradores (team_score): Float
- Puntaje autoevaluación (self_score): Float
- Puntaje pares (peers_score): Float
- Puntaje líder (manager_score): Float
- Promedio líderes (average_leaders_score): Float
  Este campo se calcula promediando los puntajes generales de todos los líderes evaluados en la misma medición. Para calcular este promedio, se deben obtener los puntajes generales de todos los líderes evaluados en la misma encuesta (survey_name) y luego promediar esos puntajes para obtener el promedio de líderes.
- Promedio otros (others_score): Float
  Promedio de los puntajes que no son autoevaluación.
- Resultados por dimensión (dimension_summary): Table
  Este campo es una tabla que almacena el resumen de resultados por dimensión evaluada. Cada fila de la tabla representa una dimensión e incluye el puntaje promedio por grupo evaluador.
- Resltados por comportamiento (question_summary): Table
  Este campo es una tabla que almacena el resumen de resultados por comportamiento evaluado. Cada fila de la tabla representa un comportamiento específico evaluado en la encuesta. Un comportamiento es una pregunta específica de la encuesta que se evalúa para el líder. El resumen de resultados por comportamiento incluye el puntaje promedio asignado a ese comportamiento específico por cada grupo de evaluadores (colaboradores, autoevaluación, pares, líder y otros).
- Pregntas abiertas (open_questions_answers): Long Text
  Este campo almacena las respuestas a las preguntas abiertas de la encuesta.  
"""

ROLE_SELF = 'Autoevaluación'
ROLE_MANAGER = 'Jefe'
ROLE_PEER = 'Par'
ROLE_TEAM = 'Colaborador'

SCORE_KEY_SELF = 'self_score'
SCORE_KEY_MANAGER = 'manager_score'
SCORE_KEY_PEER = 'peers_score'
SCORE_KEY_TEAM = 'team_score'

ROLE_TO_SCORE_KEY = {
  ROLE_SELF: SCORE_KEY_SELF,
  ROLE_MANAGER: SCORE_KEY_MANAGER,
  ROLE_PEER: SCORE_KEY_PEER,
  ROLE_TEAM: SCORE_KEY_TEAM,
}


def _get_logger():
  return frappe.logger('iq360_report_builder', allow_site=True)


def _resolve_previous_comparable_survey_name(current_survey):
  """Find previous leadership measurement for same company and template."""
  if not current_survey:
    return None

  owner = getattr(current_survey, 'su_owner', None)
  template = getattr(current_survey, 'su_template', None)
  if not owner or not template:
    return None

  current_ts = frappe.utils.get_datetime(getattr(current_survey, 'su_end_date', None) or getattr(current_survey, 'creation', None))
  candidates = frappe.get_all(
    'qp_IQ_Survey',
    filters={
      'su_owner': owner,
      'su_template': template,
      'su_is_leadership': 1,
      'name': ['!=', current_survey.name],
    },
    fields=['name', 'su_name', 'su_end_date', 'creation'],
  )

  previous = None
  for row in candidates:
    row_ts = frappe.utils.get_datetime(row.get('su_end_date') or row.get('creation'))
    if current_ts and row_ts and row_ts >= current_ts:
      continue
    if not previous:
      previous = row
      continue

    prev_ts = frappe.utils.get_datetime(previous.get('su_end_date') or previous.get('creation'))
    if row_ts and prev_ts and row_ts > prev_ts:
      previous = row

  return previous.get('su_name') if previous else None


def _get_previous_leader_question_others_map(leader_name, previous_survey_name):
  """Return question_text -> others_score map from previous generated leader report."""
  if not leader_name or not previous_survey_name:
    return {}

  report_name = frappe.db.get_value(
    'qp_IQ_Leader_360_Report',
    {'leader_name': leader_name, 'survey_name': previous_survey_name},
    'name',
  )
  if not report_name:
    return {}

  report = frappe.get_doc('qp_IQ_Leader_360_Report', report_name)
  question_map = {}
  for row in (report.question_summary or []):
    question_text = row.get('question_text')
    if question_text:
      question_map[question_text] = row.get('others_score')
  return question_map




def build_leaders_report(survey_id):
  logger = _get_logger()
  logger.info('build_leaders_report start | survey_id=%s', survey_id)

  # Get the measurement doc
  survey = frappe.get_doc('qp_IQ_Survey', survey_id)
  if not getattr(survey, 'su_is_leadership', 0):
    logger.info('build_leaders_report skipped | survey_id=%s reason=not_leadership', survey_id)
    return False

  if getattr(survey, 'su_report_generated', 0):
    logger.info('build_leaders_report skipped | survey_id=%s reason=already_generated', survey_id)
    return False

  survey_name = survey.su_name
  logger.info('survey loaded | survey_name=%s', survey_name)

  previous_survey_name = _resolve_previous_comparable_survey_name(survey)
  logger.info(
    'previous comparable survey resolved | current_survey=%s previous_survey=%s',
    survey_name,
    previous_survey_name,
  )

  # Get responses for the survey
  responses = get_all_responses_for_survey(survey_name)
  logger.info('responses fetched | count=%s', len(responses or []))

  # Group responses by leader
  leaders_responses = group_responses_by_leader(responses)
  logger.info('leaders grouped | leaders=%s', len(leaders_responses or {}))
  leaders_data = []

  questions_data = get_question_text_and_category(survey_id)
  logger.info('questions metadata loaded | questions=%s', len(questions_data or {}))

  # Process responses for each leader and collect results
  for leader, leader_responses in leaders_responses.items():
    logger.info('processing leader | leader=%s responses=%s', leader, len(leader_responses or []))
    leader_data = process_leader_data(
      survey_id,
      leader_responses,
      questions_data,
      previous_survey_name=previous_survey_name,
    )
    if not leader_data:
      logger.info('leader skipped | leader=%s reason=empty_data', leader)
      continue

    leader_data['leader_name'] = leader
    leader_data['survey_name'] = survey_name
    leaders_data.append(leader_data)

  # Average of all responses across all evaluated leaders (not average of averages)
  all_scores = []
  for data in leaders_data:
    scores = data.get('_all_scores', [])
    if scores:
      all_scores.extend(scores)
  avg_leaders_score = average(all_scores)

  # Average leaders score by dimension (same measurement), including evaluator groups.
  dimension_avg_leaders_scores = {}
  dimension_group_avg_leaders_scores = {}
  dimension_values = defaultdict(list)
  dimension_group_values = defaultdict(lambda: defaultdict(list))
  for data in leaders_data:
    # Usar los valores crudos si están disponibles, sino usar los promedios (compatibilidad)
    raw_scores = data.get('_raw_dimension_scores', {})
    if raw_scores:
      # Usar valores crudos - más correcto
      for dimension_name, raw_data in raw_scores.items():
        dimension_values[dimension_name].extend(raw_data.get('all_values', []))
        dimension_group_values[dimension_name]['others_score'].extend(raw_data.get('others_values', []))
        dimension_group_values[dimension_name][SCORE_KEY_SELF].extend(raw_data.get(f'{SCORE_KEY_SELF}_values', []))
        dimension_group_values[dimension_name][SCORE_KEY_MANAGER].extend(raw_data.get(f'{SCORE_KEY_MANAGER}_values', []))
        dimension_group_values[dimension_name][SCORE_KEY_PEER].extend(raw_data.get(f'{SCORE_KEY_PEER}_values', []))
        dimension_group_values[dimension_name][SCORE_KEY_TEAM].extend(raw_data.get(f'{SCORE_KEY_TEAM}_values', []))
    else:
      # Fallback si no hay valores crudos (para compatibilidad con datos antiguos)
      for dimension_name, dimension_data in (data.get('dimension_summary') or {}).items():
        dimension_avg = dimension_data.get('avg_score')
        if dimension_avg is not None:
          dimension_values[dimension_name].append(dimension_avg)

        for score_key in ('others_score', SCORE_KEY_SELF, SCORE_KEY_MANAGER, SCORE_KEY_PEER, SCORE_KEY_TEAM):
          score_value = dimension_data.get(score_key)
          if score_value is not None:
            dimension_group_values[dimension_name][score_key].append(score_value)

  for dimension_name, values in dimension_values.items():
    dimension_avg_leaders_scores[dimension_name] = average(values)

  for dimension_name, score_groups in dimension_group_values.items():
    dimension_group_avg_leaders_scores[dimension_name] = {
      score_key: average(values)
      for score_key, values in score_groups.items()
      if values
    }

  # Average leaders score by theme (same measurement), including evaluator groups.
  theme_avg_leaders_scores = {}
  theme_group_avg_leaders_scores = {}
  theme_values = defaultdict(list)
  theme_group_values = defaultdict(lambda: defaultdict(list))
  for data in leaders_data:
    # Usar los valores crudos si están disponibles, sino usar los promedios (compatibilidad)
    raw_scores = data.get('_raw_theme_scores', {})
    if raw_scores:
      # Usar valores crudos - más correcto
      for theme_name, raw_data in raw_scores.items():
        theme_values[theme_name].extend(raw_data.get('all_values', []))
        theme_group_values[theme_name]['others_score'].extend(raw_data.get('others_values', []))
        theme_group_values[theme_name][SCORE_KEY_SELF].extend(raw_data.get(f'{SCORE_KEY_SELF}_values', []))
        theme_group_values[theme_name][SCORE_KEY_MANAGER].extend(raw_data.get(f'{SCORE_KEY_MANAGER}_values', []))
        theme_group_values[theme_name][SCORE_KEY_PEER].extend(raw_data.get(f'{SCORE_KEY_PEER}_values', []))
        theme_group_values[theme_name][SCORE_KEY_TEAM].extend(raw_data.get(f'{SCORE_KEY_TEAM}_values', []))
    else:
      # Fallback si no hay valores crudos (para compatibilidad con datos antiguos)
      for theme_name, theme_data in (data.get('theme_summary') or {}).items():
        theme_avg = theme_data.get('avg_score')
        if theme_avg is not None:
          theme_values[theme_name].append(theme_avg)

        for score_key in ('others_score', SCORE_KEY_SELF, SCORE_KEY_MANAGER, SCORE_KEY_PEER, SCORE_KEY_TEAM):
          score_value = theme_data.get(score_key)
          if score_value is not None:
            theme_group_values[theme_name][score_key].append(score_value)

  for theme_name, values in theme_values.items():
    theme_avg_leaders_scores[theme_name] = average(values)

  for theme_name, score_groups in theme_group_values.items():
    theme_group_avg_leaders_scores[theme_name] = {
      score_key: average(values)
      for score_key, values in score_groups.items()
      if values
    }

  # Build or update the report for each leader
  for leader_data in leaders_data:
    leader_data['avg_leaders_score'] = avg_leaders_score
    for dimension_name, dimension_data in (leader_data.get('dimension_summary') or {}).items():
      dimension_data['average_leaders_score'] = dimension_avg_leaders_scores.get(dimension_name)
      dimension_group_avg = dimension_group_avg_leaders_scores.get(dimension_name, {})
      dimension_data['average_leaders_others_score'] = dimension_group_avg.get('others_score')
      dimension_data['average_leaders_self_score'] = dimension_group_avg.get(SCORE_KEY_SELF)
      dimension_data['average_leaders_manager_score'] = dimension_group_avg.get(SCORE_KEY_MANAGER)
      dimension_data['average_leaders_peers_score'] = dimension_group_avg.get(SCORE_KEY_PEER)
      dimension_data['average_leaders_team_score'] = dimension_group_avg.get(SCORE_KEY_TEAM)
    for theme_name, theme_data in (leader_data.get('theme_summary') or {}).items():
      theme_data['average_leaders_score'] = theme_avg_leaders_scores.get(theme_name)
      theme_group_avg = theme_group_avg_leaders_scores.get(theme_name, {})
      theme_data['average_leaders_others_score'] = theme_group_avg.get('others_score')
      theme_data['average_leaders_self_score'] = theme_group_avg.get(SCORE_KEY_SELF)
      theme_data['average_leaders_manager_score'] = theme_group_avg.get(SCORE_KEY_MANAGER)
      theme_data['average_leaders_peers_score'] = theme_group_avg.get(SCORE_KEY_PEER)
      theme_data['average_leaders_team_score'] = theme_group_avg.get(SCORE_KEY_TEAM)
    # Build or update the report for the leader
    report = build_leader_report(leader_data)
    logger.info(
      'leader report persisted | leader=%s report=%s',
      leader_data.get('leader_name'),
      report.name if report else None,
    )

  logger.info('build_leaders_report end | processed_leaders=%s', len(leaders_data))
  frappe.db.set_value('qp_IQ_Survey', survey_id, 'su_report_generated', 1, update_modified=False)
  frappe.db.commit()
  return True


def generate_leadership_report_on_status_change(doc, method=None):
  logger = _get_logger()

  status_finished = frappe.get_value('qp_IQ_SurveyStatus', {'se_status': 'Finalizada'}, 'name')
  if not status_finished or doc.su_status != status_finished:
    return

  previous_status = None
  try:
    previous_doc = doc.get_doc_before_save()
    previous_status = getattr(previous_doc, 'su_status', None) if previous_doc else None
  except Exception:
    previous_status = None

  if previous_status == status_finished:
    return

  if not getattr(doc, 'su_is_leadership', 0):
    logger.info('generate_leadership_report_on_status_change skipped | survey_id=%s reason=not_leadership', doc.name)
    return

  if getattr(doc, 'su_report_generated', 0):
    logger.info('generate_leadership_report_on_status_change skipped | survey_id=%s reason=already_generated', doc.name)
    return

  build_leaders_report(doc.name)


from collections import defaultdict

def group_responses_by_leader(responses):
    # Group responses by leader
    leaders_responses = defaultdict(list)
    for response in responses:
        leader_name = response.get('custom_evaluatee')
        leaders_responses[leader_name].append(response)
    return leaders_responses


def process_leader_responses(survey_id, leaders_responses, questions_data, previous_survey_name=None):
    # Process responses for each leader
    leaders_report = {}
    for leader, responses in leaders_responses.items():
        leaders_report[leader] = process_leader_data(
          survey_id,
          responses,
          questions_data,
          previous_survey_name=previous_survey_name,
        )
    return leaders_report


def process_leader_data(survey_id, responses, questions_data, previous_survey_name=None):
    logger = _get_logger()

    if not responses:
        logger.info('process_leader_data empty responses | survey_id=%s', survey_id)
        return {}

    leader_data = {}

    # Datos básicos
    first = responses[0]
    leader_data['leader_name'] = first.get('custom_evaluatee')
    leader_data['survey_name'] = first.get('survey')
    leader_data['total_responses'] = len(responses)
    previous_question_others_map = {}
    if previous_survey_name:
      previous_question_others_map = _get_previous_leader_question_others_map(
        leader_data['leader_name'],
        previous_survey_name,
      )

    evaluators = get_leader_evaluators(leader_data['leader_name'], survey_id)
    evaluator_ids = {
      e.sr_evaluating_to
      for e in evaluators
      if e.sr_evaluating_to
    }
    leader_data['total_evaluators'] = len(evaluator_ids)

    # Map de evaluadores (Contact.name -> rol)
    evaluator_map = {
      e.sr_evaluating_to: e.sr_evaluation_role
      for e in evaluators
      if e.sr_evaluating_to
    }

    # También indexamos por DNI para compatibilidad con respuestas históricas.
    if evaluator_ids:
      contact_docs = frappe.get_all(
        'Contact',
        filters={'name': ['in', list(evaluator_ids)]},
        fields=['name', 'custom_document_number'],
      )
      for contact in contact_docs:
        role = evaluator_map.get(contact.name)
        if role and contact.custom_document_number:
          evaluator_map[contact.custom_document_number] = role

    # Evaluador por respuesta (prioriza custom_evaluator si existe)
    response_evaluator_map = {
      r.name: (r.get('custom_evaluator') or r.get('user'))
      for r in responses
    }

    # Normalizar respuestas
    normalized_responses = normalize_responses(responses)


    # Estructuras acumuladoras
    scores = []
    group_scores = defaultdict(list)
    dimension_scores = defaultdict(lambda: defaultdict(list))
    dimension_themes = defaultdict(set)  # Rastrear temas por dimensión
    theme_scores = defaultdict(lambda: defaultdict(list))
    question_scores = defaultdict(lambda: defaultdict(list))
    open_questions_answers = defaultdict(list)  
    total_responses_peers = 0
    total_responses_managers = 0
    total_responses_team = 0

    # Count submitted evaluations by role (one per response document).
    for response in responses:
      evaluator_id = response.get('custom_evaluator') or response.get('user')
      evaluator_role = evaluator_map.get(evaluator_id)
      score_key = ROLE_TO_SCORE_KEY.get(evaluator_role)
      if score_key == SCORE_KEY_PEER:
        total_responses_peers += 1
      elif score_key == SCORE_KEY_MANAGER:
        total_responses_managers += 1
      elif score_key == SCORE_KEY_TEAM:
        total_responses_team += 1

    for response_name, resp_list in normalized_responses.items():
        mapped_evaluator_id = response_evaluator_map.get(response_name)
        mapped_evaluator_role = evaluator_map.get(mapped_evaluator_id)
        mapped_score_key = ROLE_TO_SCORE_KEY.get(mapped_evaluator_role)

        for resp in resp_list:

            if resp['answer_type'] == 'text':
                question_text = questions_data.get(resp['question'], {}).get('text', resp['question'])
                open_questions_answers[question_text].append(resp['answer'])
                continue

            value = resp['answer']
            scores.append(value)

            score_key = mapped_score_key
            if not score_key:
              evaluator_role = evaluator_map.get(resp.get('evaluator'))
              score_key = ROLE_TO_SCORE_KEY.get(evaluator_role)
            if not score_key:
                continue

            # Global
            group_scores[score_key].append(value)

            # Dimensión
            question_info = questions_data.get(resp['question'])
            if question_info:
                dimension = question_info.get('category') or 'Sin Categoría'
                dimension_scores[dimension][score_key].append(value)
                
                # Tema
                theme = question_info.get('theme') or 'Sin Tema'
                dimension_themes[dimension].add(theme)
                theme_scores[theme][score_key].append(value)

            # Comportamiento
            question_scores[resp['question']][score_key].append(value)

    # Resumen Global
    leader_data['overall_score'] = average(scores)
    leader_data['_all_scores'] = scores  # Guardar todas las respuestas individuales
    leader_data['total_responses_peers'] = total_responses_peers
    leader_data['total_responses_managers'] = total_responses_managers
    leader_data['total_responses_team'] = total_responses_team
    leader_data['total_evaluators_peers'] = len({
      e.sr_evaluating_to for e in evaluators
      if e.sr_evaluation_role == ROLE_PEER and e.sr_evaluating_to
    })
    leader_data['total_evaluators_managers'] = len({
      e.sr_evaluating_to for e in evaluators
      if e.sr_evaluation_role == ROLE_MANAGER and e.sr_evaluating_to
    })
    leader_data['total_evaluators_team'] = len({
      e.sr_evaluating_to for e in evaluators
      if e.sr_evaluation_role == ROLE_TEAM and e.sr_evaluating_to
    })
    leader_data[SCORE_KEY_TEAM] = average(group_scores.get(SCORE_KEY_TEAM, []))
    leader_data[SCORE_KEY_SELF] = average(group_scores.get(SCORE_KEY_SELF, []))
    leader_data[SCORE_KEY_PEER] = average(group_scores.get(SCORE_KEY_PEER, []))
    leader_data[SCORE_KEY_MANAGER] = average(group_scores.get(SCORE_KEY_MANAGER, []))

    others_values = [
        v for role, values in group_scores.items()
        if role != SCORE_KEY_SELF
        for v in values
    ]

    leader_data['others_score'] = average(others_values)

    # Resumen por dimensión
    leader_data['dimension_summary'] = {}
    leader_data['_raw_dimension_scores'] = {}

    for dim, roles in dimension_scores.items():
        dim_data = {}

        for role, values in roles.items():
            dim_data[role] = average(values)

        others = [
            v for role, values in roles.items()
            if role != SCORE_KEY_SELF
            for v in values
        ]

        # Total
        all_values = []
        for values in roles.values():
            all_values.extend(values)

        dim_data['others_score'] = average(others)
        dim_data['avg_score'] = average(all_values)
        # Agregar temas encontrados en esta dimensión
        dim_data['theme_name'] = ', '.join(sorted(dimension_themes.get(dim, [])))

        leader_data['dimension_summary'][dim] = dim_data
        # Guardar los valores crudos para calcular promedios correctos a nivel de survey
        leader_data['_raw_dimension_scores'][dim] = {
            'all_values': all_values,
            'others_values': others,
        }
        for role, values in roles.items():
            if f'{role}_values' not in leader_data['_raw_dimension_scores'][dim]:
                leader_data['_raw_dimension_scores'][dim][f'{role}_values'] = []
            leader_data['_raw_dimension_scores'][dim][f'{role}_values'].extend(values)
    
    # Resumen por tema
    leader_data['theme_summary'] = {}
    leader_data['_raw_theme_scores'] = {}

    for theme, roles in theme_scores.items():
        theme_data = {}

        for role, values in roles.items():
            theme_data[role] = average(values)

        others = [
            v for role, values in roles.items()
            if role != SCORE_KEY_SELF
            for v in values
        ]

        # Total
        all_values = []
        for values in roles.values():
            all_values.extend(values)

        theme_data['others_score'] = average(others)
        theme_data['avg_score'] = average(all_values)

        leader_data['theme_summary'][theme] = theme_data
        # Guardar los valores crudos para calcular promedios correctos a nivel de survey
        leader_data['_raw_theme_scores'][theme] = {
            'all_values': all_values,
            'others_values': others,
        }
        for role, values in roles.items():
            if f'{role}_values' not in leader_data['_raw_theme_scores'][theme]:
                leader_data['_raw_theme_scores'][theme][f'{role}_values'] = []
            leader_data['_raw_theme_scores'][theme][f'{role}_values'].extend(values)

      
    # Resumen por comportamiento
    leader_data['question_summary'] = []


    for question, roles in question_scores.items():
        q_data = {}
        q_info = questions_data.get(question, {})

        for role, values in roles.items():
            q_data[role] = average(values)

        others = []
        for role, values in roles.items():
            if role != SCORE_KEY_SELF:
                others.extend(values)

        # Total
        all_values = []
        for values in roles.values():
            all_values.extend(values)

        q_data['question_text'] = q_info.get('text', question)
        q_data['question_dimension'] = q_info.get('category', 'Sin Categoría')
        q_data['theme_name'] = q_info.get('theme', 'Sin Tema')
        q_data['others_score'] = average(others)
        previous_others_score = previous_question_others_map.get(q_data['question_text'])
        q_data['trend_delta'] = None
        if previous_others_score is not None and q_data['others_score'] is not None:
          q_data['trend_delta'] = q_data['others_score'] - previous_others_score
        q_data['gap_self_vs_others'] = q_data.get(SCORE_KEY_SELF, 0) - q_data.get('others_score', 0)
        q_data['std_dev'] = std_dev(all_values) if all_values else 0  
        #q_data['avg_score'] = average(all_values)
      
        leader_data['question_summary'].append(q_data)
      
      # Respuestas abiertas
    leader_data['open_questions_answers'] = open_questions_answers

    logger.info(
        'leader data processed | leader=%s total_responses=%s total_evaluators=%s dimension_rows=%s theme_rows=%s question_rows=%s open_questions=%s',
        leader_data.get('leader_name'),
        leader_data.get('total_responses'),
        leader_data.get('total_evaluators'),
        len(leader_data.get('dimension_summary') or {}),
        len(leader_data.get('theme_summary') or {}),
        len(leader_data.get('question_summary') or []),
        len(leader_data.get('open_questions_answers') or {}),
    )

    return leader_data

def build_leader_report(leader_data):
  logger = _get_logger()
  leader_name = leader_data.get('leader_name')
  survey_name = leader_data.get('survey_name')

  if not leader_name or not survey_name:
    logger.info('build_leader_report skipped | missing leader_name or survey_name')
    return None

  report_filters = {'leader_name': leader_name, 'survey_name': survey_name}
  if frappe.db.exists('qp_IQ_Leader_360_Report', report_filters):
    report = frappe.get_doc('qp_IQ_Leader_360_Report', report_filters)
    logger.info('build_leader_report update | report=%s leader=%s', report.name, leader_name)
  else:
    report = frappe.new_doc('qp_IQ_Leader_360_Report')
    logger.info('build_leader_report create | leader=%s survey=%s', leader_name, survey_name)

  # Campos base
  report.leader_name = leader_name
  report.survey_name = survey_name
  report.total_responses = leader_data.get('total_responses')
  report.total_evaluators = leader_data.get('total_evaluators')
  report.total_evaluators_peers = leader_data.get('total_evaluators_peers')
  report.total_evaluators_managers = leader_data.get('total_evaluators_managers')
  report.total_evaluators_team = leader_data.get('total_evaluators_team')
  report.total_responses_peers = leader_data.get('total_responses_peers')
  report.total_responses_managers = leader_data.get('total_responses_managers')
  report.total_responses_team = leader_data.get('total_responses_team')
  report.overall_score = _round2(leader_data.get('overall_score'))
  report.team_score = _round2(leader_data.get(SCORE_KEY_TEAM))
  report.self_score = _round2(leader_data.get(SCORE_KEY_SELF))
  report.peers_score = _round2(leader_data.get(SCORE_KEY_PEER))
  report.manager_score = _round2(leader_data.get(SCORE_KEY_MANAGER))
  report.others_score = _round2(leader_data.get('others_score'))
  report.avg_leaders_score = _round2(leader_data.get('avg_leaders_score') or leader_data.get('average_leaders_score'))

  # Respuestas abiertas
  open_answers = leader_data.get('open_questions_answers') or {}
  report.open_questions_answer = json.dumps(open_answers, ensure_ascii=False)

  # Tablas hijas: limpiar y recargar
  report.set('dimension_summary', [])
  for dimension_name, values in (leader_data.get('dimension_summary') or {}).items():
    report.append('dimension_summary', {
      'dimension_name': dimension_name,
      'theme_name': values.get('theme_name'),
      SCORE_KEY_SELF: _round2(values.get(SCORE_KEY_SELF)),
      SCORE_KEY_MANAGER: _round2(values.get(SCORE_KEY_MANAGER)),
      SCORE_KEY_PEER: _round2(values.get(SCORE_KEY_PEER)),
      SCORE_KEY_TEAM: _round2(values.get(SCORE_KEY_TEAM)),
      'others_score': _round2(values.get('others_score')),
      'avg_score': _round2(values.get('avg_score')),
      'average_leaders_score': _round2(values.get('average_leaders_score')),
      'average_leaders_others_score': _round2(values.get('average_leaders_others_score')),
      'average_leaders_self_score': _round2(values.get('average_leaders_self_score')),
      'average_leaders_manager_score': _round2(values.get('average_leaders_manager_score')),
      'average_leaders_peers_score': _round2(values.get('average_leaders_peers_score')),
      'average_leaders_team_score': _round2(values.get('average_leaders_team_score')),
    })

  report.set('theme_summary', [])
  for theme_name, values in (leader_data.get('theme_summary') or {}).items():
    report.append('theme_summary', {
      'theme_name': theme_name,
      SCORE_KEY_SELF: _round2(values.get(SCORE_KEY_SELF)),
      SCORE_KEY_MANAGER: _round2(values.get(SCORE_KEY_MANAGER)),
      SCORE_KEY_PEER: _round2(values.get(SCORE_KEY_PEER)),
      SCORE_KEY_TEAM: _round2(values.get(SCORE_KEY_TEAM)),
      'others_score': _round2(values.get('others_score')),
      'avg_score': _round2(values.get('avg_score')),
      'average_leaders_score': _round2(values.get('average_leaders_score')),
      'average_leaders_others_score': _round2(values.get('average_leaders_others_score')),
      'average_leaders_self_score': _round2(values.get('average_leaders_self_score')),
      'average_leaders_manager_score': _round2(values.get('average_leaders_manager_score')),
      'average_leaders_peers_score': _round2(values.get('average_leaders_peers_score')),
      'average_leaders_team_score': _round2(values.get('average_leaders_team_score')),
    })

  report.set('question_summary', [])
  for values in (leader_data.get('question_summary') or []):
    report.append('question_summary', {
      'question_text': values.get('question_text'),
      'question_dimension': values.get('question_dimension'),
      'theme_name': values.get('theme_name'),
      SCORE_KEY_SELF: _round2(values.get(SCORE_KEY_SELF)),
      SCORE_KEY_MANAGER: _round2(values.get(SCORE_KEY_MANAGER)),
      SCORE_KEY_PEER: _round2(values.get(SCORE_KEY_PEER)),
      SCORE_KEY_TEAM: _round2(values.get(SCORE_KEY_TEAM)),
      'others_score': _round2(values.get('others_score')),
      'trend_delta': _round2(values.get('trend_delta')),
      'gap_self_vs_others': _round2(values.get('gap_self_vs_others')),
      'std_deviation': _round2(values.get('std_dev')),
    })

  if report.is_new():
    report.insert(ignore_permissions=True)
    logger.info('build_leader_report inserted | report=%s', report.name)
  else:
    report.save(ignore_permissions=True)
    logger.info('build_leader_report saved | report=%s', report.name)
  frappe.db.commit()
  return report


def build_leaders_report_batched(survey_id, batch_size=None, async_mode=True):
    """
    Build leadership 360 reports using batch processing.
    
    This version processes responses in batches to handle large datasets without timeouts.
    
    Args:
        survey_id: ID of the qp_IQ_Survey
        batch_size: Optional override for batch size (default: 500)
        async_mode: If True, process in background; if False, process synchronously
    
    Returns:
        progress_doc_name if successful, False if skipped
    """
    logger = _get_logger()
    logger.info('build_leaders_report_batched start | survey_id=%s batch_size=%s async_mode=%s', survey_id, batch_size, async_mode)
    
    try:
        # Get the survey doc
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        
        if not getattr(survey, 'su_is_leadership', 0):
            logger.info('build_leaders_report_batched skipped | survey_id=%s reason=not_leadership', survey_id)
            return False
        
        if getattr(survey, 'su_report_generated', 0):
            logger.info('build_leaders_report_batched skipped | survey_id=%s reason=already_generated', survey_id)
            return False
        
        survey_name = survey.su_name
        
        # Get all responses upfront (needed for slicing)
        responses = get_all_responses_for_survey(survey_name)
        if not responses:
            logger.info('build_leaders_report_batched skipped | survey_id=%s reason=no_responses', survey_id)
            return False
        
        # Group responses by leader
        leaders_responses = group_responses_by_leader(responses)
        if not leaders_responses:
            logger.info('build_leaders_report_batched skipped | survey_id=%s reason=no_leaders', survey_id)
            return False
        
        logger.info(
            'batch processing initialized | survey=%s responses=%s leaders=%s batch_size=%s',
            survey_name,
            len(responses),
            len(leaders_responses),
            batch_size or 500
        )
        
        # Create progress tracking document
        from liseniq.batch_processor import BatchProcessor
        processor = BatchProcessor(survey_id, 'iq360', batch_size=batch_size, async_mode=async_mode)
        
        progress_name = processor.start_batch_processing(
            total_responses=len(responses),
            callback_method=process_iq360_batch_worker,
            survey_name=survey_name,
            all_responses=json.dumps(responses, default=str),
        )
        
        return progress_name
        
    except Exception as e:
        logger.error(f'Error en build_leaders_report_batched: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        return False


def process_iq360_batch_worker(survey_id, progress_name, batch_num, batch_size, survey_name, all_responses):
    """
    Worker function for processing a single batch of responses for leadership reports.
    
    This is called for each batch (either sync or async via enqueue).
    """
    logger = _get_logger()
    logger.info('process_iq360_batch_worker start | survey_id=%s batch_num=%s', survey_id, batch_num)
    
    try:
        from liseniq.batch_processor import BatchProcessor, serialize_accumulated_data, deserialize_accumulated_data
        
        # Deserialize the responses
        all_responses_list = json.loads(all_responses)
        
        # Get the slice for this batch
        processor = BatchProcessor(survey_id, 'iq360', batch_size=batch_size, async_mode=False)
        batch_responses = processor.get_batch_slice(all_responses_list, batch_num)
        
        if not batch_responses:
            logger.info('process_iq360_batch_worker empty batch | batch_num=%s', batch_num)
            return
        
        # Get metadata once
        questions_data = get_question_text_and_category(survey_id)
        
        # Process this batch and accumulate raw values
        accumulated_data = _accumulate_iq360_batch(batch_responses, questions_data, survey_id)
        
        # Store accumulated data in progress document
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        
        # Deserialize existing accumulated data
        existing_accumulated = deserialize_accumulated_data(progress_doc.accumulated_data)
        
        # Merge with new batch data
        _merge_iq360_accumulated_data(existing_accumulated, accumulated_data)
        
        # Save back
        progress_doc.accumulated_data = serialize_accumulated_data(existing_accumulated)
        progress_doc.save(ignore_permissions=True)
        
        # Update progress
        BatchProcessor.update_batch_progress(
            progress_name,
            batch_num,
            len(batch_responses),
            status='in_progress'
        )
        
        logger.info('process_iq360_batch_worker completed | batch_num=%s responses_processed=%s', batch_num, len(batch_responses))
        
    except Exception as e:
        logger.error(f'Error en process_iq360_batch_worker: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        BatchProcessor.update_batch_progress(
            progress_name,
            batch_num,
            0,
            status='failed',
            error=str(e)
        )
        raise


def _accumulate_iq360_batch(batch_responses, questions_data, survey_id):
    """
    Accumulate raw scores from a batch of responses for leadership reports.
    
    Returns a dict with raw values organized by leader.
    """
    logger = _get_logger()
    
    accumulated = {
        'leaders_data': {},  # leader_name -> raw scores and metrics
        'all_scores': [],
    }
    
    # Normalize responses for this batch
    normalized_responses = normalize_responses(batch_responses)
    
    # Group by leader as we process
    for response_name, resp_list in normalized_responses.items():
        for resp in resp_list:
            if resp['answer_type'] == 'text':
                continue
            
            # Get leader from first response in the response doc
            # (In iq360, leader is in custom_evaluatee field)
            leader_name = resp.get('custom_evaluatee')
            if not leader_name:
                continue
            
            if leader_name not in accumulated['leaders_data']:
                accumulated['leaders_data'][leader_name] = {
                    'scores': [],
                    'group_scores': defaultdict(list),
                    'dimension_scores': defaultdict(lambda: defaultdict(list)),
                    'theme_scores': defaultdict(lambda: defaultdict(list)),
                    'question_scores': defaultdict(lambda: defaultdict(list)),
                }
            
            leader_data = accumulated['leaders_data'][leader_name]
            
            # Get evaluator role (will be determined during finalization)
            value = resp['answer']
            
            # Accumulate raw scores
            leader_data['scores'].append(value)
            accumulated['all_scores'].append(value)
            
            # Get question metadata
            question_info = questions_data.get(resp['question'], {})
            dimension = question_info.get('category', 'Sin Categoría')
            theme = question_info.get('theme', 'Sin Tema')
            
            # Store scores by dimension and theme for later calculation
            leader_data['dimension_scores'][dimension]['all'].append(value)
            leader_data['theme_scores'][theme]['all'].append(value)
            leader_data['question_scores'][resp['question']]['all'].append(value)
    
    return accumulated


def _merge_iq360_accumulated_data(target, source):
    """Merge source accumulated data into target (in-place) for iq360."""
    # Merge all_scores
    if 'all_scores' in source:
        if 'all_scores' not in target:
            target['all_scores'] = []
        target['all_scores'].extend(source['all_scores'])
    
    # Merge leader data
    if 'leaders_data' in source:
        if 'leaders_data' not in target:
            target['leaders_data'] = {}
        
        for leader_name, leader_data in source['leaders_data'].items():
            if leader_name not in target['leaders_data']:
                target['leaders_data'][leader_name] = {
                    'scores': [],
                    'group_scores': defaultdict(list),
                    'dimension_scores': defaultdict(lambda: defaultdict(list)),
                    'theme_scores': defaultdict(lambda: defaultdict(list)),
                    'question_scores': defaultdict(lambda: defaultdict(list)),
                }
            
            target_leader = target['leaders_data'][leader_name]
            target_leader['scores'].extend(leader_data['scores'])
            
            # Merge dimension scores
            for dim, role_scores in leader_data['dimension_scores'].items():
                if dim not in target_leader['dimension_scores']:
                    target_leader['dimension_scores'][dim] = defaultdict(list)
                for role, values in role_scores.items():
                    target_leader['dimension_scores'][dim][role].extend(values)
            
            # Merge theme scores
            for theme, role_scores in leader_data['theme_scores'].items():
                if theme not in target_leader['theme_scores']:
                    target_leader['theme_scores'][theme] = defaultdict(list)
                for role, values in role_scores.items():
                    target_leader['theme_scores'][theme][role].extend(values)
            
            # Merge question scores
            for question, role_scores in leader_data['question_scores'].items():
                if question not in target_leader['question_scores']:
                    target_leader['question_scores'][question] = defaultdict(list)
                for role, values in role_scores.items():
                    target_leader['question_scores'][question][role].extend(values)


def finalize_iq360_reports_from_batches(survey_id, progress_name):
    """
    Finalize leadership report generation after all batches are processed.
    
    This calculates final metrics from accumulated raw values and creates all report documents.
    """
    logger = _get_logger()
    logger.info('finalize_iq360_reports_from_batches start | survey_id=%s progress_name=%s', survey_id, progress_name)
    
    try:
        from liseniq.batch_processor import deserialize_accumulated_data
        
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        survey_name = survey.su_name
        
        # Deserialize accumulated data
        accumulated_data = deserialize_accumulated_data(progress_doc.accumulated_data)
        
        if not accumulated_data or not accumulated_data.get('leaders_data'):
            logger.info('finalize_iq360_reports_from_batches | no accumulated data found')
            return False
        
        # Get metadata
        questions_data = get_question_text_and_category(survey_id)
        
        # Calculate organization-wide average (for comparison)
        all_scores = accumulated_data.get('all_scores', [])
        avg_leaders_score = average(all_scores)
        
        logger.info('organization average calculated | avg_score=%s', avg_leaders_score)
        
        # Resolve previous survey for trends
        previous_survey_name = _resolve_previous_comparable_survey_name(survey)
        
        # Build reports for each leader
        reports_count = 0
        for leader_name, leader_data in accumulated_data.get('leaders_data', {}).items():
            try:
                logger.info('processing leader from batches | leader=%s', leader_name)
                
                # Now we need to get evaluator roles (this requires DB access per leader)
                # For now, we'll recalculate with proper roles during finalization
                
                final_leader_data = _finalize_leader_scores_from_batches(
                    survey_id,
                    leader_name,
                    leader_data,
                    questions_data,
                    avg_leaders_score,
                    previous_survey_name
                )
                
                if not final_leader_data:
                    logger.info('leader skipped during finalization | leader=%s', leader_name)
                    continue
                
                # Build the report
                report = build_leader_report(final_leader_data)
                
                if report:
                    reports_count += 1
                
            except Exception as e:
                logger.error(f'Error procesando leader {leader_name}: {type(e).__name__}: {str(e)}')
                logger.exception('Stack trace:')
                continue
        
        # Mark survey as report generated
        frappe.db.set_value('qp_IQ_Survey', survey_id, 'su_report_generated', 1, update_modified=False)
        frappe.db.commit()
        
        logger.info('finalize_iq360_reports_from_batches end | reports_generated=%s', reports_count)
        return True
        
    except Exception as e:
        logger.error(f'Error en finalize_iq360_reports_from_batches: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        raise


def _finalize_leader_scores_from_batches(survey_id, leader_name, accumulated_leader_data, questions_data, avg_leaders_score, previous_survey_name):
    """
    Convert accumulated batch data into final leader report data with proper role-based calculations.
    """
    logger = _get_logger()
    
    try:
        # Get evaluators and their roles
        evaluators = get_leader_evaluators(leader_name, survey_id)
        
        if not evaluators:
            logger.warn(f'No evaluators found for leader: {leader_name}')
            return None
        
        # Build evaluator map
        evaluator_map = {
            e.sr_evaluating_to: e.sr_evaluation_role
            for e in evaluators
            if e.sr_evaluating_to
        }
        
        leader_responses = frappe.get_all(
            'qp_IQ_Response_Item',
            filters={'custom_evaluatee': leader_name},
            fields=['name', 'user', 'custom_evaluator', 'custom_evaluatee']
        )
        
        if not leader_responses:
            return None
        
        # Build response evaluator map
        response_evaluator_map = {
            r.name: (r.custom_evaluator or r.user)
            for r in leader_responses
        }
        
        # Now recalculate with proper roles
        final_data = process_leader_data(
            survey_id,
            leader_responses,
            questions_data,
            previous_survey_name=previous_survey_name
        )
        
        if final_data:
            final_data['avg_leaders_score'] = avg_leaders_score
        
        return final_data
        
    except Exception as e:
        logger.error(f'Error en _finalize_leader_scores_from_batches: {type(e).__name__}: {str(e)}')
        return None
    return report