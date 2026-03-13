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
from jose import jwt

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
    # 실제 Google 토큰 검증
    user_info = verify_google_token(req.credential)
    if not user_info or not user_info.get("email"):
        raise HTTPException(status_code=401, detail="Google 인증 실패")
    
    # JWT 토큰 생성
    token = create_token(user_info)
    
    # 관리자 여부 확인
    admin_emails = [e.strip() for e in settings.doc_admin_emails.split(",")]
    is_admin = user_info["email"] in admin_emails

    # 프로필 자동 생성 (최초 로그인 시)
    try:
        existing = search_engine.get_user_profile(user_info["email"])
        if not existing:
            search_engine.save_user_profile(
                email=user_info["email"],
                name=user_info.get("name", ""),
                student_id="",
                department="",
                grade=""
            )
    except Exception:
        pass
    
    return {
        "token": token,
        "user": {
            "email": user_info["email"],
            "name": user_info.get("name", ""),
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
        if not authorization or not authorization.startswith("Bearer "):
            pass
        
        # 사용자 프로필 조회 (컨텍스트용)
        user_context = ""
        user_email = ""
        try:
            if authorization and authorization.startswith("Bearer "):
                token = authorization.replace("Bearer ", "")
                payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
                user_email = payload.get("email", "")
        except Exception:
            pass

        if user_email:
            try:
                profile = search_engine.get_user_profile(user_email)
                if profile and (profile.get("department") or profile.get("grade")):
                    parts = []
                    if profile.get("department"): parts.append(f"학과: {profile['department']}")
                    if profile.get("grade"): parts.append(f"학년: {profile['grade']}")
                    if profile.get("student_id"): parts.append(f"학번: {profile['student_id']}")
                    user_context = "[사용자 정보] " + ", ".join(parts)
            except Exception:
                pass

        # 검색
        contexts = search_engine.search(
            query=req.message,
            top_k=settings.final_context_size
        )
        
        if not contexts:
            # 채팅 로그 저장 (검색 실패도 기록)
            try:
                search_engine.save_chat_log(
                    question=req.message,
                    answer="관련된 정보를 찾을 수 없습니다.",
                    sources=[]
                )
            except Exception:
                pass
            return {
                "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다. 질문을 다르게 표현해보시거나, 더 구체적으로 질문해주세요.",
                "sources": []
            }
        
        # 답변 생성 (사용자 컨텍스트 포함)
        history_with_profile = req.history or ""
        if user_context:
            history_with_profile = user_context + "\n" + history_with_profile

        result = generator.generate(
            query=req.message,
            contexts=contexts,
            history=history_with_profile
        )
        
        # 채팅 로그 저장
        try:
            search_engine.save_chat_log(
                question=req.message,
                answer=result.get("answer", ""),
                sources=result.get("sources", [])
            )
        except Exception:
            pass
        
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
    """공지사항 수동 크롤링 트리거 - SSE 실시간 로그"""
    from fastapi.responses import StreamingResponse
    import json as _json

    async def event_stream():
        from scripts.crawl_and_index import crawl_and_index
        log_queue = asyncio.Queue()

        async def log_callback(msg: str):
            await log_queue.put(msg)

        async def run():
            try:
                await crawl_and_index(search_engine, log_callback=log_callback)
            except Exception as e:
                await log_queue.put(f"❌ 오류: {e}")
            finally:
                await log_queue.put("__DONE__")

        asyncio.create_task(run())

        while True:
            msg = await log_queue.get()
            if msg == "__DONE__":
                yield f"data: {_json.dumps({'done': True, 'log': '✅ 크롤링 완료'}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {_json.dumps({'done': False, 'log': msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/crawl/notices/list")
async def get_notice_docs(authorization: str = Header(None)):
    """인덱싱된 공지사항 문서 목록"""
    try:
        cursor = search_engine.sqlite_conn.execute("""
            SELECT doc_name, COUNT(*) as chunk_count, source_url
            FROM documents_fts
            WHERE doc_name LIKE '[공지]%' OR doc_name LIKE '[공지첨부]%'
            GROUP BY doc_name
            ORDER BY rowid DESC
        """)
        notices = []
        for r in cursor.fetchall():
            notices.append({
                "doc_name": r[0],
                "chunk_count": r[1],
                "source_url": r[2] or ""
            })
        return {"notices": notices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/profile")
async def get_profile(authorization: str = Header(None)):
    """사용자 프로필 조회"""
    try:
        email = _get_email(authorization)
        profile = search_engine.get_user_profile(email)
        return {"profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/profile")
async def save_profile(data: dict, authorization: str = Header(None)):
    """사용자 프로필 저장"""
    try:
        email = _get_email(authorization)
        search_engine.save_user_profile(
            email=email,
            name=data.get("name", ""),
            student_id=data.get("student_id", ""),
            department=data.get("department", ""),
            grade=data.get("grade", "")
        )
        return {"message": "프로필 저장 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _get_email(authorization: str) -> str:
    """Authorization 헤더에서 이메일 추출"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            return payload.get("email", "")
        except Exception:
            pass
    return ""

@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "ok"}

@app.get("/stats")
async def get_stats(authorization: str = Header(None)):
    """이용통계 데이터"""
    try:
        return search_engine.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/faq")
async def get_faq():
    """자주 묻는 질문 (최근 30일 기준, Gemini로 그룹핑)"""
    import json
    try:
        raw = search_engine.get_frequent_questions(limit=10)
        if not raw:
            return {"faqs": []}

        # Gemini로 유사 질문 그룹핑 + 대표 질문 선정
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        lines = "\n".join(f"{i+1}. ({r['count']}회) {r['question']}" for i, r in enumerate(raw))
        prompt = f"""아래는 대학교 학칙 질의응답 시스템에서 최근 30일간 들어온 질문 목록이야.
유사한 질문끼리 그룹핑해서 대표 FAQ를 최대 8개 만들어줘.

규칙:
- 대표 질문은 자연스럽고 간결하게 다듬어줘
- 카테고리를 붙여줘 (졸업, 수강신청, 장학금, 학적, 기타 등)
- 원본 번호를 포함해줘

아래 JSON 배열 형식으로만 답해줘:
[{{"question": "대표 질문", "category": "카테고리", "original_indices": [1,3,5]}}]

질문 목록:
{lines}"""

        resp = model.generate_content(prompt)
        text = resp.text.strip()
        # JSON 추출
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        groups = json.loads(text)

        # 각 그룹에 대해 가장 좋은 답변 매칭
        faqs = []
        for g in groups[:8]:
            indices = g.get("original_indices", [])
            # 가장 많이 물어본 원본의 답변 사용
            best = None
            for idx in indices:
                if 1 <= idx <= len(raw):
                    candidate = raw[idx - 1]
                    if best is None or candidate["count"] > best["count"]:
                        best = candidate
            if best:
                sources = json.loads(best["sources"]) if isinstance(best["sources"], str) else best["sources"]
                faqs.append({
                    "question": g["question"],
                    "category": g.get("category", "기타"),
                    "answer": best["answer"],
                    "sources": sources,
                    "count": sum(raw[i-1]["count"] for i in indices if 1 <= i <= len(raw))
                })

        faqs.sort(key=lambda x: x["count"], reverse=True)
        return {"faqs": faqs}

    except Exception as e:
        # LLM 실패 시 단순 빈도 기반 폴백
        import json
        faqs = []
        for r in raw[:8]:
            sources = json.loads(r["sources"]) if isinstance(r["sources"], str) else r["sources"]
            faqs.append({
                "question": r["question"],
                "category": "기타",
                "answer": r["answer"],
                "sources": sources,
                "count": r["count"]
            })
        return {"faqs": faqs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
