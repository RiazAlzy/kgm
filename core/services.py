import json
import os
import re
import httpx
import time
from django.db import transaction
from neo4j import GraphDatabase
from llama_cloud import LlamaCloud, LlamaCloudError 
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List

from .models import StudyAsset


from django.conf import settings

# ==========================================
# STEP 1: LlamaParse Multimodal Extraction
# ==========================================
def extract_with_llamaparse(file_hash, file_path):
    print(f"[INFO] Initializing LlamaCloud client for extraction: {file_hash}", flush=True)
    llama_key = os.environ["LLAMA_CLOUD_API_KEY"]
    
    client = LlamaCloud(api_key=llama_key)
    try:
        print(f"[INFO] Parsing file via LlamaCloud (Agentic Tier): {file_path}", flush=True)
        file_obj = client.files.create(file=file_path, purpose="parse")

        # 1. Parse with Agentic Tier & Request Image Extraction
        result = client.parsing.parse(
            file_id=file_obj.id, 
            tier="agentic",
            version="latest",
            output_options={
                "images_to_save": ["embedded", "screenshot"]
            },
            expand=["markdown", "images_content_metadata"]
        )
        print(f"[SUCCESS] LlamaCloud parsing complete for {file_hash}", flush=True)
    except LlamaCloudError as e:
        print(f"[ERROR] LlamaCloud API error: {e}", flush=True)
    
    if not os.path.exists(settings.MEDIA_ROOT):
        print(f"[INFO] Creating media root directory: {settings.MEDIA_ROOT}", flush=True)
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        
    json_results = []
    downloaded_images = {}

    # 2. Pre-Download Images & Map their Filenames
    if getattr(result, "images_content_metadata", None) and result.images_content_metadata.images:
        print(f"[INFO] Downloading {len(result.images_content_metadata.images)} extracted images", flush=True)
        for image in result.images_content_metadata.images:
            image_filename = f"{file_hash}_{image.filename}"
            image_path = os.path.join(settings.MEDIA_ROOT, image_filename)
            
            # Download image from presigned URL
            print(f"[INFO] Downloading image: {image_filename}", flush=True)
            with httpx.Client() as http_client:
                response = http_client.get(image.presigned_url)
                with open(image_path, "wb") as img_file:
                    img_file.write(response.content)
            
            downloaded_images[image.filename] = image_filename

    unassigned_images = set(downloaded_images.keys())
            
    # 3. Extract Text Pages & Interleave Contextual Images
    if getattr(result, "markdown", None) and result.markdown.pages:
        print(f"[INFO] Extracting {len(result.markdown.pages)} text pages", flush=True)
        for page in result.markdown.pages:
            is_table = bool(re.search(r'\|[-:]+[-| :]*\|', page.markdown))
            json_results.append({
                "type": "table" if is_table else "text",
                "content": page.markdown
            })

            # Associate images referenced inside this specific page's markdown
            for orig_name, saved_name in list(downloaded_images.items()):
                if orig_name in page.markdown:
                    json_results.append({
                        "type": "image_path",
                        "content": saved_name
                    })
                    unassigned_images.discard(orig_name)

    # 4. Catch-all: Append any unreferenced images to the final chunk
    for orig_name in unassigned_images:
        json_results.append({
            "type": "image_path",
            "content": downloaded_images[orig_name]
        })

    # 5. Save the Unified Checkpoint
    output_path = os.path.join(settings.MEDIA_ROOT, f"{file_hash}.json")
    print(f"[INFO] Saving unified extraction checkpoint to {output_path}", flush=True)
    with open(output_path, 'w') as f:
        json.dump(json_results, f)


# ==========================================
# STEP 2: Atomic Algorithmic Chunking
# ==========================================
def chunk_to_sqlite(file_hash, document):
    input_path = os.path.join(settings.MEDIA_ROOT, f"{file_hash}.json")
    print(f"[INFO] Loading extraction checkpoint from {input_path}", flush=True)
    with open(input_path, 'r') as f:
        data = json.load(f)
        
    print(f"[INFO] Starting atomic chunking to SQLite for {file_hash}", flush=True)
    with transaction.atomic():
        deleted_count, _ = StudyAsset.objects.filter(document=document).delete()
        if deleted_count > 0:
            print(f"[INFO] Deleted {deleted_count} existing assets for document", flush=True)
        
        current_asset = None

        for idx, item in enumerate(data):
            asset_type = item.get("type")
            if asset_type in ["text", "table"]:
                asset_id = f"{file_hash}_chunk_{idx}"
                current_asset = StudyAsset.objects.create(
                    sqlite_asset_id=asset_id, 
                    document=document,
                    asset_type=asset_type, 
                    content=item.get("content"),
                    status="EXTRACTED",  
                    image_paths=[] # Initialize the empty list
                )
            elif item.get("type") == "image_path" and current_asset:
                # Append image to the previously captured text chunk
                images = current_asset.image_paths
                images.append(item.get("content"))
                current_asset.image_paths = images
                current_asset.save()
                
    print(f"[SUCCESS] Finished chunking {len(data)} items to SQLite for {file_hash}", flush=True)


# ==========================================
# STEP 3: Upload with GraphRAG
# ==========================================

class Node(BaseModel):
    id: str = Field(description="The unique name of the concept (e.g., 'Photosynthesis')")
    brief_summary: str = Field(description="A 1-sentence summary of the concept")
    sqlite_asset_id: str = Field(description="The exact deterministic sqlite_asset_id assigned to this chunk")

