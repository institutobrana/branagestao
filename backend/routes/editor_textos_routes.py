from pathlib import Path
import json
import re
import unicodedata
from html import escape as html_escape, unescape as html_unescape
from html.parser import HTMLParser

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models.modelo_documento import ModeloDocumento
from models.usuario import Usuario
from security.dependencies import get_current_user, require_module_access


router = APIRouter(
    prefix="/editor-textos",
    tags=["editor-textos"],
    dependencies=[Depends(require_module_access("configuracao"))],
)

PROJECT_DIR = Path(__file__).resolve().parents[3]
MODEL_STORAGE_DIR = PROJECT_DIR / "saas" / "storage" / "modelos"
TEXT_EXTENSIONS = {".txt", ".rtf", ".mod"}
RTF_RICH_EXTENSIONS = {".rtf", ".mod"}
TEXT_MODEL_TYPES = {
    "atestados",
    "receitas",
    "recibos",
    "etiquetas",
    "orcamentos",
    "email_agenda",
    "whatsapp_agenda",
    "outros",
}
RTF_DESTINATIONS_TO_IGNORE = {
    "fonttbl",
    "colortbl",
    "datastore",
    "themedata",
    "stylesheet",
    "info",
    "pict",
    "object",
    "fldinst",
    "fldrslt",
    "xmlopen",
    "xmlattrname",
    "xmlattrvalue",
}
MERGE_FIELDS_LEGACY = [
    {"label": "Nome completo", "token": "<<NOME COMPLETO>>"},
    {"label": "Primeiro nome", "token": "<<PRIMEIRO NOME>>"},
    {"label": "Data agenda", "token": "<<AGENDA.DATA>>"},
    {"label": "Hora agenda", "token": "<<AGENDA.HORA>>"},
    {"label": "Cirurgiao", "token": "<<CIRURGIAO.NOME>>"},
    {"label": "Telefone", "token": "<<PACIENTE.TELEFONE>>"},
    {"label": "Celular", "token": "<<PACIENTE.CELULAR>>"},
    {"label": "Email", "token": "<<PACIENTE.EMAIL>>"},
]
MERGE_SNAPSHOT_PATH = PROJECT_DIR / "saas" / "backend" / "data" / "editor_textos_mesclagem_snapshot.json"
MERGE_DEFAULT_CATEGORY = "Atestado"
FILENAME_SANITIZE = re.compile(r"[^a-zA-Z0-9._ -]+")


class ModeloTextoSalvarPayload(BaseModel):
    nome: str = Field(default="", max_length=180)
    conteudo: str = Field(default="")
    conteudo_formato: str | None = Field(default="text", max_length=20)
    tipo_modelo: str | None = Field(default=None, max_length=40)
    extensao: str | None = Field(default=None, max_length=20)


def _merge_sort_key(value: str) -> str:
    txt = str(value or "")
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    return txt.casefold()


