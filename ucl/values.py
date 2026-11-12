"""Shared strict JSON policy for expressions and HTTP request boundaries."""
import json
import math


def parse_json(text):
    def constant(value): raise ValueError('nonfinite JSON numbers are not allowed')
    def floating(value):
        result = float(value)
        if not math.isfinite(result): raise ValueError('JSON number is outside the finite numeric range')
        return result
    def record(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('duplicate JSON object key')
            result[key] = value
        return result
    return json.loads(text, parse_constant=constant, parse_float=floating, object_pairs_hook=record)
