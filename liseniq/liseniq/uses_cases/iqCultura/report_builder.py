import json
import frappe
from collections import defaultdict
from liseniq.liseniq.uses_cases.iqCultura.selectors import (
    get_all_responses_for_survey,
    get_survey_questions,
    get_question_metadata,
    get_respondents_by_demographic,
    get_responses_by_respondent,
)
from liseniq.liseniq.uses_cases.iqCultura.calculations import (
    normalize_responses,
    average,
    std_dev,
    _round2,
)

"""
qp_IQ_Cultura_Report - DocType to store culture survey reports by demographic cutoff.

Fields:
- demographic_name: The demographic cutoff value (e.g., "Finanzas", "Ventas")
- total_respondents: Number of respondents in this demographic cutoff
- cutoff_score: Average score for this demographic cutoff
- cutoff_name: Name of the demographic cutoff
- response_rate: Response rate for this cutoff
- overall_score: Overall average score
- theme_summary: Table with results by theme
  - theme_name
  - avg_score: Average score for this cutoff
  - overall_avg_score: Average score across all cutoffs
  - gap: Difference between cutoff score and overall average
  - trend_delta: Change from previous measurement
- dimension_summary: Table with results by dimension
  - dimension_name
  - theme_name
  - avg_score: Average score for this cutoff
  - overall_avg_score: Average score across all cutoffs
  - gap: Difference between cutoff score and overall average
  - trend_delta: Change from previous measurement
- question_summary: Table with results by question/attribute
  - question_name
  - dimension_name
  - theme_name
  - avg_score: Average score for this cutoff
  - overall_avg_score: Average score across all cutoffs
  - gap: Difference between cutoff score and overall average
  - trend_delta: Change from previous measurement
- open_questions_answers: JSON with open-ended question responses
"""


def _get_logger():
    logger = frappe.logger('iqCultura_report_builder', allow_site=True)
    return logger


def _print_log(msg):
    """Imprime mensaje en logs y stdout para debug"""
    print(f'[iqCultura] {msg}')
    return msg


def _convert_score_10_to_5(score):
    """Convert score from 1-10 scale to 1-5 scale using linear conversion."""
    if score is None:
        return None
    # Linear conversion: (value - 1) / 9 * 4 + 1
    return round((score - 1) / 9 * 4 + 1, 2)


def _calculate_nps(scores):
    """Calculate NPS as simple average of scores."""
    if not scores:
        return None
    return average(scores)


def _calculate_enps(scores):
    """
    Calculate ENPS (Employee Net Promoter Score).
    - Count responses with score 1-6 (detractors)
    - Count responses with score 9-10 (promoters)
    - ENPS = (promoters% - detractors%)
    """
    if not scores:
        return None
    
    total = len(scores)
    if total == 0:
        return None
    
    detractors = sum(1 for s in scores if 1 <= s <= 6)
    promoters = sum(1 for s in scores if 9 <= s <= 10)
    
    detractors_pct = (detractors / total) * 100
    promoters_pct = (promoters / total) * 100
    
    enps = promoters_pct - detractors_pct
    return round(enps, 2)


