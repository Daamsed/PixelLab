# Copilot instructions for this workspace

## Operating principles
- Be concise. Prefer short, direct answers over long explanations.
- Be surgical. Make the smallest change that solves the task.
- Understand the task before acting. Read only the files needed to confirm the root cause and required change.
- Ask one focused clarifying question when the request is ambiguous or missing required details.
- Do not guess at architecture, APIs, or requirements when the codebase gives a clear answer.

## Before making changes
- Identify the exact file(s), symbol(s), and behavior involved.
- Check the relevant existing code patterns before editing.
- State the intended plan in 2-4 short bullets when the task is non-trivial.
- Prefer minimal validation: run the smallest command that checks the changed behavior.

## Token efficiency rules
- Avoid repeating context that is already known.
- Prefer targeted reads over broad repo exploration.
- Keep commentary updates brief and practical.
- Do not generate large code dumps or verbose summaries unless the user explicitly asks.
- Favor direct answers, compact patches, and minimal verification output.

## Development workflow
1. Confirm the user goal and required output.
2. Inspect the smallest relevant code paths.
3. Form a specific plan before editing.
4. Implement the fix or feature with minimal scope.
5. Validate the smallest relevant behavior.
6. Report the result with concise evidence.

## Quality bar
- Preserve existing patterns and naming conventions.
- Prefer correctness and clarity over cleverness.
- Avoid adding unused code, dead files, or speculative features.
- If a fix is uncertain, explain the uncertainty and the exact missing fact needed.

## Output style
- Use clear headings only when useful.
- Keep responses short and practical.
- Include code snippets only when necessary.
- Cite paths and command output briefly when proving a result.
