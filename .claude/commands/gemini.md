---
description: Ask Gemini (through Google's Antigravity CLI) for a second opinion or a large-context read. Read-only.
argument-hint: <question or task for Gemini>
allowed-tools: Bash(agy:*), Bash(command -v agy), Read, Grep, Glob
---

Ask Gemini for help with: $ARGUMENTS

Gemini is an assistant on this team, reached through Google's Antigravity CLI (`agy`). You, the
Claude Code session, stay the lead and make the final decision.

Steps:

1. Check that the tool exists: `command -v agy`. If it is missing, stop and tell the user to
   install it with `curl -fsSL https://antigravity.google/cli/install.sh | bash`, then run `agy`
   once in a terminal to sign in with their Google account. Do not install it yourself.
2. Write one focused prompt for Gemini. Give it the exact files or folders to read, the question,
   and what form the answer should take (for example "list problems with file and line, most
   serious first, under 300 words"). Do not paste secrets or anything from outside this project.
3. Run it read-only from the project root, in plan mode so it cannot edit files:
   `agy -p "<your prompt>" --mode plan`
4. If it reports that the quota is reached or that sign-in is required, say so plainly and carry
   on without Gemini. Do not retry in a loop.
5. Treat the reply as a colleague's opinion, not as fact. Check each claim against the code or
   the cited source before acting on it. Report to the user: what Gemini said, which points you
   verified, which you rejected and why.

Use Gemini for what it is good at: reading a lot at once (the whole project, a long document)
and cross-checking a plan or a piece of research. Do not use it for small tasks. The quota is
shared with the user's other Antigravity use, so one well-built prompt beats several small ones.
