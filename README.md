# Video Cortes

App local para download de vídeos do YouTube e X (Twitter) e cortes básicos, com API em FastAPI + yt-dlp/FFmpeg e frontend Nuxt 3 + Vuetify.

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução

## Subir o projeto

```bash
docker compose up --build
```

Abra no navegador: [http://localhost:3101](http://localhost:3101)

- UI (Nuxt): porta `3101`
- API (FastAPI): porta `5101` — docs em [http://localhost:5101/docs](http://localhost:5101/docs)

## Onde ficam os arquivos

- Downloads: `./data/downloads`
- Cortes exportados: `./data/cortes`

Cortes gerados usam o padrão `{nome}_corte_01.mp4`, `_02`, etc.

## Uso

### Download

1. Cole a URL de um vídeo do YouTube ou do X (`x.com` / `twitter.com`)
2. Clique em **Baixar** — a origem é detectada automaticamente
3. Acompanhe o progresso e veja o arquivo na lista

### Cortes

1. Na lista, clique em **Cortar** no arquivo desejado
2. Use o player e a timeline para navegar
3. **Adicionar corte** (ou duplo clique na timeline) insere marcadores
4. Os segmentos entre os cortes são numerados na linha de edição
5. Com **2 linhas** posicionadas, clique em **Salvar trecho** para gerar o arquivo do intervalo entre elas em `./data/cortes`

## Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.12, FastAPI, yt-dlp, FFmpeg |
| Frontend | Vue 3, Nuxt 3, Vuetify 3 |
| Estilos | CSS3 + Vuetify (sem Tailwind) |
| Infra | Docker Compose |

## Aviso

Use apenas com conteúdo que você tem autorização para baixar e armazenar. A responsabilidade pelo uso é de quem opera a ferramenta.

## Desenvolvimento (opcional)

API local sem Docker (requer Python, FFmpeg e yt-dlp):

```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5101
```

Frontend:

```bash
cd web
npm install
NUXT_API_URL=http://127.0.0.1:5101 npm run dev
```
