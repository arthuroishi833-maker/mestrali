"""Confere se o domínio de um e-mail consegue receber mensagens.

O que isto faz e o que NÃO faz
------------------------------
Não existe como saber, sem enviar uma mensagem, se a caixa "fulano@..."
existe de verdade. O que dá para conferir na hora é a parte depois do "@":
perguntamos ao DNS (a "lista telefônica" da internet) se aquele domínio tem
servidor de e-mail. Isso barra erros de digitação como "gmail.con" ou
"hotmial.com.br" e domínios inventados.

A garantia de que a pessoa é dona do endereço continua sendo o link de
confirmação que o Supabase envia no cadastro ("Confirm email" ligado):
sem clicar nele, a conta não entra.

Se a consulta ao DNS falhar por problema de rede, o cadastro NÃO é
bloqueado: preferimos deixar passar (o link de confirmação resolve) a
impedir alguém de se cadastrar por uma instabilidade.
"""

from functools import lru_cache

import dns.exception
import dns.resolver

TEMPO_LIMITE = 3.0   # segundos, no total, para o DNS responder

SEM_SERVIDOR = "Não encontramos o servidor de e-mail de “@{dominio}”. Confira se digitou certo."


def _consultar(dominio, tipo):
    """Devolve as respostas do DNS; [] se o domínio existe mas não tem esse registro."""
    resolvedor = dns.resolver.Resolver()
    resolvedor.lifetime = TEMPO_LIMITE
    try:
        return list(resolvedor.resolve(dominio, tipo))
    except dns.resolver.NoAnswer:
        return []


@lru_cache(maxsize=512)
def dominio_recebe_email(dominio):
    """True = recebe; False = com certeza não recebe; None = não deu para saber."""
    try:
        registros_mx = _consultar(dominio, "MX")
        if registros_mx:
            # Um único MX "." é o jeito oficial de dizer "este domínio não recebe e-mail".
            return any(str(r.exchange) != "." for r in registros_mx)
        # Sem MX, a regra do e-mail manda tentar o endereço do próprio domínio.
        return bool(_consultar(dominio, "A") or _consultar(dominio, "AAAA"))
    except dns.resolver.NXDOMAIN:
        return False          # o domínio não existe
    except dns.exception.DNSException:
        return None           # rede fora, tempo esgotado...: não dá para afirmar nada


def erro_de_dominio(email):
    """Mensagem de erro se o domínio do e-mail não recebe mensagens; "" caso contrário."""
    dominio = email.rsplit("@", 1)[-1].strip().lower()
    if dominio_recebe_email(dominio) is False:
        return SEM_SERVIDOR.format(dominio=dominio)
    return ""
