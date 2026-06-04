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
            value = resp['answer_converted']
            question = resp['question']
            
            # Get question metadata to check if it's an open question
            question_info = questions_metadata.get(question, {})
            dimension = question_info.get('dimension') or 'Sin Dimensión'
            theme = question_info.get('theme') or 'Sin Tema'
            
            # Skip open-ended questions (dimension = 'Abierta')
            if dimension == 'Abierta':
                continue

            # Add to global scores (using converted 1-5 values)
            all_scores.append(value)

            # Add to question scores
            all_question_scores[question].append(value)

            # Add to theme and dimension scores
            all_theme_scores[theme].append(value)
            all_dimension_scores[dimension].append(value)

            # For engagement index (NPS/ENPS), use original 1-10 values
            if (all_engagement_scores is not None and 
                dimension == 'Índice de Engagement' and 
                theme == 'AMBIENTE LABORAL POSITIVO'):
                all_engagement_scores.append(resp['answer'])  # Original 1-10 value


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
            value = resp['answer_converted']
            scores.append(value)

            # Accumulate scores (already in 1-5 scale)
            theme_scores[theme].append(value)
            dimension_scores[dimension].append(value)
            question_scores[question].append(value)
            dimension_themes[dimension].add(theme)
            
            # Track engagement index scores - use ORIGINAL 1-10 values for ENPS/NPS
            if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                engagement_scores_cutoff.append(resp['answer'])  # Original 1-10 value

    # Calculate cutoff metrics
    cutoff_data['overall_score'] = global_overall_score
    cutoff_data['cutoff_score'] = average(scores)
    cutoff_data['response_rate'] = len(respondent_ids) if respondent_ids else 0
    cutoff_data['_all_scores'] = scores
    
    # Calculate NPS and ENPS for engagement index (using original 1-10 values)
    cutoff_data['nps_cutoff'] = _calculate_nps(engagement_scores_cutoff)
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
    """
    Build culture survey reports using batch processing.
    
    This version processes responses in batches to handle large datasets without timeouts.
    
    Args:
        survey_id: ID of the qp_IQ_Survey
        demographic_field: Field name to group by (e.g., 'custom_department')
        batch_size: Optional override for batch size (default: 1000)
        async_mode: If True, process in background; if False, process synchronously
    
    Returns:
        progress_doc_name if successful, False if skipped
    """
    logger = _get_logger()
    logger.info('build_cultura_report_batched start | survey_id=%s batch_size=%s async_mode=%s', survey_id, batch_size, async_mode)
    
    try:
        # Get the survey doc
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        survey_name = survey.su_name
        
        if getattr(survey, 'su_report_generated', 0):
            logger.info('build_cultura_report_batched skipped | survey_id=%s reason=already_generated', survey_id)
            return False
        
        # Get all responses upfront (needed for slicing)
        responses = get_all_responses_for_survey(survey_name)
        if not responses:
            logger.info('build_cultura_report_batched skipped | survey_id=%s reason=no_responses', survey_id)
            return False
        
        # Get demographic groups
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
        
        # Create progress tracking document
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
    """
    Worker function for processing a single batch of responses.
    
    This is called for each batch (either sync or async via enqueue).
    
    Args:
        survey_id: Survey ID
        progress_name: Name of qp_IQ_Report_Progress document
        batch_num: Which batch number (0-indexed)
        batch_size: Size of each batch
        survey_name: Name of the survey
        demographic_field: Field to group by
        respondents_by_demographic: JSON string of demographic groups
        all_responses: JSON string of all responses
    """
    logger = _get_logger()
    logger.info('process_cultura_batch_worker start | survey_id=%s batch_num=%s', survey_id, batch_num)
    
    try:
        from liseniq.batch_processor import BatchProcessor, serialize_accumulated_data, deserialize_accumulated_data
        
        # Deserialize the data
        respondents_by_demo = json.loads(respondents_by_demographic)
        all_responses_list = json.loads(all_responses)
        
        # Get the slice for this batch
        processor = BatchProcessor(survey_id, 'iqCultura', batch_size=batch_size, async_mode=False)
        batch_responses = processor.get_batch_slice(all_responses_list, batch_num)
        
        if not batch_responses:
            logger.info('process_cultura_batch_worker empty batch | batch_num=%s', batch_num)
            return
        
        # Get metadata once
        questions_metadata = get_question_metadata(survey_id)
        responses_by_respondent = get_responses_by_respondent(survey_name)
        
        # Process this batch of responses and accumulate raw values
        accumulated_data = _accumulate_cultura_batch(
            batch_responses,
            respondents_by_demo,
            questions_metadata,
            batch_num,
            survey_id
        )
        
        # Store accumulated data in progress document
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        
        # Deserialize existing accumulated data
        existing_accumulated = deserialize_accumulated_data(progress_doc.accumulated_data)
        
        # Merge with new batch data
        _merge_accumulated_data(existing_accumulated, accumulated_data)
        
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


