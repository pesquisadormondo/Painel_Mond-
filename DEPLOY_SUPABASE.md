# Painel Mondó com Supabase + GitHub (ambiente de teste da equipe)

**Resumo da decisão:** os dados ficam no **Supabase** (PostgreSQL), o código vai para o **GitHub** e o app roda no **Streamlit Community Cloud**. A equipe testa **tudo no nível de administrador** em um **ambiente de TESTE**: os números são os reais da base, mas nomes, CPF, telefones, endereços e coordenadas são **fictícios**. Dados reais com identificação ficam para um segundo projeto, protegido por login Google.

---

## 1. Onde vai cada arquivo

Se você já tem a pasta do projeto, o jeito mais simples é descompactar o `mondo-app.zip` novo em `~/Downloads/novo` e copiar por cima, sem apagar o que é seu:

```bash
rsync -av --exclude='.git' --exclude='data/*.xlsx' --exclude='.streamlit/secrets.toml' --exclude='logs/' \
  ~/Downloads/novo/mondo-app/ "/Volumes/SSD/Painel/mondo-app/"
```

Resultado (✱ = novo ou alterado nesta versão):

```
mondo-app/
├── app.py                          ✱ substituir
├── requirements.txt                ✱ substituir (agora inclui sqlalchemy e psycopg2)
├── DEPLOY_SUPABASE.md              ✱ novo (este guia)
├── sql/
│   └── 01_schema.sql               ✱ novo   → cria as tabelas no Supabase
├── scripts/
│   └── carregar_supabase.py        ✱ novo   → envia a planilha para o Supabase
├── mondo/
│   ├── carga.py                    ✱ novo
│   ├── db.py                       ✱ novo
│   ├── mascaramento.py             ✱ novo   → troca identificações por dados fictícios
│   ├── auth.py                     ✱ substituir (nível da equipe + trava)
│   ├── config.py                   ✱ substituir
│   ├── loader.py                   ✱ substituir (lê do Supabase)
│   ├── audit.py                    ✱ substituir (log no banco)
│   └── feedback.py                 ✱ substituir (feedback no banco)
├── tests/test_postgres.py          ✱ novo
├── .streamlit/
│   ├── secrets.toml                ← VOCÊ cria/edita; NUNCA vai para o Git
│   └── secrets.teste.example.toml  ✱ novo   → modelo pronto para o ambiente de teste
└── data/                           ← sua planilha .xlsx (não vai para o Git)
```

Os arquivos que você edita à mão são só dois: `.streamlit/secrets.toml` (a partir do modelo) e o comando de carga.

---

## 2. Criar o projeto de TESTE no Supabase

