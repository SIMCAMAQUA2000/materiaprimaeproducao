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
# CONFIGURAÇÕES DO ADMINISTRADOR (VOCÊ)
# ==========================================================
EMAIL_REMETENTE = "joseluisblaskowskitavares@gmail.com" 
SENHA_APP = "cjucjngpmckayyko" 
# ==========================================================

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
    msg.set_content("Bem-vindo ao Gestão POA.\n\nPara ativar sua conta, acesse: " + link)
    msg['Subject'] = "Convite de Cadastro - SGP POA"
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Erro de envio:", e)
        return False

@app.post("/api/login")
def login(data: dict, db: Session = Depends(get_db)):
    u = db.query(UserDB).filter(UserDB.username == data['username'], UserDB.password == data['password']).first()
    if not u: raise HTTPException(401, "Acesso negado")
    return {"id": u.id, "role": u.role, "empresa": u.empresa_nome}

@app.post("/api/invite")
def create_invite(req: dict, request: Request, db: Session = Depends(get_db)):
    tk = str(uuid.uuid4())
    db.add(InviteDB(email=req['email'], token=tk, role=req['role']))
    db.commit()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "https")
    link = f"{proto}://{host}/?token={tk}"
    ok = enviar_email_convite(req['email'], link)
    return {"status": "enviado" if ok else "erro", "link": link}

@app.get("/api/recebimentos/{uid}/{role}")
def list_rec(uid: int, role: str, db: Session = Depends(get_db)):
    if role in ['admin', 'fiscal']: return db.query(RecebimentoDB).all()
    return db.query(RecebimentoDB).filter(RecebimentoDB.user_id == uid).all()

@app.get("/", response_class=HTMLResponse)
async def interface():
    return """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>SGP POA v2.8</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body class="bg-slate-950 text-slate-200 font-sans">
        <div id="root">
            <div id="login-screen" class="flex items-center justify-center min-h-screen">
                <div class="bg-slate-900 p-10 rounded-3xl shadow-2xl w-96 border border-slate-800">
                    <h1 class="text-3xl font-black text-emerald-400 text-center mb-8 uppercase italic tracking-tighter">SGP POA</h1>
                    <div class="space-y-4 text-slate-900">
                        <input type="text" id="user" placeholder="Usuário" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <input type="password" id="pass" placeholder="Senha" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <button id="btn-login" class="w-full bg-emerald-500 text-slate-900 py-4 rounded-xl font-bold">ENTRAR</button>
                    </div>
                </div>
            </div>
        </div>
        <script>
            const storageKey = 'poa_prod_v28';
            async function startLogin() {
                const u = document.getElementById('user').value;
                const p = document.getElementById('pass').value;
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                if(r.ok) {
                    const data = await r.json();
                    localStorage.setItem(storageKey, JSON.stringify(data));
                    location.reload();
                } else { alert("Login falhou."); }
            }
            const activeUser = JSON.parse(localStorage.getItem(storageKey));
            if (activeUser) {
                document.getElementById('root').innerHTML = `
                <div class="min-h-screen flex">
                    <aside class="w-64 bg-black p-6 border-r border-slate-900 flex flex-col">
                        <div class="text-emerald-400 font-black text-xl mb-10 italic uppercase text-center tracking-tighter">SGP POA</div>
                        <nav class="flex-1 space-y-2">
                            <button onclick="location.reload()" class="w-full text-left p-4 rounded-xl hover:bg-slate-800 flex items-center transition"><i class="fas fa-home mr-3 text-emerald-500"></i> Dashboard</button>
                            ${activeUser.role === 'admin' ? '<button onclick="openInvites()" class="w-full text-left p-4 rounded-xl bg-blue-900/20 text-blue-300 border border-blue-900/50 flex items-center transition"><i class="fas fa-user-plus mr-3"></i> Convites</button>' : ''}
                        </nav>
                        <button onclick="localStorage.clear(); location.reload();" class="w-full text-left p-4 text-red-500 hover:bg-red-500/10 rounded-xl mt-auto transition"><i class="fas fa-power-off mr-3"></i> Sair</button>
                    </aside>
                    <main class="flex-1 p-12 overflow-y-auto" id="content"></main>
                </div>`;
                loadDashboardData();
            } else {
                const btn = document.getElementById('btn-login');
                if(btn) btn.onclick = startLogin;
            }
            async function loadDashboardData() {
                const r = await fetch('/api/recebimentos/' + activeUser.id + '/' + activeUser.role);
                const data = await r.json();
                document.getElementById('content').innerHTML = `
                    <h1 class="text-3xl font-bold text-white mb-10 uppercase tracking-tight">Painel de Produção</h1>
                    <div class="grid gap-4 italic tracking-tighter">
                        ${data.map(d => `
                        <div class="p-6 bg-slate-900 border-l-4 border-emerald-500 rounded-xl flex justify-between items-center shadow-lg hover:bg-slate-800 transition">
                            <div><p class="font-bold text-white uppercase text-lg tracking-tighter font-sans">${d.materia_prima}</p><p class="text-xs text-slate-500">Lote: ${d.lote_fornecedor}</p></div>
                            <span class="text-2xl font-black text-emerald-400 font-mono">${d.quantidade} kg</span>
                        </div>`).join('') || '<p class="text-slate-600 italic">Nenhum dado registrado.</p>'}
                    </div>`;
            }
            function openInvites() {
                document.getElementById('content').innerHTML = `
                    <h1 class="text-3xl font-bold text-blue-400 mb-10 uppercase tracking-tight">Novo Convite</h1>
                    <div class="bg-slate-900 p-10 rounded-3xl border border-slate-800 max-w-lg space-y-6 shadow-xl">
                        <div class="space-y-4 text-slate-900">
                            <input type="email" id="mail" placeholder="E-mail da Empresa" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                            <select id="role" class="w-full p-4 rounded-xl bg-slate-800 text-white border border-slate-700 font-bold outline-none">
                                <option value="empresa">Empresa (Lançamento)</option>
                                <option value="fiscal">Fiscal (Auditoria)</option>
                            </select>
                        </div>
                        <button onclick="send()" class="w-full bg-blue-600 text-white py-4 rounded-xl font-bold hover:bg-blue-500 shadow-lg transition uppercase tracking-widest">Enviar por E-mail</button>
                    </div>`;
            }
            async function send() {
                const email = document.getElementById('mail').value;
                const role = document.getElementById('role').value;
                if(!email) return alert("Digite o e-mail.");
                alert("O sistema está disparando o e-mail via SMTP...");
                const r = await fetch('/api/invite', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({email, role})
                });
                const res = await r.json();
                if(res.status === "enviado") alert("E-MAIL ENVIADO COM SUCESSO!");
                else alert("Erro ao enviar. Verifique o log no Render.");
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)