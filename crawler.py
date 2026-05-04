"""
CulturaSP — Crawler de Elevada Cultura
Coleta eventos de São Paulo capital: ópera, teatro clássico, orquestra,
ballet, infantil de qualidade, exposições, filmes de arte e livros de
editoras conservadoras.
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------

SOURCES = [
    # — Eventos ao vivo —
    {
        "name": "Theatro Municipal",
        "url": "https://www.theatromunicipal.org.br/programacao/",
        "category": "evento",
        "hint": "ópera, ballet, orquestra, recitais",
    },
    {
        "name": "OSESP",
        "url": "https://osesp.art.br/osesp/concertos-ingressos",
        "category": "evento",
        "hint": "concertos sinfônicos, câmara, recitais",
    },
    {
        "name": "Sala São Paulo",
        "url": "https://www.salasaopaulo.art.br/programacao/",
        "category": "evento",
        "hint": "concertos, recitais, câmara",
    },
    {
        "name": "Cultura Artística",
        "url": "https://www.culturaartistica.com.br/programacao",
        "category": "evento",
        "hint": "grandes nomes da música clássica, ópera, recitais internacionais",
    },
    {
        "name": "Theatro São Pedro",
        "url": "https://www.theatrosaopedro.org.br/programacao",
        "category": "evento",
        "hint": "ópera, teatro clássico, música",
    },
    {
        "name": "Tiquequê",
        "url": "https://www.tiqueteke.com.br/agenda",
        "category": "evento",
        "hint": "espetáculos musicais infantis de qualidade",
    },
    {
        "name": "Palavra Cantada",
        "url": "https://www.palavracantada.com.br/agenda",
        "category": "evento",
        "hint": "música infantil de qualidade, shows educativos",
    },
    # — Exposições —
    {
        "name": "MASP",
        "url": "https://masp.org.br/exposicoes",
        "category": "exposição",
        "hint": "exposições de arte — incluir acervo clássico e grandes mestres; rejeitar temáticas identitárias",
    },
    {
        "name": "Pinacoteca",
        "url": "https://pinacoteca.org.br/programacao/",
        "category": "exposição",
        "hint": "arte brasileira clássica e moderna",
    },
    {
        "name": "IMS São Paulo",
        "url": "https://ims.com.br/programacao/",
        "category": "exposição",
        "hint": "fotografia, artes visuais de alto nível",
    },
    {
        "name": "MIS",
        "url": "https://www.mis-sp.org.br/programacao",
        "category": "exposição",
        "hint": "cinema, fotografia, artes audiovisuais",
    },
    # — Filmes —
    {
        "name": "Espaço Itaú de Cinema",
        "url": "https://www.itaucinemas.com.br/espaco-itau",
        "category": "filme",
        "hint": "cinema de arte, clássicos, retrospectivas, filmes de autor",
    },
    {
        "name": "CineSesc",
        "url": "https://www.sescsp.org.br/programacao/cinema/",
        "category": "filme",
        "hint": "cinema de arte, clássicos, ciclos temáticos, retrospectivas",
    },
    # — Livros —
    {
        "name": "É Realizações",
        "url": "https://erealizacoes.com.br/lancamentos/",
        "category": "livro",
        "hint": "filosofia, teologia, história, pensamento clássico e conservador",
    },
    {
        "name": "Cultor de Livros",
        "url": "https://www.cultordelivros.com.br/lancamentos",
        "category": "livro",
        "hint": "filosofia clássica, espiritualidade, cultura ocidental",
    },
    {
        "name": "Quadrante",
        "url": "https://www.quadrante.com.br/novidades",
        "category": "livro",
        "hint": "teologia, filosofia escolástica, espiritualidade católica",
    },
]

# ---------------------------------------------------------------------------
# Coleta de HTML
# ---------------------------------------------------------------------------

def fetch_text(url: str, max_chars: int = 40_000) -> str:
    """Baixa a página e retorna texto limpo (sem tags, scripts, estilos)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # Compacta linhas em branco
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"ERRO: {e}"

# ---------------------------------------------------------------------------
# Extração com IA
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = """Você extrai informações de eventos, exposições, filmes ou livros
a partir de texto bruto de páginas web. Retorne APENAS um array JSON válido.
Nenhum texto fora do JSON. Nenhum markdown. Nenhum comentário."""

