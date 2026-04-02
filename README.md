# Knowledge Graph Mastere (KGM)

Knowledge Graph Mastere (KGM) is a sophisticated open-source project for exploring knowledge from documents locally. It ingests multimodal documents, processes them using **LlamaParse**, and constructs a highly dynamic, deeply nested knowledge graph in **Neo4j**. Users can then interact with this knowledge *visually* through a dynamic force-directed graph and a *conversationally* graph-powered AI chat interface.

## 🚀 Key Features

- **Resilient 3-Step Ingestion Pipeline:** A robust, state-checkpointed pipeline for extracting knowledge from documents (PDF, Markdown, Image) into logical graph nodes.
- **Deep-Nested Visual Exploration:** A high-performance WebGL force-directed graph using vanilla JS that supports infinite deep-dives through a "Breadcrumb Web" while maintaining browser RAM efficiency.
- **Agentic AI Chat:** A real-time chat interface powered by **LangGraph** that autonomously traverses your Neo4j graph and retrieves core context from **SQLite** to provide context-aware tutoring.

---

## 🛠️ Technical Stack

- **Backend:** Django 5.2 (LTS), Django Channels (WebSockets), Celery (Async Tasks).
- **Frontend:** HTMX, Alpine.js, TailwindCSS, Force-Graph (WebGL).
- **Databases:** Neo4j (Graph/Logical), SQLite (Content/Assets).
- **AI/LLM:** LangGraph (Multi-agent orchestration), LlamaParse (High-fidelity parsing), Gemini or OpenAI.

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed:
- **Python 3.10+**
- **Node.js 18+** & **npm**
- **Docker & Docker Compose**
- **API Keys:**
  - [Gemini API Key](https://aistudio.google.com/api-keys)
  - [OpenAI API Key](https://platform.openai.com/)
  - [LlamaParse Cloud API Key](https://cloud.llamaindex.ai/)

---

## 📥 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/RiazAlzy/kgm.git
cd kgm
```

### 2. Set Up Python Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Install Node.js Dependencies
Install root dev-dependencies and the Tailwind CSS theme dependencies:
```bash
npm install
cd theme/static_src
npm install
cd ../..
```

### 4. Configure Environment Variables
Copy the `.env.example` file to `.env` and fill in your API keys and configuration:
```bash
cp .env.example .env
```

---

## 🏃 Running the Application

0. **Must have docker running in the background**

1. **Run Migrations:**
   ```bash
   python manage.py migrate
   ```

2. **Launch the KGM "One-Command" Setup:**
   The project includes a convenient script to start the Django server, Tailwind watcher, and Celery worker concurrently:
   ```bash
   npm run kgm
   ```

3. **Access the App:**
   Open your browser and navigate to `http://localhost:8000`.

* **Note:** After initial setup, you can just run 'npm run kgm' to restart the project. You **must have docker running in background**.

---

## 📖 Usage Guide

1. **Upload Documents:** Ingest you documents in the Ingest tab.
2. **Explore Graph:** Visit the "Graph" tab to see your knowledge visualised. 
   - **Left-Click:** Deep-dive into a concept and its connections.
   - **Right-Click:** Open the deep-study modal to read the original source text/tables for that node.
3. **Chat with AI:** Open the "Chat" interface and ask questions.

---

## 🤝 Contributing

Contributions are welcome! Please read `CONTRIBUTING.md` for our submission process.

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.
