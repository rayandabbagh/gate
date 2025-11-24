# Diff Verification - How Agents Analyze Commits

## ✅ YES - Commits Diffs ARE Being Read and Analyzed

### 1. **Commit Diff Extraction** (`backend/utils/repo_analyzer.py`)
- Uses `git diff {parent_sha} {commit_sha}` to get the EXACT diff of the commit
- Parses the diff into structured format: `changes["diffs"]` = list of file diffs
- Each diff entry contains:
  - `file`: The file path
  - `diff`: The actual diff content (lines with `+` and `-` markers)

### 2. **Agents Read Actual Diffs**

#### **Regression Agent** (`backend/agents/regression_agent.py`)
- Reads `changes.get("diffs", [])` 
- Finds the diff for each changed file: `file_diff = next((d for d in commit_diffs if d.get("file") == file_path), None)`
- Passes actual diff content to LLM: `file_change_with_diff = {**file_change, "diff": diff_content}`
- LLM prompt includes: `Actual Commit Diff (this is what changed): {diff_content}`

#### **Test Generation Agent** (`backend/agents/test_generation_agent.py`)
- Reads `changes.get("modified_files", [])` based on commit diff
- Generates tests for exactly the code paths that changed

#### **E2E Simulation Agent** (`backend/agents/e2e_simulation_agent.py`)
- Reads `changes.get("diffs", [])` and `changes.get("modified_files", [])`
- Generates flows based on what actually changed in the commit

#### **Shadow Comparison Agent** (`backend/agents/shadow_comparison_agent.py`)
- Reads `changes.get("diffs", [])` - the actual commit diffs
- Passes `commit_diffs` to LLM for analysis
- LLM analyzes endpoint changes based on actual diff content

### 3. **Diff Included in Debug Bundle**
- `commit_changes["diffs"]` = Full structured diff array (one per file)
- `commit_changes["full_diff"]` = Complete unified diff string
- Debug Bundle includes: `## Actual Commit Diff (What Agents Analyzed)`

### 4. **How to Verify**
When you run an analysis, the Debug Bundle will show:
```markdown
## Actual Commit Diff (What Agents Analyzed)
This is the EXACT diff from this commit that all agents read and analyzed...

```diff
# File: path/to/file.py
diff --git a/path/to/file.py b/path/to/file.py
index 1234567..abcdefg 100644
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,7 +10,8 @@
 def function():
-    old_code()
+    new_code()
     ...
```

You can copy this exact diff to verify agents analyzed it.

## Summary

**YES** - The commit diff is:
1. ✅ Extracted using `git diff {parent} {commit}`
2. ✅ Parsed into structured format
3. ✅ Passed to all agents
4. ✅ Read by agents for analysis
5. ✅ Included in LLM prompts
6. ✅ Displayed in Debug Bundle for verification

The diff is the **PRIMARY INPUT** for all agents - they all read `changes["diffs"]` to understand what changed.

