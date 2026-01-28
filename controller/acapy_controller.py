import aiohttp
import logging
import asyncio
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constantes ---
OPERADORA_ADMIN = "http://localhost:8001"
CLIENTE_ADMIN = "http://localhost:8011"
# VERIFICADOR_ADMIN foi removido. A Operadora fará tudo.

# --- Estado em Memória ---
STATE = {
    "operadora_did": None,
    "kyc_schema_id": None,
    "kyc_cred_def_id": None,
    "plano_schema_id": None,
    "plano_cred_def_id": None,
    "conn_id_operadora": None 
    # conn_id_verificador removido
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
        return "Erro crítico: Não foi possível obter o DID público da Operadora. Verifique se o agente está rodando."
    
    op_did = did_data["result"]["did"]
    STATE["operadora_did"] = op_did

    # 2. Schema e CredDef: Identidade (KYC)
    s_kyc = {"schema": {"issuerId": op_did, "name": "identidade-assinante", "version": "1.0", "attrNames": ["nome_completo", "cpf", "status_conta"]}}
    resp_s_kyc = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/anoncreds/schema", s_kyc)
    
    if not resp_s_kyc: return "Erro ao criar Schema de Identidade."
    STATE["kyc_schema_id"] = resp_s_kyc["schema_state"]["schema_id"]

    cd_kyc = {"credential_definition": {"issuerId": op_did, "schemaId": STATE["kyc_schema_id"], "tag": "kyc"}}
    resp_cd_kyc = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/anoncreds/credential-definition", cd_kyc)
    
    if not resp_cd_kyc: return "Erro ao criar CredDef de Identidade."
    STATE["kyc_cred_def_id"] = resp_cd_kyc["credential_definition_state"]["credential_definition_id"]

    # 3. Schema e CredDef: Plano (Promoção)
    s_plano = {"schema": {"issuerId": op_did, "name": "plano-dados", "version": "1.0", "attrNames": ["nome_plano", "franquia_gb", "validade"]}}
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
        # Ordena para pegar a conexão ativa mais recente
        sorted_conns = sorted(conns["results"], key=lambda x: x["created_at"], reverse=True)
        STATE["conn_id_operadora"] = sorted_conns[0]["connection_id"]
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
    logging.info("Iniciando verificação de rede (via Operadora)...")
    
    conn_id = STATE.get("conn_id_operadora")
    cred_def_id = STATE.get("plano_cred_def_id")

    if not conn_id: return "Erro: Cliente não está conectado à Operadora."
    if not cred_def_id: return "Erro: Sistema não configurado."

    # 1. Solicitar Prova
    req_body = {
        "connection_id": conn_id,
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
    
    proof_resp = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/present-proof-2.0/send-request", req_body)
    if not proof_resp: return "Erro ao enviar pedido de prova."
    
    pres_ex_id = proof_resp["pres_ex_id"]

    # 2. Monitoramento e Validação
    logging.info("Aguardando prova do cliente...")
    for i in range(90):
        await asyncio.sleep(1)
        
        record = await admin_request(session, "GET", f"{OPERADORA_ADMIN}/present-proof-2.0/records/{pres_ex_id}")
        if not record or "error" in record: continue
        
        state = record["state"]
        logging.info(f"Status da prova ({i}s): {state}")

        if state == "presentation-received":
            logging.info("Prova recebida. Executando validação criptográfica...")
            
            # Executa a verificação e captura a resposta imediatamente
            verified_record = await admin_request(session, "POST", f"{OPERADORA_ADMIN}/present-proof-2.0/records/{pres_ex_id}/verify-presentation")
            
            if verified_record:
                is_verified = str(verified_record.get("verified")).lower()
                
                if is_verified == "true":
                    try:
                        # Tenta localizar os dados na estrutura 'indy' ou 'anoncreds'
                        pres_data = verified_record["by_format"]["pres"]
                        target = pres_data.get("indy") or pres_data.get("anoncreds")
                        
                        if target:
                            dados = target["presentation"]["requested_proof"]["revealed_attrs"]
                            plano = dados['attr2']['raw']
                            franquia = dados['attr1']['raw']
                            return f"Acesso Liberado. Plano: {plano} | Franquia: {franquia}"
                        else:
                            logging.warning(f"Estrutura JSON desconhecida: {pres_data.keys()}")
                            return "Verificado com sucesso, mas o formato dos dados não foi reconhecido."

                    except KeyError as e:
                        logging.error(f"Erro ao extrair atributos da prova: {e}")
                        return "Verificado com sucesso (dados ocultos ou erro de leitura)."
                else:
                    return "Acesso Negado. A assinatura digital apresentada é inválida."
            else:
                return "Erro interno ao processar a verificação."

        if state == "abandoned":
             return "Operação cancelada: O cliente rejeitou o pedido de prova."
                
    return "Timeout: O processo excedeu o tempo limite de resposta."