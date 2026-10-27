# Configuração manual no painel do Supabase

Estas configurações ficam no site do Supabase e não podem ser feitas pelo
código. Faça uma vez por projeto. Os nomes dos menus mudam de tempos em
tempos; se algum estiver diferente, procure pelo nome mais parecido.

Painel: https://supabase.com/dashboard > clique no seu projeto.

## 1. Banco de dados (SQL)

Em **SQL Editor > New query**, cole o conteúdo do arquivo e clique em **Run**.
O resultado esperado é `Success. No rows returned`.

| Situação | Arquivos, nesta ordem |
|---|---|
| Projeto novo, vazio | `sql/schema.sql` |
| Projeto que já tinha as tabelas | os arquivos `sql/migracao_*.sql` que ainda não rodou, em ordem numérica |

Todas as migrações podem ser rodadas mais de uma vez sem estragar nada.
Quando falta alguma, o app mostra um aviso vermelho logo depois do login.

A `sql/migracao_006.sql` é diferente das outras: é **opcional** e o app não
avisa se ela faltar. Ela tira permissões que o aplicativo não usa (uma
segunda tranca, além das regras de acesso por conta). Recomendada antes do
piloto.

## 2. Servidor de e-mail próprio (SMTP): faça ANTES do passo 3

O Supabase só libera a edição dos modelos de e-mail depois que um servidor
de e-mail próprio está configurado. Além disso, o serviço embutido dele:

- só entrega mensagens para **membros da equipe do projeto**;
- envia no máximo **2 e-mails por hora**.

Ou seja, sem este passo nenhum técnico de fora consegue confirmar a conta
nem redefinir a senha.

### Onde configurar

**Authentication > Emails**, na parte **SMTP Settings**: ligue
**Enable custom SMTP** e preencha os campos.

### Opção rápida para o piloto: Gmail com senha de aplicativo

Serve para poucos usuários. Use uma conta Gmail **criada só para o projeto**,
nunca a pessoal. Não consta na documentação do Supabase e não foi testada
neste projeto.

1. Crie a conta Gmail do projeto.
2. Nela, ative a verificação em duas etapas: `myaccount.google.com/security`.
3. Em `myaccount.google.com/apppasswords`, crie uma senha de aplicativo com
   o nome "Supabase". O Google mostra a senha de 16 letras uma única vez.
4. No Supabase, preencha:

| Campo | Valor |
|---|---|
| Sender email address | o Gmail do projeto |
| Sender name | o nome do produto (é o que o técnico vê) |
| Host | `smtp.gmail.com` |
| Port number | `465` |
| Minimum interval per user | `60` |
| Username | o Gmail do projeto, completo |
| Password | a senha de aplicativo de 16 letras |

5. Clique em **Save**.

Cuidados: o Google limita o volume diário e os e-mails podem cair no spam.
Avise os técnicos do piloto para olharem a caixa de spam.

### Opção definitiva: provedor de e-mail com domínio próprio

Antes de abrir para o público, troque por um serviço feito para isso. O
Supabase cita Resend, Brevo, AWS SES, Postmark, SendGrid e ZeptoMail. Em
geral eles exigem um domínio próprio verificado para enviar a qualquer
pessoa. Confira os limites do plano gratuito no site de cada um.

No piloto, o e-mail de confirmação enviado pelo Gmail **caiu na caixa de
spam**. É esse o problema que esta troca resolve.

#### Passo a passo com o Resend e o domínio mestrali.com.br

Os nomes das telas e os valores exatos aparecem no painel do Resend; use os
de lá. O roteiro é este:

1. Crie uma conta em https://resend.com.
2. Em **Domains**, clique em **Add Domain** e informe `mestrali.com.br`.
   Se o painel perguntar a região, São Paulo é a mais próxima.
3. O Resend mostra de três a quatro registros DNS (um `MX` e textos `TXT`
   de SPF e DKIM, em nomes como `send` e `resend._domainkey`). Copie cada um
   para a zona DNS do domínio, no painel do Registro.br.
4. Volte ao Resend e clique em **Verify**. Pode levar de minutos a horas.
5. Em **API Keys**, crie uma chave com permissão de envio. Ela aparece uma
   vez só: copie na hora e não cole em conversas nem em arquivos do projeto.
6. No Supabase, em **Authentication > Emails > SMTP Settings**, troque os
   campos:

   | Campo | Valor |
   |---|---|
   | Sender email | `nao-responda@mestrali.com.br` |
   | Sender name | `Mestrali` |
   | Host | `smtp.resend.com` |
   | Port | `465` |
   | Username | `resend` |
   | Password | a chave criada no passo 5 |

7. Salve e teste criando uma conta com um e-mail de fora da equipe.

Esses registros não interferem nos da página de apresentação: são nomes
diferentes dentro do mesmo domínio.

### Depois de configurar

- Em **Authentication > Rate Limits**, o limite de e-mails passa a 30 por
  hora e pode ser ajustado.
- Acrescente o provedor escolhido em `PROVEDOR_DE_EMAIL`, no arquivo
  `core/privacidade.py`: ele passa a receber o e-mail dos técnicos e precisa
  constar na política de privacidade.

