import uvicorn
import json
import sys
import os
import importlib.util
import inspect
from fastapi import Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src.server.utils import Tracer

# Load config (from root directory)
config_path = os.path.join(PROJECT_ROOT, 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

# Get app configuration
app_config = config.get('app', {})
SERVER_HOST = app_config.get('host', '0.0.0.0')
SERVER_PORT = app_config.get('port', 3020)
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

# --- Setup Frontend Serving ---

# Get project root directory (parent of src)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATIC_DIR = os.path.join(PROJECT_ROOT, 'static')
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config')

# Mount static files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    print(f"Mounted static files from {STATIC_DIR}")

# Check if user app has a root route and handle it
has_root_route = False
user_root_handler = None
user_root_methods = set()

# Find and remove user's root route if it exists
routes_to_remove = []
for route in app.routes:
    if hasattr(route, "path") and route.path == "/":
        has_root_route = True
        user_root_handler = route.endpoint
        if hasattr(route, "methods"):
            user_root_methods = route.methods
        routes_to_remove.append(route)

# Remove user's root routes
for route in routes_to_remove:
    app.routes.remove(route)

# If user had a root route, add it to /api/root for backward compatibility
if has_root_route and user_root_handler:
    # Recreate the route at /api/root
    from fastapi.routing import APIRoute
    if "GET" in user_root_methods:
        @app.get("/api/root")
        async def user_root_alternative():
            """Alternative route for user's root endpoint"""
            if inspect.iscoroutinefunction(user_root_handler):
                return await user_root_handler()
            else:
                return user_root_handler()
    print("User app root route moved to /api/root (UI is now at /)")

# Always serve UI at root - this is the primary interface
# The UI automatically loads from the port defined in config.json
@app.get("/", response_class=FileResponse)
async def read_root():
    """Serve the UI at root - automatically loads from config.json port"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "API Server is running", "frontend": "not found"}

# Frontend API endpoints
@app.get("/api/config")
async def get_config():
    """Returns server configuration for the frontend"""
    return {
        "serverPort": SERVER_PORT,
        "serverHost": SERVER_HOST,
        "serverUrl": f"http://localhost:{SERVER_PORT}"
    }

@app.get("/api/endpoints")
async def get_endpoints():
    """Returns the generated endpoints configuration"""
    endpoints_path = os.path.join(CONFIG_DIR, "endpoints.json")
    if os.path.exists(endpoints_path):
        try:
            with open(endpoints_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading endpoints: {e}")
            return []
    return []

@app.post("/api/proxy")
async def proxy_request(request: Request):
    """Proxies requests to the FastAPI backend (for backward compatibility)"""
    try:
        data = await request.json()
        method = data.get("method", "GET")
        url = data.get("url")
        headers = data.get("headers", {})
        body = data.get("body")
        
        if not url:
            return JSONResponse(
                status_code=400,
                content={"error": "URL is required"}
            )
        
        # Make request to the backend
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
                timeout=30.0
            )
            
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                }
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "details": traceback.format_exc()}
        )

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

def main():
    """Main entry point for the server"""
    print(f"Starting Wrapped Server on {SERVER_HOST}:{SERVER_PORT}...")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)

if __name__ == "__main__":
    main()
