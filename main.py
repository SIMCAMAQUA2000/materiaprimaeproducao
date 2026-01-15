import uuid, smtplib, os
from email.message import EmailMessage
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, relationship, DeclarativeBase
from datetime import datetime

# CONFIGURAÇÕES
EMAIL_REMETENTE = "joseluisblaskowskitavares@gmail.com" 
SENHA_APP = "cjucjngpmckayyko" 

SQLALCHEMY_DATABASE_URL = "sqlite:///./gestao_poa_v31.db"
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

def enviar_email(dest, link):
    msg = EmailMessage()
    msg.set_content(f"Acesse o SGP POA: {link}")
    msg['Subject'] = "Convite SGP POA"; msg['From'] = EMAIL_REMETENTE; msg['To'] = dest
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_REMETENTE, SENHA_APP)
            smtp.send_message(msg)
        return True
    except Exception as e: return False

@app.post("/api/login")
def login(data: dict, db: Session = Depends(get_db)):
    u = db.query(UserDB).filter(UserDB.username == data['username'], UserDB.password == data['password']).first()
    if not u: raise HTTPException(401)
    return {"id": u.id, "role": u.role, "empresa": u.empresa_nome}

@app.post("/api/invite")
def invite(req: dict, request: Request, db: Session = Depends(get_db)):
    tk = str(uuid.uuid4())
    db.add(InviteDB(email=req['email'], token=tk, role=req['role']))
    db.commit()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    link = f"https://{host}/?token={tk}"
    enviar_email(req['email'], link)
    return {"status": "enviado"}

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
        <title>SGP POA v3.1</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body class="bg-slate-950 text-slate-200 font-sans">
        <div id="root">
            <div id="scr-login" class="flex items-center justify-center min-h-screen">
                <div class="bg-slate-900 p-10 rounded-3xl shadow-2xl w-96 border border-slate-800">
                    <h1 class="text-3xl font-black text-emerald-400 text-center mb-8 italic">SGP POA</h1>
                    <div class="space-y-4 text-slate-900">
                        <input type="text" id="l-u" placeholder="Usuário" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none">
                        <input type="password" id="l-p" placeholder="Senha" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none">
                        <button onclick="doLogin()" class="w-full bg-emerald-500 text-slate-900 py-4 rounded-xl font-bold">ENTRAR</button>
                    </div>
                </div>
            </div>
        </div>
        <script>
            let user = JSON.parse(localStorage.getItem('poa_v31'));
            async function doLogin() {
                const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:document.getElementById('l-u').value, password:document.getElementById('l-p').value})});
                if(r.ok) { user = await r.json(); localStorage.setItem('poa_v31', JSON.stringify(user)); location.reload(); }
            }
            if(user) {
                document.getElementById('root').innerHTML = `
                <div class="min-h-screen flex">
                    <aside class="w-64 bg-black p-6 border-r border-slate-900 flex flex-col">
                        <div class="text-emerald-400 font-black text-xl mb-10 italic text-center">SGP POA</div>
                        <nav class="flex-1 space-y-2 text-sm uppercase font-bold">
                            <button onclick="location.reload()" class="w-full text-left p-4 rounded-xl hover:bg-slate-800 flex items-center"><i class="fas fa-home mr-3 text-emerald-500"></i> Dashboard</button>
                            ${user.role === 'admin' ? '<button onclick="showInvite()" class="w-full text-left p-4 rounded-xl bg-blue-900/20 text-blue-300 border border-blue-900/50 flex items-center"><i class="fas fa-user-plus mr-3"></i> Convites</button>' : ''}
                        </nav>
                        <button onclick="localStorage.clear(); location.reload();" class="w-full text-left p-4 text-red-500 hover:bg-red-500/10 rounded-xl mt-auto"><i class="fas fa-power-off mr-3"></i> Sair</button>
                    </aside>
                    <main class="flex-1 p-12" id="content"><h1 class="text-3xl font-bold">Dashboard</h1><div id="list" class="mt-8 space-y-4"></div></main>
                </div>`;
                refresh();
            }
            async function refresh() {
                const r = await fetch(`/api/recebimentos/${user.id}/${user.role}`);
                const data = await r.json();
                document.getElementById('list').innerHTML = data.map(d => `<div class="p-6 bg-slate-900 border-l-4 border-emerald-500 rounded-xl flex justify-between items-center shadow-lg"><div><p class="font-bold text-white text-lg">${d.materia_prima}</p></div><span class="text-2xl font-black text-emerald-400 font-mono">${d.quantidade} kg</span></div>`).join('') || 'Sem dados.';
            }
            function showInvite() {
                document.getElementById('content').innerHTML = `<h1 class="text-3xl font-bold text-blue-400 mb-10 uppercase">Novo Convite</h1><div class="bg-slate-900 p-10 rounded-3xl border border-slate-800 max-w-lg space-y-6"><input type="email" id="inv-e" placeholder="E-mail da Empresa" class="w-full p-4 rounded-xl bg-slate-800 text-white outline-none border border-slate-700"><select id="inv-r" class="w-full p-4 rounded-xl bg-slate-800 text-white border border-slate-700 font-bold outline-none"><option value="empresa">Empresa</option><option value="fiscal">Fiscal</option></select><button onclick="sendInv()" class="w-full bg-blue-600 text-white py-4 rounded-xl font-bold uppercase">Enviar E-mail</button></div>`;
            }
            async function sendInv() {
                const e = document.getElementById('inv-e').value;
                if(!e) return alert("E-mail?");
                alert("Enviando...");
                await fetch('/api/invite', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:e, role:document.getElementById('inv-r').value})});
                alert("Enviado!");
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))