"""
CulturaSP — Crawler de Elevada Cultura
Usa Claude com web_search nativo para encontrar e curar eventos em SP.
Só precisa da chave Anthropic — sem dependências externas de busca.
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

NOW = datetime.now()
MES = NOW.strftime("%B %Y")

QUERIES = [
    f"Theatro Municipal São Paulo programação ópera {MES}",
    f"OSESP concertos Sala São Paulo {MES}",
    f"Cultura Artística São Paulo programação {MES}",
    f"Theatro São Pedro São Paulo programação {MES}",
    f"ópera ballet concerto sinfônico São Paulo {MES}",
    f"Tiquequê Palavra Cantada agenda shows {MES}",
    f"MASP Pinacoteca IMS exposições em cartaz {MES}",
    f"Japan House São Paulo exposição {MES}",
    f"Espaço Itaú CineSesc cinema clássico arte São Paulo {MES}",
    f"É Realizações Cultor Quadrante lançamentos livros {MES}",
]

EXTRACT_SYSTEM = "Você extrai eventos culturais de resultados de busca. Retorne APENAS array JSON válido. Nenhum texto fora do JSON."

EXTRACT_PROMPT = """A partir dos resultados de busca abaixo, extraia todos os eventos,
exposições, filmes ou livros culturais em São Paulo ({mes}).

Para cada item retorne:
{{"title":"nome","description":"descrição","date":"data/período","venue":"local","price":"preço se mencionado","url":"URL mais relevante","category":"evento|exposição|filme|livro","source":"instituição"}}

Se não encontrar nada claro, retorne [].

Resultados:
{results}"""

def search_and_extract(query: str) -> list:
    """Usa Claude com web_search para buscar e extrair eventos."""
    try:
        # Passo 1: busca na web via Anthropic
        search_response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": f"Busque informações sobre: {query}"}],
        )

        # Extrai o texto dos resultados
        results_text = ""
        for block in search_response.content:
            if hasattr(block, "type") and block.type == "text":
                results_text += block.text + "\n"
            elif hasattr(block, "type") and block.type == "tool_result":
                results_text += str(block.content) + "\n"

        if not results_text.strip():
            return []

        # Passo 2: extrai eventos estruturados
        extract_response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=EXTRACT_SYSTEM,
            messages=[{
                "role": "user",
                "content": EXTRACT_PROMPT.format(mes=MES, results=results_text[:6000])
            }],
        )

        raw = extract_response.content[0].text.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw)
        items = json.loads(raw)
        return items if isinstance(items, list) else []

    except Exception as e:
        print(f"   ⚠️  Erro: {e}")
        return []


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
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=CURATE_SYSTEM,
            messages=[{"role": "user", "content": CURATE_PROMPT.format(
                item_json=json.dumps(item, ensure_ascii=False)
            )}],
        )
        raw = re.sub(r"^```json\s*|\s*```$", "", msg.content[0].text.strip())
        result = json.loads(raw)
        return {**item, **result} if result.get("approved") else None
    except Exception as e:
        print(f"   ⚠️  Curadoria erro: {e}")
        return None


def run():
    print("=" * 60)
    print(f"  CULTURA SP — {NOW.strftime('%d/%m/%Y %H:%M')} — {MES}")
    print("=" * 60)

    all_raw = []
    for query in QUERIES:
        print(f"\n🔍 {query[:65]}...")
        items = search_and_extract(query)
        print(f"   {len(items)} item(ns)")
        all_raw.extend(items)
        time.sleep(1)

    # Dedup
    seen, deduped = set(), []
    for item in all_raw:
        key = re.sub(r"\s+", " ", item.get("title", "").lower().strip())[:60]
        fk = f"{key}|{str(item.get('date',''))[:15]}"
        if key and fk not in seen:
            seen.add(fk)
            deduped.append(item)

    print(f"\n📦 Total: {len(all_raw)} | Dedup: {len(deduped)}")

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
        time.sleep(0.3)

    print(f"\n✨ Aprovados: {len(curated)} de {len(deduped)}")

    ORDER = {"evento": 0, "exposição": 1, "filme": 2, "livro": 3}
    curated.sort(key=lambda e: (ORDER.get(e.get("category", "evento"), 9), e.get("date", "")))

    out = {"updated_at": NOW.isoformat(), "total": len(curated), "events": curated}
    out_path = DATA_DIR / "events.js"
    out_path.write_text(
        f"window.CULTURA_EVENTS = {json.dumps(out, ensure_ascii=False, indent=2)};",
        encoding="utf-8"
    )
    print(f"\n💾 Salvo em {out_path}\n")


if __name__ == "__main__":
    run()
