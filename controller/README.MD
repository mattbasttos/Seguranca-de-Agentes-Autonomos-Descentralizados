# 📘 Chatbot de Operadora com IA e Identidade Descentralizada (CLI)

Este projeto simula uma operadora de telecomunicações onde um **Agente de IA (Ollama/Phi-3)** interpreta comandos de linguagem natural para controlar uma infraestrutura de **Identidade Autossoberana (Hyperledger Aries)**.

O sistema permite configurar a operadora, registrar novos clientes e vender planos de dados, tudo via API e registrado imutavelmente em Blockchain.

-----

## 🛠️ Pré-requisitos

  * **Sistema Operacional:** Linux (Ubuntu/WSL2).
  * **Docker:** Para rodar a rede Blockchain (VON Network).
  * **Python 3.12+:** Para os scripts de controle.
  * **Ollama:** Para rodar o modelo de IA localmente.
  * **GPU (Recomendado):** Para resposta rápida da IA.

-----

## 🚀 Guia de Instalação e Execução

Siga a ordem exata abaixo para garantir o funcionamento.

### 1\. Preparar a Inteligência Artificial (Ollama)

Certifique-se de que o serviço Ollama está rodando e baixe o modelo leve (Phi-3 Mini) para garantir estabilidade e velocidade.

```bash
# Verificar status do serviço
sudo systemctl status ollama

# Se der erro 500 ou travar, reinicie:
sudo systemctl restart ollama

# Baixar o modelo (apenas na primeira vez)
ollama pull phi3:mini
```

### 2\. Limpeza do Ambiente (Crucial)

Para evitar erros de *"Schema already exists"* no Blockchain, limpe as carteiras antigas antes de cada demonstração.

```bash
# Pare todos os terminais (Ctrl+C) e execute:
rm -rf ~/.indy_client/wallet/issuer_wallet_prod
rm -rf ~/.indy_client/wallet/holder_wallet_clean
```

### 3\. Iniciar a Infraestrutura (Terminais 1, 2 e 3)

Abra terminais separados para cada componente:

  * **Terminal 1 (Blockchain Ledger):**

    ```bash
    cd von-network
    ./manage start
    ```

  * **Terminal 2 (Operadora TelecomX - Issuer):**

    ```bash
    source venv/bin/activate
    python issuer/run_issuer.py
    ```

  * **Terminal 3 (Cliente - Holder):**

    ```bash
    source venv/bin/activate
    python holder/run_holder.py
    ```

### 4\. Iniciar o Cérebro do Chatbot (Terminal 4)

Este servidor conecta a IA aos agentes ACA-Py.

```bash
cd controller
source ../venv/bin/activate
python chatbot_server.py
```

*Aguarde a mensagem: `Uvicorn running on http://0.0.0.0:8080`*

-----

## 💻 Roteiro de Demonstração (Comandos CURL)

Use um **Terminal 5** para enviar os comandos como se fosse o usuário conversando com o bot. Copie e cole os comandos abaixo.

### Passo 1: Configuração da Operadora (Setup)

O comando faz a IA criar os Schemas (Identidade e Planos) e as definições de credencial no Blockchain.

```bash
curl -X POST http://localhost:8080/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Inicie os sistemas da TelecomX"}'
```

  * **Resposta Esperada:** `"Infraestrutura TelecomX configurada com sucesso. DID: Th7M..."`

### Passo 2: Onboarding do Cliente (Connection)

Estabelece um canal de comunicação criptografado e seguro entre a Operadora e o Cliente.

```bash
curl -X POST http://localhost:8080/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Faça a conexão com o novo cliente"}'
```

  * **Resposta Esperada:** `"Cliente conectado e autenticado na base da TelecomX."`

### Passo 3: Venda de Plano (Issuance)

A IA entende o nome do plano e a quantidade de gigas a partir da frase e emite a credencial para a carteira do cliente.

```bash
curl -X POST http://localhost:8080/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Ative o plano TelecomX Ultra com 500GB para este cliente"}'
```

  * **Resposta Esperada:** `"Plano 'TelecomX Ultra' (500GB) ativado na carteira do cliente."`

-----

## ✅ Como Validar que Funcionou?

Para provar que o `curl` realmente gerou uma credencial verificável:

1.  Abra o navegador em: `http://localhost:8011/api/doc` (Swagger do **Cliente**).
2.  Procure a seção **credentials** e o endpoint `GET /credentials`.
3.  Clique em **Try it out** -\> **Execute**.
4.  Você verá no JSON de resposta o plano "TelecomX Ultra" e a franquia "500GB" assinados digitalmente pela Operadora.

-----

## ⚠️ Solução de Problemas

| Erro | Solução |
| :--- | :--- |
| **Erro 500 no Curl** | O Ollama travou. Rode `sudo systemctl restart ollama`. |
| **"Schema already exists"** | Você esqueceu a limpeza. Pare tudo, rode o passo 2 (Limpeza) e reinicie. |
| **"Erro: Necessário setup..."** | Você reiniciou o servidor do chatbot e ele perdeu a memória. Refaça o Passo 1 e Passo 2. |
| **Connection Refused** | Verifique se o `chatbot_server.py` está rodando na porta 8080. |