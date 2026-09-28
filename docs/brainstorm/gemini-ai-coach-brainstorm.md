# **Architecture & Technical Specification: PKM Knowledge Ingestion & Convention Engine (V1)**

## **1. Executive Summary**

This service acts as a centralized intelligence layer that ingests idiosyncratic Personal Knowledge Management (PKM) graphs, normalizes them into a high-fidelity canonical format, and utilizes AI to extract the underlying philosophies, leadership principles, and methodologies embedded within the notes. Guided by our MVP North Stars—specifically "Iterate with Velocity on a Flexible Foundation" and "Default to Simplicity"—this engine avoids premature scaling and focuses on proving that we can programmatically understand a coach's "operating system".

## **2. Architectural Principles & Trade-offs**

* **Pragmatic Monolith:** Built using FastAPI and Python, sharing the ecosystem of the broader platform to maximize developer velocity.


* **Hybrid Data Storage:** PostgreSQL utilizing both strict relational columns for routing/graph edges and `JSONB` for the flexible preservation of source-native payloads.


* **Loss-Minimizing Ingestion:** We will not discard unsupported data. If a specific Roam query or macro cannot be mapped semantically, it is stored in a JSONB preservation envelope so it can be re-evaluated by future iterations of the engine.


* **V1 Boundary:** We will focus strictly on **Roam Research JSON** exports. We will process data in manual batches (no real-time sync webhooks yet), deferring multi-format support (Notion, Google Docs) until the core extraction logic is validated.



## **3. The Canonical Data Model**

To capture your leadership and philosophy notes without pigeonholing them into "workout" formats, we will implement a generalized **Document-Graph Interchange Model** in PostgreSQL.

### **Core Relational Tables**

* `documents`: The top-level concept (e.g., a Roam Page like `Note/ The Fabric of Us`).


* `nodes`: The atomic structural units (the nested bullets/blocks).


* `relations`: Explicitly parsed edges (`links_to`, `embeds`, `references`). This is critical for capturing your "Branched Notes" connections.


* `attributes`: Parsed key-value metadata. When the parser sees `Stage:: #Sapling`, it writes a row here linking to the parent document.


* `identities`: A ledger mapping the canonical ID to the original Roam UID, ensuring we never lose the source provenance.

## **4. The Ingestion & Convention Detection Pipeline (LangGraph)**

We will use LangGraph to orchestrate a multi-stage, stateful ingestion pipeline that handles both the deterministic parsing of the file and the agentic extraction of meaning.

### **Stage 1: Deterministic Parsing & Normalization**

A Python service ingests the Roam `.json` file. It recursively flattens the block tree, translates epoch timestamps, and extracts Roam-specific syntax (`[[links]]`, `#tags`, `((block_refs))`) into the relational `relations` and `attributes` tables.

### **Stage 2: Semantic Embedding (`pgvector`)**

The normalized text nodes are vectorized using OpenAI embeddings and stored directly in PostgreSQL via the `pgvector` extension. Because we separated the metadata in Stage 1, we can perform highly targeted hybrid searches (e.g., "Vector search for 'leadership' but only filter for nodes where `Stage == #Evergreen`").

### **Stage 3: The Convention Extraction Agent (LangGraph)**

This is where we capture your "methodology." A LangGraph agent scans the newly populated canonical database to deduce your operational rules.

1. **Taxonomy Discovery:** The agent queries the `documents` table, noting your use of prefixes (`Area/`, `Problem/`, `Virtue/`). It formally registers these as your organizational taxonomy.


2. **Principle Extraction:** The agent looks for heavily referenced nodes or pages tagged as `#Evergreen Note`. It extracts the core thesis of these notes (e.g., "To write is to learn") and encodes them as structured philosophical rules in the database.


3. **Synthesis:** The output is a highly structured `coach_methodology` JSONB object that maps your distinct worldview, ready to be utilized as the system prompt context for any downstream AI Coach agent.



## **5. Infrastructure & Developer Workflow**

* **Database Migrations:** We will use a two-tiered strategy. Alembic handles structural SQL changes, while custom Python scripts handle the evolution of the `JSONB` schemas, all enforced by automated CI checks.


* **Cost Controls:** We will deploy the "Cost Sentinel" pattern immediately to track OpenAI token usage during these heavy graph-processing runs, alerting us if ingestion costs breach our daily budget.


* **Testing:** We will use an AI "Unit-Test Generator" persona to rapidly build test coverage for the deterministic parser, ensuring edge cases in the Roam JSON do not crash the pipeline.


## 6. Analysis of Your PKM Habits & Impact on the Spec

Looking closely at the snippets, your Roam graph relies on strict, self-imposed conventions that mimic a graph database schema.

**Detected Habits & Implicit Rules:**

* **Strict Entity Namespacing (Prefixing):** You use prefixes to define explicit entity types across your graph (e.g., `Area/`, `Source/`, `Note/`, `Virtue/`, `Problem/`, `Project/`).


* **Standardized Metadata Headers:** Almost every conceptual page starts with a highly structured `- Metadata` block containing key-value pairs (`Area::`, `Type::`, `Stage::`, `Related::`, `Why did we create this?::`).


* **Zettelkasten Maturity Pipelines:** You explicitly track the lifecycle of an idea. Notes move from `Fleeting` -> `Source` -> `Evergreen`. You also track the maturity of Evergreen notes using tags like `#Seedling`, `#Sprout`, and `#Sapling`.


* **Atomic Modularity & Block Transclusion:** You rely heavily on block references `((uid))` and embeds `{{embed: }}` to weave ideas together (e.g., "Branched Notes") without duplicating the source text.
