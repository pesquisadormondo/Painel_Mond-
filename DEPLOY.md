# Colocar o painel no ar para a equipe testar

Dois caminhos. Para **dados reais**, use o **Caminho A**. O **Caminho B** (nuvem) é só para a **demonstração com dados fictícios**.

---

## Caminho A — dados reais, rodando no seu Mac (Cloudflare Tunnel)

**Como funciona:** o app roda no seu Mac, e o túnel da Cloudflare cria um link `https://….trycloudflare.com` que leva até ele. A planilha **continua só no seu computador**. Quem abrir o link vê o **nível Público** (números agregados; nomes, CPF, endereços e mapa não saem).

**Camadas de proteção:**
1. **Senha da equipe no app:** nada é carregado nem mostrado antes dela. Depois de 8 senhas erradas (somando todas as pessoas) o acesso é bloqueado por alguns minutos.
2. **Modo de desenvolvimento bloqueado:** se `dev.enabled` estiver ligado e o app detectar acesso por link externo, ele se bloqueia.
3. **Túnel aberto só durante as sessões de teste:** ao fechar o terminal, o link deixa de existir.

> **Não use `--allowed-mail`.** A lista de e-mails do túnel usa o Cloudflare Access, que **quebra o Streamlit** (testado no Opera GX e no Safari): os componentes carregados sob demanda recebem a tela de login e ficam em branco, com erros de CORS. Veja a seção de problemas abaixo.

### 1. Configurar o `.streamlit/secrets.toml`

```toml
[dev]
enabled = false                  # OBRIGATÓRIO desligado enquanto o link estiver no ar

[access]
team_password = "troque-por-uma-senha-forte"

[privacy]
k_min = 1                        # painel sem omissão nas páginas em geral
k_sensivel = 5                   # Saúde e Doações e cestas continuam protegidas
k_download = 5
pseudo_secret = "texto-longo-e-aleatorio"
```

Para testar os níveis Pesquisador e Administrador **só no seu computador** (sem túnel), use:
`MONDO_DEV=1 streamlit run app.py`

### 2. Instalar o cloudflared

```bash
brew install cloudflared      # se já tiver: brew upgrade cloudflared
```

### 3. Subir o app (Terminal 1)

```bash
cd "/Volumes/SSD/Painel/mondo-app"
source ~/venvs/mondo/bin/activate
caffeinate -d -i streamlit run app.py --server.headless true
```

`caffeinate` impede o Mac de dormir enquanto o app roda. Deixe o Mac na tomada.

### 4. Abrir o túnel (Terminal 2)

```bash
cloudflared tunnel --url http://localhost:8501
```

- O terminal imprime o link (`https://palavras-aleatorias.trycloudflare.com`). Envie **o link** e **a senha** por canais diferentes.
- Use uma senha longa e aleatória (16 caracteres ou mais). Para gerar uma: `openssl rand -base64 18`.
- O link muda a cada vez que o túnel é iniciado. Qualquer pessoa com o link chega à tela de senha, e só ela.
- Se quiser que só dispositivos convidados cheguem ao app, use a alternativa privada (Tailscale), descrita abaixo.

### 5. Receber os feedbacks

Na barra lateral há **💬 Enviar feedback** (tipo, mensagem e nome opcional). As mensagens ficam em `logs/feedback.csv` no seu Mac. Para ler pelo painel, rode localmente `MONDO_DEV=1 streamlit run app.py`, escolha Administrador e abra **Feedback da equipe**. Peça para não escreverem nomes de pessoas atendidas nem CPF.

### 6. Encerrar

**Ctrl + C** nos dois terminais. O link para de funcionar na hora.

### Se o link abrir, mas os números e tabelas não aparecem

Sintoma: caixas vermelhas com `TypeError: Failed to fetch dynamically imported module: …/static/js/Metric….js` (ou `DataFrame`, `Radio`…), ou `Cross-origin script load denied by Cross-Origin Resource Sharing policy`, enquanto `http://localhost:8501` funciona. No console aparece `blocked by CORS policy` com um endereço `cloudflareaccess.com/cdn-cgi/access/login`.

**Causa:** o túnel foi aberto com `--allowed-mail`. Essa proteção usa o Cloudflare Access, e as requisições dos arquivos que o Streamlit carrega sob demanda são redirecionadas para a página de login, o que o navegador bloqueia. Acontece em mais de um navegador (Opera GX e Safari). O app e os dados estão corretos.

**Solução:** pare o túnel (Ctrl + C) e abra um novo **sem** `--allowed-mail`:
```bash
cloudflared tunnel --url http://localhost:8501
```
Como a lista de e-mails deixa de valer, a proteção passa a ser a senha da equipe: defina uma senha forte em `[access] team_password` (reinicie o app depois de editar o `secrets.toml`), mantenha o túnel aberto só durante as sessões e compartilhe o link apenas com a equipe.

**Alternativa mais segura:** Tailscale, uma rede privada em que só os dispositivos convidados enxergam o seu Mac, sem link público. Cada pessoa precisa instalar o Tailscale. Peça e eu escrevo o passo a passo.

### Limitações e cuidados

- O Mac precisa ficar ligado, com internet. Fechar a tampa ou ficar sem rede derruba o painel.
- O link muda a cada vez que o túnel é iniciado.
- O Quick Tunnel é **para testes**: a Cloudflare não garante disponibilidade e limita a 200 requisições simultâneas.
- O tráfego passa pelos servidores da Cloudflare (números agregados, mas ainda assim um terceiro).
- Se o link der erro 502, troque `localhost` por `127.0.0.1` no comando do túnel.
- Se existir `~/.cloudflared/config.yaml`, renomeie-o durante o teste (Quick Tunnels não funcionam com ele).
- A senha da equipe é uma camada simples (compartilhada). Quem sai do projeto precisa de nova senha.