## 3. E-mail de "Esqueci minha senha" (obrigatório para a função existir)

O app pede um **código numérico**. O modelo padrão do Supabase manda só um
link, que o app não consegue abrir. Troque o modelo.

Se o editor aparecer bloqueado (sem conseguir clicar em **Source**), é porque
o passo 2 ainda não foi feito.

1. Menu da esquerda: **Authentication**.
2. Em **Notifications** (ou **Configuration**), clique em **Emails**
   (em versões antigas do painel: **Email Templates**).
3. Abra a aba **Reset Password**.
4. Em **Subject heading**, coloque:

   ```
   Seu código para criar uma senha nova
   ```

5. Em **Message body**, apague tudo e cole:

   ```html
   <h2>Criar uma senha nova</h2>
   <p>Use este código no aplicativo, em "Esqueci minha senha":</p>
   <p style="font-size: 28px; font-weight: bold; letter-spacing: 4px;">{{ .Token }}</p>
   <p>O código vale por tempo limitado. Se você não pediu a troca de senha,
   ignore este e-mail: sua senha continua a mesma.</p>
   ```

6. Clique em **Save changes**.

O trecho `{{ .Token }}` é o que o Supabase troca pelo código. Não coloque
`{{ .ConfirmationURL }}` nesse modelo: é o link que o app não usa.

### Conferir o tamanho e a validade do código

Em **Authentication > Sign In / Providers > Email**:

- **Email OTP Length**: de 6 a 10 dígitos. O app aceita qualquer valor nessa faixa.
- **Email OTP Expiration**: 3600 segundos (1 hora) ou menos.

### Como o app usa o código (para referência)

1. `reset_password_for_email(email)`: pede o envio do e-mail.
2. `verify_otp({"email", "token", "type": "recovery"})`: confere o código e
   abre uma sessão.
3. `update_user({"password": nova})`: grava a senha nova.

O código está em `core/auth.py`, nas funções `pedir_codigo_de_senha` e
`redefinir_senha`.

## 3b. E-mail de confirmação de cadastro em português (recomendado)

Quem cria uma conta recebe um e-mail com um link de confirmação. O modelo
padrão do Supabase está em inglês. Para trocar:

1. **Authentication > Emails**, aba **Confirm signup**.
2. Em **Subject heading**, coloque:

   ```
   Confirme o seu e-mail na Mestrali
   ```

3. Em **Message body**, apague tudo e cole:

   ```html
   <h2>Confirme o seu e-mail</h2>
   <p>Falta um passo para começar a usar a Mestrali. Toque no link abaixo
   para confirmar que este e-mail é seu:</p>
   <p><a href="{{ .ConfirmationURL }}">Confirmar meu e-mail</a></p>
   <p>Depois de confirmar, volte ao aplicativo e entre com o seu e-mail e a
   sua senha.</p>
   <p>Se você não criou uma conta, ignore este e-mail.</p>
   ```

4. Clique em **Save changes**.

Aqui o trecho certo é `{{ .ConfirmationURL }}` (o link). É o contrário do
modelo de senha, que usa o código `{{ .Token }}`.

O link leva ao endereço cadastrado em **URL Configuration > Site URL**. O
aplicativo não entra sozinho por esse link: a pessoa confirma e depois entra
pela aba Entrar.

## 4. Política de senha e de cadastro

O aplicativo já recusa senhas fracas antes de enviá-las. Esta configuração
faz o **servidor** do Supabase recusar também, para o caso de alguém tentar
criar ou trocar a senha sem passar pelo aplicativo.

### Onde configurar

1. Menu da esquerda: **Authentication**.
2. Em **Configuration**, clique em **Sign In / Providers**
   (em versões antigas do painel: **Providers**, ou **Policies**).
3. Abra a seção **Email**.
4. Ajuste os campos da tabela abaixo e clique em **Save**.

| Opção no painel | Valor | Por quê |
|---|---|---|
| **Minimum password length** | `8` | Igual ao aplicativo |
| **Password Requirements** | **Lowercase, uppercase letters, digits and symbols** | A opção mais forte disponível |
| **Confirm email** | ligado (em produção) | Só entra quem confirmou o e-mail |
| **Secure password change** | ligado, se disponível | Trocar a senha exige login recente |
| **Prevent use of leaked passwords** | ligado, se o seu plano permitir | Recusa senhas que já vazaram na internet (plano pago) |

### O que o Supabase não consegue repetir

Com a opção acima, aplicativo e servidor exigem as mesmas coisas:
8 caracteres, minúscula, maiúscula, número e símbolo. As diferenças que sobram:

| Regra | Aplicativo | Supabase |
|---|---|---|
| Caractere especial | só `@ # $ % &` | qualquer símbolo |
| Sem sequências (1234, abcd, 4321) | sim | **não tem essa opção** |

Nos dois casos o aplicativo é mais exigente que o servidor, então nenhuma
senha aceita pela barra de força será recusada pelo Supabase por causa
dessas regras. As sequências só são barradas pelo aplicativo.

