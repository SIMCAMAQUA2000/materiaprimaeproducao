import uuid
import smtplib
import os
from email.message import EmailMessage
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, relationship, DeclarativeBase
from datetime import datetime

# ==========================================================
# CONFIGURAÇÕES DE PRODUÇÃO
# ==========================================================
EMAIL_REMETENTE = "joseluisblaskowskitavares@gmail.com" 
SENHA_APP = "cjucjngpmckayyko" # Sua senha de app validada
# ==========================================================

# O Render usa caminhos absolutos. Ajustado para persistência básica.
SQLALCHEMY_DATABASE_URL = "sqlite:///./gestao_poa_prod.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase): pass

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String)
    empresa_nome = Column(String)
    email = Column(String, unique=True)

class InviteDB(Base):
    __tablename__ = "invites"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    token = Column(String, unique=True)
    role = Column(String)
    usado = Column(Integer, default=0)

class RecebimentoDB(Base):
    __tablename__ = "recebimentos"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    materia_prima = Column(String)
    quantidade = Column(Float)
    lote_fornecedor = Column(String)
    data_registro = Column(DateTime, default=datetime.utcnow)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(UserDB).filter(UserDB.username == "admin").first():
            db.add(UserDB(username="admin", password="123", role="admin", empresa_nome="Órgão Central", email=EMAIL_REMETENTE))
            db.commit()
    finally: db.close()
    yield

app = FastAPI(lifespan=lifespan)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def enviar_email_convite(destinatario, link):
    msg = EmailMessage()
    msg.set_content("Bem-vindo ao SGP POA.\n\nAtive sua conta aqui: " + link)
    msg['Subject'] = "Convite de Cadastro"
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Erro SMTP:", e)
        return False

@app.post("/api/login")
def login(data: dict, db: Session = Depends(get_db)):
    u = db.query(UserDB).filter(UserDB.username == data['username'], UserDB.password == data['password']).first()
    if not u: raise HTTPException(401)
    return {"id": u.id, "role": u.role, "empresa": u.empresa_nome}

@app.post("/api/invite")
def create_invite(req: dict, request: Request, db: Session = Depends(get_db)):
    tk = str(uuid.uuid4())
    db.add(InviteDB(email=req['email'], token=tk, role=req['role']))
    db.commit()
    # Detecção automática de URL para funcionar em qualquer domínio (Render, Codespace ou Local)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "http")
    link = f"{proto}://{host}/?token={tk}"
    ok = enviar_email_convite(req['email'], link)
    return {"status": "enviado" if ok else "erro", "link": link}

@app.get("/api/recebimentos/{uid}/{role}")
def list_rec(uid: int, role: str, db: Session = Depends(get_db)):
    if role in ['admin', 'fiscal']: return db.query(RecebimentoDB).all()
    return db.query(RecebimentoDB).filter(RecebimentoDB.user_id == uid).all()

@app.get("/", response_class=HTMLResponse)
async def interface():
    # O HTML permanece o mesmo da v2.7, pois já é funcional.
    # (Removido aqui por brevidade, mas deve ser mantido completo no seu arquivo)
    return """... (cole o HTML da versão 2.7 aqui) ..."""

if __name__ == "__main__":
    import uvicorn
    # Em produção, a porta é definida pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)