from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import google.generativeai as genai
import cohere
import sqlite3
from pathlib import Path
from config import settings

class FreeHybridSearch:
    """Qdrant Cloud (무료) + SQLite FTS5 (무료) 하이브리드 검색"""
    
    def __init__(self):
        # Qdrant Cloud 연결
        self.qdrant = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
        )
        
        # SQLite FTS5 (BM25 검색용)
        db_path = Path("data/fts.db")
        db_path.parent.mkdir(exist_ok=True)
        self.sqlite_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        
        # Cohere 클라이언트
        self.cohere_client = cohere.Client(settings.cohere_api_key)
        
        # Gemini 클라이언트 (임베딩용)
        genai.configure(api_key=settings.gemini_api_key)
        
        self.collection_name = "documents"
    
    def init_collections(self):
        """컬렉션 초기화"""
        # Qdrant 컬렉션 생성 (HNSW 설정)
        try:
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=3072,  # Gemini embedding-001 차원
                    distance=Distance.COSINE,
                    hnsw_config={
                        "m": 32,
                        "ef_construct": 200
                    }
                )
            )
        except Exception as e:
            print(f"Qdrant 컬렉션 이미 존재: {e}")
        
        # SQLite FTS5 테이블 생성
        self.sqlite_conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts 
            USING fts5(
                id UNINDEXED,
                content,
                doc_name UNINDEXED,
                section_path UNINDEXED,
                page UNINDEXED,
                has_table UNINDEXED,
                tokenize='porter unicode61'
            );
        """)
        self.sqlite_conn.commit()
    
    def index_chunk(self, chunk_id: str, content: str, metadata: Dict):
        """청크 인덱싱 (벡터 + BM25)"""
        # 벡터 임베딩 생성
        embedding = self._get_embedding(content)
        
        # Qdrant에 저장
        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload={
                        "content": content,
                        **metadata
                    }
                )
            ]
        )
        
        # SQLite FTS5에 저장
        self.sqlite_conn.execute("""
            INSERT OR REPLACE INTO documents_fts (id, content, doc_name, section_path, page, has_table)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            chunk_id,
            content,
            metadata.get('doc_name'),
            metadata.get('section_path'),
            metadata.get('page'),
            1 if metadata.get('has_table') else 0
        ))
        self.sqlite_conn.commit()
    
    def search(self, query: str, top_k: int = 6) -> List[Dict]:
        """하이브리드 검색 + 리랭킹"""
        # 1단계: BM25 검색 (SQLite FTS5)
        bm25_results = self._bm25_search(query, settings.bm25_top_k)
        
        # 1단계: 벡터 검색 (Qdrant HNSW)
        vector_results = self._vector_search(query, settings.vector_top_k)
        
        # 2단계: RRF로 결합
        combined = self._rrf_combine(bm25_results, vector_results)
        
        # 3단계: Rerank
        reranked = self._rerank(query, combined, top_k)
        
        return reranked
    
    def _get_embedding(self, text: str) -> List[float]:
        """Gemini 임베딩 생성"""
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text
        )
        return result['embedding']
    
    def _bm25_search(self, query: str, top_k: int) -> List[Dict]:
        """BM25 검색 (SQLite FTS5)"""
        cursor = self.sqlite_conn.execute("""
            SELECT 
                id,
                content,
                doc_name,
                section_path,
                page,
                has_table,
                bm25(documents_fts) as score
            FROM documents_fts
            WHERE documents_fts MATCH ?
            ORDER BY score
            LIMIT ?;
        """, (query, top_k))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'score': abs(row[6]),  # BM25 점수는 음수
                'content': row[1],
                'metadata': {
                    'doc_name': row[2],
                    'section_path': row[3],
                    'page': row[4],
                    'has_table': bool(row[5])
                }
            })
        
        return results
    
    def _vector_search(self, query: str, top_k: int) -> List[Dict]:
        """벡터 검색 (Qdrant HNSW)"""
        query_vector = self._get_embedding(query)
        
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            search_params={"hnsw_ef": 128}  # 검색 시 정확도 설정
        )
        
        return [
            {
                'id': str(result.id),
                'score': result.score,
                'content': result.payload['content'],
                'metadata': {k: v for k, v in result.payload.items() if k != 'content'}
            }
            for result in results
        ]
    
    def _rrf_combine(self, bm25_results: List[Dict], vector_results: List[Dict], k: int = 60) -> List[Dict]:
        """Reciprocal Rank Fusion으로 결과 결합"""
        scores = {}
        contents = {}
        metadata = {}
        
        # BM25 결과 처리
        for rank, result in enumerate(bm25_results, 1):
            doc_id = result['id']
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
            contents[doc_id] = result['content']
            metadata[doc_id] = result['metadata']
        
        # 벡터 결과 처리
        for rank, result in enumerate(vector_results, 1):
            doc_id = result['id']
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
            contents[doc_id] = result['content']
            metadata[doc_id] = result['metadata']
        
        # 점수 순 정렬
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {
                'id': doc_id,
                'score': score,
                'content': contents[doc_id],
                'metadata': metadata[doc_id]
            }
            for doc_id, score in sorted_docs[:40]  # top 40만
        ]
    
    def _rerank(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        """Cohere Rerank로 최종 정렬"""
        if not candidates:
            return []
        
        # Cohere Rerank API 호출
        docs = [c['content'] for c in candidates]
        
        rerank_response = self.cohere_client.rerank(
            model="rerank-multilingual-v3.0",
            query=query,
            documents=docs,
            top_n=top_k
        )
        
        # 결과 재구성
        reranked = []
        for result in rerank_response.results:
            idx = result.index
            reranked.append({
                **candidates[idx],
                'rerank_score': result.relevance_score
            })
        
        return reranked
    
    def delete_all(self):
        """모든 데이터 삭제"""
        try:
            self.qdrant.delete_collection(self.collection_name)
        except:
            pass
        
        self.sqlite_conn.execute("DROP TABLE IF EXISTS documents_fts;")
        self.sqlite_conn.commit()
        
        self.init_collections()
    
    def close(self):
        """연결 종료"""
        self.sqlite_conn.close()
