"""
CulturaSP — Crawler de Elevada Cultura
Usa Google Custom Search + Claude para encontrar e curar eventos em SP.
Não depende de scraping direto — funciona no GitHub Actions.
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic
import requests

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_KEY    = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX     = os.environ.get("GOOGLE_CX", "")

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

NOW   = datetime.now()
MES   = NOW.strftime("%B %Y")

QUERIES = [
    f"Theatro Municipal São Paulo programação ópera {MES}",
    f"OSESP concertos Sala São Paulo {MES}",
    f"Cultura Artística São Paulo programação {MES}",
    f"Theatro São Pedro São Paulo programação {MES}",
    f"ópera ballet São Paulo {MES} ingressos",
    f"concerto sinfônico São Paulo {MES}",
    f"recital piano violino São Paulo {MES}",
    f"Tiquequê agenda shows {MES}",
    f"Palavra Cantada agenda {MES}",
    f"MASP exposições em cartaz {MES}",
    f"Pinacoteca São Paulo exposições {MES}",
    f"IMS São Paulo exposição {MES}",
    f"Japan House São Paulo exposição {MES}",
    f"Espaço Itaú cinema clássicos retrô São Paulo {MES}",
    f"CineSesc filmes arte clássicos {MES}",
    f"É Realizações lançamentos livros {MES}",
    f"Cultor de Livros lançamentos {MES}",
    f"Quadrante Editora lançamentos {MES}",
]

# ---------------------------------------------------------------------------
# Google Custom Search
# ---------------------------------------------------------------------------

def google_search(query: str, num: int = 5) -> list:
    if not GOOGLE_KEY or not GOOGLE_CX:
        return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_KEY, "cx": GOOGLE_CX, "q": query, "num": num, "lr": "lang_pt", "gl": "br"}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        return [{"title": i.get("title",""), "snippet": i.get("snippet",""), "url": i.get("link","")} for i in items]
    except Exception as e:
        print(f"   ⚠️  Google erro: {e}")
        return []

# ---------------------------------------------------------------------------
# Extração com IA
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = "Você extrai eventos culturais de resultados de busca. Retorne APENAS array JSON válido."

def extract_from_snippets(snippets: list) -> list:
    if not snippets:
        return []
    snippets_text = "\n\n".join([f"Título: {s['title']}\nURL: {s['url']}\nTrecho: {s['snippet']}" for s in snippets])
    prompt = f"""Extraia eventos, exposições, filmes ou livros culturais em São Paulo ({MES}).

Para cada item retorne:
{{"title":"nome","description":"descrição","date":"data/período","venue":"local","price":"preço","url":"URL","category":"evento|exposição|filme|livro","source":"instituição"}}

Se não encontrar nada claro, retorne [].

Resultados:
{snippets_text}"""
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=2048,
            system=EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = re.sub(r"^```json\s*|\s*```$", "", msg.content[0].text.strip())
        items = json.loads(raw)
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"   ⚠️  Extração erro: {e}")
        return []

# ---------------------------------------------------------------------------
# Curadoria
# ---------------------------------------------------------------------------

CURATE_SYSTEM = "Você é um curador de alta cultura clássico e conservador. Retorne APENAS objeto JSON válido."

CURATE_PROMPT = """Avalie este item cultural.

APROVAR: ópera, ballet clássico, concerto/recital clássico, teatro de texto canônico
(Shakespeare, Molière, Tchekhov, Ibsen), infantil de qualidade (Tiquequê, Palavra Cantada),
exposição de grandes mestres/acervo clássico, filme clássico ou de autor consagrado,
livro de filosofia/teologia/história/literatura clássica.

REJEITAR: tema identitário (gênero, raça como protagonismo político, LGBT), subversão,
transgressão, "decolonial", dança contemporânea, performance, instalação conceitual,
linguagem ativista ("corpos dissidentes", "narrativas apagadas", "colonialidade").

Para ópera/teatro: julgue pela OBRA, não pela direção cênica. Wagner/Verdi/Mozart = APROVAR.
NA DÚVIDA: REJEITAR.

Item: {item_json}

Retorne: {{"approved":true/false,"score":1-10,"category_label":"Ópera|Ballet|Orquestra|Recital|Teatro|Infantil|Exposição|Cinema|Livro","curator_note":"até 15 palavras"}}"""

def curate_item(item: dict):
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=300,
            system=CURATE_SYSTEM,
            messages=[{"role": "user", "content": CURATE_PROMPT.format(item_json=json.dumps(item, ensure_ascii=False))}],
        )
        raw = re.sub(r"^```json\s*|\s*```$", "", msg.content[0].text.strip())
        result = json.loads(raw)
        return {**item, **result} if result.get("approved") else None
    except Exception as e:
        print(f"   ⚠️  Curadoria erro: {e}")
        return None

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run():
    print("=" * 60)
    print(f"  CULTURA SP — {NOW.strftime('%d/%m/%Y %H:%M')} — {MES}")
    print("=" * 60)

    if not GOOGLE_KEY or not GOOGLE_CX:
        print("\n⚠️  GOOGLE_API_KEY ou GOOGLE_CX ausentes. Configure os secrets no GitHub.\n")

    all_raw = []
    for query in QUERIES:
        print(f"\n🔍 {query[:65]}...")
        snippets = google_search(query)
        if not snippets:
            print("   0 resultados")
            continue
        items = extract_from_snippets(snippets)
        print(f"   {len(items)} item(ns)")
        all_raw.extend(items)
        time.sleep(0.3)

    # Dedup
    seen, deduped = set(), []
    for item in all_raw:
        key = re.sub(r"\s+", " ", item.get("title","").lower().strip())[:60]
        fk = f"{key}|{str(item.get('date',''))[:15]}"
        if key and fk not in seen:
            seen.add(fk)
            deduped.append(item)

    print(f"\n📦 Total: {len(all_raw)} | Dedup: {len(deduped)}")

    # Curadoria
    print(f"\n🎭 Curando {len(deduped)} itens...")
    curated = []
    for i, item in enumerate(deduped, 1):
        print(f"  [{i:2d}/{len(deduped)}] {item.get('title','')[:50]}...", end=" ", flush=True)
        result = curate_item(item)
        if result:
            curated.append(result)
            print(f"✅ ({result.get('category_label','')} · {result.get('score','')})")
        else:
            print("❌")
        time.sleep(0.2)

    print(f"\n✨ Aprovados: {len(curated)} de {len(deduped)}")

    ORDER = {"evento":0,"exposição":1,"filme":2,"livro":3}
    curated.sort(key=lambda e: (ORDER.get(e.get("category","evento"),9), e.get("date","")))

    out = {"updated_at": NOW.isoformat(), "total": len(curated), "events": curated}
    out_path = DATA_DIR / "events.js"
    out_path.write_text(f"window.CULTURA_EVENTS = {json.dumps(out, ensure_ascii=False, indent=2)};", encoding="utf-8")
    print(f"\n💾 Salvo em {out_path}\n")

if __name__ == "__main__":
    run()
