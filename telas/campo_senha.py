"""Campos de senha: o de senha nova (com barra de força) e o simples.

Por que um componente próprio
-----------------------------
O st.text_input só avisa o Python quando o usuário aperta Enter ou sai do
campo, então não dá para mostrar a força "enquanto digita". Este componente
é um pequeno pedaço de HTML + JavaScript (Custom Components v2, a forma
oficial do Streamlit) que:

  - desenha o campo (sempre oculto, tipo "password"), a barra e a lista de
    requisitos com ✓ / ✗, tudo no navegador, a cada tecla, sem ir ao servidor
    (funciona bem mesmo com internet ruim no celular);
  - entrega a senha ao Python quando o usuário sai do campo (tocar no próximo
    campo ou no botão já conta como sair).

Sem biblioteca de terceiros: nada extra a instalar, e a senha não passa por
código que não seja deste projeto.

Por que também um campo simples (sem barra)
-------------------------------------------
Fora de um st.form, o campo de senha padrão do Streamlit tem um defeito de
uso: quem aperta Tab cai no botão do "olhinho" e o valor digitado não é
enviado; ao clicar em seguida no botão da tela, a senha chega vazia. Por
isso os campos "Repita a senha" e "Senha atual" que ficam ao lado da barra
de força usam este mesmo componente, que envia o valor sempre que o campo
perde o foco.

As REGRAS não estão escritas aqui: vêm de core/validacao.py (mínimo de
caracteres, especiais aceitos, tamanho da sequência proibida). O JavaScript
só as aplica para DESENHAR a barra. Quem decide se a senha é aceita é o
Python, em validar_senha(), antes de qualquer envio ao Supabase.
"""

import streamlit as st

from core.validacao import ESPECIAIS_DA_SENHA, MAX_SENHA, MIN_SENHA, TAMANHO_DA_SEQUENCIA

_HTML = """
<div class="campo-senha">
  <label class="rotulo" for="senha"></label>
  <div class="caixa">
    <input id="senha" type="password" autocomplete="new-password" autocapitalize="off"
           autocorrect="off" spellcheck="false" />
    <button class="olho" type="button" aria-pressed="false">Mostrar</button>
  </div>
  <div class="forca">
    <div class="trilho"><div class="barra"></div></div>
    <!-- Os três nomes ficam empilhados; o CSS mostra só o do nível atual. -->
    <span class="nivel" aria-hidden="true">
      <span data-n="fraca">Fraca</span><span data-n="media">Média</span><span data-n="forte">Forte</span>
    </span>
    <!-- Para leitores de tela: o nível em texto, anunciado quando muda. -->
    <span class="so-leitor" role="status" aria-live="polite"></span>
  </div>
  <ul class="requisitos"></ul>
</div>
"""

