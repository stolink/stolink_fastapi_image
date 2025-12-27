# LangGraph Image Generation Graph
# Orchestrates image generation/editing workflow using LangGraph StateGraph

from typing import TypedDict, Literal, Optional, Annotated
from operator import add
import logging

from langgraph.graph import StateGraph, START, END

from app.services.bedrock_service import get_bedrock_service
from app.services.prompt_service import get_prompt_service
from app.services.s3_service import get_s3_service
from app.services.gemini_service import get_gemini_service

logger = logging.getLogger(__name__)


# =============================================================================
# State Definition
# =============================================================================

class ImageGraphState(TypedDict):
    """State that flows through the image generation graph."""
    # Input
    action: Literal["create", "edit"]
    message: str  # Character description or edit request
    source_image_url: Optional[str]  # For edit action
    
    # Intermediate
    enhanced_prompt: Optional[str]
    edit_prompt: Optional[str]  # For edit action (Gemini)
    generated_image_bytes: Optional[bytes]
    
    # Output
    result_image_url: Optional[str]
    error: Optional[str]
    
    # Metadata
    job_id: Optional[str]
    character_id: Optional[str]


# =============================================================================
# Node Functions
# =============================================================================

def generate_prompt_node(state: ImageGraphState) -> ImageGraphState:
    """
    Node: Generate optimized prompt using Claude.
    Routes based on action type (create vs edit).
    """
    try:
        prompt_service = get_prompt_service()
        
        if state["action"] == "create":
            # Generate character creation prompt
            logger.info(f"[Node: generate_prompt] Creating prompt for: {state['message'][:50]}...")
            enhanced_prompt = prompt_service.create_character_prompt(state["message"])
            return {
                **state,
                "enhanced_prompt": enhanced_prompt,
            }
        else:
            # Generate edit prompt for Gemini
            logger.info(f"[Node: generate_prompt] Creating edit prompt for: {state['message'][:50]}...")
            edit_prompt = prompt_service.create_edit_prompt(state["message"])
            return {
                **state,
                "edit_prompt": edit_prompt,
            }
            
    except Exception as e:
        logger.error(f"[Node: generate_prompt] Failed: {e}")
        return {**state, "error": str(e)}


def create_image_node(state: ImageGraphState) -> ImageGraphState:
    """
    Node: Generate new image using Amazon Nova Canvas.
    """
    if state.get("error"):
        return state
    
    try:
        logger.info("[Node: create_image] Invoking Nova Canvas...")
        bedrock = get_bedrock_service()
        
        image_bytes = bedrock.invoke_nova_canvas(
            prompt=state["enhanced_prompt"],
            negative_prompt="blurry, distorted, low quality, deformed face"
        )
        
        logger.info(f"[Node: create_image] Generated image: {len(image_bytes)} bytes")
        return {**state, "generated_image_bytes": image_bytes}
        
    except Exception as e:
        logger.error(f"[Node: create_image] Failed: {e}")
        return {**state, "error": str(e)}


def edit_image_node(state: ImageGraphState) -> ImageGraphState:
    """
    Node: Edit existing image using Google Gemini (Nano Banana).
    """
    if state.get("error"):
        return state
    
    try:
        logger.info("[Node: edit_image] Downloading source image...")
        s3_service = get_s3_service()
        source_bytes = s3_service.download_image(state["source_image_url"])
        
        logger.info("[Node: edit_image] Invoking Google Gemini...")
        gemini = get_gemini_service()
        
        edited_bytes = gemini.edit_image(
            image_bytes=source_bytes,
            edit_prompt=state["edit_prompt"],
        )
        
        logger.info(f"[Node: edit_image] Edited image: {len(edited_bytes)} bytes")
        return {**state, "generated_image_bytes": edited_bytes}
        
    except Exception as e:
        logger.error(f"[Node: edit_image] Failed: {e}")
        return {**state, "error": str(e)}


def upload_to_s3_node(state: ImageGraphState) -> ImageGraphState:
    """
    Node: Upload generated/edited image to S3.
    """
    if state.get("error") or not state.get("generated_image_bytes"):
        return state
    
    try:
        logger.info("[Node: upload_to_s3] Uploading to S3...")
        s3_service = get_s3_service()
        
        prefix = "character" if state["action"] == "create" else "edited"
        url = s3_service.upload_image(state["generated_image_bytes"], prefix=prefix)
        
        logger.info(f"[Node: upload_to_s3] Uploaded: {url}")
        return {**state, "result_image_url": url}
        
    except Exception as e:
        logger.error(f"[Node: upload_to_s3] Failed: {e}")
        return {**state, "error": str(e)}


# =============================================================================
# Routing Functions
# =============================================================================

def route_by_action(state: ImageGraphState) -> str:
    """Route to create or edit node based on action type."""
    if state.get("error"):
        return "end"
    return state["action"]


# =============================================================================
# Graph Builder
# =============================================================================

def build_image_graph() -> StateGraph:
    """Build and compile the image generation graph."""
    
    # Create graph with state schema
    graph = StateGraph(ImageGraphState)
    
    # Add nodes
    graph.add_node("generate_prompt", generate_prompt_node)
    graph.add_node("create_image", create_image_node)
    graph.add_node("edit_image", edit_image_node)
    graph.add_node("upload_to_s3", upload_to_s3_node)
    
    # Add edges
    # START -> generate_prompt
    graph.add_edge(START, "generate_prompt")
    
    # generate_prompt -> (create_image | edit_image) based on action
    graph.add_conditional_edges(
        "generate_prompt",
        route_by_action,
        {
            "create": "create_image",
            "edit": "edit_image",
            "end": END,
        }
    )
    
    # create_image -> upload_to_s3
    graph.add_edge("create_image", "upload_to_s3")
    
    # edit_image -> upload_to_s3
    graph.add_edge("edit_image", "upload_to_s3")
    
    # upload_to_s3 -> END
    graph.add_edge("upload_to_s3", END)
    
    return graph.compile()


# =============================================================================
# Graph Singleton
# =============================================================================

_image_graph = None


def get_image_graph():
    """Get or create the compiled image graph."""
    global _image_graph
    if _image_graph is None:
        _image_graph = build_image_graph()
    return _image_graph
