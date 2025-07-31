
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
db = None

try:
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully")
    else:
        print("Warning: Firebase credentials not found. Some features will be disabled.")
        print("To enable full functionality, add your firebase-admin-key.json file")
except Exception as e:
    print(f"Warning: Firebase initialization failed: {e}")
    print("Some features will be disabled. To enable full functionality, add valid Firebase credentials")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUBAGENTS_DIRS = ["community_agents"]  # Only web-imported agents

# Dynamic repository discovery instead of hardcoded URLs
REPOSITORIES_TO_SCAN = [
    {
        "owner": "wshobson",
        "repo": "agents",
        "branch": "main",
        "path": ""
    },
    {
        "owner": "anthropics",
        "repo": "anthropic-cookbook",
        "branch": "main", 
        "path": "agents"
    },
    {
        "owner": "Claude-3-Sonnet",
        "repo": "agents",
        "branch": "main",
        "path": ""
    }
]

# GitHub-wide search patterns for finding agent repositories
GITHUB_SEARCH_PATTERNS = [
    "claude subagent filename:*.md",
    "anthropic agent filename:*.md", 
    "claude tools filename:*.md",
    "subagent markdown filename:*.md",
    "claude-compatible filename:*.md",
    "anthropic-cookbook filename:*.md",
    "claude agent filename:*.md",
    "anthropic subagent filename:*.md"
]

def is_valid_subagent_file(content: str) -> bool:
    """Validate if a file is a proper Claude subagent"""
    try:
        # Check for YAML frontmatter
        if '---' not in content or content.count('---') < 2:
            return False
        
        # Extract frontmatter
        parts = content.split('---')
        if len(parts) < 3:
            return False
        
        front_matter = parts[1].strip()
        body = parts[2].strip()
        
        # Parse YAML
        data = yaml.safe_load(front_matter)
        if not data:
            return False
        
        # Check for required fields
        if 'name' not in data or 'description' not in data:
            return False
        
        # Check if it's actually a subagent (not just any markdown)
        name_lower = data['name'].lower()
        description_lower = data['description'].lower()
        
        # Must contain subagent-related keywords
        subagent_keywords = ['subagent', 'claude', 'anthropic', 'agent', 'assistant', 'tool']
        has_subagent_keyword = any(keyword in name_lower or keyword in description_lower 
                                 for keyword in subagent_keywords)
        
        if not has_subagent_keyword:
            return False
        
        # Must have meaningful content
        if len(body.strip()) < 50:  # At least 50 characters of content
            return False
        
        return True
        
    except Exception:
        return False

def search_github_for_agents():
    """Search GitHub for repositories containing Claude subagents"""
    discovered_repos = []
    
    for pattern in GITHUB_SEARCH_PATTERNS:
        try:
            # Search for repositories with the pattern
            search_url = f"https://api.github.com/search/repositories?q={pattern}&sort=stars&order=desc&per_page=100"
            response = requests.get(search_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Claude-Subagents-Marketplace"
            })
            
            if response.status_code == 200:
                results = response.json()
                for repo in results.get('items', []):
                    repo_info = {
                        "owner": repo['owner']['login'],
                        "repo": repo['name'],
                        "branch": "main",
                        "path": "",
                        "stars": repo['stargazers_count'],
                        "description": repo['description'],
                        "url": repo['html_url']
                    }
                    discovered_repos.append(repo_info)
                    print(f"🔍 Found potential agent repo: {repo['owner']['login']}/{repo['name']} ({repo['stargazers_count']} stars)")
            
            # Rate limiting - GitHub allows 30 requests per minute for unauthenticated requests
            time.sleep(2)
            
        except Exception as e:
            print(f"Error searching for pattern '{pattern}': {str(e)}")
            continue
    
    return discovered_repos

