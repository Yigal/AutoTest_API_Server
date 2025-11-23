import ast
import json
import inspect
import os
import sys
from typing import List, Dict, Any

def parse_fastapi_file(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as source:
        tree = ast.parse(source.read())

    endpoints = []
    defined_models = {}

    # First pass: Find models (Pydantic classes)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            model_fields = {}
            model_schema = []
            
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    field_type = "string" # Default
                    is_optional = False
                    
                    if isinstance(item.annotation, ast.Name):
                        field_type = item.annotation.id
                    elif isinstance(item.annotation, ast.Subscript): # e.g. List[str] or Optional[str]
                         if hasattr(item.annotation.value, 'id'):
                             container_type = item.annotation.value.id
                             if container_type == 'Optional':
                                 is_optional = True
                                 # Try to get inner type
                                 if hasattr(item.annotation.slice, 'id'): # Python < 3.9
                                     field_type = item.annotation.slice.id
                                 elif hasattr(item.annotation.slice, 'value') and hasattr(item.annotation.slice.value, 'id'): # Python >= 3.9
                                     field_type = item.annotation.slice.value.id
                             else:
                                 field_type = container_type

                    # Map types to default values
                    default_value = "string"
                    if field_type in ["int", "Integer"]: default_value = 0
                    elif field_type in ["float", "Float"]: default_value = 0.0
                    elif field_type in ["bool", "Boolean"]: default_value = True
                    elif field_type in ["list", "List"]: default_value = []
                    elif field_type in ["dict", "Dict"]: default_value = {}
                    
                    model_fields[field_name] = default_value
                    
                    model_schema.append({
                        "name": field_name,
                        "type": field_type,
                        "required": not is_optional,
                        "default": default_value
                    })
            
            if model_fields:
                defined_models[node.name] = {
                    "example": model_fields,
                    "schema": model_schema
                }

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check for decorators
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and hasattr(decorator.func, "attr"):
                    method = decorator.func.attr.upper()
                    if method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                        # Extract path
                        path = "/"
                        if decorator.args:
                            if isinstance(decorator.args[0], ast.Constant):
                                path = decorator.args[0].value
                            elif isinstance(decorator.args[0], ast.Str): # For older python versions
                                path = decorator.args[0].s
                        
                        # Extract docstring
                        docstring = ast.get_docstring(node) or "No description available."
                        
                        # Extract arguments
                        args = []
                        body_param = None
                        
                        for arg in node.args.args:
                            arg_name = arg.arg
                            arg_type = "string" # Default
                            
                            # Try to infer type annotation
                            if arg.annotation:
                                if isinstance(arg.annotation, ast.Name):
                                    arg_type = arg.annotation.id
                                elif isinstance(arg.annotation, ast.Subscript):
                                    if hasattr(arg.annotation.value, 'id'):
                                         arg_type = arg.annotation.value.id
                            
                            # Check if it's a known model or matches heuristic
                            if arg_type in defined_models:
                                body_param = {
                                    "name": arg_name,
                                    "type": arg_type,
                                    "required": True,
                                    "example": defined_models[arg_type]["example"],
                                    "schema": defined_models[arg_type]["schema"]
                                }
                            elif arg_type in ["Item", "User", "Dict", "BaseModel"] or arg_type.endswith("Request") or arg_type.endswith("Model"):
                                # Fallback for unknown models
                                body_param = {
                                    "name": arg_name,
                                    "type": arg_type,
                                    "required": True,
                                    "example": {"example": "value"},
                                    "schema": []
                                }
                            else:
                                args.append({
                                    "name": arg_name,
                                    "type": arg_type,
                                    "in": "path" if f"{{{arg_name}}}" in path else "query"
                                })

                        # Generate curl command
                        curl_cmd = f"curl -X {method} 'http://localhost:8011{path}'"
                        
                        # Add query params to curl
                        query_params = [a for a in args if a["in"] == "query"]
                        if query_params:
                            curl_cmd = curl_cmd.rstrip("'")
                            curl_cmd += "?" + "&".join([f"{p['name']}={{value}}" for p in query_params]) + "'"
                            
                        # Add path params to curl (placeholder)
                        path_params = [a for a in args if a["in"] == "path"]
                        for p in path_params:
                             # This is a simple replacement, might need more robust handling
                             pass

                        if body_param:
                            example_json = json.dumps(body_param['example'])
                            curl_cmd += f" -H 'Content-Type: application/json' -d '{example_json}'"

                        endpoints.append({
                            "method": method,
                            "path": path,
                            "description": docstring.strip(),
                            "parameters": args,
                            "body": body_param,
                            "curl": curl_cmd
                        })
                        
    return endpoints

def main():
    # Read config (from root directory)
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("config.json not found. Using defaults.")
        config = {
            "pythonServerFile": "./api_server.py",
            "endpointsOutputFile": "frontend/config/endpoints.json"
        }

    server_file = config.get("pythonServerFile", "./api_server.py")
    output_file = config.get("endpointsOutputFile", "frontend/config/endpoints.json")

    if not os.path.exists(server_file):
        print(f"Error: Server file {server_file} not found.")
        return

    print(f"Parsing {server_file}...")
    endpoints = parse_fastapi_file(server_file)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(endpoints, f, indent=2)
    
    print(f"Generated {len(endpoints)} endpoints in {output_file}")

if __name__ == "__main__":
    main()
