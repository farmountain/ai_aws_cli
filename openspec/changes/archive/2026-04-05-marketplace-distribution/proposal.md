## Why

aaws v0.3.0 ships a fully functional MCP server with 5 tools, but discoverability is limited to users who find the GitHub repo directly. Publishing to MCP marketplaces (awesome-mcp-servers, Claude Code plugin directory, Cline marketplace) puts aaws in front of developers who are actively looking for cloud-platform MCP integrations. This is the natural next step after the v0.3.0 MCP release.

## What Changes

- Add a submission entry for the awesome-mcp-servers curated list (Cloud Platforms category)
- Create a Claude Code plugin manifest (`.claude-plugin/`) so aaws can be installed as a first-class plugin
- Add a project-scoped `.mcp.json` for zero-config MCP setup in Claude Code projects
- Prepare a Cline MCP marketplace submission (GitHub issue template)
- Add submission drafts and instructions under `.github/marketplace/`

## Capabilities

### New Capabilities
- `plugin-packaging`: Plugin manifest, MCP config, and metadata files needed for marketplace distribution
- `marketplace-submissions`: PR and issue drafts for external marketplace submissions (awesome-mcp-servers, Cline)

### Modified Capabilities

None. This change adds distribution artifacts only; no runtime behavior changes.

## Impact

- New files: `.claude-plugin/plugin.json`, `.claude-plugin/README.md`, `.mcp.json`, `.github/marketplace/*.md`
- No changes to source code, dependencies, or APIs
- No breaking changes
