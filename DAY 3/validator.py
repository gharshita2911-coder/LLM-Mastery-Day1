from jsonschema import validate, ValidationError
from lead_schema import lead_schema

def validate_schema(data,schema):
    try:
        validate(instance=data, schema=schema)
        return {
            "valid": True,
            "errors": None 
        }
    except ValidationError as e:
        return {
            "valid": False,
            "errors": e.message 
        }