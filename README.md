# Radar Tarifaço & Madeira — MVP

Painel web estático para monitorar notícias públicas sobre tarifas comerciais, comércio exterior e possíveis impactos na indústria brasileira da madeira.

## O que já está pronto

- Painel responsivo para computador e celular.
- Busca e filtros por categoria, prioridade e período.
- Destaque de alertas críticos.
- Classificação automática de notícias por relevância.
- Coleta por Google News RSS, RSS do MDIC e páginas da ABIMCI, USTR e MDIC.
- Atualização diária por GitHub Actions.
- Publicação gratuita como site estático pelo GitHub Pages.
- Configuração de termos e fontes sem alterar o código Python.

## Arquitetura

```text
index.html                         Painel principal
assets/style.css                   Aparência do painel
assets/app.js                      Filtros, indicadores e listagem
data/noticias.json                 Base consumida pelo painel
config/monitoramento.json          Termos e fontes monitorados
scripts/atualizar_noticias.py      Coleta, classificação e deduplicação
.github/workflows/atualizar.yml    Execução diária automática
requirements.txt                   Dependências Python
```

## Testar no computador

Não abra o `index.html` diretamente com duplo clique, pois alguns navegadores bloqueiam a leitura do JSON local. Abra um terminal dentro da pasta e execute:

```bash
python -m http.server 8000
```

Depois acesse:

```text
http://localhost:8000
```

Para testar a coleta manualmente:

```bash
pip install -r requirements.txt
python scripts/atualizar_noticias.py
```

A coleta precisa de acesso à internet.

## Publicar pelo GitHub

### 1. Criar o repositório

1. Entre no GitHub.
2. Crie um novo repositório, por exemplo `radar-tarifaco-madeira`.
3. Para o MVP público, a opção mais simples é um repositório público.
4. Faça upload de todos os arquivos e pastas deste projeto, inclusive `.github`.

### 2. Ativar a automação

1. Abra a aba **Actions** do repositório.
2. Autorize os workflows, caso o GitHub solicite.
3. Abra **Atualizar radar de noticias**.
4. Clique em **Run workflow** para executar o primeiro teste.
5. Verifique se o arquivo `data/noticias.json` foi atualizado.

A execução programada ocorre diariamente às 10:00 UTC, aproximadamente 07:00 no horário de São Paulo.

### 3. Ativar o site

1. Abra **Settings > Pages**.
2. Em **Build and deployment**, selecione publicação a partir de uma branch.
3. Selecione a branch `main` e a pasta `/ (root)`.
4. Salve.
5. O GitHub mostrará o endereço público do painel.

## Personalizar termos e fontes

Edite `config/monitoramento.json`.

Você pode acrescentar:

- consultas de notícias;
- páginas públicas monitoradas;
- termos relacionados a madeira;
- termos tarifários;
- nomes de produtos;
- NCMs ou códigos HTS relevantes;
- empresas e associações setoriais.

Exemplo de nova consulta:

```json
"molduras de pinus exportação Estados Unidos tarifa"
```

## Como a prioridade é calculada

O atualizador atribui peso maior para publicações que combinam:

- termos tarifários, como Seção 301, Seção 232, tarifa ou ordem executiva;
- referências ao Brasil e aos Estados Unidos;
- produtos e expressões da indústria madeireira;
- fontes oficiais;
- indicações de entrada em vigor ou ação final.

A classificação é um apoio de triagem, não uma conclusão jurídica ou comercial.

## Limitações deste MVP

- O Google News RSS é usado como mecanismo gratuito de descoberta e pode mudar ou limitar resultados.
- Alguns sites podem alterar seu HTML e exigir ajuste no coletor.
- O painel não lê matérias protegidas por assinatura.
- Os resumos vêm dos feeds ou do trecho público disponível; eles não substituem a leitura da fonte.
- Ainda não há integração automática com dados detalhados do Comex Stat por NCM.
- O painel não deve receber informações confidenciais ou internas da BrasPine enquanto estiver publicado em endereço público.

## Próximas evoluções recomendadas

1. Cadastro dos NCMs e produtos mais relevantes para a BrasPine.
2. Série mensal de exportações para os Estados Unidos.
3. Comparação com Chile, China, Canadá e outros concorrentes.
4. Alertas por e-mail ou Microsoft Teams somente para eventos críticos.
5. Resumo executivo diário com validação das fontes oficiais.
6. Hospedagem em ambiente corporativo ou intranet para incluir informações internas.

## Segurança e uso corporativo

Este MVP trabalha apenas com fontes públicas. Antes de incluir dados internos, valide a hospedagem e o controle de acesso com a área de TI e com as políticas da BrasPine.
