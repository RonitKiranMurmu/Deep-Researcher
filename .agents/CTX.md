# Project Knowledge: Deep Researcher V2

## Overview
Deep Researcher V2 is a hybrid desktop application engineered to execute autonomous, multi-step research workflows. It synthesizes information from the web, documents, and structured sources into verifiable reports.

## Architecture & Repositories
The project is divided into three primary modules:
1. **Frontend (`/app`)**
   - **Stack**: Electron, Vite, React 19, Tailwind CSS 4, Shadcn UI, Framer Motion.
   - **Role**: Provides a secure, native desktop environment. Manages workspaces, visualizes Chain-of-Thought processes in real-time, and renders rich, structured artifacts.
2. **Backend (`/backend`)**
   - **Stack**: Python 3.12+, FastAPI, Google Gemini, Ollama, SQLite.
   - **Role**: The core research engine. It handles agentic orchestration, multi-step reasoning, web crawling, RAG, and persistent logging to prevent data loss.
3. **MCP Tools Server (`/MCP_Tools_Server`)**
   - **Stack**: Python.
   - **Role**: Implements Model Context Protocol (MCP) standards. Acts as the interface layer for tools, allowing agents to reliably interact with external APIs, the local filesystem, and data processing utilities.

## Key Concepts & Terminology
- **Harness Engineering**: Structuring LLM interactions with strict, predictable scaffolding.
- **Agentic Workflows**: Multi-step, autonomous planning and execution rather than single-shot prompts.
- **Model Context Protocol (MCP)**: Standardized tool use and context window management.
- **Chain-of-Thought (CoT)**: Exposed reasoning steps for user audibility.
- **RAG & Semantic Search**: Grounding LLM outputs in verifiable, retrieved data.
- **Workspace Isolation**: Sandboxing research tasks into persistent, stateful environments.
