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
ROLE_MANAGER = 'Líder/Jefe'
ROLE_PEER = 'Par/Igual'
ROLE_TEAM = 'Persona a Cargo'

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
    leader_data = process_leader_data(survey_id, leader_responses, questions_data)
    if not leader_data:
      logger.info('leader skipped | leader=%s reason=empty_data', leader)
      continue

    leader_data['leader_name'] = leader
    leader_data['survey_name'] = survey_name
    leaders_data.append(leader_data)

  # Average of overall scores across all evaluated leaders
  overall_scores = [
    data.get('overall_score')
    for data in leaders_data
    if data.get('overall_score') is not None
  ]
  avg_leaders_score = average(overall_scores)
  logger.info(
    'leaders average computed | leaders_with_score=%s avg_leaders_score=%s',
    len(overall_scores),
    avg_leaders_score,
  )

  # Build or update the report for each leader
  for leader_data in leaders_data:
    leader_data['avg_leaders_score'] = avg_leaders_score
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


def process_leader_responses(survey_id, leaders_responses, questions_data):
    # Process responses for each leader
    leaders_report = {}
    for leader, responses in leaders_responses.items():
        leaders_report[leader] = process_leader_data(survey_id, responses, questions_data)
    return leaders_report


def process_leader_data(survey_id, responses, questions_data):
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

            # Comportamiento
            question_scores[resp['question']][score_key].append(value)

    # Resumen Global
    leader_data['overall_score'] = average(scores)
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

        leader_data['dimension_summary'][dim] = dim_data

      
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
        q_data['others_score'] = average(others)
        q_data['gap_self_vs_others'] = q_data.get(SCORE_KEY_SELF, 0) - q_data.get('others_score', 0)
        q_data['std_dev'] = std_dev(all_values) if all_values else 0  
        #q_data['avg_score'] = average(all_values)
      
        leader_data['question_summary'].append(q_data)
      
      # Respuestas abiertas
    leader_data['open_questions_answers'] = open_questions_answers

    logger.info(
        'leader data processed | leader=%s total_responses=%s total_evaluators=%s dimension_rows=%s question_rows=%s open_questions=%s',
        leader_data.get('leader_name'),
        leader_data.get('total_responses'),
        leader_data.get('total_evaluators'),
        len(leader_data.get('dimension_summary') or {}),
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
      SCORE_KEY_SELF: _round2(values.get(SCORE_KEY_SELF)),
      SCORE_KEY_MANAGER: _round2(values.get(SCORE_KEY_MANAGER)),
      SCORE_KEY_PEER: _round2(values.get(SCORE_KEY_PEER)),
      SCORE_KEY_TEAM: _round2(values.get(SCORE_KEY_TEAM)),
      'others_score': _round2(values.get('others_score')),
      'avg_score': _round2(values.get('avg_score')),
    })

  report.set('question_summary', [])
  for values in (leader_data.get('question_summary') or []):
    report.append('question_summary', {
      'question_text': values.get('question_text'),
      'question_dimension': values.get('question_dimension'),
      SCORE_KEY_SELF: _round2(values.get(SCORE_KEY_SELF)),
      SCORE_KEY_MANAGER: _round2(values.get(SCORE_KEY_MANAGER)),
      SCORE_KEY_PEER: _round2(values.get(SCORE_KEY_PEER)),
      SCORE_KEY_TEAM: _round2(values.get(SCORE_KEY_TEAM)),
      'others_score': _round2(values.get('others_score')),
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