1. Em [supabase.com](https://supabase.com), crie uma conta e um **novo projeto**. Nome sugerido: `mondo-teste`.
2. Escolha uma **região** (se houver, *South America (São Paulo)*) e anote a **senha do banco** (guarde em um gerenciador de senhas).
3. Com o projeto pronto, clique em **Connect** (no topo do painel) e escolha **Session pooler**. O endereço tem este formato:
   ```
   postgresql://postgres.SEU-REF:SUA-SENHA@aws-1-REGIAO.pooler.supabase.com:5432/postgres
   ```
   Use o **Session pooler**: a conexão direta (`db.<ref>.supabase.co`) usa IPv6 no plano gratuito e costuma falhar em redes IPv4 (inclusive no Streamlit Cloud).
4. Para o app, troque o início por `postgresql+psycopg2://` e acrescente `?sslmode=require` no final:
   ```
   postgresql+psycopg2://postgres.SEU-REF:SUA-SENHA@aws-1-REGIAO.pooler.supabase.com:5432/postgres?sslmode=require
   ```
   Se a senha tiver caracteres especiais (`@ : / # ? %`), codifique-os: `@` vira `%40`, `/` vira `%2F`, `#` vira `%23` e assim por diante.

---

## 3. Instalar e carregar os dados mascarados

No Terminal, dentro da pasta do projeto, com o ambiente virtual ativo:

```bash
cd "/Volumes/SSD/Painel/mondo-app"
source ~/venvs/mondo/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql+psycopg2://postgres.SEU-REF:SUA-SENHA@aws-1-REGIAO.pooler.supabase.com:5432/postgres?sslmode=require"
python scripts/carregar_supabase.py --criar-esquema --mascarar
```

O script mostra a planilha usada, o banco e o modo (`TESTE (dados mascarados)`), pede confirmação e imprime as linhas carregadas por tabela (cerca de 15 mil no total). No fim, deve aparecer: **"Carga marcada como TESTE (mascarada)"**.

Detalhes úteis:
- A planilha usada é o primeiro `.xlsx` da pasta `data/`. Para indicar outra: `--xlsx caminho/arquivo.xlsx`.
- Repetir o comando **substitui** os dados (use quando a planilha mudar). Com a mesma `--semente`, os nomes fictícios são sempre os mesmos.
- Se você já criou as tabelas e quer só recarregar, omita `--criar-esquema`.
- Se der erro de conexão, confira: usuário `postgres.<ref>`, host do **pooler**, `?sslmode=require` e a senha codificada.

### Conferir no Supabase (2 minutos)

1. Em **Table Editor**, escolha o schema `core` e abra `morador`: os nomes devem ser "Pessoa Fictícia 12.3" e os CPFs, fictícios.
2. Em **Project Settings → API → Exposed schemas**, confirme que **`core` e `acesso` NÃO estão na lista** (só `public`). Assim ninguém lê os dados pela API pública do Supabase. As tabelas já nascem com RLS ligado e sem acesso para `anon`/`authenticated`.

---

## 4. Rodar o app contra o Supabase (no seu Mac)

Copie o modelo e preencha:

```bash
cp .streamlit/secrets.teste.example.toml .streamlit/secrets.toml
open -e .streamlit/secrets.toml      # edite: URL do banco, senha da equipe, chave de pseudonimização
streamlit run app.py
```

Abra `http://localhost:8501`, digite a **senha da equipe**. Você deve ver:
- o aviso azul **🧪 Ambiente de TESTE** na barra lateral;
- **Nível de acesso: Administrador** e o menu **Administração** (Qualidade dos dados, Consulta ao cadastro, Acessos e auditoria, Feedback da equipe);
- na tela **Dados: explorar e baixar**, as tabelas identificadas (com nomes fictícios).

Gere uma senha forte com `openssl rand -base64 18` e a chave de pseudonimização com `openssl rand -hex 24`.

---

## 5. Subir para o GitHub e publicar

```bash
cd "/Volumes/SSD/Painel/mondo-app"
git status                                            # confira: sem secrets.toml, planilha real ou logs
git status --short | grep -Ei "xlsx|secrets|logs/|\._" || echo "nada sensível na lista"
git add .
git commit -m "Banco no Supabase, ambiente de teste mascarado e tela de dados"
git push
```

No [Streamlit Community Cloud](https://share.streamlit.io):
1. **Create app** → escolha o repositório, a branch `main` e o arquivo `app.py`.
2. Em **Advanced settings**: Python **3.12**; em **Secrets**, cole o **mesmo conteúdo** do seu `secrets.toml` (a senha do banco só existe aqui e no seu Mac).
3. Depois do deploy, abra o link, digite a senha da equipe e confira o banner de teste.

O feedback e o registro de acessos agora ficam **no banco** (tabelas `acesso.feedback` e `acesso.log_acesso`) e não se perdem quando o app reinicia. Para ler o feedback, entre como administrador e abra **Feedback da equipe**.

---

## 6. Roteiro de validação da equipe (nível administrador)

- [ ] **Visão geral, Atividades, Território, Perfil, Saúde, Doações, Avaliações, Indicadores:** os números fazem sentido para quem conhece a base?
- [ ] **Filtros** da barra lateral e **Dados: explorar e baixar** (agregadas, microdados, identificadas, pacote .zip): filtram e baixam certo? Abre no Excel?
- [ ] **Território → Mapa das famílias:** os pontos aparecem (as coordenadas foram deslocadas ~1 km de propósito)?
- [ ] **Qualidade dos dados:** a lista de problemas confere com o que vocês conhecem?
- [ ] **Consulta ao cadastro:** busca por nome fictício ou código (ex.: `12.3`).
- [ ] **Acessos e auditoria** e **Feedback da equipe:** registram o que foi feito?
- [ ] Use a caixa **💬 Enviar feedback** na barra lateral para anotar tudo que estranhar.

Como o corte "<5" está desligado (`k_min = k_sensivel = k_explorador = 1`), pequenos números aparecem. O `k_download = 5` continua protegendo os **arquivos de pesquisador** (ele generaliza combinações raras de comunidade, idade, sexo e zona; coloque `1` se quiser desligar também).

---

## 7. Para a apresentação

O ambiente de teste é feito **para a equipe do projeto**: acesso por senha compartilhada, nível de administrador e identificações fictícias. Se for mostrá-lo a outras pessoas (professores, colegas, outra equipe), tenha em mente:

- **Os números e os agrupamentos são os reais** (atividades, comunidades, saúde, participações). Só as identificações individuais são fictícias. Combinações como comunidade + faixa etária + atendimento de saúde continuam sendo informação sensível.
- Para uma plateia maior, o mais seguro é **apresentar a tela do seu computador** em vez de distribuir o link e a senha.
- Para uma demonstração sem nenhum dado real, use a planilha fictícia (`demo/dados_demo.xlsx`, gerada por `python scripts/gerar_demo.py`).
- **Não use o ambiente de teste para decidir nada sobre pessoas:** os nomes e CPFs não existem.

---

## 8. Depois: dados reais (outro projeto Supabase)

Quando o Instituto aprovar o uso dos dados reais (perguntas N7, N9 e N14 do questionário):

1. Crie **outro projeto Supabase** (`mondo-real`) em região adequada à LGPD e outra senha de banco. Não misture com o de teste.
2. Carregue **sem `--mascarar`** (o script exige digitar `CARREGAR DADOS REAIS`):
   ```bash
   export DATABASE_URL="…projeto-real…"
   python scripts/carregar_supabase.py --criar-esquema
   ```
3. Em um app separado (ou nos mesmos segredos, com a URL do projeto real), configure o **login Google** (`[auth]` e `[access]` com a lista de e-mails; veja o README). **Remova `team_level`.**
4. O app **recusa** `team_level = "admin"` quando a carga não está marcada como mascarada: administrador de dados reais só entra por login Google.

---

## 9. Segurança e limitações

- A senha do banco existe só nos segredos do Streamlit e no seu Mac. Nunca a coloque em arquivo versionado.
- O app conecta como dono do banco (servidor). Não use a chave `anon` do Supabase neste app.
- A senha da equipe é compartilhada: troque-a quando alguém sair do projeto. O app bloqueia o acesso por alguns minutos depois de 8 senhas erradas.
- Projetos gratuitos do Supabase podem ser **pausados** após um período sem uso; é preciso reativar no painel.
- O Streamlit Community Cloud e o Supabase são serviços de terceiros: para dados reais, valide região, contrato e base legal (LGPD) antes.
- Esta versão do app lê os dados do banco e os mantém em memória por até 6 horas (ou até usar **Recarregar dados** em *Qualidade dos dados*).
