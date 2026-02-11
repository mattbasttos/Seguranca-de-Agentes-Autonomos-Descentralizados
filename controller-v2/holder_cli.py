import sys
import time
import threading
import logging
import requests
import json
from flask import Flask, request

# --- CONFIGURAÇÕES ---
MY_PORT = 5002
AGENT_URL = "http://localhost:8011"
AGENT_NAME = "CLIENTE (NOTIFICAÇÃO)"

current_connection_id = None
pending_offer_id = None
pending_proof_id = None # Guarda o ID do pedido para responder manualmente se quiser

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format='%(message)s')
app = Flask(__name__)

# --- WEBHOOKS (Recepção de Alertas) ---

@app.route('/webhooks/topic/issue_credential_v2_0/', methods=['POST'])
def receive_offer_v2():
    global pending_offer_id
    data = request.json
    state = data['state']
    
    if state == 'offer-received':
        pending_offer_id = data['cred_ex_id']
        print(f"\n\n🎁 NOVO PLANO RECEBIDO! (Vá na Opção 2 para aceitar)")
        print(">> ", end="", flush=True)
    elif state == 'done':
        #print(f"\n\n✅ Plano salvo na Carteira com sucesso!")
        print(">> ", end="", flush=True)
    return "", 200

@app.route('/webhooks/topic/present_proof_v2_0/', methods=['POST'])
def receive_proof_req_v2():
    """Apenas notifica que a Operadora pediu a prova"""
    global pending_proof_id
    data = request.json
    state = data['state']
    pres_ex_id = data['pres_ex_id']
    
    if state == 'request-received':
        pending_proof_id = pres_ex_id
        # --- AQUI ESTÁ A NOTIFICAÇÃO SIMPLES ---
        print(f"\n\n🛡️ A OPERADORA SOLICITOU VERIFICAÇÃO DE IDENTIDADE!")
        print(f"   (O pedido ID {pres_ex_id} está aguardando sua aprovação)")
        print(f"   Se quiser liberar o acesso, vá na Opção 3.")
        print(">> ", end="", flush=True)
        
    return "", 200

@app.route('/webhooks/topic/basicmessages/', methods=['POST'])
def receive_msg():
    data = request.json
    if data['state'] == 'received':
        print(f"\n\n🔔 [OPERADORA]: {data['content']}")
        print(">> ", end="", flush=True)
    return "", 200

# Rotas Curinga
@app.route('/webhooks/topic/connections/', methods=['POST'])
def i_conn(): return "", 200
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
    except: pass

def accept_invitation():
    inv = input("JSON Convite: ")
    requests.post(f"{AGENT_URL}/out-of-band/receive-invitation", json=json.loads(inv))
    print("✅ Aceito.")

def accept_credential():
    global pending_offer_id
    if not pending_offer_id:
        print("⚠️ Nenhuma oferta pendente.")
        return
    try:
        requests.post(f"{AGENT_URL}/issue-credential-2.0/records/{pending_offer_id}/send-request", json={})
        print(f"\n\n✅ Plano salvo na Carteira com sucesso!")
        pending_offer_id = None
    except Exception as e: print(f"Erro: {e}")

def list_credentials():
    print("\n--- MINHA CARTEIRA ---")
    try:
        resp = requests.get(f"{AGENT_URL}/credentials")
        creds = resp.json().get('results', [])
        if not creds: print("(Vazia)")
        for i, c in enumerate(creds):
            print(f"💳 [{i+1}] {c['attrs']}")
    except: print("Erro ao ler carteira.")

def send_proof_manual():
    global pending_proof_id
    if not pending_proof_id:
        print("⚠️ Nenhum pedido de verificação pendente.")
        return
    
    print(f"Processando pedido {pending_proof_id}...")
    try:
        # 1. Busca credencial no banco
        time.sleep(1)
        creds_resp = requests.get(f"{AGENT_URL}/present-proof-2.0/records/{pending_proof_id}/credentials")
        creds = creds_resp.json()
        
        if not creds:
            print("❌ Você não tem a credencial exigida (Plano/Franquia).")
            return

        cred_v2_id = creds[0]['record_id']
        
        # 2. Envia a prova
        body = {
            "requested_attributes": {
                "attr_franquia": {"cred_id": cred_v2_id, "revealed": True},
                "attr_plano": {"cred_id": cred_v2_id, "revealed": True}
            },
            "requested_predicates": {}
        }
        
        requests.post(f"{AGENT_URL}/present-proof-2.0/records/{pending_proof_id}/send-presentation", json=body)
        print("✅ Prova enviada manualmente!")
        pending_proof_id = None

    except Exception as e:
        print(f"Erro: {e}")

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
        print("1. Aceitar Convite")
        print("2. Aceitar Plano (Salvar)")
        print("3. Enviar Prova (Liberar Acesso)")
        print("4. Minha Carteira")
        print("5. Chat")
        print("0. Sair")
        opt = input(">> ")
        if opt == '1': accept_invitation()
        elif opt == '2': accept_credential()
        elif opt == '3': send_proof_manual()
        elif opt == '4': list_credentials()
        elif opt == '5': send_message()
        elif opt == '0': sys.exit()

if __name__ == "__main__":
    menu()