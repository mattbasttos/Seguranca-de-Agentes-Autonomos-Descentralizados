import requests
import json
import logging
from typing import Dict, Any

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "phi3:mini"

# --- PROMPT REFORÇADO ---
SYSTEM_PROMPT = """
Você é o orquestrador JSON da TelecomX.
Sua tarefa é classificar a intenção do usuário em uma das funções abaixo.

REGRAS CRÍTICAS:
1. Responda APENAS com JSON válido.
2. USE APENAS OS NOMES DE FUNÇÃO EXATOS LISTADOS ABAIXO. NÃO TRADUZA. NÃO INVENTE.
3. Se a intenção for ativar um plano, use SEMPRE "ativar_plano".

LISTA DE FUNÇÕES PERMITIDAS:

1. setup_telco
   - Gatilhos: "Iniciar sistema", "Configurar".
   - Params: {}

2. conectar_cliente
   - Gatilhos: "Conectar cliente", "Novo assinante", "Onboarding".
   - Params: {}

3. ativar_plano
   - Gatilhos: "Ativar plano", "Vender promoção", "Quero 50GB".
   - Params:
     - "nome_plano": (string) Ex: "Promoção Turbo".
     - "franquia": (string) Ex: "50GB".

4. verificar_acesso
   - Gatilhos: "Verificar acesso", "Validar plano".
   - Params: {}

Exemplo de Saída Correta:
{
  "function_name": "ativar_plano",
  "parameters": {
    "nome_plano": "Turbo 5G",
    "franquia": "500GB"
  }
}
"""

def get_ollama_function_call(user_prompt: str) -> Dict[str, Any]:
    logging.info(f"Enviando para Phi-3: {user_prompt}")
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0, # Criatividade zero
            "num_predict": 128  # Limita o tamanho da resposta para evitar alucinações longas
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        content = response.json()["message"]["content"]
        logging.info(f"Resposta IA: {content}")
        return json.loads(content)
    except Exception as e:
        logging.error(f"Erro IA: {e}")
        return {"function_name": "error", "parameters": {"message": str(e)}}