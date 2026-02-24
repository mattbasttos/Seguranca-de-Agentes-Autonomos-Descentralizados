import sys
import time
import threading
import logging
import requests
import json
from flask import Flask, request
from ai_brain import ask_ollama

MY_PORT = 5002
AGENT_URL = "http://localhost:8011"
AGENT_NAME = "CLIENTE (COM ASSISTENTE IA)"

current_connection_id = None
pending_offer_id = None

app = Flask(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# --- WEBHOOKS V2.0 ---
@app.route('/webhooks/topic/issue_credential_v2_0/', methods=['POST'])
def receive_offer():
    global pending_offer_id
    data = request.json
    if data['state'] == 'offer-received':
        pending_offer_id = data['cred_ex_id']
        print(f"\n\n🎁 A Operadora enviou uma Credencial! Vá na Opção 2 para aceitar.")
        print(">> ", end="", flush=True)
    elif data['state'] == 'done':
        print(f"\n\n✅ Credencial adicionada à Carteira Digital!")
        print(">> ", end="", flush=True)
    return "", 200

@app.route('/webhooks/topic/basicmessages/', methods=['POST'])
def r_msg():
    data = request.json
    if data['state'] == 'received':
        print(f"\n\n🔔 [OPERADORA]: {data['content']}")
        print(">> ", end="", flush=True)
    return "", 200

@app.route('/webhooks/topic/connections/', methods=['POST'])
def c(): return "", 200

# --- FUNÇÕES ---
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

def accept_invitation():
    try: 
        requests.post(f"{AGENT_URL}/out-of-band/receive-invitation", json=json.loads(input("JSON Convite: ")))
        print("✅ Convite processado.")
    except: 
        print("Erro ao processar convite.")

def accept_cred():
    global pending_offer_id
    if pending_offer_id:
        requests.post(f"{AGENT_URL}/issue-credential-2.0/records/{pending_offer_id}/send-request", json={})
        print("✅ Aceitando credencial...")
        pending_offer_id = None
    else: 
        print("⚠️ Nenhuma oferta de credencial pendente no momento.")

def list_credentials():
    print("\n--- MINHA CARTEIRA DIGITAL ---")
    try:
        resp = requests.get(f"{AGENT_URL}/credentials")
        creds = resp.json().get('results', [])
        
        if not creds:
            print("(Carteira Vazia - Nenhuma credencial encontrada)")
            return
        
        for i, c in enumerate(creds):
            cred_id = c.get('referent', 'ID Indisponível')
            schema_id = c.get('schema_id', '')
            
            tipo_cred = "CREDENCIAL"
            if schema_id:
                partes = schema_id.split(':')
                if len(partes) >= 3:
                    tipo_cred = partes[2].replace('-', ' ').upper()
            
            print(f"\n💳 {tipo_cred} (Item #{i+1})")
            print(f"   🆔 ID: {cred_id}")
            attrs = c.get('attrs', {})
            for k, v in attrs.items():
                print(f"   - {k.capitalize()}: {v}")
    except Exception as e:
        print(f"Erro ao ler carteira: {e}")

def chat_ia():
    if not current_connection_id: 
        return print("⚠️ Conecte-se à Operadora primeiro (Opção 1).")
        
    print("\n--- CHAT COM ASSISTENTE IA ---")
    print("💡 DICAS DE PEDIDOS (Você pode pedir 3 tipos de credenciais):")
    print(" 🔹 Identidade: 'Quero fazer minha identidade. Meu nome é [Seu Nome] e meu CPF é [Seu CPF]'")
    print(" 🔹 Plano:      'Gostaria de assinar o plano [Nome do Plano] com franquia de [Ex: 50GB]'")
    print(" 🔹 Clube VIP:  'Quero entrar pro clube de vantagens na categoria [Ex: Ouro] com [Ex: 100] pontos'")
    print("-" * 65)
    
    msg_usuario = input("\nVocê: ")
    
    # --- A TRAVA DE SEGURANÇA AQUI ---
    if not msg_usuario.strip():
        print("⚠️ Mensagem vazia. Envio cancelado para evitar que a IA alucine!")
        return
    
    persona = (
        "Você é um assistente virtual de um cliente. Sua função é pegar a mensagem do usuário "
        "e formulá-la de maneira clara e direta para a Operadora. Responda APENAS com a mensagem formatada "
        "em primeira pessoa, sem saudações extras ou explicações suas."
    )
    resp_ia = ask_ollama(persona, msg_usuario)
    msg_final = resp_ia.get('content', msg_usuario)
    
    print("\n🤖 Assistente: Entendido! Já estruturei o seu pedido e enviei para a Operadora.")
    requests.post(f"{AGENT_URL}/connections/{current_connection_id}/send-message", json={"content": msg_final})

def chat_manual():
    if not current_connection_id: 
        return print("⚠️ Conecte-se à Operadora primeiro (Opção 1).")
    
    print("\n--- CHAT DIRETO ---")
    msg = input("Você: ")
    if msg.strip():
        requests.post(f"{AGENT_URL}/connections/{current_connection_id}/send-message", json={"content": msg})
        print("✅ Mensagem enviada diretamente.")

def menu():
    threading.Thread(target=lambda: app.run(port=MY_PORT, debug=False, use_reloader=False), daemon=True).start()
    time.sleep(1)
    check_conn()
    while True:
        print(f"\n=== {AGENT_NAME} ===")
        print("1. Aceitar Convite")
        print("2. Aceitar Credencial na Carteira")
        print("3. Minha Carteira (Ver Credenciais)")
        print("4. Chat com Operadora (Via IA - Para pedir credenciais)")
        print("5. Chat Direto (Manual - Mensagem livre)")
        print("6. Verificar Conexão Ativa")
        print("0. Sair")
        opt = input(">> ")
        
        if opt == '1': accept_invitation()
        elif opt == '2': accept_cred()
        elif opt == '3': list_credentials()
        elif opt == '4': chat_ia()
        elif opt == '5': chat_manual()
        elif opt == '6': show_connection()
        elif opt == '0': sys.exit()

if __name__ == "__main__":
    menu()