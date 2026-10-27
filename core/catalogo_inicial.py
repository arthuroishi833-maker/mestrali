"""Listas iniciais do catálogo, uma por área de trabalho, criadas no primeiro acesso.

Os valores são APENAS EXEMPLOS para demonstração. Cada técnico deve
ajustar custo e preço na tela Catálogo.

  tipo:  "mao_de_obra" (serviço) ou "peca"
  custo: quanto o técnico gasta (material, peça)
  preco: quanto cobra do cliente
"""

# Nome mostrado na tela para cada tipo. No banco o valor continua sendo
# "mao_de_obra" / "peca" (trocar o valor exigiria alterar o banco).
TIPOS = {"mao_de_obra": "Serviço", "peca": "Peça"}
# Títulos das seções do catálogo (plural).
TIPOS_PLURAL = {"mao_de_obra": "Serviços", "peca": "Peças"}



def _item(nome, tipo, custo, preco):
    return {"nome": nome, "tipo": tipo, "custo": float(custo), "preco": float(preco)}


S, P = "mao_de_obra", "peca"

# Uma lista de exemplo para cada área de trabalho. No primeiro acesso o
# técnico escolhe a área (telas/catalogo.py) e recebe a lista dela.
# Para incluir uma área nova, basta acrescentar uma entrada aqui.
# "outra" começa com o catálogo vazio, para quem prefere cadastrar tudo.
AREAS = {
    "ar_condicionado": {
        "nome": "Ar-condicionado e refrigeração",
        "itens": [
            _item("Instalação de split", S, 120, 550),
            _item("Limpeza / higienização", S, 20, 180),
            _item("Manutenção preventiva", S, 15, 150),
            _item("Carga de gás", S, 150, 350),
            _item("Capacitor", P, 30, 90),
            _item("Motor ventilador", P, 220, 420),
            _item("Bobina", P, 90, 220),
            _item("Compressor", P, 750, 1450),
            _item("Placa eletrônica", P, 280, 580),
        ],
    },
    "eletrica": {
        "nome": "Elétrica",
        "itens": [
            _item("Visita técnica / diagnóstico", S, 10, 100),
            _item("Instalação de tomada ou interruptor", S, 5, 60),
            _item("Instalação de chuveiro elétrico", S, 10, 120),
            _item("Instalação de luminária", S, 5, 80),
            _item("Troca de disjuntor", S, 5, 90),
            _item("Disjuntor", P, 18, 40),
            _item("Tomada com placa", P, 12, 28),
            _item("Fio 2,5 mm (metro)", P, 3, 6),
            _item("Lâmpada LED", P, 9, 20),
        ],
    },
    "hidraulica": {
        "nome": "Hidráulica e encanamento",
        "itens": [
            _item("Visita técnica / diagnóstico", S, 10, 100),
            _item("Desentupimento de pia ou ralo", S, 15, 150),
            _item("Conserto de vazamento", S, 15, 160),
            _item("Troca de torneira", S, 5, 80),
            _item("Reparo de descarga", S, 10, 120),
            _item("Torneira", P, 45, 95),
            _item("Sifão", P, 15, 35),
            _item("Kit reparo de descarga", P, 35, 75),
            _item("Registro", P, 40, 85),
        ],
    },
    "seguranca": {
        "nome": "Câmeras, alarmes e portões",
        "itens": [
            _item("Visita técnica / diagnóstico", S, 10, 100),
            _item("Instalação de câmera", S, 15, 150),
            _item("Configuração de acesso pelo celular", S, 0, 100),
            _item("Manutenção de portão eletrônico", S, 20, 180),
            _item("Instalação de interfone", S, 15, 160),
            _item("Câmera", P, 160, 290),
            _item("Gravador (DVR)", P, 380, 650),
            _item("Fonte de alimentação", P, 25, 60),
            _item("Cabo (metro)", P, 2, 5),
        ],
    },
    "linha_branca": {
        "nome": "Geladeiras e máquinas de lavar",
        "itens": [
            _item("Visita técnica / diagnóstico", S, 10, 100),
            _item("Conserto de máquina de lavar", S, 20, 220),
            _item("Conserto de geladeira", S, 20, 250),
            _item("Carga de gás em geladeira", S, 90, 300),
            _item("Limpeza interna de máquina de lavar", S, 15, 150),
            _item("Placa eletrônica", P, 220, 450),
            _item("Bomba de drenagem", P, 55, 130),
            _item("Termostato", P, 45, 110),
            _item("Borracha da porta", P, 80, 180),
        ],
    },
    "bikes_eletricas": {
        "nome": "Bikes e scooters elétricas",
        "itens": [
            _item("Visita técnica / diagnóstico", S, 10, 100),
            _item("Revisão geral", S, 20, 200),
            _item("Troca de pneu ou câmara de ar", S, 10, 80),
            _item("Regulagem de freios", S, 5, 70),
            _item("Reparo elétrico (controlador ou fiação)", S, 20, 180),
            _item("Câmara de ar", P, 25, 50),
            _item("Pastilha de freio (par)", P, 30, 60),
            _item("Controlador", P, 250, 420),
            _item("Carregador", P, 120, 220),
        ],
    },
    "outra": {"nome": "Outra área (começo com o catálogo vazio)", "itens": []},
}

# A lista de ar-condicionado, usada nos exemplos da página e nos testes.
ITENS_INICIAIS = AREAS["ar_condicionado"]["itens"]
