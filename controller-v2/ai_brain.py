import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:mini" # Pode mudar para llama3 se quiser

def ask_ollama(system_persona: str, user_message: str):
    """Chatbot normal para conversar"""
    prompt = f"{system_persona}\nUsuário: {user_message}\nResposta:"
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.4}}
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        return {"content": resp.json()['response']}
    except Exception as e:
        return {"content": f"(Erro IA: {e})"}

def extract_intent(user_message: str):
    """
    IA MESTRA DA OPERADORA: Lê a frase e decide qual credencial emitir.
    Espera um JSON: {"tipo": "identidade|plano|clube", "dados": { ... }}
    """
    system_instruction = """
    Você é um sistema de extração de dados JSON.
    Temos 3 tipos de credenciais disponíveis:
    1. "identidade": Exige "nome" e "cpf".
    2. "plano": Exige "nome_plano" e "franquia".
    3. "clube": Exige "categoria" (ex: Ouro, VIP) e "pontos".
    
    Analise a frase. Se o usuário estiver pedindo uma dessas credenciais e informando os dados, extraia-os.
    Retorne APENAS UM JSON VÁLIDO.
    Exemplo: {"tipo": "plano", "dados": {"nome_plano": "Fibra", "franquia": "500GB"}}
    Se faltar informação ou não for um pedido, retorne: {}
    NÃO ESCREVA NENHUM TEXTO ALÉM DO JSON.
    """
    
    prompt = f"{system_instruction}\nFrase: \"{user_message}\"\nJSON:"
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.1}}
    
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        texto = resp.json()['response']
        
        # Limpa markdown caso a IA teime em colocar
        if "```json" in texto:
            texto = texto.split("```json")[1].split("```")[0]
            
        return json.loads(texto.strip())
    except:
        return {}