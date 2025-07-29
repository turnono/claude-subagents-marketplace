
from fastapi import FastAPI, HTTPException, Response, Query, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
import yaml
import glob
import requests
import firebase_admin
from firebase_admin import auth, credentials, firestore
import json
import schedule
import threading
import time

# --- Firebase Setup ---
cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase-admin-key.json")
if os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    raise RuntimeError("Missing Firebase credentials")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUBAGENTS_DIRS = ["agents", "subagents", "community_agents"]
GITHUB_IMPORT_URLS = [
    "https://raw.githubusercontent.com/wshobson/agents/main/code-reviewer.md",
    "https://raw.githubusercontent.com/wshobson/agents/main/debugger.md"
]

class Subagent(BaseModel):
    name: str
    description: str
    tools: List[str]
    content: str

# --- Auth Helper ---
def verify_token(request: Request):
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid auth header")
    id_token = auth_header.split(" ")[1]
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

@app.get("/agents", response_model=List[Subagent])
def list_agents(q: str = Query(default=None, description="Optional search query")):
    agents = []
    for directory in SUBAGENTS_DIRS:
        for filepath in glob.glob(f"{directory}/*.md"):
            with open(filepath, "r") as f:
                content = f.read()
            try:
                front_matter = content.split('---')[1]
                body = content.split('---')[2].strip()
                data = yaml.safe_load(front_matter)
                agent = Subagent(name=data['name'], description=data['description'], tools=data['tools'], content=body)
                if not q or q.lower() in agent.name.lower() or q.lower() in agent.description.lower() or any(q.lower() in t.lower() for t in agent.tools):
                    agents.append(agent)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse {filepath}: {str(e)}")
    return agents

@app.get("/meta")
def get_metadata():
    results = []
    try:
        docs = db.collection("agents").stream()
        for doc in docs:
            data = doc.to_dict()
            data['name'] = doc.id
            results.append(data)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firestore error: {str(e)}")

@app.post("/agents", response_model=Subagent)
def add_agent(agent: Subagent, user=Depends(verify_token)):
    filename = f"agents/{agent.name.lower().replace(' ', '_')}.md"
    with open(filename, "w") as f:
        f.write(f"---\n")
        f.write(yaml.dump({"name": agent.name, "description": agent.description, "tools": agent.tools}))
        f.write("---\n\n")
        f.write(agent.content)
    db.collection("agents").document(agent.name).set({
        "description": agent.description,
        "tools": agent.tools,
        "submitted_by": user["uid"],
        "likes": 0
    })
    return agent

@app.post("/like/{agent_name}")
def like_agent(agent_name: str):
    try:
        doc_ref = db.collection("agents").document(agent_name)
        doc_ref.update({"likes": firestore.Increment(1)})
        return {"message": f"Liked {agent_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update likes: {str(e)}")

@app.post("/import")
def import_from_github():
    imported = []
    for url in GITHUB_IMPORT_URLS:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                content = response.text
                front_matter = content.split('---')[1]
                body = content.split('---')[2].strip()
                data = yaml.safe_load(front_matter)
                filename = f"community_agents/{data['name'].lower().replace(' ', '_')}.md"
                with open(filename, "w") as f:
                    f.write(content)
                db.collection("agents").document(data['name']).set({
                    "description": data['description'],
                    "tools": data['tools'],
                    "submitted_by": "import-script",
                    "likes": 0
                })
                imported.append(data['name'])
        except Exception:
            continue
    return {"imported": imported}

@app.get("/docs.html")
def serve_docs():
    docs_path = os.path.join(os.path.dirname(__file__), "docs.html")
    if not os.path.exists(docs_path):
        raise HTTPException(status_code=404, detail="Documentation page not found")
    return FileResponse(docs_path, media_type="text/html")

@app.get("/firebase.json")
def get_firebase_json():
    return JSONResponse(content={
        "hosting": {
            "public": "public",
            "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
            "rewrites": [{"source": "**", "destination": "/index.html"}]
        }
    })

@app.get("/")
def index():
    index_path = os.path.join("public", "index.html")
    if not os.path.exists(index_path):
        return Response("<h1>Claude Subagents Marketplace</h1><p>Welcome.</p>", media_type="text/html")
    return FileResponse(index_path, media_type="text/html")

# --- Scheduler to sync imports hourly ---
def background_scheduler():
    def job():
        import_from_github()
    schedule.every(1).hours.do(job)
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=background_scheduler, daemon=True).start()
