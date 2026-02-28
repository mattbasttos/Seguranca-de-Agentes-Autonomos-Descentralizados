import requests
import json

# Nosso Dataset de Validação com as 50 frases categorizadas
dataset = [
    # Categoria 1: Identidade Digital
    ("identidade", "Quero criar minha identidade digital, meu CPF é 12345678900"),
    ("identidade", "Preciso emitir meu perfil na operadora, me chamo João Silva"),
    ("identidade", "Como faço para gerar a credencial de identidade no meu nome?"),
    ("identidade", "Cadastrar identidade digital para Maria Souza, CPF 09876543211"),
    ("identidade", "Quero fazer meu ID digital agora"),
    ("identidade", "Gera aí meu perfil de usuário, CPF 11122233344"),
    ("identidade", "Preciso da minha credencial de cliente"),
    ("identidade", "Faz o meu cadastro de identidade, por favor"),
    ("identidade", "Queria registrar meus dados para ter o ID da operadora"),
    ("identidade", "Cria minha identidade, me chamo Ana"),
    ("identidade", "Emitir ID. CPF 55544433322"),
    ("identidade", "Manda o convite pra minha identidade digital"),

    # Categoria 2: Plano de Internet/Dados
    ("plano", "Quero assinar o plano Básico de 50GB"),
    ("plano", "Me vê o plano Premium com internet ilimitada"),
    ("plano", "Desejo contratar o plano de dados de 100GB"),
    ("plano", "Muda meu pacote pro plano Família, por favor"),
    ("plano", "Queria pegar aquele plano de 20 giga"),
    ("plano", "Assinar pacote de internet Básico"),
    ("plano", "Como eu contrato o plano avançado?"),
    ("plano", "Bota o plano de 50gb no meu número"),
    ("plano", "Preciso de mais internet, quero o plano Max"),
    ("plano", "Contratar plano 200GB"),
    ("plano", "Libera o pacote premium pra mim"),
    ("plano", "Quero comprar o plano controle de 30GB"),
    ("plano", "Assinatura do plano básico de dados"),

    # Categoria 3: Clube de Vantagens
    ("clube", "Quero entrar no clube de vantagens"),
    ("clube", "Como faço para participar do programa de pontos?"),
    ("clube", "Me cadastra no clube de benefícios, tenho 500 pontos"),
    ("clube", "Quero minha credencial do clube VIP"),
    ("clube", "Mano, me bota naquele esquema de vantagens lá"),
    ("clube", "Queria resgatar minha entrada no clube de ofertas"),
    ("clube", "Adiciona meu perfil no clube de recompensas"),
    ("clube", "Emitir credencial do clube"),
    ("clube", "Quero fazer parte do clube de vantagens da operadora"),
    ("clube", "Me inclui no programa VIP de benefícios"),

    # Categoria 4: Ruído / Safety (A IA deve ignorar)
    ("ruido", "Bom dia, tudo bem?"),
    ("ruido", "Minha internet caiu desde ontem, me ajuda!"),
    ("ruido", "O sinal da minha TV está ruim"),
    ("ruido", "Quero falar com um atendente humano"),
    ("ruido", "Vocês demoram muito pra responder"),
    ("ruido", "Boa tarde"),
    ("ruido", "Qual o telefone da ouvidoria?"),
    ("ruido", "Meu boleto veio com o valor errado"),
    ("ruido", "Olá!"),
    ("ruido", "Como eu faço para cancelar minha linha?"),
    ("ruido", "A fatura deste mês já fechou?"),
    ("ruido", "Tá chovendo muito aqui e o 5G não funciona"),
    ("ruido", "Obrigado pela ajuda"),
    ("ruido", "Valeu, tchau!"),
    ("ruido", "Onde fica a loja física mais próxima?")
]

def extrair_intencao_ollama(texto):
    """Envia a frase para o Ollama local e exige um retorno em JSON."""
    url = "http://localhost:11434/api/generate"
    
    prompt = f"""Analise a frase do cliente de telecomunicações. 
    Retorne APENAS um objeto JSON com a chave "intencao". 
    Os valores permitidos para "intencao" são: "identidade", "plano", "clube" ou "ruido".
    Se a frase não for um pedido claro de emissão, classifique como "ruido".
    
    Frase: "{texto}"
    """
    
    payload = {
        "model": "phi3:mini", # Mude para "phi3:mini" se for o nome exato da sua tag no Ollama
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        resposta = requests.post(url, json=payload).json()
        resultado_json = json.loads(resposta['response'])
        return resultado_json.get("intencao", "ruido")
    except Exception as e:
        return "ruido"

# Dicionário para guardar a matriz de confusão
metricas = {
    "identidade": {"VP": 0, "FP": 0, "FN": 0},
    "plano":      {"VP": 0, "FP": 0, "FN": 0},
    "clube":      {"VP": 0, "FP": 0, "FN": 0},
    "ruido":      {"VP": 0, "FP": 0, "FN": 0}
}

print("🤖 Iniciando avaliação do modelo Phi-3 com 50 frases...\n")

for i, (intencao_esperada, frase) in enumerate(dataset, 1):
    intencao_obtida = extrair_intencao_ollama(frase)
    
    print(f"[{i}/50] Testando: '{frase[:30]}...' -> Esperado: {intencao_esperada} | Obtido: {intencao_obtida}")
    
    if intencao_obtida == intencao_esperada:
        metricas[intencao_esperada]["VP"] += 1
    else:
        if intencao_obtida in metricas:
            metricas[intencao_obtida]["FP"] += 1
        metricas[intencao_esperada]["FN"] += 1

print("\n" + "="*55)
print(f"{'Categoria':<18} | {'Precisão':<10} | {'Recall':<10} | {'F1-Score':<10}")
print("-" * 55)

soma_f1 = 0

for categoria, valores in metricas.items():
    vp = valores["VP"]
    fp = valores["FP"]
    fn = valores["FN"]
    
    precisao = vp / (vp + fp) if (vp + fp) > 0 else 0
    recall = vp / (vp + fn) if (vp + fn) > 0 else 0
    f1 = (2 * precisao * recall) / (precisao + recall) if (precisao + recall) > 0 else 0
    
    soma_f1 += f1
    print(f"{categoria:<18} | {precisao:<10.2f} | {recall:<10.2f} | {f1:<10.2f}")

print("-" * 55)
media_global = soma_f1 / 4
print(f"{'MÉDIA GLOBAL':<18} | {'-':<10} | {'-':<10} | {media_global:<10.2f}")