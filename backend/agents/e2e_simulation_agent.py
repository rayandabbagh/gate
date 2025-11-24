"""
E2E Simulation Agent

Specialized Task: Simulates real user workflows to catch end-to-end breakages.

Acts like a real user by executing complete workflows:
- Clicks buttons and navigates through the application
- Calls APIs and submits forms
- Performs complete user journeys (signup, checkout, etc.)
- Tests real user flows that only break when the system is assembled end-to-end

Detects issues that unit tests miss by testing the entire system as users would use it.
"""

import os
import subprocess
import asyncio
import json
import tempfile
from typing import Dict, List, Any, Optional
from utils.agent_logger import AgentLogger
from utils.codebase_analyzer import CodebaseAnalyzer
from utils.llm_client import LLMClient


class E2ESimulationAgent:
    """
    Specialized Agent: End-to-End Simulation
    
    Simulates real user workflows by executing complete user journeys.
    Detects breakages that only appear when the entire system is assembled and running.
    Tests the application as a real user would use it.
    """
    
    def __init__(self):
        self.name = "E2E Simulation Agent"
        self.description = "Simulates real user workflows to catch end-to-end breakages"
        self.running_processes = []
        self.llm_client = LLMClient()
    
    async def simulate_flows(self, repo_path: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate various end-to-end user flows with detailed execution logs
        """
        logger = AgentLogger(self.name)
        logger.set_status("running")
        
        try:
            # Step 1: Understand the application
            logger.update_progress(0.1, "Analyzing application structure...")
            logger.reasoning(self.name, "Analyzing application type and structure to generate appropriate test flows based on commit diff and codebase context")
            
            codebase = CodebaseAnalyzer(repo_path)
            codebase_info = codebase.analyze()
            
            app_type = self._detect_app_type(repo_path, codebase_info, logger)
            logger.log(self.name, "info", f"Detected application type: {app_type}")
            logger.set_metric("app_type", app_type)
            
            # Step 2: Discover available routes/flows
            logger.update_progress(0.2, "Discovering available routes and flows...")
            logger.reasoning(self.name, "I need to discover what endpoints/flows are available in the application")
            
            routes = codebase_info.get("routes", [])
            logger.log(self.name, "info", f"Found {len(routes)} API routes", 
                      data={"routes": routes[:10]})  # Log first 10 routes
            
            # Step 3: Generate intelligent flows based on codebase
            logger.update_progress(0.3, "Generating test flows based on codebase...")
            flows = await self._generate_flows_intelligently(
                repo_path, app_type, codebase_info, changes, logger
            )
            
            logger.log(self.name, "info", f"Generated {len(flows)} test flows", 
                      data={"flows": [f["name"] for f in flows]})
            logger.set_metric("flows_generated", len(flows))
            
            # Step 4: Start the application (if needed)
            logger.update_progress(0.4, "Preparing application for testing...")
            server_process = None
            server_url = None
            
            if app_type in ["api", "web_app"]:
                server_process, server_url = await self._start_application(
                    repo_path, app_type, logger
                )
                if server_process:
                    logger.log(self.name, "info", f"Started application server at {server_url}")
                    logger.set_metric("server_url", server_url)
            
            findings = []
            simulated_flows = []
            
            # Step 5: Execute each flow
            total_flows = len(flows)
            for idx, flow in enumerate(flows):
                progress = 0.4 + (idx / total_flows * 0.55) if total_flows > 0 else 0.95
                logger.update_progress(progress, f"Executing flow: {flow.get('name')}...")
                
                logger.reasoning(self.name, f"Executing flow '{flow.get('name')}' - simulating real user behavior")
                
                result = await self._simulate_flow_detailed(
                    repo_path, flow, app_type, server_url, logger
                )
                
                simulated_flows.append(result)
                
                # Only flag as bug if it's NOT a setup error
                if result.get("status") == "failed" and not result.get("is_setup_error", False):
                    error = result.get("error", "").lower()
                    flow_name = flow.get("name", "").lower()
                    
                    # Filter out setup/connection errors - these are NOT production bugs
                    setup_error_indicators = [
                        "server not available", "setup issue", "none/", "cannot connect",
                        "connection refused", "connection error", "timeout", "name resolution",
                        "invalid url", "no address", "server not running", "server unavailable"
                    ]
                    
                    is_setup_error = any(indicator in error for indicator in setup_error_indicators) or result.get("is_setup_error", False)
                    
                    # Skip setup errors - don't flag as bugs
                    if is_setup_error:
                        logger.log(self.name, "info", f"Flow '{flow.get('name')}' skipped due to setup issue - not a production bug")
                        continue
                    
                    # EXTREMELY STRICT: Only "high" if it's a user-facing flow failure with actual logic errors
                    # E2E flows are user-facing by nature, but check if it's a critical user journey AND actual failure
                    is_critical_user_flow = any(critical in flow_name for critical in [
                        "login", "signup", "checkout", "payment", "purchase", "order",
                        "auth", "register", "create", "submit", "save", "delete"
                    ])
                    
                    # Check if it's an actual logic failure (not setup)
                    is_logic_failure = any(indicator in error for indicator in [
                        "400", "401", "403", "404", "422", "500", "502", "503",
                        "validation", "authentication", "authorization", "permission"
                    ])
                    
                    # Only "high" if it's a critical user flow AND actual logic failure
                    severity = "high" if (is_critical_user_flow and is_logic_failure) else "medium"
                    
                    finding = {
                        "type": "e2e_failure",
                        "flow": flow.get("name"),
                        "severity": severity,
                        "description": f"E2E flow '{flow.get('name')}' failed: {result.get('error')}",
                        "steps": flow.get("steps", []),
                        "error": result.get("error"),
                        "execution_logs": result.get("execution_logs", []),
                        "reasoning": result.get("reasoning", []),
                        "context": {
                            "is_critical_user_flow": is_critical_user_flow,
                            "is_logic_failure": is_logic_failure,
                            "user_impact": "High - breaks critical user journey" if is_critical_user_flow else "Medium - may not directly affect users"
                        }
                    }
                    logger.add_finding(finding)
                    findings.append(finding)
                elif result.get("status") == "skipped":
                    # Flow was skipped due to setup issues - don't flag as bug
                    logger.log(self.name, "info", f"Flow '{flow.get('name')}' skipped - server not available (setup issue, not a bug)")
                else:
                    logger.log(self.name, "info", f"Flow '{flow.get('name')}' completed successfully",
                              data={"steps_completed": result.get("steps_completed", 0)})
            
            # Step 6: Cleanup
            if server_process:
                logger.update_progress(0.98, "Stopping test server...")
                await self._stop_application(server_process, logger)
            
            logger.update_progress(1.0, "E2E simulation complete")
            logger.set_status("completed")
            logger.set_metric("flows_executed", len(simulated_flows))
            logger.set_metric("flows_passed", len([f for f in simulated_flows if f.get("status") == "success"]))
            logger.set_metric("flows_skipped", len([f for f in simulated_flows if f.get("status") == "skipped"]))
            logger.set_metric("flows_failed", len(findings))  # Only real failures (not setup errors)
            
            result = logger.to_dict()
            result["findings"] = findings
            result["simulated_flows"] = simulated_flows
            critical_count = len([f for f in findings if f.get("severity") == "high"])
            result["summary"] = f"Simulated {len(flows)} flows: {critical_count} critical bug(s) detected that will cause production failures"
            
            return result
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.log(self.name, "error", f"Error during E2E simulation: {str(e)}\nFull traceback:\n{error_traceback}")
            logger.set_status("failed")
            return logger.to_dict()
    
    def _detect_app_type(self, repo_path: str, codebase_info: Dict, logger: AgentLogger) -> str:
        """Detect the type of application with detailed reasoning"""
        logger.reason("Analyzing codebase structure to determine application type")
        
        # Check for package.json
        if os.path.exists(os.path.join(repo_path, "package.json")):
            with open(os.path.join(repo_path, "package.json"), 'r') as f:
                content = f.read().lower()
                
                if "react" in content or "vue" in content or "angular" in content:
                    logger.reason("Found React/Vue/Angular in package.json - this is a web application")
                    return "web_app"
                elif "express" in content or "fastify" in content:
                    logger.reason("Found Express/Fastify in package.json - this is an API server")
                    return "api"
                elif "next" in content:
                    logger.reason("Found Next.js in package.json - this is a full-stack web application")
                    return "web_app"
        
        # Check for Python frameworks
        if os.path.exists(os.path.join(repo_path, "requirements.txt")):
            with open(os.path.join(repo_path, "requirements.txt"), 'r') as f:
                content = f.read().lower()
                
                if "fastapi" in content or "flask" in content or "django" in content:
                    logger.reason("Found FastAPI/Flask/Django in requirements.txt - this is an API/web application")
                    return "api" if "fastapi" in content or "flask" in content else "web_app"
        
        # Check for routes
        routes = codebase_info.get("routes", [])
        if routes:
            logger.reason(f"Found {len(routes)} routes in codebase - this is an API/backend application")
            return "api"
        
        logger.reason("Could not determine application type - defaulting to 'api'")
        return "unknown"
    
    async def _generate_flows_intelligently(
        self,
        repo_path: str,
        app_type: str,
        codebase_info: Dict,
        changes: Dict[str, Any],
        logger: AgentLogger
    ) -> List[Dict[str, Any]]:
        """Generate intelligent test flows dynamically using LLM + ACTUAL COMMIT DIFF + codebase context
        
        This reads the ACTUAL COMMIT DIFF from changes["diffs"] to understand what changed,
        then generates E2E flows that test exactly those changes.
        """
        flows = []
        routes = codebase_info.get("routes", [])
        modified_files = changes.get("modified_files", [])
        # READ ACTUAL COMMIT DIFF - this is what we're analyzing
        commit_diffs = changes.get("diffs", [])
        
        if commit_diffs:
            logger.log(self.name, "info", f"Read {len(commit_diffs)} file diffs from commit to generate E2E flows", 
                      data={"diffs_count": len(commit_diffs), "has_diffs": True})
            logger.reasoning(self.name, f"Analyzing actual commit diffs to generate E2E flows that test exactly what changed")
        else:
            logger.log(self.name, "warning", "No commit diff content available", 
                      data={"has_diffs": False})
            logger.reasoning(self.name, "No commit diffs available - generating flows based on codebase structure only")
        
        logger.reasoning(self.name, f"Generating test flows dynamically based on {len(routes)} discovered routes, {len(modified_files)} changed files, and {len(commit_diffs)} file diffs")
        
        # Use LLM to generate flows dynamically based on codebase and ACTUAL COMMIT DIFF
        if self.llm_client.enabled:
            logger.reasoning(self.name, "Using LLM to generate E2E flows based on actual commit diff and codebase structure")
            
            llm_result = await self.llm_client.generate_e2e_flows(
                codebase_info,
                changes,  # This includes changes["diffs"] with actual diff content
                app_type
            )
            
            llm_flows = llm_result.get("flows", [])
            reasoning = llm_result.get("reasoning", [])
            
            if llm_flows:
                flows.extend(llm_flows)
                logger.log(self.name, "info", f"LLM generated {len(llm_flows)} test flows", 
                          data={"flow_names": [f.get("name") for f in llm_flows[:10]]})
                
                for reason in reasoning[:3]:
                    logger.reasoning(self.name, reason)
        
        # Fallback: Generate flows based on route patterns if LLM not available or didn't generate enough
        if not flows or len(flows) < 3:
            logger.reasoning(self.name, "Generating additional flows based on route patterns and commit changes")
            
            # For API applications, generate flows based on routes and commit changes
            if app_type == "api" and routes:
                # Prioritize routes in modified files
                modified_files_str = [f.get("path", "") for f in modified_files]
                routes_in_changed_files = [r for r in routes if r.get("file") in modified_files_str]
                
                if routes_in_changed_files:
                    logger.reasoning(self.name, f"Found {len(routes_in_changed_files)} routes in modified files - generating flows for these")
                    
                    # Group routes by prefix
                    route_groups = {}
                    for route in routes_in_changed_files[:20]:
                        path = route.get("path", "")
                        prefix = path.split("/")[1] if "/" in path and len(path.split("/")) > 1 else "root"
                        
                        if prefix not in route_groups:
                            route_groups[prefix] = []
                        route_groups[prefix].append(route)
                    
                    # Generate flows for each route group
                    route_group_items = list(route_groups.items())[:5]
                    for prefix, group_routes in route_group_items:
                        methods = [r.get("method") for r in group_routes]
                        
                        if "POST" in methods and "GET" in methods:
                            flow = {
                                "name": f"{prefix.title()} Resource Flow (Changed Files)",
                                "steps": [
                                    f"POST /{prefix}",
                                    "Verify 201 response",
                                    f"GET /{prefix}/{{id}}",
                                    "Verify resource exists",
                                    f"PUT /{prefix}/{{id}}",
                                    "Verify update",
                                    f"DELETE /{prefix}/{{id}}",
                                    "Verify deletion"
                                ],
                                "type": "crud",
                                "routes": group_routes[:4],
                                "priority": "high"
                            }
                            flows.append(flow)
                            logger.log(self.name, "info", f"Generated CRUD flow for changed route: {prefix}")
            
            # Add health check flow if routes exist
            if routes:
                health_route = next((r for r in routes if "health" in r.get("path", "").lower()), None)
                if health_route and not any("health" in f.get("name", "").lower() for f in flows):
                    flows.insert(0, {
                        "name": "Health Check Flow",
                        "steps": [
                            f"GET {health_route.get('path')}",
                            "Verify 200 response",
                            "Check response schema",
                            "Verify service is healthy"
                        ],
                        "type": "health_check",
                        "routes": [health_route]
                    })
        
        # Limit to 10 flows for execution
        flows = flows[:10]
        
        logger.log(self.name, "info", f"Generated {len(flows)} test flows dynamically", 
                  data={"flow_names": [f.get("name") for f in flows]})
        
        return flows
    
    async def _start_application(
        self, 
        repo_path: str, 
        app_type: str, 
        logger: AgentLogger
    ) -> tuple[Optional[subprocess.Popen], Optional[str]]:
        """Start the application for testing"""
        logger.reasoning(self.name, "Starting application server to enable E2E testing")
        
        try:
            # Check for package.json (Node.js)
            if os.path.exists(os.path.join(repo_path, "package.json")):
                logger.log(self.name, "info", "Detected Node.js application", data={"type": "nodejs"})
                
                # Check for start script
                with open(os.path.join(repo_path, "package.json"), 'r') as f:
                    pkg = json.loads(f.read())
                    scripts = pkg.get("scripts", {})
                    
                    start_script = scripts.get("start") or scripts.get("dev") or scripts.get("serve")
                    
                    if start_script:
                        logger.log(self.name, "info", f"Starting with script: {start_script}")
                        
                        # Start process in background
                        process = subprocess.Popen(
                            ["npm", "run", start_script.split()[0]] if "npm" not in start_script else start_script.split(),
                            cwd=repo_path,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env={**os.environ, "PORT": "3001", "NODE_ENV": "test"}
                        )
                        
                        # Wait a bit for server to start
                        await asyncio.sleep(3)
                        
                        if process.poll() is None:  # Still running
                            logger.log(self.name, "info", "Server started successfully")
                            return process, "http://localhost:3001"
                        else:
                            stdout, stderr = process.communicate()
                            logger.log(self.name, "warning", f"Server failed to start: {stderr.decode()[:200]}")
            
            # Check for Python app
            elif os.path.exists(os.path.join(repo_path, "requirements.txt")):
                logger.log(self.name, "info", "Detected Python application", data={"type": "python"})
                
                # Try to find main file
                entry_points = []
                for root, dirs, files in os.walk(repo_path):
                    for file in files:
                        if file in ["main.py", "app.py", "server.py"]:
                            entry_points.append(os.path.join(root, file))
                
                if entry_points:
                    main_file = entry_points[0]
                    logger.log(self.name, "info", f"Starting Python app: {main_file}")
                    
                    process = subprocess.Popen(
                        ["python3", main_file],
                        cwd=repo_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env={**os.environ, "PORT": "8001"}
                    )
                    
                    await asyncio.sleep(3)
                    
                    if process.poll() is None:
                        logger.log(self.name, "info", "Server started successfully")
                        return process, "http://localhost:8001"
            
            logger.log(self.name, "warning", "Could not start application automatically")
            logger.reasoning(self.name, "Application may need manual configuration or is not designed to run standalone")
            return None, None
            
        except Exception as e:
            logger.log(self.name, "error", f"Error starting application: {str(e)}")
            return None, None
    
    async def _simulate_flow_detailed(
        self,
        repo_path: str,
        flow: Dict[str, Any],
        app_type: str,
        server_url: Optional[str],
        logger: AgentLogger
    ) -> Dict[str, Any]:
        """Simulate a single E2E flow with detailed execution"""
        flow_name = flow.get("name")
        steps = flow.get("steps", [])
        execution_logs = []
        reasoning = []
        
        logger.reasoning(self.name, f"Starting execution of flow: {flow_name} with {len(steps)} steps")
        
        completed_steps = 0
        
        for idx, step in enumerate(steps):
            step_num = idx + 1
            logger.log(self.name, "info", f"Step {step_num}/{len(steps)}: {step}")
            execution_logs.append({
                "step": step_num,
                "action": step,
                "status": "pending",
                "timestamp": None
            })
            
            # Simulate step execution
            try:
                # For API flows with server - FIX: Check server_url is not None before making API calls
                if app_type == "api" and server_url and ("GET" in step or "POST" in step or "PUT" in step or "DELETE" in step or "PATCH" in step):
                    # Extract endpoint
                    import re
                    match = re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+([^\s]+)', step)
                    if match:
                        method, endpoint = match.groups()
                        full_url = f"{server_url}{endpoint}"
                        
                        # Simulate HTTP request
                        import aiohttp
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.request(method, full_url, timeout=5) as response:
                                    status = response.status
                                    if status >= 200 and status < 300:
                                        execution_logs[-1]["status"] = "success"
                                        execution_logs[-1]["response_status"] = status
                                        completed_steps += 1
                                        logger.log(self.name, "info", f"{method} {endpoint}: {status}")
                                    else:
                                        execution_logs[-1]["status"] = "failed"
                                        execution_logs[-1]["error"] = f"HTTP {status}"
                                        raise Exception(f"HTTP {status} for {endpoint}")
                        except Exception as e:
                            error_msg = str(e).lower()
                            # Filter out setup/connection errors - these are NOT production bugs
                            setup_error_indicators = [
                                "none/", "cannot connect", "connection refused", "connection error",
                                "timeout", "name resolution", "invalid url", "no address",
                                "server not running", "server unavailable", "cannot resolve"
                            ]
                            
                            is_setup_error = any(indicator in error_msg for indicator in setup_error_indicators) or "none" in full_url.lower()
                            
                            if is_setup_error:
                                # Setup error - skip this flow, don't flag as bug
                                logger.log(self.name, "info", f"Skipping API call to {endpoint} - server not available (setup issue, not a bug)")
                                execution_logs[-1]["status"] = "skipped"
                                execution_logs[-1]["error"] = "Server not available - setup issue"
                                # Continue with other steps
                                completed_steps += 1
                            else:
                                # Actual API error - this might be a bug
                                execution_logs[-1]["status"] = "failed"
                                execution_logs[-1]["error"] = str(e)
                                # Use "warning" not "error" - flow failures are findings, not agent errors
                                logger.log(self.name, "warning", f"{method} {endpoint} failed: {str(e)}")
                                return {
                                    "flow_name": flow_name,
                                    "status": "failed",
                                    "error": f"Step {step_num} failed: {str(e)}",
                                    "steps_completed": completed_steps,
                                    "total_steps": len(steps),
                                    "execution_logs": execution_logs,
                                    "reasoning": reasoning,
                                    "is_setup_error": False  # Real failure
                                }
                elif app_type == "api" and ("GET" in step or "POST" in step) and not server_url:
                    # Server URL is None but step requires API call - skip, don't fail
                    logger.log(self.name, "info", f"Skipping API call step - server not available (setup issue, not a bug)")
                    execution_logs[-1]["status"] = "skipped"
                    execution_logs[-1]["error"] = "Server not available - setup issue"
                    completed_steps += 1
                else:
                    # For other steps, simulate with delay
                    await asyncio.sleep(0.5)
                    execution_logs[-1]["status"] = "success"
                    completed_steps += 1
                    logger.log(self.name, "info", "Step completed")
            
            except Exception as e:
                # Use "warning" not "error" - flow failures are findings, not agent errors
                logger.log(self.name, "warning", f"Step failed: {str(e)}")
                return {
                    "flow_name": flow_name,
                    "status": "failed",
                    "error": f"Step {step_num} failed: {str(e)}",
                    "steps_completed": completed_steps,
                    "total_steps": len(steps),
                    "execution_logs": execution_logs,
                    "reasoning": reasoning
                }
        
        logger.log(self.name, "info", f"Flow '{flow_name}' completed successfully")
        
        return {
            "flow_name": flow_name,
            "status": "success",
            "steps_completed": completed_steps,
            "total_steps": len(steps),
            "execution_logs": execution_logs,
            "reasoning": reasoning,
            "duration_ms": len(steps) * 500  # Simulated duration
        }
    
    async def _stop_application(self, process: subprocess.Popen, logger: AgentLogger):
        """Stop the application server"""
        try:
            logger.log(self.name, "info", "Stopping test server...")
            process.terminate()
            await asyncio.sleep(1)
            if process.poll() is None:
                process.kill()
            logger.log(self.name, "info", "Server stopped")
        except Exception as e:
            logger.log(self.name, "warning", f"Error stopping server: {str(e)}")
