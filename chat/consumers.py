import json
import os
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from neo4j import AsyncGraphDatabase


# ==========================================
# LangGraph Tools (Async)
# ==========================================

@tool
async def search_concept_vectors(query: str) -> str:
    """Finds exact entry-point nodes in the Neo4j knowledge graph using vector similarity."""
    # 1. Initialize embeddings dynamically
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider == "gemini":
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=os.environ.get("GOOGLE_API_KEY"))
    else:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=os.environ.get("OPENAI_API_KEY"))
    
    # 2. Embed the query asynchronously
    query_vector = await embeddings.aembed_query(query)

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    # 3. Vector Index Search
    cypher = """
    CALL db.index.vector.queryNodes('concept_embeddings', 5, $query_vector) YIELD node, score
    RETURN node.name AS name, node.brief_summary AS summary, node.sqlite_asset_ids AS asset_ids, score
    """
    
    async with driver.session() as session:
        result = await session.run(cypher, query_vector=query_vector)
        records = [record.data() async for record in result]
    await driver.close()
    
    return json.dumps(records) if records else "No matching concepts found."

@tool
async def traverse_deep_graph(node_name: str) -> str:
    """Navigates nested edges dynamically from a specific concept node to find related concepts."""
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    cypher = """
    MATCH (n:Concept {name: $node_name})-[r]-(m:Concept)
    RETURN type(r) AS relation, m.name AS connected_concept, m.brief_summary AS summary, m.sqlite_asset_ids AS asset_ids
    LIMIT 10
    """
    async with driver.session() as session:
        result = await session.run(cypher, node_name=node_name)
        records = [record.data() async for record in result]
    await driver.close()
    
    return json.dumps(records) if records else "No related concepts found."

@sync_to_async
def _fetch_asset_from_db(asset_id: str):
    from core.models import StudyAsset
    asset = StudyAsset.objects.filter(sqlite_asset_id=asset_id).first()
    return asset.content if asset else f"Asset {asset_id} not found."

@tool
async def retrieve_sqlite_asset(asset_id: str) -> str:
    """Fetches the heavy text/tables/images from SQLite using the node's sqlite_asset_id."""
    return await _fetch_asset_from_db(asset_id)


# ==========================================
# WebSocket Consumer
# ==========================================

class ChatConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        await self.accept()
        
        # Volatile Memory setup per WebSocket session
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}
        self.memory = MemorySaver()

        # Initialize Model & Tools
        tools = [search_concept_vectors, traverse_deep_graph, retrieve_sqlite_asset]
        provider = os.environ.get("LLM_PROVIDER").lower()
        llm_model = os.environ.get("LLM_MODEL")
        if provider == "gemini":
            # Google API requires 'models/' prefix for many versions
            model_name = llm_model if llm_model.startswith("models/") else f"models/{llm_model}"
            llm = ChatGoogleGenerativeAI(
                model=model_name, 
                google_api_key=os.environ.get("GOOGLE_API_KEY"),
                temperature=0.2,
            )
        else:
            llm = ChatOpenAI(
                model=llm_model,
                api_key=os.environ.get("OPENAI_API_KEY"),
                temperature=0.2,
                streaming=True
            )
        llm_with_tools = llm.bind_tools(tools)

        # Agent Node
        async def chatbot(state: MessagesState):
            response = await llm_with_tools.ainvoke(state["messages"])
            return {"messages": [response]}

        # Build Graph
        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("chatbot", chatbot)
        graph_builder.add_node("tools", ToolNode(tools=tools))
        
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_conditional_edges("chatbot", tools_condition)
        graph_builder.add_edge("tools", "chatbot")
        
        self.graph = graph_builder.compile(checkpointer=self.memory)

    async def disconnect(self, close_code):
        # MemorySaver is garbage collected naturally when WebSocket drops
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_message = data.get("message")
        if not user_message:
            return

        # V2 Streaming for granular intermediate steps and tokens
        async for event in self.graph.astream_events(
            {"messages": [HumanMessage(content=user_message)]},
            config=self.config,
            version="v2"
        ):
            kind = event["event"]
            
            # Stream Tokens
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    await self.send(text_data=json.dumps({
                        "type": "token",
                        "content": chunk.content
                    }))
                    
            # Stream Tool Execution (Agentic UI Feedback)
            elif kind == "on_tool_start":
                tool_name = event["name"]
                if tool_name == "search_concept_vectors":
                    msg = "Searching Neo4j for vector entry points..."
                elif tool_name == "traverse_deep_graph":
                    msg = "Traversing nested relationships..."
                elif tool_name == "retrieve_sqlite_asset":
                    msg = "Fetching core document context from SQLite..."
                else:
                    msg = "Thinking..."

                await self.send(text_data=json.dumps({
                    "type": "status",
                    "message": msg
                }))
                
        # Signal frontend that the stream is complete
        await self.send(text_data=json.dumps({"type": "end"}))