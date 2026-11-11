# Instituto Mondó — painéis com 3 níveis de acesso

Aplicativo Streamlit com painéis interativos dos indicadores do Instituto Mondó.

| Nível | Quem | Como entra | O que vê |
|---|---|---|---|
| 1. Público | Qualquer pessoa | Sem login | Só números agregados; valores menores que *k* (padrão 5) são omitidos |
| 2. Pesquisador | Pesquisadores aprovados | Login Google + e-mail autorizado + aceite do termo | Painéis e **download de dados pseudonimizados** |
| 3. Administrador | Equipe gestora | Login Google + e-mail de administrador | Tudo, inclusive cadastro, mapa das casas, qualidade e auditoria |

**Tela “Dados: explorar e baixar”** (todos os níveis): escolha a tabela, aplique filtros (ano, dimensão, categoria, atividade, tipo, turma, sexo, faixa etária, comunidade, zona, período), defina como somar e baixe em CSV, CSV para Excel ou XLSX.
- **Público:** só tabelas agregadas (até 3 colunas de agrupamento); contagens menores que `k_explorador` aparecem como “<k”.
- **Pesquisador:** agregadas + microdados pseudonimizados (após aceitar o termo) + pacote .zip; os filtros demográficos usam os valores já generalizados pelo k-anonimato.
- **Administrador:** tudo, inclusive tabelas identificadas (CPF e telefone mascarados por padrão, confirmação obrigatória, tudo registrado).

Esta é a **fase 1**: o app lê a planilha `.xlsx` e aplica as regras no próprio Python. A fase 2 (documentação, seção 11)
move os dados para o Supabase e as regras de privacidade para o banco.

## 1. Rodar no seu computador

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # edite os valores
# coloque a planilha .xlsx na pasta data/
streamlit run app.py
```

Para testar sem configurar o Google, ligue `dev.enabled = true` no `secrets.toml`: aparece um seletor de nível na barra
lateral. **Nunca ligue isso em produção.**

## 2. Login com Google

1. No [Google Cloud Console](https://console.cloud.google.com/) crie um projeto e, em *APIs e serviços → Credenciais*, um
   **ID de cliente OAuth** do tipo *Aplicativo da Web*.
2. Em *URIs de redirecionamento autorizados*, informe `http://localhost:8501/oauth2callback` (e a URL real do app em produção,
   terminando em `/oauth2callback`).
3. Copie `client_id` e `client_secret` para a seção `[auth]` do `secrets.toml`; gere um `cookie_secret` aleatório longo.
4. Liste os e-mails em `[access]` (administradores e pesquisadores, com validade opcional).

O Google só **confirma quem a pessoa é**. Quem **pode** entrar em cada nível é decidido pelas listas do `secrets.toml`.
Conta Google não listada vê apenas o painel público.

## 3. O que o app faz com os dados

| Etapa | Regra |
|---|---|
| Carga | Converte tipos, completa zeros de CPF, trata `#N/A`/`n/r`, une variantes de texto, remove linhas duplicadas e gera o relatório de qualidade |
| Níveis 1 e 2 | Remove nomes, CPF, telefone, endereço, coordenadas e textos livres; ids viram códigos HMAC-SHA256; nascimento vira faixa etária |
| Nível 1 | Células de 1 a *k*−1 pessoas são omitidas (configurável, veja abaixo); se só uma célula for omitida, a menor restante também é (supressão complementar) |
| Download | k-anonimato (comunidade, faixa etária, sexo, zona) por supressão local, dicionário de dados e LEIA-ME no pacote |
| Auditoria | Login, geração e download de pacotes, consultas ao cadastro e revelação de CPF/telefone vão para `logs/log_acesso.csv` (sem o texto das buscas) |

### Ajustar o corte de privacidade (`[privacy]` no `secrets.toml`)

| Chave | Efeito | Padrão |
|---|---|---|
| `k_min` | Painel público, páginas em geral. `1` = não omite nada | 5 |
| `k_sensivel` | Painel público, páginas de **Saúde** e **Doações e cestas** | 5 |
| `k_download` | k-anonimato dos arquivos baixados por pesquisadores | 5 |
| `k_explorador` | Tabelas agregadas baixadas no nível **público** (tela Dados) | 5 |

As três são independentes: relaxar `k_min` não relaxa saúde nem download. Cuidado ao baixar o corte no painel público:
grupos pequenos podem permitir reconhecer pessoas, especialmente em saúde, entre crianças e adolescentes e em comunidades
pequenas (LGPD, arts. 5º II e 14). A decisão final deve ser do Instituto e do encarregado de dados (pergunta N9).

## 4. Limitações que você precisa conhecer

