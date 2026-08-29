# Corpus snapshots

Ingesting the papers ([`ingest/ingest.py`](../ingest/ingest.py)) re-embeds 400+ papers, which is
slow. These snapshot artifacts let you skip that: they capture the already-ingested data from both
stores so you can restore it in seconds.

| Artifact | Store | Contents |
|---|---|---|
| `paper_chunks.sql.gz` | Postgres | `paper_chunks` rows, including pgvector embeddings |
| `meili_settings.json` | Meilisearch | index settings (searchable/filterable attrs, stop words, ranking rules) |
| `meili_documents.ndjson.gz` | Meilisearch | all documents in the `paper_chunks` index |

All commands below run from the repo root with the stack up
(`docker compose up -d db meilisearch`). They use `${MEILI_MASTER_KEY:-masterkey}`, so either export
`MEILI_MASTER_KEY` or rely on the `masterkey` default.

## Import (skip ingestion)

```bash
# 1. Create the tables first (Postgres) — the snapshot is data-only
uv run python -m db.init_db

# 2. Postgres: load rows (truncate first so re-imports don't duplicate)
docker compose exec -T db psql -U postgres -d sayargyi -c "TRUNCATE paper_chunks"
gunzip -c snapshots/paper_chunks.sql.gz | docker compose exec -T db psql -U postgres -d sayargyi

# 3. Meilisearch: create the index, apply settings, then load documents
curl -s -X POST http://localhost:7700/indexes \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-masterkey}" \
  -H "Content-Type: application/json" \
  --data '{"uid":"paper_chunks","primaryKey":"id"}'

curl -s -X PATCH http://localhost:7700/indexes/paper_chunks/settings \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-masterkey}" \
  -H "Content-Type: application/json" \
  --data-binary @snapshots/meili_settings.json

gunzip -c snapshots/meili_documents.ndjson.gz | curl -s -X POST \
  "http://localhost:7700/indexes/paper_chunks/documents?primaryKey=id" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-masterkey}" \
  -H "Content-Type: application/x-ndjson" \
  --data-binary @-
```

Meilisearch processes document/settings updates asynchronously. Check progress with:

```bash
curl -s http://localhost:7700/tasks?limit=5 \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-masterkey}" | jq '.results[] | {type, status}'
```

Once the tasks show `"status": "succeeded"`, start the app without running ingestion:

```bash
uv run streamlit run app.py
```

## Export (regenerate the snapshot)

Run this after re-ingesting to refresh the committed artifacts. Requires `jq`.

```bash
mkdir -p snapshots

# Postgres: paper_chunks table, data only (schema is created by db.init_db)
docker compose exec -T db pg_dump -U postgres -d sayargyi \
  --data-only --no-owner -t paper_chunks \
  | gzip > snapshots/paper_chunks.sql.gz

# Meilisearch: index settings
curl -s http://localhost:7700/indexes/paper_chunks/settings \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-masterkey}" \
  > snapshots/meili_settings.json

# Meilisearch: all documents as newline-delimited JSON
curl -s "http://localhost:7700/indexes/paper_chunks/documents?limit=1000000" \
  -H "Authorization: Bearer ${MEILI_MASTER_KEY:-masterkey}" \
  | jq -c '.results[]' | gzip > snapshots/meili_documents.ndjson.gz
```

## A note on committing these files

The Postgres dump is dominated by 384-dimension embeddings and can be tens of MB even gzipped. If it
grows past what you want in normal git history, track it with [Git LFS](https://git-lfs.com/):

```bash
git lfs track "snapshots/*.gz"
git add .gitattributes snapshots/
```
