# Capability: marketplace-submissions

## Purpose

Provide ready-to-submit draft entries for external MCP marketplace listings and curated directories.

## Requirements

### Requirement: awesome-mcp-servers PR draft
The project SHALL include a draft PR entry for the awesome-mcp-servers curated list, ready to submit to the punkpeye/awesome-mcp-servers repository.

#### Scenario: PR draft content
- **WHEN** the awesome-mcp-servers PR draft is read
- **THEN** it SHALL contain the exact list entry line formatted as `- [aaws](url) - description`, a PR title, and a PR description body

#### Scenario: Category placement
- **WHEN** the list entry is reviewed
- **THEN** it SHALL target the "Cloud Platforms" category

### Requirement: Cline marketplace submission draft
The project SHALL include a draft GitHub issue for submitting aaws to the Cline MCP marketplace at cline/mcp-marketplace.

#### Scenario: Submission content
- **WHEN** the Cline submission draft is read
- **THEN** it SHALL contain the issue title and body with server name, repository URL, description, tools list, installation instructions, and category

### Requirement: Submission drafts location
All marketplace submission drafts SHALL be stored under `.github/marketplace/`.

#### Scenario: File organization
- **WHEN** a contributor looks for submission drafts
- **THEN** they SHALL find them at `.github/marketplace/awesome-mcp-servers-pr.md` and `.github/marketplace/cline-marketplace-submission.md`

### Requirement: Owner placeholder
All submission drafts SHALL use `[owner]` as a placeholder for the GitHub username or organization, to be replaced before submission.

#### Scenario: Placeholder usage
- **WHEN** a submission draft contains a GitHub URL
- **THEN** the URL SHALL use `[owner]` in place of the actual GitHub username (e.g., `https://github.com/[owner]/ai_aws_cli`)
