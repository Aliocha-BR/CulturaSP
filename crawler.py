"""
CulturaSP — Crawler de Elevada Cultura
Usa Claude com web_search nativo para encontrar e curar eventos em SP.
Busca a temporada ANUAL completa para capturar óperas e ballets com antecedência.
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

NOW  = datetime.now()
MES  = NOW.strftime("%B %Y")   # mês atual ex: "maio 2026"
ANO  = NOW.strftime("%Y")      # ano ex: "2026"

# ---------------------------------------------------------------------------
# Queries — mix de temporada anual (ópera/ballet) + mês corrente (concertos/expo)
# ---------------------------------------------------------------------------

QUERIES = [
    # — Ópera: temporada anual completa —
    f"temporada ópera São Paulo {ANO} Theatro Municipal programação completa",
    f"temporada ópera São Paulo {ANO} Theatro São Pedro programação completa",
    f"ópera São Paulo {ANO} ingressos datas Teatro Bradesco Cultura Artística",

    # — Ballet: temporada anual completa —
    f"ballet clássico São Paulo {ANO} temporada completa Lago dos Cisnes Giselle Quebra-Nozes",
    f"Moscow City Ballet São Paulo {ANO}",
    f"Ballet Clássico São Petersburgo São Paulo {ANO}",
    f"Balé da Cidade São Paulo temporada {ANO}",

    # — Teatro clássico ocidental: por autor —
    f"Shakespeare São Paulo em cartaz {MES} {ANO}",
    f"Molière Tchekhov Ibsen Strindberg peça teatro São Paulo {ANO}",
    f"Dostoiévski Kafka Beckett Brecht teatro São Paulo {ANO}",

    # — Teatro brasileiro clássico: por autor —
    f"Nelson Rodrigues peça teatro São Paulo em cartaz {ANO}",
    f"Ariano Suassuna peça teatro São Paulo {ANO}",
    f"Nelson Rodrigues Ariano Suassuna Machado de Assis adaptação teatro São Paulo {ANO}",

    # — Por casa de teatro —
    f"Teatro FAAP programação peças {MES} {ANO}",
    f"Teatro Santander São Paulo programação {MES} {ANO}",
    f"Teatro das Artes São Paulo peças clássicas {MES} {ANO}",
    f"Theatro São Pedro programação peças {MES} {ANO}",

    # — Concertos e recitais: mês corrente —
    f"OSESP concertos Sala São Paulo {MES}",
    f"concerto sinfônico recital piano violino São Paulo {MES}",
    f"Cultura Artística São Paulo programação {MES}",
    f"SESC São Paulo concerto música clássica câmara {MES}",

    # — Exposições: mês corrente —
    f"MASP Pinacoteca IMS exposições em cartaz {MES}",
    f"Japan House São Paulo exposição {MES}",
    f"SESC São Paulo exposição arte fotografia {MES}",

    # — Cinema de arte: mês corrente —
    f"Espaço Itaú CineSesc cinema clássico arte retrospectiva São Paulo {MES}",
    f"SESC São Paulo cinema clássico arte {MES}",

    # — Infantil: mês corrente —
    f"Tiquequê Palavra Cantada agenda shows São Paulo {MES}",

    # — Livros: ano atual —
    f"É Realizações Cultor de Livros Quadrante lançamentos {ANO}",

    # — Ticketing para capturar eventos não divulgados nos sites oficiais —
    f"site:sympla.com.br ópera ballet clássico São Paulo {ANO}",
    f"site:uhuu.com ballet ópera São Paulo {ANO}",
]

# ---------------------------------------------------------------------------
# Busca + extração via Anthropic web_search
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = (
    "Você extrai eventos culturais de resultados de busca. "
    "Retorne APENAS array JSON válido. Nenhum texto fora do JSON."
)

EXTRACT_PROMPT = """Extraia todos os eventos, exposições, filmes ou livros culturais
em São Paulo mencionados abaixo. Inclua eventos futuros de {ano}, mesmo que ainda
não seja o mês deles — especialmente óperas e ballets que esgotam rápido.

Para cada item retorne:
{{"title":"nome","description":"descrição","date":"data ou período completo",
"venue":"local/teatro","price":"preço se mencionado","url":"URL mais relevante",
"category":"evento|exposição|filme|livro","source":"instituição"}}

Se não encontrar nada claro, retorne [].