_CSS = """
.campo-senha { font-family: inherit; color: var(--st-text-color); }
.rotulo { display: block; font-weight: 600; font-size: 1rem; margin-bottom: 0.3rem; }
.caixa {
  display: flex; align-items: center;
  border: 1.5px solid var(--st-border-color, #5B84AD); border-radius: 12px;
  background: var(--st-secondary-background-color, #EEF6FD);
}
.caixa:focus-within { border-color: var(--st-primary-color); box-shadow: 0 0 0 3px rgba(10, 88, 202, 0.18); }
.caixa input {
  flex: 1; min-width: 0; min-height: 2.9rem; padding: 0 0.8rem;
  border: 0; outline: 0; background: transparent;
  font: inherit; font-size: 1.05rem; color: inherit;
}
.olho {
  min-height: 2.9rem; padding: 0 0.9rem; border: 0; background: transparent;
  font: inherit; font-weight: 600; color: var(--st-primary-color); cursor: pointer;
}
[hidden] { display: none !important; }
.so-leitor {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip-path: inset(50%); white-space: nowrap;
}

/* Curva de saída forte: começa rápido e assenta devagar, sem "quicar". */
.campo-senha { --saida: cubic-bezier(0.23, 1, 0.32, 1); }

/* ---------- Barra ----------
   A barra tem sempre a largura toda e desliza por dentro do trilho
   (transform), em vez de mudar de largura: o navegador desenha isso sem
   recalcular a página. Quem move a barra e mistura a cor é o JavaScript,
   com uma "mola" (veja lá embaixo): por isso aqui não há transition. */
.forca { display: flex; align-items: center; gap: 0.7rem; margin-top: 0.65rem; }
.trilho {
  position: relative; flex: 1; height: 8px; border-radius: 999px;
  background: #D5DEE8; overflow: hidden;
}
.barra {
  height: 100%; width: 100%; border-radius: 999px;
  background-color: #D92D20;
  /* A ponta da barra é um pouco mais clara, como a frente de um líquido. */
  background-image: linear-gradient(90deg, transparent 55%, rgba(255, 255, 255, 0.38));
  transform: translateX(-100%);
  will-change: transform;
}

/* Um brilho atravessa a barra uma vez, quando a senha fica forte. */
.trilho::after {
  content: ""; position: absolute; top: 0; bottom: 0; left: 0; width: 35%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
  transform: translateX(-120%);
}
.forca[data-nivel="forte"] .trilho::after {
  transform: translateX(400%);
  transition: transform 650ms var(--saida) 140ms;
}

/* ---------- Nome do nível: um sai, o outro entra ---------- */
.nivel { display: grid; min-width: 4.2rem; font-weight: 700; font-size: 0.95rem; }
.nivel span {
  grid-area: 1 / 1; opacity: 0; transform: translateY(4px);
  transition: opacity 180ms var(--saida), transform 180ms var(--saida);
}
.nivel span[data-n="fraca"] { color: #B42318; }
.nivel span[data-n="media"] { color: #93530A; }
.nivel span[data-n="forte"] { color: #0E7A4B; }
.forca[data-nivel="fraca"] .nivel span[data-n="fraca"],
.forca[data-nivel="media"] .nivel span[data-n="media"],
.forca[data-nivel="forte"] .nivel span[data-n="forte"] { opacity: 1; transform: translateY(0); }

/* ---------- Lista de requisitos ----------
   Os itens são criados uma vez e só mudam de estado: é isso que permite
   o "x" virar "visto" com transição, em vez de a lista piscar a cada tecla. */
.requisitos { list-style: none; margin: 0.55rem 0 0; padding: 0; font-size: 0.95rem; }
.requisitos li {
  display: flex; align-items: baseline; gap: 0.5rem; padding: 0.12rem 0;
  color: #42526A; transition: color 200ms ease;
}
.requisitos li.ok { color: #0F1B2D; }
.marca { display: grid; width: 1.1rem; font-weight: 800; }
.marca span {
  grid-area: 1 / 1;
  transition: opacity 160ms var(--saida), transform 160ms var(--saida);
}
.marca .nao { color: #B42318; opacity: 1; transform: scale(1); }
.marca .sim { color: #0E7A4B; opacity: 0; transform: scale(0.9); }
li.ok .marca .nao { opacity: 0; transform: scale(0.9); }
li.ok .marca .sim { opacity: 1; transform: scale(1); }

/* Quem pede menos movimento continua vendo a mudança de cor e de estado,
   mas sem deslizes: a barra pula direto para o novo tamanho. */
@media (prefers-reduced-motion: reduce) {
  .barra { transition: background-color 200ms ease; will-change: auto; }
  .trilho::after { display: none; }
  .nivel span, .marca span { transform: none !important; transition: opacity 150ms ease; }
}
"""

