from typing import Dict, List, Tuple

from .open_api import ParameterStyle, Parameter
from .exceptions import OpenApiException


def _format_simple(value: any, explode: bool) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    if isinstance(value, dict):
        if explode:
            values = [f"{k}={v}" for k, v in value.items()]
        else:
            values = []
            for k, v in value.items():
                values.extend([k, str(v)])
        return ",".join(values)
    raise OpenApiException(f"Cannot simple format {value}")


def _format_form(parameter: Parameter, value: any) -> dict:
    name = parameter.name
    if isinstance(value, str):
        return {name: value}
    if isinstance(value, bool):
        return {name: 'true'} if value else {name: 'false'}
    if isinstance(value, (int, float)):
        return {name: str(value)}
    if isinstance(value, list):
        if parameter.explode:
            # TODO: this is actually wrong, we should insert ALL values here
            v = value[-1] if value else ''
            return {name: v}
        else:
            return {name: _format_simple(value, parameter.explode)}
    if isinstance(value, dict):
        if parameter.explode:
            return {k: str(v) for k, v in value.items()}
        else:
            return {name: _format_simple(value, False)}
    raise OpenApiException(f"Cannot form format {value}")


def format_parameter_value(parameter: Parameter, value: any) -> dict:
    # see https://swagger.io/specification/#style-examples
    if parameter.style == ParameterStyle.SIMPLE:
        return {parameter.name: _format_simple(value, parameter.explode)}
    elif parameter.style == ParameterStyle.FORM:
        return _format_form(parameter, value)
    raise OpenApiException(f"Unknown style = {parameter.style}, explode = {parameter.explode}")