class Edge(BaseModel):
    source: str = Field(description="Source concept ID")
    target: str = Field(description="Target concept ID")
    relation: str = Field(description="The relationship action (e.g., 'DEPENDS_ON', 'PRODUCES')")

class GraphExtraction(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


def process_and_upload_assets(file_hash, document):
    """
    Per-asset GraphRAG extraction and instant Neo4j promotion.
    """
    neo4j_uri = os.environ["NEO4J_URI"]
    neo4j_user = os.environ["NEO4J_USER"]
    neo4j_password = os.environ["NEO4J_PASSWORD"]
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    llm_model = os.environ.get("LLM_MODEL")

    if provider == "gemini":
        model_name = llm_model if llm_model.startswith("models/") else f"models/{llm_model}"
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=os.environ.get("GOOGLE_API_KEY"), temperature=0)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=os.environ.get("GOOGLE_API_KEY"))
        embedding_dim = 768
    else:
        llm = ChatOpenAI(model=llm_model, api_key=os.environ.get("OPENAI_API_KEY"), temperature=0)
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=os.environ.get("OPENAI_API_KEY"))
        embedding_dim = 1536

    structured_llm = llm.with_structured_output(GraphExtraction)

    # Ensure Vector Index exists
    with driver.session() as session:
        session.run(f"""
        CREATE VECTOR INDEX concept_embeddings IF NOT EXISTS FOR (c:Concept) ON (c.embedding)
        OPTIONS {{indexConfig: {{ `vector.dimensions`: {embedding_dim}, `vector.similarity_function`: 'cosine' }}}}
        """)

    # 1. Fetch ONLY assets that are EXTRACTED (handles pause/retry automatically)
    assets = StudyAsset.objects.filter(
        sqlite_asset_id__startswith=f"{file_hash}_chunk_",
        asset_type__in=["text", "table"],
        status="EXTRACTED"
    ).order_by('sqlite_asset_id')

    for idx, asset in enumerate(assets):
        asset_id = asset.sqlite_asset_id
        chunk_text = asset.content
        
        try:
            # --- 2. GraphRAG Context Search ---
            chunk_vector = embeddings.embed_query(chunk_text)
            existing_graph_context = []
            with driver.session() as session:
                cypher = """
                CALL db.index.vector.queryNodes('concept_embeddings', 4, $embedding) YIELD node, score
                OPTIONAL MATCH (node)-[r]-(m:Concept)
                RETURN node.name as concept, node.brief_summary as summary, type(r) as relation, m.name as related_concept
                """
                try:
                    result = session.run(cypher, embedding=chunk_vector)
                    existing_graph_context.extend([record.data() for record in result])
                except Exception:
                    pass # Index warming up

            unique_context = {json.dumps(d, sort_keys=True) for d in existing_graph_context if d.get('concept')}
            context_str = json.dumps([json.loads(c) for c in unique_context], indent=2)

            # --- 3. AI Extraction ---
            extraction_prompt = ChatPromptTemplate.from_template("""
            You are an advanced Knowledge Graph extraction agent. Extract entities and relationships.
            EXISTING GRAPH CONTEXT: {context}
            NEW CHUNK: {chunk}
            RULES: EVERY node must be assigned sqlite_asset_id: "{asset_id}". 
            """)

            extraction = structured_llm.invoke(
                extraction_prompt.format(
                    context=context_str if context_str != "[]" else "Empty graph.",
                    chunk=chunk_text,
                    asset_id=asset_id
                )
            )

            # --- 4. Instant Neo4j Promotion (MERGE) ---
            with driver.session() as session:
                # Merge Nodes
                for node in extraction.nodes:
                    node_vector = embeddings.embed_query(f"{node.id}: {node.brief_summary}")
                    session.run("""
                        MERGE (n:Concept {name: $name})
                        SET n.brief_summary = $summary,
                            n.embedding = $embedding,
                            n.sqlite_asset_ids = CASE 
                                WHEN $asset_id IN coalesce(n.sqlite_asset_ids, []) THEN coalesce(n.sqlite_asset_ids, []) 
                                ELSE coalesce(n.sqlite_asset_ids, []) + $asset_id 
                            END
                    """, name=node.id, asset_id=asset_id, summary=node.brief_summary, embedding=node_vector)

                # Merge Edges
                for edge in extraction.edges:
                    raw_relation = edge.relation.upper().replace(" ", "_").replace("-", "_")
                    relation_type = re.sub(r'[^A-Z0-9_]', '', raw_relation) or "RELATED_TO"
                    session.run(f"""
                        MATCH (source:Concept {{name: $source_name}})
                        MATCH (target:Concept {{name: $target_name}})
                        MERGE (source)-[r:{relation_type}]->(target)
                    """, source_name=edge.source, target_name=edge.target)

            # --- 5. Asset Checkpoint Commit ---
            asset.status = "UPLOADED"
            asset.save()
            time.sleep(1) # API rate limit safety

        except Exception as e:
            driver.close()
            # Fail document status if an asset fails; retrying will pick up where it left off
            document.status = "UPLOAD_FAILED"
            document.save()
            raise e 

    # --- 6. Final Completion Commit ---
    driver.close()
    document.status = "COMPLETED"
    document.save()