_JS = """
export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const raiz = parentElement.querySelector(".campo-senha");
  if (!raiz) return;
  const input = raiz.querySelector("input");
  const olho = raiz.querySelector(".olho");
  const forca = raiz.querySelector(".forca");
  const barra = raiz.querySelector(".barra");
  const anuncio = raiz.querySelector(".so-leitor");
  const lista = raiz.querySelector(".requisitos");

  raiz.querySelector(".rotulo").textContent = data.rotulo;
  input.maxLength = data.maximo;
  input.autocomplete = data.preenchimento;
  // Campo simples (repetir senha, senha atual): sem barra e sem lista.
  forca.hidden = !data.com_barra;
  lista.hidden = !data.com_barra;

  // Há sequência (1234, dcba...) de `tamanho` ou mais caracteres seguidos?
  function temSequencia(texto, tamanho) {
    const t = texto.toLowerCase();
    let subindo = 1, descendo = 1;
    for (let i = 1; i < t.length; i++) {
      const a = t[i - 1], b = t[i];
      const numeros = a >= "0" && a <= "9" && b >= "0" && b <= "9";
      const letras = a >= "a" && a <= "z" && b >= "a" && b <= "z";
      const passo = (numeros || letras) ? b.charCodeAt(0) - a.charCodeAt(0) : 0;
      subindo = passo === 1 ? subindo + 1 : 1;
      descendo = passo === -1 ? descendo + 1 : 1;
      if (subindo >= tamanho || descendo >= tamanho) return true;
    }
    return false;
  }

  // Os mesmos requisitos de core/validacao.py, com os parâmetros vindos do Python.
  function requisitos(s) {
    const especial = [...s].some((c) => data.especiais.includes(c));
    return [
      [data.minimo + " caracteres", s.length >= data.minimo],
      ["uma letra minúscula", /[a-z]/.test(s)],
      ["uma letra maiúscula", /[A-Z]/.test(s)],
      ["um número", /[0-9]/.test(s)],
      ["um caractere especial (" + [...data.especiais].join(" ") + ")", especial],
      ["sem sequências como 1234 ou abcd", s.length > 0 && !temSequencia(s, data.sequencia)],
    ];
  }

  // Cria os itens da lista UMA vez. Depois só o estado de cada um muda, o que
  // deixa o CSS fazer a transição (recriar a lista a cada tecla a faria piscar).
  function montarLista(itens) {
    lista.replaceChildren(...itens.map(([texto]) => {
      const li = document.createElement("li");
      const marca = document.createElement("span");
      marca.className = "marca";
      marca.setAttribute("aria-hidden", "true");
      const nao = document.createElement("span"); nao.className = "nao"; nao.textContent = "✗";
      const sim = document.createElement("span"); sim.className = "sim"; sim.textContent = "✓";
      marca.append(nao, sim);
      const rotulo = document.createElement("span");
      rotulo.textContent = texto;
      const estado = document.createElement("span");   // só para leitores de tela
      estado.className = "so-leitor";
      li.append(marca, rotulo, estado);
      return li;
    }));
  }

  // ---------- Movimento da barra: uma mola ----------
  // Em vez de ir de um ponto a outro num tempo fixo, a barra é puxada para o
  // alvo como se estivesse presa a uma mola: acelera, desacelera e assenta.
  // Se o alvo muda no meio do caminho (a pessoa continua digitando), ela
  // aproveita a velocidade que já tinha, sem parar nem recomeçar.
  // É a mesma conta de um controle PD: força = rigidez * erro - amortecimento * velocidade.
  const RIGIDEZ = 170, AMORTECIMENTO = 21;
  const CORES = [[217, 45, 32], [247, 144, 9], [18, 133, 90]];   // fraca, média, forte
  const mola = {
    cheio: { valor: 0, alvo: 0, vel: 0 },   // quanto da barra está preenchido (0 a 1)
    tom: { valor: 0, alvo: 0, vel: 0 },     // posição na escala de cores (0 a 2)
    quadro: 0, antes: 0,
  };

  function pintar() {
    const cheio = Math.min(1, Math.max(0, mola.cheio.valor));
    barra.style.transform = "translateX(" + ((cheio - 1) * 100).toFixed(2) + "%)";
    // Mistura as duas cores vizinhas na escala (vermelho > laranja > verde).
    const tom = Math.min(2, Math.max(0, mola.tom.valor));
    const i = Math.min(1, Math.floor(tom)), f = tom - i;
    const cor = CORES[i].map((c, k) => Math.round(c + (CORES[i + 1][k] - c) * f));
    barra.style.backgroundColor = "rgb(" + cor.join(",") + ")";
  }

  function passo(agora) {
    // dt em segundos, limitado: se a aba ficou parada, a mola não "explode".
    const dt = Math.min(0.032, (agora - mola.antes) / 1000);
    mola.antes = agora;
    let parado = true;
    for (const m of [mola.cheio, mola.tom]) {
      const forcaDaMola = RIGIDEZ * (m.alvo - m.valor) - AMORTECIMENTO * m.vel;
      m.vel += forcaDaMola * dt;
      m.valor += m.vel * dt;
      if (Math.abs(m.vel) > 0.002 || Math.abs(m.alvo - m.valor) > 0.001) parado = false;
      else { m.valor = m.alvo; m.vel = 0; }
    }
    pintar();
    mola.quadro = parado ? 0 : requestAnimationFrame(passo);
  }

  function moverBarra(cheio, tom) {
    mola.cheio.alvo = cheio;
    mola.tom.alvo = tom;
    // Quem pede menos movimento: vai direto ao alvo (a cor troca pelo CSS).
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      cancelAnimationFrame(mola.quadro); mola.quadro = 0;
      for (const m of [mola.cheio, mola.tom]) { m.valor = m.alvo; m.vel = 0; }
      pintar();
    } else if (!mola.quadro) {
      mola.antes = performance.now();
      mola.quadro = requestAnimationFrame(passo);
    }
  }

  function desenhar() {
    if (!data.com_barra) return;
    const s = input.value;
    const itens = requisitos(s);
    if (lista.children.length !== itens.length) montarLista(itens);
    itens.forEach(([, ok], i) => {
      const li = lista.children[i];
      li.classList.toggle("ok", ok);
      li.lastElementChild.textContent = ok ? " (ok)" : " (falta)";
    });

    const cumpridos = itens.filter((item) => item[1]).length;
    let nome = "", chave = "", tom = 0;
    if (s.length > 0) {
      if (cumpridos === itens.length) { nome = "Forte"; chave = "forte"; tom = 2; }
      else if (cumpridos >= 4) { nome = "Média"; chave = "media"; tom = 1; }
      else { nome = "Fraca"; chave = "fraca"; }
    }
    forca.dataset.nivel = chave;
    // O tamanho conta "meio ponto" a cada letra até chegar ao mínimo, para a
    // barra avançar um pouco a cada tecla em vez de só pular de degrau em degrau.
    const tamanho = Math.min(1, s.length / data.minimo);
    const pontos = cumpridos - (itens[0][1] ? 1 : 0) + tamanho;
    moverBarra(s.length ? Math.max(0.06, pontos / itens.length) : 0, tom);
    const frase = nome ? "Força da senha: " + nome : "";
    if (anuncio.textContent !== frase) anuncio.textContent = frase;
  }

  // Entrega a senha ao Python só quando o usuário SAI do campo (ou o navegador
  // preenche sozinho). Enviar durante a digitação faria o Streamlit redesenhar
  // a tela e o campo perderia o foco no meio da senha.
  function enviar() {
    if (raiz.dataset.enviado !== input.value) {
      raiz.dataset.enviado = input.value;
      setStateValue("value", input.value);
    }
  }
  input.oninput = desenhar;
  input.onchange = enviar;
  input.onblur = enviar;

  olho.onclick = () => {
    const mostrando = input.type === "text";
    input.type = mostrando ? "password" : "text";
    olho.textContent = mostrando ? "Mostrar" : "Ocultar";
    olho.setAttribute("aria-pressed", String(!mostrando));
  };

  desenhar();
}
"""

