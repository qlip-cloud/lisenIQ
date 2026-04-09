import json
from collections import defaultdict
import math

def safe_float(value):
    try:
        return float(value)
    except:
        return None


def average(values):
    return sum(values) / len(values) if values else 0


def std_dev(values):
    if len(values) <= 1:
        return 0

    avg = average(values)
    variance = sum((x - avg) ** 2 for x in values) / len(values)
    return math.sqrt(variance)

def parse_answer(value):
    try:
        return float(value), 'score'
    except (ValueError, TypeError):
        return value, 'text'

def _round2(value):
  if value is None:
    return None
  try:
    return round(float(value), 2)
  except (TypeError, ValueError):
    return value

def normalize_responses(responses):
    parsed_data = defaultdict(list)

    for response in responses:
        json_data = json.loads(response.response_json) if response.response_json else {}

        json_data.pop('__token', None)

        for key, value in json_data.items():
            answer, answer_type = parse_answer(value)
            parsed_data[response.name].append({
                'survey': response.survey,
                'evaluator': response.user,
                'custom_evaluatee': response.custom_evaluatee,
                'question': key,
                'answer': answer,
                'answer_type': answer_type
            })

    return parsed_data