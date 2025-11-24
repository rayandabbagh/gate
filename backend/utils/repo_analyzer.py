"""
Repository Analyzer
Analyzes git repository changes and extracts metadata
"""

import os
import subprocess
from typing import Dict, List, Any, Optional


class RepoAnalyzer:
    """Analyzes repository changes"""
    
    def analyze_changes(self, repo_path: str, commit_sha: str, branch: str = "main") -> Dict[str, Any]:
        """
        Analyze a SPECIFIC COMMIT by extracting its diff against its parent.
        
        The commit SHA is REQUIRED - this is what we're analyzing to see if it's production-safe.
        The repo is just context to understand the codebase structure.
        
        Returns changes with actual diff content from the commit.
        """
        if not commit_sha:
            raise ValueError("Commit SHA is REQUIRED. We analyze specific commits to check if they're production-safe.")
        
        changes = {
            "repo_path": repo_path,
            "branch": branch,
            "commit_sha": commit_sha,
            "modified_files": [],
            "modified_files_str": [],
            "added_files": [],
            "deleted_files": [],
            "total_additions": 0,
            "total_deletions": 0,
            "diffs": []  # Actual diff content from the commit for agents to read
        }
        
        try:
            # Verify this is a git repo
            if not os.path.exists(os.path.join(repo_path, ".git")):
                raise ValueError(f"Not a git repository: {repo_path}. Commit analysis requires a git repository.")
            
            # Verify commit exists - try full SHA first, then short SHA
            commit_exists = self._run_git_command(repo_path, f"cat-file -t {commit_sha}")
            if not commit_exists or "commit" not in commit_exists.lower():
                # Try to find commit by short SHA if full SHA not found
                print(f"[repo_analyzer] Commit {commit_sha} not found with full SHA, trying to resolve short SHA...")
                try:
                    result = subprocess.run(
                        ["git", "rev-parse", "--verify", f"{commit_sha}^{{commit}}"],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        full_sha = result.stdout.strip()
                        commit_sha = full_sha  # Use full SHA
                        print(f"[repo_analyzer] Found commit by short SHA, using full SHA: {commit_sha}")
                        # Verify again with full SHA
                        commit_exists = self._run_git_command(repo_path, f"cat-file -t {commit_sha}")
                        if not commit_exists or "commit" not in commit_exists.lower():
                            raise ValueError(f"Commit {commit_sha} not found in repository after resolution. Please verify the commit SHA is correct.")
                    else:
                        # Try git log to find similar commit
                        log_result = subprocess.run(
                            ["git", "log", "--oneline", "--all", f"--grep={commit_sha[:7]}", "-n", "1"],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if log_result.returncode == 0 and log_result.stdout:
                            # Extract SHA from log output
                            log_line = log_result.stdout.split('\n')[0]
                            if log_line:
                                potential_sha = log_line.split()[0]
                                print(f"[repo_analyzer] Found similar commit in log: {potential_sha}")
                                raise ValueError(f"Commit {commit_sha} not found. Did you mean {potential_sha}? Please verify the commit SHA is correct.")
                        raise ValueError(f"Commit {commit_sha} not found in repository. Please verify the commit SHA is correct.")
                except ValueError:
                    raise
                except Exception as e:
                    raise ValueError(f"Error finding commit {commit_sha}: {str(e)}. Please verify the commit SHA is correct.")
            
            # Store the actual commit SHA being analyzed
            changes["commit_sha"] = commit_sha
            print(f"[repo_analyzer] Analyzing commit: {commit_sha}")
            
            # Get commit info (message, author, date)
            commit_info = self._run_git_command(repo_path, f"show --no-patch --format=%s%n%an%n%ae%n%ai {commit_sha}")
            if commit_info:
                lines = commit_info.strip().split('\n')
                if len(lines) >= 1:
                    changes["commit_message"] = lines[0]
                if len(lines) >= 2:
                    changes["commit_author"] = lines[1]
                if len(lines) >= 3:
                    changes["commit_email"] = lines[2]
                if len(lines) >= 4:
                    changes["commit_date"] = lines[3]
            
            # Get parent commit SHA
            parent_sha = self._run_git_command(repo_path, f"rev-parse {commit_sha}^")
            if parent_sha:
                parent_sha = parent_sha.strip()
                changes["parent_sha"] = parent_sha
            
            # Get diff of this commit against its parent
            # This shows EXACTLY what changed in this commit
            if parent_sha:
                # Compare commit against its parent
                print(f"[repo_analyzer] Getting diff: {parent_sha}..{commit_sha}")
                diff_stats = self._run_git_command(repo_path, f"diff --stat {parent_sha} {commit_sha}")
                diff_content = self._run_git_command(repo_path, f"diff {parent_sha} {commit_sha}")
                
                # If diff is empty, try unified diff format
                if not diff_content:
                    diff_content = self._run_git_command(repo_path, f"diff -U5 {parent_sha} {commit_sha}")
            else:
                # First commit has no parent, compare against empty tree
                print(f"[repo_analyzer] First commit - using git show")
                diff_stats = self._run_git_command(repo_path, f"show --stat {commit_sha}")
                diff_content = self._run_git_command(repo_path, f"show {commit_sha}")
            
            if diff_stats:
                changes = self._parse_git_diff(diff_stats, changes)
            elif not changes.get("modified_files"):
                # If no stats but we might have diff content, try parsing it directly
                if diff_content:
                    # Try to extract file list from diff
                    lines = diff_content.split('\n')
                    for line in lines:
                        if line.startswith('+++ b/'):
                            file_path = line[6:].strip()
                            if file_path and file_path != '/dev/null':
                                changes["modified_files"].append({
                                    "path": file_path,
                                    "additions": 0,
                                    "deletions": 0
                                })
                                changes["modified_files_str"].append(file_path)
            
            if diff_content:
                changes["diffs"] = self._parse_diff_content(diff_content)
                # Also store full diff for reference
                changes["full_diff"] = diff_content
                print(f"[repo_analyzer] Successfully extracted diff: {len(changes['diffs'])} files, {len(diff_content)} chars")
            else:
                # If no diff content, this might be a merge commit or empty commit
                print(f"[repo_analyzer] Warning: No diff content for commit {commit_sha} - this may be a merge/empty commit")
                changes["diffs"] = []
                changes["full_diff"] = ""
        
        except Exception as e:
            error_msg = f"Error analyzing commit {commit_sha}: {str(e)}"
            print(error_msg)
            raise ValueError(error_msg)
        
        return changes
    
    def _parse_diff_content(self, diff_content: str) -> List[Dict[str, Any]]:
        """Parse actual diff content so agents can read what changed"""
        diffs = []
        current_file = None
        current_diff = []
        
        lines = diff_content.split('\n')
        
        for line in lines:
            # New file section starts
            if line.startswith('diff --git'):
                if current_file and current_diff:
                    diffs.append({
                        "file": current_file,
                        "diff": '\n'.join(current_diff)
                    })
                current_diff = [line]
                current_file = None
            elif line.startswith('--- a/') or line.startswith('+++ b/'):
                if line.startswith('+++ b/'):
                    current_file = line[6:].strip()  # Extract file path
                current_diff.append(line)
            elif current_diff:
                current_diff.append(line)
        
        # Add last file
        if current_file and current_diff:
            diffs.append({
                "file": current_file,
                "diff": '\n'.join(current_diff)
            })
        
        return diffs
    
    def _run_git_command(self, repo_path: str, command: str) -> Optional[str]:
        """Run a git command and return output"""
        try:
            cmd_parts = command.split()
            result = subprocess.run(
                ["git"] + cmd_parts,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30  # Increased timeout for large repos
            )
            if result.returncode == 0:
                output = result.stdout.strip() if result.stdout else None
                if output:
                    print(f"[repo_analyzer] Git command succeeded: {' '.join(cmd_parts[:3])}... (output: {len(output)} chars)")
                return output
            else:
                # Log error for debugging
                error_msg = result.stderr.strip() if result.stderr else f"Git command failed: {command}"
                print(f"[repo_analyzer] Warning: Git command failed: {' '.join(cmd_parts[:3])}... - {error_msg[:100]}")
                return None
        except subprocess.TimeoutExpired:
            print(f"[repo_analyzer] Warning: Git command timed out: {command}")
            return None
        except Exception as e:
            print(f"[repo_analyzer] Warning: Error running git command {command}: {str(e)}")
            return None
    
    def _parse_git_diff(self, diff_output: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Parse git diff output"""
        lines = diff_output.split('\n')
        
        for line in lines:
            if '|' in line and '+++' not in line and '---' not in line:
                # Format: " file.py | 10 ++++++++++---"
                parts = line.split('|')
                if len(parts) == 2:
                    file_path = parts[0].strip()
                    stats = parts[1].strip()
                    
                    # Parse additions/deletions
                    additions = stats.count('+')
                    deletions = stats.count('-')
                    
                    changes["modified_files"].append({
                        "path": file_path,
                        "additions": additions,
                        "deletions": deletions
                    })
                    changes["modified_files_str"].append(file_path)
                    changes["total_additions"] += additions
                    changes["total_deletions"] += deletions
        
        return changes
    
    def _analyze_all_files(self, repo_path: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze all files in repository (fallback when git not available)"""
        code_extensions = [".py", ".js", ".ts", ".java", ".go", ".cpp", ".c", ".tsx", ".jsx"]
        
        for root, dirs, files in os.walk(repo_path):
            # Skip common directories
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__", ".venv", "venv"]]
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                if any(rel_path.endswith(ext) for ext in code_extensions):
                    # Count lines (simplified)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                        
                        changes["modified_files"].append({
                            "path": rel_path,
                            "additions": lines,
                            "deletions": 0
                        })
                        changes["modified_files_str"].append(rel_path)
                        changes["total_additions"] += lines
                    except:
                        pass
        
        return changes

