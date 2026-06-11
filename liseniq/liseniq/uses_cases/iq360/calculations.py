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
        # 1. Identificar si es un diccionario o un objeto
        is_dict = isinstance(response, dict)
        
        # 2. Extraer de forma segura el JSON crudo
        raw_json = response.get('response_json') if is_dict else getattr(response, 'response_json', None)
        json_data = json.loads(raw_json) if raw_json else {}

        # 3. Extraer de forma segura los metadatos del documento de respuesta
        resp_name = response.get('name') if is_dict else getattr(response, 'name', None)
        resp_survey = response.get('survey') if is_dict else getattr(response, 'survey', None)
        resp_user = response.get('user') if is_dict else getattr(response, 'user', None)
        resp_evaluatee = response.get('custom_evaluatee') if is_dict else getattr(response, 'custom_evaluatee', None)

        # Quitar token de seguridad si existe
        json_data.pop('__token', None)

        # 4. Iterar sobre las respuestas del JSON
        for key, value in json_data.items():
            answer, answer_type = parse_answer(value)
            
            # Usamos las variables seguras que extrajimos arriba
            parsed_data[resp_name].append({
                'survey': resp_survey,
                'evaluator': resp_user,
                'custom_evaluatee': resp_evaluatee,
                'question': key,
                'answer': answer,
                'answer_type': answer_type
            })

    return parsed_data