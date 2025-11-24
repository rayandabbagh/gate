"""
Test Executor
Actually executes generated tests and flags failures as potential production bugs
"""

import os
import subprocess
import tempfile
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


class TestExecutor:
    """Executes generated tests and reports failures"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    async def execute_test_file(
        self, 
        test_file_path: str, 
        test_code: str,
        test_language: str = "python"
    ) -> Dict[str, Any]:
        """
        Write test code to file and execute it
        
        Returns: {
            "success": bool,
            "passed": int,
            "failed": int,
            "errors": List[str],
            "test_results": List[Dict]
        }
        """
        # Create test file in temp location or appropriate test directory
        test_dir = self._ensure_test_directory(test_file_path)
        full_test_path = os.path.join(test_dir, os.path.basename(test_file_path))
        
        # Write test code to file
        os.makedirs(os.path.dirname(full_test_path), exist_ok=True)
        with open(full_test_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        
        # Execute tests based on language
        if test_language == "python":
            return await self._execute_python_tests(full_test_path)
        elif test_language in ["javascript", "typescript"]:
            return await self._execute_js_tests(full_test_path)
        else:
            return {
                "success": False,
                "passed": 0,
                "failed": 0,
                "errors": [f"Unsupported test language: {test_language}"],
                "test_results": []
            }
    
    def _ensure_test_directory(self, test_file_path: str) -> str:
        """Ensure test directory exists, create if needed"""
        # Try to use existing test structure
        test_dir_candidates = [
            os.path.join(self.repo_path, "tests"),
            os.path.join(self.repo_path, "__tests__"),
            os.path.join(self.repo_path, "test"),
            os.path.dirname(os.path.join(self.repo_path, test_file_path)),
            os.path.join(self.repo_path, ".gate_tests")  # Fallback: dedicated directory
        ]
        
        for test_dir in test_dir_candidates:
            if os.path.exists(test_dir):
                return test_dir
        
        # Create fallback directory
        fallback_dir = os.path.join(self.repo_path, ".gate_tests")
        os.makedirs(fallback_dir, exist_ok=True)
        return fallback_dir
    
    async def _execute_python_tests(self, test_file_path: str) -> Dict[str, Any]:
        """Execute Python tests using pytest"""
        results = {
            "success": True,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "test_results": [],
            "output": ""
        }
        
        try:
            # Check if pytest is available
            pytest_check = subprocess.run(
                ["python", "-m", "pytest", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if pytest_check.returncode != 0:
                # Try pip installing pytest
                subprocess.run(
                    ["python", "-m", "pip", "install", "pytest", "-q"],
                    capture_output=True,
                    timeout=30
                )
            
            # Run pytest on the test file
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", test_file_path,
                "-v",
                "--tb=short",
                cwd=self.repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
            output = stdout.decode('utf-8', errors='ignore')
            results["output"] = output
            
            # Parse pytest output
            lines = output.split('\n')
            for line in lines:
                if "passed" in line.lower() and "failed" in line.lower():
                    # Format: "3 passed, 1 failed in 0.5s"
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.isdigit():
                                if i > 0 and "passed" in parts[i-1].lower():
                                    results["passed"] = int(part)
                                elif i > 0 and "failed" in parts[i-1].lower():
                                    results["failed"] = int(part)
                    except:
                        pass
                
                # Extract failed test details
                if "FAILED" in line or "ERROR" in line:
                    test_result = {
                        "name": line.strip(),
                        "status": "failed",
                        "error": ""
                    }
                    results["test_results"].append(test_result)
                
                # Extract error messages
                if "AssertionError" in line or "Error:" in line:
                    results["errors"].append(line.strip())
            
            # Overall success
            results["success"] = results["failed"] == 0 and process.returncode == 0
            
            # If no explicit counts found, check return code
            if results["passed"] == 0 and results["failed"] == 0:
                results["success"] = process.returncode == 0
                if process.returncode != 0:
                    results["failed"] = 1
                    results["errors"].append("Test execution failed - check output for details")
            
        except asyncio.TimeoutError:
            results["success"] = False
            results["errors"].append(f"Test execution timed out after 60 seconds")
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Error executing tests: {str(e)}")
        
        return results
    
    async def _execute_js_tests(self, test_file_path: str) -> Dict[str, Any]:
        """Execute JavaScript/TypeScript tests using jest or mocha"""
        results = {
            "success": True,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "test_results": [],
            "output": ""
        }
        
        try:
            # Check for package.json to determine test runner
            package_json_path = os.path.join(self.repo_path, "package.json")
            test_runner = "jest"  # Default
            
            if os.path.exists(package_json_path):
                import json
                with open(package_json_path, 'r') as f:
                    package_json = json.load(f)
                    scripts = package_json.get("scripts", {})
                    if "test" in scripts:
                        test_script = scripts["test"]
                        if "mocha" in test_script:
                            test_runner = "mocha"
                        elif "jest" in test_script or "jest" in package_json.get("devDependencies", {}):
                            test_runner = "jest"
            
            # Run tests
            if test_runner == "jest":
                process = await asyncio.create_subprocess_exec(
                    "npx", "jest", test_file_path,
                    cwd=self.repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "npx", "mocha", test_file_path,
                    cwd=self.repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
            
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
            output = stdout.decode('utf-8', errors='ignore')
            results["output"] = output
            
            # Parse output
            lines = output.split('\n')
            for line in lines:
                if "passing" in line.lower() and "failing" in line.lower():
                    # Format: "3 passing (50ms), 1 failing"
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.isdigit():
                                if i > 0 and "passing" in parts[i-1].lower():
                                    results["passed"] = int(part)
                                elif i > 0 and "failing" in parts[i-1].lower():
                                    results["failed"] = int(part)
                    except:
                        pass
                
                if "FAIL" in line or "Error:" in line:
                    results["errors"].append(line.strip())
            
            results["success"] = results["failed"] == 0 and process.returncode == 0
            
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"Error executing tests: {str(e)}")
        
        return results
    
    async def execute_all_generated_tests(
        self, 
        generated_tests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute all generated tests and aggregate results
        
        Returns: {
            "total_tests": int,
            "total_passed": int,
            "total_failed": int,
            "test_executions": List[Dict],
            "failures": List[Dict]  # These are potential production bugs!
        }
        """
        results = {
            "total_tests": len(generated_tests),
            "total_passed": 0,
            "total_failed": 0,
            "test_executions": [],
            "failures": []
        }
        
        for test_info in generated_tests:
            test_file_path = test_info.get("test_file_path", "")
            test_code = test_info.get("test_code", "")
            source_file = test_info.get("source_file", "")
            
            # Determine language from file extension
            if test_file_path.endswith(".py"):
                language = "python"
            elif test_file_path.endswith((".js", ".ts")):
                language = "javascript"
            else:
                language = "python"  # Default
            
            # Execute test
            execution_result = await self.execute_test_file(
                test_file_path,
                test_code,
                language
            )
            
            # Aggregate results
            results["total_passed"] += execution_result.get("passed", 0)
            results["total_failed"] += execution_result.get("failed", 0)
            
            execution_info = {
                "source_file": source_file,
                "test_file": test_file_path,
                "passed": execution_result.get("passed", 0),
                "failed": execution_result.get("failed", 0),
                "success": execution_result.get("success", False),
                "errors": execution_result.get("errors", []),
                "output": execution_result.get("output", "")[:500]  # Limit output
            }
            results["test_executions"].append(execution_info)
            
            # Flag failures as potential production bugs
            # CRITICAL: Only flag if it's an ACTUAL logic failure, not test setup issues
            if execution_result.get("failed", 0) > 0 or not execution_result.get("success", False):
                errors = execution_result.get("errors", [])
                output = execution_result.get("output", "").lower()
                error_text = " ".join(errors).lower() if errors else ""
                full_error_context = (error_text + " " + output).lower()
                
                # Filter out setup/import errors - these are NOT production bugs
                setup_error_indicators = [
                    "modulenotfounderror", "importerror", "import error",
                    "no module named", "cannot import", "failed to import",
                    "syntaxerror", "indentationerror", "file not found",
                    "permission denied", "file not found",
                    "test file not found", "cannot open",
                    "todo", "not implemented", "pass",
                    "test discovery", "no tests collected", "no tests ran",
                    "test file is empty", "collected 0 items"
                ]
                
                is_setup_error = any(indicator in full_error_context for indicator in setup_error_indicators)
                
                # Only flag if it's NOT a setup error AND it's an actual test logic failure
                if not is_setup_error:
                    # Check if this is a user-facing logic issue (assertion failures, validation errors, etc.)
                    is_logic_failure = any(indicator in full_error_context for indicator in [
                        "assertionerror", "assert", "assertion failed",
                        "validationerror", "valueerror", "typeerror",
                        "runtimeerror", "keyerror", "attributeerror"
                    ])
                    
                    # Check if this is a user-facing issue (API errors, validation failures, etc.)
                    is_user_facing = any(indicator in full_error_context for indicator in [
                        "assertionerror", "validation", "api", "endpoint", "route", 
                        "http", "status", "response", "request", "authentication",
                        "authorization", "permission", "access", "unauthorized"
                    ]) or any("/api/" in source_file.lower() or "/route" in source_file.lower() or 
                           "auth" in source_file.lower() or "payment" in source_file.lower() 
                           for _ in [1])
                    
                    # Only flag as "high" if it's a real logic failure that WILL affect end users
                    # If it's just a setup issue or non-user-facing error, don't flag it
                    if is_logic_failure and is_user_facing:
                        severity = "high"
                    elif is_logic_failure:
                        severity = "medium"  # Logic failure but not user-facing
                    else:
                        # Not a real failure - skip it
                        continue
                    
                    failure = {
                        "type": "test_failure",
                        "file": source_file,
                        "test_file": test_file_path,
                        "severity": severity,
                        "description": f"Generated tests failed for {source_file} - {execution_result.get('failed', 0)} test(s) failed due to logic errors",
                        "suggested_fix": f"Review test failures in {test_file_path}. These tests were generated to proof-test commit changes. {'This indicates a user-facing bug that must be fixed.' if is_user_facing else 'Review to determine if this affects end users.'}",
                        "reasoning": [
                            f"Tests were autonomously generated for {source_file} based on commit changes",
                            f"Test execution resulted in {execution_result.get('failed', 0)} failure(s) due to actual logic errors (not setup issues)",
                            "User-facing impact" if is_user_facing else "May not directly affect end users - review needed"
                        ],
                        "context": {
                            "test_execution_result": execution_result,
                            "errors": execution_result.get("errors", []),
                            "is_user_facing": is_user_facing,
                            "is_logic_failure": is_logic_failure
                        }
                    }
                    results["failures"].append(failure)
                # else: It's a setup error - silently skip (don't flag as bug)
        
        return results

