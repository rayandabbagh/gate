# Gate - AI Agent Team for Post-Merge Bug Prevention

A team of specialized AI agents that orchestrate, test, compare, simulate, and validate every release after merge - catching production bugs before they ever reach your users.

## The Problem

Pre-merge AI review only understands the code change - not the system. And bugs don't appear in diffs. They appear in reality. The moment code is merged, it enters a world PR reviewers cannot see: real data, real configs, real dependencies, real distributed systems, real human flows.

**This is where 90% of critical failures are born - not in the code review stage.**

## The Solution

A coordinated team of specialized AI agents, each handling one part of the reliability puzzle:

### 1. Regression Agent
**Specialized Task**: Detects risky changes and potential regressions by analyzing entire codebase context.

- Reads commit diffs to understand what changed
- Uses full codebase context to identify risks
- Autonomously generates regression tests for affected areas
- Checks for side effects, missing guards, dependency drift

### 2. Test Generation Agent
**Specialized Task**: Generates comprehensive tests for changed code paths.

- Reads commit diffs to identify changed code paths
- Understands what needs testing based on codebase patterns
- Autonomously generates unit, integration, and property tests
- Fills gaps in test coverage for modified code

### 3. E2E Simulation Agent
**Specialized Task**: Simulates real user workflows to catch end-to-end breakages.

- Reads commit diffs to see what user-facing flows might be affected
- Understands application structure and user workflows
- Autonomously generates realistic user flows (signup, checkout, etc.)
- Tests the entire system as users would use it

### 4. Shadow Comparison Agent
**Specialized Task**: Compares new release behavior with previous version using shadow traffic.

- Reads commit diffs to see what API endpoints or behaviors changed
- Understands what should be compared between versions
- Autonomously generates comparison tests for endpoints
- Flags behavioral changes before users experience them

## How It Works

1. **Reads Commit Diffs**: Each agent analyzes what changed in the commit
2. **Understands Context**: Uses LLM to understand the role of that commit in the context of the entire codebase
3. **Generates Autonomous Work**: Based on that understanding, each agent autonomously generates its own tests, simulations, or checks

See [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) for detailed explanation.

## Quick Start

1. **Install Dependencies**:
```bash
cd gate-project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Add Gemini API Key** (optional but recommended):
```bash
cd backend
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

3. **Start Server**:
```bash
./start.sh
```

4. **Open UI**:
Open `frontend/index.html` in your browser

5. **Analyze a Commit**:
- Enter GitHub repository URL
- Enter commit SHA
- Click "Analyze Repository"

## Output: DebugBundle

When issues are found, all agents collaborate to produce a **DebugBundle** - optimized for coding agents (Cursor, Claude, Copilot) to instantly fix the issues.

The DebugBundle includes:
- What each agent found
- What each agent tested/simulated/checked
- Reproduction steps
- Context for fixing the issues

## Documentation

- [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) - How agents work
- [GEMINI_SETUP.md](GEMINI_SETUP.md) - Gemini API setup
- [backend/README_ANALYSIS.md](backend/README_ANALYSIS.md) - Codebase analysis details

## Key Features

- **Full Codebase Context**: Each agent analyzes the entire repository, not just the diff
- **Commit-Specific**: Each analysis is tied to a specific commit SHA
- **Autonomous**: Agents intelligently generate tests/simulations based on understanding
- **LLM-Enhanced**: Uses Gemini AI for intelligent code analysis (when API key configured)
- **DebugBundle**: Optimized for coding agents to instantly fix issues

## Vision

- AI writes the code
- AI tests the code
- AI verifies the system (handled by Gate)
- AI guards the release (handled by Gate)
- AI gathers context (handled by Gate)
- AI hands the fix to coding agents on a silver platter (handled by Gate)

Engineers stay in control - but they no longer firefight, no longer guess, and no longer get blindsided by production failures.

This is the new foundation of software reliability.
