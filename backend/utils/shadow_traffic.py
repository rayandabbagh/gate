"""
Shadow Traffic Utility
Actually runs two versions side-by-side and compares real responses
"""

import os
import subprocess
import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class ShadowTrafficRunner:
    """Runs actual shadow traffic - two versions side-by-side"""
    
    def __init__(self, repo_path: str, commit_sha: str):
        self.repo_path = repo_path
        self.commit_sha = commit_sha
        self.parent_sha: Optional[str] = None
        self.version_a_process: Optional[subprocess.Popen] = None  # Parent version
        self.version_b_process: Optional[subprocess.Popen] = None  # Current commit
        self.version_a_port = 8001  # Parent version port
        self.version_b_port = 8002  # Current commit port
        self.version_a_url = f"http://localhost:{self.version_a_port}"
        self.version_b_url = f"http://localhost:{self.version_b_port}"
    
    async def setup_dual_deployment(self) -> Tuple[bool, Optional[str]]:
        """
        Set up dual deployment:
        - Version A: parent commit (last good version)
        - Version B: current commit (what we're testing)
        """
        try:
            # Get parent commit
            result = subprocess.run(
                ['git', 'rev-parse', f'{self.commit_sha}^'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False, "Could not find parent commit"
            
            self.parent_sha = result.stdout.strip()
            
            # Start Version A (parent commit)
            version_a_started = await self._start_version(self.parent_sha, self.version_a_port, "A")
            if not version_a_started:
                return False, "Failed to start version A (parent commit)"
            
            # Start Version B (current commit - already checked out)
            version_b_started = await self._start_version(self.commit_sha, self.version_b_port, "B")
            if not version_b_started:
                await self._stop_version("A", self.version_a_process)
                return False, "Failed to start version B (current commit)"
            
            # Wait for both servers to be ready
            await asyncio.sleep(3)
            
            # Verify both are running
            version_a_ready = await self._check_server_ready(self.version_a_url)
            version_b_ready = await self._check_server_ready(self.version_b_url)
            
            if not version_a_ready or not version_b_ready:
                return False, f"Servers not ready - A: {version_a_ready}, B: {version_b_ready}"
            
            return True, None
        
        except Exception as e:
            return False, f"Error setting up dual deployment: {str(e)}"
    
    async def _start_version(self, commit_sha: str, port: int, version_label: str) -> bool:
        """Start a version of the application at a specific commit"""
        try:
            # Create temporary directory for this version
            temp_dir = os.path.join(self.repo_path, f".gate_shadow_{version_label}")
            
            # If doesn't exist or wrong commit, reclone
            if not os.path.exists(temp_dir) or not self._is_correct_commit(temp_dir, commit_sha):
                if os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Copy repo
                import shutil
                shutil.copytree(self.repo_path, temp_dir, ignore=shutil.ignore_patterns('.git', 'node_modules', '__pycache__'))
                
                # Checkout specific commit
                subprocess.run(
                    ['git', 'checkout', commit_sha],
                    cwd=temp_dir,
                    capture_output=True,
                    timeout=10
                )
            
            # Detect how to start the application
            start_command = self._detect_start_command(temp_dir)
            if not start_command:
                return False
            
            # Start server
            env = os.environ.copy()
            env['PORT'] = str(port)
            
            process = subprocess.Popen(
                start_command,
                cwd=temp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                shell=True
            )
            
            if version_label == "A":
                self.version_a_process = process
            else:
                self.version_b_process = process
            
            return True
        
        except Exception as e:
            print(f"Error starting version {version_label}: {str(e)}")
            return False
    
    def _is_correct_commit(self, repo_path: str, commit_sha: str) -> bool:
        """Check if repo is at correct commit"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() == commit_sha
        except:
            return False
    
    def _detect_start_command(self, repo_path: str) -> Optional[str]:
        """Detect how to start the application"""
        # Check for common patterns
        package_json = os.path.join(repo_path, "package.json")
        if os.path.exists(package_json):
            import json
            with open(package_json, 'r') as f:
                pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "start" in scripts:
                    return f"npm start"
                elif "dev" in scripts:
                    return f"npm run dev"
        
        # Check for Python apps
        main_py = os.path.join(repo_path, "main.py")
        if os.path.exists(main_py):
            return "python main.py"
        
        app_py = os.path.join(repo_path, "app.py")
        if os.path.exists(app_py):
            return "python app.py"
        
        # Check for uvicorn
        if os.path.exists(os.path.join(repo_path, "backend", "main.py")):
            return "cd backend && uvicorn main:app --port $PORT"
        
        return None
    
    async def _check_server_ready(self, url: str, max_retries: int = 10) -> bool:
        """Check if server is ready"""
        for _ in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                        if response.status < 500:
                            return True
            except:
                pass
            await asyncio.sleep(1)
        return False
    
    async def run_shadow_comparison(
        self, 
        endpoints: List[Dict[str, Any]],
        test_requests: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Run actual shadow traffic comparison:
        - Send same request to both versions
        - Compare responses (status, latency, body, schema)
        """
        comparisons = []
        discrepancies = []
        
        try:
            # Generate test requests if not provided
            if not test_requests:
                test_requests = self._generate_test_requests(endpoints)
            
            async with aiohttp.ClientSession() as session:
                for request in test_requests:
                    method = request.get("method", "GET")
                    path = request.get("path", "/")
                    data = request.get("data")
                    headers = request.get("headers", {})
                    
                    # Send request to both versions simultaneously
                    version_a_response, version_a_time = await self._send_request(
                        session, self.version_a_url + path, method, data, headers
                    )
                    version_b_response, version_b_time = await self._send_request(
                        session, self.version_b_url + path, method, data, headers
                    )
                    
                    # Compare responses
                    comparison = self._compare_responses(
                        path,
                        method,
                        version_a_response,
                        version_a_time,
                        version_b_response,
                        version_b_time
                    )
                    
                    comparisons.append(comparison)
                    
                    if comparison.get("has_discrepancy"):
                        discrepancies.append(comparison)
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Error running shadow comparison: {str(e)}",
                "comparisons": comparisons,
                "discrepancies": discrepancies
            }
        
        return {
            "success": True,
            "comparisons": comparisons,
            "discrepancies": discrepancies,
            "total_compared": len(comparisons),
            "discrepancies_found": len(discrepancies)
        }
    
    async def _send_request(
        self,
        session: aiohttp.ClientSession,
        url: str,
        method: str,
        data: Optional[Any],
        headers: Dict[str, str]
    ) -> Tuple[Dict[str, Any], float]:
        """Send request and measure latency"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with session.request(method, url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                body = await response.text()
                latency = (asyncio.get_event_loop().time() - start_time) * 1000  # ms
                
                # Try to parse JSON
                try:
                    body_json = json.loads(body)
                except:
                    body_json = None
                
                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": body,
                    "body_json": body_json,
                    "size": len(body)
                }, latency
        except Exception as e:
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            return {
                "status": 0,
                "error": str(e),
                "body": None,
                "body_json": None,
                "size": 0
            }, latency
    
    def _compare_responses(
        self,
        path: str,
        method: str,
        version_a_response: Dict[str, Any],
        version_a_latency: float,
        version_b_response: Dict[str, Any],
        version_b_latency: float
    ) -> Dict[str, Any]:
        """Compare two responses and identify discrepancies"""
        discrepancies = []
        has_discrepancy = False
        critical = False
        
        # Compare status codes
        if version_a_response.get("status") != version_b_response.get("status"):
            has_discrepancy = True
            critical = True
            discrepancies.append({
                "type": "status_code_mismatch",
                "description": f"Status code changed: {version_a_response.get('status')} -> {version_b_response.get('status')}",
                "critical": True
            })
        
        # Compare response bodies (if both are JSON)
        if version_a_response.get("body_json") and version_b_response.get("body_json"):
            schema_a = self._extract_schema(version_a_response["body_json"])
            schema_b = self._extract_schema(version_b_response["body_json"])
            
            if schema_a != schema_b:
                has_discrepancy = True
                discrepancies.append({
                    "type": "schema_change",
                    "description": f"Response schema changed",
                    "critical": False
                })
        
        # Compare latency (significant increase)
        latency_increase = version_b_latency - version_a_latency
        if latency_increase > 100:  # 100ms increase
            has_discrepancy = True
            discrepancies.append({
                "type": "latency_increase",
                "description": f"Latency increased by {latency_increase:.0f}ms ({version_a_latency:.0f}ms -> {version_b_latency:.0f}ms)",
                "critical": False
            })
        
        # Compare response size (significant change)
        size_a = version_a_response.get("size", 0)
        size_b = version_b_response.get("size", 0)
        if size_a > 0:
            size_change = abs(size_b - size_a) / size_a
            if size_change > 0.2:  # 20% change
                has_discrepancy = True
                discrepancies.append({
                    "type": "response_size_change",
                    "description": f"Response size changed by {size_change*100:.0f}%",
                    "critical": False
                })
        
        return {
            "endpoint": path,
            "method": method,
            "has_discrepancy": has_discrepancy,
            "critical": critical,
            "discrepancies": discrepancies,
            "version_a": {
                "status": version_a_response.get("status"),
                "latency_ms": version_a_latency,
                "size": size_a
            },
            "version_b": {
                "status": version_b_response.get("status"),
                "latency_ms": version_b_latency,
                "size": size_b
            }
        }
    
    def _extract_schema(self, obj: Any) -> Any:
        """Extract JSON schema structure"""
        if isinstance(obj, dict):
            return {k: self._extract_schema(v) for k, v in obj.items()}
        elif isinstance(obj, list) and len(obj) > 0:
            return [self._extract_schema(obj[0])]
        else:
            return type(obj).__name__
    
    def _generate_test_requests(self, endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate test requests for endpoints"""
        requests = []
        
        for endpoint in endpoints:
            path = endpoint.get("path", "/")
            method = endpoint.get("method", "GET")
            
            request = {
                "method": method,
                "path": path,
                "headers": {"Content-Type": "application/json"}
            }
            
            # Add test data for POST/PUT requests
            if method in ["POST", "PUT", "PATCH"]:
                request["data"] = {}  # Basic empty payload
            
            requests.append(request)
        
        return requests
    
    async def cleanup(self):
        """Stop both versions and clean up"""
        await self._stop_version("A", self.version_a_process)
        await self._stop_version("B", self.version_b_process)
        
        # Clean up temp directories
        for label in ["A", "B"]:
            temp_dir = os.path.join(self.repo_path, f".gate_shadow_{label}")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    async def _stop_version(self, version_label: str, process: Optional[subprocess.Popen]):
        """Stop a version"""
        if process:
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.poll() is None:
                    process.kill()
            except:
                pass

