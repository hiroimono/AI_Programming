"""RAG Service — central microservice for retrieval-augmented generation.

Used by Level-2-App (writing assistant), Level-3-App (chatbot SaaS),
and future apps. Owns all document parsing, embedding, and semantic
search; the consuming apps stay thin.

Architecture details:
    Documents/Strategy Documents/4.2 RAG Microservice Architecture and Schema-per-App
    Approach (EN).md
"""
