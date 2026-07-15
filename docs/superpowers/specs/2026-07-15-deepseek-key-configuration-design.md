# DeepSeek API Key Configuration Design

## Goal

Make the README match the application's secure configuration path and remove
the real DeepSeek API key from the Git-tracked YAML configuration without
losing the user's local setup.

## Configuration Boundary

- `.env` stores the local `DEEPSEEK_API_KEY` secret and remains ignored by Git.
- `config/llm_config.yaml` stores non-secret model and trigger settings and
  references the secret as `${DEEPSEEK_API_KEY}`.
- `server/main.py` continues loading the project-root `.env` during startup.
- No secret value is copied into documentation, command output, commits, or
  other tracked files.

## Migration

Read the existing literal key from the locally modified YAML configuration and
write it to `.env` without printing it. Replace the YAML value with the
environment-variable reference. Preserve every other existing YAML setting.

## README Changes

Update Quick Start so key configuration happens before server startup. Include
both PowerShell and POSIX copy commands, show the expected `.env` variable name
using a placeholder only, and state that model/threshold tuning belongs in
`config/llm_config.yaml` while secrets do not.

## Verification and Startup

Confirm `.env` is ignored, the tracked YAML contains only the environment
reference, and no tracked configuration contains the migrated secret. Start
Uvicorn on `127.0.0.1:8000` and verify the root page returns HTTP 200. Do not
print or otherwise expose the secret during verification.
