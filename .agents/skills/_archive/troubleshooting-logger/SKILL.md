---
name: troubleshooting-logger
description: Auto-log solved problems and solutions to TROUBLESHOOTING.md when user confirms a fix works. Trigger on phrases like fixed/solved/working/OK/问题解决了/搞定了/可以了/好了. Extracts problem, cause, solution, and affected files.
---

# Troubleshooting Logger

## 触发条件 / Trigger Conditions

当用户确认问题已解决时激活：
- fixed, solved, working, OK, normal now
- 问题解决了, 搞定了, 可以了, 好了, 没问题了
- that worked, finally done
- XX is fixed, XX works now
- 任何确认之前问题已解决的表达

## Workflow

1. Identify the problem: Review recent conversation to extract:
   - What the user reported (symptom)
   - Root cause (technical reason)
   - Solution (what was done to fix it)
   - Files involved

2. Read existing document: Read TROUBLESHOOTING.md in project root. Check if same problem already logged.

3. Append entry: If new problem, append to TROUBLESHOOTING.md in this format:

## N. Problem Title

**Date**: YYYY-MM-DD
**Symptom**: What the user saw
**Root Cause**: Technical explanation
**Solution**: Specific fix steps or code
**Files**: Which files were modified
**Scope**: How many files/models affected

4. Confirm: Tell user the issue has been logged to the troubleshooting document.

## Document Location

- Log file: TROUBLESHOOTING.md (project root)
- Create with title and format header if it does not exist

## Guidelines

- Log every resolved issue, even small ones
- Be specific with technical details
- Include reusable code snippets or commands
- If multiple solutions exist, log the best one
