"""Privacidade (LGPD): textos da política e rotinas de exportação.

ATENÇÃO, DONO DO SISTEMA
------------------------
Os valores marcados com PREENCHER abaixo são informações jurídicas que só
você (com um advogado) pode definir. Enquanto houver algum PREENCHER, a
política aparece com esses avisos e o sistema NÃO deve ser oferecido a
usuários reais.

Mudou o texto da política de forma relevante? Aumente VERSAO_POLITICA:
todos os usuários terão de aceitar a nova versão no próximo acesso.
"""

import re
from datetime import datetime, timezone

from core.busca import normalizar

VERSAO_POLITICA = "1.0"
PREENCHER = "PREENCHER"

# ---------------------------------------------------------------- PREENCHER
DATA_DA_POLITICA = "13/10/2026"        # ex.: "15/10/2026"
CONTROLADOR_NOME = "Arthur Oishi do Amaral Ribeiro e Breno Fonseca Regis"        # nome ou razão social de quem oferece o sistema
# Opcional. Fica vazio no piloto, de propósito: o CPF apareceria para todo técnico
# que criasse conta. Nome, cidade e e-mail já dizem quem é o responsável. Quando
# houver CNPJ, escreva-o aqui (ex.: "CNPJ 00.000.000/0001-00") e ele entra na política.
CONTROLADOR_DOCUMENTO = ""
CONTROLADOR_CIDADE = "Vila Velha/ES"      # ex.: "Vila Velha/ES"
ENCARREGADO_NOME = "Arthur Oishi do Amaral Ribeiro e Breno Fonseca Regis"        # pessoa que responde pelos pedidos de privacidade
ENCARREGADO_EMAIL = "mestrali.orcamentos@gmail.com"       # canal de contato de privacidade
PRAZO_DE_RESPOSTA = "15 dias"       # ex.: "15 dias"
PRAZO_DE_RETENCAO = "Enquanto a sua conta existir; depois do encerramento, os dados são apagados em até 30 dias"       # por quanto tempo os orçamentos ficam guardados
BASE_LEGAL_DA_CONTA = "execução de contrato (LGPD, art. 7º, V)"     # ex.: execução de contrato (art. 7º, V)
BASE_LEGAL_DOS_CLIENTES = "legítimo interesse do técnico em orçar o serviço pedido pelo cliente (LGPD, art. 7º, IX)" # base legal para tratar dados dos clientes dos técnicos
REGIAO_DO_SUPABASE = "São Paulo, Brasil (sa-east-1)"      # painel do Supabase > Project Settings > General > Region
PROVEDOR_DE_EMAIL = "Gmail (Google), Estados Unidos"       # quem envia os e-mails de acesso. Ex.: "Gmail (Google), Estados Unidos"
# --------------------------------------------------------------------------


def pendencias():
    """Nomes dos campos acima que ainda estão como PREENCHER."""
    campos = {
        "DATA_DA_POLITICA": DATA_DA_POLITICA,
        "CONTROLADOR_NOME": CONTROLADOR_NOME,
        "CONTROLADOR_CIDADE": CONTROLADOR_CIDADE,
        "ENCARREGADO_NOME": ENCARREGADO_NOME,
        "ENCARREGADO_EMAIL": ENCARREGADO_EMAIL,
        "PRAZO_DE_RESPOSTA": PRAZO_DE_RESPOSTA,
        "PRAZO_DE_RETENCAO": PRAZO_DE_RETENCAO,
        "BASE_LEGAL_DA_CONTA": BASE_LEGAL_DA_CONTA,
        "BASE_LEGAL_DOS_CLIENTES": BASE_LEGAL_DOS_CLIENTES,
        "REGIAO_DO_SUPABASE": REGIAO_DO_SUPABASE,
        "PROVEDOR_DE_EMAIL": PROVEDOR_DE_EMAIL,
    }
    return [nome for nome, valor in campos.items() if valor == PREENCHER]


# Textos de finalidade mostrados nas telas onde os dados são pedidos.
FINALIDADE_CADASTRO = "Usamos seu e-mail só para criar e proteger sua conta."
FINALIDADE_PERFIL = (
    "Estes dados aparecem nos orçamentos que você envia aos seus clientes. "
    "Não são usados para mais nada."
)
FINALIDADE_CLIENTE = (
    "Os dados do cliente servem só para gerar e enviar este orçamento. "
    "Não inclua CPF, endereço completo nem informações de saúde."
)


def quem_somos():
    """Nome, documento (se houver) e cidade do responsável, separados por vírgula."""
    partes = [CONTROLADOR_NOME, CONTROLADOR_DOCUMENTO.strip(), CONTROLADOR_CIDADE]
    return ", ".join(parte for parte in partes if parte)


