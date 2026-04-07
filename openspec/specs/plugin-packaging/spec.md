# Capability: plugin-packaging

## Purpose

Package the aaws MCP server for discovery and installation by Claude Code and compatible AI coding tools.

## Requirements

### Requirement: Claude Code plugin manifest
The project SHALL include a `.claude-plugin/plugin.json` manifest that declares the plugin name, version, description, MCP server command, and the list of available tools.

#### Scenario: Plugin discovery
- **WHEN** a user places the aaws repo in their Claude Code plugin directory
- **THEN** Claude Code SHALL read `.claude-plugin/plugin.json` and register the aaws MCP server

#### Scenario: Manifest completeness
- **WHEN** `.claude-plugin/plugin.json` is parsed
- **THEN** it SHALL contain fields for name, display_name, version, description, mcp_server configuration, and tools list

### Requirement: Project-scoped MCP configuration
The project SHALL include a `.mcp.json` file at the repository root that configures the aaws MCP server for automatic discovery by Claude Code.

#### Scenario: Zero-config MCP setup
- **WHEN** a user opens the aaws repo in Claude Code
- **THEN** Claude Code SHALL detect `.mcp.json` and offer to start the aaws MCP server without manual configuration

#### Scenario: MCP server command
- **WHEN** `.mcp.json` is read by Claude Code
- **THEN** the server command SHALL be `python -m aaws.mcp_server` with stdio transport

### Requirement: Plugin README
The project SHALL include a `.claude-plugin/README.md` that documents the plugin's tools, prerequisites, and installation options.

#### Scenario: Installation guidance
- **WHEN** a user reads `.claude-plugin/README.md`
- **THEN** it SHALL describe at least two installation methods (project-scoped `.mcp.json` and user-scoped `claude mcp add`)
