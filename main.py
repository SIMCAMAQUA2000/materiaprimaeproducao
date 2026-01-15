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
# CONFIGURAÇÕES DE PRODUÇÃO (Render + Gmail)
# ==========================================================
EMAIL_REMETENTE = "joseluisblaskowskitavares@gmail.com" 
SENHA_APP = "cjucjngpmckayyko" # Senha de app validada conforme image_98dc88.png
# ==========================================================

# Banco de dados persistente no diretório do Render
SQLALCHEMY_DATABASE_URL = "sqlite:///./gestao_poa_v3.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase): pass

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String) # 'admin', 'empresa', 'fiscal'
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
            db.add(UserDB(username="admin", password="123", role="admin", empresa_nome="Órgão Fiscalizador", email=EMAIL_REMETENTE))
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
    msg.set_content(f"Bem-vindo ao SGP POA.\n\nPara ativar sua conta e acessar o sistema, clique no link abaixo:\n\n{link}")
    msg['Subject'] = "Convite de Cadastro - SGP POA"
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Erro SMTP: {e}")
        return False

# --- API ENDPOINTS ---

@app.post("/api/login")
def login(data: dict, db: Session = Depends(get_db)):
    u = db.query(UserDB).filter(UserDB.username == data['username'], UserDB.password == data['password']).first()
    if not u: raise HTTPException(401, "Credenciais inválidas")
    return {"id": u.id, "role": u.role, "empresa": u.empresa_nome}

@app.post("/api/invite")
def create_invite(req: dict, request: Request, db: Session = Depends(get_db)):
    tk = str(uuid.uuid4())
    db.add(InviteDB(email=req['email'], token=tk, role=req['role']))
    db.commit()
    
    # Detecta automaticamente a URL pública (Render ou GitHub)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "https")
    link = f"{proto}://{host}/?token={tk}"
    
    ok = enviar_email_convite(req['email'], link)
    return {"status": "enviado" if ok else "erro", "link": link}

@app.post("/api/register")
def register(data: dict, db: Session = Depends(get_db)):
    inv = db.query(InviteDB).filter(InviteDB.token == data['token'], InviteDB.usado == 0).first()
    if not inv: raise HTTPException(400, "Token inválido ou já usado")
    db.add(UserDB(username=data['username'], password=data['password'], role=inv.role, empresa_nome=data['empresa_nome'], email=inv.email))
    inv.usado = 1
    db.commit()
    return {"ok": True}

@app.get("/api/recebimentos/{uid}/{role}")
def list_rec(uid: int, role: str, db: Session = Depends(get_db)):
    if role in ['admin', 'fiscal']: return db.query(RecebimentoDB).all()
    return db.query(RecebimentoDB).filter(RecebimentoDB.user_id == uid).all()

@app.post("/api/recebimento")
def add_rec(data: dict, db: Session = Depends(get_db)):
    db.add(RecebimentoDB(user_id=data['uid'], materia_prima=data['mp'], quantidade=data['qtd'], lote_fornecedor=data['lote']))
    db.commit()
    return {"ok": True}

# --- INTERFACE VISUAL (SPA) ---

