import requests
import json
import logging

# Configuração do Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:mini"  # Certifique-se que este modelo está baixado no Ollama

def ask_ollama(system_persona: str, user_message: str):
    """Gera uma resposta de conversação (Chat)."""
    prompt = f"{system_persona}\nUser: {user_message}\nResposta (Curta e útil):"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        return {"content": resp.json()['response']}
    except Exception as e:
        return {"content": f"(Erro IA: {e})"}

def extract_credential_data(user_message: str):
    """
    Função Especializada: Tenta encontrar Nome e Plano na frase.
    Retorna JSON puro: {"nome": "...", "plano": "..."}
    """
    system_instruction = (
        "Voce e um extrator de dados para uma empresa de telecom. "
        "Analise a frase. Se houver um NOME DE PESSOA e um TIPO DE PLANO (internet, fibra, etc), extraia-os. "
        "Retorne APENAS um JSON valido no formato: {\"nome\": \"...\", \"plano\": \"...\"}. "
        "Se nao encontrar, retorne um JSON vazio {}."
        "Nao escreva nada alem do JSON."
    )
    
    prompt = f"{system_instruction}\nFrase: \"{user_message}\"\nJSON:"
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json", # Força resposta JSON
        "options": {"temperature": 0.1} # Criatividade baixa para ser preciso
    }
    
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        response_text = resp.json()['response']
        # Tenta limpar caso o modelo coloque markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        return json.loads(response_text)
    except Exception as e:
        return {}