def _accumulate_cultura_batch(batch_responses, respondents_by_demographic, questions_metadata, batch_num, survey_id):
    """
    Accumulate raw scores from a batch of responses.
    
    Returns a dict with raw values (not averages) that can be merged with other batches.
    """
    logger = _get_logger()
    
    accumulated = {
        'all_scores': [],
        'theme_scores': defaultdict(list),
        'dimension_scores': defaultdict(list),
        'question_scores': defaultdict(list),
        'engagement_scores': [],
        'demographic_cutoff_data': {},
    }
    
    # Normalize responses for this batch
    normalized_responses = normalize_responses(batch_responses)
    
    # Process each response in the batch
    for response_name, resp_list in normalized_responses.items():
        for resp in resp_list:
            if resp['answer_type'] == 'text':
                continue
            
            value = resp['answer_converted']  # 1-5 scale
            question = resp['question']
            
            question_info = questions_metadata.get(question, {})
            dimension = question_info.get('dimension') or 'Sin Dimensión'
            theme = question_info.get('theme') or 'Sin Tema'
            
            # Skip open-ended questions
            if dimension == 'Abierta':
                continue
            
            # Add to global scores (using converted 1-5 values)
            accumulated['all_scores'].append(value)
            accumulated['question_scores'][question].append(value)
            accumulated['theme_scores'][theme].append(value)
            accumulated['dimension_scores'][dimension].append(value)
            
            # For engagement index, use original 1-10 values
            if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                accumulated['engagement_scores'].append(resp['answer'])
    
    # Also process by demographic cutoff for this batch
    for demographic_value, respondent_ids in respondents_by_demographic.items():
        cutoff_responses = []
        for r in batch_responses:
            user_field = r.get('user') if isinstance(r, dict) else r.user
            if user_field in respondent_ids:
                cutoff_responses.append(r)
        
        if not cutoff_responses:
            continue
        
        # Accumulate scores by demographic cutoff
        if demographic_value not in accumulated['demographic_cutoff_data']:
            accumulated['demographic_cutoff_data'][demographic_value] = {
                'scores': [],
                'theme_scores': defaultdict(list),
                'dimension_scores': defaultdict(list),
                'question_scores': defaultdict(list),
                'engagement_scores': [],
                'respondent_ids': set(respondent_ids),
            }
        
        cutoff_data = accumulated['demographic_cutoff_data'][demographic_value]
        normalized_cutoff = normalize_responses(cutoff_responses)
        
        for response_name, resp_list in normalized_cutoff.items():
            for resp in resp_list:
                if resp['answer_type'] == 'text':
                    continue
                
                value = resp['answer_converted']
                question = resp['question']
                
                question_info = questions_metadata.get(question, {})
                dimension = question_info.get('dimension') or 'Sin Dimensión'
                theme = question_info.get('theme') or 'Sin Tema'
                
                if dimension == 'Abierta':
                    continue
                
                cutoff_data['scores'].append(value)
                cutoff_data['question_scores'][question].append(value)
                cutoff_data['theme_scores'][theme].append(value)
                cutoff_data['dimension_scores'][dimension].append(value)
                
                if dimension == 'Índice de Engagement' and theme == 'AMBIENTE LABORAL POSITIVO':
                    cutoff_data['engagement_scores'].append(resp['answer'])
    
    return accumulated


