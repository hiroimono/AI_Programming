"""chatbot-service: Level-3 embeddable AI chatbot backend.

Standalone B2B2C multi-tenant service:
  - Our customers (companies) = tenants; each manages one or more Bots.
  - A Bot's widget is embedded on the customer's website and used by
    anonymous end-users.

Owns its own database (tenant/bot/documents/conversations) and its own
RAG pipeline (adapted from RAG-Service patterns, behind Embedder/Retriever
Protocol seams so it can later delegate to the shared RAG-Service).
"""
