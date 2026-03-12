from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    cohere_api_key: str
    google_client_id: str
    
    # Qdrant Cloud (무료 1GB)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    
    # 앱 설정
    allowed_domain: str = "kookmin.ac.kr"
    doc_admin_emails: str = ""
    jwt_secret: str
    
    # 청킹 설정
    chunk_size: int = 550
    chunk_overlap: int = 100
    
    # 검색 설정
    bm25_top_k: int = 20
    vector_top_k: int = 20
    rerank_top_k: int = 6
    final_context_size: int = 5
    
    class Config:
        env_file = ".env"

settings = Settings()
