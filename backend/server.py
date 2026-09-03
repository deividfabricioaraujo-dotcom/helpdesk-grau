try:
    import importlib

    dotenv_module = importlib.import_module("dotenv")
    load_dotenv = dotenv_module.load_dotenv
except ModuleNotFoundError:  # pragma: no cover - dependency may be absent in some environments
    def load_dotenv(*args, **kwargs):
        return False

from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import (  # type: ignore[import-not-found]
    FastAPI,
    APIRouter,
    HTTPException,
    Request,
    Response,
    Depends,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Optional, Annotated
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging
import uuid
import bcrypt
import jwt

from emergentintegrations.llm.chat import (
    LlmChat,
    UserMessage,
    TextDelta,
    StreamDone,
)


# ----------------------------------------------------------------------------
# DB + App setup
# ----------------------------------------------------------------------------

mongo_url = os.environ["MONGO_URL"]

client = AsyncIOMotorClient(mongo_url)

db = client[os.environ["DB_NAME"]]

app = FastAPI(title="grau TI — Helpdesk")

api_router = APIRouter(prefix="/api")

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


PyObjectId = Annotated[
    str,
    BeforeValidator(str),
]


PRIORITY_LABELS = {
    "baixa": "Baixa",
    "media": "Média",
    "alta": "Alta",
    "urgente": "Urgente",
}

STATUS_LABELS = {
    "aberto": "Aberto",
    "em_andamento": "Em Andamento",
    "resolvido": "Resolvido",
    "cancelado": "Cancelado",
}

DEVICE_LABELS = {
    "pc": "Computador",
    "mouse": "Mouse",
    "keyboard": "Teclado",
    "internet_projector": "Internet/Projetor",
}


def now_utc():
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------------------
# WebSocket Manager
# ----------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

        if websocket not in self.active_connections:
            self.active_connections.append(websocket)

        logger.info(
            "WebSocket conectado. Clientes ativos: %s",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        logger.info(
            "WebSocket desconectado. Clientes ativos: %s",
            len(self.active_connections),
        )

    async def broadcast(self, message: dict):
        disconnected = []

        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    "Falha ao enviar atualização WebSocket: %s",
                    e,
                )
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


# ----------------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    user_id: str,
    username: str,
) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "type": "access",
        "exp": now_utc() + timedelta(days=7),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


async def get_current_admin(
    request: Request,
) -> dict:
    token = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get(
            "Authorization",
            "",
        )

        token = (
            auth_header[7:]
            if auth_header.startswith("Bearer ")
            else None
        )

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Não autenticado",
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401,
                detail="Token inválido",
            )

        user = await db.admins.find_one(
            {
                "_id": ObjectId(
                    payload["sub"]
                )
            }
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Usuário não encontrado",
            )

        return {
            "id": str(user["_id"]),
            "username": user["username"],
            "name": user["name"],
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Sessão expirada",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
        )


# ----------------------------------------------------------------------------
# WebSocket authentication
# ----------------------------------------------------------------------------

async def authenticate_websocket(
    websocket: WebSocket,
):
    token = websocket.cookies.get(
        "access_token"
    )

    if not token:
        auth_header = websocket.headers.get(
            "Authorization",
            "",
        )

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        if payload.get("type") != "access":
            return None

        user = await db.admins.find_one(
            {
                "_id": ObjectId(
                    payload["sub"]
                )
            }
        )

        if not user:
            return None

        return {
            "id": str(user["_id"]),
            "username": user["username"],
            "name": user["name"],
        }

    except Exception:
        return None


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class DeviceStatus(BaseModel):
    pc: str = "ok"
    mouse: str = "ok"
    keyboard: str = "ok"
    internet_projector: str = "ok"


class TicketCreate(BaseModel):
    requester_name: str
    building: str
    floor: str
    room: str
    devices: DeviceStatus = Field(
        default_factory=DeviceStatus
    )
    priority: str = "media"
    talk_to_deivid: bool = False
    notes: str = ""


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = ""


class ChatRequest(BaseModel):
    message: str
    scope: str = "public"
    session_id: Optional[str] = None


def serialize_ticket(doc: dict) -> dict:
    doc = dict(doc)

    doc["id"] = str(
        doc.pop("_id")
    )

    return doc


# ----------------------------------------------------------------------------
# WebSocket endpoint
# ----------------------------------------------------------------------------

