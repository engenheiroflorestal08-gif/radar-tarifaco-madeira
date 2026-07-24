# Atualização V2 — Competitividade de molduras de pinus

Este pacote acrescenta ao painel:

- tabela por país;
- preço médio em US$/metro linear;
- conversão editável para US$/m³;
- tarifa legal atual/configurada;
- tarifa efetiva observada no mês;
- preço estimado após a tarifa;
- ranking de maior tarifa;
- ranking de maior preço médio;
- ranking de menor preço após tarifa;
- atualização automática com dados públicos do U.S. Census Bureau.

## Arquivos deste pacote

```text
index.html
assets/style.css
assets/competitividade.js
data/competitividade.json
scripts/atualizar_competitividade.py
.github/workflows/atualizar_competitividade.yml
```

## 1. Enviar os arquivos ao GitHub

1. Descompacte o arquivo ZIP.
2. Abra o repositório `radar-tarifaco-madeira` no GitHub.
3. Clique em **Add file > Upload files**.
4. Abra a pasta descompactada.
5. Selecione o conteúdo da pasta, inclusive `.github`.
6. Arraste os itens para o GitHub.
7. Em **Commit changes**, escreva:

```text
Adicionar comparativo de molduras por país
```

8. Clique no botão verde **Commit changes**.

O arquivo `index.html` e o arquivo `assets/style.css` existentes serão substituídos pelas versões novas.

## 2. Criar a chave gratuita do U.S. Census

A API de comércio exterior do U.S. Census exige uma chave.

1. Solicite uma chave na página de desenvolvedores do U.S. Census.
2. A chave será enviada ao seu e-mail.
3. Não coloque a chave dentro do código ou em arquivo público.

## 3. Salvar a chave com segurança no GitHub

1. No repositório, abra **Settings**.
2. No menu esquerdo, abra **Secrets and variables > Actions**.
3. Clique em **New repository secret**.
4. Em **Name**, digite exatamente:

```text
CENSUS_API_KEY
```

5. Em **Secret**, cole a chave recebida.
6. Clique em **Add secret**.

## 4. Executar a primeira atualização

1. Abra a aba **Actions**.
2. Clique em **Atualizar competitividade de molduras**.
3. Clique em **Run workflow**.
4. Confirme a branch `main`.
5. Clique novamente em **Run workflow**.
6. Aguarde a marca verde.
7. Espere de 1 a 3 minutos e atualize o site com `Ctrl + F5`.

## Como os valores são calculados

```text
Preço US$/m linear = valor de importação / quantidade em metros

Tarifa efetiva = direito aduaneiro calculado / valor de importação

US$/m³ = US$/m linear / (espessura em m × largura em m)

Preço após tarifa = US$/m³ × (1 + tarifa aplicada)
```

A conversão inicial usa 18 mm × 70 mm, mas as dimensões podem ser alteradas diretamente no painel.

## Observação sobre a tarifa do Brasil

O arquivo inicial registra 25% como tarifa legal adicional da Seção 301, vigente desde 22 de julho de 2026. O painel também apresenta a tarifa efetiva observada nos dados mensais quando ela estiver disponível.

Antes de decisões comerciais ou aduaneiras, valide o HTS utilizado, os capítulos 99 aplicáveis e eventuais exceções com a área responsável.
