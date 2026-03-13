from typing import List, Dict
import uuid as uuid_lib
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
                source_url UNINDEXED,
                tokenize='porter unicode61'
            );
        """)

        # 채팅 로그 테이블
        self.sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT,
                sources TEXT,
                user_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.sqlite_conn.commit()
    
    def index_chunk(self, chunk_id: str, content: str, metadata: Dict):
        """청크 인덱싱 (벡터 + BM25)"""
        embedding = self._get_embedding(content)

        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=str(uuid_lib.UUID(chunk_id)),  # UUID 형식 보장
                    vector=embedding,
                    payload={"content": content, **metadata}
                )
            ]
        )

        self.sqlite_conn.execute("""
            INSERT OR REPLACE INTO documents_fts (id, content, doc_name, section_path, page, has_table, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            chunk_id,
            content,
            metadata.get('doc_name'),
            metadata.get('section_path'),
            metadata.get('page'),
            1 if metadata.get('has_table') else 0,
            metadata.get('source_url', '')
        ))
        self.sqlite_conn.commit()
    def index_chunks_batch(self, chunks: List[Dict]):
        """청크 배치 인덱싱 (벡터 + BM25) - 대량 처리용"""
        if not chunks:
            return

        # 배치 임베딩 생성
        texts = [c['content'] for c in chunks]
        embeddings = self._get_embeddings_batch(texts)

        # Qdrant 배치 저장
        points = []
        for i, chunk in enumerate(chunks):
            points.append(
                PointStruct(
                    id=str(uuid_lib.UUID(chunk['id'])),  # UUID 형식 보장
                    vector=embeddings[i],
                    payload={"content": chunk['content'], **chunk['metadata']}
                )
            )

        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=points
        )

        # SQLite 배치 저장
        rows = []
        for chunk in chunks:
            rows.append((
                chunk['id'],
                chunk['content'],
                chunk['metadata'].get('doc_name'),
                chunk['metadata'].get('section_path'),
                chunk['metadata'].get('page'),
                1 if chunk['metadata'].get('has_table') else 0,
                chunk['metadata'].get('source_url', '')
            ))

        self.sqlite_conn.executemany("""
            INSERT OR REPLACE INTO documents_fts (id, content, doc_name, section_path, page, has_table, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, rows)
        self.sqlite_conn.commit()

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """배치 임베딩 생성 (한 번에 최대 100개)"""
        embeddings = []
        for text in texts:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text
            )
            embeddings.append(result['embedding'])
        return embeddings
    
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
        # FTS5 특수문자 이스케이프: 알파벳/숫자/한글/공백만 남기고 제거
        import re
        safe_query = re.sub(r'[^\w\s가-힣]', ' ', query).strip()
        if not safe_query:
            return []

        try:
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
            """, (safe_query, top_k))
        except Exception:
            return []
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'score': abs(row[6]),
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
    
    def delete_by_doc_name(self, doc_name: str) -> int:
        """특정 문서의 모든 청크 삭제 (Qdrant + SQLite)"""
        # SQLite에서 해당 문서의 chunk id 목록 조회
        cursor = self.sqlite_conn.execute(
            "SELECT id FROM documents_fts WHERE doc_name = ?", (doc_name,)
        )
        ids = [row[0] for row in cursor.fetchall()]

        if not ids:
            return 0

        # Qdrant에서 삭제
        try:
            from qdrant_client.models import PointIdsList
            self.qdrant.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[str(uuid_lib.UUID(i)) for i in ids])
            )
        except Exception as e:
            print(f"Qdrant 삭제 오류: {e}")

        # SQLite에서 삭제
        self.sqlite_conn.execute(
            "DELETE FROM documents_fts WHERE doc_name = ?", (doc_name,)
        )
        self.sqlite_conn.commit()

        return len(ids)

    def get_indexed_sources(self) -> list:
        """인덱싱된 source_url 목록 (공지 중복 체크용)"""
        cursor = self.sqlite_conn.execute(
            "SELECT DISTINCT source_url FROM documents_fts WHERE source_url IS NOT NULL"
        )
        return [row[0] for row in cursor.fetchall() if row[0]]

    def get_doc_names(self) -> list:
        """인덱싱된 문서명 목록 조회"""
        cursor = self.sqlite_conn.execute(
            "SELECT DISTINCT doc_name, COUNT(*) as chunk_count FROM documents_fts GROUP BY doc_name"
        )
        return [{"doc_name": row[0], "chunk_count": row[1]} for row in cursor.fetchall()]

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
    def save_chat_log(self, question: str, answer: str, sources: list, user_email: str = ""):
        """채팅 로그 저장"""
        import json
        self.sqlite_conn.execute(
            "INSERT INTO chat_logs (question, answer, sources, user_email) VALUES (?, ?, ?, ?)",
            (question, answer, json.dumps(sources, ensure_ascii=False), user_email)
        )
        self.sqlite_conn.commit()

    def get_frequent_questions(self, limit: int = 10) -> list:
        """자주 묻는 질문 조회 (최근 30일, 유사 질문 그룹핑은 LLM에서 처리)"""
        cursor = self.sqlite_conn.execute("""
            SELECT question, answer, sources, COUNT(*) as cnt
            FROM chat_logs
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY question
            ORDER BY cnt DESC
            LIMIT ?
        """, (limit * 3,))  # LLM 그룹핑용으로 넉넉히
        return [{"question": r[0], "answer": r[1], "sources": r[2], "count": r[3]} for r in cursor.fetchall()]
    def get_stats(self) -> dict:
        """이용통계 데이터 조회"""
        stats = {}

        # 총 질문 수
        r = self.sqlite_conn.execute("SELECT COUNT(*) FROM chat_logs").fetchone()
        stats["total_questions"] = r[0] if r else 0

        # 오늘 질문 수
        r = self.sqlite_conn.execute(
            "SELECT COUNT(*) FROM chat_logs WHERE date(created_at) = date('now')"
        ).fetchone()
        stats["today_questions"] = r[0] if r else 0

        # 최근 7일 일별 질문 수
        cursor = self.sqlite_conn.execute("""
            SELECT date(created_at) as d, COUNT(*) as cnt
            FROM chat_logs
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY d ORDER BY d
        """)
        stats["daily_7d"] = [{"date": r[0], "count": r[1]} for r in cursor.fetchall()]

        # 최근 30일 주별 질문 수
        cursor = self.sqlite_conn.execute("""
            SELECT strftime('%W', created_at) as week, COUNT(*) as cnt
            FROM chat_logs
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY week ORDER BY week
        """)
        stats["weekly_30d"] = [{"week": r[0], "count": r[1]} for r in cursor.fetchall()]

        # 시간대별 질문 분포 (0~23시)
        cursor = self.sqlite_conn.execute("""
            SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour, COUNT(*) as cnt
            FROM chat_logs
            GROUP BY hour ORDER BY hour
        """)
        hour_data = {r[0]: r[1] for r in cursor.fetchall()}
        stats["hourly"] = [{"hour": h, "count": hour_data.get(h, 0)} for h in range(24)]

        # 인덱싱된 문서 수 / 총 청크 수
        r = self.sqlite_conn.execute(
            "SELECT COUNT(DISTINCT doc_name), COUNT(*) FROM documents_fts"
        ).fetchone()
        stats["total_docs"] = r[0] if r else 0
        stats["total_chunks"] = r[1] if r else 0

        # 최근 30일 가장 많이 참조된 문서 TOP 10
        import json as _json
        cursor = self.sqlite_conn.execute(
            "SELECT sources FROM chat_logs WHERE created_at >= datetime('now', '-30 days') AND sources IS NOT NULL"
        )
        doc_counts = {}
        for row in cursor.fetchall():
            try:
                sources = _json.loads(row[0]) if isinstance(row[0], str) else row[0]
                for s in sources:
                    name = s.get("uri") or s.get("doc_name") or ""
                    if name:
                        doc_counts[name] = doc_counts.get(name, 0) + 1
            except Exception:
                pass
        sorted_docs = sorted(doc_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        stats["docs_top10"] = [{"doc_name": d[0], "count": d[1]} for d in sorted_docs]

        return stats




