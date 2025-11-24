"""
Gate - AI Agent Team for Post-Merge Bug Prevention
Main API server that orchestrates the agent team
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import os
import subprocess
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from agents.regression_agent import RegressionAgent
from agents.test_generation_agent import TestGenerationAgent
from agents.e2e_simulation_agent import E2ESimulationAgent
from agents.shadow_comparison_agent import ShadowComparisonAgent
from utils.debug_bundle import DebugBundleGenerator
from utils.repo_analyzer import RepoAnalyzer
from utils.github_handler import GitHubHandler

app = FastAPI(title="Gate - AI Agent Team", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents
regression_agent = RegressionAgent()
test_agent = TestGenerationAgent()
e2e_agent = E2ESimulationAgent()
shadow_agent = ShadowComparisonAgent()
bundle_generator = DebugBundleGenerator()
repo_analyzer = RepoAnalyzer()
github_handler = GitHubHandler()


class AnalyzeRequest(BaseModel):
    source_type: str = "local"  # "local" or "github"
    repo_path: Optional[str] = None
    github_url: Optional[str] = None
    commit_sha: str  # REQUIRED - this is what we're analyzing to check if it's production-safe
    branch: Optional[str] = "main"


class AgentStatus(BaseModel):
    agent_name: str
    status: str  # "running", "completed", "failed"
    progress: float
    findings: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


@app.get("/")
def root():
    return {
        "name": "Gate",
        "description": "AI Agent Team That Stops Production Bugs Before They Reach Your Users",
        "agents": [
            "Regression Agent",
            "Test Generation Agent",
            "E2E Simulation Agent",
            "Shadow/Canary Comparison Agent"
        ]
    }


@app.post("/analyze")
async def analyze_release(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Analyze a SPECIFIC COMMIT to check if it's production-safe.
    
    The commit SHA is REQUIRED - this is what we're analyzing.
    The repository is just context to understand the codebase structure.
    Agents read the commit diff, understand it in full codebase context, and check for bugs.
    """
    # Validate commit SHA
    if not request.commit_sha or not request.commit_sha.strip():
        raise HTTPException(
            status_code=400, 
            detail="Commit SHA is REQUIRED. We analyze specific commits to check if they're production-safe before they reach users."
        )
    
    commit_sha = request.commit_sha.strip()
    
    # Validate commit SHA format (at least 7 characters for short SHA, up to 40 for full SHA)
    if len(commit_sha) < 7 or not all(c in '0123456789abcdefABCDEF' for c in commit_sha):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid commit SHA format: {commit_sha}. Please provide a valid git commit SHA."
        )
    
    repo_path = None
    
    # Handle GitHub repositories
    if request.source_type == "github":
        if not request.github_url:
            raise HTTPException(status_code=400, detail="GitHub URL is required when source_type is 'github'")
        
        try:
            # Clone GitHub repository and checkout the specific commit
            repo_path = github_handler.clone_repository(request.github_url, commit_sha)
            if not repo_path:
                raise HTTPException(status_code=500, detail="Failed to clone GitHub repository")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error cloning GitHub repository: {str(e)}")
    
    # Handle local repositories
    else:
        if not request.repo_path:
            raise HTTPException(status_code=400, detail="Repository path is required when source_type is 'local'")
        
        repo_path = request.repo_path
        
        # Check if user accidentally entered a GitHub URL
        if repo_path.startswith('http') or 'github.com' in repo_path:
            raise HTTPException(
                status_code=400, 
                detail=f"This looks like a GitHub URL. Please select 'GitHub Repository' as the source type, or provide a local file path. Received: {repo_path}"
            )
        
        if not os.path.exists(repo_path):
            raise HTTPException(
                status_code=400, 
                detail=f"Repository path not found: {repo_path}. Please check the path is correct. If this is a GitHub repository, select 'GitHub Repository' as the source type."
            )
        
        # Verify commit exists in local repo
        try:
            result = subprocess.run(
                ['git', 'cat-file', '-t', commit_sha],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0 or 'commit' not in result.stdout.lower():
                raise HTTPException(
                    status_code=400,
                    detail=f"Commit {commit_sha} not found in repository {repo_path}. Please verify the commit SHA is correct."
                )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=400, detail=f"Timeout checking commit {commit_sha} in repository")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error verifying commit {commit_sha}: {str(e)}")
    
    # Start analysis
    analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Run analysis in background
    background_tasks.add_task(
        run_agent_analysis,
        analysis_id,
        repo_path,
        commit_sha,
        request.branch or "main"
    )
    
    return {
        "analysis_id": analysis_id,
        "status": "started",
        "message": f"Analyzing commit {commit_sha[:8]} to check if it's production-safe. Use /status/{analysis_id} to check progress.",
        "commit_sha": commit_sha,
        "repo_path": repo_path
    }