def _load_merge_fields_payload() -> dict:
    entries: list[dict] = []
    category_order: list[str] = []
    if MERGE_SNAPSHOT_PATH.exists():
        try:
            raw = json.loads(MERGE_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            category_order = [
                str(cat).strip()
                for cat in (raw.get("categorias_ordem_arquivo") or [])
                if str(cat).strip()
            ]
            for item in (raw.get("campos") or []):
                categoria = str(item.get("categoria") or "").strip()
                campo = str(item.get("campo") or "").strip()
                descricao = str(item.get("descricao") or "").strip()
                token = str(item.get("token") or "").strip()
                if not categoria or not campo:
                    continue
                if not token:
                    token = f"<<{categoria}.{campo}>>"
                entries.append(
                    {
                        "categoria": categoria,
                        "campo": campo,
                        "descricao": descricao or campo,
                        "token": token,
                    }
                )
        except Exception:
            entries = []
            category_order = []

    if not entries:
        for item in MERGE_FIELDS_LEGACY:
            token = str(item.get("token") or "").strip()
            label = str(item.get("label") or token).strip()
            categoria = "Geral"
            campo = label
            if token.startswith("<<") and token.endswith(">>") and "." in token:
                miolo = token[2:-2]
                categoria, campo = (miolo.split(".", 1) + [""])[:2]
                categoria = str(categoria).strip() or "Geral"
                campo = str(campo).strip() or label
            if categoria not in category_order:
                category_order.append(categoria)
            entries.append(
                {
                    "categoria": categoria,
                    "campo": campo,
                    "descricao": label or campo,
                    "token": token,
                }
            )

    grouped: dict[str, list[dict]] = {}
    for item in entries:
        cat = item["categoria"]
        grouped.setdefault(cat, []).append(
            {
                "campo": item["campo"],
                "descricao": item["descricao"],
                "token": item["token"],
            }
        )
        if cat not in category_order:
            category_order.append(cat)

    categorias: list[dict] = []
    for cat in category_order:
        campos = sorted(grouped.get(cat, []), key=lambda row: _merge_sort_key(row.get("campo", "")))
        if not campos:
            continue
        categorias.append({"nome": cat, "campos": campos})

    flat = [
        {"label": item["descricao"], "token": item["token"]}
        for cat in categorias
        for item in cat["campos"]
    ]
    default_category = MERGE_DEFAULT_CATEGORY
    if categorias and default_category not in {c["nome"] for c in categorias}:
        default_category = str(categorias[0].get("nome") or MERGE_DEFAULT_CATEGORY)
    return {
        "campos": flat,
        "categorias": categorias,
        "categoria_padrao": default_category,
    }


MERGE_FIELDS_PAYLOAD = _load_merge_fields_payload()


def _normalize_tipo_modelo(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in TEXT_MODEL_TYPES:
        return raw
    return "outros"


def _normalize_extensao(value: str | None, default: str = ".txt") -> str:
    raw = str(value or "").strip().lower()
    if raw and not raw.startswith("."):
        raw = f".{raw}"
    if raw in TEXT_EXTENSIONS:
        return raw
    return default


def _safe_relative_path(path_rel: str) -> Path | None:
    rel = str(path_rel or "").strip().replace("\\", "/")
    if not rel:
        return None
    abs_path = (PROJECT_DIR / rel).resolve()
    try:
        if not str(abs_path).startswith(str(PROJECT_DIR.resolve())):
            return None
    except Exception:
        return None
    return abs_path


def _read_text_file(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc).replace("\x00", "")
        except Exception:
            continue
    return ""


def _looks_like_rtf(content: str) -> bool:
    return str(content or "").lstrip().startswith("{\\rtf")


def _normalize_content_format(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"html", "text"}:
        return raw
    return "text"


def _load_raw_content(item: ModeloDocumento) -> str:
    abs_path = _safe_relative_path(str(item.caminho_arquivo or ""))
    if not abs_path or not abs_path.exists() or not abs_path.is_file():
        return ""
    return _read_text_file(abs_path)


def _rtf_to_text(content: str) -> str:
    rtf = str(content or "")
    if not rtf:
        return ""

    out: list[str] = []
    stack: list[tuple[bool, int]] = []
    ignorable = False
    ucskip = 1
    curskip = 0
    idx = 0

    while idx < len(rtf):
        ch = rtf[idx]
        if ch == "{":
            stack.append((ignorable, ucskip))
            idx += 1
            continue
        if ch == "}":
            if stack:
                ignorable, ucskip = stack.pop()
            idx += 1
            continue
        if ch == "\\":
            idx += 1
            if idx >= len(rtf):
                break
            ctrl = rtf[idx]
            if ctrl in "\\{}":
                if not ignorable and curskip <= 0:
                    out.append(ctrl)
                elif curskip > 0:
                    curskip -= 1
                idx += 1
                continue
            if ctrl == "*":
                ignorable = True
                idx += 1
                continue
            if ctrl == "'":
                if idx + 2 < len(rtf):
                    hexcode = rtf[idx + 1 : idx + 3]
                    try:
                        decoded = bytes.fromhex(hexcode).decode("cp1252", errors="ignore")
                    except Exception:
                        decoded = ""
                    if not ignorable and curskip <= 0:
                        out.append(decoded)
                    elif curskip > 0:
                        curskip -= 1
                idx += 3
                continue
            m = re.match(r"([a-zA-Z]+)(-?\d+)? ?", rtf[idx:])
            if m:
                word = m.group(1) or ""
                arg_txt = m.group(2)
                idx += len(m.group(0))
                if word in {"par", "line"} and not ignorable:
                    out.append("\n")
                elif word == "tab" and not ignorable:
                    out.append("\t")
                elif word == "uc" and arg_txt:
                    try:
                        ucskip = max(0, int(arg_txt))
                    except Exception:
                        ucskip = 1
                elif word == "u" and arg_txt:
                    try:
                        codepoint = int(arg_txt)
                        if codepoint < 0:
                            codepoint += 65536
                        if not ignorable:
                            out.append(chr(codepoint))
                        curskip = ucskip
                    except Exception:
                        pass
                elif word in RTF_DESTINATIONS_TO_IGNORE:
                    ignorable = True
                continue
            idx += 1
            continue
        if curskip > 0:
            curskip -= 1
            idx += 1
            continue
        if not ignorable:
            out.append(ch)
        idx += 1

    text = "".join(out)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _rtf_to_html(content: str) -> str:
    rtf = str(content or "")
    if not rtf:
        return "<p></p>"

    out: list[str] = []
    stack: list[tuple[bool, int, dict, str]] = []
    ignorable = False
    ucskip = 1
    curskip = 0
    state = {"b": False, "i": False, "u": False}
    align = "left"
    para_open = False
    idx = 0

    def normalize_align(value: str) -> str:
        if value == "center":
            return "center"
        if value == "right":
            return "right"
        if value == "justify":
            return "justify"
        return "left"

    def open_para() -> None:
        nonlocal para_open
        if para_open:
            return
        style = ""
        if align != "left":
            style = f' style="text-align:{align}"'
        out.append(f"<p{style}>")
        para_open = True

    def close_para() -> None:
        nonlocal para_open
        if para_open:
            out.append("</p>")
            para_open = False

    def apply_state(target: dict) -> None:
        nonlocal state
        # fecha primeiro na ordem inversa
        if state["u"] and not target["u"]:
            out.append("</u>")
        if state["i"] and not target["i"]:
            out.append("</em>")
        if state["b"] and not target["b"]:
            out.append("</strong>")
        # abre na ordem fixa
        if not state["b"] and target["b"]:
            out.append("<strong>")
        if not state["i"] and target["i"]:
            out.append("<em>")
        if not state["u"] and target["u"]:
            out.append("<u>")
        state = {"b": bool(target["b"]), "i": bool(target["i"]), "u": bool(target["u"])}

    def break_paragraph() -> None:
        apply_state({"b": False, "i": False, "u": False})
        close_para()
        open_para()

    open_para()
    while idx < len(rtf):
        ch = rtf[idx]
        if ch == "{":
            stack.append((ignorable, ucskip, state.copy(), align))
            idx += 1
            continue
        if ch == "}":
            if stack:
                prev_ignorable, prev_ucskip, prev_state, prev_align = stack.pop()
                if not ignorable:
                    if align != prev_align:
                        apply_state({"b": False, "i": False, "u": False})
                        close_para()
                        align = normalize_align(prev_align)
                        open_para()
                    apply_state(prev_state)
                ignorable, ucskip = prev_ignorable, prev_ucskip
            idx += 1
            continue
        if ch == "\\":
            idx += 1
            if idx >= len(rtf):
                break
            ctrl = rtf[idx]
            if ctrl in "\\{}":
                if not ignorable and curskip <= 0:
                    open_para()
                    out.append(html_escape(ctrl))
                elif curskip > 0:
                    curskip -= 1
                idx += 1
                continue
            if ctrl == "*":
                ignorable = True
                idx += 1
                continue
            if ctrl == "'":
                if idx + 2 < len(rtf):
                    hexcode = rtf[idx + 1 : idx + 3]
                    try:
                        decoded = bytes.fromhex(hexcode).decode("cp1252", errors="ignore")
                    except Exception:
                        decoded = ""
                    if not ignorable and curskip <= 0:
                        open_para()
                        out.append(html_escape(decoded))
                    elif curskip > 0:
                        curskip -= 1
                idx += 3
                continue
            m = re.match(r"([a-zA-Z]+)(-?\d+)? ?", rtf[idx:])
            if m:
                word = (m.group(1) or "").lower()
                arg_txt = m.group(2)
                arg_num = int(arg_txt) if arg_txt and arg_txt.lstrip("-").isdigit() else None
                idx += len(m.group(0))

                if word in {"par"} and not ignorable:
                    break_paragraph()
                elif word in {"line"} and not ignorable:
                    open_para()
                    out.append("<br>")
                elif word == "tab" and not ignorable:
                    open_para()
                    out.append("&emsp;")
                elif word == "uc" and arg_num is not None:
                    ucskip = max(0, arg_num)
                elif word == "u" and arg_num is not None:
                    if not ignorable:
                        cp = arg_num if arg_num >= 0 else arg_num + 65536
                        open_para()
                        out.append(html_escape(chr(cp)))
                    curskip = ucskip
                elif word == "b" and not ignorable:
                    target = state.copy()
                    target["b"] = bool(arg_num is None or arg_num != 0)
                    apply_state(target)
                elif word == "i" and not ignorable:
                    target = state.copy()
                    target["i"] = bool(arg_num is None or arg_num != 0)
                    apply_state(target)
                elif word in {"ul"} and not ignorable:
                    target = state.copy()
                    target["u"] = bool(arg_num is None or arg_num != 0)
                    apply_state(target)
                elif word in {"ulnone", "ul0"} and not ignorable:
                    target = state.copy()
                    target["u"] = False
                    apply_state(target)
                elif word == "ql" and not ignorable:
                    if align != "left":
                        apply_state({"b": False, "i": False, "u": False})
                        close_para()
                        align = "left"
                        open_para()
                elif word == "qc" and not ignorable:
                    if align != "center":
                        apply_state({"b": False, "i": False, "u": False})
                        close_para()
                        align = "center"
                        open_para()
                elif word == "qr" and not ignorable:
                    if align != "right":
                        apply_state({"b": False, "i": False, "u": False})
                        close_para()
                        align = "right"
                        open_para()
                elif word == "qj" and not ignorable:
                    if align != "justify":
                        apply_state({"b": False, "i": False, "u": False})
                        close_para()
                        align = "justify"
                        open_para()
                elif word in RTF_DESTINATIONS_TO_IGNORE:
                    ignorable = True
                continue
            idx += 1
            continue
        if curskip > 0:
            curskip -= 1
            idx += 1
            continue
        if not ignorable:
            open_para()
            out.append(html_escape(ch))
        idx += 1

    apply_state({"b": False, "i": False, "u": False})
    close_para()
    html = "".join(out).strip()
    if not html:
        return "<p></p>"
    return html


def _escape_rtf_text(text: str) -> str:
    out: list[str] = []
    for ch in str(text or ""):
        if ch == "\\":
            out.append("\\\\")
            continue
        if ch == "{":
            out.append("\\{")
            continue
        if ch == "}":
            out.append("\\}")
            continue
        if ch == "\r":
            continue
        if ch == "\n":
            out.append("\\par ")
            continue
        if ch == "\t":
            out.append("\\tab ")
            continue
        code = ord(ch)
        if 32 <= code <= 126:
            out.append(ch)
            continue
        try:
            encoded = ch.encode("cp1252")
            for b in encoded:
                out.append(f"\\'{b:02x}")
        except Exception:
            out.append(f"\\u{code}?")
    return "".join(out)


class _HtmlToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        t = (tag or "").lower()
        if t in {"br"}:
            self.parts.append("\n")
        elif t in {"p", "div", "li"}:
            if self.parts:
                self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = (tag or "").lower()
        if t in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data or "")

    def text(self) -> str:
        raw = html_unescape("".join(self.parts))
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
        return raw


class _HtmlToRtfParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.block_open = False
        self.list_depth = 0
        self.list_ordered_stack: list[bool] = []
        self.list_item_index_stack: list[int] = []
        self.open_tags: list[str] = []

    def _attrs_dict(self, attrs) -> dict:
        return {str(k or "").lower(): str(v or "") for k, v in (attrs or [])}

    def _append_block_break(self) -> None:
        if self.parts and not self.parts[-1].endswith("\\par "):
            self.parts.append("\\par ")

    def _append_alignment(self, attrs: dict) -> None:
        align_attr = str(attrs.get("align", "")).strip().lower()
        style = str(attrs.get("style", "")).strip().lower()
        align_val = align_attr
        if "text-align" in style:
            m = re.search(r"text-align\s*:\s*([a-z]+)", style)
            if m:
                align_val = m.group(1).strip().lower()
        if align_val in {"center", "right", "justify", "left"}:
            cmd = {"left": "\\ql ", "center": "\\qc ", "right": "\\qr ", "justify": "\\qj "}.get(align_val, "\\ql ")
            self.parts.append(cmd)

    def handle_starttag(self, tag: str, attrs) -> None:
        t = (tag or "").lower()
        attrs_map = self._attrs_dict(attrs)
        if t in {"p", "div"}:
            self._append_block_break()
            self._append_alignment(attrs_map)
            self.block_open = True
            return
        if t == "br":
            self.parts.append("\\line ")
            return
        if t in {"strong", "b"}:
            self.parts.append("\\b ")
            self.open_tags.append("b")
            return
        if t in {"em", "i"}:
            self.parts.append("\\i ")
            self.open_tags.append("i")
            return
        if t == "u":
            self.parts.append("\\ul ")
            self.open_tags.append("u")
            return
        if t in {"ul", "ol"}:
            self.list_depth += 1
            self.list_ordered_stack.append(t == "ol")
            self.list_item_index_stack.append(0)
            self._append_block_break()
            return
        if t == "li":
            self._append_block_break()
            bullet = "\\bullet\\tab "
            if self.list_ordered_stack and self.list_ordered_stack[-1]:
                self.list_item_index_stack[-1] += 1
                bullet = f"{self.list_item_index_stack[-1]}.\\tab "
            self.parts.append("\\tab ")
            self.parts.append(bullet)
            self.block_open = True
            return

    def handle_endtag(self, tag: str) -> None:
        t = (tag or "").lower()
        if t in {"strong", "b"}:
            self.parts.append("\\b0 ")
            if self.open_tags and self.open_tags[-1] == "b":
                self.open_tags.pop()
            return
        if t in {"em", "i"}:
            self.parts.append("\\i0 ")
            if self.open_tags and self.open_tags[-1] == "i":
                self.open_tags.pop()
            return
        if t == "u":
            self.parts.append("\\ul0 ")
            if self.open_tags and self.open_tags[-1] == "u":
                self.open_tags.pop()
            return
        if t in {"p", "div", "li"}:
            self._append_block_break()
            self.block_open = False
            return
        if t in {"ul", "ol"}:
            if self.list_ordered_stack:
                self.list_ordered_stack.pop()
            if self.list_item_index_stack:
                self.list_item_index_stack.pop()
            self.list_depth = max(0, self.list_depth - 1)
            self._append_block_break()
            return

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(_escape_rtf_text(html_unescape(data)))

    def to_rtf_body(self) -> str:
        body = "".join(self.parts).strip()
        if not body:
            return "\\par "
        return body


def _html_to_text(content: str) -> str:
    parser = _HtmlToTextParser()
    parser.feed(str(content or ""))
    parser.close()
    return parser.text()


def _html_to_rtf(content: str) -> str:
    parser = _HtmlToRtfParser()
    parser.feed(str(content or ""))
    parser.close()
    body = parser.to_rtf_body()
    return "{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\viewkind4\\uc1\\pard\\f0\\fs20 " + body + "}"


def _text_to_rtf(text: str) -> str:
    plain = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    escaped = (
        plain.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\t", "\\tab ")
        .replace("\n", "\\par\n")
    )
    return "{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\f0\\fs20 " + escaped + "}"


def _sanitize_filename(name: str) -> str:
    base = FILENAME_SANITIZE.sub("", str(name or "").strip())
    base = base.strip(". ").strip()
    if not base:
        base = "Novo modelo"
    return base[:120]


def _next_available_filename(db: Session, clinica_id: int, tipo_modelo: str, filename: str) -> str:
    stem = Path(filename).stem
    ext = Path(filename).suffix
    candidate = filename
    counter = 2
    while True:
        exists = (
            db.query(ModeloDocumento.id)
            .filter(
                ModeloDocumento.clinica_id == int(clinica_id),
                ModeloDocumento.tipo_modelo == str(tipo_modelo),
                ModeloDocumento.nome_arquivo == candidate,
            )
            .first()
        )
        if not exists:
            return candidate
        candidate = f"{stem} {counter}{ext}"
        counter += 1


def _serialize_item(item: ModeloDocumento) -> dict:
    return {
        "id": int(item.id),
        "nome": str(item.nome_exibicao or "").strip(),
        "tipo_modelo": str(item.tipo_modelo or "").strip(),
        "nome_arquivo": str(item.nome_arquivo or "").strip(),
        "extensao": str(item.extensao or "").strip().lower(),
        "origem": str(item.origem or "").strip(),
        "sistema": item.clinica_id is None,
    }


def _load_content(item: ModeloDocumento) -> str:
    raw = _load_raw_content(item)
    ext = str(item.extensao or "").strip().lower()
    if ext in RTF_RICH_EXTENSIONS or _looks_like_rtf(raw):
        return _rtf_to_text(raw)
    return raw


def _load_content_bundle(item: ModeloDocumento) -> dict:
    raw = _load_raw_content(item)
    ext = str(item.extensao or "").strip().lower()
    if ext in RTF_RICH_EXTENSIONS or _looks_like_rtf(raw):
        html = _rtf_to_html(raw)
        return {
            "text": _rtf_to_text(raw),
            "html": html,
            "format": "html",
        }
    return {
        "text": raw,
        "html": "",
        "format": "text",
    }


def _build_clinic_model_path(clinica_id: int, tipo_modelo: str, nome_arquivo: str) -> tuple[str, Path]:
    rel = Path("saas") / "storage" / "modelos" / "clinicas" / str(int(clinica_id)) / str(tipo_modelo) / str(nome_arquivo)
    abs_path = (PROJECT_DIR / rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return rel.as_posix(), abs_path


def _ensure_editable_item(db: Session, current_user: Usuario, source: ModeloDocumento) -> ModeloDocumento:
    if int(source.clinica_id or 0) == int(current_user.clinica_id):
        return source
    existing = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.clinica_id == int(current_user.clinica_id),
            ModeloDocumento.tipo_modelo == str(source.tipo_modelo or ""),
            ModeloDocumento.nome_arquivo == str(source.nome_arquivo or ""),
        )
        .first()
    )
    if existing:
        return existing
    rel, abs_path = _build_clinic_model_path(
        int(current_user.clinica_id),
        str(source.tipo_modelo or "outros"),
        str(source.nome_arquivo or "novo.txt"),
    )
    copied_content = _load_raw_content(source)
    ext = str(source.extensao or "").strip().lower()
    if ext in RTF_RICH_EXTENSIONS:
        if _looks_like_rtf(copied_content):
            abs_path.write_text(copied_content, encoding="utf-8")
        else:
            abs_path.write_text(_text_to_rtf(copied_content), encoding="utf-8")
    else:
        abs_path.write_text(copied_content, encoding="utf-8")
    clone = ModeloDocumento(
        clinica_id=int(current_user.clinica_id),
        tipo_modelo=str(source.tipo_modelo or "outros"),
        codigo=str(source.codigo or ""),
        nome_exibicao=str(source.nome_exibicao or source.nome_arquivo or "Novo modelo"),
        nome_arquivo=str(source.nome_arquivo or "novo.txt"),
        extensao=str(source.extensao or ".txt"),
        caminho_arquivo=rel,
        ativo=True,
        padrao_clinica=bool(source.padrao_clinica),
        origem="clinica",
    )
    db.add(clone)
    db.flush()
    return clone


