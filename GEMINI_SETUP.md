# Gemini API Setup

## How to Add Your API Key

1. Create a `.env` file in the `backend/` directory:

```bash
cd gate-project/backend
cp .env.example .env
```

2. Edit the `.env` file and add your Gemini API key:

```
GEMINI_API_KEY=your_actual_api_key_here
```

3. Get your API key from: https://makersuite.google.com/app/apikey

## What Happens With/Without API Key

### With API Key (LLM-Enhanced Analysis):
- **Regression Agent**: Uses Gemini to analyze code changes in full codebase context, identifying risks that static analysis might miss
- **Test Generation Agent**: Uses Gemini to generate intelligent test suggestions based on code patterns
- **Findings**: More contextual and actionable explanations

### Without API Key (Static Analysis):
- **Regression Agent**: Uses pattern matching, AST analysis, and heuristics to detect risks
- **Test Generation Agent**: Uses AST parsing to generate test templates
- **Findings**: Still comprehensive but based on static analysis only

Both modes analyze the **entire codebase** - the difference is in the intelligence of the analysis.

## How Analysis Works

### Full Codebase Analysis (Both Modes)

1. **Codebase Analyzer** scans entire repository:
   - Discovers all code files
   - Builds dependency graph
   - Finds API routes
   - Identifies entry points
   - Detects test files

2. **Each Agent** receives full codebase context:
   - Total files analyzed
   - File types and counts
   - Routes discovered
   - Entry points
   - Test coverage

3. **Analysis is commit-specific**:
   - Each analysis is tied to a specific commit SHA
   - Agents analyze that commit's changes against the entire codebase
   - DebugBundle includes the commit SHA and scope

### Without LLM (Current Default)

Agents use:
- **Pattern Matching**: Detects risky patterns (large changes, missing validation, etc.)
- **AST Analysis**: Parses code structure (functions, classes, imports)
- **Dependency Analysis**: Traces relationships between files
- **Heuristics**: Rule-based detection of potential issues

### With LLM (When API Key Added)

Agents also use:
- **Context-Aware Reasoning**: Understands code intent in full codebase context
- **Intelligent Risk Assessment**: Identifies subtle issues pattern matching might miss
- **Actionable Explanations**: Provides clearer reasoning for findings
- **Smart Test Generation**: Creates tests that match codebase patterns

## Next Steps

1. Add your API key to `backend/.env`
2. Restart the backend server
3. Agents will automatically use LLM when available