def campo_senha_nova(rotulo, chave):
    """Campo de senha nova, com a barra de força. Devolve a senha digitada.

    chave: identificador único do campo na tela. Para limpar o campo
    (depois de trocar a senha, por exemplo), use outra chave.
    """
    return _desenhar(rotulo, chave, com_barra=True, preenchimento="new-password")


def campo_senha(rotulo, chave, nova=True):
    """Campo de senha simples, sem barra (repetir a senha, senha atual).

    nova=False avisa o navegador de que é a senha que a pessoa já tem,
    para o gerenciador de senhas oferecer a senha certa.
    """
    return _desenhar(rotulo, chave, com_barra=False,
                     preenchimento="new-password" if nova else "current-password")


def _desenhar(rotulo, chave, com_barra, preenchimento):
    # Registrar aqui dentro (a cada desenho da tela) é o uso normal do
    # Streamlit e mantém o componente disponível em qualquer sessão.
    componente = st.components.v2.component("campo_senha_nova", html=_HTML, css=_CSS, js=_JS)
    resultado = componente(
        key=chave,
        data={
            "rotulo": rotulo,
            "com_barra": com_barra,
            "preenchimento": preenchimento,
            "minimo": MIN_SENHA,
            "maximo": MAX_SENHA,
            "especiais": ESPECIAIS_DA_SENHA,
            "sequencia": TAMANHO_DA_SEQUENCIA,
        },
        on_value_change=lambda: None,   # necessário para "resultado.value" existir sempre
    )
    return resultado.value or ""
