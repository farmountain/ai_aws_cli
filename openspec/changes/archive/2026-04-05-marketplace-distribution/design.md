## Context

aaws v0.3.0 added an MCP server (`src/aaws/mcp_server.py`) with 5 tools for AI-assisted AWS CLI operations. The server uses FastMCP with stdio transport and is installable via `pip install aaws[mcp]`. Currently, users must discover the project through GitHub search or word-of-mouth. Three MCP marketplaces exist as distribution channels: the awesome-mcp-servers curated list, the Claude Code plugin system, and the Cline MCP marketplace.

## Goals / Non-Goals

**Goals:**
- Make aaws discoverable in the three major MCP marketplaces
- Provide zero-config MCP setup for Claude Code projects via `.mcp.json`
- Create a reusable plugin manifest that describes aaws capabilities
- Prepare submission-ready drafts that only need the GitHub owner filled in

**Non-Goals:**
- Runtime code changes or new MCP tools
- Automated submission pipelines or CI for marketplace publishing
- Supporting MCP marketplaces beyond the initial three
- Version-syncing plugin metadata with pyproject.toml

## Decisions

### 1. Plugin manifest in `.claude-plugin/` directory
Store the Claude Code plugin manifest at `.claude-plugin/plugin.json` with a companion README. This follows the emerging convention for Claude Code plugins and keeps plugin metadata separate from source code.

**Alternative considered:** Embedding plugin metadata in `pyproject.toml` — rejected because Claude Code expects a standalone manifest file.

### 2. Project-scoped `.mcp.json` at repo root
Provide a `.mcp.json` that auto-configures the MCP server when the repo is opened in Claude Code. Uses `python -m aaws.mcp_server` as the command, matching the existing entry point.

**Alternative considered:** Only documenting the `claude mcp add` command — rejected because `.mcp.json` provides zero-config setup and is version-controllable.

### 3. Submission drafts in `.github/marketplace/`
Store PR/issue drafts under `.github/marketplace/` rather than in docs or at the repo root. This keeps submission artifacts grouped with other GitHub-related files and out of the way of regular development.

**Alternative considered:** A top-level `marketplace/` directory — rejected to keep the root clean and group with `.github/` conventions.

### 4. Placeholder `[owner]` for GitHub username
All submission drafts use `[owner]` as a placeholder for the GitHub username/org. This avoids hardcoding and makes the drafts reusable if the repo is forked or transferred.

## Risks / Trade-offs

- **Marketplace format drift** → Submission formats may change. Mitigation: drafts are plain markdown, easy to update manually.
- **Plugin spec instability** → Claude Code plugin format is not yet finalized. Mitigation: keep the manifest minimal; update when the spec stabilizes.
- **Stale metadata** → Plugin version (0.3.0) won't auto-update with releases. Mitigation: accepted trade-off; manual update on major releases is sufficient for now.
