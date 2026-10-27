"""Atendimento: contatos de suporte e as perguntas frequentes da tela Ajuda.

ATENÇÃO, DONO DO SISTEMA
------------------------
Preencha os três valores abaixo com os contatos de vocês. Enquanto estiverem
como PREENCHER, a tela Ajuda mostra as perguntas frequentes e avisa que o
canal de atendimento ainda está sendo configurado.
"""

from core.validacao import formatar_telefone, validar_email, validar_telefone
from core.whatsapp import montar_link

PREENCHER = "PREENCHER"

# ---------------------------------------------------------------- PREENCHER
SUPORTE_WHATSAPP = "27992432065"   # só números, com DDD. Ex.: "27999990000"
SUPORTE_EMAIL = "mestrali.orcamentos@gmail.com"      # ex.: "suporte@seudominio.com.br"
SUPORTE_HORARIO = "Segunda a sexta, das 8h às 18h"    # ex.: "Segunda a sexta, das 8h às 18h"
# --------------------------------------------------------------------------

MENSAGEM_INICIAL = "Olá! Preciso de ajuda com o sistema de orçamentos."


def whatsapp_do_suporte():
    """Devolve o WhatsApp de suporte (só dígitos), ou "" se não estiver configurado."""
    numero, erro = validar_telefone("" if SUPORTE_WHATSAPP == PREENCHER else SUPORTE_WHATSAPP)
    return "" if erro else numero


def email_do_suporte():
    """Devolve o e-mail de suporte, ou "" se não estiver configurado."""
    email, erro = validar_email("" if SUPORTE_EMAIL == PREENCHER else SUPORTE_EMAIL)
    return "" if erro else email


def horario_do_suporte():
    return "" if SUPORTE_HORARIO == PREENCHER else SUPORTE_HORARIO.strip()


def contato_configurado():
    """True se há pelo menos um jeito de falar com o suporte."""
    return bool(whatsapp_do_suporte() or email_do_suporte())


def link_do_whatsapp():
    """Link que abre a conversa com o suporte, ou "" se não houver WhatsApp."""
    numero = whatsapp_do_suporte()
    return montar_link(numero, MENSAGEM_INICIAL) if numero else ""


def whatsapp_formatado():
    return formatar_telefone(whatsapp_do_suporte())


# Perguntas frequentes. Cada resposta descreve o que o sistema FAZ hoje;
# ao mudar uma tela, confira se a resposta daqui continua verdadeira.
# (pergunta, resposta, aparece_antes_do_login)
PERGUNTAS = [
    ("Esqueci minha senha. O que eu faço?",
     "Na tela de entrada, digite o seu e-mail e toque em **Esqueci minha senha**. "
     "O código chega nesse mesmo e-mail: digite-o e crie a senha nova.",
     True),
    ("Não recebi o e-mail de confirmação ou o código.",
     "Espere alguns minutos e olhe também a caixa de **spam**. Confira se digitou o e-mail "
     "certo. Se não chegar, fale com o suporte.",
     True),
    ("Que senha o sistema aceita?",
     "Pelo menos 8 caracteres, com letra minúscula, letra maiúscula, número e um destes "
     "símbolos: @ # $ % &. Sequências como 1234 ou abcd não são aceitas. A barra de força "
     "mostra o que falta enquanto você digita.",
     True),
    ("Como envio o orçamento para o cliente?",
     "Depois de salvar, toque em **1. Baixar o PDF** e em seguida em **2. Abrir o WhatsApp "
     "com a mensagem pronta**. O WhatsApp abre com o texto preenchido, mas não anexa "
     "arquivos: anexe na conversa o PDF que você baixou.",
     False),
    ("O cliente vê meu custo ou meu lucro?",
     "Não. Custo, lucro e margem aparecem só para você, no **Resumo interno**. O PDF e a "
     "mensagem do WhatsApp nunca mostram esses números.",
     False),
    ("Posso mudar o preço só em um orçamento?",
     "Sim. No passo **Itens**, altere o **Valor unitário** do item. O preço do catálogo "
     "continua o mesmo para os próximos orçamentos.",
     False),
    ("O item que eu preciso não está no catálogo.",
     "No passo **Itens**, use a aba **Item avulso** para um item só deste orçamento, ou "
     "cadastre o item em **Catálogo** para usar sempre.",
     False),
    ("Errei um orçamento que já salvei.",
     "Em **Orçamentos**, abra o orçamento. **Corrigir dados do cliente** altera nome, "
     "WhatsApp, equipamento, pagamento e observações. Itens e valores não mudam depois de "
     "salvos: exclua o orçamento e faça outro.",
     False),
    ("Como coloco meu logo e meu telefone no PDF?",
     "Em **Perfil**, preencha o nome da empresa, o telefone e envie o logo. Eles passam a "
     "aparecer no topo de todos os orçamentos.",
     False),
    ("Preciso entrar com a senha toda vez?",
     "Não. Neste aparelho você continua conectado por até 30 dias. Para sair, use **Sair da "
     "conta**, em **Perfil**. Em aparelho emprestado, saia sempre ao terminar.",
     False),
    ("Como apago meus dados ou os de um cliente?",
     "Em **Perfil**, abra **Privacidade**. Lá você baixa uma cópia dos seus dados, remove "
     "os dados de um cliente ou exclui a sua conta.",
     False),
]


def perguntas(antes_do_login=False):
    """As perguntas da Ajuda. Antes do login, só as que tratam de acesso."""
    return [(p, r) for p, r, acesso in PERGUNTAS if acesso or not antes_do_login]
