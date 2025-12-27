# Graph module
# Import lazily to avoid circular imports

__all__ = [
    "ImageGraphState",
    "build_image_graph",
    "get_image_graph",
]


def get_image_graph():
    """Get the compiled image graph."""
    from .image_graph import get_image_graph as _get_image_graph
    return _get_image_graph()


def build_image_graph():
    """Build and compile the image graph."""
    from .image_graph import build_image_graph as _build_image_graph
    return _build_image_graph()
