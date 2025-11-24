"""
Codebase Analyzer
Analyzes codebase structure, dependencies, and relationships using AST and static analysis
"""

import os
import ast
import re
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path


class CodebaseAnalyzer:
    """Analyzes codebase structure and relationships"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.files_by_extension: Dict[str, List[str]] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.routes: List[Dict[str, str]] = []
        self.entry_points: List[str] = []
        self.test_files: List[str] = []
        
    def analyze(self) -> Dict[str, Any]:
        """Perform comprehensive codebase analysis"""
        self._scan_files()
        self._analyze_dependencies()
        self._extract_routes()
        self._find_entry_points()
        self._find_tests()
        
        return {
            "files_by_extension": self.files_by_extension,
            "dependencies": self.dependencies,
            "routes": self.routes,
            "entry_points": self.entry_points,
            "test_files": self.test_files,
            "total_files": sum(len(files) if isinstance(files, list) else 0 for files in self.files_by_extension.values()) if isinstance(self.files_by_extension, dict) else 0,
            "has_tests": len(self.test_files) > 0
        }
    
    def _scan_files(self):
        """Scan repository for all code files"""
        ignore_patterns = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}
        
        for root, dirs, files in os.walk(self.repo_path):
            # Filter ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)
                ext = os.path.splitext(file)[1]
                
                if ext in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.cpp', '.c']:
                    if ext not in self.files_by_extension:
                        self.files_by_extension[ext] = []
                    self.files_by_extension[ext].append(rel_path)
    
    def _analyze_dependencies(self):
        """Analyze dependencies between files"""
        # Ensure files_by_extension is a dict
        if not isinstance(self.files_by_extension, dict):
            return
        
        # Python imports
        py_files = self.files_by_extension.get('.py', [])
        if not isinstance(py_files, list):
            py_files = []
        
        for py_file in py_files:
            full_path = os.path.join(self.repo_path, py_file)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=py_file)
                    imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            imports.extend(alias.name for alias in node.names)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module)
                    self.dependencies[py_file] = imports
            except:
                pass
        
        # JavaScript/TypeScript imports
        js_files = self.files_by_extension.get('.js', [])
        ts_files = self.files_by_extension.get('.ts', [])
        if not isinstance(js_files, list):
            js_files = []
        if not isinstance(ts_files, list):
            ts_files = []
        
        for js_file in js_files + ts_files:
            full_path = os.path.join(self.repo_path, js_file)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Match import/require statements
                    imports = re.findall(r'(?:import|from|require\([\'\"])([^\'\"]+)', content)
                    # Convert to list safely - use list comprehension to avoid shadowing issues
                    if isinstance(imports, (list, tuple, set)):
                        self.dependencies[js_file] = [imp for imp in set(imports)]
                    else:
                        self.dependencies[js_file] = []
            except:
                pass
    
    def _extract_routes(self):
        """Extract API routes from codebase"""
        # Ensure files_by_extension is a dict
        if not isinstance(self.files_by_extension, dict):
            return
        
        # Python FastAPI/Flask
        py_files = self.files_by_extension.get('.py', [])
        if not isinstance(py_files, list):
            py_files = []
        
        for py_file in py_files:
            full_path = os.path.join(self.repo_path, py_file)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # FastAPI routes
                    fastapi_routes = re.findall(r'@app\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']', content, re.IGNORECASE)
                    for method, path in fastapi_routes:
                        self.routes.append({
                            "method": method.upper(),
                            "path": path,
                            "file": py_file,
                            "framework": "FastAPI"
                        })
                    
                    # Flask routes
                    flask_routes = re.findall(r'@app\.route\s*\(["\']([^"\']+)["\']', content)
                    for path in flask_routes:
                        self.routes.append({
                            "method": "GET",
                            "path": path,
                            "file": py_file,
                            "framework": "Flask"
                        })
            except:
                pass
        
        # Express.js routes
        js_files = self.files_by_extension.get('.js', [])
        ts_files = self.files_by_extension.get('.ts', [])
        if not isinstance(js_files, list):
            js_files = []
        if not isinstance(ts_files, list):
            ts_files = []
        
        for js_file in js_files + ts_files:
            full_path = os.path.join(self.repo_path, js_file)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Express routes
                    express_routes = re.findall(r'app\.(get|post|put|delete|patch)\s*\(["\']([^"\']+)["\']', content, re.IGNORECASE)
                    for method, path in express_routes:
                        self.routes.append({
                            "method": method.upper(),
                            "path": path,
                            "file": js_file,
                            "framework": "Express"
                        })
            except:
                pass
    
    def _find_entry_points(self):
        """Find application entry points"""
        # Common entry point files
        entry_patterns = ['main.py', 'app.py', 'index.js', 'index.ts', 'server.js', 'server.ts', 'main.go']
        
        if not isinstance(self.files_by_extension, dict):
            return
        for ext, files in self.files_by_extension.items():
            if not isinstance(files, list):
                continue
            for file in files:
                filename = os.path.basename(file)
                if filename in entry_patterns:
                    self.entry_points.append(file)
                    
                # Check for __main__ pattern in Python
                if ext == '.py' and filename != '__init__.py':
                    full_path = os.path.join(self.repo_path, file)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            if 'if __name__ == "__main__"' in f.read():
                                self.entry_points.append(file)
                    except:
                        pass
    
    def _find_tests(self):
        """Find test files"""
        test_patterns = ['test_', '_test', '.test.', '.spec.']
        
        if not isinstance(self.files_by_extension, dict):
            return
        for ext, files in self.files_by_extension.items():
            if not isinstance(files, list):
                continue
            for file in files:
                filename = os.path.basename(file)
                if any(pattern in filename for pattern in test_patterns):
                    self.test_files.append(file)
                
                # Check test directories
                path_parts = file.split(os.sep)
                if 'test' in path_parts or 'tests' in path_parts or '__tests__' in path_parts:
                    self.test_files.append(file)
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a file"""
        full_path = os.path.join(self.repo_path, file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except:
                pass
        return None
    
    def find_related_files(self, file_path: str, max_depth: int = 2) -> List[str]:
        """Find files related to a given file through imports/dependencies"""
        related = set([file_path])
        
        # Get direct dependencies
        if file_path in self.dependencies:
            deps = self.dependencies[file_path]
            if isinstance(deps, list):
                for dep in deps[:10]:  # Limit to first 10
                    # Try to find file matching dependency
                    if isinstance(self.files_by_extension, dict):
                        try:
                            for ext, files in self.files_by_extension.items():
                                if isinstance(files, list):
                                    for f in files:
                                        if isinstance(f, str) and (dep.replace('.', os.sep) in f or dep.split('.')[0] in f):
                                            related.add(f)
                        except (AttributeError, TypeError) as e:
                            # If .items() fails, files_by_extension is not a dict
                            pass
        
        # Convert set to list - use [] + list() to ensure we get a list
        return [f for f in related] if related else []

