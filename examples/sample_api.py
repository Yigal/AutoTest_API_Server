from fastapi import FastAPI, HTTPException, Query, Path, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import inspect
# Note: This is a sample API server
# In a real scenario, you would import your own utilities
# from debug_utils import Tracer  # Uncomment if using debug utilities
import json

app = FastAPI(title="Sample API Server", description="A sample API server for testing purposes.")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class Item(BaseModel):
    name: str
    price: float
    is_offer: Optional[bool] = None

class User(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None

# In-memory storage
items_db: Dict[int, Item] = {
    1: Item(name="Foo", price=50.2),
    2: Item(name="Bar", price=62, is_offer=True),
}
users_db: Dict[int, User] = {}

@app.post("/source")
async def get_source_endpoint(request: Request):
    """
    Retrieves the source code for a function by path.
    Expects JSON body: { "path": "/path", "method": "POST" }
    """
    with open("server_debug.log", "a") as f:
        f.write("Source endpoint hit\n")

    try:
        data = await request.json()
        with open("server_debug.log", "a") as f:
            f.write(f"Source request data: {json.dumps(data)}\n")

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
        
        # Get source code
        try:
            source_lines, start_line = inspect.getsourcelines(target_func)
            source_code = "".join(source_lines)
        except:
            source_code = "Source not available"
            start_line = 0

        return {
            "source": source_code,
            "start_line": start_line
        }

    except Exception as e:
        return {"error": str(e)}

@app.post("/debug")
async def debug_endpoint(request: Request):
    """
    Debugs a function by path.
    Expects JSON body: { "path": "/path", "method": "POST", "body": {...}, "query": {...} }
    """
    with open("server_debug.log", "a") as f:
        f.write("Debug endpoint hit\n")
    
    try:
        data = await request.json()
        with open("server_debug.log", "a") as f:
            f.write(f"Received data: {json.dumps(data)}\n")
            
        target_path = data.get("path")
        target_method = data.get("method", "GET").upper()
        request_body = data.get("body", {})
        # query_params = data.get("query", {}) # Not fully implemented for now

        # Find the route
        target_route = None
        for route in app.routes:
            if hasattr(route, "path") and route.path == target_path:
                if target_method in route.methods:
                    target_route = route
                    break
        
        if not target_route:
            with open("server_debug.log", "a") as f:
                f.write(f"Route not found for {target_path} {target_method}\n")
            raise HTTPException(status_code=404, detail="Endpoint not found")

        # Get the function
        target_func = target_route.endpoint
        with open("server_debug.log", "a") as f:
            f.write(f"Found target function: {target_func.__name__}\n")
        
        # Prepare arguments
        # This is a simplified argument binder. 
        # Real FastAPI does complex dependency injection and validation.
        # We will try to bind body to the Pydantic model if possible.
        
        sig = inspect.signature(target_func)
        kwargs = {}
        
        for param_name, param in sig.parameters.items():
            # Check if it's a Pydantic model
            if issubclass(param.annotation, BaseModel):
                try:
                    model_instance = param.annotation(**request_body)
                    kwargs[param_name] = model_instance
                except Exception as e:
                    with open("server_debug.log", "a") as f:
                        f.write(f"Arg binding error: {str(e)}\n")
                    return {"error": f"Failed to validate body for {param_name}: {str(e)}"}
            else:
                # Try to find in body or query (simplified)
                if param_name in request_body:
                    kwargs[param_name] = request_body[param_name]
        
        # Run with Tracer
        tracer = Tracer()
        
        if inspect.iscoroutinefunction(target_func):
            result = await tracer.run_async(target_func, **kwargs)
        else:
            result = tracer.run(target_func, **kwargs)
            
        # Get source code of the function to send back
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
        with open("server_debug.log", "a") as f:
            f.write(f"Exception in debug_endpoint: {str(e)}\n{traceback.format_exc()}\n")
        return {"error": str(e), "details": traceback.format_exc()}

@app.get("/")
def read_root():
    """
    Root endpoint.
    Returns a welcome message.
    """
    return {"message": "Welcome to the Sample API Server"}

@app.get("/items/{item_id}")
def read_item(
    item_id: int = Path(..., title="The ID of the item to get"),
    q: Optional[str] = Query(None, alias="item-query")
):
    """
    Get an item by ID.
    Optionally filter by query string.
    """
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item_id": item_id, "item": items_db[item_id], "q": q}

@app.post("/items/", status_code=201)
def create_item(item: Item):
    """
    Create a new item.
    Requires an Item object in the body.
    """
    new_id = max(items_db.keys()) + 1 if items_db else 1
    items_db[new_id] = item
    return {"item_id": new_id, "item": item}

@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    """
    Update an existing item.
    """
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    items_db[item_id] = item
    return {"item_id": item_id, "item": item}

@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    """
    Delete an item by ID.
    """
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    del items_db[item_id]
    return {"message": "Item deleted successfully"}

@app.get("/users/me")
def read_user_me():
    """
    Get current user.
    Returns a mock user.
    """
    return {"username": "fakecurrentuser", "email": "user@example.com"}

@app.post("/users/", response_model=User)
def create_user(user: User):
    """
    Create a new user.
    """
    new_id = len(users_db) + 1
    users_db[new_id] = user
    return user

@app.get("/text-response", response_class=str)
def text_response():
    """
    Returns a plain text response.
    """
    return "This is a plain text response."

@app.get("/xml-response")
def xml_response():
    """
    Returns a mock XML response (as string for simplicity).
    """
    return "<note><to>User</to><from>Server</from><heading>Reminder</heading><body>Don't forget me this weekend!</body></note>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
