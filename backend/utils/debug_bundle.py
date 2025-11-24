"""
DebugBundle Generator
Creates a concise, actionable DebugBundle optimized for coding agents
Contains only what's necessary to understand and fix issues
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class DebugBundleGenerator:
    """Generates concise DebugBundles optimized for coding agents"""
    
    def generate_bundle(
        self,
        analysis_id: str,
        regression_results: Dict[str, Any],
        test_results: Dict[str, Any],
        e2e_results: Dict[str, Any],
        shadow_results: Dict[str, Any],
        repo_path: str,
        changes: Dict[str, Any],
        codebase_context: Optional[Dict[str, Any]] = None,
        commit_sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate DebugBundle focused on analyzing THIS COMMIT for potential production bugs.
        Bundle explains what push was made and what bugs it might introduce in production.
        Optimized format for pasting into Cursor/LLM to improve the code.
        """
        all_findings = (
            regression_results.get("findings", []) +
            test_results.get("findings", []) +
            e2e_results.get("findings", []) +
            shadow_results.get("findings", [])
        )
        
        # Categorize findings by severity - ONLY flag truly CRITICAL bugs
        # Agents only set severity="high" when something is truly critical
        # So we ONLY flag bugs with severity="high" (nothing else)
        critical_findings = [f for f in all_findings if f.get("severity") == "high"]
        medium_findings = [f for f in all_findings if f.get("severity") == "medium"]
        low_findings = [f for f in all_findings if f.get("severity") == "low" or not f.get("severity")]
        
        # ALL bugs (even micro) trigger bundle generation
        has_any_bugs = len(all_findings) > 0
        
        # Generate concise root cause summary
        root_cause_summary = self._generate_concise_summary(all_findings)
        
        # Generate actionable reproduction steps
        reproduction_steps = self._generate_reproduction_steps(
            regression_results,
            test_results,
            e2e_results,
            shadow_results
        )
        
        # Extract only relevant code context
        code_context = self._extract_relevant_code(changes, all_findings)
        
        # ONLY flag URGENT bugs (critical/high severity) - ignore low/medium unless they're truly urgent
        # Focus on bugs that WILL cause production issues
        urgent_bugs = critical_findings  # Only critical/high severity
        has_urgent_bugs = len(urgent_bugs) > 0
        
        # Extract commit information
        commit_summary = self._extract_commit_summary(changes, commit_sha)
        
        # Include actual diff content in bundle
        actual_diff = changes.get("diffs", [])
        full_diff = changes.get("full_diff", "")
        
        bundle = {
            "analysis_id": analysis_id,
            "generated_at": datetime.now().isoformat(),
            "commit_sha": commit_sha,
            "release_safe": not has_urgent_bugs,
            "bugs_found": has_urgent_bugs,
            "bugs_caught_before_prod": has_urgent_bugs,
            
            # What Commit Was Pushed (with actual diff)
            "commit_summary": commit_summary,
            "what_was_pushed": self._describe_what_was_pushed(changes, commit_sha),
            "diff_content": actual_diff,  # Include actual diffs
            "full_diff": full_diff,  # Full unified diff
            
            # What Bugs This Commit Might Introduce in Production (ONLY URGENT/CRITICAL)
            # Ultra-concise format optimized for coding agents: what changed + what's broken + how to fix
            "production_bugs": self._explain_production_bugs_concise(critical_findings, changes) if has_urgent_bugs else "No urgent bugs detected. This commit appears safe for production.",
            "bugs_explanation": self._explain_production_bugs_concise(critical_findings, changes) if has_urgent_bugs else "No urgent bugs detected. Release is safe for production.",
            
            # Summary
            "summary": root_cause_summary,
            
            # Codebase Context (this commit was analyzed in context of full codebase)
            "codebase_scope": {
                "total_files_in_codebase": codebase_context.get("total_files", 0) if codebase_context else 0,
                "files_by_type": {k: len(v) if isinstance(v, list) else v for k, v in codebase_context.get("files_by_extension", {}).items()} if codebase_context else {},
                "note": "This commit was analyzed in the context of the entire codebase to understand dependencies and side effects"
            },
            
            # All Issues Found (ONLY URGENT/CRITICAL bugs flagged)
            "issues": {
                "critical": critical_findings,  # Only show critical
                "medium": [],  # Don't flag medium unless urgent
                "low": [],  # Don't flag low
                "total": len(urgent_bugs),  # Only count urgent
                "count_by_severity": {
                    "critical": len(critical_findings),
                    "medium": 0,
                    "low": 0
                }
            },
            
            # What Changed in This Commit (with actual diff)
            "commit_changes": {
                "changed_files": [f.get("path") for f in changes.get("modified_files", [])],
                "files_modified": len(changes.get("modified_files", [])),
                "lines_added": changes.get("total_additions", 0),
                "lines_deleted": changes.get("total_deletions", 0),
                "diffs": actual_diff,  # Actual diff content
                "full_diff": full_diff  # Full unified diff for agents
            },
            
            # Code Context (what changed that might cause bugs)
            "affected_code": code_context,
            
            # How to Reproduce Bugs This Commit Might Cause
            "how_to_reproduce": reproduction_steps,
            
            # Agent Analysis Summary (what each agent did)
            "agent_analysis": {
                "regression": {
                    "scope": f"Analyzed {codebase_context.get('total_files', 0) if codebase_context else 0} files across entire codebase",
                    "focus": "Risky changes, missing guards, dependency drift, side effects",
                    "findings_count": len(regression_results.get("findings", [])),
                    "key_findings": regression_results.get("findings", [])[:5]
                },
                "test_generation": {
                    "scope": f"Analyzed {len(changes.get('modified_files', []))} changed files",
                    "focus": "Missing tests, inadequate coverage, test generation",
                    "findings_count": len(test_results.get("findings", [])),
                    "key_findings": test_results.get("findings", [])[:5]
                },
                "e2e_simulation": {
                    "scope": f"Discovered {len(codebase_context.get('routes', [])) if codebase_context else 0} routes, executed {len(e2e_results.get('simulated_flows', []))} flows",
                    "focus": "Real user workflows, end-to-end breakages",
                    "findings_count": len(e2e_results.get("findings", [])),
                    "key_findings": e2e_results.get("findings", [])[:5]
                },
                "shadow_comparison": {
                    "scope": f"Compared {len(shadow_results.get('comparisons', []))} endpoints between versions",
                    "focus": "Behavioral changes, latency, response schema differences",
                    "findings_count": len(shadow_results.get("findings", [])),
                    "key_findings": shadow_results.get("findings", [])[:5]
                }
            },
            
            # How to Fix (actionable - only for urgent bugs)
            "how_to_fix": self._generate_fix_instructions(urgent_bugs, codebase_context) if has_urgent_bugs else [],
            
            # Ready for Cursor/LLM (formatted for immediate paste)
            "ready_for_coding_agent": has_urgent_bugs,
            "cursor_ready": True,  # Always ready, even if no bugs (for reference)
            
            # Pre-Production Warning (ONLY if urgent bugs)
            "pre_production_warning": self._generate_pre_production_warning(urgent_bugs, critical_findings, []) if has_urgent_bugs else None
        }
        
        return bundle
    
    def _extract_commit_summary(self, changes: Dict[str, Any], commit_sha: Optional[str]) -> Dict[str, Any]:
        """Extract summary of what this commit changed"""
        return {
            "sha": commit_sha or "unknown",
            "files_changed": len(changes.get("modified_files", [])),
            "additions": changes.get("total_additions", 0),
            "deletions": changes.get("total_deletions", 0),
            "changed_files_list": [f.get("path") for f in changes.get("modified_files", [])]
        }
    
    def _describe_what_was_pushed(self, changes: Dict[str, Any], commit_sha: Optional[str]) -> str:
        """Describe what push/commit was made in clear terms"""
        # Get commit SHA from changes if not provided
        commit_sha = commit_sha or changes.get("commit_sha") or "unknown"
        
        modified_files = changes.get("modified_files", [])
        additions = changes.get("total_additions", 0)
        deletions = changes.get("total_deletions", 0)
        
        commit_ref = commit_sha[:8] if commit_sha and commit_sha != "unknown" else "unknown"
        
        # Check if we actually have diff content
        has_diffs = bool(changes.get("diffs") or changes.get("full_diff"))
        
        if not has_diffs and len(modified_files) == 0:
            return f"Commit {commit_ref}: No changes detected or diff extraction failed. This may be an empty commit or merge commit."
        
        description = f"Commit {commit_ref} was pushed with the following changes:\n\n"
        description += f"Files Modified: {len(modified_files)}\n"
        description += f"Lines Added: {additions}\n"
        description += f"Lines Deleted: {deletions}\n\n"
        
        if modified_files:
            description += "Files Changed:\n"
            for file_change in modified_files[:10]:  # Show first 10
                file_path = file_change.get("path", "unknown")
                file_additions = file_change.get("additions", 0)
                file_deletions = file_change.get("deletions", 0)
                description += f"  - {file_path} (+{file_additions}/-{file_deletions})\n"
            
            if len(modified_files) > 10:
                description += f"  ... and {len(modified_files) - 10} more files\n"
        else:
            description += "Note: File list unavailable - diff extraction may have failed.\n"
        
        if not has_diffs:
            description += "\nWARNING: Actual diff content not available. This may be a merge commit or the commit SHA was not found."
        
        return description.strip()
    
    def _explain_production_bugs_concise(
        self, 
        critical: List[Dict[str, Any]], 
        changes: Dict[str, Any]
    ) -> str:
        """Ultra-concise bug explanation optimized for coding agents: what changed + what's broken + how to fix"""
        if not critical:
            return "No urgent bugs detected. This commit appears safe for production."
        
        explanation = ""
        
        # For each critical bug, provide context that a coding agent needs to fix it
        for idx, bug in enumerate(critical, 1):
            if idx > 1:
                explanation += "\n"
            
            explanation += f"Bug #{idx}: {bug.get('type', 'Unknown').replace('_', ' ').title()}\n"
            
            # Location
            file_or_endpoint = bug.get('file') or bug.get('endpoint') or bug.get('flow', 'unknown')
            explanation += f"Location: {file_or_endpoint}\n"
            
            # What's broken (detailed description)
            description = bug.get('description', 'Unknown bug')
            explanation += f"Problem: {description}\n"
            
            # Why this breaks (context for the agent)
            if bug.get('reasoning'):
                reasons = bug['reasoning'] if isinstance(bug['reasoning'], list) else [str(bug['reasoning'])]
                if reasons:
                    explanation += f"Why this breaks: {reasons[0]}\n"
            
            # How to fix (actionable instruction)
            if bug.get('suggested_fix'):
                explanation += f"Fix: {bug['suggested_fix']}\n"
            else:
                # Generate fix based on bug type
                fix = self._generate_fix_from_bug(bug)
                explanation += f"Fix: {fix}\n"
        
        return explanation.strip()
    
    def _generate_fix_from_bug(self, bug: Dict[str, Any]) -> str:
        """Generate concise fix instruction from bug"""
        bug_type = bug.get("type", "")
        description = bug.get("description", "")
        file_path = bug.get("file") or bug.get("endpoint", "")
        
        if "latency" in description.lower():
            return f"Review changes in {file_path} - optimize code paths that may cause latency increase"
        elif "status_code" in description.lower() or "status" in description.lower():
            return f"Review status code changes in {file_path} - ensure they match intended behavior"
        elif "schema" in description.lower() or "response" in description.lower():
            return f"Review response format changes in {file_path} - ensure backward compatibility"
        elif "regression" in description.lower() or "breaking" in description.lower():
            return f"Review changes in {file_path} - may break existing functionality"
        else:
            return f"Review changes in {file_path} and verify intent - ensure it doesn't break existing functionality"
    
    def _explain_production_bugs(
        self, 
        all_findings: List[Dict[str, Any]], 
        critical: List[Dict[str, Any]], 
        medium: List[Dict[str, Any]], 
        low: List[Dict[str, Any]],
        changes: Dict[str, Any]
    ) -> str:
        """Explain what urgent bugs this commit might introduce in production - optimized for Cursor
        
        ONLY flags urgent/critical bugs that WILL cause production failures.
        Includes context and fix instructions for immediate use in coding agents.
        """
        if not all_findings:
            return "No urgent bugs detected. This commit appears safe for production."
        
        commit_ref = changes.get("commit_sha", "this commit")
        if isinstance(commit_ref, str) and len(commit_ref) > 8:
            commit_ref = commit_ref[:8]
        
        # Include commit diff context in explanation
        has_diffs = bool(changes.get("diffs") or changes.get("full_diff"))
        diff_context = f"\nNOTE: All analysis is based on LLM analysis of the commit diff in full codebase context. "
        diff_context += "Latency/performance predictions are based on code analysis, not actual runtime measurements.\n\n" if any("latency" in str(f.get("description", "")).lower() for f in critical) else ""
        
        explanation = f"This commit ({commit_ref}) might introduce the following URGENT bugs in production:\n\n"
        explanation += "These bugs WILL cause production failures if deployed. Fix before merging to production.\n"
        explanation += diff_context
        
        # CRITICAL bugs only - these are urgent
        if critical:
            explanation += f"URGENT BUGS ({len(critical)}): MUST FIX BEFORE PRODUCTION\n"
            explanation += "=" * 70 + "\n\n"
            for idx, bug in enumerate(critical, 1):  # Show ALL critical bugs
                explanation += f"Bug {idx}: {bug.get('description', 'Unknown bug')}\n"
                explanation += f"  File/Endpoint: {bug.get('file') or bug.get('endpoint', 'unknown')}\n"
                explanation += f"  Type: {bug.get('type', 'unknown').replace('_', ' ').title()}\n"
                
                # Add context about prediction vs measurement
                if bug.get("context", {}).get("is_predicted"):
                    explanation += f"  Note: This analysis is LLM-predicted based on code changes, not actual runtime measurement.\n"
                
                # Why this is a bug (context)
                if bug.get('reasoning'):
                    reasons = bug['reasoning'] if isinstance(bug['reasoning'], list) else [str(bug['reasoning'])]
                    explanation += f"  Why this WILL cause a production bug:\n"
                    for reason in reasons[:3]:  # Top 3 reasons
                        explanation += f"    - {reason}\n"
                
                # Show actual diff context if available
                if has_diffs:
                    explanation += f"  Context: See commit diff below to understand what changed.\n"
                
                # How to fix (actionable)
                if bug.get('suggested_fix'):
                    explanation += f"  How to fix: {bug['suggested_fix']}\n"
                else:
                    file_or_endpoint = bug.get('file') or bug.get('endpoint', 'unknown')
                    explanation += f"  How to fix: Review the change in {file_or_endpoint} and verify intent. The commit diff below shows what changed - ensure it doesn't break existing functionality.\n"
                
                explanation += "\n"
        else:
            explanation += "No urgent bugs detected. This commit appears safe for production.\n"
        
        explanation += "=" * 70 + "\n"
        explanation += "RECOMMENDATION: Fix the bugs above before deploying to production.\n"
        explanation += "Each bug includes context (why it's a bug) and fix instructions (how to fix).\n"
        explanation += "Copy this bundle into Cursor for immediate fixes.\n\n"
        explanation += "COMMIT DIFF: The diff below shows exactly what changed - use this to fix the bugs."
        
        return explanation.strip()
    
    def _generate_concise_summary(self, findings: List[Dict[str, Any]]) -> str:
        """Generate concise summary of production bugs this commit might introduce"""
        if not findings:
            return "This commit was analyzed for production bugs. No bugs detected - appears safe for production."
        
        critical = [f for f in findings if f.get("severity") == "high"]
        medium = [f for f in findings if f.get("severity") == "medium"]
        low = [f for f in findings if f.get("severity") == "low"]
        
        summary = f"This commit might introduce {len(findings)} bug(s) in production: {len(critical)} critical, {len(medium)} medium, {len(low)} low.\n\n"
        
        # Show most critical bugs
        if critical:
            summary += "Critical bugs that WILL cause production failures:\n"
            for finding in critical[:3]:  # Top 3 critical
                summary += f"- {finding.get('description')} (File: {finding.get('file', 'unknown')})\n"
            summary += "\n"
        
        # Show medium bugs
        if medium:
            summary += "Medium risk bugs that MIGHT cause production issues:\n"
            for finding in medium[:2]:  # Top 2 medium
                summary += f"- {finding.get('description')} (File: {finding.get('file', 'unknown')})\n"
            summary += "\n"
        
        return summary.strip()
    
    def _explain_bugs_caught(self, all_findings: List[Dict[str, Any]], critical: List[Dict[str, Any]], 
                             medium: List[Dict[str, Any]], low: List[Dict[str, Any]]) -> str:
        """Clearly explain what bugs were caught before production"""
        if not all_findings:
            return "No bugs detected. Release is safe for production."
        
        explanation = f"Bugs caught before production deployment:\n\n"
        explanation += f"Total bugs found: {len(all_findings)}\n"
        explanation += f"- Critical: {len(critical)}\n"
        explanation += f"- Medium: {len(medium)}\n"
        explanation += f"- Low: {len(low)}\n\n"
        
        explanation += "What each bug is:\n\n"
        
        # Explain each bug clearly
        for idx, finding in enumerate(all_findings[:15], 1):  # Show up to 15 bugs with explanations
            severity = finding.get("severity", "medium")
            ftype = finding.get("type", "issue")
            description = finding.get("description", "Unknown issue")
            file_path = finding.get("file", "unknown")
            reasoning = finding.get("reasoning", [])
            
            explanation += f"Bug {idx} ({severity.upper()}):\n"
            explanation += f"  Type: {ftype.replace('_', ' ').title()}\n"
            explanation += f"  Description: {description}\n"
            explanation += f"  File: {file_path}\n"
            
            if reasoning:
                explanation += f"  Why this is a bug: {reasoning[0] if isinstance(reasoning, list) and reasoning else str(reasoning)}\n"
            
            suggested_fix = finding.get("suggested_fix")
            if suggested_fix:
                explanation += f"  How to fix: {suggested_fix}\n"
            
            explanation += "\n"
        
        if len(all_findings) > 15:
            explanation += f"... and {len(all_findings) - 15} more bugs (see full bundle for details)\n"
        
        return explanation.strip()
    
    def _generate_pre_production_warning(self, all_findings: List[Dict[str, Any]], 
                                         critical: List[Dict[str, Any]], 
                                         medium: List[Dict[str, Any]]) -> str:
        """Generate clear pre-production warning about bugs caught"""
        if not all_findings:
            return None
        
        warning = "PRE-PRODUCTION WARNING: Bugs detected before deployment\n\n"
        
        if critical:
            warning += f"CRITICAL: {len(critical)} critical bug(s) must be fixed before production.\n"
            warning += "These could cause production failures or data loss.\n\n"
        
        if medium:
            warning += f"MEDIUM: {len(medium)} medium severity bug(s) should be fixed.\n"
            warning += "These could cause user-facing issues or degraded performance.\n\n"
        
        warning += f"Total bugs caught: {len(all_findings)}\n"
        warning += "Review the Debug Bundle below for detailed explanations and fixes.\n\n"
        warning += "Do not deploy to production until bugs are resolved."
        
        return warning
    
    def _generate_reproduction_steps(
        self,
        regression_results: Dict[str, Any],
        test_results: Dict[str, Any],
        e2e_results: Dict[str, Any],
        shadow_results: Dict[str, Any]
    ) -> List[str]:
        """Generate concise reproduction steps"""
        steps = []
        
        # E2E failures
        e2e_findings = e2e_results.get("findings", [])
        if e2e_findings:
            steps.append(f"E2E Flow Failures ({len(e2e_findings)}):")
            for finding in e2e_findings[:3]:
                steps.append(f"  - {finding.get('flow')}: {finding.get('error', 'Failed')}")
        
        # Test failures
        test_findings = test_results.get("findings", [])
        if test_findings:
            steps.append(f"Missing/Inadequate Tests ({len(test_findings)}):")
            for finding in test_findings[:3]:
                steps.append(f"  - {finding.get('file')}: {finding.get('description', '')}")
        
        # Regression risks
        reg_findings = regression_results.get("findings", [])
        if reg_findings:
            steps.append(f"Regression Risks ({len(reg_findings)}):")
            for finding in reg_findings[:3]:
                steps.append(f"  - {finding.get('file')}: {finding.get('description', '')}")
        
        # Shadow comparison
        shadow_findings = shadow_results.get("findings", [])
        if shadow_findings:
            steps.append(f"Behavioral Changes ({len(shadow_findings)}):")
            for finding in shadow_findings[:3]:
                steps.append(f"  - {finding.get('endpoint')}: {finding.get('description', '')}")
        
        return steps if steps else ["No specific reproduction steps - review changes manually"]
    
    def _extract_relevant_code(self, changes: Dict[str, Any], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract only code context relevant to findings"""
        affected_files = {}
        
        # Get files with issues
        for finding in findings:
            file_path = finding.get("file")
            if file_path:
                if file_path not in affected_files:
                    affected_files[file_path] = {
                        "file": file_path,
                        "issues": [],
                        "severity": finding.get("severity", "medium")
                    }
                affected_files[file_path]["issues"].append({
                    "type": finding.get("type"),
                    "description": finding.get("description"),
                    "suggested_fix": finding.get("suggested_fix")
                })
        
        # Add changed files
        for file_change in changes.get("modified_files", []):
            file_path = file_change.get("path")
            if file_path not in affected_files:
                affected_files[file_path] = {
                    "file": file_path,
                    "issues": [],
                    "severity": "info"
                }
            affected_files[file_path]["lines_changed"] = file_change.get("additions", 0) + file_change.get("deletions", 0)
        
        return list(affected_files.values())
    
    def _generate_fix_instructions(
        self,
        findings: List[Dict[str, Any]],
        codebase_context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable fix instructions"""
        instructions = []
        
        # Group by file
        by_file = {}
        for finding in findings:
            file_path = finding.get("file")
            if file_path:
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(finding)
        
        for file_path, file_findings in by_file.items():
            critical_count = len([f for f in file_findings if f.get("severity") == "high"])
            
            instruction = f"Fix {file_path}:"
            if critical_count > 0:
                instruction += f" {critical_count} critical issue(s)"
            
            # Get suggested fixes
            fixes = [f.get("suggested_fix") for f in file_findings if f.get("suggested_fix")]
            if fixes:
                instruction += f" - {fixes[0]}"
            
            instructions.append(instruction)
        
        if not instructions:
            instructions.append("Review all changed files manually before deployment")
        
        return instructions[:10]  # Limit to 10 most important