def _merge_accumulated_data(target, source):
    """Merge source accumulated data into target (in-place)."""
    # Merge global scores
    if 'all_scores' in source:
        if 'all_scores' not in target:
            target['all_scores'] = []
        target['all_scores'].extend(source['all_scores'])
    
    # Merge theme, dimension, question scores
    for key in ['theme_scores', 'dimension_scores', 'question_scores']:
        if key in source:
            if key not in target:
                target[key] = defaultdict(list)
            for name, values in source[key].items():
                target[key][name].extend(values)
    
    # Merge engagement scores
    if 'engagement_scores' in source:
        if 'engagement_scores' not in target:
            target['engagement_scores'] = []
        target['engagement_scores'].extend(source['engagement_scores'])
    
    # Merge demographic cutoff data
    if 'demographic_cutoff_data' in source:
        if 'demographic_cutoff_data' not in target:
            target['demographic_cutoff_data'] = {}
        
        for demo_value, demo_data in source['demographic_cutoff_data'].items():
            if demo_value not in target['demographic_cutoff_data']:
                target['demographic_cutoff_data'][demo_value] = {
                    'scores': [],
                    'theme_scores': defaultdict(list),
                    'dimension_scores': defaultdict(list),
                    'question_scores': defaultdict(list),
                    'engagement_scores': [],
                    'respondent_ids': set(),
                }
            
            target_demo = target['demographic_cutoff_data'][demo_value]
            target_demo['scores'].extend(demo_data['scores'])
            target_demo['engagement_scores'].extend(demo_data['engagement_scores'])
            
            # Ensure respondent_ids is always a set
            if isinstance(demo_data['respondent_ids'], set):
                target_demo['respondent_ids'].update(demo_data['respondent_ids'])
            else:
                target_demo['respondent_ids'].update(set(demo_data['respondent_ids']))
            
            for name, values in demo_data['theme_scores'].items():
                target_demo['theme_scores'][name].extend(values)
            for name, values in demo_data['dimension_scores'].items():
                target_demo['dimension_scores'][name].extend(values)
            for name, values in demo_data['question_scores'].items():
                target_demo['question_scores'][name].extend(values)


