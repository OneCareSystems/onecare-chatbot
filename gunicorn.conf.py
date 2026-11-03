def post_worker_init(worker):
    """Load the embedding model before handling chatbot requests."""
    from knowledgebase.embedding import preload_embedder

    worker.log.info("Preloading OneCare embedding model...")

    preload_embedder()

    worker.log.info("OneCare embedding model is ready.")