Resultados:
{results}"""

def search_and_extract(query: str) -> list:
    try:
        # Busca na web via Anthropic
        search_resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": f"Busque: {query}"}],
        )

        # Coleta todo o texto retornado
        results_text = ""
        for block in search_resp.content:
            if hasattr(block, "text"):
                results_text += block.text + "\n"

        if not results_text.strip():
            return []

        # Extrai eventos estruturados
        extract_resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            system=EXTRACT_SYSTEM,
            messages=[{
                "role": "user",
                "content": EXTRACT_PROMPT.format(ano=ANO, results=results_text[:8000])
            }],
        )

        raw = extract_resp.content[0].text.strip()
        raw = re.sub(r"^```json\s*|\s*```$", "", raw)
        items = json.loads(raw)
        return items if isinstance(items, list) else []

    except Exception as e:
        print(f"   ⚠️  Erro: {e}")
        return []

# ---------------------------------------------------------------------------
# Curadoria
# ---------------------------------------------------------------------------

CURATE_SYSTEM = (
    "Você é um curador de alta cultura clássico e conservador. "
    "Retorne APENAS objeto JSON válido."
)

CURATE_PROMPT = """Avalie este item cultural.

APROVAR: ópera do repertório lírico tradicional (Wagner, Verdi, Puccini, Mozart,
Rossini, Offenbach, Giordano, Strauss, Prokofiev, Stravinsky etc), ballet clássico
(Lago dos Cisnes, Giselle, Quebra-Nozes, Dom Quixote, Bela Adormecida etc),
concerto/recital sinfônico ou de câmara com repertório clássico,
teatro de texto canônico ocidental (Shakespeare, Molière, Tchekhov, Ibsen,
Strindberg, Dostoiévski, Brecht, Beckett, Wilde, Racine, Corneille) OU teatro
brasileiro clássico de qualidade (Nelson Rodrigues, Ariano Suassuna, Jorge Andrade,
Machado de Assis adaptado),
infantil de qualidade reconhecida (Tiquequê, Palavra Cantada),
exposição de grandes mestres ou acervo clássico,
filme clássico ou de diretor consagrado, livro de filosofia/teologia/história/
literatura clássica.

REJEITAR: tema identitário (gênero, raça como protagonismo político, LGBT),
subversão, transgressão, "decolonial", dança contemporânea, performance,
instalação conceitual, linguagem ativista ("corpos dissidentes", "narrativas
apagadas", "colonialidade", "escrevivência", "resistência").

Para ópera/teatro: julgue pela OBRA (compositor/autor), não pela direção cênica.
Wagner/Verdi/Mozart/Offenbach/Strauss = APROVAR independente de quem dirige.
Ópera com tema político explícito (campo de concentração, militância) = REJEITAR.

NA DÚVIDA: REJEITAR.

Item: {item_json}

Retorne:
{{"approved":true/false,"score":1-10,
"category_label":"Ópera|Ballet|Orquestra|Recital|Teatro|Infantil|Exposição|Cinema|Livro",
"curator_note":"justificativa em até 15 palavras",
"urgency":"alta|normal"}}

urgency=alta se o evento esgota rápido (ópera, ballet internacional, recital único)."""

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

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run():
    print("=" * 60)
    print(f"  CULTURA SP — {NOW.strftime('%d/%m/%Y %H:%M')}")
    print(f"  Buscando temporada {ANO} + eventos de {MES}")
    print("=" * 60)

    all_raw = []
    for query in QUERIES:
        print(f"\n🔍 {query[:70]}...")
        items = search_and_extract(query)
        print(f"   {len(items)} item(ns)")
        all_raw.extend(items)
        time.sleep(1)

    # Dedup por título + data
    seen, deduped = set(), []
    for item in all_raw:
        key = re.sub(r"\s+", " ", item.get("title", "").lower().strip())[:60]
        fk  = f"{key}|{str(item.get('date', ''))[:20]}"
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
            urgency = "🔴" if result.get("urgency") == "alta" else ""
            print(f"✅ {urgency}({result.get('category_label','')} · {result.get('score','')})")
        else:
            print("❌")
        time.sleep(0.3)

    print(f"\n✨ Aprovados: {len(curated)} de {len(deduped)}")

    # Ordena: urgência alta primeiro, depois por categoria e data
    def sort_key(e):
        urgency_order = 0 if e.get("urgency") == "alta" else 1
        cat_order = {"evento": 0, "exposição": 1, "filme": 2, "livro": 3}
        return (urgency_order, cat_order.get(e.get("category", "evento"), 9), e.get("date", ""))

    curated.sort(key=sort_key)

    out = {"updated_at": NOW.isoformat(), "total": len(curated), "events": curated}
    out_path = DATA_DIR / "events.js"
    out_path.write_text(
        f"window.CULTURA_EVENTS = {json.dumps(out, ensure_ascii=False, indent=2)};",
        encoding="utf-8"
    )
    print(f"\n💾 Salvo em {out_path}\n")

if __name__ == "__main__":
    run()
