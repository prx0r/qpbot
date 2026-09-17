"""Agent memory bank — experience carried run to run.

Experience is plain markdown files. The harness transports them, the model
authors them. Retrieval is deliberately dumb: the loop injects the bank (or
its inventory) and the model reads what it wants. No embeddings, no rerank.
"""
from .bank import MemoryBank

__all__ = ["MemoryBank"]
