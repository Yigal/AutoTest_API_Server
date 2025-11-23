import uvicorn
import json
import sys
import os
import importlib.util
import inspect
from fastapi import Request, HTTPException
from pydantic import BaseModel
from debug_utils import Tracer

# Load config (from root directory)
config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

SERVER_PORT = config.get('serverPort', 8011)
PYTHON_FILE = config.get('pythonServerFile', './api_server.py')

def load_user_app(file_path):
    module_name = os.path.basename(file_path).replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    
    # Find FastAPI app instance
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if hasattr(attr, 'router') and hasattr(attr, 'openapi'): # Duck typing check for FastAPI app
            return attr
            
    raise ValueError("Could not find FastAPI app instance in " + file_path)

print(f"Loading user server from {PYTHON_FILE}...")
try:
    app = load_user_app(PYTHON_FILE)
except Exception as e:
    print(f"Error loading user server: {e}")
    sys.exit(1)

# --- Inject Debug Endpoints ---

@app.post("/source")
async def get_source_endpoint(request: Request):
    """
    Retrieves the source code for a function by path.
    Expects JSON body: { "path": "/path", "method": "POST" }
    """
    print("Source endpoint hit (in wrapper)")
    try:
        data = await request.json()
        target_path = data.get("path")
        target_method = data.get("method", "GET").upper()

        # Find the route
        target_route = None
        for route in app.routes:
            if hasattr(route, "path") and route.path == target_path:
                if target_method in route.methods:
                    target_route = route
                    break
        
        if not target_route:
            raise HTTPException(status_code=404, detail="Endpoint not found")

        # Get the function
        target_func = target_route.endpoint
        
        # Unwrap to get the actual function if decorated
        target_func = inspect.unwrap(target_func)
        
        print(f"Resolved target function: {target_func.__name__}")
        
        # Get source code
        try:
            source_lines, start_line = inspect.getsourcelines(target_func)
            source_code = "".join(source_lines)
            print(f"Retrieved {len(source_lines)} lines of source code")
        except Exception as e:
            print(f"Failed to get source: {e}")
            source_code = "Source not available"
            start_line = 0

        return {
            "source": source_code,
            "start_line": start_line
        }

    except Exception as e:
        print(f"Error in source endpoint: {e}")
        return {"error": str(e)}

@app.post("/debug")
async def debug_endpoint(request: Request):
    """
    Debugs a function by path.
    Expects JSON body: { "path": "/path", "method": "POST", "body": {...}, "query": {...} }
    """
    print("Debug endpoint hit (in wrapper)")
    try:
        data = await request.json()
        target_path = data.get("path")
        target_method = data.get("method", "GET").upper()
        request_body = data.get("body", {})

        # Find the route
        target_route = None
        for route in app.routes:
            if hasattr(route, "path") and route.path == target_path:
                if target_method in route.methods:
                    target_route = route
                    break
        
        if not target_route:
            raise HTTPException(status_code=404, detail="Endpoint not found")

        # Get the function
        target_func = target_route.endpoint
        target_func = inspect.unwrap(target_func) # Unwrap for debugging too
        
        print(f"Debugging target function: {target_func.__name__}")
        
        # Prepare arguments
        sig = inspect.signature(target_func)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            # Check if it's a Pydantic model
            if issubclass(param.annotation, BaseModel):
                try:
                    model_instance = param.annotation(**request_body)
                    kwargs[param_name] = model_instance
                except Exception as e:
                    return {"error": f"Failed to validate body for {param_name}: {str(e)}"}
            else:
                if param_name in request_body:
                    kwargs[param_name] = request_body[param_name]
        
        # Run with Tracer
        tracer = Tracer()
        
        if inspect.iscoroutinefunction(target_func):
            result = await tracer.run_async(target_func, **kwargs)
        else:
            result = tracer.run(target_func, **kwargs)
            
        # Get source code
        try:
            source_lines, start_line = inspect.getsourcelines(target_func)
            source_code = "".join(source_lines)
        except:
            source_code = "Source not available"
            start_line = 0

        return {
            "result": result,
            "trace": tracer.get_log(),
            "source": source_code,
            "start_line": start_line
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "details": traceback.format_exc()}

if __name__ == "__main__":
    print(f"Starting Wrapped Server on port {SERVER_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
