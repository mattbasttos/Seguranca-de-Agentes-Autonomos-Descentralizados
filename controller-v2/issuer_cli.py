import sys
import time
import threading
import logging
import requests
import json
from flask import Flask, request

# --- CONFIGURAÇÕES ---
MY_PORT = 5001
AGENT_URL = "http://localhost:8001"
AGENT_NAME = "OPERADORA (V2.0)"

# Estado Global
current_connection_id = None
cred_def_id = None 

# Logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format='%(message)s')
app = Flask(__name__)

# --- WEBHOOKS ---

@app.route('/webhooks/topic/basicmessages/', methods=['POST'])
def receive_message():
    data = request.json
    if data['state'] == 'received':
        print(f"\n\n🔔 [CLIENTE]: {data['content']}")
        print(">> ", end="", flush=True)
    return "", 200

@app.route('/webhooks/topic/present_proof_v2_0/', methods=['POST'])
def receive_proof_v2():
    data = request.json
    state = data['state']
    pres_ex_id = data['pres_ex_id']

    if state == 'presentation-received':
        print(f"\n\n🔎 Prova recebida (ID: {pres_ex_id}). Validando assinatura...")
        
        try:
            # Solicita verificação criptográfica ao Agente
            url_ver = f"{AGENT_URL}/present-proof-2.0/records/{pres_ex_id}/verify-presentation"
            ver_resp = requests.post(url_ver).json()
            
            is_verified = str(ver_resp.get("verified")).lower()
            
            if is_verified == "true":
                # Tenta extrair os dados revelados
                pres_data = ver_resp["by_format"]["pres"]
                target = pres_data.get("indy") or pres_data.get("anoncreds")
                
                print(f"✅ ACESSO LIBERADO! Identidade Confirmada.")
                
                if target:
                    try:
                        dados = target["presentation"]["requested_proof"]["revealed_attrs"]
                        # Tenta pegar os valores crus
                        plano = dados.get('attr_plano', {}).get('raw')
                        franquia = dados.get('attr_franquia', {}).get('raw')
                        if plano: print(f"   📋 Plano: {plano} | Franquia: {franquia}")
                    except: pass
            else:
                print("❌ ACESSO NEGADO. Assinatura inválida.")
                
        except Exception as e:
            print(f"❌ Erro na validação: {e}")
            
        print(">> ", end="", flush=True)

    return "", 200

# Rotas Curinga
@app.route('/webhooks/topic/connections/', methods=['POST'])
def i_conn(): return "", 200
@app.route('/webhooks/topic/issue_credential_v2_0/', methods=['POST'])
def i_issue(): return "", 200
@app.route('/webhooks/topic/revocation_registry/', methods=['POST'])
def i_rev(): return "", 200

def start_webhook():
    try: app.run(port=MY_PORT, debug=False, use_reloader=False)
    except: pass

# --- FUNÇÕES ---

def check_connection():
    global current_connection_id
    try:
        resp = requests.get(f"{AGENT_URL}/connections", params={"state": "active"})
        res = resp.json().get('results', [])
        if res:
            res.sort(key=lambda x: x['created_at'], reverse=True)
            current_connection_id = res[0]['connection_id']
            print(f"✅ Conectado: {current_connection_id}")
    except: print("❌ Agente offline.")

def setup_telco():
    global cred_def_id
    print("\n--- SETUP ANONCREDS ---")
    
    # 1. DID
    try:
        did = requests.get(f"{AGENT_URL}/wallet/did/public").json()['result']['did']
    except: 
        print("❌ Sem DID Público.")
        return

    # 2. Schema
    schema_body = {
        "schema": {
            "issuerId": did, "name": "plano-dados-v2", "version": "2.0", 
            "attrNames": ["nome_plano", "franquia_gb", "validade"]
        }
    }
    s_resp = requests.post(f"{AGENT_URL}/anoncreds/schema", json=schema_body)
    if s_resp.status_code != 200: return print(f"Erro Schema: {s_resp.text}")
    schema_id = s_resp.json()["schema_state"]["schema_id"]
    print(f"✅ Schema Criado")

    # 3. CredDef
    cd_body = {
        "credential_definition": {"issuerId": did, "schemaId": schema_id, "tag": "promo-v2"}
    }
    c_resp = requests.post(f"{AGENT_URL}/anoncreds/credential-definition", json=cd_body)
    if c_resp.status_code != 200: return print(f"Erro CredDef: {c_resp.text}")
    
    cred_def_id = c_resp.json()["credential_definition_state"]["credential_definition_id"]
    print(f"✅ Setup OK! CredDef ID: {cred_def_id}")

