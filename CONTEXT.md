# Project Name: Knowledge Graph Mastere (KGM)

## 1. Project Context & Vision

### Overview
This is an 'open-source' project for exploring knowledge from documents, meant to be used locally. It ingests multimodal documents (containing text, images, and tables), processes them using **LlamaParse** to understand deep document hierarchy, and constructs a highly dynamic, deeply nested knowledge graph in Neo4j. Users can then interact with this knowledge visually through a dynamic force-directed graph and a conversationally graph-powered AI chat interface. 

The "agentic" nature comes from the system utilizing **LangGraph** to autonomously navigate the vector-enhanced graph, fetch context, and retrieve complex information, providing users with synthesized, context-aware answers. 

### Technical Stack
*   **Backend Framework:** Django 5.2 LTS for robust architecture and routing.
*   **Frontend Architecture:** HTMX for dynamic server-rendered HTML replacements, Alpine.js for lightweight frontend reactivity (modals, toggles), and TailwindCSS for utility-first styling. 
*   **Vanilla JS & Graph Engine:** Vanilla JavaScript utilizing 2D `force-graph` library for high-performance WebGL rendering of the Neo4j graph without the bloat of a heavy SPA framework.
*   **SQLite (The Content Library):** Stores the heavy, readable study materials.
    *   `Document` Table: Hashes of files to prevent accidental re-uploads (Note: Once processed, knowledge is entirely decoupled from the source document).
    *   `StudyAsset` Table: Stores granular content blocks (paragraphs, tables, image paths) mapped 1-to-1 with Neo4j Nodes via `sqlite_asset_id`.
*   **Neo4j (The "Brain Map"):** Stores the logical connections, keywords, and vectors.
    *   **Dynamic Ontology:** Nodes are dynamically categorized and connected by the LLM. 
    *   Properties on Nodes: `name` ("Photosynthesis"), `brief_summary`, `vector_embedding`, and crucially, **`sqlite_asset_id`**.
    *   Relationships: Dynamically determined context edges (e.g., `[:DEPENDS_ON]`, `[:DERIVED_FROM]`).
*   **AI Pipeline:** LangGraph for the agent workflow, utilizing `LlamaParse` for high-fidelity multimodal document extraction and initial structural generation, and an LLM to build and query the deep-nested graph.
*   **Asynchronous Task Processing:** Celery to handle computationally intensive document ingestion and graph construction. 
*   **Real-time Communication:** Django Channels and a Daphne server to manage WebSockets for streaming LangGraph responses token-by-token and tool-states to the chat interface.

## 2. Project Structure

```text
kgm/                                   # Project Root
├── chat/                              # Django App: Real-time LangGraph Chat
│   ├── static/                        # App-specific static files
│   │   └── chat.js                    # WebSocket setup & Alpine.js state logic
│   ├── templates/                     # App-specific templates (no redundant app sub-folder)
│   │   ├── partials/                  # HTMX partials folder
│   │   └── chat.html                  # AI Chat UI extending base.html
│   ├── consumers.py                   # AsyncWebsocketConsumer for LangGraph workflow
│   ├── routing.py                     # WebSocket URL routing definitions
│   ├── urls.py                        # View routing for chat page
│   └── views.py                       # Renders chat.html
├── core/                              # Django App: Document Handling
│   ├── static/                        # App-specific static files
│   │   └── core.js                    # File upload logic & progress WebSocket handler
│   ├── templates/                     # App-specific templates
│   │   ├── partials/                  # HTMX partials folder
│   │   │   └── upload_progress.html   # HTMX partial for dynamic task progress UI
│   │   └── core.html                  # Upload UI extending base.html
│   ├── models.py                      # Document hash logic & StudyAsset SQLite table
│   ├── services.py                    # LlamaParse extraction & Neo4j Saga Pattern logic
│   ├── tasks.py                       # Celery tasks for isolated DB staging & processing
│   ├── urls.py                        # View routing for upload endpoints
│   └── views.py                       # Renders core.html & handles initial uploads
├── graph/                             # Django App: Graph Visualization
│   ├── static/                        # App-specific static files
│   │   └── graph.js                   # WebGL force-graph rendering & RAM GC pruning
│   ├── templates/                     # App-specific templates
│   │   ├── partials/                  # HTMX partials folder
│   │   │   └── asset_modal.html       # HTMX partial for SQLite StudyAsset deep-dive modal
│   │   └── graph.html                 # Graph WebGL UI extending base.html
│   ├── services.py                    # Neo4j Breadcrumb queries & 1st-degree fetches
│   ├── urls.py                        # API endpoints for node expansion & views
│   └── views.py                       # Renders graph.html & node HTMX requests
├── kgm/                               # Django Config Directory
│   ├── celery.py                      # Celery app initialization & broker config
│   ├── settings.py                    # Global config (Tailwind, Neo4j, Channels, Celery)
│   └── urls.py                        # Root URL routing to apps
├── media/
├── theme/                             # Django-tailwind app
│   └── templates/                     # Global templates
│       └── base.html                  # Master layout with global nav & CSS links
├── .env                               # Environment variables (DB credentials, API keys)
├── .env.example                       # Safe template for required environment variables
├── .gitignore                         # Ignore rules for Python, Node, DBs, and media
├── docker-compose.local.yml           # Local orchestration for neo4j
├── manage.py                          # Django management script
├── package.json                       # Tailwind and dev-watcher run scripts
├── README.md                          # Project documentation and setup instructions
└── requirements.txt                   # Python dependencies (Django 5.2, LangGraph, etc.)
```

