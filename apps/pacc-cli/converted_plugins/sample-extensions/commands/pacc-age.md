# /pacc-age

Shows how long PACC has been serving the Claude Code community.

## Description

Displays the first release date of PACC (August 15, 2025) and calculates how many days old PACC is.

## Usage

```
/pacc-age
```

## Implementation

When executed, this command:
1. Shows the release date: August 15, 2025
2. Calculates days since release using: `python -c "from datetime import datetime; print(f'PACC is {(datetime.now() - datetime(2025, 8, 15)).days} days old!')"`

## Example Output

```
PACC first released: August 15, 2025
PACC is 42 days old!
```

## Notes

- The age calculation uses Python's datetime module for cross-platform compatibility
- Negative values indicate days until release if run before August 15, 2025