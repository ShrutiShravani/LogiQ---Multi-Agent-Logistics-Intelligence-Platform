# 🚚 LogiQ — Multi-Agent Logistics Intelligence Platform

**LogiQ** is a production-grade multi-agent AI system designed to automate complex logistics workflows—from document ingestion and route mapping to weather-adjusted pricing and forensic validation.

It enables accurate, reliable, and cost-efficient decision-making by replacing manual validation with a state-aware agentic architecture.

---

## ❓ Why LogiQ?

Traditional logistics systems often struggle with operational inefficiencies that lead to significant revenue leakage:

*   **Manual Dependency:** High reliance on manual data entry and human validation.
*   **Operational Errors:** Frequent inaccuracies in weight calculation, route selection, and cost estimation.
*   **Static Logic:** A lack of real-time intelligence to account for external variables like weather or traffic.

---

## ✅ The Solution

LogiQ solves these challenges by utilizing a robust, production-ready AI stack:

*   **Multi-Agent Orchestration:** Specialized agents (Router, Pricer, Auditor) working in a directed graph to handle discrete logistics tasks.
*   **Retrieval-Augmented Decision Pipelines:** Utilizing RAG to extract and verify waybill data against historical and real-time records.
*   **Trust & Safety Validation Layers:** Automated quality gates to ensure pricing integrity and document accuracy.
*   **Cost-Aware System Design:** Optimized to run efficiently on standard hardware (32GB RAM) while maintaining high-concurrency performance.




Architecture Overview-



graph TD 


A[FastAPI Ingestion] --> B{Supervisor}
B --> C[Document Agent: Extraction]
C --> D{Validation}
D -- "Success" --> E[Route Agent: Mapping]
E --> F[Pricing Agent: XGBoost]
F --> G[Critic Agent: Validation]
G -- "Invalid" --> B
F --> I[MLflow & LangSmith: Telemetry]
G --> H[PostgreSQL: Persistence]





⚙️ Core Capabilities



🧠 1. Multi-Agent Orchestration (LangGraph)


- Modular agents for routing, pricing, and validation


- Stateful workflows with retry and correction loops


- Clean separation of responsibilities for scalability


🔎 2. RAG-Based Data Processing


- Processes semi-structured logistics data


- Embedding + retrieval pipeline for contextual decisions


- Structured outputs for downstream agents


🛡️ 3. Trust & Safety (Defense-in-Depth)


- Multi-stage validation pipeline:


- Schema validation (Pydantic)


- Statistical anomaly detection (Z-score)


- LLM-based expert validation (Phi-3)



🔐 4. Guardrails (NeMo)


- Prevents unsafe or invalid outputs


- Ensures system reliability (similar to fraud detection systems)



⚡ 5. Efficiency & Cost Optimization (FinOps)


- Spatial-temporal batching of logistics requests


- Reduces redundant API calls (routing/pricing)


- Improves throughput and cost efficiency



🧱 6. Fault-Tolerant System Design


- Redis caching


- Dead-letter queues


-Circuit breakers


- Ensures high reliability under failure conditions



📊 7. Evaluation & Observability


MLflow → experiment tracking


LangSmith → agent tracing


Metrics: accuracy, latency, system performance




🧠 Core Design Decisions


1. Why Multi-Agent (LangGraph)?


Logistics workflows involve:


- document parsing

- routing

- pricing

- validation



Instead of a single LLM, responsibilities are split into agents via a LangGraph DAG.



✅ Enables:


- modular design


- retry loops

- stateful execution



2. Why Actor–Critic Architecture?


- LLMs are unreliable for critical decisions.


We introduced:


- Actor → performs task (extract, price)


- Critic → validates output deterministically


Critic checks:

weight ≠ 0

parcel consistency

route validity


👉 Invalid outputs trigger automatic retry loops



3. Why XGBoost for Pricing?


LLMs are not ideal for numerical prediction.

XGBoost provides:

- strong performance on tabular logistics data

- interpretable pricing

- low latency


4. Why Redis (Caching)?

Geocoding APIs are:

- expensive

- slow

Redis:

- caches frequent locations

- reduces API calls

- improves latency


5. Why PostgreSQL (State)?

Logistics systems require:

- persistence


- auditability

PostgreSQL enables:


- shipment tracking


- reproducibility


- debugging



📈 Benchmarks

| Metric                        | Value              |
| ----------------------------- | ------------------ |
| Extraction Accuracy           | 96%                |
| Latency (p99)                 | ~9s                |
| Token Cost                    | ~$0.0001 / request |            
| Manual Intervention Reduction | ~80%               |




🔍 Observability


LangSmith → tracing, debugging, cost monitoring


MLflow → experiment tracking

Enables:


- full system visibility

- reproducibility

- production debugging




🧰 Tech Stack


- AI / LLM:
LangGraph, LangChain, Phi-3


- Machine Learning:
XGBoost


- Backend & Infra:
FastAPI, Redis, PostgreSQL, Docker


- Evaluation:
MLflow, LangSmith



⚠️ Challenges & Engineering Decisions


🔌 API Reliability

Problem: External API failures (Mapbox)


Solution: Fallback to Haversine distance → ensured uptime

🤖 LLM Reliability

Problem: Incorrect numerical outputs


Solution: Deterministic Critic layer → fast validation


🧩 Distributed Systems



Problem: MLflow DNS issues in containers


Solution: Configured host allowlist



🔄 Example Workflow



Input: Waybill / logistics request



Output:

- structured shipment data


- optimized route


- predicted pricing


- validated decision



🚀 Getting Started


1. Prerequisites

•	Docker & Docker Compose

•	OpenAI API Key (for document proecssing)



 2.How to run:

# Clone the repository


git clone https://github.com/yourusername/logiq-agent-ops.git


cd logiq-agent-ops


# Set up environment variables


cp .env.example .env



# LLM & Tracing

OPENAI_API_KEY=your_key

LANGCHAIN_API_KEY=your_langsmith_key

LANGCHAIN_PROJECT="LogiQ-Intelligence-Platform"

LANGCHAIN_TRACING_V2="true"

LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"



# External APIs

MAPBOX_ACCESS_TOKEN=your_mapbox_token

VISUAL_CROSSING_KEY=your_weather_key

NOMINATIM_URL=https://nominatim.openstreetmap.org/search

NOMINATIM_REVERSE_URL=https://nominatim.openstreetmap.org/reverse

APP_USER_AGENT=LogiQ_Senior_Project_V2



# Databases (Docker Internal)

POSTGRES_USER=logiq_user

POSTGRES_PASSWORD=logiq_pass

POSTGRES_DB=logiq_db

POSTGRES_HOST=db

POSTGRES_PORT=5432

REDIS_HOST=redis

REDIS_PORT=6379


# Observability


MLFLOW_TRACKING_URI=http://mlflow_server:5000


MLFLOW_EXPERIMENT_NAME=Logistics_Pricing_Live


# Start the full stack (API + Redis + MLflow)


docker-compose up –build


# Run tests locally


pip install -r requirements.txt

uvicorn app:app --reload

pytest tests