---

## Caminho B — Streamlit Community Cloud (somente dados fictícios)

Na nuvem gratuita a planilha precisaria estar **dentro do repositório do GitHub**. Isso colocaria nomes, CPFs e dados de saúde de crianças e adolescentes em um serviço de terceiros, e por isso **não é recomendado com os dados reais**. Use a planilha fictícia `demo/dados_demo.xlsx` (gerada por `python scripts/gerar_demo.py`).

1. Crie um repositório no GitHub e envie o projeto:
   ```bash
   cd "/Volumes/SSD/Painel/mondo-app"
   git init && git add . && git status     # confira: NÃO pode aparecer data/*.xlsx nem secrets.toml
   git commit -m "Painel Mondó (demonstração)"
   git branch -M main
   git remote add origin https://github.com/SEU-USUARIO/mondo-app.git
   git push -u origin main
   ```
2. Em [share.streamlit.io](https://share.streamlit.io), **Create app** → escolha o repositório, a branch `main` e o arquivo `app.py`.
3. Em **Advanced settings**, escolha Python 3.12 e cole em **Secrets**:
   ```toml
   [data]
   xlsx_path = "demo/dados_demo.xlsx"

   [dev]
   enabled = true          # aceitável aqui: os dados são fictícios

   [privacy]
   pseudo_secret = "qualquer-texto-longo"
   ```
4. Para restringir quem vê: no app, **Share** → convide por e-mail. De acordo com a documentação, cada usuário tem direito a **1 app privado** (que exige repositório privado).
5. O `logs/` da nuvem é temporário: feedbacks e auditoria se perdem ao reiniciar o app.

---

## Checklist antes de compartilhar o link

- [ ] `[dev] enabled = false` e nenhuma variável `MONDO_DEV` no terminal do túnel.
- [ ] `team_password` definida.
- [ ] Senha longa e aleatória (16+ caracteres) definida, e túnel aberto só durante a sessão (sem `--allowed-mail`).
- [ ] Você abriu o link em uma janela anônima e conferiu: só aparecem totais, sem nomes, CPF ou mapa.
- [ ] A equipe sabe que são **dados reais em fase de teste** e que não devem copiar nem divulgar prints fora do projeto.

## Para a versão oficial

Quando houver mais gente de fora do projeto: dados no Supabase, login Google com listas de acesso, hospedagem definida pelo Instituto (pergunta N14) e validação de LGPD (perguntas N7 e N9). Veja o README, seção "Próximos passos".

---

## Atualizar o GitHub com uma nova versão

**Primeiro, uma regra de ouro:** o que vai para o GitHub **nunca** pode incluir a planilha real, o `secrets.toml` nem a pasta `logs/`. O `.gitignore` do projeto já os exclui; confirme sempre com `git status` antes de enviar.

### Se você já tem o repositório no seu Mac

1. Baixe o `mondo-app.zip` novo e descompacte em uma pasta temporária (ex.: `~/Downloads/novo`).
2. Copie os arquivos novos por cima do projeto **sem apagar** o que é seu (`.git`, planilha, `secrets.toml`, logs):
   ```bash
   rsync -av --exclude='.git' --exclude='data/*.xlsx' --exclude='.streamlit/secrets.toml' --exclude='logs/' \
     ~/Downloads/novo/mondo-app/ "/Volumes/SSD/Painel/mondo-app/"
   ```
3. Confira o que mudou e rode os testes:
   ```bash
   cd "/Volumes/SSD/Painel/mondo-app"
   source ~/venvs/mondo/bin/activate
   git status
   pytest tests -q
   ```
4. **Verifique que nada sensível entrou:**
   ```bash
   git status --short | grep -Ei "xlsx|secrets|logs/|\._" || echo "nada sensível na lista"
   git ls-files | grep -Ei "\.xlsx$"       # deve listar apenas demo/dados_demo.xlsx
   ```
5. Envie:
   ```bash
   git add .
   git commit -m "Tela Dados (explorar e baixar), feedback e senha da equipe"
   git push
   ```
6. No Streamlit Community Cloud, o app costuma ser atualizado sozinho depois do `push` (pode levar alguns minutos). Se não atualizar, abra o app e use **Reboot app**.

### Se ainda não criou o repositório

```bash
cd "/Volumes/SSD/Painel/mondo-app"
git init
git add . && git status          # confira: sem planilha real, secrets.toml ou logs
git commit -m "Painel Mondó"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/mondo-app.git     # crie antes o repositório vazio no GitHub
git push -u origin main
```

Na primeira vez, o GitHub pede autenticação. O jeito mais simples no Mac: `brew install gh` e depois `gh auth login`.

### Se a planilha real chegou a ser enviada ao GitHub

Apagar o arquivo em um commit novo **não basta**: ele continua no histórico. Torne o repositório privado imediatamente e me avise: o caminho seguro é recriar o repositório limpo (ou limpar o histórico com `git filter-repo`) e tratar os dados como expostos.

### Problemas comuns

| Sintoma | Solução |
|---|---|
| `fatal: not a git repository` | Você não está na pasta do projeto: use `cd` até ela |
| `git push` pede senha e falha | Use `gh auth login` (ou um token de acesso pessoal no lugar da senha) |
| Aparecem arquivos `._algo` no `git status` | São do macOS em disco exFAT. O `.gitignore` já os ignora; se aparecerem, rode `git rm --cached ._*` |
| `rejected … fetch first` | Alguém alterou o repositório: rode `git pull --rebase` e depois `git push` |
