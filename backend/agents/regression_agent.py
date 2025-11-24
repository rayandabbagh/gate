"""
Regression Agent

Specialized Task: Detects risky changes and potential regressions by analyzing the entire codebase context.

Analyzes each commit against the full codebase to identify:
- Risky changes and logic shifts
- Missing guards and validation
- Dependency drift and breaking changes
- Side effects across the system
- Code patterns that could cause production issues

Uses full codebase context to understand relationships between files and detect issues that diff-only analysis would miss.
"""

import os
import ast
import subprocess
from typing import Dict, List, Any, Optional
from utils.agent_logger import AgentLogger
from utils.codebase_analyzer import CodebaseAnalyzer
from utils.llm_client import LLMClient


class RegressionAgent:
    """
    Specialized Agent: Regression Detection
    
    Analyzes the entire codebase to detect risky changes that could cause production failures.
    Focuses on understanding code changes in context of the whole system, not just the diff.
    """
    
    def __init__(self):
        self.name = "Regression Agent"
        self.description = "Detects risky changes and potential regressions by analyzing entire codebase context"
        self.llm_client = LLMClient()
    
    async def analyze(self, repo_path: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the repository for potential regressions with detailed logging and reasoning
        """
        logger = AgentLogger()
        logger.log(self.name, "info", "Starting regression analysis against entire codebase")
        logger.log(self.name, "reasoning", "Understanding the entire codebase structure to detect regressions in context")
        
        try:
            # Step 1: Understand the codebase structure
            codebase = CodebaseAnalyzer(repo_path)
            codebase_info = codebase.analyze()
            
            logger.log(self.name, "info", f"Analyzed {codebase_info['total_files']} code files across entire codebase")
            logger.log(self.name, "reasoning", f"Identified {codebase_info['total_files']} files for comprehensive analysis")
            logger.set_metric("total_files", codebase_info['total_files'])
            
            # Safely extract files_by_type - handle case where files_by_extension might not be a dict
            files_by_ext = codebase_info.get('files_by_extension', {})
            if isinstance(files_by_ext, dict):
                files_by_type = {k: len(v) if isinstance(v, list) else v for k, v in files_by_ext.items()}
            else:
                files_by_type = {}
            logger.set_metric("files_by_type", files_by_type)
            
            # Step 2: Analyze each changed file in context
            logger.update_progress(0.3, "Analyzing changed files in full codebase context...")
            findings = []
            
            modified_files = changes.get("modified_files", [])
            logger.log(self.name, "info", f"Found {len(modified_files)} modified files", 
                      data={"modified_files": [f.get("path") for f in modified_files]})
            
            for idx, file_change in enumerate(modified_files):
                file_path = file_change.get("path")
                full_path = os.path.join(repo_path, file_path)
                
                progress = 0.3 + (idx / len(modified_files) * 0.4) if modified_files else 0.7
                logger.update_progress(progress, f"Analyzing {file_path}...")
                
                logger.reasoning(self.name, f"Analyzing {file_path}: {file_change.get('additions', 0)} additions, {file_change.get('deletions', 0)} deletions")
                
                # READ ACTUAL COMMIT DIFF for this file
                commit_diffs = changes.get("diffs", [])
                file_diff = next((d for d in commit_diffs if d.get("file") == file_path), None)
                
                if file_diff:
                    diff_content = file_diff.get("diff", "")
                    logger.log(self.name, "info", f"Read actual commit diff for {file_path} ({len(diff_content)} chars)", 
                              data={"diff_length": len(diff_content), "has_diff": True})
                    logger.reasoning(self.name, f"Analyzing actual commit diff for {file_path} in full codebase context")
                else:
                    logger.log(self.name, "warning", f"No diff content found for {file_path}", 
                              data={"has_diff": False})
                    diff_content = ""
                
                if os.path.exists(full_path):
                    # Get related files to understand context
                    related_files = codebase.find_related_files(file_path)
                    logger.log(self.name, "info", f"Found {len(related_files)} related files for {file_path}", 
                              data={"related_files": related_files[:5]})
                    logger.reasoning(self.name, f"Analyzing {file_path} diff in context of {len(related_files)} related files across codebase")
                    
                    # Use LLM for intelligent analysis if available - INCLUDING ACTUAL DIFF
                    content = codebase.get_file_content(file_path)
                    codebase_summary = {
                        "total_files": codebase_info.get("total_files", 0),
                        "files_by_extension": codebase_info.get("files_by_extension", {}),
                        "routes": codebase_info.get("routes", []),
                        "entry_points": codebase_info.get("entry_points", [])
                    }
                    
                    # Include diff in change context for LLM
                    file_change_with_diff = {**file_change, "diff": diff_content}
                    
                    if content and self.llm_client.enabled:
                        logger.reasoning(self.name, f"Using LLM to analyze {file_path} commit diff in full codebase context")
                        llm_analysis = await self.llm_client.analyze_codebase_context(
                            file_path, content, codebase_summary, file_change_with_diff
                        )
                        if llm_analysis.get("risks"):
                            logger.log(self.name, "warning", f"LLM identified {len(llm_analysis.get('risks', []))} potential risks based on commit diff",
                                      data={"risks": llm_analysis.get("risks", [])[:3]})
                    
                    # Deep analysis of the file
                    risk_assessment = await self._assess_file_risk_in_context(
                        file_path, file_change, codebase, logger, llm_analysis if content and self.llm_client.enabled else None
                    )
                    
                    if risk_assessment:
                        # Use LLM's detailed_description if available (much more detailed than static analysis)
                        description = risk_assessment.get("description")
                        if llm_analysis and llm_analysis.get("detailed_description"):
                            description = llm_analysis.get("detailed_description")
                        elif llm_analysis and llm_analysis.get("risks"):
                            # Fallback to combining risks if detailed_description not available
                            description = ". ".join(llm_analysis.get("risks", []))
                        
                        finding = {
                            "type": "regression_risk",
                            "file": file_path,
                            "severity": risk_assessment.get("severity", "medium"),
                            "description": description,  # Now uses LLM's detailed description when available
                            "suggested_fix": risk_assessment.get("suggestion"),  # Only used in Debug Bundle, not logs
                            "reasoning": risk_assessment.get("reasoning", []),
                            "context": risk_assessment.get("context", {})
                        }
                        logger.add_finding(finding)
                        findings.append(finding)
            
            # Step 3: Check for dependency changes
            logger.update_progress(0.7, "Checking dependency changes...")
            logger.reasoning(self.name, "Dependency changes can introduce breaking changes that affect the entire system")
            dep_issues = await self._check_dependencies_in_context(repo_path, changes, codebase, logger)
            findings.extend(dep_issues)
            
            # Step 4: Check for missing error handling
            logger.update_progress(0.85, "Analyzing error handling patterns...")
            logger.reason("Missing error handling in critical paths can cause production failures")
            error_handling_issues = await self._check_error_handling_in_context(
                repo_path, changes, codebase, logger
            )
            findings.extend(error_handling_issues)
            
            # Step 5: Check for side effects
            logger.update_progress(0.95, "Detecting potential side effects...")
            logger.reason("Changes in one file can have side effects on other parts of the system")
            side_effect_issues = await self._check_side_effects(
                repo_path, changes, codebase, logger
            )
            findings.extend(side_effect_issues)
            
            logger.update_progress(1.0, "Analysis complete")
            logger.set_status("completed")
            logger.set_metric("findings_count", len(findings))
            logger.set_metric("critical_findings", len([f for f in findings if f.get("severity") == "high"]))
            
            result = {
                "agent_name": self.name,
                "status": logger.status,
                "progress": logger.progress,
                "findings": findings,
                "logs": logger.logs,  # Use logs attribute directly
                "reasoning": logger.get_agent_reasoning(),
                "metrics": logger.metrics,
                "summary": f"Found {len([f for f in findings if f.get('severity') == 'high'])} critical bug(s) that will cause production failures"
            }
            
            return result
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.log(self.name, "error", f"Error during analysis: {str(e)}\nFull traceback:\n{error_traceback}")
            logger.set_status("failed")
            return logger.to_dict()
    
    async def _assess_file_risk_in_context(
        self, 
        file_path: str, 
        change: Dict[str, Any], 
        codebase: CodebaseAnalyzer,
        logger: AgentLogger,
        llm_analysis: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Assess risk level for a changed file in full codebase context"""
        full_path = os.path.join(codebase.repo_path, file_path)
        reasoning = []
        risk_factors = []
        context = {}
        
        try:
            content = codebase.get_file_content(file_path)
            if not content:
                return None
            
            # AST Analysis for Python files
            if file_path.endswith('.py'):
                try:
                    tree = ast.parse(content)
                    context["ast_analysis"] = {
                        "functions": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
                        "classes": len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]),
                        "imports": len([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))])
                    }
                    
                    # Check for removed functions
                    if change.get("deletions", 0) > change.get("additions", 0):
                        reasoning.append(f"More deletions ({change.get('deletions')}) than additions ({change.get('additions')}) - possible code removal")
                        risk_factors.append("Code removal detected - may break dependent code")
                        
                except SyntaxError:
                    logger.log(self.name, "warning", f"Syntax error in {file_path}")
            
            # Check for removed validation/guards
            validation_keywords = ["validate", "check", "guard", "assert", "require", "verify"]
            has_validation = any(kw in content.lower() for kw in validation_keywords)
            
            if has_validation and change.get("deletions", 0) > change.get("additions", 0):
                reasoning.append("Validation keywords found and more deletions than additions - possible validation removal")
                risk_factors.append("Possible removal of validation/guard logic")
                context["validation_risk"] = True
            
            # Check for large changes
            total_changes = change.get("additions", 0) + change.get("deletions", 0)
            if total_changes > 100:
                reasoning.append(f"Large change detected ({total_changes} lines) - high risk of side effects")
                risk_factors.append(f"Large change ({total_changes} lines) - high risk of side effects")
                context["change_size"] = total_changes
            
            # Check for critical file patterns
            critical_patterns = {
                "auth": ["auth", "login", "session", "token", "jwt"],
                "payment": ["payment", "checkout", "billing", "transaction"],
                "database": ["db", "database", "model", "migration", "schema"],
                "api": ["api", "route", "endpoint", "controller"]
            }
            
            file_lower = file_path.lower()
            for category, patterns in critical_patterns.items():
                if any(pattern in file_lower for pattern in patterns):
                    reasoning.append(f"Changes in critical {category} area: {file_path}")
                    risk_factors.append(f"Changes in critical {category} area")
                    context["critical_area"] = category
                    break
            
            # Check for imports changes (may affect dependencies)
            related_files = codebase.find_related_files(file_path)
            if len(related_files) > 10:
                reasoning.append(f"File has {len(related_files)} related files - changes may have wide impact")
                risk_factors.append("High coupling - changes may affect many files")
                context["coupling"] = len(related_files)
            
            # Check if file is an entry point
            entry_points = codebase.entry_points if hasattr(codebase, 'entry_points') and isinstance(codebase.entry_points, list) else []
            if file_path in entry_points:
                reasoning.append(f"File is an application entry point - critical for system startup")
                risk_factors.append("Entry point file - critical for application")
                context["is_entry_point"] = True
            
            if risk_factors:
                # EXTREMELY STRICT: Only mark as "high" if it WILL directly affect end users
                # Must be in a critical user-facing area AND have multiple risk factors
                is_user_facing_critical = (
                    context.get("critical_area") in ["auth", "payment", "api"] or  # User-facing critical areas
                    context.get("is_entry_point")  # Application entry points affect users
                )
                has_multiple_critical_risks = (
                    len(risk_factors) > 2 and 
                    (context.get("validation_risk") or context.get("critical_area"))
                )
                
                # Only "high" if it WILL break end users
                severity = "high" if (
                    is_user_facing_critical and has_multiple_critical_risks
                ) else "medium"
                
                logger.log(self.name, "warning", f"Risk detected in {file_path}: {', '.join(risk_factors[:3])}")
                
                # Generate a more detailed description based on context (even without LLM)
                # Include specific details about what might break
                description_parts = []
                
                if context.get("critical_area"):
                    area = context.get("critical_area")
                    if area == "auth":
                        description_parts.append(f"Changes in authentication file {file_path} - this affects user login, session management, and access control")
                    elif area == "payment":
                        description_parts.append(f"Changes in payment file {file_path} - this affects checkout, billing, and transaction processing")
                    elif area == "api":
                        description_parts.append(f"Changes in API file {file_path} - this affects endpoint responses and client integrations")
                
                if change.get("deletions", 0) > change.get("additions", 0):
                    deletions = change.get("deletions", 0)
                    additions = change.get("additions", 0)
                    description_parts.append(f"Code removal detected: {deletions} lines deleted vs {additions} added - functions, classes, or validation logic may have been removed")
                    
                    # Try to identify what might break
                    related_files = codebase.find_related_files(file_path)
                    if len(related_files) > 5:
                        sample_files = ", ".join([os.path.basename(f) for f in list(related_files)[:3]])
                        description_parts.append(f"File is imported by {len(related_files)} other files (e.g., {sample_files}) - if functions/methods were removed, these files will break with AttributeError or ImportError at runtime")
                
                if context.get("validation_risk"):
                    description_parts.append(f"Validation or guard logic appears to have been removed - invalid input may now pass through and cause downstream failures")
                
                if context.get("coupling"):
                    coupling_count = context.get("coupling", 0)
                    description_parts.append(f"High coupling detected: {coupling_count} files depend on this file - changes here could break dependent code across the codebase")
                
                # Combine description parts or fall back to risk factors
                if description_parts:
                    description = ". ".join(description_parts)
                else:
                    description = "; ".join(risk_factors)
                
                return {
                    "severity": severity,
                    "description": description,  # Much more detailed now
                    "suggestion": "Review carefully, add integration tests, and verify related files",  # Only used in Debug Bundle
                    "reasoning": reasoning,
                    "context": context
                }
        
        except Exception as e:
            logger.log(self.name, "error", f"Error analyzing {file_path}: {str(e)}")
        
        return None
    
    async def _check_dependencies_in_context(
        self, 
        repo_path: str, 
        changes: Dict[str, Any], 
        codebase: CodebaseAnalyzer,
        logger: AgentLogger
    ) -> List[Dict[str, Any]]:
        """Check for dependency changes that might cause issues"""
        findings = []
        
        dep_files = ["package.json", "requirements.txt", "Pipfile", "go.mod", "Cargo.toml", "pom.xml"]
        
        for dep_file in dep_files:
            dep_path = os.path.join(repo_path, dep_file)
            if os.path.exists(dep_path):
                # Check if file was modified
                modified_files_str = changes.get("modified_files_str", [])
                if dep_file in modified_files_str:
                    logger.reason(f"Dependency file {dep_file} was modified - need to check for breaking changes")
                    
                    try:
                        with open(dep_path, 'r') as f:
                            content = f.read()
                        
                        # Try to parse and detect version changes
                        if dep_file == "package.json":
                            import json
                            data = json.loads(content)
                            deps = data.get("dependencies", {}) | data.get("devDependencies", {})
                            logger.log(self.name, "info", f"Found {len(deps)} dependencies in {dep_file}", 
                                      data={"dependency_count": len(deps)})
                        
                        # EXTREMELY STRICT: Only "high" if dependency changes WILL break end users
                        # Most dependency updates are backward compatible - only flag if truly breaking
                        finding = {
                            "type": "dependency_change",
                            "file": dep_file,
                            "severity": "medium",  # Default to medium - only high if we confirm it breaks users
                            "description": f"Dependencies changed in {dep_file} - review for potential breaking changes",
                            "suggested_fix": "Review changelog, test thoroughly, and check for breaking changes",
                            "reasoning": [f"Dependency file {dep_file} was modified - may introduce breaking changes"],
                            "context": {"dependency_file": dep_file, "user_impact": "unknown"}
                        }
                        logger.add_finding(finding)
                        findings.append(finding)
                    except Exception as e:
                        logger.log(self.name, "error", f"Error reading {dep_file}: {str(e)}")
        
        return findings
    
    async def _check_error_handling_in_context(
        self, 
        repo_path: str, 
        changes: Dict[str, Any], 
        codebase: CodebaseAnalyzer,
        logger: AgentLogger
    ) -> List[Dict[str, Any]]:
        """Check for missing error handling in changed code"""
        findings = []
        
        error_handling_patterns = {
            ".py": ["try:", "except", "raise", "assert"],
            ".js": ["try", "catch", "throw", "Promise.catch"],
            ".ts": ["try", "catch", "throw", "Promise.catch"],
            ".go": ["error", "panic", "recover"],
            ".java": ["try", "catch", "throw", "throws"]
        }
        
        for file_change in changes.get("modified_files", []):
            file_path = file_change.get("path")
            full_path = os.path.join(repo_path, file_path)
            
            ext = os.path.splitext(file_path)[1]
            if ext in error_handling_patterns:
                content = codebase.get_file_content(file_path)
                if content:
                    patterns = error_handling_patterns[ext]
                    has_error_handling = any(pattern in content for pattern in patterns)
                    
                    # Check if this is a critical file (API, auth, payment)
                    is_critical = any(p in file_path.lower() for p in ["api", "auth", "payment", "route"])
                    
                    if is_critical and not has_error_handling:
                        logger.reason(f"Critical file {file_path} may be missing error handling")
                        
                        # EXTREMELY STRICT: Only "high" if missing error handling WILL break end users
                        # Check if it's a user-facing API/auth/payment endpoint
                        is_user_facing_critical = any(user_facing in file_path.lower() for user_facing in [
                            "api", "route", "endpoint", "auth", "login", "payment", "checkout"
                        ])
                        
                        finding = {
                            "type": "missing_error_handling",
                            "file": file_path,
                            "severity": "high" if is_user_facing_critical else "medium",
                            "description": f"Missing error handling in {'user-facing' if is_user_facing_critical else 'critical'} file {file_path}",
                            "suggested_fix": "Add try-catch blocks or error handling patterns to prevent user-facing errors",
                            "reasoning": [f"{'User-facing' if is_user_facing_critical else 'Critical'} file {file_path} doesn't appear to have error handling"],
                            "context": {"file_type": ext, "is_critical": is_critical, "is_user_facing": is_user_facing_critical}
                        }
                        logger.add_finding(finding)
                        findings.append(finding)
        
        return findings
    
    async def _check_side_effects(
        self, 
        repo_path: str, 
        changes: Dict[str, Any], 
        codebase: CodebaseAnalyzer,
        logger: AgentLogger
    ) -> List[Dict[str, Any]]:
        """Check for potential side effects of changes"""
        findings = []
        
        # Check if changed files are imported by many other files
        for file_change in changes.get("modified_files", []):
            file_path = file_change.get("path")
            related_files = codebase.find_related_files(file_path)
            
            if len(related_files) > 15:  # High coupling threshold
                logger.reason(f"File {file_path} is highly coupled - changes may affect {len(related_files)} files")
                
                finding = {
                    "type": "high_coupling_risk",
                    "file": file_path,
                    "severity": "medium",
                    "description": f"High coupling detected: {file_path} is related to {len(related_files)} other files",
                    "suggested_fix": "Review all dependent files and run full test suite",
                    "reasoning": [f"File {file_path} has high coupling - changes may cause side effects"],
                    "context": {"related_files_count": len(related_files)}
                }
                logger.add_finding(finding)
                findings.append(finding)
        
        return findings
