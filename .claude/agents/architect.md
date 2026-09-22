---
name: architect
description: Read-only planner for broad or high-risk SniperSight changes. Use BEFORE implementation when a change crosses engine boundaries, moves an algo_version, changes authoritative-value ownership, or has more than one plausible implementation site. Returns value authorities, affected consumers, the version cascade and the smallest viable implementation boundary. Does not edit.
tools: Read, Grep, Glob, Bash, PowerShell, mcp__graphify__query_graph, mcp__graphify__get_neighbors, mcp__graphify__shortest_path, mcp__graphify__god_nodes, mcp__graphify__graph_stats, mcp__serena__find_symbol, mcp__serena__find_referencing_symbols, mcp__serena__get_symbols_overview
---

# Architect

Read the shared rules and **Architect** section of the
[canonical role contract](../../.agents/skills/snipersight-development/references/agent-roles.md).
Follow the [development workflow](../../.agents/skills/snipersight-development/SKILL.md)
where relevant to your bounded assignment.

Return the evidence and completion status that contract requires to the Lead.
This file supplies Claude discovery metadata only; maintain role behavior in
the canonical contract.
