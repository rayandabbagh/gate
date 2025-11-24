# How Gate Analyzes Your Codebase

## Overview

Gate analyzes the **entire codebase** against each commit using a coordinated team of specialized AI agents. Each agent has full context of the entire repository structure, not just the diff.

## Full Codebase Analysis

### Codebase Analyzer (`utils/codebase_analyzer.py`)

The `CodebaseAnalyzer` scans the entire repository:

1. **File Discovery**: Walks the entire repository, ignoring `.git`, `node_modules`, `venv`, etc.
2. **File Classification**: Categorizes files by extension (`.py`, `.js`, `.ts`, etc.)
3. **Dependency Analysis**: Extracts imports/requires to build a dependency graph
4. **Route Detection**: Finds API routes (FastAPI, Flask, Express, etc.)
5. **Entry Point Discovery**: Identifies main entry files (`main.py`, `app.py`, `index.js`, etc.)
6. **Test File Detection**: Finds all test files in the repository

**Result**: A complete map of the codebase structure with:
- Total file count
- Files by type
- Dependency relationships
- API routes
- Entry points
- Test coverage

### LLM-Enhanced Analysis

When a `GEMINI_API_KEY` is configured, agents use Gemini AI to:

1. **Context-Aware Risk Assessment**: Analyze changes in the context of the entire codebase
2. **Intelligent Test Generation**: Generate tests based on codebase patterns
3. **Smart Finding Explanation**: Provide actionable explanations for detected issues

The LLM receives:
- The changed file content
- Codebase summary (total files, types, routes)
- The specific changes (additions/deletions)

And returns:
- Potential risks
- Reasoning for flagging issues
- Suggested checks

## How Each Agent Acts

### 1. Regression Agent

**Scope**: Analyzes the entire codebase to detect risky changes

**Process**:
1. Gets full codebase structure from `CodebaseAnalyzer`
2. For each changed file:
   - Finds related files through dependency graph
   - Analyzes file in context of entire codebase
   - Uses LLM (if available) to assess risks with full context
   - Checks for:
     - Removed validation/guards
     - Large changes (>100 lines)
     - Critical file patterns (auth, payment, database)
     - Dependency drift
3. Checks dependency changes across entire codebase
4. Analyzes error handling patterns
5. Detects potential side effects

**Output**: Findings with reasoning about why each change is risky in context of the full codebase

### 2. Test Generation Agent

**Scope**: Analyzes changed files and generates tests

**Process**:
1. Gets codebase structure to understand test patterns
2. For each changed file:
   - Checks if tests exist
   - Uses AST analysis to identify functions/classes
   - Uses LLM (if available) to generate intelligent test suggestions
   - Generates test templates
3. Identifies missing test coverage

**Output**: Generated tests and missing coverage findings

### 3. E2E Simulation Agent

**Scope**: Simulates real user flows across entire application

**Process**:
1. Detects application type (web app, API, full-stack) from codebase structure
2. Discovers all routes from codebase analysis
3. Generates realistic user flows based on:
   - Discovered routes
   - Application type
   - Changed files
4. Attempts to start application (if possible)
5. Simulates flows:
   - API calls
   - Button clicks
   - Form submissions
   - Navigation

**Output**: Flow execution results and failures

### 4. Shadow Comparison Agent

**Scope**: Compares behavior between versions

**Process**:
1. Discovers all API endpoints from codebase
2. For each endpoint:
   - Makes requests to current version
   - Makes requests to previous version (if available)
   - Compares:
     - Response status codes
     - Latency
     - Response size
     - Response structure
3. Flags any behavioral differences

**Output**: Comparison results showing behavioral changes

## Commit-Specific Analysis

Each analysis is tied to a specific commit SHA. The agents:

1. **Checkout the commit** (via GitHub handler)
2. **Analyze changes** for that specific commit
3. **Run all agents** against that commit with full codebase context
4. **Generate DebugBundle** specific to that commit

The DebugBundle includes:
- Commit SHA
- What each agent analyzed
- Findings specific to that commit
- Codebase context (total files analyzed, scope)
- Ready-to-paste format for coding agents

## Output: DebugBundle

The DebugBundle is optimized for **immediate paste into coding agents** (Cursor, Claude, Copilot):

- **Concise**: Only essential information
- **Actionable**: Clear instructions on how to fix
- **Context-Aware**: Shows what was analyzed (X files across entire codebase)
- **Commit-Specific**: Tied to specific commit SHA
- **Agent Transparency**: Shows exactly what each agent did

Format: Markdown-like text that can be directly pasted into any coding agent.

