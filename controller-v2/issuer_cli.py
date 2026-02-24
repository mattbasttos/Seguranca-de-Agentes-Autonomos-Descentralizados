import sys
import time
import threading
import logging
import requests
import json
import os
from flask import Flask, request
from ai_brain import extract_intent

MY_PORT = 5001
AGENT_URL = "http://localhost:8001"
AGENT_NAME = "OPERADORA (IA AUTOMÁTICA)"

current_connection_id = None
DB_FILE = "telecom_db.json"
verification_results = {}

SCHEMAS_DEF = {
    "identidade": {"name": "identidade-digital", "attrs": ["nome", "cpf", "status"]},
    "plano":      {"name": "plano-internet", "attrs": ["nome_plano", "franquia", "validade"]},
    "clube":      {"name": "clube-vantagens", "attrs": ["categoria", "pontos", "desconto"]}
}

app = Flask(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

def load_db():
    if os.path.exists(DB_FILE):
        return json.load(open(DB_FILE))
    return {}

def save_db(data):
    json.dump(data, open(DB_FILE, 'w'), indent=4)

@app.route('/webhooks/topic/basicmessages/', methods=['POST'])
def receive_message():
    data = request.json
    if data['state'] != 'received': return "", 200
    
    msg = data['content']
    
    # --- FILTRO DE RUÍDO COM NOTIFICAÇÃO ---
    if "received your message" in msg.lower():
        print(f"\n✅ [SISTEMA]: O Cliente recebeu sua mensagem.")
        print(">> ", end="", flush=True)
        return "", 200
        
    print(f"\n\n🔔 [CLIENTE]: {msg}")
    
    print("🤖 IA processando o pedido...", end="", flush=True)
    intencao = extract_intent(msg)
    
    if intencao and "tipo" in intencao:
        tipo = intencao["tipo"]
        dados = intencao["dados"]
        
        db = load_db()
        if tipo in db:
            cred_def_id = db[tipo]
            print(f"\n✨ IA Identificou Pedido: {tipo.upper()}! Emitindo automaticamente...")
            
            atributos = []
            if tipo == "identidade":
                atributos = [
                    {"name": "nome", "value": dados.get("nome", "Desconhecido")},
                    {"name": "cpf", "value": dados.get("cpf", "000.000.000-00")},
                    {"name": "status", "value": "Verificado"}
                ]
            elif tipo == "plano":
                atributos = [
                    {"name": "nome_plano", "value": dados.get("nome_plano", "Básico")},
                    {"name": "franquia", "value": dados.get("franquia", "Ilimitado")},
                    {"name": "validade", "value": "30 Dias"}
                ]
            elif tipo == "clube":
                atributos = [
                    {"name": "categoria", "value": dados.get("categoria", "Bronze")},
                    {"name": "pontos", "value": str(dados.get("pontos", "0"))},
                    {"name": "desconto", "value": "10%"}
                ]

            body = {
                "connection_id": current_connection_id or data['connection_id'],
                "filter": {"anoncreds": {"cred_def_id": cred_def_id}},
                "credential_preview": {"@type": "issue-credential/2.0/credential-preview", "attributes": atributos}
            }
            try:
                requests.post(f"{AGENT_URL}/issue-credential-2.0/send", json=body)
                print(f"✅ Credencial do tipo '{tipo}' disparada para o cliente!")
                requests.post(f"{AGENT_URL}/connections/{data['connection_id']}/send-message", 
                              json={"content": f"Sua credencial '{tipo}' foi gerada pela nossa IA. Verifique sua carteira!"})
            except Exception as e: print(f"Erro ao emitir: {e}")
        else:
            print(f"\n⚠️ IA pediu {tipo}, mas a Operadora ainda não fez o Setup desse modelo.")
    else:
        print("\r💬 Apenas conversa normal. Responda pelo Chat.")
    
    print(">> ", end="", flush=True)
    return "", 200

@app.route('/webhooks/topic/present_proof_v2_0/', methods=['POST'])
def receive_proof():
    data = request.json
    pres_ex_id = data.get('pres_ex_id')
    
    if data['state'] == 'presentation-received':
        print(f"\n\n🔎 Prova Recebida! ID: {pres_ex_id}")
        
        # MÁGICA DE UX: Tenta descobrir qual credencial foi verificada lendo o pedido original
        tipo_cred = "CREDENCIAL"
        try:
            rec = requests.get(f"{AGENT_URL}/present-proof-2.0/records/{pres_ex_id}").json()
            # Uma busca textual rápida na resposta para descobrir o tipo
            req_str = json.dumps(rec)
            if "Verificar identidade" in req_str: tipo_cred = "IDENTIDADE"
            elif "Verificar plano" in req_str: tipo_cred = "PLANO"
            elif "Verificar clube" in req_str: tipo_cred = "CLUBE VIP"
        except: pass

        try:
            resp = requests.post(f"{AGENT_URL}/present-proof-2.0/records/{pres_ex_id}/verify-presentation").json()
            if str(resp.get("verified")).lower() == "true":
                print(f"✅ Verificação de {tipo_cred} foi um sucesso! Acesso Liberado.")
                verification_results[pres_ex_id] = True
            else:
                print(f"❌ Assinatura de {tipo_cred} INVÁLIDA!")
                verification_results[pres_ex_id] = False
        except Exception as e:
            pass 
        print(">> ", end="", flush=True)
    return "", 200

@app.route('/webhooks/topic/connections/', methods=['POST'])
def c(): return "", 200
@app.route('/webhooks/topic/issue_credential_v2_0/', methods=['POST'])
def i(): return "", 200

def check_conn():
    global current_connection_id
    try:
        r = requests.get(f"{AGENT_URL}/connections?state=active").json().get('results', [])
        if r:
            r.sort(key=lambda x: x['created_at'], reverse=True)
            current_connection_id = r[0]['connection_id']
            print(f"✅ Conectado: {current_connection_id}")
    except: pass

def show_connection():
    if not current_connection_id:
        print("⚠️ Nenhuma conexão ativa no momento.")
        return
    try:
        resp = requests.get(f"{AGENT_URL}/connections/{current_connection_id}").json()
        their_label = resp.get('their_label', 'Desconhecido')
        state = resp.get('state', 'Desconhecido')
        print(f"\n🔗 STATUS DA CONEXÃO:")
        print(f"   - ID Local: {current_connection_id}")
        print(f"   - Conectado com: {their_label}")
        print(f"   - Estado: {state.upper()}")
    except Exception as e:
        print(f"Erro ao buscar detalhes da conexão: {e}")

def setup_all_schemas():
    print("\n--- INICIALIZANDO TODOS OS 3 SCHEMAS ---")
    try:
        did = requests.get(f"{AGENT_URL}/wallet/did/public").json()['result']['did']
    except: 
        return print("❌ Sem DID Público.")

    db = load_db()
    for tipo, config in SCHEMAS_DEF.items():
        if tipo in db:
            print(f"🔹 {tipo.upper()} já está configurado.")
            continue
            
        print(f"⚙️ Criando {tipo.upper()}...")
        s_body = {"schema": {"issuerId": did, "name": config["name"], "version": "1.0", "attrNames": config["attrs"]}}
        s_resp = requests.post(f"{AGENT_URL}/anoncreds/schema", json=s_body).json()
        s_id = s_resp["schema_state"]["schema_id"]
        
        cd_body = {"credential_definition": {"issuerId": did, "schemaId": s_id, "tag": "v1"}}
        cd_resp = requests.post(f"{AGENT_URL}/anoncreds/credential-definition", json=cd_body).json()
        cd_id = cd_resp["credential_definition_state"]["credential_definition_id"]
        
        db[tipo] = cd_id
        save_db(db)
        print(f"   ✅ OK!")
    
    print("\n✅ Setup Completo! O sistema agora lembrará destas configurações.")

def pedir_prova():
    if not current_connection_id: return print("⚠️ Sem conexão ativa.")
    db = load_db()
    
    print("\n--- PEDIR VERIFICAÇÃO ---")
    print("1. Identidade | 2. Plano de Dados | 3. Clube VIP")
    escolha = input("Qual credencial verificar? (1/2/3): ")
    
    tipo_map = {"1": "identidade", "2": "plano", "3": "clube"}
    tipo = tipo_map.get(escolha)
    
    if not tipo or tipo not in db: return print("⚠️ Inválido ou não configurado.")
    
    attr_alvo = SCHEMAS_DEF[tipo]["attrs"][0] 
    
    req_body = {
        "connection_id": current_connection_id,
        "presentation_request": {
            "anoncreds": {
                "name": f"Verificar {tipo}",
                "version": "1.0",
                "requested_attributes": {
                    "attr1": {"name": attr_alvo, "restrictions": [{"cred_def_id": db[tipo]}]}
                },
                "requested_predicates": {}
            }
        }
    }
    
    try:
        resp = requests.post(f"{AGENT_URL}/present-proof-2.0/send-request", json=req_body)
        
        if resp.status_code != 200:
            print("❌ Falha na comunicação com o Agente.")
            return
            
        pres_ex_id = resp.json().get('pres_ex_id')
        verification_results[pres_ex_id] = None 
        
        print("⏳ Verificando carteira do cliente...")
        
        for _ in range(5): 
            time.sleep(1)
            if verification_results.get(pres_ex_id) is not None:
                del verification_results[pres_ex_id] 
                return 
        
        print("❌ ASSINATURA NÃO EXISTE.")
        del verification_results[pres_ex_id]
        
    except Exception as e:
        print(f"❌ Erro Crítico: {e}")

def menu():
    threading.Thread(target=lambda: app.run(port=MY_PORT, debug=False, use_reloader=False), daemon=True).start()
    time.sleep(1)
    check_conn()
    while True:
        print(f"\n=== {AGENT_NAME} ===")
        print("1. Gerar Convite")
        print("2. Setup Completo (3 Credenciais)")
        print("3. Solicitar Verificação de Cliente")
        print("4. Chat Manual")
        print("5. Verificar Conexão Ativa")
        print("0. Sair")
        opt = input(">> ")
        if opt == '1': 
            try: print("\n", requests.post(f"{AGENT_URL}/out-of-band/create-invitation", json={"handshake_protocols": ["https://didcomm.org/didexchange/1.0"]}).json()['invitation'])
            except: pass
        elif opt == '2': setup_all_schemas()
        elif opt == '3': pedir_prova()
        elif opt == '4':
            if current_connection_id: requests.post(f"{AGENT_URL}/connections/{current_connection_id}/send-message", json={"content": input("\n--- CHAT DIRETO ---\nVocê: ")})
        elif opt == '5': show_connection()
        elif opt == '0': sys.exit()

if __name__ == "__main__":
    menu()