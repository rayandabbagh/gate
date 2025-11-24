"""
GitHub Repository Handler
Clones and manages GitHub repositories for analysis
"""

import os
import subprocess
import tempfile
import shutil
import re
from typing import Dict, Optional, Tuple
from pathlib import Path


class GitHubHandler:
    """Handles GitHub repository cloning and management"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.cloned_repos_dir = os.path.join(self.temp_dir, 'gate_cloned_repos')
        os.makedirs(self.cloned_repos_dir, exist_ok=True)
    
    def parse_github_url(self, github_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse GitHub URL to extract owner, repo, and optionally commit SHA
        
        Returns: (owner, repo, commit_sha_from_url)
        """
        # Clean URL
        url = github_url.strip()
        
        # Remove .git suffix
        if url.endswith('.git'):
            url = url[:-4]
        
        # Extract owner and repo, and optionally commit
        commit_sha = None
        
        # Check for commit in URL first (more specific pattern)
        commit_match = re.search(r'github\.com/([^/]+)/([^/]+)/commit/([a-f0-9]+)', url)
        if commit_match:
            owner = commit_match.group(1)
            repo = commit_match.group(2)
            commit_sha = commit_match.group(3)
            return owner, repo, commit_sha
        
        # Check for tree/branch with commit
        tree_match = re.search(r'github\.com/([^/]+)/([^/]+)/tree/([a-f0-9]+)', url)
        if tree_match:
            owner = tree_match.group(1)
            repo = tree_match.group(2)
            commit_sha = tree_match.group(3)
            return owner, repo, commit_sha
        
        # Basic owner/repo pattern
        match = re.search(r'github\.com/([^/]+)/([^/]+)', url)
        if match:
            owner = match.group(1)
            repo = match.group(2).split('/')[0]  # Remove any trailing paths
            return owner, repo, None
        
        return None, None, None
    
    def clone_repository(self, github_url: str, commit_sha: Optional[str] = None) -> Optional[str]:
        """
        Clone a GitHub repository to a temporary directory
        
        Returns: Path to cloned repository, or None if failed
        """
        owner, repo, url_commit = self.parse_github_url(github_url)
        
        if not owner or not repo:
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        
        # Use commit from URL if provided, otherwise use parameter
        commit_sha = commit_sha or url_commit
        
        # Create unique directory name
        repo_name = f"{owner}_{repo}"
        if commit_sha:
            repo_name += f"_{commit_sha[:8]}"
        
        clone_path = os.path.join(self.cloned_repos_dir, repo_name)
        
        # Check if already cloned
        if os.path.exists(clone_path):
            print(f"Repository already cloned at {clone_path}")
            if commit_sha:
                # Checkout specific commit
                try:
                    subprocess.run(
                        ['git', 'checkout', commit_sha],
                        cwd=clone_path,
                        check=True,
                        capture_output=True,
                        timeout=30
                    )
                except:
                    # If checkout fails, reclone
                    shutil.rmtree(clone_path, ignore_errors=True)
        
        # Clone if doesn't exist
        if not os.path.exists(clone_path):
            clone_url = f"https://github.com/{owner}/{repo}.git"
            print(f"Cloning {clone_url} to {clone_path}")
            
            try:
                # Clone repository
                subprocess.run(
                    ['git', 'clone', clone_url, clone_path],
                    check=True,
                    capture_output=True,
                    timeout=120
                )
                
                # Checkout specific commit if provided
                if commit_sha:
                    print(f"[github_handler] Checking out commit {commit_sha}")
                    checkout_result = subprocess.run(
                        ['git', 'checkout', commit_sha],
                        cwd=clone_path,
                        check=False,  # Don't fail if checkout fails
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if checkout_result.returncode != 0:
                        # Try fetching first
                        print(f"[github_handler] Checkout failed, fetching...")
                        subprocess.run(['git', 'fetch', '--all'], cwd=clone_path, capture_output=True, timeout=30)
                        # Try again
                        checkout_result = subprocess.run(
                            ['git', 'checkout', commit_sha],
                            cwd=clone_path,
                            check=False,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if checkout_result.returncode != 0:
                            raise Exception(f"Failed to checkout commit {commit_sha}: {checkout_result.stderr}")
                    print(f"[github_handler] Successfully checked out commit {commit_sha}")
                
                return clone_path
                
            except subprocess.TimeoutExpired:
                raise Exception(f"Timeout while cloning repository: {github_url}")
            except subprocess.CalledProcessError as e:
                raise Exception(f"Failed to clone repository: {github_url}. Error: {e.stderr.decode()}")
        
        return clone_path
    
    def get_repo_info(self, github_url: str) -> Dict[str, str]:
        """Get repository information from GitHub URL"""
        owner, repo, commit_sha = self.parse_github_url(github_url)
        
        if not owner or not repo:
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        
        return {
            'owner': owner,
            'repo': repo,
            'full_name': f"{owner}/{repo}",
            'url': f"https://github.com/{owner}/{repo}",
            'commit_sha_from_url': commit_sha
        }
    
    def cleanup(self, repo_path: str) -> None:
        """Clean up cloned repository (optional - for cleanup scripts)"""
        if os.path.exists(repo_path) and repo_path.startswith(self.cloned_repos_dir):
            try:
                shutil.rmtree(repo_path)
                print(f"Cleaned up repository: {repo_path}")
            except Exception as e:
                print(f"Failed to cleanup {repo_path}: {e}")

