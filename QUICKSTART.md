# Quick Start Guide

## Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

## Setup (2 minutes)

1. **Create and activate virtual environment:**
   ```bash
   cd gate-project
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the backend server:**
   ```bash
   cd backend
   python main.py
   ```
   
   Or use the startup script:
   ```bash
   ./start.sh
   ```
   
   You should see:
   ```
   INFO:     Started server process
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

3. **Open the frontend:**
   - Open `frontend/index.html` in your web browser
   - Or serve it with: `python -m http.server 3000` (from the frontend directory)

## Using Gate

1. **Enter Repository Path:**
   - In the UI, enter the full path to your repository
   - Example: `/Users/rayandabbagh/Desktop/sentinel`
   
2. **Optional Settings:**
   - Commit SHA: Leave empty to analyze latest changes
   - Branch: Default is "main"

3. **Start Analysis:**
   - Click "Start Analysis"
   - Watch the 4 agents work:
     - Regression Agent
     - Test Generation Agent
     - E2E Simulation Agent
     - Shadow Comparison Agent

4. **View Results:**
   - See the summary of findings
   - Review the DebugBundle (if issues found)
   - Use the DebugBundle to fix issues with coding agents

## Example Repository

Try analyzing any of these:
- `/Users/rayandabbagh/Desktop/sentinel`
- `/Users/rayandabbagh/Desktop/amal-repos/amal`
- Or any other code repository on your system

## Troubleshooting

**"Cannot connect to backend API"**
- Make sure the backend is running on port 8000
- Check: `http://localhost:8000` should return JSON

**"Repository path not found"**
- Use absolute paths (full path starting with `/`)
- Make sure the path exists and is accessible

**Import errors in Python**
- Make sure you've installed dependencies: `pip install -r requirements.txt`
- Run from the `backend` directory: `cd backend && python main.py`

## What Happens During Analysis

1. **Repository Analysis**: Git changes are analyzed
2. **Regression Detection**: Full codebase context checked for risks
3. **Test Generation**: Tests generated for changed paths
4. **E2E Simulation**: User flows simulated end-to-end
5. **Shadow Comparison**: New version compared with previous
6. **DebugBundle Creation**: All findings compiled into fix-ready bundle

## Next Steps

- Integrate with your CI/CD pipeline
- Connect to real AI models (OpenAI, Anthropic)
- Add more sophisticated code analysis
- Set up webhooks for automatic analysis on merge

## Support

For questions or issues, check the main README.md file.

