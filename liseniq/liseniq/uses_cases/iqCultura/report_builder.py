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
    convert_score_10_to_5,
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


def _calculate_nps(scores):
    """Calculate NPS as simple average of scores."""
    if not scores:
        return None
    scores_scale_1_to_5 = [convert_score_10_to_5(s) for s in scores if isinstance(s, (int, float))]
    return average(scores_scale_1_to_5)


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
    enps_engagement_scores = []

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
        enps_engagement_scores,
    )

    # Calculate global averages
    global_overall_score = average(all_scores)
    global_theme_scores = {theme: average(scores) for theme, scores in all_theme_scores.items()}
    global_dimension_scores = {dim: average(scores) for dim, scores in all_dimension_scores.items()}
    global_question_scores = {q: average(scores) for q, scores in all_question_scores.items()}
    global_nps_org = _calculate_nps(all_engagement_scores)
    global_enps_org = _calculate_enps(enps_engagement_scores)

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
            cutoff_responses = []
            for r in responses:
                # Handle both dict (from history) and object responses
                user_field = r.get('user') if isinstance(r, dict) else r.user
                name_field = r.get('name') if isinstance(r, dict) else r.name
                
                if user_field in respondent_ids:
                    cutoff_responses.append(r)
                    continue
                
                # Check in responses_by_respondent
                for resp_name, resp_list in responses_by_respondent.items():
                    if resp_name in respondent_ids or any(
                        (rr.get('user') if isinstance(rr, dict) else rr.user) in respondent_ids
                        for rr in resp_list
                    ):
                        if name_field == resp_name or user_field == resp_name:
                            cutoff_responses.append(r)
                            break


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
    enps_engagement_scores=None,
):
    """Process all responses to calculate global metrics.
    
    Uses answer_converted (1-5 scale) for all metrics.
    Uses answer (original 1-10 scale) ONLY for ENPS/NPS calculations.
    """
    normalized_responses = normalize_responses(responses)

    for response_name, resp_list in normalized_responses.items():
        for resp in resp_list:
            if resp['answer_type'] == 'text':
                continue

            # Use converted value (1-5 scale) for metrics
            value = resp['answer']
            question = resp['question']
            
            # Get question metadata to check if it's an open question
            question_info = questions_metadata.get(question, {})
            dimension = question_info.get('dimension') or 'Sin Dimensión'
            theme = question_info.get('theme') or 'Sin Tema'
            
            # Skip open-ended questions (dimension = 'Abierta')
            if dimension == 'Abierta':
                continue
            if dimension == 'Índice de Engagement':
                value = resp['answer_converted']
            # Add to global scores (using converted 1-5 values)
            all_scores.append(value)

            # Add to question scores
            all_question_scores[question].append(value)

            # Add to theme and dimension scores
            all_theme_scores[theme].append(value)
            all_dimension_scores[dimension].append(value)

            # For engagement index (NPS/ENPS), use original 1-10 values
            if (enps_engagement_scores is not None and 
                dimension == 'Índice de Engagement' and 
                theme == 'AMBIENTE LABORAL POSITIVO'):
                enps_engagement_scores.append(resp['answer'])  # Original 1-10 value

            if all_engagement_scores is not None and dimension == 'Índice de Engagement':
                all_engagement_scores.append(resp['answer_converted'])  


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
    engagement_scores_cutoff = []  
    engagement_scores_cutoff_converted = [] 

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

            # Use converted value (1-5 scale) for all metrics
            value = resp['answer']
            if dimension == 'Índice de Engagement':
                value = resp['answer_converted']
            scores.append(value)

            # Accumulate scores (already in 1-5 scale)
            theme_scores[theme].append(value)
            dimension_scores[dimension].append(value)
            question_scores[question].append(value)
            dimension_themes[dimension].add(theme)
            

            if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                engagement_scores_cutoff.append(resp['answer'])  
            
            if dimension == 'Índice de Engagement':
                engagement_scores_cutoff_converted.append(value)

    # Calculate cutoff metrics
    cutoff_data['overall_score'] = global_overall_score
    cutoff_data['cutoff_score'] = average(scores)
    cutoff_data['response_rate'] = len(respondent_ids) if respondent_ids else 0
    cutoff_data['_all_scores'] = scores
    
    # Calculate NPS and ENPS for engagement index (using original 1-10 values)
    cutoff_data['nps_cutoff'] = _calculate_nps(engagement_scores_cutoff_converted)
    cutoff_data['enps_cutoff'] = _calculate_enps(engagement_scores_cutoff)
    cutoff_data['nps_org'] = global_nps_org
    cutoff_data['enps_org'] = global_enps_org

    # Theme summary (values already in 1-5 scale, no conversion needed)
    cutoff_data['theme_summary'] = {}
    for theme, values in theme_scores.items():
        # Values are already in 1-5 scale from normalize_responses
        theme_avg = average(values)
        
        # Global average is also in 1-5 scale
        global_avg = global_theme_scores.get(theme)
        
        cutoff_data['theme_summary'][theme] = {
            'avg_score': theme_avg,
            'overall_avg_score': global_avg,
            'gap': (theme_avg - global_avg) if (theme_avg and global_avg) else None,
            'trend_delta': None,  # Will be calculated if there's a previous report
        }

    # Dimension summary (values already in 1-5 scale, no conversion needed)
    cutoff_data['dimension_summary'] = {}
    for dimension, values in dimension_scores.items():
        # Values are already in 1-5 scale from normalize_responses
        dim_avg = average(values)
        
        # Global average is also in 1-5 scale
        global_avg = global_dimension_scores.get(dimension)
        
        cutoff_data['dimension_summary'][dimension] = {
            'avg_score': dim_avg,
            'overall_avg_score': global_avg,
            'gap': (dim_avg - global_avg) if (dim_avg and global_avg) else None,
            'trend_delta': None,
            'theme_name': ', '.join(sorted(dimension_themes.get(dimension, []))),
        }

    # Question summary (values already in 1-5 scale, no conversion needed)
    cutoff_data['question_summary'] = []
    for question, values in question_scores.items():
        # Values are already in 1-5 scale from normalize_responses
        q_avg = average(values)
        
        question_info = questions_metadata.get(question, {})
        theme = question_info.get('theme') or 'Sin Tema'
        dimension = question_info.get('dimension') or 'Sin Dimensión'
        
        # Global average is also in 1-5 scale
        global_avg = global_question_scores.get(question)

        previous_score = previous_cutoff_data.get(question_info.get('text', question))
        trend_delta = None
        if previous_score is not None and q_avg is not None:
            trend_delta = q_avg - previous_score

        cutoff_data['question_summary'].append({
            'question_name': question_info.get('text', question),
            'dimension_name': dimension,
            'theme_name': theme,
            'avg_score': q_avg,
            'overall_avg_score': global_avg,
            'gap': (q_avg - global_avg) if (q_avg and global_avg) else None,
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


# ============================================================================
# BATCH PROCESSING IMPLEMENTATION
# ============================================================================

def build_cultura_report_batched(survey_id, demographic_field, batch_size=None, async_mode=True):
    logger = _get_logger()
    logger.info('build_cultura_report_batched start | survey_id=%s batch_size=%s async_mode=%s', survey_id, batch_size, async_mode)
    
    try:
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        survey_name = survey.su_name
        
        if getattr(survey, 'su_report_generated', 0):
            logger.info('build_cultura_report_batched skipped | survey_id=%s reason=already_generated', survey_id)
            return False
        
        responses = get_all_responses_for_survey(survey_name)
        if not responses:
            logger.info('build_cultura_report_batched skipped | survey_id=%s reason=no_responses', survey_id)
            return False
        
        
        respondents_by_demographic = get_respondents_by_demographic(survey_id, demographic_field)
        if not respondents_by_demographic:
            logger.info('build_cultura_report_batched skipped | survey_id=%s reason=no_demographic_data', survey_id)
            return False
        
        logger.info(
            'batch processing initialized | survey=%s responses=%s demographics=%s batch_size=%s',
            survey_name,
            len(responses),
            len(respondents_by_demographic),
            batch_size or 1000
        )
        

        from liseniq.batch_processor import BatchProcessor
        processor = BatchProcessor(survey_id, 'iqCultura', batch_size=batch_size, async_mode=async_mode)
        
        progress_name = processor.start_batch_processing(
            total_responses=len(responses),
            callback_method=process_cultura_batch_worker,
            survey_name=survey_name,
            demographic_field=demographic_field,
            respondents_by_demographic=json.dumps(respondents_by_demographic, default=str),
            all_responses=json.dumps(responses, default=str),
        )
        
        return progress_name
        
    except Exception as e:
        logger.error(f'Error en build_cultura_report_batched: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        return False


def process_cultura_batch_worker(survey_id, progress_name, batch_num, batch_size, survey_name, demographic_field, respondents_by_demographic, all_responses):
    logger = _get_logger()
    logger.info('process_cultura_batch_worker start | survey_id=%s batch_num=%s', survey_id, batch_num)
    
    try:
        from liseniq.batch_processor import BatchProcessor, serialize_accumulated_data, deserialize_accumulated_data
        
        respondents_by_demo = json.loads(respondents_by_demographic)
        all_responses_list = json.loads(all_responses)
        
        processor = BatchProcessor(survey_id, 'iqCultura', batch_size=batch_size, async_mode=False)
        batch_responses = processor.get_batch_slice(all_responses_list, batch_num)
        
        if not batch_responses:
            logger.info('process_cultura_batch_worker empty batch | batch_num=%s', batch_num)
            return
        
        questions_metadata = get_question_metadata(survey_id)
        
        accumulated_data = _accumulate_cultura_batch(batch_responses, questions_metadata)
        
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        existing_accumulated = deserialize_accumulated_data(progress_doc.accumulated_data)
        
        _merge_accumulated_data(existing_accumulated, accumulated_data)
        
        progress_doc.accumulated_data = serialize_accumulated_data(existing_accumulated)
        progress_doc.save(ignore_permissions=True)
        
        _update_demographic_reports_from_batch(
            batch_responses=batch_responses,
            respondents_by_demo=respondents_by_demo,
            questions_metadata=questions_metadata,
            survey_name=survey_name,
            demographic_field=demographic_field,
            progress_name=progress_name
        )
        
        BatchProcessor.update_batch_progress(
            progress_name,
            batch_num,
            len(batch_responses),
            status='in_progress'
        )
        
        logger.info('process_cultura_batch_worker completed | batch_num=%s responses_processed=%s', batch_num, len(batch_responses))

        from liseniq.batch_processor import BatchProcessor
        
        BatchProcessor.finalize_batch_processing(
            progress_name=progress_name,
            finalize_callback=finalize_cultura_reports_from_batches
        )
        
        logger.info('process_cultura_batch_worker completed | batch_num=%s responses_processed=%s', batch_num, len(batch_responses))

    except Exception as e:
        logger.error(f'Error en process_cultura_batch_worker: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        BatchProcessor.update_batch_progress(
            progress_name,
            batch_num,
            0,
            status='failed',
            error=str(e)
        )
        raise

def _accumulate_cultura_batch(batch_responses, questions_metadata):
  
    def empty_stat(): 
        return {'total': 0.0, 'count': 0}
        
    accumulated = {
        'total_respondents': 0, 
        'global_score': empty_stat(),
        'theme_scores': defaultdict(empty_stat),
        'dimension_scores': defaultdict(empty_stat),
        'question_scores': defaultdict(empty_stat),
        'engagement_scores': empty_stat(),
        'enps_promoters': empty_stat(),
        'enps_detractors': empty_stat(),
    }
    
    normalized_responses = normalize_responses(batch_responses)
    
    accumulated['total_respondents'] = len(normalized_responses)
    
    for response_name, resp_list in normalized_responses.items():
        for resp in resp_list:
            if resp.get('answer_type') == 'text':
                continue
            
            value = resp.get('answer') 
            question = resp.get('question')
            
            question_info = questions_metadata.get(question, {})
            dimension = question_info.get('dimension') or 'Sin Dimensión'
            theme = question_info.get('theme') or 'Sin Tema'
            
            if dimension == 'Abierta':
                continue
            
            if dimension == 'Índice de Engagement':
                value = resp.get('answer_converted')

            accumulated['global_score']['total'] += value
            accumulated['global_score']['count'] += 1
            
 
            accumulated['question_scores'][question]['total'] += value
            accumulated['question_scores'][question]['count'] += 1
            
            accumulated['theme_scores'][theme]['total'] += value
            accumulated['theme_scores'][theme]['count'] += 1
            
            accumulated['dimension_scores'][dimension]['total'] += value
            accumulated['dimension_scores'][dimension]['count'] += 1
            
         
            if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                original_value = resp.get('answer')  
                if original_value is not None:
                    if original_value >= 9:
                        accumulated['enps_promoters']['total'] += 1
                        accumulated['enps_promoters']['count'] += 1 
                    elif original_value <= 6:
                        accumulated['enps_detractors']['total'] += 1
                        accumulated['enps_detractors']['count'] += 1

            
            if dimension == 'Índice de Engagement':
                accumulated['engagement_scores']['total'] += value
                accumulated['engagement_scores']['count'] += 1

    return accumulated
   

def _merge_accumulated_data(target, source):
    
    def merge_stat_nodes(target_node, source_node):
        if 'total' not in target_node:
            target_node['total'] = 0.0
        if 'count' not in target_node:
            target_node['count'] = 0
            
        target_node['total'] += source_node.get('total', 0.0)
        target_node['count'] += source_node.get('count', 0)


    if 'global_score' in source:
        if 'global_score' not in target:
            target['global_score'] = {'total': 0.0, 'count': 0}
        merge_stat_nodes(target['global_score'], source['global_score'])

    if 'engagement_scores' in source:
        if 'engagement_scores' not in target:
            target['engagement_scores'] = {'total': 0.0, 'count': 0}
        merge_stat_nodes(target['engagement_scores'], source['engagement_scores'])

    if 'total_respondents' in source:
        target['total_respondents'] = target.get('total_respondents', 0) + source['total_respondents']

    if 'enps_promoters' in source:
        if 'enps_promoters' not in target: target['enps_promoters'] = {'total': 0.0, 'count': 0}
        target['enps_promoters']['total'] += source['enps_promoters']['total']
        target['enps_promoters']['count'] += source['enps_promoters']['count']

    if 'enps_detractors' in source:
        if 'enps_detractors' not in target: target['enps_detractors'] = {'total': 0.0, 'count': 0}
        target['enps_detractors']['total'] += source['enps_detractors']['total']
        target['enps_detractors']['count'] += source['enps_detractors']['count']
    for key in ['theme_scores', 'dimension_scores', 'question_scores']:
        if key in source:
            if key not in target:
                target[key] = {}
                
            for name, source_node in source[key].items():
                if name not in target[key]:
                    target[key][name] = {'total': 0.0, 'count': 0}
                merge_stat_nodes(target[key][name], source_node)


def _update_demographic_reports_from_batch(batch_responses, respondents_by_demo, questions_metadata, survey_name, demographic_field, progress_name):
   
    responses_by_cutoff = defaultdict(list)
    
    user_to_demo_map = {}
    for demo_value, user_ids in respondents_by_demo.items():
        for uid in user_ids:
            user_to_demo_map[uid] = demo_value

    for r in batch_responses:
        user_field = r.get('user') if isinstance(r, dict) else getattr(r, 'user', None)
        demo_value = user_to_demo_map.get(user_field, 'Sin clasificar')
        responses_by_cutoff[demo_value].append(r)

    for demo_value, cutoff_responses in responses_by_cutoff.items():
        expected_responses_for_cutoff = len(respondents_by_demo.get(demo_value, []))

        report_name = frappe.db.get_value('qp_IQ_Cultura_Report', {
            'survey_name': survey_name,
            'cutoff_name': demo_value,
            'progress_reference': progress_name,
        }, 'name')

        if report_name:
            report_doc = frappe.get_doc('qp_IQ_Cultura_Report', report_name)
        else:

            report_doc = frappe.new_doc('qp_IQ_Cultura_Report')
            report_doc.survey_name = survey_name
            report_doc.cutoff_name = demo_value
            report_doc.demographic_name = frappe.db.get_value('qp_IQ_DemographicType', demographic_field, 'dt_title') or demographic_field
            report_doc.progress_reference = progress_name
            report_doc.total_score_accumulator = 0.0
            report_doc.total_respondents = 0
            report_doc.enps_promotores = 0
            report_doc.enps_detractores = 0
            report_doc.engagement_response_count = 0
            report_doc.engagement_score_accumulator = 0.0
            report_doc.total_responses_processed = 0
            
        normalized_cutoff = normalize_responses(cutoff_responses)
        
        unique_users_in_batch = set()


        open_answers = json.loads(report_doc.open_questions_answers) if getattr(report_doc, 'open_questions_answers', None) else {}

        for response_name, resp_list in normalized_cutoff.items():
            for resp in resp_list:
                
                question = resp.get('question')
                user_field = resp.get('user')
                value = resp.get('answer')
                
                if user_field:
                    unique_users_in_batch.add(user_field)
                
    
                question_info = questions_metadata.get(question, {})
                theme = question_info.get('theme') or 'Sin Tema'
                dimension = question_info.get('dimension') or 'Sin Dimensión'
                question_text = question_info.get('text', question)

                if dimension == 'Índice de Engagement':
                    value = resp.get('answer_converted')
                
                if dimension == 'Abierta':
                    text_val = resp.get('answer')
                    if text_val and str(text_val).strip():
                        if question_text not in open_answers:
                            open_answers[question_text] = []
                        open_answers[question_text].append(text_val)
                    continue
                

                report_doc.total_score_accumulator += value
                if not getattr(report_doc, 'theme_summary', None):
                    report_doc.theme_summary = []
                if not getattr(report_doc, 'dimension_summary', None):
                    report_doc.dimension_summary = []
                if not getattr(report_doc, 'question_summary', None):
                    report_doc.question_summary = []
                theme_row = next((row for row in report_doc.theme_summary if row.theme_name == theme), None)
                if not theme_row:
                    theme_row = report_doc.append('theme_summary', {'theme_name': theme, 'total_score': 0.0, 'response_count': 0})
                theme_row.total_score += value
                theme_row.response_count += 1


                dim_row = next((row for row in report_doc.dimension_summary if row.dimension_name == dimension), None)
                if not dim_row:
                    dim_row = report_doc.append('dimension_summary', {'theme_name': theme, 'dimension_name': dimension, 'total_score': 0.0, 'response_count': 0})
                dim_row.total_score += value
                dim_row.response_count += 1

                q_row = next((row for row in report_doc.question_summary if row.question_name == question_text), None)
                if not q_row:
                    q_row = report_doc.append('question_summary', {'question_name': question_text, 'dimension_name': dimension, 'theme_name': theme, 'total_score': 0.0, 'response_count': 0, 'question_id': question})
                q_row.total_score += value
                q_row.response_count += 1

                if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                    original_value = resp.get('answer')  
                    if original_value is not None:
                        if original_value >= 9:
                            report_doc.enps_promotores += 1
                        elif original_value <= 6:
                            report_doc.enps_detractores += 1

                if dimension == 'Índice de Engagement':
                    report_doc.engagement_response_count += 1
                    report_doc.engagement_score_accumulator = getattr(report_doc, 'engagement_score_accumulator', 0.0) + value
                
                report_doc.total_responses_processed += 1
        report_doc.total_respondents += len(unique_users_in_batch)

        report_doc.response_rate = expected_responses_for_cutoff

        report_doc.open_questions_answers = json.dumps(open_answers, ensure_ascii=False)

        report_doc.save(ignore_permissions=True)


def finalize_cultura_reports_from_batches(survey_id, progress_name):
    """
    Finaliza la generación de reportes tras procesar todos los lotes.
    Calcula las métricas organizacionales finales y actualiza los documentos de cortes existentes.
    """
    logger = _get_logger()
    logger.info('finalize_cultura_reports_from_batches start | survey_id=%s progress_name=%s', survey_id, progress_name)
    
    try:
        from liseniq.batch_processor import deserialize_accumulated_data
        
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        survey_name = survey.su_name
        
        
        accumulated_data = deserialize_accumulated_data(progress_doc.accumulated_data)
        
        # Validación de seguridad adaptada a la nueva estructura
        global_score_data = accumulated_data.get('global_score', {})
        if not accumulated_data or global_score_data.get('count', 0) == 0:
            logger.info('finalize_cultura_reports_from_batches | no organizational data found')
            return False
            
        def _get_avg(node):
            return node['total'] / node['count'] if node and node.get('count', 0) > 0 else 0.0

        global_overall_score = _get_avg(global_score_data)
        
        global_theme_scores = {
            theme: _get_avg(node)
            for theme, node in accumulated_data.get('theme_scores', {}).items()
        }
        global_dimension_scores = {
            dim: _get_avg(node)
            for dim, node in accumulated_data.get('dimension_scores', {}).items()
        }
        global_question_scores = {
            q: _get_avg(node)
            for q, node in accumulated_data.get('question_scores', {}).items()
        }
        
        
        global_nps_org = _get_avg(accumulated_data.get('engagement_scores', {})) 
        total_respondents = accumulated_data.get('total_respondents', 0)
        enps_promoters = accumulated_data.get('enps_promoters', {})
        enps_detractors = accumulated_data.get('enps_detractors', {})
        global_enps_org = calculate_enps_for_batch(total_respondents, enps_promoters, enps_detractors)
        
        logger.info(
            'global metrics calculated | overall_score=%s themes=%s dimensions=%s questions=%s',
            global_overall_score, len(global_theme_scores), len(global_dimension_scores), len(global_question_scores)
        )
        
        previous_survey_name = _resolve_previous_comparable_survey_name(survey)
        
        reports = frappe.get_all('qp_IQ_Cultura_Report', 
            filters={'progress_reference': progress_name}, 
            fields=['name', 'cutoff_name']
        )
        
        reports_count = 0
        
        for r_info in reports:
            try:
                report_doc = frappe.get_doc('qp_IQ_Cultura_Report', r_info['name'])
                
                logger.info(
                    'Finalizing metrics for demographic cutoff | cutoff=%s respondents=%s',
                    report_doc.cutoff_name, report_doc.total_respondents
                )
                
             
                report_doc.overall_score = round(global_overall_score, 2)
                report_doc.nps_org = round(global_nps_org, 2)
                report_doc.enps_org = round(global_enps_org, 2)
                report_doc.enps_cutoff = calculate_enps_for_batch(report_doc.total_respondents, {'total': report_doc.enps_promotores}, {'total': report_doc.enps_detractores})
                engagement_response_count = getattr(report_doc, 'engagement_response_count', 0)
                engagement_score_accumulator = getattr(report_doc, 'engagement_score_accumulator', 0.0)
                report_doc.nps_cutoff = round(engagement_score_accumulator / engagement_response_count, 2) if engagement_response_count > 0 else 0.0
                
                total_accumulated = getattr(report_doc, 'total_score_accumulator', 0.0)
                total_resp = getattr(report_doc, 'total_responses_processed', 0)
                report_doc.cutoff_score = round(total_accumulated / total_resp, 2) if total_resp > 0 else 0.0
                
               
                for row in report_doc.theme_summary:
                    t_score = getattr(row, 'total_score', 0.0)
                    t_count = getattr(row, 'response_count', 0)
                    
                    row.avg_score = round(t_score / t_count, 2) if t_count > 0 else 0.0
                    row.overall_avg_score = round(global_theme_scores.get(row.theme_name, 0.0), 2)
                    row.gap = round(row.avg_score - row.overall_avg_score, 2)
                    row.trend_delta = None 
                

                for row in report_doc.dimension_summary:
                    d_score = getattr(row, 'total_score', 0.0)
                    d_count = getattr(row, 'response_count', 0)
                    
                    row.avg_score = round(d_score / d_count, 2) if d_count > 0 else 0.0
                    row.overall_avg_score = round(global_dimension_scores.get(row.dimension_name, 0.0), 2)
                    row.gap = round(row.avg_score - row.overall_avg_score, 2)
                    row.trend_delta = None
                

                for row in report_doc.question_summary:
                    q_score = getattr(row, 'total_score', 0.0)
                    q_count = getattr(row, 'response_count', 0)
                    
                    row.avg_score = round(q_score / q_count, 2) if q_count > 0 else 0.0
                    row.overall_avg_score = round(global_question_scores.get(row.question_id, 0.0), 2)
                    row.gap = round(row.avg_score - row.overall_avg_score, 2)
                    row.trend_delta = None
                

                report_doc.save(ignore_permissions=True)
                reports_count += 1
                
            except Exception as e:
                logger.error(f'Error finalizando reporte {r_info["cutoff_name"]}: {type(e).__name__}: {str(e)}')
                logger.exception('Stack trace:')
                continue
                

        frappe.db.set_value('qp_IQ_Survey', survey_id, 'su_report_generated', 1, update_modified=False)
        frappe.db.commit()
        
        logger.info('finalize_cultura_reports_from_batches end | reports_finalized=%s', reports_count)
        return True
        
    except Exception as e:
        logger.error(f'Error en finalize_cultura_reports_from_batches: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        raise

def calculate_enps_for_batch(total_responses, enps_promoters, enps_detractors):
    """
    Calcula el ENPS para un batch específico usando los contadores de promotores y detractores.
    """
    try:
        promoters_count = enps_promoters.get('total', 0)
        detractors_count = enps_detractors.get('total', 0)
        
        if total_responses == 0:
            return 0.0
        
        promoters_percentage = (promoters_count / total_responses) * 100 
        detractors_percentage = (detractors_count / total_responses) * 100
        nps_score = promoters_percentage - detractors_percentage
        return round(nps_score, 2)
    
    except Exception as e:
        logger = _get_logger()
        logger.error(f'Error calculando ENPS para batch: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        return 0.0