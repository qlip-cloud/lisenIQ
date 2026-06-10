import json
from collections import defaultdict
import math


def safe_float(value):
    """Safely convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def average(values):
    """Calculate average of a list of values"""
    if not values:
        return None
    valid_values = [v for v in values if v is not None]
    return sum(valid_values) / len(valid_values) if valid_values else None


def std_dev(values):
    """Calculate standard deviation of a list of values"""
    if not values or len(values) <= 1:
        return 0
    
    valid_values = [v for v in values if v is not None]
    if len(valid_values) <= 1:
        return 0

    avg = average(valid_values)
    variance = sum((x - avg) ** 2 for x in valid_values) / len(valid_values)
    return math.sqrt(variance)


def _round2(value):
    """Round value to 2 decimal places"""
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return value


def convert_score_10_to_5(score):
    """Convert score from 1-10 scale to 1-5 scale"""
    if score is None:
        return None
    # If already in 1-5 range, return as is
    if score <= 5:
        return score
    # Convert 1-10 to 1-5
    if 1 <= score <= 2:
        return 1
    elif 3 <= score <= 4:
        return 2
    elif 5 <= score <= 6:
        return 3
    elif 7 <= score <= 8:
        return 4
    elif 9 <= score <= 10:
        return 5
    return score


def parse_answer(value):
    """Parse answer and determine if it's a score or text"""
    try:
        return float(value), 'score'
    except (ValueError, TypeError):
        return value, 'text'


def normalize_responses(responses):
    """
    Normalize survey responses from JSON format to structured format.
    Converts numeric answers from 1-10 to 1-5 scale (if needed).
    Returns dict: {response_name: [{question, answer, answer_converted, answer_type, evaluator}, ...]}
    
    Fields:
    - answer: Original value (1-10 scale, used ONLY for ENPS/NPS calculations)
    - answer_converted: Converted to 1-5 scale (used for all other metrics)
    """
    parsed_data = defaultdict(list)

    for response in responses:
        # Handle both dict (from history) and object responses
        if isinstance(response, dict):
            # For historic data, use response_data; for regular, use response_json
            json_text = response.get('response_data') or response.get('response_json')
            user = response.get('user')
            response_name = response.get('name')
            survey = response.get('survey')
        else:
            json_text = response.response_json
            user = response.user
            response_name = response.name
            survey = response.survey
            
        json_data = json.loads(json_text) if json_text else {}
        json_data.pop('__token', None)

        for key, value in json_data.items():
            answer, answer_type = parse_answer(value)
            
            # Convert score to 1-5 scale if it's numeric
            answer_converted = answer
            if answer_type == 'score':
                answer_converted = convert_score_10_to_5(answer)
            
            parsed_data[response_name].append({
                'survey': survey,
                'user': user,
                'question': key,
                'answer': answer, 
                'answer_converted': answer_converted,  # Converted to 1-5, use for metrics
                'answer_type': answer_type,
            })

    return parsed_data