def extract_items(source: dict, page_text: str) -> list[dict]:
    """Usa Claude Haiku para extrair itens estruturados da página."""

    if page_text.startswith("ERRO:"):
        return []

    category = source["category"]
    hint = source["hint"]
    source_name = source["name"]

    if category == "livro":
        schema = """{
  "title": "Título do livro",
  "author": "Autor",
  "description": "Sinopse ou descrição breve",
  "publisher": "Editora",
  "date": "Data de lançamento se disponível",
  "price": "Preço se disponível",
  "url": "URL de compra se disponível",
  "category": "livro"
}"""
        instruction = (
            f"Extraia livros lançados nos últimos 3 meses do site '{source_name}'. "
            f"Contexto: {hint}. "
            "Retorne array JSON com os campos acima. Array vazio [] se não encontrar nada."
        )
    elif category == "filme":
        schema = """{
  "title": "Título do filme",
  "director": "Diretor se mencionado",
  "description": "Sinopse ou descrição",
  "date": "Datas/horários de exibição",
  "venue": "Nome do cinema/sala",
  "price": "Preço se disponível",
  "url": "Link para ingresso/informação",
  "category": "filme"
}"""
        instruction = (
            f"Extraia filmes em cartaz do site '{source_name}'. "
            f"Contexto: {hint}. "
            "Retorne array JSON com os campos acima. Array vazio [] se não encontrar nada."
        )
    elif category == "exposição":
        schema = """{
  "title": "Título da exposição",
  "artist": "Artista(s) ou curador",
  "description": "Descrição da exposição",
  "date": "Período da exposição (datas de início e fim)",
  "venue": "Nome do museu/espaço",
  "price": "Preço se disponível",
  "url": "Link para mais informações",
  "category": "exposição"
}"""
        instruction = (
            f"Extraia exposições em cartaz do site '{source_name}'. "
            f"Contexto: {hint}. "
            "Retorne array JSON com os campos acima. Array vazio [] se não encontrar nada."
        )
    else:  # evento ao vivo
        schema = """{
  "title": "Nome do espetáculo",
  "description": "Descrição do evento",
  "date": "Data e horário (cada apresentação separada)",
  "venue": "Local/teatro",
  "price": "Preço do ingresso se disponível",
  "url": "Link para ingresso ou mais informações",
  "category": "evento"
}"""
        instruction = (
            f"Extraia eventos em cartaz do site '{source_name}'. "
            f"Contexto: {hint}. "
            "IMPORTANTE: cada apresentação em data diferente deve ser um item separado. "
            "Retorne array JSON com os campos acima. Array vazio [] se não encontrar nada."
        )

    prompt = f"{instruction}\n\nSchema de cada item:\n{schema}\n\nTexto da página:\n{page_text}"

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Remove possíveis blocos markdown
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        items = json.loads(raw)
        if not isinstance(items, list):
            return []
        # Injeta fonte
        for item in items:
            item["source"] = source_name
            if not item.get("venue") and category == "evento":
                item["venue"] = source_name
        return items
    except Exception as e:
        print(f"   ⚠️  Erro na extração IA: {e}")
        return []

# ---------------------------------------------------------------------------
# Curadoria com IA
# ---------------------------------------------------------------------------

CURATE_SYSTEM = """Você é um curador de alta cultura com gosto clássico e conservador.
Avalie o item e retorne APENAS um objeto JSON válido. Nenhum texto fora do JSON."""

