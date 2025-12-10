import aiohttp
import logging
import asyncio
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constantes ---
OPERADORA_ADMIN = "http://localhost:8001"
CLIENTE_ADMIN = "http://localhost:8011"
VERIFICADOR_ADMIN = "http://localhost:8021"

# --- Estado em Memória ---
STATE = {
    "operadora_did": None,
    "kyc_schema_id": None,
    "kyc_cred_def_id": None,
    "plano_schema_id": None,
    "plano_cred_def_id": None,
    "conn_id_operadora": None,
    "conn_id_verificador": None
}

# --- Auxiliar HTTP ---
async def admin_request(session, method, url, json_data=None, params=None):
    try:
        async with session.request(method, url, json=json_data, params=params) as resp:
            if resp.status >= 400:
                text = await resp.text()
                logging.error(f"Erro API {resp.status} em {url}: {text}")
                return None
            return await resp.json()
    except Exception as e:
        logging.error(f"Exceção Request {url}: {e}")
        return None

# --- Funcionalidades de Telecom ---

async def setup_telco(session: aiohttp.ClientSession) -> str:
    """Configura Schemas e CredDefs da TelecomX no Blockchain."""
    logging.info("Iniciando setup da TelecomX...")

    # 1. Obter DID
    did_data = await admin_request(session, "GET", f"{OPERADORA_ADMIN}/wallet/did/public")
    if not did_data: 
        return "Erro crítico: Não foi possível obter o DID público da Operadora. Verifique se o agente está rodando e conectado ao ledger."
    
    op_did = did_data["result"]["did"]
    STATE["operadora_did"] = op_did

    # 2. Schema e CredDef: Identidade (KYC)
    s_kyc = {"schema": {"issuerId": op_did, "name": "identidade-assinante", "version": "1.2", "attrNames": ["nome_completo", "cpf", "status_conta"]}}
    resp_s_kyc = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/anoncreds/schema", s_kyc)
    
    if not resp_s_kyc: return "Erro ao criar Schema de Identidade (verifique os logs do terminal do chatbot)."
    STATE["kyc_schema_id"] = resp_s_kyc["schema_state"]["schema_id"]

    cd_kyc = {"credential_definition": {"issuerId": op_did, "schemaId": STATE["kyc_schema_id"], "tag": "kyc"}}
    resp_cd_kyc = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/anoncreds/credential-definition", cd_kyc)
    
    if not resp_cd_kyc: return "Erro ao criar CredDef de Identidade."
    STATE["kyc_cred_def_id"] = resp_cd_kyc["credential_definition_state"]["credential_definition_id"]

    # 3. Schema e CredDef: Plano (Promoção)
    s_plano = {"schema": {"issuerId": op_did, "name": "plano-dados", "version": "1.2", "attrNames": ["nome_plano", "franquia_gb", "validade"]}}
    resp_s_plano = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/anoncreds/schema", s_plano)
    
    if not resp_s_plano: return "Erro ao criar Schema de Plano."
    STATE["plano_schema_id"] = resp_s_plano["schema_state"]["schema_id"]

    cd_plano = {"credential_definition": {"issuerId": op_did, "schemaId": STATE["plano_schema_id"], "tag": "promo"}}
    resp_cd_plano = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/anoncreds/credential-definition", cd_plano)
    
    if not resp_cd_plano: return "Erro ao criar CredDef de Plano."
    STATE["plano_cred_def_id"] = resp_cd_plano["credential_definition_state"]["credential_definition_id"]

    return f"Infraestrutura TelecomX configurada com sucesso. DID: {op_did}"

async def conectar_cliente(session: aiohttp.ClientSession) -> str:
    logging.info("Conectando cliente à Operadora...")

    # 1. Convite da Operadora
    body = {"handshake_protocols": ["https://didcomm.org/didexchange/1.0"]}
    inv_resp = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/out-of-band/create-invitation", body)
    if not inv_resp: return "Erro ao criar convite na Operadora."

    # 2. Cliente Aceita
    acc_resp = await admin_request(session, "POST", f"{CLIENTE_ADMIN}/out-of-band/receive-invitation", inv_resp["invitation"])
    if not acc_resp: return "Erro ao receber convite no Cliente."

    # 3. Resgatar ID da Conexão
    await asyncio.sleep(2)
    conns = await admin_request(session, "GET", f"{OPERADORA_ADMIN}/connections", params={"their_label": "Holder"})
    
    if conns and conns.get("results"):
        # Pega a conexão mais recente (última da lista ou ordena se necessário)
        STATE["conn_id_operadora"] = conns["results"][0]["connection_id"]
        return "Cliente conectado e autenticado na base da TelecomX."
    
    return "Conexão iniciada, mas ID não encontrado na Operadora."

