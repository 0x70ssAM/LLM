# Ollama Chat (FastAPI + Docker)

A lightweight, containerized FastAPI application for chatting with Ollama-hosted LLM models such as `gpt-oss` or `llama3`, with streaming support, a built-in web UI, and configurable environment variables.

---

## Features

- **FastAPI backend** with REST + streaming endpoints  
- **Simple HTML/JS front-end** served directly by the API  
- **Dockerized** for consistent deployment  
- **Environment-driven configuration** via `.env`  
- **Streaming responses** using Server-Sent Events (SSE)  
- **Prebuilt installer script** (`ollama.sh`) for Ollama & Docker setup  

---

## Prerequisites

- **Ollama** installed and configured on the host  
- **Docker** & **docker-compose** installed  
- **Python 3.11** (only for local development without Docker)  

If you need Ollama and Docker installed, run:

```bash
./ollama.sh