Se o servidor recusar uma senha por outro motivo (por exemplo, senha que já
vazou na internet), o aplicativo mostra "A senha foi recusada pelo servidor
por ser fraca ou muito conhecida".

### Onde ficam as regras no aplicativo

Todas em `core/validacao.py`: `requisitos_da_senha`, `tem_sequencia` e
`validar_senha`. As telas (cadastro, "esqueci minha senha", trocar senha) e
as funções de `core/auth.py` usam essas mesmas funções; a senha é conferida
de novo imediatamente antes de cada envio ao Supabase.

Quem já tem conta continua entrando com a senha antiga: as regras valem para
senhas **novas** (cadastro, troca e redefinição).

## 5. Reforços recomendados antes do piloto

Nada aqui é obrigatório para o sistema funcionar. São ajustes do painel que
diminuem riscos que o código não consegue fechar sozinho.

| Onde | O que ajustar | Por quê |
|---|---|---|
| **Authentication > Sign In / Providers > Email** | **Email OTP Length**: `8` | O código de "Esqueci minha senha" fica 100 vezes mais difícil de adivinhar que com 6 dígitos. O app aceita de 6 a 10. |
| Mesmo lugar | **Email OTP Expiration**: `900` (15 minutos) | Um código que vale por pouco tempo dá menos chance a quem tenta adivinhar. |
| **Authentication > Sign In / Providers** | **Allow new users to sign up**: desligado, se o piloto for só por convite | Com o cadastro aberto, qualquer pessoa na internet cria conta, e cada cadastro gasta um e-mail do limite por hora. Com ele fechado, vocês criam as contas dos técnicos em **Authentication > Users > Add user**. O app mostra "Novos cadastros estão desativados" a quem tentar. |
| **Authentication > Attack Protection** (ou **Bot and Abuse Protection**) | Proteção por CAPTCHA | Só vale a pena ao abrir o cadastro ao público. Exige mexer no app; peça antes de ligar. |
| **Authentication > Rate Limits** | Conferir os limites de e-mails e de tentativas | Os limites do Supabase são a proteção de verdade contra quem tenta adivinhar senhas; o freio do app vale só para a sessão do navegador. |
| **Authentication > Sessions** | **Time-box user sessions** / **Inactivity timeout**, se o plano permitir | Hoje quem entra fica conectado até sair. Em aparelho compartilhado, um prazo máximo ajuda. |
| **Project Settings > API Keys** | Conferir que o app usa a chave **publishable** | A chave secreta ignora a separação de dados entre contas. O app se recusa a rodar com ela, mas ela nunca deve sair do painel. |

### O que o sistema já faz por conta própria

- Cada conta só alcança as próprias linhas (Row Level Security em todas as
  tabelas, conferido em `tests/test_sql.py` com tentativas de invasão).
- Um visitante sem login não lê nenhuma tabela.
- O link de confirmação de e-mail traz tokens de acesso no endereço; o app
  os tira da barra de endereço e do histórico do navegador.
- O logo guardado no banco só é aberto se for uma imagem pequena em formato
  comum (WebP, PNG ou JPEG).
- Senhas nunca são gravadas nem registradas pelo app.

### Limites conhecidos (decisões de vocês)

- **O cadastro revela se um e-mail já tem conta** ("Já existe uma conta com
  este e-mail"). Foi um pedido de usabilidade. O "Esqueci minha senha" não
  revela.
- **Não há limite de linhas por conta.** Alguém com conta e conhecimento
  técnico poderia gravar muitos registros pela API e encher o banco do plano
  gratuito. Com cadastro fechado no piloto, o risco fica restrito aos
  convidados.
- **Dois orçamentos gravados no mesmo instante podem receber o mesmo número.**
  O app evita o toque duplo; o banco não impede.

## 6. Usuários de teste (para os testes com o Supabase real)

Os testes de `tests/test_supabase_real.py` fazem login com duas contas e
conferem, entre outras coisas, que uma não enxerga os dados da outra.

1. **Authentication > Users > Add user > Create new user**.
2. Informe um e-mail (pode ser inventado, ex.: `teste1@exemplo.com`) e uma
   senha de 8 caracteres ou mais; marque **Auto Confirm User**.
3. Repita para a segunda conta (`teste2@exemplo.com`).
4. No arquivo `.env` do projeto, preencha `TESTE_EMAIL_1`, `TESTE_SENHA_1`,
   `TESTE_EMAIL_2` e `TESTE_SENHA_2` (os nomes já estão no `.env.example`).
5. Na linha seguinte, declare que as duas contas são só de teste:

   ```
   TESTE_CONTAS_DESCARTAVEIS=sim
   ```

   Sem essa linha os testes são pulados. É uma trava: eles entram nas contas,
   gravam e apagam dados, trocam a senha da conta 1 e encerram sessões.
   **Nunca coloque aqui a sua conta de uso**, nem a de um técnico.
6. Rode:

   ```bash
   pytest tests/test_supabase_real.py -v
   ```

Use contas só de teste: os testes gravam e apagam dados e trocam (e depois
devolvem) a senha da conta 1. O ideal é um projeto Supabase separado só para
testes; nesse caso aponte o `.env` para ele antes de rodar.