def texto_da_politica():
    """A política de privacidade, em Markdown, escrita a partir do que o código faz."""
    return f"""
**Política de Privacidade — versão {VERSAO_POLITICA}, de {DATA_DA_POLITICA}**

**1. Quem somos.** {quem_somos()},
responsáveis por este sistema de orçamentos para prestadores de serviço.

**2. Dados da sua conta (você, técnico).**
- E-mail e senha: para você entrar e recuperar o acesso. A senha é guardada
  apenas de forma embaralhada (hash); ninguém consegue lê-la.
- Nome da empresa, telefone e logo: aparecem nos orçamentos que você gera.
- Itens do catálogo, com seus custos e preços: para montar os orçamentos.
- Registro de aceite desta política: versão aceita, data e hora.

Base legal: {BASE_LEGAL_DA_CONTA}.

**3. Dados dos seus clientes.**
Nome, telefone (opcional), equipamento, condições de pagamento e observações
de cada orçamento. São usados só para gerar o PDF, montar a mensagem do
WhatsApp e listar seus orçamentos. Você, técnico, é quem decide coletar esses
dados e responde por eles perante o seu cliente; nós apenas os guardamos e
processamos para você. Base legal: {BASE_LEGAL_DOS_CLIENTES}.

**4. O que não coletamos.** CPF, endereço completo, dados de pagamento,
localização e dados sensíveis (como saúde). Não use os campos de texto livre
para esse tipo de informação. O sistema não se destina a menores de 18 anos.

**5. Com quem os dados são compartilhados.**
- Supabase (banco de dados e login), região {REGIAO_DO_SUPABASE}.
- Provedor de e-mail, que envia a confirmação de cadastro e o código de senha
  e por isso recebe o seu endereço de e-mail: {PROVEDOR_DE_EMAIL}.
- Streamlit Community Cloud (hospedagem do aplicativo), Estados Unidos.
- WhatsApp (Meta): recebe o telefone e o primeiro nome do cliente, o
  equipamento e o valor total, somente quando você toca no botão de enviar.

Parte desses serviços fica fora do Brasil, o que caracteriza transferência
internacional de dados. Não vendemos dados e não usamos publicidade nem
ferramentas de análise de comportamento.

**6. Cookies.** Usamos um cookie essencial para manter seu login por até
30 dias e um cookie técnico de segurança da plataforma. Não há cookies de
publicidade.

**7. Por quanto tempo guardamos.** {PRAZO_DE_RETENCAO}. Você pode apagar
orçamentos, os dados de um cliente ou a conta inteira a qualquer momento,
na tela Privacidade.

**8. Seus direitos.** Confirmar, acessar, corrigir, exportar e apagar seus
dados, e retirar seu consentimento. A exportação e a exclusão estão na tela
Privacidade; para os demais pedidos, use o canal abaixo.

**9. Encarregado de dados.** {ENCARREGADO_NOME} — {ENCARREGADO_EMAIL}.
Respondemos em até {PRAZO_DE_RESPOSTA}.
"""


def texto_do_contato():
    """Texto do canal de privacidade (contato do encarregado)."""
    return f"""
**Canal de privacidade**

Dúvidas ou pedidos sobre dados pessoais: **{ENCARREGADO_EMAIL}**
(encarregado: {ENCARREGADO_NOME}). Respondemos em até {PRAZO_DE_RESPOSTA}.

**É cliente de um técnico que usa este sistema?** Procure primeiro o técnico
que fez o seu orçamento: é ele quem pode localizar, entregar ou apagar os
seus dados. Se não conseguir, escreva para o e-mail acima.
"""


# ------------------------------------------------------------- exportação
def so_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def orcamento_e_do_cliente(orcamento, termo):
    """True se o orçamento pertence ao cliente procurado.

    termo: parte do nome (ignora acentos e maiúsculas) OU o telefone
    (com ou sem máscara; precisa ter pelo menos 8 dígitos para valer).
    """
    termo_nome = normalizar(termo)
    if not termo_nome:
        return False
    digitos = so_digitos(termo)
    if len(digitos) >= 8 and digitos in so_digitos(orcamento.get("cliente_telefone")):
        return True
    return termo_nome in normalizar(orcamento.get("cliente_nome"))


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def montar_exportacao_da_conta(email, perfil, catalogo, orcamentos, aceites):
    """Tudo o que o sistema guarda sobre o técnico, num dict pronto para virar JSON."""
    return {
        "gerado_em": _agora(),
        "conta": {"email": email},
        "perfil": perfil,
        "catalogo": catalogo,
        "orcamentos": orcamentos,
        "aceites_da_politica": aceites,
    }


def montar_exportacao_do_cliente(termo, orcamentos):
    """Os orçamentos de um cliente, sem os custos e a margem do técnico.

    O arquivo é para entregar ao cliente: leva só o que diz respeito a ele.
    """
    limpos = []
    for orcamento in orcamentos:
        limpos.append({
            "numero": orcamento.get("numero"),
            "data": orcamento.get("criado_em"),
            "cliente_nome": orcamento.get("cliente_nome"),
            "cliente_telefone": orcamento.get("cliente_telefone"),
            "equipamento": orcamento.get("equipamento"),
            "condicoes_pagamento": orcamento.get("condicoes_pagamento"),
            "observacoes": orcamento.get("observacoes"),
            "total": orcamento.get("total"),
            "itens": [
                {"descricao": item.get("nome"), "quantidade": item.get("quantidade"),
                 "valor_unitario": item.get("preco_unitario")}
                for item in orcamento.get("itens", [])
            ],
        })
    return {"gerado_em": _agora(), "busca": termo, "orcamentos": limpos}


# Valores gravados no lugar dos dados pessoais quando um cliente é anonimizado.
# Os itens e os valores do orçamento ficam, para o histórico do técnico.
DADOS_ANONIMOS = {
    "cliente_nome": "Cliente removido",
    "cliente_telefone": "",
    "equipamento": "",
    "condicoes_pagamento": "",
    "observacoes": "",
}
