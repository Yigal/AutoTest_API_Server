# Refactoring Plan: Remove RabbitMQ and Reorganize Codebase

## Current Structure Analysis

### Current Directory Structure
```
AutoTest_API_Server/
├── api-tester/
│   └── server-test-ui/          # Main application (redundant nesting)
│       ├── api_server.py         # FastAPI backend
│       ├── server.js             # Node.js frontend server
│       ├── config.json           # Contains unused rabbitmqQueue
│       ├── requirements.txt      # Python dependencies
│       ├── package.json          # Node.js dependencies
│       ├── public/               # Frontend static files
│       ├── config/               # Endpoint configurations
│       └── [debug utilities]
├── rabbitmq_worker/              # TO BE REMOVED
│   ├── worker.py                 # RabbitMQ consumer (not used by API)
│   ├── docker-compose.yml        # RabbitMQ Docker setup
│   ├── Dockerfile                # Worker container
│   ├── config.json               # RabbitMQ config
│   └── requirements.txt          # pika dependency
└── start.sh                      # Startup script (references RabbitMQ)
```

### Issues Identified
1. **RabbitMQ is not integrated**: The API server (`api_server.py`) doesn't publish messages to RabbitMQ
2. **Redundant directory nesting**: `api-tester/server-test-ui` is unnecessarily nested
3. **Unused configuration**: `rabbitmqQueue` in config.json is not referenced in code
4. **Mixed concerns**: Backend and frontend are in the same directory

## Proposed New Structure

```
AutoTest_API_Server/
├── backend/                      # FastAPI server
│   ├── api_server.py
│   ├── debug_utils.py
│   ├── debug_wrapper.py
│   ├── generate_endpoints.py
│   └── requirements.txt
├── frontend/                     # Node.js server + UI
│   ├── server.js                 # Express server
│   ├── start.js                  # Startup script
│   ├── package.json
│   ├── public/                   # Static files
│   │   ├── index.html
│   │   ├── script.js
│   │   ├── style.css
│   │   └── sidebar_update.css
│   └── config/                   # Endpoint configurations
│       └── endpoints.json
├── config.json                   # Root-level configuration
└── start.sh                      # Simplified startup script
```

## Refactoring Steps

### Phase 1: Remove RabbitMQ Components
1. **Delete rabbitmq_worker directory**
   - Remove entire `rabbitmq_worker/` folder
   - This includes:
     - `worker.py`
     - `docker-compose.yml`
     - `Dockerfile`
     - `config.json`
     - `requirements.txt`

### Phase 2: Clean Up Configuration
2. **Remove RabbitMQ references from config.json**
   - Remove `rabbitmqQueue` field from `api-tester/server-test-ui/config.json`
   - Move config.json to root level (simplify path references)

### Phase 3: Reorganize Directory Structure
3. **Create new directory structure**
   - Create `backend/` directory
   - Create `frontend/` directory
   - Move Python files to `backend/`
   - Move Node.js files and public assets to `frontend/`

4. **File movements:**
   ```
   api-tester/server-test-ui/api_server.py          → backend/api_server.py
   api-tester/server-test-ui/debug_utils.py         → backend/debug_utils.py
   api-tester/server-test-ui/debug_wrapper.py       → backend/debug_wrapper.py
   api-tester/server-test-ui/generate_endpoints.py   → backend/generate_endpoints.py
   api-tester/server-test-ui/requirements.txt       → backend/requirements.txt
   
   api-tester/server-test-ui/server.js              → frontend/server.js
   api-tester/server-test-ui/start.js                → frontend/start.js
   api-tester/server-test-ui/package.json            → frontend/package.json
   api-tester/server-test-ui/package-lock.json       → frontend/package-lock.json
   api-tester/server-test-ui/public/                 → frontend/public/
   api-tester/server-test-ui/config/endpoints.json   → frontend/config/endpoints.json
   ```

### Phase 4: Update File References
5. **Update import paths in Python files**
   - Check `debug_utils.py` imports in `api_server.py`
   - Update any relative imports

6. **Update paths in Node.js files**
   - Update `server.js` to reference new paths for:
     - `config.json` location
     - `endpoints.json` location
     - Static file paths (should remain relative)

7. **Update start.sh**
   - Remove RabbitMQ Docker commands
   - Update paths to new directory structure
   - Simplify startup process
   - Remove RabbitMQ management URL from output

8. **Update config.json paths**
   - Update `endpointsOutputFile` path in config.json
   - Update `pythonServerFile` if it references the old path

### Phase 5: Clean Up
9. **Remove old directories**
   - Delete `api-tester/` directory after confirming all files moved

10. **Update .gitignore if needed**
    - Ensure new structure is properly tracked

## Detailed Changes

### start.sh Changes
**Remove:**
- RabbitMQ Docker compose commands
- RabbitMQ management URL output
- RabbitMQ cleanup in trap handler

**Update:**
- Change `cd api-tester/server-test-ui` to `cd frontend`
- Simplify startup to just start the frontend server (which starts backend)

### config.json Changes
**Remove:**
- `rabbitmqQueue` field

**Update:**
- `endpointsOutputFile`: `"./config/endpoints.json"` → `"frontend/config/endpoints.json"` (if moved to root)
- Or keep relative path if config stays in frontend directory

### server.js Changes
**Update:**
- Config file path: `./config.json` → may need adjustment based on final location
- Endpoints file path: adjust if config.json moves to root

## Testing Checklist
- [ ] Verify FastAPI server starts correctly
- [ ] Verify Node.js server starts correctly
- [ ] Test API endpoints work
- [ ] Test frontend UI loads and functions
- [ ] Verify debug endpoints work
- [ ] Check that endpoint generation still works
- [ ] Verify start.sh script works end-to-end

## Benefits of New Structure
1. **Clearer separation**: Backend and frontend are distinct
2. **Simpler paths**: No redundant nesting
3. **Easier maintenance**: Logical organization
4. **Reduced complexity**: No unused RabbitMQ infrastructure
5. **Better scalability**: Easy to add new components

## Risk Mitigation
- Keep a backup of the original structure
- Test each phase before proceeding
- Update one component at a time
- Verify imports and paths after each move

