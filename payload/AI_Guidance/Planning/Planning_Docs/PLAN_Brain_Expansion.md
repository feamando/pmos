# Plan: Brain Expansion & Synaptic Density

**Objective:** To evolve the Brain from a static entity registry into a high-density, interconnected knowledge graph that functions as the "long-term memory" and "signal guidance" for the AI agent.

## Core Metaphor
- **Entities (Neurons):** The core nodes (People, Projects, Teams).
- **Context (Signal):** The rich, updated content defining the entity's current state.
- **Connections (Synapses):** The explicit and implicit relationships between entities.

---

## Strategy 1: Structured Metadata (The Synapses)

**Goal:** Move from implicit text mentions to explicit, typed relationships.

### 1.1 Typed Relationships in Frontmatter
Introduce a standard schema for `relationships` in the YAML frontmatter of every Brain file.

**Current:**
```yaml
aliases: ['OTP']
```

**Proposed:**
```yaml
relationships:
  owner: ['[[Entities/Nikita_Gorshkov]]']
  blocked_by: ['[[Projects/Logistics_Upgrade]]']
  dependency_for: ['[[Projects/Winter_Campaign]]']
  relates_to: 
    - '[[Architecture/OWL]]'
    - '[[Entities/Team_Good_Chop]]'
```

### 1.2 Automated Bi-Directional Linking (`synapse_builder.py`)
A new maintenance tool that runs periodically to enforce reciprocity.
- *Logic:* If Project A lists "Owner: Person B", the script updates Person B's file to list "Owns: Project A".
- *Benefit:* Ensures that traversing from *any* node reveals the full graph context.

---

## Strategy 2: Contextual Mirroring (The Signal)

**Goal:** Increase the "resolution" of the signal by ingesting deep content, not just metadata.

### 2.1 Deep Content Ingestion
Currently, we sync *status* (Jira) or *existence* (GitHub). We need to sync *substance*.

- **Confluence Mirroring:**
  - Create a tool (`confluence_brain_sync.py`) to fetch full page content for key architectural docs.
  - Summarize the content into a "Knowledge" section in the corresponding Brain file.
  - *Ref:* "Knowledge Graph Construction" best practice: iterative refinement of extracted knowledge.

- **Repo Readmes & Architecture:**
  - Enhance `github_brain_sync.py` to pull `README.md` and `ARCHITECTURE.md` content.
  - Store this as a "Technical Context" block in Project files.

### 2.2 "State of the Union" Sections
- Introduce a reserved section in every Brain file: `## Current State`.
- This section is *overwritten* (not appended) by specific synthesis tools, providing an always-fresh summary of the entity's health, rather than a long changelog history.

### 2.3 Source Verification & Data Hygiene (Crucial)
**Constraint:** Confluence and GDocs are often stale ("flakey"). They cannot be treated as absolute sources of truth.

**Mitigation Rules:**
1.  **Freshness Weighting:** When ingesting external docs, check `last_updated`. If > 90 days, tag content as `(Potentially Stale)` in the Brain.
2.  **Code Over Prose:** Prioritize structural truth from Git (e.g., `package.json` dependencies, `CODEOWNERS`) over Confluence descriptions. Code doesn't lie; documentation often does.
3.  **Curator Pattern:** The ingestion tools must not blindly mirror text. They must act as *curators*, using LLM synthesis to flag contradictions (e.g., "Confluence says Owner is X, but Git history shows only Y commits").

---

## Strategy 3: Vectorization (The Hidden Layer)

**Goal:** Enable semantic "fuzzy" connections that explicit links miss.

### 3.1 Embedding Index
- Generate vector embeddings for every paragraph in the Brain.
- Store these in a local vector store (e.g., FAISS or a simple JSON/numpy store for portability).
- *Usage:* When the Agent queries "logistics issues", the system retrieves not just files with the word "logistics", but files describing "shipping delays" or "warehouse bottlenecks" even if the keyword matches are weak.

---

## Critical Analysis & Feasibility Review ("Red Team")

**Challenge:** Does increasing "density" actually improve performance, or does it just create noise?

### 1. The Token Cost & Context Window Problem
*   **Critique:** "Fatter" Brain files with deep content mirroring (Strategy 2) will bloat the context window. If every Project file includes a full Confluence summary, loading 5 related projects might exceed token limits or diluting the Agent's attention.
*   **Counter-Measure:** strict *summarization* upon ingestion. Never mirror raw text; mirror a compressed, AI-generated summary. Implement "Lazy Loading" where only the high-level metadata is loaded initially, and deep content is fetched only if specifically requested.

### 2. The Staleness & Drift Risk
*   **Critique:** Mirroring external data (Confluence/Jira) creates a "Source of Truth" conflict. If the Brain copy lags behind the live Confluence page by 24 hours, the Agent may make decisions on obsolete data.
*   **Counter-Measure:** All mirrored sections must be timestamped and clearly marked as "Cached". The system must prioritize live fetching for critical queries (`get_page`) over reading the cached Brain version. The Brain acts as an *index* and *map*, not the definitive database for volatile data.

### 3. Maintenance Burden vs. Value
*   **Critique:** Typed relationships (Strategy 1) are brittle. Maintaining `blocked_by` manually is toil. If it's not automated, it will rot.
*   **Counter-Measure:** Relationships must be *inferred* automatically from the daily context updates, not manually edited. The `brain_updater.py` should parse "Blocker: X" in daily notes and update the YAML automatically. Manual editing should be the exception.

### 4. GraphRAG Complexity
*   **Critique:** Building a true GraphRAG system (Strategy 3) adds significant architectural complexity (vector DBs, embedding models) to a currently simple file-based system.
*   **Counter-Measure:** Start with "Graph-Lite". Use the explicit links (Strategy 1) for navigation first. Only implement embeddings if keyword search proves insufficient. Stick to file-based semantic search tools (like `ripgrep` with smart regex) before adopting a vector DB.

### Conclusion
The "Synapse" approach (Strategy 1) yields the highest immediate ROI for reasoning. The "Signal" approach (Strategy 2) helps understanding but carries high token/maintenance costs. We will proceed with **Strategy 1 (Metadata)** and **Strategy 2 (Summarized Mirroring only)** immediately, while deferring Vectorization.
