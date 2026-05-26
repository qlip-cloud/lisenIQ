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


def parse_answer(value):
    """Parse answer and determine if it's a score or text"""
    try:
        return float(value), 'score'
    except (ValueError, TypeError):
        return value, 'text'


def normalize_responses(responses):
    """
    Normalize survey responses from JSON format to structured format.
    Returns dict: {response_name: [{question, answer, answer_type, evaluator}, ...]}
    """
    parsed_data = defaultdict(list)

    for response in responses:
        json_data = json.loads(response.response_json) if response.response_json else {}
        json_data.pop('__token', None)

        for key, value in json_data.items():
            answer, answer_type = parse_answer(value)
            parsed_data[response.name].append({
                'survey': response.survey,
                'evaluator': response.user,
                'question': key,
                'answer': answer,
                'answer_type': answer_type,
            })

    return parsed_data