CURATE_PROMPT = """Avalie este item cultural segundo os critérios abaixo.

=== CRITÉRIOS DE APROVAÇÃO ===
APROVAR se for:
- Ópera (qualquer título do repertório lírico)
- Ballet clássico (repertório tradicional: Lago dos Cisnes, Giselle, etc.)
- Concerto sinfônico, de câmara ou recital (piano, cordas, voz)
- Teatro de texto clássico (Shakespeare, Molière, Tchekhov, Ibsen, Sófocles,
  Eurípides, Schiller e outros do cânone ocidental)
- Espetáculo infantil musical de qualidade reconhecida (Tiquequê, Palavra Cantada)
- Exposição de acervo clássico, grandes mestres ou fotografia de alto nível artístico
- Filme clássico, de diretor consagrado, retrospectiva ou cinema de arte
- Livro de filosofia clássica, teologia, história, literatura canônica ou
  pensamento conservador publicado nos últimos 3 meses

=== CRITÉRIOS DE REJEIÇÃO ===
REJEITAR se houver qualquer sinal de:
- Tema central identitário (gênero, raça como protagonismo político, LGBT)
- Proposta de subversão, transgressão, desconstrução ou "resistência"
- Teatro experimental sem texto canônico
- Dança contemporânea, performance, instalação conceitual
- Linguagem ativista: "decolonial", "corpos dissidentes", "narrativas apagadas",
  "lugar de fala", "representatividade", "vozes silenciadas"
- Arte cujo objetivo principal é provocar, chocar ou questionar valores tradicionais

IMPORTANTE: para óperas e peças de teatro, julgue pela OBRA (compositor, título, repertório),
não pela direção cênica. Uma montagem contemporânea de Wagner, Verdi, Mozart ou Puccini
deve ser APROVADA. Só rejeite se a própria obra for de vanguarda política.

NA DÚVIDA: REJEITAR.

=== ITEM A AVALIAR ===
{item_json}

=== RETORNE ESTE JSON ===
{{
  "approved": true ou false,
  "score": número de 1 a 10 (qualidade cultural estimada),
  "category_label": "Ópera" | "Ballet" | "Orquestra" | "Recital" | "Teatro" |
                    "Infantil" | "Exposição" | "Cinema" | "Livro",
  "curator_note": "frase curta justificando a decisão (máx 15 palavras)"
}}"""


def curate_item(item: dict) -> dict | None:
    """Avalia um item e retorna dict enriquecido ou None se rejeitado."""
    prompt = CURATE_PROMPT.format(item_json=json.dumps(item, ensure_ascii=False))
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=CURATE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        if not result.get("approved"):
            return None
        # Mescla avaliação com dados originais
        return {**item, **result}
    except Exception as e:
        print(f"   ⚠️  Erro na curadoria: {e}")
        return None

# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run():
    print("=" * 60)
    print("  CULTURA SP — Crawler de Elevada Cultura")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    all_raw = []

    # 1. Coleta e extração
    for source in SOURCES:
        print(f"\n📡 {source['name']}...")
        text = fetch_text(source["url"])
        if text.startswith("ERRO:"):
            print(f"   ⚠️  {text}")
            continue
        items = extract_items(source, text)
        print(f"   {len(items)} item(ns) extraído(s)")
        all_raw.extend(items)
        time.sleep(0.5)

    # 2. Deduplicação por título normalizado
    seen = set()
    deduped = []
    for item in all_raw:
        key = re.sub(r"\s+", " ", item.get("title", "").lower().strip())[:60]
        date_key = item.get("date", "")[:20]
        full_key = f"{key}|{date_key}"
        if key and full_key not in seen:
            seen.add(full_key)
            deduped.append(item)

    print(f"\n📦 Total bruto: {len(all_raw)} | Após dedup: {len(deduped)}")

    # 3. Curadoria
    print(f"\n🎭 Curando {len(deduped)} itens...")
    curated = []
    for i, item in enumerate(deduped, 1):
        preview = item.get("title", "")[:50]
        print(f"  [{i:2d}/{len(deduped)}] {preview}...", end=" ", flush=True)
        result = curate_item(item)
        if result:
            curated.append(result)
            print(f"✅ ({result.get('category_label', '')} • {result.get('score', '')})")
        else:
            print("❌")
        time.sleep(0.2)

    print(f"\n✨ Aprovados: {len(curated)} de {len(deduped)}")

    # 4. Ordena: eventos primeiro por data, depois exposições, filmes, livros
    def sort_key(item):
        order = {"evento": 0, "exposição": 1, "filme": 2, "livro": 3}
        cat = item.get("category", "evento")
        return (order.get(cat, 9), item.get("date", ""))

    curated.sort(key=sort_key)

    # 5. Salva
    output = {
        "updated_at": datetime.now().isoformat(),
        "total": len(curated),
        "events": curated,
    }
    payload = json.dumps(output, ensure_ascii=False, indent=2)
    out_path = DATA_DIR / "events.js"
    out_path.write_text(f"window.CULTURA_EVENTS = {payload};", encoding="utf-8")
    print(f"\n💾 Salvo em {out_path}")
    print("Abra index.html no navegador para ver os eventos!\n")


if __name__ == "__main__":
    run()