- **Mesmo processo para os 3 níveis.** Na fase 1 o servidor carrega os dados completos em memória, mesmo quando mostra o
  painel público. A separação por papéis do banco (fase 2) elimina isso.
- **Painel público interativo.** Filtros combinados podem permitir inferir valores por diferença entre consultas. A supressão
  por célula reduz o risco, mas não o elimina. Para garantias mais fortes, publique tabelas agregadas fixas.
- **Pseudonimizado ≠ anônimo.** Participações combinam atividade, datas e tipo (inclui saúde). O k-anonimato cobre só os
  campos demográficos do arquivo de moradores.
- **Não testado de ponta a ponta:** o login real com Google e o backend `postgres` (Supabase). Os demais fluxos têm testes
  automatizados com dados sintéticos (`pytest tests`) e foram executados com a planilha real em memória.
- **Hospedagem:** não coloque a planilha em repositório público. Em hospedagens com disco temporário (por exemplo, Streamlit
  Community Cloud) o `log_acesso.csv` se perde ao reiniciar e a planilha teria de estar no próprio repositório; prefira
  hospedar em servidor controlado ou esperar a fase 2 (dados no Supabase).
- **Significados em validação:** *ciclo*, *grupo*, *IPM*, `TURMA` e `COMUNIDADE` em atividades (ver questionário v0.2).
- **LGPD:** o `TERMO_DE_USO.md` é um rascunho; base legal, consentimento de menores e encarregado precisam de validação
  jurídica antes de abrir os níveis 2 e 1 ao uso real.

## 5. Banco no Supabase e ambiente de teste

Veja **`DEPLOY_SUPABASE.md`**: mapa de onde vai cada arquivo, criação do projeto Supabase, carga dos dados **mascarados**
(`python scripts/carregar_supabase.py --criar-esquema --mascarar`), execução do app contra o banco, publicação (GitHub +
Streamlit Cloud) e roteiro de validação. Modelo de segredos: `.streamlit/secrets.teste.example.toml`.

## 6. Colocar no ar com túnel (alternativa, dados locais)

Veja o **`DEPLOY.md`**: passo a passo para compartilhar o painel com dados reais a partir do seu Mac (Cloudflare Tunnel, com
lista de e-mails e senha da equipe) e para publicar uma demonstração com dados fictícios na nuvem
(`python scripts/gerar_demo.py` gera `demo/dados_demo.xlsx`). O painel tem uma caixa **💬 Enviar feedback** na barra lateral;
as mensagens ficam em `logs/feedback.csv` e aparecem em **Administração → Feedback da equipe**.

## 7. Atualizar os dados

Substitua o `.xlsx` em `data/` (o app detecta a mudança) ou use **Administração → Qualidade dos dados → Recarregar**.

## 8. Mapa dos arquivos

```
app.py                 entrada: acesso, filtros e navegação por nível
mondo/config.py        configurações (secrets, k, caminhos)
mondo/auth.py          níveis de acesso, listas de e-mails e validade
mondo/loader.py        planilha → modelo v0.2 da documentação + relatório de qualidade
mondo/privacy.py       faixas etárias, HMAC, supressão e k-anonimato
mondo/metrics.py       tabelas derivadas e indicadores (IND-01 a IND-15)
mondo/ui.py            contexto, filtros e gráficos reutilizáveis
mondo/pages.py         as telas (painéis, download, administração)
mondo/exportacao.py    pacote do pesquisador (CSVs + dicionário + LEIA-ME)
mondo/audit.py         registro de auditoria
mondo/feedback.py      caixa de feedback da equipe
mondo/carga.py         carga do modelo no PostgreSQL/Supabase
mondo/db.py            conexão com o banco (auditoria e feedback)
mondo/mascaramento.py  troca identificações por dados fictícios (ambiente de teste)
sql/01_schema.sql      tabelas, restrições e segurança (RLS) do Supabase
scripts/carregar_supabase.py  envia a planilha ao Supabase
DEPLOY_SUPABASE.md     guia: Supabase + GitHub + ambiente de teste
scripts/gerar_demo.py  planilha fictícia de demonstração
demo/dados_demo.xlsx   dados 100% fictícios
DEPLOY.md              como colocar no ar
tests/                 testes com planilha sintética (sem dados reais)
TERMO_DE_USO.md        termo exibido antes do download (rascunho)
```

## 9. Próximos passos

1. Script SQL do PostgreSQL (schemas `raw`, `core`, `pesquisa`, `publico`, `acesso`), papéis e visões com supressão.
2. Script de carga para o Supabase com o mesmo saneamento do `loader.py`.
3. Trocar `data.backend` para `postgres` e, depois, conectar cada nível ao seu papel de banco.
4. Incluir financiadores, projetos, rubricas e indicadores formais quando houver as fontes.