## 3. Setup and Execution

* The AI model, API keys, and all database credentials must be strictly controlled by the `.env` file.
* **No secrets should ever be hard-coded.**
* The setup must prioritize a seamless developer experience.
* Once the `.env` is configured, a user should be able to spin up the entire stack (Django, neo4j, Celery) simply by running `npm run dev`.

## 4. Core Technical Workflows

### Detailed Workflow 1: The 3-Step Resilient Ingestion Pipeline

*Goal: To build a highly resilient, four-phase pipeline that ingests a document and transforms it into a knowledge graph. Each step creates a persistent checkpoint, identified by a hash of the document's content. This architecture guarantees that if any step fails, the process can be safely and efficiently retried from the exact point of failure by re-uploading the same file.*

#### 1. Upload & Granular State Check
*   A student uploads a document. The backend calculates a hash of the file's content. This hash uniquely identifies the document.
*   The system queries the `Document` table for this hash:
    *   **If the hash does not exist:** This is a new document. A record is created, the status is set to `PENDING`, and the pipeline is initiated at Step 1.
    *   **If the hash exists:**
        *   **Reject:** If the status is `COMPLETED` or any in-progress state (`EXTRACTING`, `CHUNKING`, `STITCHING`, `UPLOADING`), the upload is rejected to prevent redundant work.
        *   **Retry:** If the status is `EXTRACTION_FAILED`, `CHUNKING_FAILED`, `STITCHING_FAILED`, or `UPLOAD_FAILED`, the system queues a retry task. The task worker will intelligently resume the process from the beginning of the failed step.

#### 2. Task Delegation (Celery)
*   The document's hash is passed to a Celery worker, moving the entire computationally-intensive pipeline off the main web thread.

---

#### **Step 1: LlamaParse Extraction & File Checkpoint**
*   **Status:** `EXTRACTING`
*   **Process:** The worker sends the document to LlamaParse to get the comprehensive hierarchy JSON, and extracted images using JSON mode.
*   **Checkpoint Commit:** This step's success is defined by the **saving** of these artifacts to the media directory, all named with the document's unique hash (e.g., `[hash].json`, `[hash]_image_1.png`). If the server crashes during the save, incomplete files are discarded. Only a complete save allows progression to the next step.

---

#### **Step 2 (Atomic): Algorithmic Chunking & StudyAsset Creation**
*   **Status:** `CHUNKING`
*   **Process:** A script reads the `[hash].json` file. It programmatically slices the Markdown into logical chunks.
*   **Checkpoint Commit:** Each chunk is saved as a new row in the `StudyAsset` SQLite table with a `EXTRACTED` satus within a single, **atomic database transaction**. Every StudyAsset is tagged with the document's hash. If the transaction fails for any reason, it is rolled back completely, preventing any orphaned StudyAsset rows.

