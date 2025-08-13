---
name: test_agent
description: A test agent for PACC integration testing
model: claude-3-sonnet
tools:
  - search
  - file_operations
parameters:
  temperature:
    type: number
    description: Controls randomness in responses
    default: 0.7
  max_tokens:
    type: integer
    description: Maximum number of tokens in response
    default: 1000
version: 1.0.0
---

# Test Agent

This is a test agent that demonstrates the PACC installation system.

## Features

- Search capabilities
- File operations
- Configurable parameters

## Usage

This agent can be used for basic tasks with Claude Code.