def finalize_cultura_reports_from_batches(survey_id, progress_name):
    """
    Finalize report generation after all batches are processed.
    
    This calculates final metrics from accumulated raw values and creates all report documents.
    """
    logger = _get_logger()
    logger.info('finalize_cultura_reports_from_batches start | survey_id=%s progress_name=%s', survey_id, progress_name)
    
    try:
        from liseniq.batch_processor import deserialize_accumulated_data
        
        progress_doc = frappe.get_doc('qp_IQ_Report_Progress', progress_name)
        survey = frappe.get_doc('qp_IQ_Survey', survey_id)
        survey_name = survey.su_name
        
        # Deserialize accumulated data
        accumulated_data = deserialize_accumulated_data(progress_doc.accumulated_data)
        
        if not accumulated_data or not accumulated_data.get('all_scores'):
            logger.info('finalize_cultura_reports_from_batches | no accumulated data found')
            return False
        
        # Calculate global metrics
        questions_metadata = get_question_metadata(survey_id)
        
        global_overall_score = average(accumulated_data.get('all_scores', []))
        global_theme_scores = {
            theme: average(scores)
            for theme, scores in accumulated_data.get('theme_scores', {}).items()
        }
        global_dimension_scores = {
            dim: average(scores)
            for dim, scores in accumulated_data.get('dimension_scores', {}).items()
        }
        global_question_scores = {
            q: average(scores)
            for q, scores in accumulated_data.get('question_scores', {}).items()
        }
        global_nps_org = _calculate_nps(accumulated_data.get('engagement_scores', []))
        global_enps_org = _calculate_enps(accumulated_data.get('engagement_scores', []))
        
        logger.info(
            'global metrics calculated | overall_score=%s themes=%s dimensions=%s questions=%s',
            global_overall_score,
            len(global_theme_scores),
            len(global_dimension_scores),
            len(global_question_scores),
        )
        
        # Resolve previous survey for trend
        previous_survey_name = _resolve_previous_comparable_survey_name(survey)
        
        # Build reports for each demographic cutoff
        reports_count = 0
        for demographic_value, cutoff_data in accumulated_data.get('demographic_cutoff_data', {}).items():
            try:
                logger.info(
                    'processing demographic cutoff from batches | cutoff=%s respondents=%s',
                    demographic_value,
                    len(cutoff_data.get('respondent_ids', set())),
                )
                
                # Calculate cutoff metrics from accumulated raw values
                cutoff_input = {
                    'demographic_value': demographic_value,
                    'total_respondents': len(cutoff_data.get('respondent_ids', set())),
                    'overall_score': global_overall_score,
                    'cutoff_score': average(cutoff_data.get('scores', [])),
                    'response_rate': len(cutoff_data.get('respondent_ids', set())),
                    'nps_cutoff': _calculate_nps(cutoff_data.get('engagement_scores', [])),
                    'enps_cutoff': _calculate_enps(cutoff_data.get('engagement_scores', [])),
                    'nps_org': global_nps_org,
                    'enps_org': global_enps_org,
                    'theme_summary': {},
                    'dimension_summary': {},
                    'question_summary': [],
                    'open_questions_answers': {},
                }
                
                # Build theme summary from accumulated scores
                for theme, values in cutoff_data.get('theme_scores', {}).items():
                    theme_avg = average(values)
                    global_avg = global_theme_scores.get(theme)
                    cutoff_input['theme_summary'][theme] = {
                        'avg_score': theme_avg,
                        'overall_avg_score': global_avg,
                        'gap': (theme_avg - global_avg) if (theme_avg and global_avg) else None,
                        'trend_delta': None,
                    }
                
                # Build dimension summary from accumulated scores
                for dimension, values in cutoff_data.get('dimension_scores', {}).items():
                    dim_avg = average(values)
                    global_avg = global_dimension_scores.get(dimension)
                    cutoff_input['dimension_summary'][dimension] = {
                        'avg_score': dim_avg,
                        'overall_avg_score': global_avg,
                        'gap': (dim_avg - global_avg) if (dim_avg and global_avg) else None,
                        'trend_delta': None,
                        'theme_name': ', '.join(sorted(
                            set(questions_metadata.get(q, {}).get('theme', 'Sin Tema')
                                for q in cutoff_data.get('question_scores', {}))
                        )),
                    }
                
                # Build question summary from accumulated scores
                for question, values in cutoff_data.get('question_scores', {}).items():
                    q_avg = average(values)
                    question_info = questions_metadata.get(question, {})
                    theme = question_info.get('theme') or 'Sin Tema'
                    dimension = question_info.get('dimension') or 'Sin Dimensión'
                    global_avg = global_question_scores.get(question)
                    
                    cutoff_input['question_summary'].append({
                        'question_name': question_info.get('text', question),
                        'dimension_name': dimension,
                        'theme_name': theme,
                        'avg_score': q_avg,
                        'overall_avg_score': global_avg,
                        'gap': (q_avg - global_avg) if (q_avg and global_avg) else None,
                        'trend_delta': None,
                    })
                
                # Get demographic field name
                demographic_field = progress_doc.demographic_field or 'custom_department'
                
                # Build the report
                report = build_cultura_culture_report(
                    cutoff_input,
                    survey_name,
                    demographic_field,
                    demographic_value
                )
                
                if report:
                    reports_count += 1
                
            except Exception as e:
                logger.error(f'Error procesando cutoff {demographic_value}: {type(e).__name__}: {str(e)}')
                logger.exception('Stack trace:')
                continue
        
        # Mark survey as report generated
        frappe.db.set_value('qp_IQ_Survey', survey_id, 'su_report_generated', 1, update_modified=False)
        frappe.db.commit()
        
        logger.info('finalize_cultura_reports_from_batches end | reports_generated=%s', reports_count)
        return True
        
    except Exception as e:
        logger.error(f'Error en finalize_cultura_reports_from_batches: {type(e).__name__}: {str(e)}')
        logger.exception('Stack trace:')
        raise