@app.websocket("/api/ws/tickets")
async def tickets_websocket(
    websocket: WebSocket,
):
    admin = await authenticate_websocket(
        websocket
    )

    if not admin:
        await websocket.close(
            code=1008,
            reason="Não autenticado",
        )
        return

    await manager.connect(websocket)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "message": "Atualizações em tempo real ativas",
            }
        )

        while True:
            try:
                data = await websocket.receive_text()

                if data == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong"
                        }
                    )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.warning(
            "Erro no WebSocket: %s",
            e,
        )

    finally:
        manager.disconnect(websocket)


# ----------------------------------------------------------------------------
# Auth routes
# ----------------------------------------------------------------------------

@api_router.post("/auth/login")
async def login(
    body: LoginRequest,
    response: Response,
):
    username = body.username.strip().lower()

    user = await db.admins.find_one(
        {
            "username": username
        }
    )

    if not user or not verify_password(
        body.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha inválidos",
        )

    token = create_access_token(
        str(user["_id"]),
        user["username"],
    )

    response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=False,
    samesite="lax",
    max_age=COOKIE_MAX_AGE_SECONDS,
    path="/",
)

    return {
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "name": user["name"],
        },
    }


@api_router.post("/auth/logout")
async def logout(
    response: Response,
):
    response.delete_cookie(
        "access_token",
        path="/",
    )

    return {
        "ok": True
    }


@api_router.get("/auth/me")
async def me(
    admin: dict = Depends(
        get_current_admin
    ),
):
    return admin


# ----------------------------------------------------------------------------
# Ticket routes
# ----------------------------------------------------------------------------

@api_router.post("/tickets")
async def create_ticket(
    body: TicketCreate,
):
    if (
        not body.requester_name.strip()
        or not body.building.strip()
        or not body.room.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="Nome, prédio e sala são obrigatórios",
        )

    if body.priority not in PRIORITY_LABELS:
        raise HTTPException(
            status_code=400,
            detail="Prioridade inválida",
        )

    created_at = now_utc().isoformat()

    code = (
        "GT-"
        + uuid.uuid4().hex[:6].upper()
    )

    doc = {
        "code": code,
        "requester_name": body.requester_name.strip(),
        "building": body.building.strip(),
        "floor": body.floor.strip(),
        "room": body.room.strip(),
        "devices": body.devices.model_dump(),
        "priority": body.priority,
        "talk_to_deivid": body.talk_to_deivid,
        "notes": body.notes.strip(),
        "status": "aberto",
        "archived": False,
        "created_at": created_at,
        "updated_at": created_at,
        "audit": [
            {
                "by": body.requester_name.strip(),
                "action": "criado",
                "from_status": None,
                "to_status": "aberto",
                "at": created_at,
                "note": "Chamado aberto pelo solicitante",
            }
        ],
    }

    res = await db.tickets.insert_one(
        doc
    )

    doc["_id"] = res.inserted_id

    ticket = serialize_ticket(doc)

    # AVISA TODOS OS PAINÉIS ADMINISTRATIVOS IMEDIATAMENTE.
    await manager.broadcast(
        {
            "type": "ticket_created",
            "ticket": ticket,
        }
    )

    return ticket


@api_router.get("/tickets")
async def list_tickets(
    archived: bool = False,
    building: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    admin: dict = Depends(
        get_current_admin
    ),
):
    query: dict = {
        "archived": archived
    }

    if building:
        query["building"] = building

    if priority:
        query["priority"] = priority

    if status:
        query["status"] = status

    if search:
        query["$or"] = [
            {
                "requester_name": {
                    "$regex": search,
                    "$options": "i",
                }
            },
            {
                "room": {
                    "$regex": search,
                    "$options": "i",
                }
            },
            {
                "code": {
                    "$regex": search,
                    "$options": "i",
                }
            },
        ]

    tickets = (
        await db.tickets
        .find(query)
        .sort("created_at", -1)
        .to_list(1000)
    )

    return [
        serialize_ticket(t)
        for t in tickets
    ]


@api_router.get("/tickets/stats")
async def stats(
    admin: dict = Depends(
        get_current_admin
    ),
):
    base = {
        "archived": False
    }

    open_count = (
        await db.tickets.count_documents(
            {
                **base,
                "status": "aberto",
            }
        )
    )

    in_progress = (
        await db.tickets.count_documents(
            {
                **base,
                "status": "em_andamento",
            }
        )
    )

    urgent = (
        await db.tickets.count_documents(
            {
                **base,
                "priority": "urgente",
                "status": {
                    "$nin": [
                        "resolvido",
                        "cancelado",
                    ]
                },
            }
        )
    )

    resolved = (
        await db.tickets.count_documents(
            {
                **base,
                "status": "resolvido",
            }
        )
    )

    buildings = await db.tickets.distinct(
        "building",
        {
            "archived": False
        },
    )

    return {
        "open": open_count,
        "in_progress": in_progress,
        "urgent": urgent,
        "resolved": resolved,
        "buildings": sorted(
            [
                b
                for b in buildings
                if b
            ]
        ),
    }