def scan_github_trending():
    """Scan GitHub trending repositories for potential agent repositories"""
    trending_repos = []
    
    try:
        # Focus on repositories that actually contain Claude subagents
        popular_repos = [
            {"owner": "wshobson", "repo": "agents", "path": ""},
            {"owner": "anthropics", "repo": "anthropic-cookbook", "path": "agents"},
            {"owner": "Claude-3-Sonnet", "repo": "agents", "path": ""},
            {"owner": "microsoft", "repo": "semantic-kernel", "path": "samples"},
            {"owner": "langchain-ai", "repo": "langchain", "path": "templates"},
            {"owner": "openai", "repo": "openai-cookbook", "path": "examples"},
            {"owner": "microsoft", "repo": "autogen", "path": "samples"},
            {"owner": "huggingface", "repo": "transformers", "path": "examples"}
        ]
        
        for repo in popular_repos:
            repo_info = {
                "owner": repo["owner"],
                "repo": repo["repo"],
                "branch": "main",
                "path": repo["path"],
                "source": "trending"
            }
            trending_repos.append(repo_info)
            
    except Exception as e:
        print(f"Error scanning trending repos: {str(e)}")
    
    return trending_repos

def discover_agents_in_repo(owner: str, repo: str, branch: str = "main", path: str = ""):
    """Dynamically discover agent files in a GitHub repository"""
    try:
        # Use GitHub API to list files in the repository
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(api_url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Claude-Subagents-Marketplace"
        })
        
        if response.status_code != 200:
            print(f"Failed to access {owner}/{repo}: {response.status_code}")
            return []
        
        files = response.json()
        agent_urls = []
        
        for file in files:
            if file["type"] == "file" and file["name"].endswith(".md"):
                # Check if it's likely an agent file by looking for YAML frontmatter
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}/{file['name']}"
                agent_urls.append(raw_url)
            elif file["type"] == "dir":
                # Recursively scan subdirectories
                sub_path = f"{path}/{file['name']}" if path else file['name']
                sub_agents = discover_agents_in_repo(owner, repo, branch, sub_path)
                agent_urls.extend(sub_agents)
        
        return agent_urls
    except Exception as e:
        print(f"Error discovering agents in {owner}/{repo}: {str(e)}")
        return []

def get_all_agent_urls():
    """Get all agent URLs from all configured repositories"""
    all_urls = []
    for repo_config in REPOSITORIES_TO_SCAN:
        urls = discover_agents_in_repo(
            repo_config["owner"],
            repo_config["repo"], 
            repo_config["branch"],
            repo_config["path"]
        )
        all_urls.extend(urls)
        print(f"Discovered {len(urls)} agents in {repo_config['owner']}/{repo_config['repo']}")
    return all_urls

def get_github_wide_agents():
    """Get agents from GitHub-wide search"""
    print("🌐 Starting GitHub-wide agent discovery...")
    
    # Search for agent repositories
    discovered_repos = search_github_for_agents()
    trending_repos = scan_github_trending()
    
    all_repos = discovered_repos + trending_repos
    print(f"🔍 Found {len(all_repos)} potential repositories")
    
    all_urls = []
    for repo in all_repos:
        try:
            urls = discover_agents_in_repo(
                repo["owner"],
                repo["repo"],
                repo.get("branch", "main"),
                repo.get("path", "")
            )
            if urls:
                all_urls.extend(urls)
                print(f"✅ Found {len(urls)} agents in {repo['owner']}/{repo['repo']}")
        except Exception as e:
            print(f"❌ Error scanning {repo['owner']}/{repo['repo']}: {str(e)}")
            continue
    
    return all_urls

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

@app.get("/agents/{agent_name}/download")
def download_agent(agent_name: str):
    """Download the full markdown content of a specific agent"""
    for directory in SUBAGENTS_DIRS:
        for filepath in glob.glob(f"{directory}/*.md"):
            with open(filepath, "r") as f:
                content = f.read()
            try:
                front_matter = content.split('---')[1]
                data = yaml.safe_load(front_matter)
                if data['name'] == agent_name:
                    # Return the full markdown content
                    return Response(
                        content=content,
                        media_type="text/markdown",
                        headers={
                            "Content-Disposition": f"attachment; filename=\"{agent_name}.md\""
                        }
                    )
            except Exception as e:
                continue
    
    raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/agents/{agent_name}")