def _query_visible_models(db: Session, current_user: Usuario):
    rows = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.ativo.is_(True),
            or_(
                ModeloDocumento.clinica_id == int(current_user.clinica_id),
                ModeloDocumento.clinica_id.is_(None),
            ),
            ModeloDocumento.extensao.in_(tuple(TEXT_EXTENSIONS)),
        )
        .order_by(ModeloDocumento.nome_exibicao.asc(), ModeloDocumento.id.asc())
        .all()
    )
    chosen: dict[tuple[str, str], ModeloDocumento] = {}
    for row in rows:
        key = (
            str(row.tipo_modelo or "").strip().lower(),
            str(row.nome_arquivo or "").strip().lower(),
        )
        prev = chosen.get(key)
        if prev is None:
            chosen[key] = row
            continue
        prev_is_base = prev.clinica_id is None
        cur_is_clinic = int(row.clinica_id or 0) == int(current_user.clinica_id)
        if prev_is_base and cur_is_clinic:
            chosen[key] = row
    items = sorted(
        chosen.values(),
        key=lambda x: (
            str(x.nome_exibicao or "").strip().lower(),
            str(x.tipo_modelo or "").strip().lower(),
            int(x.id or 0),
        ),
    )
    return items


@router.get("/campos")
def listar_campos_editor_textos(
    current_user: Usuario = Depends(get_current_user),
):
    return {
        "campos": list(MERGE_FIELDS_PAYLOAD.get("campos") or []),
        "categorias": list(MERGE_FIELDS_PAYLOAD.get("categorias") or []),
        "categoria_padrao": str(MERGE_FIELDS_PAYLOAD.get("categoria_padrao") or MERGE_DEFAULT_CATEGORY),
    }