async def ativar_plano(session: aiohttp.ClientSession, nome_plano: str, franquia: str) -> str:
    conn_id = STATE.get("conn_id_operadora")
    cred_def_id = STATE.get("plano_cred_def_id")

    if not conn_id or not cred_def_id: return "Erro: Necessário setup e conexão prévia."

    body = {
        "connection_id": conn_id,
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

    resp = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/issue-credential-2.0/send", body)
    if resp:
        return f"Plano '{nome_plano}' ({franquia}) ativado na carteira do cliente."
    return "Falha na ativação."

async def verificar_acesso(session: aiohttp.ClientSession) -> str:
    logging.info("Iniciando verificação de rede...")
    
    cred_def_id = STATE.get("plano_cred_def_id")
    if not cred_def_id: return "Erro: Sistema não configurado. Execute o setup primeiro."

    # 1. Conexão Verificador <-> Cliente
    # Criamos o convite
    body_inv = {"handshake_protocols": ["https://didcomm.org/didexchange/1.0"]}
    inv_resp = await admin_request(session, "POST", f"{VERIFICADOR_ADMIN}/out-of-band/create-invitation", body_inv)
    
    # O Cliente aceita
    await admin_request(session, "POST", f"{CLIENTE_ADMIN}/out-of-band/receive-invitation", inv_resp["invitation"])
    
    # ESPERA INTELIGENTE PELA CONEXÃO
    # Tenta por até 15 segundos encontrar a conexão ativa
    verifier_conn_id = None
    for _ in range(15):
        await asyncio.sleep(1)
        conns = await admin_request(session, "GET", f"{VERIFICADOR_ADMIN}/connections", params={"their_label": "Holder", "state": "active"})
        if conns and conns.get("results"):
            # Pega a mais recente
            verifier_conn_id = conns["results"][-1]["connection_id"] # -1 pega a última da lista
            break
    
    if not verifier_conn_id:
        return "Erro: Falha ao estabelecer conexão ativa entre Rede e Cliente (Timeout de conexão)."

    # 2. Solicitar Prova
    req_body = {
        "connection_id": verifier_conn_id,
        "presentation_request": {
            "anoncreds": {
                "name": "Verificacao de Rede TelecomX",
                "version": "1.0",
                "requested_attributes": {
                    "attr1": {"name": "franquia_gb", "restrictions": [{"cred_def_id": cred_def_id}]},
                    "attr2": {"name": "nome_plano", "restrictions": [{"cred_def_id": cred_def_id}]}
                },
                "requested_predicates": {}
            }
        }
    }
    
    proof_resp = await admin_request(session, "POST", f"{VERIFICADOR_ADMIN}/present-proof-2.0/send-request", req_body)
    if not proof_resp: return "Erro ao enviar pedido de prova."
    
    pres_ex_id = proof_resp["pres_ex_id"]

    # 3. Aumento de verificação para 90 segundos
    logging.info("Aguardando prova do cliente (pode demorar devido à carga da CPU)...")
    for i in range(90):
        await asyncio.sleep(1)
        record = await admin_request(session, "GET", f"{VERIFICADOR_ADMIN}/present-proof-2.0/records/{pres_ex_id}")
        
        if not record: continue
        
        state = record["state"]
        logging.info(f"Status da prova ({i}s): {state}") # Log para você acompanhar

        if state == "done" or state == "verified":
            if str(record["verified"]).lower() == "true":
                try:
                    dados = record["by_format"]["pres"]["anoncreds"]["presentation"]["requested_proof"]["revealed_attrs"]
                    return f"Acesso Liberado! Plano: {dados['attr2']['raw']} | Franquia: {dados['attr1']['raw']}"
                except KeyError:
                    return "Verificado, mas erro ao ler dados."
            else:
                return "Acesso Negado! Credencial inválida."
        
        if state == "abandoned":
             return "O Cliente rejeitou o pedido de prova."
                
    return "Timeout: O Cliente demorou muito para responder (Tente novamente)."