# Store analysis results in memory (in production, use database/cache)
analysis_storage: Dict[str, Dict[str, Any]] = {}

@app.get("/status/{analysis_id}")
async def get_status(analysis_id: str):
    """Get the status of an ongoing analysis with detailed logs"""
    if analysis_id not in analysis_storage:
        return {
            "analysis_id": analysis_id,
            "status": "not_found",
            "agents": [],
            "codebase_context": {}
        }
    
    stored = analysis_storage[analysis_id]
    return {
        "analysis_id": analysis_id,
        "status": stored.get("status", "running"),
        "agents": stored.get("agents", []),
        "codebase_context": stored.get("codebase_context", {})
    }


@app.get("/results/{analysis_id}")
async def get_results(analysis_id: str):
    """Get the final results and DebugBundle for an analysis"""
    if analysis_id not in analysis_storage:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    
    stored = analysis_storage[analysis_id]
    results = stored.get("results", {})
    
    return {
        "analysis_id": analysis_id,
        "safe": results.get("safe", True),
        "bugs_found": results.get("bugs_found", False),
        "issues_found": results.get("issues_found", 0),
        "critical_count": results.get("critical_count", 0),  # CRITICAL: Frontend needs this!
        "medium_count": results.get("medium_count", 0),
        "low_count": results.get("low_count", 0),
        "debug_bundle": results.get("debug_bundle"),
        "summary": results.get("summary", "Analysis complete"),
        "bugs_explanation": results.get("bugs_explanation", "No urgent bugs detected."),
        "what_was_pushed": results.get("what_was_pushed", "No changes detected."),
        "production_bugs": results.get("production_bugs", "No urgent bugs detected."),
        "pre_production_warning": results.get("pre_production_warning"),
        "agents": stored.get("agents", []),
        "codebase_context": stored.get("codebase_context", {}),
        "commit_sha": results.get("commit_sha") or stored.get("commit_sha"),
        "commit_diffs": results.get("commit_diffs", []),
        "full_diff": results.get("full_diff", "")
    }


