# How Gate Agents Work

## Core Concept

Each agent follows the same intelligent workflow:

1. **Reads Commit Diffs**: Analyzes what changed in the commit
2. **Understands Context**: Uses LLM to understand the role of that commit in the context of the entire codebase
3. **Generates Autonomous Work**: Based on that understanding, each agent autonomously generates its own tests, simulations, or checks

## Agent Workflow

### 1. Read Commit Diffs

Each agent starts by reading the commit diffs through `RepoAnalyzer`:
- Modified files and their changes
- Additions and deletions
- File paths and line changes
- Context about what changed

### 2. Understand Full Codebase Context

Each agent gets full codebase context from `CodebaseAnalyzer`:
- Total files in repository
- File types and structure
- Dependency relationships
- Routes and API endpoints
- Entry points
- Existing test coverage

### 3. Use LLM to Understand Role of Commit

When Gemini API key is configured, each agent uses LLM to:
- Understand what the commit does in context of entire codebase
- Identify affected areas and potential impact
- Reason about risks and changes needed

**Example Prompt Structure**:
```
You are analyzing a commit in the context of an entire codebase.

Codebase Summary:
- Total files: X
- File types: Python (Y), JavaScript (Z)
- Routes found: [list of routes]
- Entry points: [main files]

Commit Changes:
- File: path/to/file.py
- Additions: N lines
- Deletions: M lines
- Diff: [actual diff content]

Question: What is the role of this commit? What areas might be affected? 
What should we test/simulate/check?
```

### 4. Autonomously Generate Work

Based on understanding, each agent **autonomously generates** its own work:

#### Regression Agent
- **Reads diffs**: Sees what files changed
- **Understands context**: LLM understands risky patterns in full codebase context
- **Generates checks**: Creates regression tests for affected areas, checks for side effects, validates dependencies

#### Test Generation Agent
- **Reads diffs**: Sees what code paths changed
- **Understands context**: LLM understands what needs testing based on codebase patterns
- **Generates tests**: Creates unit tests, integration tests, property tests for exactly the changed code paths

#### E2E Simulation Agent
- **Reads diffs**: Sees what user-facing flows might be affected
- **Understands context**: LLM understands application structure and user workflows
- **Generates flows**: Creates realistic user flows (signup, checkout, etc.) that test the changed areas

#### Shadow Comparison Agent
- **Reads diffs**: Sees what API endpoints or behaviors changed
- **Understands context**: LLM understands what should be compared between versions
- **Generates comparisons**: Creates comparison tests for endpoints, checks for behavioral changes

## Example: Test Generation Agent Workflow

```
1. Read Commit Diff:
   - File: src/api/user.py
   - Changes: Added new validation function, modified login endpoint
   - 15 additions, 3 deletions

2. Get Full Codebase Context:
   - 234 total files analyzed
   - Python: 120 files, JavaScript: 45 files
   - Routes: /api/user/login, /api/user/profile
   - Test files: tests/test_user.py exists

3. LLM Understanding:
   - "This commit adds validation to user login. 
      The new validation function checks email format and password strength.
      The login endpoint is modified to use this validation.
      Related files: user.py, auth.py, models.py
      Areas to test: validation logic, login flow, error handling"

4. Autonomously Generate Tests:
   - Generate unit test for new validation function
   - Generate integration test for login endpoint with new validation
   - Generate edge case tests for invalid inputs
   - Check if existing tests need updates
```

## Key Points

1. **Not Static Scripts**: Agents don't run pre-written tests. They intelligently generate tests/simulations based on understanding.

2. **Full Context**: Each agent has access to the entire codebase, not just the diff, to make intelligent decisions.

3. **Autonomous**: Each agent decides what to test/simulate/check based on its understanding, not from a checklist.

4. **Commit-Specific**: Each analysis is tied to a specific commit SHA, so agents understand exactly what changed.

5. **Coordinated**: Agents work together but each has its specialized domain:
   - Regression Agent: Risky changes and side effects
   - Test Generation Agent: Test coverage for changed paths
   - E2E Simulation Agent: Real user workflows
   - Shadow Comparison Agent: Behavioral changes between versions

## Output

When issues are found, all agents collaborate to produce a **DebugBundle**:
- What each agent found
- What each agent tested/simulated/checked
- Reproduction steps
- Context for fixing the issues

The DebugBundle is optimized for coding agents (Cursor, Claude, Copilot) to instantly fix the issues.

