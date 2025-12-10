import logging
import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

import acapy_controller
import ollama_client

app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state["session"] = aiohttp.ClientSession()
    yield
    await app_state["session"].close()

app = FastAPI(lifespan=lifespan)

class ChatInput(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(inp: ChatInput):
    # 1. IA interpreta
    cmd = ollama_client.get_ollama_function_call(inp.message)
    func = cmd.get("function_name")
    params = cmd.get("parameters", {})

    if func == "error":
        raise HTTPException(500, detail=params.get("message"))

    # 2. Controller executa
    session = app_state["session"]
    result = ""

    try:
        if func == "setup_telco":
            result = await acapy_controller.setup_telco(session)
        elif func == "conectar_cliente":
            result = await acapy_controller.conectar_cliente(session)
        elif func == "ativar_plano":
            result = await acapy_controller.ativar_plano(session, **params)
        elif func == "verificar_acesso":
            result = await acapy_controller.verificar_acesso(session)
        else:
            result = f"Função desconhecida: {func}"
    except Exception as e:
        result = f"Erro de execução: {str(e)}"

    return {"response": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)