def get_agent(agent_name: str):
    """Get a specific agent by name"""
    for directory in SUBAGENTS_DIRS:
        for filepath in glob.glob(f"{directory}/*.md"):
            with open(filepath, "r") as f:
                content = f.read()
            try:
                front_matter = content.split('---')[1]
                body = content.split('---')[2].strip()
                data = yaml.safe_load(front_matter)
                if data['name'] == agent_name:
                    return Subagent(
                        name=data['name'], 
                        description=data['description'], 
                        tools=data['tools'], 
                        content=body
                    )
            except Exception as e:
                continue
    
    raise HTTPException(status_code=404, detail="Agent not found")

@app.get("/meta")
def get_metadata():
    if db is None:
        return {"message": "Firebase not configured", "agents": []}
    
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
    
    if db is not None:
        db.collection("agents").document(agent.name).set({
            "description": agent.description,
            "tools": agent.tools,
            "submitted_by": user["uid"],
            "likes": 0
        })
    
    return agent

@app.post("/like/{agent_name}")
def like_agent(agent_name: str):
    if db is None:
        return {"message": f"Liked {agent_name} (Firebase not configured)"}
    
    try:
        doc_ref = db.collection("agents").document(agent_name)
        doc_ref.update({"likes": firestore.Increment(1)})
        return {"message": f"Liked {agent_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update likes: {str(e)}")

@app.post("/import")
def import_from_github():
    # Ensure community_agents directory exists
    os.makedirs("community_agents", exist_ok=True)
    
    print("🔍 Discovering agents from repositories...")
    all_urls = get_all_agent_urls()
    print(f"📦 Found {len(all_urls)} potential agent files")
    
    imported = []
    failed = []
    
    for url in all_urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                content = response.text
                
                # Check if it has YAML frontmatter (basic validation)
                if '---' not in content or content.count('---') < 2:
                    print(f"⚠️  Skipping {url}: No YAML frontmatter found")
                    continue
                
                # Validate if this is actually a subagent file
                if not is_valid_subagent_file(content):
                    print(f"⚠️  Skipping {url}: Not a valid Claude subagent file")
                    continue
                
                front_matter = content.split('---')[1]
                body = content.split('---')[2].strip()
                data = yaml.safe_load(front_matter)
                
                # Validate required fields
                if not data or 'name' not in data or 'description' not in data:
                    print(f"⚠️  Skipping {url}: Missing required fields")
                    continue
                
                # Add default tools if not present
                if 'tools' not in data:
                    # Intelligently assign tools based on agent type
                    agent_name = data['name'].lower()
                    if 'code' in agent_name or 'review' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Git']
                    elif 'debug' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Python', 'JavaScript']
                    elif 'python' in agent_name:
                        data['tools'] = ['Read', 'Python', 'Pip', 'Virtualenv']
                    elif 'javascript' in agent_name or 'js' in agent_name:
                        data['tools'] = ['Read', 'JavaScript', 'TypeScript', 'Node.js']
                    elif 'data' in agent_name or 'scientist' in agent_name:
                        data['tools'] = ['Read', 'Python', 'R', 'SQL', 'Jupyter']
                    elif 'ml' in agent_name or 'machine' in agent_name:
                        data['tools'] = ['Read', 'Python', 'TensorFlow', 'PyTorch', 'Scikit-learn']
                    elif 'security' in agent_name or 'audit' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Security']
                    elif 'devops' in agent_name or 'ops' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Docker', 'Kubernetes']
                    elif 'content' in agent_name or 'writer' in agent_name:
                        data['tools'] = ['Read', 'Write', 'Markdown', 'HTML']
                    else:
                        data['tools'] = ['Read', 'Grep', 'Bash']
                
                # Ensure tools is always a list
                if isinstance(data['tools'], str):
                    # Convert comma-separated string to list
                    data['tools'] = [tool.strip() for tool in data['tools'].split(',')]
                elif not isinstance(data['tools'], list):
                    data['tools'] = ['Read', 'Grep', 'Bash']  # Default fallback
                
                # Create filename with proper naming
                filename = f"community_agents/{data['name'].lower().replace(' ', '-').replace('_', '-')}.md"
                
                # Reconstruct the content with proper YAML
                new_content = f"---\nname: {data['name']}\ndescription: {data['description']}\ntools:\n"
                for tool in data['tools']:
                    new_content += f"  - {tool}\n"
                new_content += f"---\n\n{body}"
                
                with open(filename, "w") as f:
                    f.write(new_content)
                
                if db is not None:
                    db.collection("agents").document(data['name']).set({
                        "description": data['description'],
                        "tools": data['tools'],
                        "submitted_by": "import-script",
                            "likes": 0,
                            "source_url": url
                        })
                    imported.append(data['name'])
                    print(f"✅ Imported: {data['name']}")
            else:
                failed.append(url)
                print(f"❌ Failed to fetch {url}: {response.status_code}")
        except Exception as e:
            failed.append(url)
            print(f"❌ Error importing from {url}: {str(e)}")
            continue
    
    print(f"🎉 Import complete: {len(imported)} successful, {len(failed)} failed")
    return {
        "imported": imported,
        "failed": failed,
        "total_discovered": len(all_urls),
        "success_rate": f"{len(imported)}/{len(all_urls)}"
    }

