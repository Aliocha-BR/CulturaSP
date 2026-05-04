# Cultura SP

Curadoria semanal de elevada cultura em São Paulo: ópera, música clássica,
ballet, teatro clássico, exposições, cinema de arte e livros.

## Como configurar (uma vez só)

### 1. Criar conta no GitHub
Acesse **github.com** e crie uma conta gratuita.

### 2. Criar o repositório
- Clique em **New repository**
- Nome sugerido: `cultura-sp`
- Marque **Public** (necessário para o GitHub Pages gratuito)
- Clique em **Create repository**

### 3. Subir os arquivos
Na página do repositório recém-criado, clique em **uploading an existing file**
e arraste todos estes arquivos:
```
index.html
crawler.py
requirements.txt
data/events.js
.github/workflows/atualizar.yml
```
> Atenção: o arquivo `.github/workflows/atualizar.yml` precisa manter
> exatamente essa estrutura de pastas. Use o botão de upload de pasta
> ou arraste a pasta `.github` inteira.

### 4. Adicionar a chave da Anthropic
- No repositório, vá em **Settings → Secrets and variables → Actions**
- Clique em **New repository secret**
- Nome: `ANTHROPIC_API_KEY`
- Valor: sua chave `sk-ant-api03-...`
- Clique em **Add secret**

### 5. Ativar o GitHub Pages
- Vá em **Settings → Pages**
- Em **Source**, selecione **Deploy from a branch**
- Branch: `main`, pasta: `/ (root)`
- Clique em **Save**

Após alguns minutos, seu site estará em:
`https://SEU_USUARIO.github.io/cultura-sp`

### 6. Rodar o crawler pela primeira vez
- Vá em **Actions → Atualizar Eventos**
- Clique em **Run workflow → Run workflow**
- Aguarde ~3 minutos

Após rodar, atualize a página do site — os eventos aparecerão.

## Uso no celular

Abra `https://SEU_USUARIO.github.io/cultura-sp` no Safari (iPhone) ou Chrome (Android)
e adicione à tela inicial:
- **iPhone**: botão de compartilhar → "Adicionar à Tela de Início"
- **Android**: menu (⋮) → "Adicionar à tela inicial"

O site funciona como um app — sem instalar nada.

## Atualização automática

O crawler roda automaticamente toda **segunda-feira às 8h** (horário de Brasília).
Você também pode rodar manualmente a qualquer momento em **Actions → Run workflow**.

## Custo estimado

~$0,05–0,15 por rodada da API Anthropic (dependendo do número de eventos).
Com $5 de crédito, você tem meses de uso.
