# FIAP 10DTSR - Projeto Integrado - Validação de Identidade com Cloud & Cognitive Services

Este projeto é uma solução desenvolvida para o case da Quantum Finance do MBA em Data Science & Artificial Intelligence. O objetivo é criar um fluxo de validação de identidade automatizado para novos clientes, utilizando múltiplos serviços de IA em nuvem para prevenir fraudes.

## Sobre o Projeto

A fintech Quantum Finance necessita de um processo de onboarding seguro para validar a identidade de seus clientes. Este projeto implementa o fluxo de validação que analisa e compara três documentos: a CNH (Carteira Nacional de Habilitação), um comprovante de residência e uma selfie do usuário.

O processo é considerado aprovado apenas se todas as validações forem bem-sucedidas.

## Funcionalidades e Serviços Utilizados

O projeto integra diferentes serviços de nuvem para realizar a análise completa dos documentos:

1.  **Análise da CNH - AWS Textract**:
    * Utiliza o serviço de Reconhecimento Óptico de Caracteres (OCR) da AWS para extrair todo o texto presente na imagem da CNH.
    * Uma expressão regular (Regex) é aplicada sobre o texto extraído para isolar o **Nome Completo** e o **CPF**.

2.  **Análise do Comprovante de Residência - OpenAI GPT-4o**:
    * A imagem do comprovante é enviada para a API do GPT-4o.
    * O modelo é instruído a analisar a imagem e retornar um JSON estruturado contendo o **Nome do Titular** e o **Endereço Completo**.

3.  **Comparação Facial - AWS Rekognition**:
    * O serviço de reconhecimento facial da AWS é utilizado para comparar a foto presente na CNH com a selfie enviada pelo usuário.
    * O serviço retorna um percentual de similaridade entre as faces.

4.  **Integração e Validação - Python**:
    * Um script em Python orquestra todas as chamadas de API.
    * Valida se o nome extraído da CNH é compatível com o nome do comprovante.
    * Valida se a similaridade facial está acima do limiar mínimo definido (95%).
    * Consolida todos os resultados e emite um parecer final de **Aprovado** ou **Não Aprovado**.

## Como Executar o Projeto

Este projeto foi desenvolvido em um ambiente Google Colab.

### 1. Pré-requisitos (Dependências)

Instale as bibliotecas Python necessárias, detalhadas dentro do próprio notebook.

### 2. Configuração das Chaves de API

Para a execução, são necessárias as chaves de acesso da AWS e da OpenAI. No Google Colab, configure-as como "Secrets" (no painel à esquerda, ícone de chave) com os seguintes nomes:

* `aws_access_id`: Seu ID de chave de acesso da AWS.
* `aws_access_key`: Sua chave de acesso secreta da AWS.
* `openai_api_key`: Sua chave de API da OpenAI.

### 3. Execução

1.  Abra o notebook `Projeto_final_cognitive_environments.ipynb` no Google Colab.
2.  Execute as células de código em sequência.
3.  Quando solicitado, faça o upload dos três arquivos: CNH, comprovante de residência e selfie.
4.  Ao final da execução, a última célula exibirá um resumo completo de todas as validações e o resultado final.

## Autores

* Lucian Cláudio da Silva | RM: 359082
* Matheus Vitor da Silva Souza | RM: 358585
* Maurício Mourão Jorge | RM: 359495