@router.get("/modelos")
def listar_modelos_editor_textos(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = _query_visible_models(db, current_user)
    return {"itens": [_serialize_item(item) for item in items]}


@router.get("/modelos/{modelo_id}")
def detalhar_modelo_editor_textos(
    modelo_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.id == int(modelo_id),
            ModeloDocumento.ativo.is_(True),
            or_(
                ModeloDocumento.clinica_id == int(current_user.clinica_id),
                ModeloDocumento.clinica_id.is_(None),
            ),
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado.")
    ext = str(item.extensao or "").strip().lower()
    if ext not in TEXT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de arquivo nao editavel no editor interno.")
    content = _load_content_bundle(item)
    response = _serialize_item(item)
    response["conteudo"] = content["text"]
    response["conteudo_html"] = content["html"]
    response["conteudo_formato"] = content["format"]
    return response


@router.post("/modelos")
def criar_modelo_editor_textos(
    payload: ModeloTextoSalvarPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nome = str(payload.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do modelo.")
    tipo_modelo = _normalize_tipo_modelo(payload.tipo_modelo)
    ext = _normalize_extensao(payload.extensao, ".txt")
    base_filename = f"{_sanitize_filename(nome)}{ext}"
    final_filename = _next_available_filename(db, int(current_user.clinica_id), tipo_modelo, base_filename)
    rel_path, abs_path = _build_clinic_model_path(int(current_user.clinica_id), tipo_modelo, final_filename)

    content = str(payload.conteudo or "")
    content_format = _normalize_content_format(payload.conteudo_formato)
    if ext in RTF_RICH_EXTENSIONS:
        if content_format == "html":
            abs_path.write_text(_html_to_rtf(content), encoding="utf-8")
        else:
            abs_path.write_text(_text_to_rtf(content), encoding="utf-8")
    else:
        if content_format == "html":
            content = _html_to_text(content)
        abs_path.write_text(content, encoding="utf-8")

    item = ModeloDocumento(
        clinica_id=int(current_user.clinica_id),
        tipo_modelo=tipo_modelo,
        codigo=f"{tipo_modelo}:{Path(final_filename).stem}".lower()[:80],
        nome_exibicao=nome[:180],
        nome_arquivo=final_filename,
        extensao=ext,
        caminho_arquivo=rel_path,
        ativo=True,
        padrao_clinica=False,
        origem="clinica",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    response = _serialize_item(item)
    loaded = _load_content_bundle(item)
    response["conteudo"] = loaded["text"]
    response["conteudo_html"] = loaded["html"]
    response["conteudo_formato"] = loaded["format"]
    return response


@router.put("/modelos/{modelo_id}")
def salvar_modelo_editor_textos(
    modelo_id: int,
    payload: ModeloTextoSalvarPayload,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = (
        db.query(ModeloDocumento)
        .filter(
            ModeloDocumento.id == int(modelo_id),
            ModeloDocumento.ativo.is_(True),
            or_(
                ModeloDocumento.clinica_id == int(current_user.clinica_id),
                ModeloDocumento.clinica_id.is_(None),
            ),
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado.")

    editable = _ensure_editable_item(db, current_user, source)
    nome = str(payload.nome or editable.nome_exibicao or "").strip()
    if nome:
        editable.nome_exibicao = nome[:180]
    ext = _normalize_extensao(payload.extensao, str(editable.extensao or ".txt"))
    if ext != str(editable.extensao or "").lower():
        editable.extensao = ext
        stem = Path(str(editable.nome_arquivo or "modelo")).stem
        editable.nome_arquivo = f"{stem}{ext}"
        rel, _ = _build_clinic_model_path(int(current_user.clinica_id), str(editable.tipo_modelo or "outros"), str(editable.nome_arquivo))
        editable.caminho_arquivo = rel

    rel_path, abs_path = _build_clinic_model_path(
        int(current_user.clinica_id),
        str(editable.tipo_modelo or "outros"),
        str(editable.nome_arquivo or "novo.txt"),
    )
    editable.caminho_arquivo = rel_path

    content = str(payload.conteudo or "")
    content_format = _normalize_content_format(payload.conteudo_formato)
    if str(editable.extensao or "").lower() in RTF_RICH_EXTENSIONS:
        if content_format == "html":
            abs_path.write_text(_html_to_rtf(content), encoding="utf-8")
        else:
            abs_path.write_text(_text_to_rtf(content), encoding="utf-8")
    else:
        if content_format == "html":
            content = _html_to_text(content)
        abs_path.write_text(content, encoding="utf-8")

    db.add(editable)
    db.commit()
    db.refresh(editable)
    response = _serialize_item(editable)
    loaded = _load_content_bundle(editable)
    response["conteudo"] = loaded["text"]
    response["conteudo_html"] = loaded["html"]
    response["conteudo_formato"] = loaded["format"]
    return response