def ativar_plano():
    if not current_connection_id or not cred_def_id:
        print("⚠️ Necessário setup e conexão.")
        return

    print("\n--- ATIVAR PLANO (ISSUE 2.0) ---")
    nome_plano = input("Nome do Plano: ")
    franquia = input("Franquia (ex: 50GB): ")

    body = {
        "connection_id": current_connection_id,
        "filter": {"anoncreds": {"cred_def_id": cred_def_id}},
        "credential_preview": {
            "@type": "issue-credential/2.0/credential-preview",
            "attributes": [
                {"name": "nome_plano", "value": nome_plano},
                {"name": "franquia_gb", "value": franquia},
                {"name": "validade", "value": "30 dias"}
            ]
        }
    }

    try:
        resp = requests.post(f"{AGENT_URL}/issue-credential-2.0/send", json=body)
        if resp.status_code == 200:
            print(f"✅ Oferta enviada ao cliente!")
        else:
            print(f"❌ Falha: {resp.text}")
    except Exception as e: print(f"Erro: {e}")

def verificar_acesso():
    if not current_connection_id: return
    
    print("\n--- VERIFICAR ACESSO (PROOF 2.0) ---")
    print("Enviando desafio criptográfico ao cliente...")
    
    req_body = {
        "connection_id": current_connection_id,
        "presentation_request": {
            "anoncreds": {
                "name": "Verificacao de Rede TelecomX",
                "version": "1.0",
                "requested_attributes": {
                    "attr_franquia": {"name": "franquia_gb", "restrictions": [{"cred_def_id": cred_def_id} if cred_def_id else {}]},
                    "attr_plano": {"name": "nome_plano", "restrictions": [{"cred_def_id": cred_def_id} if cred_def_id else {}]}
                },
                "requested_predicates": {}
            }
        }
    }
    
    try:
        requests.post(f"{AGENT_URL}/present-proof-2.0/send-request", json=req_body)
        print("✅ Pedido enviado! Aguardando o cliente provar automaticamente...")
    except Exception as e: print(f"Erro: {e}")

def create_invitation():
    try:
        resp = requests.post(f"{AGENT_URL}/out-of-band/create-invitation", 
                           json={"handshake_protocols": ["https://didcomm.org/didexchange/1.0"]})
        print(f"\nConvite:\n{json.dumps(resp.json()['invitation'])}")
    except: pass

def send_message():
    if current_connection_id:
        requests.post(f"{AGENT_URL}/connections/{current_connection_id}/send-message", json={"content": input("Msg: ")})
        print("Enviada.")

def menu():
    t = threading.Thread(target=start_webhook, daemon=True)
    t.start()
    time.sleep(1)
    check_connection()
    while True:
        print(f"\n=== {AGENT_NAME} ===")
        print("1. Gerar Convite")
        print("2. Setup Telecom (AnonCreds)")
        print("3. Ativar Plano (Emitir)")
        print("4. Verificar Acesso (Pedir Prova)")
        print("5. Chat")
        print("0. Sair")
        opt = input(">> ")
        if opt == '1': create_invitation()
        elif opt == '2': setup_telco()
        elif opt == '3': ativar_plano()
        elif opt == '4': verificar_acesso()
        elif opt == '5': send_message()
        elif opt == '0': sys.exit()

if __name__ == "__main__":
    menu()