def build_cultura_report(survey_id, demographic_field):
    """
    Build culture survey reports by demographic cutoff.
    
    Args:
        survey_id: ID of the qp_IQ_Survey
        demographic_field: Field name to group by (e.g., 'custom_department', 'custom_area')
    
    Returns:
        Boolean indicating if reports were generated successfully
    """
    logger = _get_logger()
    logger.info('build_cultura_report start | survey_id=%s demographic_field=%s', survey_id, demographic_field)
    print(f'\\n[iqCultura DEBUG] build_cultura_report start | survey_id={survey_id} demographic_field={demographic_field}')

    try:
        # Get the survey doc
        print('[iqCultura DEBUG] Obteniendo survey...')
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        survey_name = survey.su_name
        logger.info('survey loaded | survey_name=%s', survey_name)
        print(f'[iqCultura DEBUG] Survey cargada: {survey_name}')
        
        if getattr(survey, 'su_report_generated', 0):
            logger.info('build_cultura_report skipped | survey_id=%s reason=already_generated', survey_id)
            return False
        # Get all responses for the survey
        print('[iqCultura DEBUG] Obteniendo respuestas...')
        responses = get_all_responses_for_survey(survey_name)
        logger.info('responses fetched | count=%s', len(responses or []))
        print(f'[iqCultura DEBUG] Respuestas obtenidas: {len(responses or [])}')

        if not responses:
            logger.info('build_cultura_report skipped | survey_id=%s reason=no_responses', survey_id)
            print('[iqCultura DEBUG] Sin respuestas!')
            return False

        # Get respondents grouped by demographic
        print(f'[iqCultura DEBUG] Agrupando por demográfico: {demographic_field}...')
        respondents_by_demographic = get_respondents_by_demographic(survey_id, demographic_field)
        logger.info('respondents grouped by demographic | groups=%s', len(respondents_by_demographic or {}))
        print(f'[iqCultura DEBUG] Grupos demográficos: {len(respondents_by_demographic or {})}')
        
        if respondents_by_demographic:
            print(f'[iqCultura DEBUG] Valores demográficos encontrados: {list(respondents_by_demographic.keys())}')

        if not respondents_by_demographic:
            logger.info('build_cultura_report skipped | survey_id=%s reason=no_demographic_data', survey_id)
            print('[iqCultura DEBUG] ¡Sin datos demográficos!')
            return False
    
    except Exception as e:
        logger.error(f'Error en inicio de build_cultura_report: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        print(f'[iqCultura ERROR] {type(e).__name__}: {str(e)}')
        import traceback
        print(traceback.format_exc())
        return False

    # Get question metadata
    print('[iqCultura DEBUG] Obteniendo metadatos de preguntas...')
    questions_metadata = get_question_metadata(survey_id)
    logger.info('questions metadata loaded | questions=%s', len(questions_metadata or {}))
    print(f'[iqCultura DEBUG] Metadatos de preguntas: {len(questions_metadata or {})}')

    # Get responses grouped by respondent
    print('[iqCultura DEBUG] Agrupando respuestas por respondent...')
    responses_by_respondent = get_responses_by_respondent(survey_name)

    # Calculate global metrics (across all respondents)
    print('[iqCultura DEBUG] Calculando métricas globales...')
    all_scores = []
    all_theme_scores = defaultdict(list)
    all_dimension_scores = defaultdict(list)
    all_question_scores = defaultdict(list)
    all_engagement_scores = []

    # Process all responses to get global metrics
    _process_responses_for_global_metrics(
        responses,
        responses_by_respondent,
        questions_metadata,
        all_scores,
        all_theme_scores,
        all_dimension_scores,
        all_question_scores,
        all_engagement_scores,
    )

    # Calculate global averages
    global_overall_score = average(all_scores)
    global_theme_scores = {theme: average(scores) for theme, scores in all_theme_scores.items()}
    global_dimension_scores = {dim: average(scores) for dim, scores in all_dimension_scores.items()}
    global_question_scores = {q: average(scores) for q, scores in all_question_scores.items()}
    global_nps_org = _calculate_nps(all_engagement_scores)
    global_enps_org = _calculate_enps(all_engagement_scores)

    logger.info(
        'global metrics calculated | overall_score=%s themes=%s dimensions=%s questions=%s',
        global_overall_score,
        len(global_theme_scores),
        len(global_dimension_scores),
        len(global_question_scores),
    )
    print(f'[iqCultura DEBUG] Métricas globales calculadas: overall={global_overall_score}, themes={len(global_theme_scores)}, dims={len(global_dimension_scores)}, questions={len(global_question_scores)}')

    # Get previous comparable survey for trend calculation
    previous_survey_name = _resolve_previous_comparable_survey_name(survey)
    logger.info(
        'previous comparable survey resolved | current_survey=%s previous_survey=%s',
        survey_name,
        previous_survey_name,
    )

    # Build reports for each demographic cutoff
    reports_count = 0
    for demographic_value, respondent_ids in respondents_by_demographic.items():
        try:
            logger.info(
                'processing demographic cutoff | cutoff=%s respondents=%s',
                demographic_value,
                len(respondent_ids),
            )
            print(f'[iqCultura DEBUG] Procesando cutoff: {demographic_value} con {len(respondent_ids)} respondents')

            # Get responses for this demographic cutoff
            cutoff_responses = [
                r for r in responses
                if r.user in respondent_ids or r.name in [
                    resp_name for resp_name, resp_list in responses_by_respondent.items()
                    if responses_by_respondent.get(resp_name) and any(
                        rr.user in respondent_ids for rr in responses_by_respondent.get(resp_name, [])
                    )
                ]
            ]

            print(f'[iqCultura DEBUG] Respuestas para cutoff {demographic_value}: {len(cutoff_responses)}')

            if not cutoff_responses:
                logger.info('demographic cutoff skipped | cutoff=%s reason=no_responses', demographic_value)
                print(f'[iqCultura DEBUG] Sin respuestas para {demographic_value}, saltando...')
                continue

            cutoff_data = process_demographic_cutoff_data(
                survey_id,
                cutoff_responses,
                respondent_ids,
                demographic_value,
                questions_metadata,
                global_overall_score,
                global_theme_scores,
                global_dimension_scores,
                global_question_scores,
                previous_survey_name,
                global_nps_org,
                global_enps_org,
            )

            if not cutoff_data:
                logger.info('demographic cutoff skipped | cutoff=%s reason=empty_data', demographic_value)
                print(f'[iqCultura DEBUG] Sin datos procesados para {demographic_value}, saltando...')
                continue

            # Build or update the report
            print(f'[iqCultura DEBUG] Creando/actualizando reporte para {demographic_value}...')
            report = build_cultura_culture_report(cutoff_data, survey_name, demographic_field, demographic_value)
            logger.info(
                'demographic report persisted | cutoff=%s report=%s',
                demographic_value,
                report.name if report else None,
            )
            print(f'[iqCultura DEBUG] Reporte creado: {report.name if report else "FALLÓ"}')
            
            if report:
                reports_count += 1

        except Exception as e:
            logger.error(f'Error procesando cutoff {demographic_value}: {type(e).__name__}: {str(e)}')
            logger.exception('Stack trace:')
            print(f'[iqCultura ERROR] Error en cutoff {demographic_value}: {type(e).__name__}: {str(e)}')
            import traceback
            print(traceback.format_exc())
            continue

    logger.info('build_cultura_report end | processed_cutoffs=%s', len(respondents_by_demographic))
    print(f'[iqCultura DEBUG] COMPLETADO: {reports_count} reportes generados de {len(respondents_by_demographic)} cutoffs')
    frappe.db.set_value('qp_IQ_Survey', survey_id, 'su_report_generated', 1, update_modified=False)
    frappe.db.commit()
    return True


def _resolve_previous_comparable_survey_name(current_survey):
    """Find previous culture measurement for same company and template."""
    if not current_survey:
        return None

    owner = getattr(current_survey, 'su_owner', None)
    template = getattr(current_survey, 'su_template', None)
    if not owner or not template:
        return None

    current_ts = frappe.utils.get_datetime(
        getattr(current_survey, 'su_end_date', None) or getattr(current_survey, 'creation', None)
    )
    
    candidates = frappe.get_all(
        'qp_IQ_Survey',
        filters={
            'su_owner': owner,
            'su_template': template,
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


def _get_previous_cultura_report_data(demographic_value, previous_survey_name):
    """Get previous report data for a demographic cutoff for trend calculation."""
    if not demographic_value or not previous_survey_name:
        return {}

    report_name = frappe.db.get_value(
        'qp_IQ_Cultura_Report',
        {'demographic_name': demographic_value, 'parent_survey': previous_survey_name},
        'name',
    )
    
    if not report_name:
        return {}

    report = frappe.get_doc('qp_IQ_Cultura_Report', report_name)
    previous_data = {}

    # Map question names to avg_score from previous report
    for row in (report.question_summary or []):
        question_text = row.get('question_name')
        if question_text:
            previous_data[question_text] = row.get('avg_score')

    return previous_data


def _process_responses_for_global_metrics(
    responses,
    responses_by_respondent,
    questions_metadata,
    all_scores,
    all_theme_scores,
    all_dimension_scores,
    all_question_scores,
    all_engagement_scores=None,
):
    """Process all responses to calculate global metrics."""
    normalized_responses = normalize_responses(responses)

    for response_name, resp_list in normalized_responses.items():
        for resp in resp_list:
            if resp['answer_type'] == 'text':
                continue

            value = resp['answer']
            question = resp['question']
            
            # Get question metadata to check if it's an open question
            question_info = questions_metadata.get(question, {})
            dimension = question_info.get('dimension') or 'Sin Dimensión'
            theme = question_info.get('theme') or 'Sin Tema'
            
            # Skip open-ended questions (dimension = 'Abierta')
            if dimension == 'Abierta':
                continue

            # Add to global scores
            all_scores.append(value)

            # Add to question scores
            all_question_scores[question].append(value)

            # Add to theme and dimension scores
            all_theme_scores[theme].append(value)
            all_dimension_scores[dimension].append(value)

            if (all_engagement_scores is not None and 
                dimension == 'Índice de Engagement' and 
                theme == 'AMBIENTE LABORAL POSITIVO'):
                all_engagement_scores.append(value)


def process_demographic_cutoff_data(
    survey_id,
    responses,
    respondent_ids,
    demographic_value,
    questions_metadata,
    global_overall_score,
    global_theme_scores,
    global_dimension_scores,
    global_question_scores,
    previous_survey_name=None,
    global_nps_org=None,
    global_enps_org=None,
):
    """Process data for a specific demographic cutoff."""
    logger = _get_logger()

    if not responses:
        logger.info('process_demographic_cutoff_data empty responses | survey_id=%s cutoff=%s', survey_id, demographic_value)
        return {}

    cutoff_data = {}
    cutoff_data['demographic_value'] = demographic_value
    cutoff_data['total_respondents'] = len(respondent_ids)

    # Get previous report data if available
    previous_cutoff_data = {}
    if previous_survey_name:
        previous_cutoff_data = _get_previous_cultura_report_data(demographic_value, previous_survey_name)

    # Normalize responses
    normalized_responses = normalize_responses(responses)

    # Accumulators for scores by theme, dimension, question
    scores = []
    theme_scores = defaultdict(list)
    dimension_scores = defaultdict(list)
    question_scores = defaultdict(list)
    dimension_themes = defaultdict(set)
    open_questions_answers = defaultdict(list)
    
    # Accumulators for engagement index (NPS/ENPS)
    engagement_scores_cutoff = []  # For this cutoff

    # Process responses for this cutoff
    for response_name, resp_list in normalized_responses.items():
        for resp in resp_list:
            # Get question info first to check if it's an open question
            question = resp['question']
            question_info = questions_metadata.get(question, {})
            dimension = question_info.get('dimension') or 'Sin Dimensión'
            theme = question_info.get('theme') or 'Sin Tema'
            
            # Handle open-ended questions (text or dimension = 'Abierta')
            if resp['answer_type'] == 'text' or dimension == 'Abierta':
                question_text = question_info.get('text', question)
                open_questions_answers[question_text].append(resp['answer'])
                continue

            value = resp['answer']
            scores.append(value)

            # Accumulate scores (only numeric values from non-open questions)
            theme_scores[theme].append(value)
            dimension_scores[dimension].append(value)
            question_scores[question].append(value)
            dimension_themes[dimension].add(theme)
            
            # Track engagement index scores (only AMBIENTE LABORAL POSITIVO theme + Índice de Engagement dimension)
            if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                engagement_scores_cutoff.append(value)

    # Calculate cutoff metrics
    cutoff_data['overall_score'] = global_overall_score
    cutoff_data['cutoff_score'] = average(scores)
    cutoff_data['response_rate'] = len(respondent_ids) if respondent_ids else 0
    cutoff_data['_all_scores'] = scores
    
    # Calculate NPS and ENPS for engagement index
    cutoff_data['nps_cutoff'] = _calculate_nps(engagement_scores_cutoff)
    cutoff_data['enps_cutoff'] = _calculate_enps(engagement_scores_cutoff)
    cutoff_data['nps_org'] = global_nps_org
    cutoff_data['enps_org'] = global_enps_org

    # Theme summary (convert scores to 1-5 scale)
    cutoff_data['theme_summary'] = {}
    for theme, values in theme_scores.items():
        # Convert scores to 1-5 scale for average calculation
        values_converted = [_convert_score_10_to_5(v) for v in values]
        theme_avg = average(values_converted)
        
        # Get global average and convert to 1-5 scale
        global_avg = global_theme_scores.get(theme)
        global_avg_converted = _convert_score_10_to_5(global_avg) if global_avg else None
        
        cutoff_data['theme_summary'][theme] = {
            'avg_score': theme_avg,
            'overall_avg_score': global_avg_converted,
            'gap': (theme_avg - global_avg_converted) if (theme_avg and global_avg_converted) else None,
            'trend_delta': None,  # Will be calculated if there's a previous report
        }

    # Dimension summary (convert scores to 1-5 scale)
    cutoff_data['dimension_summary'] = {}
    for dimension, values in dimension_scores.items():
        # Convert scores to 1-5 scale for average calculation
        values_converted = [_convert_score_10_to_5(v) for v in values]
        dim_avg = average(values_converted)
        
        # Get global average and convert to 1-5 scale
        global_avg = global_dimension_scores.get(dimension)
        global_avg_converted = _convert_score_10_to_5(global_avg) if global_avg else None
        
        cutoff_data['dimension_summary'][dimension] = {
            'avg_score': dim_avg,
            'overall_avg_score': global_avg_converted,
            'gap': (dim_avg - global_avg_converted) if (dim_avg and global_avg_converted) else None,
            'trend_delta': None,
            'theme_name': ', '.join(sorted(dimension_themes.get(dimension, []))),
        }

    # Question summary (convert scores to 1-5 scale)
    cutoff_data['question_summary'] = []
    for question, values in question_scores.items():
        # Convert scores to 1-5 scale for average calculation
        values_converted = [_convert_score_10_to_5(v) for v in values]
        q_avg = average(values_converted)
        
        question_info = questions_metadata.get(question, {})
        theme = question_info.get('theme') or 'Sin Tema'
        dimension = question_info.get('dimension') or 'Sin Dimensión'
        
        # Get global average and convert to 1-5 scale
        global_avg = global_question_scores.get(question)
        global_avg_converted = _convert_score_10_to_5(global_avg) if global_avg else None

        previous_score = previous_cutoff_data.get(question_info.get('text', question))
        trend_delta = None
        if previous_score is not None and q_avg is not None:
            trend_delta = q_avg - previous_score

        cutoff_data['question_summary'].append({
            'question_name': question_info.get('text', question),
            'dimension_name': dimension,
            'theme_name': theme,
            'avg_score': q_avg,
            'overall_avg_score': global_avg_converted,
            'gap': (q_avg - global_avg_converted) if (q_avg and global_avg_converted) else None,
            'trend_delta': trend_delta,
        })

    # Open questions
    cutoff_data['open_questions_answers'] = open_questions_answers

    logger.info(
        'demographic cutoff data processed | cutoff=%s total_respondents=%s overall_score=%s themes=%s dimensions=%s questions=%s',
        demographic_value,
        cutoff_data.get('total_respondents'),
        cutoff_data.get('overall_score'),
        len(cutoff_data.get('theme_summary', {})),
        len(cutoff_data.get('dimension_summary', {})),
        len(cutoff_data.get('question_summary', [])),
    )

    return cutoff_data


def build_cultura_culture_report(cutoff_data, survey_name, demographic_field, demographic_value):
    """Build or update the qp_IQ_Cultura_Report document."""
    logger = _get_logger()

    if not cutoff_data:
        logger.info('build_cultura_culture_report skipped | missing cutoff_data')
        return None

    # Check if report already exists
    report_filters = {'demographic_name': demographic_value, 'survey_name': survey_name}
    if frappe.db.exists('qp_IQ_Cultura_Report', report_filters):
        report = frappe.get_doc('qp_IQ_Cultura_Report', report_filters)
        logger.info('build_cultura_culture_report update | report=%s cutoff=%s', report.name, demographic_value)
    else:
        report = frappe.new_doc('qp_IQ_Cultura_Report')
        logger.info('build_cultura_culture_report create | survey=%s cutoff=%s', survey_name, demographic_value)

    # Set basic fields
    report.survey_name = survey_name
    report.demographic_name = frappe.db.get_value('qp_IQ_DemographicType', demographic_field, 'dt_title') or demographic_field
    report.cutoff_name = demographic_value
    report.survey_name = survey_name
    report.total_respondents = cutoff_data.get('total_respondents')
    report.response_rate = _round2(cutoff_data.get('response_rate'))
    report.overall_score = _round2(cutoff_data.get('overall_score'))
    report.cutoff_score = _round2(cutoff_data.get('cutoff_score'))
    
    # Set NPS and ENPS fields
    report.nps_cutoff = _round2(cutoff_data.get('nps_cutoff'))
    report.enps_cutoff = _round2(cutoff_data.get('enps_cutoff'))
    report.nps_org = _round2(cutoff_data.get('nps_org'))
    report.enps_org = _round2(cutoff_data.get('enps_org'))

    # Set open questions answers as JSON
    open_answers = cutoff_data.get('open_questions_answers') or {}
    report.open_questions_answers = json.dumps(open_answers, ensure_ascii=False)

    # Theme summary table
    report.set('theme_summary', [])
    for theme_name, values in (cutoff_data.get('theme_summary') or {}).items():
        report.append('theme_summary', {
            'theme_name': theme_name,
            'avg_score': _round2(values.get('avg_score')),
            'overall_avg_score': _round2(values.get('overall_avg_score')),
            'gap': _round2(values.get('gap')),
            'trend_delta': _round2(values.get('trend_delta')),
        })

    # Dimension summary table
    report.set('dimension_summary', [])
    for dimension_name, values in (cutoff_data.get('dimension_summary') or {}).items():
        report.append('dimension_summary', {
            'dimension_name': dimension_name,
            'theme_name': values.get('theme_name'),
            'avg_score': _round2(values.get('avg_score')),
            'overall_avg_score': _round2(values.get('overall_avg_score')),
            'gap': _round2(values.get('gap')),
            'trend_delta': _round2(values.get('trend_delta')),
        })

    # Question summary table
    report.set('question_summary', [])
    for values in (cutoff_data.get('question_summary') or []):
        report.append('question_summary', {
            'question_name': values.get('question_name'),
            'dimension_name': values.get('dimension_name'),
            'theme_name': values.get('theme_name'),
            'avg_score': _round2(values.get('avg_score')),
            'overall_avg_score': _round2(values.get('overall_avg_score')),
            'gap': _round2(values.get('gap')),
            'trend_delta': _round2(values.get('trend_delta')),
        })

    # Save or insert the report
    if report.is_new():
        report.insert(ignore_permissions=True)
        logger.info('build_cultura_culture_report inserted | report=%s', report.name)
    else:
        report.save(ignore_permissions=True)
        logger.info('build_cultura_culture_report saved | report=%s', report.name)

    frappe.db.commit()
    return report
