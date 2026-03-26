# AI Chatbot — LLM Provider Options

Notes for future production implementation. Current setup uses **Ollama + llama3.2:latest** running in-cluster on Minikube (CPU only) — response time is 2-3 minutes. This document outlines faster alternatives.

---

## Why it's slow now

The bottleneck is **hardware, not architecture**. Minikube runs on your Mac mini sharing CPU cores with everything else. No GPU, no dedicated compute. LLM inference on CPU is inherently slow regardless of which model or framework you use.

The K8s architecture is already correct — it's just waiting for real hardware behind it.

---

## Option 1 — Smaller local model (`llama3.2:1b`)

Fastest path, zero code changes. Just change the model name in `k8s/deployment.yaml` and the Ollama initContainer.

**Change in `k8s/ollama-deployment.yaml`:**
```yaml
# initContainer — change pull target
ollama pull llama3.2:1b

# also update the deployment env var in k8s/deployment.yaml:
- name: OLLAMA_MODEL
  value: "llama3.2:1b"
```

| | Current (3B) | 1B model |
|---|---|---|
| Response time (CPU) | 2-3 min | ~40-60s |
| Model size | ~2 GB | ~0.7 GB |
| Answer quality | Good | Noticeably worse |
| Code changes | — | Model name only |

**Best for:** dev/testing when you need it faster but want to stay fully local.

---

## Option 2 — Groq API (cloud, fastest)

Groq runs llama3 on custom LPU hardware. Free tier is generous. ~2s response time.

**Free tier:** 14,400 requests/day  
**Sign up:** https://console.groq.com  
**Models available:** `llama3-8b-8192`, `llama3-70b-8192`, `mixtral-8x7b-32768`

### Implementation

**1. Add to `requirements.txt`:**
```
langchain-groq>=0.2.0
```

**2. Add secret to K8s:**
```bash
kubectl create secret generic ai-secrets \
  --from-literal=groq-api-key=gsk_your_key_here \
  -n ca-system
```

**3. Add env var to `k8s/deployment.yaml`:**
```yaml
- name: LLM_PROVIDER
  value: "groq"
- name: GROQ_API_KEY
  valueFrom:
    secretKeyRef:
      name: ai-secrets
      key: groq-api-key
```

**4. Update `app/ai_chat.py` — replace `_call_ollama`:**
```python
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")  # ollama | groq | mistral

def _get_llm():
    if LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama3-8b-8192",
            api_key=os.environ["GROQ_API_KEY"],
            temperature=0.3,
        )
    elif LLM_PROVIDER == "mistral":
        from langchain_mistralai import ChatMistralAI
        return ChatMistralAI(
            model="mistral-small-latest",
            api_key=os.environ["MISTRAL_API_KEY"],
            temperature=0.3,
        )
    else:
        from langchain_ollama import OllamaLLM
        return OllamaLLM(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.3,
        )
```

---

## Option 3 — Mistral API (cloud, best free tier)

Similar speed to Groq (~3s). Better free tier for high volume.

**Free tier:** 1 billion tokens/month  
**Sign up:** https://console.mistral.ai  
**Models:** `mistral-small-latest`, `mistral-medium-latest`, `mistral-large-latest`

### Implementation

Same pattern as Groq above — set `LLM_PROVIDER=mistral` and `MISTRAL_API_KEY` env var.

**Add to `requirements.txt`:**
```
langchain-mistralai>=0.2.0
```

---

## Option 4 — Own server with GPU (best long-term)

With a GPU node, Ollama responds in ~2s — fully local, no API cost, no data leaving the cluster. The existing K8s architecture (`ollama-deployment.yaml`) already supports this — just needs real hardware behind it.

| Hardware | Approx. cost | Response time |
|---|---|---|
| Hetzner GX2-32 (CPU only, 16 vCPU) | ~€0.40/hr | ~30-60s |
| Hetzner AX102 (dedicated, no GPU) | ~€299/mo | ~20-40s |
| RunPod RTX 4090 (GPU) | ~€0.74/hr | **~1-2s** |
| Own server + RTX 3090 | one-time ~€800 | **~1-2s** |
| Own server + RTX 4090 | one-time ~€1500 | **~1-2s** |

**Note on Cloudflare:** Cloudflare is DNS/CDN/networking — not compute. It sits in front of your server but does not run inference. Cloudflare Workers AI exists as a separate product but is a different architecture entirely.

---

## Comparison summary

| Option | Response time | Cost | Privacy | Code change needed |
|---|---|---|---|---|
| Ollama llama3.2:1b (now) | ~40-60s | Free | ✅ Fully local | Model name only |
| Ollama llama3.2:3B (now) | 2-3 min | Free | ✅ Fully local | — |
| **Groq API** | **~2s** | Free (14.4K req/day) | ❌ Data leaves cluster | Small |
| **Mistral API** | **~3s** | Free (1B tokens/month) | ❌ Data leaves cluster | Small |
| Own GPU server + Ollama | ~1-2s | Hardware cost | ✅ Fully local | None |

---

## Recommended path

| Stage | Provider | Reason |
|---|---|---|
| Now (dev/demo) | Groq or Mistral API | Fast, free, 30-min integration |
| Production (early) | Groq/Mistral API | Until user volume justifies own hardware |
| Production (scale) | Own GPU server + Ollama | Fully local, fast, no per-request cost |

The `LLM_PROVIDER` env var approach above means switching between them is a single K8s secret + env var change — no redeploy of application code needed.