@app.get("/", response_class=HTMLResponse)
async def interface():
    return """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>SGP POA v3.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body class="bg-slate-950 text-slate-200 font-sans">
        <div id="main-root">
            <div id="scr-login" class="flex items-center justify-center min-h-screen">
                <div class="bg-slate-900 p-10 rounded-3xl shadow-2xl w-96 border border-slate-800">
                    <h1 class="text-3xl font-black text-emerald-400 text-center mb-8 italic uppercase tracking-tighter">SGP POA</h1>
                    <div class="space-y-4">
                        <input type="text" id="l-u" placeholder="Usuário" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <input type="password" id="l-p" placeholder="Senha" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <button onclick="doLogin()" class="w-full bg-emerald-500 text-slate-900 py-4 rounded-xl font-bold hover:bg-emerald-400 transition uppercase">Entrar</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let user = JSON.parse(localStorage.getItem('poa_v3_session'));
            const urlToken = new URLSearchParams(window.location.search).get('token');

            if (urlToken) { renderRegisterPage(urlToken); }
            else if (user) { renderApp(); }

            async function doLogin() {
                const username = document.getElementById('l-u').value;
                const password = document.getElementById('l-p').value;
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });
                if(r.ok) {
                    user = await r.json();
                    localStorage.setItem('poa_v3_session', JSON.stringify(user));
                    renderApp();
                } else { alert("Acesso negado. Verifique os dados."); }
            }

            function renderApp() {
                document.getElementById('main-root').innerHTML = `
                <div class="min-h-screen flex">
                    <aside class="w-64 bg-black p-6 border-r border-slate-900 flex flex-col">
                        <div class="text-emerald-400 font-black text-xl mb-10 italic uppercase text-center tracking-tighter">SGP POA</div>
                        <nav class="flex-1 space-y-2">
                            <button onclick="renderDash()" class="w-full text-left p-4 rounded-xl hover:bg-slate-800 flex items-center transition"><i class="fas fa-home mr-3 text-emerald-500"></i> Dashboard</button>
                            ${user.role === 'admin' ? '<button onclick="renderInviteForm()" class="w-full text-left p-4 rounded-xl bg-blue-900/20 text-blue-400 flex items-center border border-blue-900/50 transition"><i class="fas fa-user-plus mr-3"></i> Convites</button>' : ''}
                            ${user.role === 'empresa' ? '<button onclick="renderEntryForm()" class="w-full text-left p-4 rounded-xl hover:bg-slate-800 flex items-center transition"><i class="fas fa-plus mr-3"></i> Novo Lote</button>' : ''}
                        </nav>
                        <button onclick="logout()" class="w-full text-left p-4 text-red-500 hover:bg-red-500/10 rounded-xl mt-auto transition"><i class="fas fa-power-off mr-3"></i> Sair</button>
                    </aside>
                    <main class="flex-1 p-12 overflow-y-auto" id="app-content"></main>
                </div>`;
                renderDash();
            }

            async function renderDash() {
                const r = await fetch('/api/recebimentos/'+user.id+'/'+user.role);
                const data = await r.json();
                document.getElementById('app-content').innerHTML = `
                    <h1 class="text-3xl font-bold mb-10 uppercase tracking-tight text-white">Monitoramento de POA</h1>
                    <div class="grid gap-4">${data.map(d => `
                        <div class="p-6 bg-slate-900 border-l-4 border-emerald-500 rounded-xl flex justify-between items-center shadow-lg">
                            <div><p class="font-bold text-white text-lg uppercase tracking-tighter">${d.materia_prima}</p><p class="text-xs text-slate-500 italic">Lote: ${d.lote_fornecedor}</p></div>
                            <span class="text-2xl font-black text-emerald-400 font-mono">${d.quantidade} kg</span>
                        </div>
                    `).join('') || '<p class="text-slate-600 italic">Nenhum dado encontrado.</p>'}</div>`;
            }

            function renderInviteForm() {
                document.getElementById('app-content').innerHTML = `
                    <h1 class="text-3xl font-bold text-blue-400 mb-10 uppercase tracking-tight">Gestão de Convites</h1>
                    <div class="bg-slate-900 p-10 rounded-3xl border border-slate-800 max-w-lg space-y-6 shadow-xl">
                        <input type="email" id="inv-e" placeholder="E-mail da Empresa" class="w-full p-4 rounded-xl bg-slate-800 text-white border border-slate-700 outline-none">
                        <select id="inv-r" class="w-full p-4 rounded-xl bg-slate-800 text-white border border-slate-700 font-bold outline-none">
                            <option value="empresa">Empresa (Lançamento)</option>
                            <option value="fiscal">Fiscal (Auditoria)</option>
                        </select>
                        <button onclick="sendInv()" class="w-full bg-blue-600 text-white py-4 rounded-xl font-bold hover:bg-blue-500 transition shadow-lg uppercase tracking-widest">Enviar Convite</button>
                    </div>`;
            }

            async function sendInv() {
                const email = document.getElementById('inv-e').value;
                const role = document.getElementById('inv-r').value;
                if(!email) return alert("Insira um e-mail.");
                const r = await fetch('/api/invite', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({email, role})
                });
                const res = await r.json();
                if (res.status === "enviado") alert("E-mail enviado com sucesso!");
                else alert("Erro no envio. Verifique o terminal.");
            }

            function renderRegisterPage(token) {
                document.getElementById('main-root').innerHTML = `
                <div class="flex items-center justify-center min-h-screen">
                    <div class="bg-slate-900 p-10 rounded-3xl shadow-2xl w-96 border-t-4 border-blue-500 text-slate-900">
                        <h2 class="text-xl font-bold mb-6 text-white text-center">Ativar Conta</h2>
                        <div class="space-y-4">
                            <input type="text" id="reg-emp" placeholder="Nome da Empresa / SIF" class="w-full p-4 rounded-xl bg-slate-800 text-white border-none outline-none">
                            <input type="text" id="reg-u" placeholder="Novo Usuário" class="w-full p-4 rounded-xl bg-slate-800 text-white border-none outline-none">
                            <input type="password" id="reg-p" placeholder="Senha" class="w-full p-4 rounded-xl bg-slate-800 text-white border-none outline-none">
                            <button onclick="submitRegister('${token}')" class="w-full bg-blue-500 text-white py-4 rounded-xl font-bold uppercase hover:bg-blue-400 transition shadow-lg">Cadastrar</button>
                        </div>
                    </div>
                </div>`;
            }

            async function submitRegister(token) {
                const r = await fetch('/api/register', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({
                        token,
                        username: document.getElementById('reg-u').value,
                        password: document.getElementById('reg-p').value,
                        empresa_nome: document.getElementById('reg-emp').value
                    })
                });
                if(r.ok) { alert("Cadastro realizado!"); window.location.href = "/"; }
                else alert("Erro no convite.");
            }

            function renderEntryForm() {
                document.getElementById('app-content').innerHTML = `
                    <h1 class="text-3xl font-bold mb-10 uppercase tracking-tight">Novo Recebimento</h1>
                    <div class="bg-slate-900 p-8 rounded-3xl border border-slate-800 max-w-lg space-y-4 text-slate-900">
                        <input type="text" id="f-mp" placeholder="Matéria Prima" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <input type="number" id="f-qtd" placeholder="Qtd (kg)" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <input type="text" id="f-lote" placeholder="Lote do Fornecedor" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700">
                        <button onclick="saveRec()" class="w-full bg-emerald-500 text-slate-900 py-4 rounded-xl font-bold uppercase tracking-widest shadow-lg">Salvar Dados</button>
                    </div>`;
            }

            async function saveRec() {
                await fetch('/api/recebimento', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({uid:user.id, mp:document.getElementById('f-mp').value, qtd:parseFloat(document.getElementById('f-qtd').value), lote:document.getElementById('f-lote').value})
                });
                renderDash();
            }

            function logout() { localStorage.clear(); location.reload(); }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    import os
    # Render usa a variável PORT dinâmica
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)