# PACC CLI Test Samples

These sample extensions demonstrate valid PACC extension formats for testing the CLI.

## Contents

- **hooks/pacc-celebration-hook.json**: PostToolUse hook that celebrates your PACC'd session
- **agents/pacc-man.md**: Helper agent for PACC CLI (use only when explicitly requested)
- **commands/pacc-age.md**: Shows how long PACC has been around

## Testing Commands

### Validate Extensions

```bash
cd apps/pacc-cli

# Validate individual extensions
python -m pacc validate ./examples/samples/hooks/pacc-celebration-hook.json --type hooks
python -m pacc validate ./examples/samples/agents/pacc-man.md --type agents
python -m pacc validate ./examples/samples/commands/pacc-age.md --type commands

# Or validate all at once
python -m pacc validate ./examples/samples/
```

### Install Extensions (when CLI is complete)

```bash
# Install to project
pacc install ./examples/samples/hooks/pacc-celebration-hook.json --project
pacc install ./examples/samples/agents/pacc-man.md --project
pacc install ./examples/samples/commands/pacc-age.md --project

# Or install all at once with interactive selection
pacc install ./examples/samples/ --project
```

## Extension Details

### pacc-celebration-hook.json
- **Type**: Hook
- **Event**: PostToolUse
- **Action**: Echoes "Your Claude Code session is PACC'd!" after tool execution
- **Safety**: Non-intrusive, runs after tool completion

### pacc-man.md
- **Type**: Agent
- **Activation**: Only when explicitly requested by user
- **Action**: Thanks the user and shows PACC help
- **Safety**: Contains instructions to never auto-activate

### pacc-age.md
- **Type**: Command
- **Command**: `/pacc-age`
- **Action**: Shows PACC release date and calculates age in days
- **Implementation**: Uses Python datetime for cross-platform compatibility

## Notes

These samples are designed to:
- Pass all PACC validation checks
- Be non-intrusive (PostToolUse hook, agent requires explicit invocation)
- Demonstrate proper extension structure
- Be fun and PACC-themed!
- Provide a quick way to test PACC CLI functionality

## Validation Testing

You can test the validation system with these samples:

```python
# Test programmatically
from pacc.validators.hooks import HooksValidator
from pacc.validators.agents import AgentsValidator
from pacc.validators.commands import CommandsValidator

# Validate hook
hook_validator = HooksValidator()
result = hook_validator.validate_single("./examples/samples/hooks/pacc-celebration-hook.json")
print(f"Hook valid: {result.is_valid}")

# Validate agent
agent_validator = AgentsValidator()
result = agent_validator.validate_single("./examples/samples/agents/pacc-man.md")
print(f"Agent valid: {result.is_valid}")

# Validate command
command_validator = CommandsValidator()
result = command_validator.validate_single("./examples/samples/commands/pacc-age.md")
print(f"Command valid: {result.is_valid}")
```