@app.post("/import-github-wide")
def import_from_github_wide():
    """Import agents from GitHub-wide search"""
    # Ensure community_agents directory exists
    os.makedirs("community_agents", exist_ok=True)
    
    print("🌐 Starting GitHub-wide agent discovery...")
    all_urls = get_github_wide_agents()
    print(f"📦 Found {len(all_urls)} potential agent files from GitHub-wide search")
    
    imported = []
    failed = []
    
    for url in all_urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                content = response.text
                
                # Check if it has YAML frontmatter (basic validation)
                if '---' not in content or content.count('---') < 2:
                    print(f"⚠️  Skipping {url}: No YAML frontmatter found")
                    continue
                
                # Validate if this is actually a subagent file
                if not is_valid_subagent_file(content):
                    print(f"⚠️  Skipping {url}: Not a valid Claude subagent file")
                    continue
                
                front_matter = content.split('---')[1]
                body = content.split('---')[2].strip()
                data = yaml.safe_load(front_matter)
                
                # Validate required fields
                if not data or 'name' not in data or 'description' not in data:
                    print(f"⚠️  Skipping {url}: Missing required fields")
                    continue
                
                # Add default tools if not present
                if 'tools' not in data:
                    # Intelligently assign tools based on agent type
                    agent_name = data['name'].lower()
                    if 'code' in agent_name or 'review' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Git']
                    elif 'debug' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Python', 'JavaScript']
                    elif 'python' in agent_name:
                        data['tools'] = ['Read', 'Python', 'Pip', 'Virtualenv']
                    elif 'javascript' in agent_name or 'js' in agent_name:
                        data['tools'] = ['Read', 'JavaScript', 'TypeScript', 'Node.js']
                    elif 'data' in agent_name or 'scientist' in agent_name:
                        data['tools'] = ['Read', 'Python', 'R', 'SQL', 'Jupyter']
                    elif 'ml' in agent_name or 'machine' in agent_name:
                        data['tools'] = ['Read', 'Python', 'TensorFlow', 'PyTorch', 'Scikit-learn']
                    elif 'security' in agent_name or 'audit' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Security']
                    elif 'devops' in agent_name or 'ops' in agent_name:
                        data['tools'] = ['Read', 'Grep', 'Bash', 'Docker', 'Kubernetes']
                    elif 'content' in agent_name or 'writer' in agent_name:
                        data['tools'] = ['Read', 'Write', 'Markdown', 'HTML']
                    else:
                        data['tools'] = ['Read', 'Grep', 'Bash']
                
                # Ensure tools is always a list
                if isinstance(data['tools'], str):
                    # Convert comma-separated string to list
                    data['tools'] = [tool.strip() for tool in data['tools'].split(',')]
                elif not isinstance(data['tools'], list):
                    data['tools'] = ['Read', 'Grep', 'Bash']  # Default fallback
                
                # Create filename with proper naming
                filename = f"community_agents/{data['name'].lower().replace(' ', '-').replace('_', '-')}.md"
                
                # Reconstruct the content with proper YAML
                new_content = f"---\nname: {data['name']}\ndescription: {data['description']}\ntools:\n"
                for tool in data['tools']:
                    new_content += f"  - {tool}\n"
                new_content += f"---\n\n{body}"
                
                with open(filename, "w") as f:
                    f.write(new_content)
                
                if db is not None:
                    db.collection("agents").document(data['name']).set({
                        "description": data['description'],
                        "tools": data['tools'],
                        "submitted_by": "github-wide-scan",
                        "likes": 0,
                        "source_url": url
                })
                imported.append(data['name'])
                print(f"✅ Imported: {data['name']}")
            else:
                failed.append(url)
                print(f"❌ Failed to fetch {url}: {response.status_code}")
        except Exception as e:
            failed.append(url)
            print(f"❌ Error importing from {url}: {str(e)}")
            continue
    
    print(f"🎉 GitHub-wide import complete: {len(imported)} successful, {len(failed)} failed")
    return {
        "imported": imported,
        "failed": failed,
        "total_discovered": len(all_urls),
        "success_rate": f"{len(imported)}/{len(all_urls)}",
        "source": "github-wide-search"
    }

