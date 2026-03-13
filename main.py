from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uuid
import os
import asyncio
import threading
from pathlib import Path
from datetime import datetime

from config import settings
from search.free_hybrid_search import FreeHybridSearch
from generation.generator import AnswerGenerator
from preprocessing.pdf_parser import PDFToMarkdown
from preprocessing.html_parser import HTMLToMarkdown
from preprocessing.chunker import SemanticChunker
from auth import verify_token, verify_admin, create_token, verify_google_token

app = FastAPI(title="KDD RAG System")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="."), name="static")

# 전역 객체
search_engine = FreeHybridSearch()
generator = AnswerGenerator()
chunker = SemanticChunker(
    chunk_size=settings.chunk_size,
    overlap=settings.chunk_overlap
)

# 업로드 디렉토리
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# 요청/응답 모델
class ChatRequest(BaseModel):
    message: str
    history: Optional[str] = ""

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]

class AuthRequest(BaseModel):
    credential: str

class AuthResponse(BaseModel):
    token: str
    user: dict

@app.on_event("startup")
async def startup():
    """서버 시작 시 초기화"""
    search_engine.init_collections()
    print("✅ Qdrant + SQLite FTS5 초기화 완료")

    # 백그라운드 스케줄러 시작 (매일 새벽 3시 공지 크롤링)
    def scheduler():
        import time
        while True:
            now = datetime.now()
            # 다음 새벽 3시까지 대기
            next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if next_run <= now:
                from datetime import timedelta
                next_run += timedelta(days=1)
            wait_sec = (next_run - now).total_seconds()
            print(f"⏰ 다음 공지 크롤링: {next_run.strftime('%Y-%m-%d %H:%M')} ({wait_sec/3600:.1f}시간 후)")
            time.sleep(wait_sec)
            try:
                print("🔄 공지사항 자동 크롤링 시작...")
                asyncio.run(run_crawl())
            except Exception as e:
                print(f"❌ 크롤링 실패: {e}")

    async def run_crawl():
        from scripts.crawl_and_index import crawl_and_index
        await crawl_and_index(search_engine)

    t = threading.Thread(target=scheduler, daemon=True)
    t.start()

@app.post("/auth/google", response_model=AuthResponse)
async def google_login(req: AuthRequest):
    """Google OAuth 로그인"""
    # 테스트용 임시 우회
    user_info = {
        "email": "22615jin@kookmin.ac.kr",
        "name": "테스트 사용자"
    }
    
    # JWT 토큰 생성
    token = create_token(user_info)
    
    # 관리자 여부 확인
    admin_emails = [e.strip() for e in settings.doc_admin_emails.split(",")]
    is_admin = user_info["email"] in admin_emails
    
    return {
        "token": token,
        "user": {
            "email": user_info["email"],
            "name": user_info["name"],
            "isDocAdmin": is_admin
        }
    }

@app.get("/auth/me")
async def get_me(user: dict = Depends(verify_token)):
    """현재 사용자 정보"""
    admin_emails = [e.strip() for e in settings.doc_admin_emails.split(",")]
    is_admin = user.get("email") in admin_emails
    
    return {
        "user": {
            **user,
            "isDocAdmin": is_admin
        }
    }

@app.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest, authorization: str = Header(None)):
    """채팅 엔드포인트"""
    try:
        # 테스트용: 토큰 검증 우회
        if not authorization or not authorization.startswith("Bearer "):
            # 토큰 없으면 테스트 사용자로 자동 로그인
            pass
        
        # 검색
        contexts = search_engine.search(
            query=req.message,
            top_k=settings.final_context_size
        )
        
        if not contexts:
            return {
                "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다.",
                "sources": []
            }
        
        # 답변 생성
        result = generator.generate(
            query=req.message,
            contexts=contexts,
            history=req.history
        )
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(verify_admin)
):
    """문서 업로드 및 인덱싱"""
    try:
        # 파일 저장
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 파일 타입에 따라 파싱
        if file.filename.endswith('.pdf'):
            parser = PDFToMarkdown()
            chunks = parser.parse(str(file_path), file.filename)
        elif file.filename.endswith('.html'):
            parser = HTMLToMarkdown()
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            chunks = parser.parse(html_content, file.filename)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # 청킹
        all_chunks = []
        for chunk in chunks:
            sub_chunks = chunker.chunk(chunk['content'], chunk['metadata'])
            all_chunks.extend(sub_chunks)
        
        # 인덱싱
        for chunk in all_chunks:
            chunk_id = str(uuid.uuid4())
            search_engine.index_chunk(
                chunk_id=chunk_id,
                content=chunk['content'],
                metadata=chunk['metadata']
            )
        
        return {
            "message": f"Successfully indexed {len(all_chunks)} chunks",
            "filename": file.filename,
            "chunks": len(all_chunks)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset")
async def reset_index(user: dict = Depends(verify_admin)):
    """인덱스 초기화"""
    try:
        search_engine.delete_all()
        return {"message": "Index reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/crawl/notices")
async def trigger_crawl(user: dict = Depends(verify_admin)):
    """공지사항 수동 크롤링 트리거 (관리자 전용)"""
    async def run():
        from scripts.crawl_and_index import crawl_and_index
        await crawl_and_index(search_engine)
    asyncio.create_task(run())
    return {"message": "공지사항 크롤링 시작됨 (백그라운드 실행)"}

@app.get("/documents")
async def list_documents(authorization: str = Header(None)):
    """업로드된 문서 목록 + 인덱싱 청크 수"""
    try:
        # 인덱싱된 문서 정보 (청크 수 포함)
        indexed = {d["doc_name"]: d["chunk_count"] for d in search_engine.get_doc_names()}

        files = []
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                files.append({
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "type": f.suffix,
                    "chunk_count": indexed.get(f.name, 0),
                    "indexed": f.name in indexed
                })
        return {"documents": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{filename}")
async def delete_document(filename: str, user: dict = Depends(verify_admin)):
    """문서 삭제 (파일 + Qdrant + SQLite 모두 삭제)"""
    try:
        # 인덱스에서 삭제
        deleted_chunks = search_engine.delete_by_doc_name(filename)

        # 파일 삭제
        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            file_path.unlink()

        return {
            "message": f"{filename} 삭제 완료",
            "deleted_chunks": deleted_chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{filename}/preview")
async def preview_document(filename: str, authorization: str = Header(None)):
    """문서 파일 다운로드/미리보기"""
    from fastapi.responses import FileResponse
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
