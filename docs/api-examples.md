# API request examples

Interactive OpenAPI docs: `http://localhost:8000/docs`  
Base URL below assumes `http://localhost:8000`.

## Auth

```bash
# Register employee
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"newhire@example.com","password":"password123","full_name":"New Hire"}' | jq

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123"}' | jq -r .access_token)

curl -s http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN" | jq
```

## Documents (admin)

```bash
# Upload a sample policy
curl -s -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F title='HR PTO Policy' \
  -F department='HR' \
  -F category='Benefits' \
  -F file=@sample-documents/hr-pto-policy.txt | jq

# List
curl -s 'http://localhost:8000/api/v1/documents?q=PTO' \
  -H "Authorization: Bearer $TOKEN" | jq

# Reprocess
DOC_ID=<uuid>
curl -s -X POST "http://localhost:8000/api/v1/documents/$DOC_ID/reprocess" \
  -H "Authorization: Bearer $TOKEN" | jq
```

## Search & RAG

```bash
# Keyword search
curl -s 'http://localhost:8000/api/v1/search?q=expense' \
  -H "Authorization: Bearer $TOKEN" | jq

# Semantic search
curl -s -X POST http://localhost:8000/api/v1/search/semantic \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"query":"How many PTO days do employees get?","top_k":5}' | jq

# Ask a grounded question
CONV=$(curl -s -X POST http://localhost:8000/api/v1/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"PTO"}' | jq -r .id)

curl -s -X POST "http://localhost:8000/api/v1/conversations/$CONV/messages" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"content":"How many PTO days do employees receive?"}' | jq
```

## Health & admin

```bash
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8000/ready | jq

curl -s 'http://localhost:8000/api/v1/admin/analytics' \
  -H "Authorization: Bearer $TOKEN" | jq '.total_documents,.average_llm_latency_ms'

curl -s 'http://localhost:8000/api/v1/admin/ingestion-jobs?limit=10' \
  -H "Authorization: Bearer $TOKEN" | jq
```
