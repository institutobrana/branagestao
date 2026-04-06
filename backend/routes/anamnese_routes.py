from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.anamnese import AnamnesePergunta, AnamneseQuestionario
from models.anamnese_resposta import AnamneseResposta
from models.paciente import Paciente
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access

router = APIRouter(
    prefix="/anamnese",
    tags=["anamnese"],
    dependencies=[Depends(require_module_access("anamnese"))],
)


class QuestionarioPayload(BaseModel):
    nome: str
    ativo: bool = True
    ordem: int | None = None


class PerguntaPayload(BaseModel):
    numero: int | None = None
    texto: str
    ativo: bool = True


class RespostaPayload(BaseModel):
    pergunta_id: int
    resposta: str | None = None


def _questionario_or_404(db: Session, clinica_id: int, questionario_id: int) -> AnamneseQuestionario:
    item = (
        db.query(AnamneseQuestionario)
        .filter(
            AnamneseQuestionario.id == questionario_id,
            AnamneseQuestionario.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Questionario nao encontrado.")
    return item


def _pergunta_or_404(db: Session, clinica_id: int, pergunta_id: int) -> AnamnesePergunta:
    item = (
        db.query(AnamnesePergunta)
        .filter(
            AnamnesePergunta.id == pergunta_id,
            AnamnesePergunta.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Pergunta nao encontrada.")
    return item


def _paciente_or_404(db: Session, clinica_id: int, paciente_id: int) -> Paciente:
    item = (
        db.query(Paciente)
        .filter(
            Paciente.id == paciente_id,
            Paciente.clinica_id == clinica_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado.")
    return item


@router.get("/questionarios")
def listar_questionarios(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(AnamneseQuestionario)
        .filter(AnamneseQuestionario.clinica_id == current_user.clinica_id)
        .order_by(AnamneseQuestionario.ordem.asc(), AnamneseQuestionario.nome.asc())
        .all()
    )
    return [
        {
            "id": int(item.id),
            "nome": str(item.nome or "").strip(),
            "ativo": bool(item.ativo),
            "ordem": int(item.ordem or 0),
        }
        for item in itens
    ]


@router.post("/questionarios")
def criar_questionario(
    payload: QuestionarioPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = str(payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do questionario.")
    existe = (
        db.query(AnamneseQuestionario.id)
        .filter(
            AnamneseQuestionario.clinica_id == current_user.clinica_id,
            AnamneseQuestionario.nome == nome,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe questionario com este nome.")
    ordem = int(payload.ordem or 0) or None
    if ordem is None:
        ordem = (
            db.query(func.max(AnamneseQuestionario.ordem))
            .filter(AnamneseQuestionario.clinica_id == current_user.clinica_id)
            .scalar()
        )
        ordem = int(ordem or 0) + 1
    item = AnamneseQuestionario(
        clinica_id=current_user.clinica_id,
        nome=nome,
        ativo=bool(payload.ativo),
        ordem=max(1, int(ordem)),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": int(item.id), "nome": item.nome, "ativo": bool(item.ativo), "ordem": int(item.ordem or 0)}


@router.put("/questionarios/{questionario_id}")
def atualizar_questionario(
    questionario_id: int,
    payload: QuestionarioPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _questionario_or_404(db, current_user.clinica_id, questionario_id)
    nome = str(payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do questionario.")
    existe = (
        db.query(AnamneseQuestionario.id)
        .filter(
            AnamneseQuestionario.clinica_id == current_user.clinica_id,
            AnamneseQuestionario.nome == nome,
            AnamneseQuestionario.id != item.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe questionario com este nome.")
    item.nome = nome
    item.ativo = bool(payload.ativo)
    if payload.ordem is not None:
        item.ordem = max(1, int(payload.ordem))
    db.commit()
    return {"detail": "Questionario atualizado."}


@router.delete("/questionarios/{questionario_id}")
def excluir_questionario(
    questionario_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _questionario_or_404(db, current_user.clinica_id, questionario_id)
    perguntas = (
        db.query(AnamnesePergunta.id)
        .filter(
            AnamnesePergunta.clinica_id == current_user.clinica_id,
            AnamnesePergunta.questionario_id == item.id,
        )
        .first()
    )
    if perguntas:
        raise HTTPException(status_code=409, detail="Remova as perguntas antes de excluir o questionario.")
    db.delete(item)
    db.commit()
    return {"detail": "Questionario excluido."}


@router.get("/questionarios/{questionario_id}/perguntas")
def listar_perguntas(
    questionario_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _questionario_or_404(db, current_user.clinica_id, questionario_id)
    itens = (
        db.query(AnamnesePergunta)
        .filter(
            AnamnesePergunta.clinica_id == current_user.clinica_id,
            AnamnesePergunta.questionario_id == questionario_id,
        )
        .order_by(AnamnesePergunta.numero.asc(), AnamnesePergunta.id.asc())
        .all()
    )
    return [
        {
            "id": int(item.id),
            "numero": int(item.numero or 0),
            "texto": str(item.texto or "").strip(),
            "ativo": bool(item.ativo),
        }
        for item in itens
    ]


@router.post("/questionarios/{questionario_id}/perguntas")
def criar_pergunta(
    questionario_id: int,
    payload: PerguntaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _questionario_or_404(db, current_user.clinica_id, questionario_id)
    texto = str(payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Informe o texto da pergunta.")
    numero = int(payload.numero or 0)
    if numero <= 0:
        numero = (
            db.query(func.max(AnamnesePergunta.numero))
            .filter(
                AnamnesePergunta.clinica_id == current_user.clinica_id,
                AnamnesePergunta.questionario_id == questionario_id,
            )
            .scalar()
        )
        numero = int(numero or 0) + 1
    existe = (
        db.query(AnamnesePergunta.id)
        .filter(
            AnamnesePergunta.clinica_id == current_user.clinica_id,
            AnamnesePergunta.questionario_id == questionario_id,
            AnamnesePergunta.numero == numero,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe pergunta com este numero.")
    item = AnamnesePergunta(
        clinica_id=current_user.clinica_id,
        questionario_id=questionario_id,
        numero=numero,
        texto=texto,
        ativo=bool(payload.ativo),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": int(item.id), "numero": int(item.numero or 0), "texto": item.texto, "ativo": bool(item.ativo)}


@router.put("/perguntas/{pergunta_id}")
def atualizar_pergunta(
    pergunta_id: int,
    payload: PerguntaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _pergunta_or_404(db, current_user.clinica_id, pergunta_id)
    texto = str(payload.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Informe o texto da pergunta.")
    numero = int(payload.numero or item.numero or 0)
    if numero <= 0:
        raise HTTPException(status_code=400, detail="Numero invalido.")
    existe = (
        db.query(AnamnesePergunta.id)
        .filter(
            AnamnesePergunta.clinica_id == current_user.clinica_id,
            AnamnesePergunta.questionario_id == item.questionario_id,
            AnamnesePergunta.numero == numero,
            AnamnesePergunta.id != item.id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ja existe pergunta com este numero.")
    item.numero = numero
    item.texto = texto
    item.ativo = bool(payload.ativo)
    db.commit()
    return {"detail": "Pergunta atualizada."}


@router.delete("/perguntas/{pergunta_id}")
def excluir_pergunta(
    pergunta_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _pergunta_or_404(db, current_user.clinica_id, pergunta_id)
    db.delete(item)
    db.commit()
    return {"detail": "Pergunta excluida."}


@router.post("/questionarios/{questionario_id}/renumerar")
def renumerar_perguntas(
    questionario_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _questionario_or_404(db, current_user.clinica_id, questionario_id)
    itens = (
        db.query(AnamnesePergunta)
        .filter(
            AnamnesePergunta.clinica_id == current_user.clinica_id,
            AnamnesePergunta.questionario_id == questionario_id,
        )
        .order_by(AnamnesePergunta.numero.asc(), AnamnesePergunta.id.asc())
        .all()
    )
    numero = 1
    for item in itens:
        item.numero = numero
        numero += 1
    db.commit()
    return {"detail": "Perguntas renumeradas.", "total": len(itens)}


@router.get("/pacientes/{paciente_id}/respostas")
def listar_respostas_paciente(
    paciente_id: int,
    questionario_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _paciente_or_404(db, current_user.clinica_id, paciente_id)
    qid = int(questionario_id or 0)
    if qid <= 0:
        qid = (
            db.query(AnamneseQuestionario.id)
            .filter(AnamneseQuestionario.clinica_id == current_user.clinica_id)
            .order_by(AnamneseQuestionario.ordem.asc(), AnamneseQuestionario.id.asc())
            .scalar()
        )
    if not qid:
        return {"questionario_id": None, "questionario_nome": "", "itens": []}

    questionario = _questionario_or_404(db, current_user.clinica_id, int(qid))
    perguntas = (
        db.query(AnamnesePergunta)
        .filter(
            AnamnesePergunta.clinica_id == current_user.clinica_id,
            AnamnesePergunta.questionario_id == questionario.id,
        )
        .order_by(AnamnesePergunta.numero.asc(), AnamnesePergunta.id.asc())
        .all()
    )
    respostas = (
        db.query(AnamneseResposta)
        .filter(
            AnamneseResposta.clinica_id == current_user.clinica_id,
            AnamneseResposta.paciente_id == int(paciente_id),
            AnamneseResposta.pergunta_id.in_([int(p.id) for p in perguntas] or [0]),
        )
        .all()
    )
    respostas_map = {int(r.pergunta_id): str(r.resposta or "") for r in respostas}
    itens = [
        {
            "pergunta_id": int(p.id),
            "numero": int(p.numero or 0),
            "texto": str(p.texto or "").strip(),
            "resposta": respostas_map.get(int(p.id), ""),
        }
        for p in perguntas
    ]
    return {
        "questionario_id": int(questionario.id),
        "questionario_nome": str(questionario.nome or "").strip(),
        "itens": itens,
    }


@router.put("/pacientes/{paciente_id}/respostas")
def salvar_resposta_paciente(
    paciente_id: int,
    payload: RespostaPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _paciente_or_404(db, current_user.clinica_id, paciente_id)
    pergunta = _pergunta_or_404(db, current_user.clinica_id, int(payload.pergunta_id))
    resposta_txt = str(payload.resposta or "").strip()
    atual = (
        db.query(AnamneseResposta)
        .filter(
            AnamneseResposta.clinica_id == current_user.clinica_id,
            AnamneseResposta.paciente_id == int(paciente_id),
            AnamneseResposta.pergunta_id == int(pergunta.id),
        )
        .first()
    )
    if not resposta_txt:
        if atual:
            db.delete(atual)
            db.commit()
        return {"detail": "Resposta limpa."}

    if atual is None:
        atual = AnamneseResposta(
            clinica_id=current_user.clinica_id,
            paciente_id=int(paciente_id),
            questionario_id=int(pergunta.questionario_id),
            pergunta_id=int(pergunta.id),
            resposta=resposta_txt,
        )
        db.add(atual)
    else:
        atual.resposta = resposta_txt
    db.commit()
    return {"detail": "Resposta salva."}
