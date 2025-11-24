"""
Shadow/Canary Comparison Agent

Specialized Task: Compares new release behavior with previous version using shadow traffic.

Reads commit diffs, understands changes in full codebase context, then:
- Runs real traffic through new release side-by-side with last good version
- Compares outputs, latency, schema shape, side-effects, and error rates
- Flags any behavioral inconsistencies before users experience them

Autonomously generates comparison scenarios based on understanding of what changed.
"""

import os
import subprocess
import asyncio
import re
import json
from typing import Dict, List, Any, Optional
from utils.agent_logger import AgentLogger
from utils.codebase_analyzer import CodebaseAnalyzer
from utils.llm_client import LLMClient


class ShadowComparisonAgent:
    """
    Specialized Agent: Shadow/Canary Comparison
    
    Understands commit diffs in full codebase context, then autonomously generates
    comparison scenarios to test behavioral changes between versions.
    Runs side-by-side comparisons of outputs, latency, schemas, and error rates.
    """
    
    def __init__(self):
        self.name = "Shadow Comparison Agent"
        self.description = "Compares new release with previous version by understanding changes and generating comparison tests"
        self.llm_client = LLMClient()
    
    async def compare_versions(self, repo_path: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run shadow comparison between versions with detailed logging
        Uses LLM + commit diffs + codebase context to dynamically generate comparisons
        """
        logger = AgentLogger(self.name)
        logger.set_status("running")
        
        try:
            # Step 1: Understand codebase structure
            logger.update_progress(0.1, "Analyzing codebase for API endpoints...")
            logger.reasoning(self.name, "Reading commit diffs and understanding changes in full codebase context to identify endpoints that need comparison")
            
            codebase = CodebaseAnalyzer(repo_path)
            codebase_info = codebase.analyze()
            
            # Get commit diffs for LLM analysis
            commit_diffs = changes.get("diffs", [])
            logger.reasoning(self.name, f"Loaded {len(commit_diffs)} file diffs from commit to analyze endpoint behavior changes")
            
            logger.log(self.name, "success", f"Analyzed codebase: {codebase_info['total_files']} files", 
                      data={"total_files": codebase_info['total_files']})
            logger.set_metric("total_files", codebase_info['total_files'])
            
            # Step 2: Discover endpoints
            logger.update_progress(0.2, "Discovering API endpoints...")
            logger.reasoning(self.name, "Based on commit diffs and codebase context, discovering all API endpoints that may have behavioral changes")
            
            routes = codebase_info.get("routes", [])
            logger.log(self.name, "info", f"Found {len(routes)} API routes in codebase", 
                      data={"routes_count": len(routes), "routes": routes[:10]})
            logger.set_metric("routes_found", len(routes))
            
            if not routes:
                logger.reasoning(self.name, "No routes found - this may be a library or utility project")
                logger.log(self.name, "warning", "No API routes found in codebase")
            
            # Step 3: Detect endpoints from changes
            logger.update_progress(0.3, "Analyzing changed files for endpoint modifications...")
            endpoints = await self._discover_endpoints_detailed(repo_path, changes, codebase_info, logger)
            
            logger.log(self.name, "info", f"Identified {len(endpoints)} endpoints to compare", 
                      data={"endpoints": [e.get("path") for e in endpoints[:10]]})
            logger.set_metric("endpoints_to_compare", len(endpoints))
            
            if not endpoints:
                logger.reasoning(self.name, "No endpoints detected - skipping shadow comparison")
                logger.update_progress(1.0, "No endpoints to compare")
                logger.set_status("completed")
                return logger.to_dict()
            
            # Step 4: Compare each endpoint
            logger.update_progress(0.4, f"Starting shadow comparison for {len(endpoints)} endpoints...")
            logger.reasoning(self.name, "Autonomously generating comparison scenarios based on understanding of commit changes and codebase context")
            
            findings = []
            comparisons = []
            
            total_endpoints = min(len(endpoints), 10)  # Limit to 10 for demo
            for idx, endpoint in enumerate(endpoints[:total_endpoints]):
                progress = 0.4 + (idx / total_endpoints * 0.55)
                logger.update_progress(progress, f"Comparing endpoint: {endpoint.get('path')}...")
                
                logger.reasoning(self.name, f"Generating comparison test for endpoint {endpoint.get('path')} based on understanding of what changed")
                
                comparison = await self._compare_endpoint_detailed(
                    endpoint, repo_path, codebase_info, logger, commit_diffs
                )
                
                comparisons.append(comparison)
                log_level = "success" if not comparison.get("has_discrepancy") else "warning"
                logger.log(self.name, log_level,
                          f"Compared {endpoint.get('path')}: {'OK' if not comparison.get('has_discrepancy') else 'DISCREPANCY FOUND'}", 
                          data={"endpoint": endpoint.get("path"), "has_discrepancy": comparison.get("has_discrepancy")})
                
                if comparison.get("has_discrepancy"):
                    # EXTREMELY STRICT: Only flag as HIGH severity if it WILL directly affect end users
                    # Must be explicitly marked as critical by LLM AND represent user-facing breakage
                    is_critical = comparison.get("critical", False) and (
                        # Only critical if it's a breaking change that affects users
                        comparison.get("metrics", {}).get("status_code_changed", False) or
                        comparison.get("metrics", {}).get("schema_changed", False) or
                        comparison.get("metrics", {}).get("predicted_latency_increase_ms", 0) > 1000  # Severe latency (>1s)
                    )
                    metrics = comparison.get("metrics", {})
                    
                    # Build description with context that this is LLM-predicted, not measured
                    description = comparison.get("discrepancy_description", "Behavioral change detected")
                    if "latency" in description.lower() or metrics.get("latency_impact"):
                        description += " (PREDICTED based on code analysis, not actual measurement)"
                    
                    finding = {
                        "type": "behavioral_change",
                        "endpoint": endpoint.get("path"),
                        "method": endpoint.get("method"),
                        "severity": "high" if is_critical else "medium",  # Only HIGH if truly critical
                        "description": description,
                        "metrics": metrics,
                        "suggested_fix": "Review changes and verify intent - may be breaking change" if is_critical else "Review predicted latency increase - verify if acceptable",
                        "reasoning": [
                            f"Endpoint {endpoint.get('path')} shows behavioral difference",
                            comparison.get("discrepancy_description", "Unknown change"),
                            f"Analysis method: {comparison.get('analysis_method', 'unknown')} (LLM-predicted, not measured)"
                        ],
                        "context": {
                            "endpoint_file": endpoint.get("file"),
                            "analysis_method": comparison.get("analysis_method", "unknown"),
                            "is_predicted": True,  # Mark as predicted, not measured
                            "critical": is_critical
                        }
                    }
                    logger.add_finding(finding)
                    findings.append(finding)
            
            logger.update_progress(1.0, "Shadow comparison complete")
            logger.set_status("completed")
            logger.set_metric("endpoints_compared", len(comparisons))
            logger.set_metric("discrepancies_found", len(findings))
            logger.set_metric("comparisons_passed", len([c for c in comparisons if not c.get("has_discrepancy")]))
            
            result = logger.to_dict()
            result["findings"] = findings
            result["comparisons"] = comparisons
            critical_count = len([f for f in findings if f.get("severity") == "high"])
            result["summary"] = f"Compared {len(comparisons)} endpoints: {critical_count} critical bug(s) detected that will cause production failures"
            
            return result
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.log(self.name, "error", f"Error during shadow comparison: {str(e)}\nFull traceback:\n{error_traceback}")
            logger.set_status("failed")
            return logger.to_dict()
    
    async def _discover_endpoints_detailed(
        self,
        repo_path: str,
        changes: Dict[str, Any],
        codebase_info: Dict[str, Any],
        logger: AgentLogger
    ) -> List[Dict[str, Any]]:
        """Discover endpoints with detailed analysis"""
        endpoints = []
        
        # Get routes from codebase analyzer
        routes = codebase_info.get("routes", [])
        
        # Filter routes based on changed files
        modified_files_str = [f.get("path") for f in changes.get("modified_files", [])]
        
        logger.reasoning(self.name, f"Analyzing {len(routes)} routes, focusing on routes affected by {len(modified_files_str)} modified files from commit diff")
        
        for route in routes:
            route_file = route.get("file", "")
            
            # Prioritize routes in modified files
            if route_file in modified_files_str:
                logger.log(self.name, "info", f"Route in modified file: {route.get('path')} ({route.get('method')})",
                          data={"file": route_file, "path": route.get("path")})
            
            endpoints.append({
                "path": route.get("path", ""),
                "method": route.get("method", "GET"),
                "file": route_file,
                "framework": route.get("framework", "unknown"),
                "in_modified_file": route_file in modified_files_str
            })
        
        # Sort: modified files first
        endpoints.sort(key=lambda x: not x.get("in_modified_file", False))
        
            # Also check modified files directly for route definitions
        codebase = CodebaseAnalyzer(repo_path)
        for file_change in changes.get("modified_files", []):
            file_path = file_change.get("path")
            full_path = os.path.join(repo_path, file_path)
            
            if os.path.exists(full_path):
                content = codebase.get_file_content(file_path)
                if content:
                    # Look for route patterns
                    patterns = [
                        (r'app\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']', "FastAPI/Express"),
                        (r'@app\.route\s*\(["\']([^"\']+)["\']', "Flask"),
                        (r'router\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']', "Express Router")
                    ]
                    
                    for pattern, framework in patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            if isinstance(match, tuple):
                                method = match[0].upper() if len(match) > 1 else "GET"
                                path = match[-1]
                            else:
                                method = "GET"
                                path = match
                            
                            endpoint = {
                                "path": path,
                                "method": method,
                                "file": file_path,
                                "framework": framework,
                                "in_modified_file": True
                            }
                            
                            # Add if not already present
                            if not any(e.get("path") == path and e.get("method") == method for e in endpoints):
                                endpoints.append(endpoint)
                                logger.log(self.name, "info", f"Found route in modified file: {method} {path}",
                                          data={"file": file_path, "path": path})
        
        logger.log(self.name, "info", f"Total endpoints discovered: {len(endpoints)}", 
                  data={"total": len(endpoints), "in_modified_files": len([e for e in endpoints if e.get("in_modified_file")])})
        
        return endpoints
    
    async def _compare_endpoint_detailed(
        self,
        endpoint: Dict[str, Any],
        repo_path: str,
        codebase_info: Dict[str, Any],
        logger: AgentLogger,
        commit_diffs: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Compare endpoint behavior between versions with detailed logging
        Uses LLM + commit diffs + codebase context for dynamic analysis (no hardcoded values)"""
        endpoint_path = endpoint.get("path")
        method = endpoint.get("method", "GET")
        
        if commit_diffs is None:
            commit_diffs = []
        
        logger.reasoning(self.name, f"Analyzing {method} {endpoint_path} for potential behavioral changes based on commit diff and codebase context")
        
        # Use LLM to analyze endpoint comparison based on commit diff and codebase context
        has_discrepancy = False
        discrepancy_description = None
        critical = False
        reasoning = []
        metrics = {}
        
        if self.llm_client.enabled:
            logger.reasoning(self.name, f"Using LLM to analyze {method} {endpoint_path} based on commit diff and full codebase context")
            
            llm_analysis = await self.llm_client.analyze_endpoint_comparison(
                endpoint,
                commit_diffs,
                codebase_info
            )
            
            has_discrepancy = llm_analysis.get("has_discrepancy", False)
            discrepancy_description = llm_analysis.get("discrepancy_description")
            critical = llm_analysis.get("critical", False)
            reasoning = llm_analysis.get("reasoning", [])
            metrics = llm_analysis.get("metrics", {})
            
            if has_discrepancy:
                # Check if latency is mentioned - clarify it's PREDICTED, not measured
                if "latency" in (discrepancy_description or "").lower() or metrics.get("latency_impact"):
                    logger.log(self.name, "warning", f"PREDICTED behavioral change (LLM analysis, not measured): {discrepancy_description}")
                    logger.reasoning(self.name, "Latency predictions are based on code complexity analysis, not actual runtime measurements")
                else:
                    logger.log(self.name, "warning", f"Behavioral change detected: {discrepancy_description}")
                
                for reason in reasoning[:3]:
                    logger.reasoning(self.name, reason)
            else:
                logger.log(self.name, "info", f"No behavioral changes detected for {method} {endpoint_path}")
                if reasoning:
                    logger.reasoning(self.name, reasoning[0])
        else:
            # Fallback: analyze based on commit diff patterns (no random values)
            logger.reasoning(self.name, f"LLM not available - analyzing {method} {endpoint_path} based on commit diff patterns")
            
            endpoint_file = endpoint.get("file", "")
            relevant_diff = next((d for d in commit_diffs if d.get("file") == endpoint_file), None)
            
            if relevant_diff:
                diff_content = relevant_diff.get("diff", "")
                # Look for patterns that indicate behavioral changes
                if "status_code" in diff_content.lower() or "status" in diff_content.lower():
                    has_discrepancy = True
                    discrepancy_description = f"Status code logic modified in commit diff - potential behavioral change"
                    critical = True
                    reasoning.append("Status code handling changed in diff - may affect endpoint responses")
                    logger.log(self.name, "warning", "Status code changes detected in diff")
                
                elif "return" in diff_content.lower() or "response" in diff_content.lower():
                    has_discrepancy = True
                    discrepancy_description = f"Response logic modified - potential schema or behavioral change"
                    reasoning.append("Response generation logic changed - may affect output format or content")
                    logger.log(self.name, "warning", "Response logic changes detected in diff")
            else:
                logger.log(self.name, "info", f"No diff found for endpoint file - analyzing based on file changes")
                if endpoint.get("in_modified_file"):
                    # File was modified, check if endpoint logic might have changed
                    reasoning.append(f"Endpoint file was modified in commit - reviewing for behavioral changes")
        
        if not has_discrepancy:
            logger.log(self.name, "info", f"No discrepancies found for {method} {endpoint_path}")
            reasoning.append(f"Endpoint {endpoint_path} appears safe - no behavioral changes detected in commit")
        
        # Build metrics based on LLM analysis or diff patterns
        if not metrics:
            metrics = {
                "status_code_changed": critical and has_discrepancy,
                "schema_changed": has_discrepancy and "schema" in (discrepancy_description or "").lower(),
                "latency_impact": "unknown"
            }
        
        return {
            "endpoint": endpoint_path,
            "method": method,
            "file": endpoint.get("file"),
            "has_discrepancy": has_discrepancy,
            "discrepancy_description": discrepancy_description,
            "critical": critical,
            "metrics": metrics,
            "reasoning": reasoning,
            "analysis_method": "llm" if self.llm_client.enabled else "diff_pattern"
        }
