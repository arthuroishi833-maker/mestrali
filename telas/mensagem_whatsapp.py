"""Caixa com a mensagem do WhatsApp, editável, e o botão que abre a conversa.

Por que um componente próprio
-----------------------------
Com as peças prontas do Streamlit (st.text_area + st.link_button) haveria um
defeito: o Streamlit só fica sabendo do texto novo quando a pessoa SAI da
caixa. Quem editasse e tocasse direto no botão abriria o WhatsApp ainda com o
texto antigo. Aqui o endereço do botão é refeito no navegador a cada tecla,
então o que está na caixa é sempre o que vai para a conversa.

Nada é enviado ao servidor: a edição vale só para aquele envio. A mensagem
fixa do técnico é gravada no Perfil.

SEGURANÇA: o texto entra no endereço por encodeURIComponent, então nenhum
caractere digitado consegue mudar para onde o botão aponta. O início do
endereço (https://wa.me/...) vem pronto do Python, de core/whatsapp.py.
"""

import streamlit as st

from core.validacao import MAX_MENSAGEM_ENVIO
from core.whatsapp import inicio_do_link

_HTML = """
<div class="mensagem">
  <label class="rotulo" for="texto">2. Confira a mensagem (pode editar)</label>
  <textarea id="texto" rows="8"></textarea>
  <div class="apoio">
    <button class="restaurar" type="button" hidden>Desfazer minhas alterações</button>
    <span class="contador" aria-live="polite"></span>
  </div>
  <a class="abrir" target="_blank" rel="noopener noreferrer">3. Abrir o WhatsApp com esta mensagem</a>
</div>
"""

_CSS = """
.mensagem { font-family: inherit; color: var(--st-text-color); }
.rotulo { display: block; font-weight: 600; font-size: 0.98rem; margin-bottom: 0.35rem; }
textarea {
  display: block; width: 100%; box-sizing: border-box; resize: vertical;
  min-height: 9rem; padding: 0.7rem 0.8rem;
  font: inherit; font-size: 1.05rem; line-height: 1.45; color: inherit;
  background: var(--st-secondary-background-color);
  border: 1px solid var(--st-border-color); border-radius: 10px;
}
textarea:focus { outline: 2px solid var(--st-primary-color); outline-offset: -1px; }
.apoio {
  display: flex; justify-content: space-between; align-items: center; gap: 0.75rem;
  min-height: 2rem; margin: 0.3rem 0 0.7rem; font-size: 0.9rem; color: #42526A;
}
.contador { margin-left: auto; font-variant-numeric: tabular-nums; }
.contador.cheio { color: #B42318; font-weight: 700; }
.restaurar {
  font: inherit; font-weight: 600; color: var(--st-primary-color);
  background: none; border: 0; padding: 0.3rem 0; cursor: pointer; text-decoration: underline;
}
.abrir {
  display: flex; align-items: center; justify-content: center; box-sizing: border-box;
  width: 100%; min-height: 3rem; padding: 0.5rem 1rem;
  font-weight: 600; font-size: 1.02rem; text-align: center; text-decoration: none;
  color: var(--st-text-color); background: #FFFFFF;
  border: 1px solid var(--st-border-color); border-radius: 12px;
  transition: background-color 150ms ease, border-color 150ms ease, transform 80ms ease;
}
.abrir:active { transform: scale(0.985); }
.abrir:focus-visible, .restaurar:focus-visible { outline: 3px solid #8DB8F5; outline-offset: 2px; }
@media (hover: hover) and (pointer: fine) {
  .abrir:hover { border-color: var(--st-primary-color); color: var(--st-primary-color); }
}
[hidden] { display: none !important; }
@media (prefers-reduced-motion: reduce) { .abrir { transition: none; } }
"""

_JS = """
export default function (component) {
  const { data, parentElement } = component;
  const raiz = parentElement.querySelector(".mensagem");
  if (!raiz) return;
  const caixa = raiz.querySelector("textarea");
  const abrir = raiz.querySelector(".abrir");
  const restaurar = raiz.querySelector(".restaurar");
  const contador = raiz.querySelector(".contador");

  caixa.maxLength = data.maximo;
  // Só preenche na primeira vez (ou quando o texto original mudou): se o
  // Streamlit redesenhar a tela, o que a pessoa já editou não se perde.
  if (raiz.dataset.original !== data.texto) {
    raiz.dataset.original = data.texto;
    caixa.value = data.texto;
  }

  function atualizar() {
    // O endereço do botão acompanha a caixa, a cada tecla.
    abrir.href = data.inicio + encodeURIComponent(caixa.value.trim());
    contador.textContent = caixa.value.length + " / " + data.maximo;
    contador.classList.toggle("cheio", caixa.value.length >= data.maximo);
    restaurar.hidden = caixa.value === data.texto;
  }
  caixa.oninput = atualizar;
  restaurar.onclick = () => { caixa.value = data.texto; atualizar(); caixa.focus(); };
  atualizar();
}
"""

def mostrar(telefone, mensagem, chave):
    """Desenha a caixa com a mensagem e o botão "Abrir o WhatsApp".

    telefone: do cliente, só dígitos (ou "" para escolher o contato no WhatsApp).
    mensagem: o texto inicial, já montado por core.whatsapp.montar_mensagem.
    chave: identificador único na tela (um por orçamento).
    """
    # Registrar aqui dentro (a cada desenho da tela) é o uso normal do
    # Streamlit e mantém o componente disponível em qualquer sessão.
    componente = st.components.v2.component("mensagem_whatsapp", html=_HTML, css=_CSS, js=_JS)
    componente(
        key=chave,
        data={
            # O limite daqui é maior que o do modelo do Perfil: os marcadores
            # ({cliente}, {equipamento}...) já foram trocados e o texto cresceu.
            "texto": mensagem[:MAX_MENSAGEM_ENVIO],
            "inicio": inicio_do_link(telefone),
            "maximo": MAX_MENSAGEM_ENVIO,
        },
    )