@app.post("/repositories")
def add_repository(repo_data: dict, user=Depends(verify_token)):
    """Add a new repository to scan for agents"""
    try:
        # Validate repository data
        required_fields = ["owner", "repo"]
        for field in required_fields:
            if field not in repo_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Test if repository exists and is accessible
        test_url = f"https://api.github.com/repos/{repo_data['owner']}/{repo_data['repo']}"
        response = requests.get(test_url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Claude-Subagents-Marketplace"
        })
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Repository not found or not accessible: {repo_data['owner']}/{repo_data['repo']}")
        
        # Add to repositories list
        new_repo = {
            "owner": repo_data["owner"],
            "repo": repo_data["repo"],
            "branch": repo_data.get("branch", "main"),
            "path": repo_data.get("path", ""),
            "added_by": user.get("email", "unknown"),
            "added_at": time.time()
        }
        
        REPOSITORIES_TO_SCAN.append(new_repo)
        
        # Store in Firebase if available
        if db is not None:
            db.collection("repositories").document(f"{repo_data['owner']}/{repo_data['repo']}").set(new_repo)
        
        return {
            "message": f"Repository {repo_data['owner']}/{repo_data['repo']} added successfully",
            "repository": new_repo
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add repository: {str(e)}")

@app.get("/repositories")
def list_repositories():
    """List all repositories being scanned"""
    return {
        "repositories": REPOSITORIES_TO_SCAN,
        "total": len(REPOSITORIES_TO_SCAN)
    }

@app.get("/search-github")
def search_github_repositories():
    """Search GitHub for potential agent repositories"""
    try:
        discovered_repos = search_github_for_agents()
        trending_repos = scan_github_trending()
        
        all_repos = discovered_repos + trending_repos
        
        return {
            "discovered_repositories": len(discovered_repos),
            "trending_repositories": len(trending_repos),
            "total_repositories": len(all_repos),
            "repositories": all_repos[:20],  # Return first 20 for preview
            "search_patterns": GITHUB_SEARCH_PATTERNS
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search GitHub: {str(e)}")

@app.post("/add-search-pattern")
def add_search_pattern(pattern: str, user=Depends(verify_token)):
    """Add a new search pattern for GitHub-wide discovery"""
    if pattern not in GITHUB_SEARCH_PATTERNS:
        GITHUB_SEARCH_PATTERNS.append(pattern)
        
        if db is not None:
            db.collection("search_patterns").document(pattern).set({
                "pattern": pattern,
                "added_by": user.get("email", "unknown"),
                "added_at": time.time()
            })
        
        return {
            "message": f"Search pattern '{pattern}' added successfully",
            "total_patterns": len(GITHUB_SEARCH_PATTERNS)
        }
    else:
        return {
            "message": f"Search pattern '{pattern}' already exists",
            "total_patterns": len(GITHUB_SEARCH_PATTERNS)
        }

@app.get("/search-patterns")
def list_search_patterns():
    """List all search patterns used for GitHub-wide discovery"""
    return {
        "patterns": GITHUB_SEARCH_PATTERNS,
        "total": len(GITHUB_SEARCH_PATTERNS)
    }

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
