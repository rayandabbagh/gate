"""
LLM Client
Integrates with Gemini API for intelligent code analysis
"""

import os
import json
from typing import Dict, List, Any, Optional
import google.generativeai as genai_api

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will rely on system environment variables


class LLMClient:
    """Client for Gemini API integration"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai_api.configure(api_key=self.api_key)
            # Use gemini-flash-latest (fast and capable)
            model_name = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
            try:
                self.client = genai_api.GenerativeModel(model_name)
                self.enabled = True
            except Exception as e:
                self.client = None
                self.enabled = False
                print(f"Warning: Could not initialize Gemini model '{model_name}': {str(e)}. LLM features disabled.")
        else:
            self.client = None
            self.enabled = False
            print("Warning: GEMINI_API_KEY not found. LLM features disabled.")
    
    async def analyze_codebase_context(
        self, 
        file_path: str, 
        content: str, 
        codebase_summary: Dict[str, Any],
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze code in context of entire codebase - Regression Agent
        """
        if not self.enabled:
            return {"analysis": "LLM not available", "reasoning": []}
        
        try:
            prompt = f"""
You are the Regression Agent, a specialized AI agent focused on preventing production bugs by detecting risky changes.

YOUR ROLE:
- You understand the entire codebase, not just the diff
- You detect risky changes, logic shifts, side-effects, missing guards, dependency drift
- You think like a senior engineer who can spot when "This will break something"
- You analyze changes in the context of the whole system, identifying dependencies and relationships
- **CRITICAL: You are EXTREMELY STRICT - only flag something as "critical" if it WILL directly affect end users of the product**

**EXTREMELY IMPORTANT - BUG DESCRIPTION REQUIREMENTS:**
When you identify a risk, you MUST provide an EXTREMELY DETAILED description that explains:
1. **EXACTLY what code was changed/removed** (specific functions, classes, methods, lines)
2. **EXACTLY what might break** (which files, functions, or user flows will fail)
3. **EXACTLY why it will break** (what dependencies rely on this code, what conditions will cause failure)
4. **EXACTLY how end users will be affected** (what error will they see, what feature will stop working, what data might be lost)
5. **EXACTLY what conditions trigger the bug** (specific user actions, API calls, edge cases)

DO NOT use vague phrases like:
- "may break dependent code" → Instead: "Function `authenticate_user()` was removed, but it's called by `login_api.py:42`, `session_manager.py:15`, and `oauth_handler.py:89`. Users attempting to log in will receive `AttributeError: module has no attribute 'authenticate_user'` and authentication will completely fail."
- "possible validation removal" → Instead: "The `validate_email()` check was deleted from line 23-28. User registration endpoint `POST /api/register` in `auth_routes.py` now accepts invalid emails like 'test@' or '@domain.com', which will cause database constraint violations and registration failures."
- "high coupling risk" → Instead: "File `oauth_service.py` was modified and is imported by 24 other files including `login_api.py`, `session_manager.py`, `api_middleware.py`. If the `get_access_token()` method signature changed, all 24 files will break at runtime with `TypeError: get_access_token() takes X positional arguments but Y were given`."

YOUR APPROACH:
1. Read the commit diff and understand what changed
2. Analyze the change in context of the entire codebase structure
3. Identify what could break, what side effects might occur, what dependencies might be affected
4. Look for missing guards, validation, error handling
5. Check for logic shifts that could cause regressions

**SEVERITY GUIDELINES (EXTREMELY STRICT):**
- **CRITICAL (severity="high")**: ONLY flag if the change WILL cause:
  - End users to experience errors, crashes, or broken functionality
  - Data loss or corruption that affects users
  - Security vulnerabilities that expose user data
  - Breaking changes that will cause user-facing features to fail
  - Missing critical validation that allows invalid user input to break the system
- **MEDIUM (severity="medium")**: Code quality issues, potential future problems, or issues that don't directly affect end users
- **LOW (severity="low")**: Minor improvements, refactoring suggestions, or non-user-facing issues

**DO NOT flag as CRITICAL:**
- Code style issues
- Missing tests (unless the code will break for users)
- Performance optimizations (unless it causes user-facing slowness)
- Internal refactoring (unless it breaks user functionality)
- Developer experience issues
- Non-user-facing code paths
- **Documentation-only changes (comments, docstrings, READMEs)** - These do NOT affect runtime behavior
- **Cosmetic changes** - Formatting, whitespace, variable renaming (unless it breaks imports)
- **Comment removal** - Removing comments or docstrings does NOT break code execution
- **Code that's never executed** - Dead code, unused functions, unreachable code

Codebase Summary:
- Total files: {codebase_summary.get('total_files', 0)}
- File types: {', '.join([f'{len(files) if isinstance(files, list) else files} {ext}' for ext, files in codebase_summary.get('files_by_extension', {}).items()]) if codebase_summary.get('files_by_extension') else 'unknown'}
- Routes found: {len(codebase_summary.get('routes', [])) if isinstance(codebase_summary.get('routes'), list) else codebase_summary.get('routes', 0)}
- Entry points: {', '.join(codebase_summary.get('entry_points', [])) if isinstance(codebase_summary.get('entry_points'), list) else str(codebase_summary.get('entry_points', 'unknown'))}

File: {file_path}
Change: {changes.get('additions', 0)} additions, {changes.get('deletions', 0)} deletions

    Code:
    ```
    {content[:2000]}
    ```

    Actual Commit Diff (this is what changed):
    ```
    {changes.get('diff', 'No diff available')[:1500]}
    ```

    Analyze this file change (from the diff above) in the context of the entire codebase:
1. What EXACTLY was changed/removed? (specific functions, methods, lines)
2. What EXACTLY will break? (which files, functions, or user flows)
3. Why EXACTLY will it break? (what dependencies rely on this, what conditions cause failure)
4. How EXACTLY will end users be affected? (what error, what feature failure, what data loss)
5. What EXACTLY triggers the bug? (specific user actions, API calls, edge cases)

Respond in JSON format with:
{{
    "risks": ["EXTREMELY DETAILED risk description 1", "EXTREMELY DETAILED risk description 2"],
    "reasoning": ["EXACT explanation of why risk1 will break", "EXACT explanation of why risk2 will break"],
    "suggested_checks": ["specific check1", "specific check2"],
    "detailed_description": "A SINGLE EXTREMELY DETAILED description explaining EXACTLY what will break, how, why, and when end users will be affected. Include specific file names, function names, line numbers, error messages, and user-facing symptoms."
}}
"""
            
            response = self.client.generate_content(prompt)
            result_text = response.text
            
            # Try to parse JSON from response
            try:
                if "```json" in result_text:
                    json_start = result_text.find("```json") + 7
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                elif "```" in result_text:
                    json_start = result_text.find("```") + 3
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                
                result = json.loads(result_text)
                return result
            except:
                # Fallback if JSON parsing fails
                return {
                    "analysis": result_text[:500],
                    "reasoning": [result_text] if result_text else []
                }
        
        except Exception as e:
            print(f"Error in LLM analysis: {str(e)}")
            return {"analysis": f"Error: {str(e)}", "reasoning": []}
    
    async def generate_test_suggestions(
        self,
        file_path: str,
        content: str,
        functions: List[str],
        classes: List[str],
        commit_diff: str = ""
    ) -> Dict[str, Any]:
        """Generate intelligent test suggestions using LLM - Test Generation Agent
        
        Args:
            commit_diff: The ACTUAL commit diff content showing what changed
        """
        if not self.enabled:
            return {"tests": [], "reasoning": []}
        
        try:
            diff_section = ""
            if commit_diff:
                diff_section = f"""
Actual Commit Diff (this is what changed - generate tests for THIS):
```
{commit_diff[:2000]}
```
"""
            
            prompt = f"""
You are the Test Generation Agent, a specialized AI agent focused on autonomously generating comprehensive tests to proof-test commits before production.

YOUR ROLE:
- You read the ACTUAL COMMIT DIFF and understand EXACTLY what code changed
- You autonomously generate unit, integration, property, and invariance tests for changed code paths
- You create tests that catch bugs before they reach production
- You focus on testing EXACTLY the code paths that changed in the diff
- **CRITICAL: You are EXTREMELY STRICT - only flag test failures as "critical" if they indicate bugs that WILL directly affect end users**

**SEVERITY GUIDELINES (EXTREMELY STRICT):**
- **CRITICAL (severity="high")**: ONLY flag if test failures indicate:
  - User-facing functionality is broken (APIs return errors, UI breaks, features don't work)
  - Data integrity issues that affect user data
  - Security vulnerabilities that expose user information
  - Breaking changes that cause user workflows to fail
- **MEDIUM (severity="medium")**: Test failures in non-user-facing code, edge cases, or internal logic issues
- **LOW (severity="low")**: Missing test coverage for non-critical paths, code quality issues

YOUR APPROACH:
1. Read the commit diff below to understand what changed
2. Understand the functions, classes, and logic that changed (from the diff)
3. Generate test cases that cover:
   - **UNIT TESTS**: Normal operation scenarios for the changed code, edge cases, boundary conditions, error handling
   - **INTEGRATION TESTS**: Test how changed code integrates with other parts of the system (APIs, databases, external services, dependencies)
   - **REGRESSION TESTS**: Test that existing functionality still works after these changes
   - **END-TO-END TESTS**: Test complete workflows that use the changed code

**CRITICAL: Generate BOTH unit tests AND integration tests. Integration tests are essential to catch regressions where changed code breaks integration with other parts of the system.**

File: {file_path}
Functions Changed: {', '.join(functions[:10])}
Classes Changed: {', '.join(classes[:5])}

Current Code:
```
{content[:2000]}
```
{diff_section}
Generate comprehensive test cases that will catch production bugs. 
Focus EXACTLY on what changed in the diff above - test those specific changes.

Respond in JSON:
{{
    "test_cases": [{{"name": "test_name", "description": "what it tests", "code": "test code"}}],
    "reasoning": ["why these tests are needed based on the diff"]
}}
"""
            
            response = self.client.generate_content(prompt)
            result_text = response.text
            
            try:
                if "```json" in result_text:
                    json_start = result_text.find("```json") + 7
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                elif "```" in result_text:
                    json_start = result_text.find("```") + 3
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                
                result = json.loads(result_text)
                return result
            except:
                return {
                    "tests": [],
                    "reasoning": [result_text] if result_text else []
                }
        
        except Exception as e:
            print(f"Error in LLM test generation: {str(e)}")
            return {"tests": [], "reasoning": []}
    
    async def explain_finding(
        self,
        finding: Dict[str, Any],
        codebase_context: Dict[str, Any],
        agent_name: Optional[str] = None
    ) -> str:
        """Generate human-readable explanation of a finding - can be called by any agent"""
        if not self.enabled:
            return finding.get("description", "")
        
        try:
            agent_context = ""
            if agent_name:
                agent_context = f"This finding was detected by the {agent_name}. "
            
            prompt = f"""
You are an AI agent helping developers fix production bugs caught before deployment.

{agent_context}Explain this code analysis finding in a way that's immediately actionable for fixing it:

Finding:
- Type: {finding.get('type')}
- File: {finding.get('file')}
- Description: {finding.get('description')}
- Severity: {finding.get('severity')}

Codebase Context:
- Total files analyzed: {codebase_context.get('total_files', 0)}
- Related files: {len(codebase_context.get('dependencies', {}).get(finding.get('file'), []))}

Generate a clear, concise explanation of:
1. What the issue is
2. Why it's a problem in context of the full codebase
3. How to fix it

Keep it under 200 words and be actionable.
"""
            
            response = self.client.generate_content(prompt)
            return response.text.strip()
        
        except Exception as e:
            return finding.get("description", "")
    
    async def generate_e2e_flows(
        self,
        codebase_info: Dict[str, Any],
        changes: Dict[str, Any],
        app_type: str
    ) -> Dict[str, Any]:
        """Generate E2E test flows dynamically based on codebase and ACTUAL COMMIT DIFF - E2E Simulation Agent"""
        if not self.enabled:
            return {"flows": [], "reasoning": []}
        
        try:
            modified_files = [f.get("path") for f in changes.get("modified_files", [])]
            routes = codebase_info.get("routes", [])
            
            # Include ACTUAL COMMIT DIFF in prompt
            commit_diffs = changes.get("diffs", [])
            diff_section = ""
            if commit_diffs:
                diff_summary = "\n".join([f"File: {d.get('file')}\n{d.get('diff', '')[:1000]}..." for d in commit_diffs[:5]])
                diff_section = f"""
Actual Commit Diff (this is what changed - generate E2E flows that test THESE changes):
```diff
{diff_summary}
```
"""
            
            prompt = f"""
You are the E2E Simulation Agent, a specialized AI agent focused on simulating real user workflows to catch end-to-end breakages.

YOUR ROLE:
- You read the ACTUAL COMMIT DIFF and understand exactly what changed
- You act like a real user - you click buttons, call APIs, fill forms, navigate through the application
- You simulate complete user journeys that test the changes in the diff
- You catch breakages that only appear when the system is assembled end-to-end
- You test the millions of complex and unique flows that real customers run
- **CRITICAL: You are EXTREMELY STRICT - only flag flow failures as "critical" if they represent bugs that WILL directly affect end users**

**SEVERITY GUIDELINES (EXTREMELY STRICT):**
- **CRITICAL (severity="high")**: ONLY flag if E2E flow failures indicate:
  - User workflows are completely broken (users cannot complete actions)
  - User-facing features fail (buttons don't work, forms don't submit, pages crash)
  - API endpoints return errors that break user functionality
  - User data is lost or corrupted during workflows
  - Critical user journeys are blocked (signup, checkout, login, etc.)
- **MEDIUM (severity="medium")**: Minor UI issues, non-critical flows, or edge cases that don't block users
- **LOW (severity="low")**: Cosmetic issues, performance in non-critical paths, or developer-only flows

YOUR APPROACH:
1. Read the commit diff below to understand EXACTLY what changed
2. Identify critical user workflows that might be affected by these specific changes
3. Generate realistic test flows that simulate actual user behavior testing the changed code
4. Prioritize flows that test changed files/endpoints (from the diff)
5. Create flows that verify end-to-end functionality for the changed code paths

Application Type: {app_type}
Total Files: {codebase_info.get('total_files', 0)}
Routes Found: {len(routes)}
Modified Files in Commit: {', '.join(modified_files[:10])}

Routes in codebase:
{json.dumps([{'path': r.get('path'), 'method': r.get('method')} for r in routes[:20]], indent=2)}

{diff_section}

Commit Summary:
- Files Modified: {len(modified_files)}
- Lines Added: {changes.get('total_additions', 0)}
- Lines Deleted: {changes.get('total_deletions', 0)}

Generate realistic E2E test flows that:
1. Test the EXACT changes shown in the diff above
2. Cover critical user journeys affected by these changes
3. Verify end-to-end workflows for changed endpoints/files
4. Test edge cases and error scenarios for the modified code

Respond in JSON format:
{{
    "flows": [
        {{
            "name": "Flow Name",
            "steps": ["step1", "step2"],
            "type": "flow_type",
            "priority": "high|medium|low",
            "routes_covered": ["route1", "route2"]
        }}
    ],
    "reasoning": ["why flow 1 is needed based on the diff", "why flow 2 is needed"]
}}
"""
            
            response = self.client.generate_content(prompt)
            result_text = response.text
            
            try:
                if "```json" in result_text:
                    json_start = result_text.find("```json") + 7
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                elif "```" in result_text:
                    json_start = result_text.find("```") + 3
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                
                result = json.loads(result_text)
                return result
            except:
                return {
                    "flows": [],
                    "reasoning": [result_text[:500]] if result_text else []
                }
        
        except Exception as e:
            print(f"Error in LLM E2E flow generation: {str(e)}")
            return {"flows": [], "reasoning": []}
    
    async def analyze_endpoint_comparison(
        self,
        endpoint: Dict[str, Any],
        commit_diffs: List[Dict[str, Any]],
        codebase_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze endpoint behavior comparison based on commit changes and codebase context - Shadow Comparison Agent"""
        if not self.enabled:
            return {"has_discrepancy": False, "discrepancy_description": None, "reasoning": []}
        
        try:
            endpoint_file = endpoint.get("file", "")
            relevant_diffs = [d for d in commit_diffs if d.get("file") == endpoint_file]
            
            prompt = f"""
You are the Shadow/Canary Comparison Agent, a specialized AI agent focused on comparing new release behavior with the previous version.

YOUR ROLE:
- You run real traffic through the new release side-by-side with the last good version
- You compare outputs, latency, schema shape, side-effects, and error rates
- You flag anything inconsistent before users ever feel it
- You detect behavioral changes, performance regressions, and breaking changes
- **CRITICAL: You are EXTREMELY STRICT - only flag discrepancies as "critical" if they WILL directly affect end users**

YOUR APPROACH:
1. Analyze the commit diff for this endpoint's file
2. Determine if the endpoint's behavior might have changed
3. Check for potential breaking changes (status codes, response schema, error handling)
4. Identify performance regressions (latency increases, resource usage)
5. Detect side effects that could affect other parts of the system

Analyze this endpoint in the context of a commit change to determine if it might have behavioral changes.

Endpoint:
- Path: {endpoint.get('path')}
- Method: {endpoint.get('method')}
- File: {endpoint_file}

Commit Diff for this endpoint's file:
```diff
{relevant_diffs[0].get('diff', '')[:2000] if relevant_diffs else 'No diff for this file'}
```

Codebase Context:
- Total Files: {codebase_context.get('total_files', 0)}
- Routes: {len(codebase_context.get('routes', []))}

IMPORTANT: You are predicting potential issues based on code analysis, NOT measuring actual runtime behavior.
- Latency predictions are based on code complexity analysis, not actual measurements
- Status code changes are based on diff analysis
- Schema changes are based on response structure analysis

**SEVERITY GUIDELINES (EXTREMELY STRICT):**
- **CRITICAL (critical=true)**: ONLY flag if the change WILL cause:
  - End users to experience errors (API returns 500, endpoints break)
  - Breaking changes that break user-facing features (response schema changes that break clients)
  - Status code changes that cause user workflows to fail (200→500, 200→404)
  - Severe latency increases (>1000ms) that make features unusable for users
  - Data corruption or loss that affects user data
- **MEDIUM (critical=false)**: 
  - Minor latency increases (<500ms) that don't significantly impact user experience
  - Non-breaking schema additions (backward compatible)
  - Internal optimizations that don't affect user-facing behavior
  - Changes that don't directly impact end users

**DO NOT flag as CRITICAL:**
- Minor latency increases (<500ms predicted)
- Backward-compatible schema additions
- Internal code changes that don't affect API contracts
- Non-user-facing endpoints
- Developer-only endpoints

Based on the commit diff and codebase context, analyze:
1. Could this endpoint's behavior change in a way that WILL break end users?
2. Are there breaking changes in the diff that WILL cause user-facing failures?
3. Could there be severe performance regressions (>1000ms) that make features unusable?
4. Could there be side effects that WILL directly impact end users?

ONLY set critical=true if the change WILL cause production failures that affect end users.
DO NOT flag minor latency increases as critical unless they're severe (>1000ms predicted increase that makes features unusable).

Respond in JSON format:
{{
    "has_discrepancy": true|false,
    "discrepancy_description": "description of potential issue",
    "critical": true|false,  // Only true if WILL cause production failure
    "metrics": {{
        "latency_impact": "low|medium|high",  // PREDICTED based on code analysis
        "status_code_changed": true|false,
        "schema_changed": true|false,
        "predicted_latency_increase_ms": 0  // PREDICTED increase in milliseconds (if applicable)
    }},
    "reasoning": ["why this might be an issue", "what changed"]
}}
"""
            
            response = self.client.generate_content(prompt)
            result_text = response.text
            
            try:
                if "```json" in result_text:
                    json_start = result_text.find("```json") + 7
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                elif "```" in result_text:
                    json_start = result_text.find("```") + 3
                    json_end = result_text.find("```", json_start)
                    result_text = result_text[json_start:json_end].strip()
                
                result = json.loads(result_text)
                return result
            except:
                return {
                    "has_discrepancy": False,
                    "discrepancy_description": None,
                    "reasoning": [result_text[:500]] if result_text else []
                }
        
        except Exception as e:
            print(f"Error in LLM endpoint comparison: {str(e)}")
            return {"has_discrepancy": False, "discrepancy_description": None, "reasoning": []}