@api_router.get(
    "/tickets/public/{code}"
)
async def public_lookup(
    code: str,
):
    doc = await db.tickets.find_one(
        {
            "code": code.strip().upper()
        }
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Chamado não encontrado",
        )

    return {
        "code": doc["code"],
        "status": doc["status"],
        "priority": doc["priority"],
        "building": doc["building"],
        "room": doc["room"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


@api_router.patch(
    "/tickets/{ticket_id}/status"
)
async def update_status(
    ticket_id: str,
    body: StatusUpdate,
    admin: dict = Depends(
        get_current_admin
    ),
):
    if body.status not in STATUS_LABELS:
        raise HTTPException(
            status_code=400,
            detail="Status inválido",
        )

    try:
        object_id = ObjectId(ticket_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="ID do chamado inválido",
        )

    doc = await db.tickets.find_one(
        {
            "_id": object_id
        }
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Chamado não encontrado",
        )

    updated_at = now_utc().isoformat()

    entry = {
        "by": admin["name"],
        "action": "status_alterado",
        "from_status": doc["status"],
        "to_status": body.status,
        "at": updated_at,
        "note": body.note or "",
    }

    await db.tickets.update_one(
        {
            "_id": object_id
        },
        {
            "$set": {
                "status": body.status,
                "updated_at": updated_at,
            },
            "$push": {
                "audit": entry
            },
        },
    )

    updated = await db.tickets.find_one(
        {
            "_id": object_id
        }
    )

    ticket = serialize_ticket(updated)

    await manager.broadcast(
        {
            "type": "ticket_updated",
            "ticket": ticket,
            "action": "status_alterado",
        }
    )

    return ticket


@api_router.patch(
    "/tickets/{ticket_id}/archive"
)
async def archive_ticket(
    ticket_id: str,
    admin: dict = Depends(
        get_current_admin
    ),
):
    try:
        object_id = ObjectId(ticket_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="ID do chamado inválido",
        )

    doc = await db.tickets.find_one(
        {
            "_id": object_id
        }
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Chamado não encontrado",
        )

    new_archived = not doc.get(
        "archived",
        False,
    )

    updated_at = now_utc().isoformat()

    entry = {
        "by": admin["name"],
        "action": (
            "arquivado"
            if new_archived
            else "desarquivado"
        ),
        "from_status": doc["status"],
        "to_status": doc["status"],
        "at": updated_at,
        "note": "",
    }

    await db.tickets.update_one(
        {
            "_id": object_id
        },
        {
            "$set": {
                "archived": new_archived,
                "updated_at": updated_at,
            },
            "$push": {
                "audit": entry
            },
        },
    )

    updated = await db.tickets.find_one(
        {
            "_id": object_id
        }
    )

    ticket = serialize_ticket(updated)

    await manager.broadcast(
        {
            "type": "ticket_archived",
            "ticket": ticket,
            "action": entry["action"],
        }
    )

    return ticket


# ----------------------------------------------------------------------------
# Deivid AI
# ----------------------------------------------------------------------------

async def build_context(
    scope: str,
) -> str:
    tickets = (
        await db.tickets
        .find(
            {
                "archived": False
            }
        )
        .sort("created_at", -1)
        .to_list(200)
    )

    if not tickets:
        return "Não há chamados ativos no momento."

    lines = []

    for t in tickets:
        devices = t.get(
            "devices",
            {},
        )

        problems = [
            DEVICE_LABELS[k]
            for k, v in devices.items()
            if v == "problem"
            and k in DEVICE_LABELS
        ]

        prob_txt = (
            ", ".join(problems)
            if problems
            else "nenhum equipamento com defeito informado"
        )

        if scope == "admin":
            lines.append(
                f"[{t['code']}] "
                f"Solicitante: {t['requester_name']} | "
                f"Local: {t['building']}/"
                f"Andar {t.get('floor','-')}/"
                f"Sala {t['room']} | "
                f"Prioridade: "
                f"{PRIORITY_LABELS[t['priority']]} | "
                f"Status: "
                f"{STATUS_LABELS[t['status']]} | "
                f"Problemas: {prob_txt} | "
                f"Falar com Deivid: "
                f"{'Sim' if t.get('talk_to_deivid') else 'Não'} | "
                f"Obs: {t.get('notes','') or '-'} | "
                f"Aberto em: {t['created_at'][:16]}"
            )

        else:
            lines.append(
                f"[{t['code']}] "
                f"Local: {t['building']}/"
                f"Sala {t['room']} | "
                f"Prioridade: "
                f"{PRIORITY_LABELS[t['priority']]} | "
                f"Status: "
                f"{STATUS_LABELS[t['status']]} | "
                f"Problemas: {prob_txt}"
            )

    return "\n".join(lines)


@api_router.post("/chat")
async def chat(
    body: ChatRequest,
):
    context = await build_context(
        body.scope
    )

    if body.scope == "admin":
        system = (
            "Você é o Deivid, assistente virtual "
            "de TI da grau Técnico, em modo "
            "SOMENTE LEITURA. "
            "Você NÃO cria, altera nem arquiva "
            "chamados — apenas lê, resume e "
            "responde perguntas com base nos "
            "dados fornecidos. "
            "Responda em português do Brasil, "
            "de forma objetiva e profissional. "
            "Use os dados reais dos chamados abaixo. "
            "Se perguntarem algo fora dos dados, "
            "diga que só tem acesso aos chamados atuais."
            "\n\n"
            f"=== CHAMADOS ATIVOS ===\n{context}"
        )

    else:
        system = (
            "Você é o Deivid, assistente virtual "
            "de TI da grau Técnico, em modo "
            "SOMENTE LEITURA e PÚBLICO. "
            "Ajude solicitantes com dúvidas gerais "
            "de TI e a consultar o andamento dos "
            "chamados por código. "
            "NÃO revele nomes de solicitantes "
            "nem observações privadas. "
            "Responda em português do Brasil, "
            "breve e educado."
            "\n\n"
            f"=== RESUMO DOS CHAMADOS "
            f"(sem dados pessoais) ===\n{context}"
        )

    session_id = (
        body.session_id
        or str(uuid.uuid4())
    )

    chat_client = (
        LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system,
        )
        .with_model(
            "gemini",
            "gemini-3-flash-preview",
        )
    )

    user_message = UserMessage(
        text=body.message
    )

    async def event_generator():
        try:
            async for event in chat_client.stream_message(
                user_message
            ):
                if isinstance(
                    event,
                    TextDelta,
                ):
                    yield event.content

                elif isinstance(
                    event,
                    StreamDone,
                ):
                    break

        except Exception as e:
            logger.error(
                f"Deivid chat error: {e}"
            )

            yield (
                "Desculpe, tive um problema "
                "para responder agora. "
                "Tente novamente."
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ----------------------------------------------------------------------------
# Routers / CORS
# ----------------------------------------------------------------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get(
        "CORS_ORIGINS",
        "*",
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------------
# Seeding
# ----------------------------------------------------------------------------

async def seed_admins():
    admins = [
        {
            "username": os.environ[
                "DEIVID_USERNAME"
            ],
            "password": os.environ[
                "DEIVID_PASSWORD"
            ],
            "name": "Deivid",
            "email": os.environ[
                "DEIVID_EMAIL"
            ],
        },
        {
            "username": os.environ[
                "BRUNO_USERNAME"
            ],
            "password": os.environ[
                "BRUNO_PASSWORD"
            ],
            "name": "Bruno",
            "email": os.environ[
                "BRUNO_EMAIL"
            ],
        },
    ]

    for a in admins:
        uname = (
            a["username"]
            .strip()
            .lower()
        )

        existing = await db.admins.find_one(
            {
                "username": uname
            }
        )

        if existing is None:
            await db.admins.insert_one(
                {
                    "username": uname,
                    "password_hash": hash_password(
                        a["password"]
                    ),
                    "name": a["name"],
                    "email": a["email"],
                    "created_at": now_utc().isoformat(),
                }
            )

            logger.info(
                f"Seeded admin: {uname}"
            )

        elif not verify_password(
            a["password"],
            existing["password_hash"],
        ):
            await db.admins.update_one(
                {
                    "username": uname
                },
                {
                    "$set": {
                        "password_hash": hash_password(
                            a["password"]
                        )
                    }
                },
            )

            logger.info(
                f"Updated admin password: {uname}"
            )


@app.on_event("startup")
async def startup():
    await db.admins.create_index(
        "username",
        unique=True,
    )

    await db.tickets.create_index(
        "code",
        unique=True,
    )

    await seed_admins()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()