---

#### **Step 3: AI Stitching & Graph JSON Generation**
*   **Status:** `UPLOADING`
*   **Process:** *for every StudyAsset*
    *   **Input:** The StudyAsset extracted from step 2.
    *   **GraphRAG:** Use GraphRAG to know what is already in the graph so that it can determine how to fit the new knowledge.
    *   **Output:** A script reads the `[asset_id]_graph.json` and executes the Cypher queries against Neo4j.
    *   **Safety MERGE:** All writes use the `MERGE` operation to prevent duplicate nodes or relationships.
    *   **Checkpoint:** Once the `[asset_id]_graph.json` is processed, the `StudyAsset` status is set to `UPLOADED`.
*   **Failure & Retry:** If the connection drops mid-upload, the status of the **document** becomes `UPLOAD_FAILED`. On retry, the script simply runs again on `StudyAsset` that has `EXTRACTED` status and pases those that has `UPLOADED` status.
*   **Completion Commit:** when all `StudyAsset` has the status `UPLOADED`, the document status becomes `COMPLETED`.

---

### Detailed Workflow 2: Visual Concept Exploration (The "Breadcrumb Web")
*Goal: Allow infinite deep-dive exploration of the graph without creating a visual hairball or bloating the browser's RAM.*

1.  **Initial Load:** The Graph UI requests the highest-level entry-point nodes via a lightweight query. Vanilla JS renders these via `force-graph`.
2.  **Deep Traversal & RAM Garbage Collection:**
    *   The student clicks a node (e.g., "Mitochondria" from "Cell").
    *   Vanilla JS requests the 1st-degree connections for "Mitochondria" from the backend (`/api/graph/expand/?node_id=1024`).
    *   **Memory Pruning:** Instead of just "hiding" the siblings (like "Nucleus" or "Ribosome"), JavaScript entirely drops them from the `graphData` arrays. This allows the browser's Garbage Collector to free the RAM. 
3.  **Visual Render State:** The graph array must contain:
    *   The currently clicked node (Mitochondria) - *Rendered visually prominent.*
    *   The newly fetched 1st-degree connections - *Rendered as standard nodes.*
    *   **The Breadcrumb Trail:** A single linear parent chain going all the way back to the root (e.g., `Biology -> Cell -> Mitochondria`). - *Rendered visually distinct.*
4.  **Result:** The user maintains spatial context of exactly how deep they are and how they got there, they can click backwards up the parent chain at any time, but off-screen data consumes zero background resources.
5.  **Deep Dive Study Modal:** Right-clicking any node triggers an HTMX request to fetch the heavy StudyAsset (text/images) from SQLite via its `sqlite_asset_id` and renders it in an Alpine.js modal.

---

### Detailed Workflow 3: LangGraph Chat Agent
*Goal: Provide a chat interface that acts as an intelligent tutor using LangGraph, with a highly responsive, low-perceived-latency UI.*

1.  **Volatile Memory & WebSocket Setup:** The student opens the chat. Vanilla JS connects to `ws/chat/stream/`. Chat history is managed as state within the LangGraph graph instance.
2.  **The Student's Prompt:** The student asks a cross-concept question.
3.  **LangGraph State Workflow:** The Django `ChatConsumer` triggers a compiled LangGraph workflow defined with tools for graph traversal and retrieval:
    *   `Search_Concept_Vectors`: Finds exact entry-point nodes.
    *   `Traverse_Deep_Graph`: Navigates the deeply nested edges dynamically.
    *   `Retrieve_SQLite_Asset`: Fetches the heavy text/tables (and image paths) from SQLite using the node's `sqlite_asset_id`.
4.  **Agentic Execution & Streaming UI:** 
    *   As LangGraph evaluates the input and decides which tools to call, the Django WebSocket **streams intermediate state events** to the frontend.
    *   The user sees dynamic status indicators: *"Searching graph..."* -> *"Fetching text from SQLite..."* -> *"Thinking..."*. 
    *   LangGraph synthesizes the retrieved information and streams the final text response back via WebSockets token-by-token, masking the database query latency and providing a fluid UX.

---