async def run_agent_analysis(analysis_id: str, repo_path: str, commit_sha: str, branch: str):
    """
    Orchestrate all agents to analyze the release with detailed logging
    """
    try:
        # Initialize storage
        analysis_storage[analysis_id] = {
            "status": "running",
            "agents": [],
            "repo_path": repo_path,
            "commit_sha": commit_sha,
            "branch": branch,
            "codebase_context": {}
        }
        
        # Step 1: Analyze codebase structure (for context)
        from utils.codebase_analyzer import CodebaseAnalyzer
        codebase_analyzer = CodebaseAnalyzer(repo_path)
        codebase_info = codebase_analyzer.analyze()
        analysis_storage[analysis_id]["codebase_context"] = codebase_info
        
        # Step 2: Analyze repository changes
        print(f"[{analysis_id}] Analyzing repository changes...")
        changes = repo_analyzer.analyze_changes(repo_path, commit_sha, branch)
        
        # Initialize agent results
        agent_results = {
            "regression": None,
            "test_generation": None,
            "e2e_simulation": None,
            "shadow_comparison": None
        }
        
        # Step 2: Run Regression Agent
        print(f"[{analysis_id}] Running Regression Agent...")
        regression_results = await regression_agent.analyze(repo_path, changes)
        agent_results["regression"] = regression_results
        analysis_storage[analysis_id]["agents"] = [
            {
                "agent_name": "Regression Agent",
                "status": regression_results.get("status", "completed"),
                "progress": regression_results.get("progress", 1.0),
                "findings": regression_results.get("findings", []),
                "logs": regression_results.get("logs", []),
                "reasoning": regression_results.get("reasoning", []),
                "metrics": regression_results.get("metrics", {}),
                "summary": regression_results.get("summary", "")
            }
        ]
        
        # Step 3: Run Test Generation Agent
        print(f"[{analysis_id}] Running Test Generation Agent...")
        test_results = await test_agent.generate_tests(repo_path, changes)
        agent_results["test_generation"] = test_results
        analysis_storage[analysis_id]["agents"].append({
            "agent_name": "Test Generation Agent",
            "status": test_results.get("status", "completed"),
            "progress": test_results.get("progress", 1.0),
            "findings": test_results.get("findings", []),
            "logs": test_results.get("logs", []),
            "reasoning": test_results.get("reasoning", []),
            "metrics": test_results.get("metrics", {}),
            "summary": test_results.get("summary", "")
        })
        
        # Step 4: Run E2E Simulation Agent
        print(f"[{analysis_id}] Running E2E Simulation Agent...")
        e2e_results = await e2e_agent.simulate_flows(repo_path, changes)
        agent_results["e2e_simulation"] = e2e_results
        analysis_storage[analysis_id]["agents"].append({
            "agent_name": "E2E Simulation Agent",
            "status": e2e_results.get("status", "completed"),
            "progress": e2e_results.get("progress", 1.0),
            "findings": e2e_results.get("findings", []),
            "logs": e2e_results.get("logs", []),
            "reasoning": e2e_results.get("reasoning", []),
            "metrics": e2e_results.get("metrics", {}),
            "summary": e2e_results.get("summary", ""),
            "simulated_flows": e2e_results.get("simulated_flows", [])
        })
        
        # Step 5: Run Shadow Comparison Agent
        print(f"[{analysis_id}] Running Shadow Comparison Agent...")
        shadow_results = await shadow_agent.compare_versions(repo_path, changes)
        agent_results["shadow_comparison"] = shadow_results
        analysis_storage[analysis_id]["agents"].append({
            "agent_name": "Shadow Comparison Agent",
            "status": shadow_results.get("status", "completed"),
            "progress": shadow_results.get("progress", 1.0),
            "findings": shadow_results.get("findings", []),
            "logs": shadow_results.get("logs", []),
            "reasoning": shadow_results.get("reasoning", []),
            "metrics": shadow_results.get("metrics", {}),
            "summary": shadow_results.get("summary", "")
        })
        
        # CRITICAL FIX: Aggregate findings from the SAME source that frontend agent cards use!
        # Frontend reads from analysis_storage[analysis_id]["agents"], so we MUST use that too!
        # This ensures Results tab shows the SAME count as agent cards!
        
        all_agent_data = analysis_storage[analysis_id].get("agents", [])
        
        # Extract findings from stored agent data (SAME as what frontend sees)
        all_findings = []
        for agent_data in all_agent_data:
            agent_findings = agent_data.get("findings", [])
            all_findings.extend(agent_findings)
        
        # DEBUG: Count critical bugs from stored agent data (same as frontend)
        print(f"[{analysis_id}] DEBUG: Counting critical bugs from stored agent data (same source as frontend):")
        total_critical_from_agents = 0
        for agent_data in all_agent_data:
            agent_name = agent_data.get("agent_name", "Unknown")
            agent_findings = agent_data.get("findings", [])
            agent_high = [f for f in agent_findings if f.get("severity") == "high"]
            critical_count = len(agent_high)
            total_critical_from_agents += critical_count
            print(f"  {agent_name}: {len(agent_findings)} total findings, {critical_count} critical (severity='high')")
        
        # ONLY flag CRITICAL bugs - must be truly critical (will cause production failures)
        # Agents only set severity="high" when something is truly critical
        # So we ONLY flag bugs with severity="high" (nothing else)
        urgent_bugs = [f for f in all_findings if f.get("severity") == "high"]
        has_urgent_bugs = len(urgent_bugs) > 0
        
        print(f"[{analysis_id}] DEBUG: TOTAL CRITICAL BUGS: {len(urgent_bugs)} (sum from agents: {total_critical_from_agents})")
        print(f"[{analysis_id}] Urgent bugs caught before production: {len(urgent_bugs)} critical bugs")
        if has_urgent_bugs:
            print(f"[{analysis_id}]   These WILL cause production failures - must fix before deployment")
        
        # ONLY generate debug bundle if there are urgent bugs to fix
        # Debug bundle is ONLY for feeding to Cursor to patch bugs
        debug_bundle = None
        if has_urgent_bugs:
            debug_bundle = bundle_generator.generate_bundle(
                analysis_id=analysis_id,
                regression_results=regression_results,
                test_results=test_results,
                e2e_results=e2e_results,
                shadow_results=shadow_results,
                repo_path=repo_path,
                changes=changes,
                codebase_context=analysis_storage[analysis_id].get("codebase_context", {}),
                commit_sha=commit_sha
            )
        else:
            print(f"[{analysis_id}] No urgent bugs detected - skipping debug bundle generation (only generated for urgent bugs)")
        
        # Store final results (ONLY URGENT bugs)
        critical_count = len(urgent_bugs)
        
        # Get actual commit diff for display
        commit_diffs = changes.get("diffs", [])
        full_diff = changes.get("full_diff", "")
        
        analysis_storage[analysis_id]["status"] = "completed"
        analysis_storage[analysis_id]["results"] = {
            "safe": not has_urgent_bugs,
            "bugs_found": has_urgent_bugs,
            "issues_found": critical_count,  # Only count urgent bugs
            "critical_count": critical_count,
            "medium_count": 0,  # Don't flag medium
            "low_count": 0,  # Don't flag low
            "debug_bundle": debug_bundle,  # Only generated if urgent bugs found
            "summary": f"Commit analyzed for production bugs. This commit might introduce {critical_count} urgent bug(s) that WILL cause production failures." if has_urgent_bugs else "Commit analyzed for production bugs. No urgent bugs detected - appears safe for production.",
            "bugs_explanation": debug_bundle.get("bugs_explanation", "No urgent bugs detected.") if debug_bundle else "No urgent bugs detected. Debug bundle not generated (only generated when urgent bugs are found).",
            "what_was_pushed": debug_bundle.get("what_was_pushed", "No changes detected.") if debug_bundle else "No urgent bugs detected - no debug bundle generated.",
            "production_bugs": debug_bundle.get("production_bugs", "No urgent bugs detected.") if debug_bundle else "No urgent bugs detected - no debug bundle generated.",
            "pre_production_warning": debug_bundle.get("pre_production_warning") if debug_bundle else None,
            "codebase_context": analysis_storage[analysis_id].get("codebase_context", {}),
            "commit_sha": commit_sha,
            "commit_diffs": commit_diffs,  # Include actual diffs
            "full_diff": full_diff  # Include full unified diff
        }
        
        print(f"Analysis {analysis_id} completed. Issues found: {len(all_findings)}")
        
    except Exception as e:
        print(f"Error in analysis {analysis_id}: {str(e)}")
        if analysis_id in analysis_storage:
            analysis_storage[analysis_id]["status"] = "failed"
            analysis_storage[analysis_id]["error"] = str(e)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="0.0.0.0", port=port)

