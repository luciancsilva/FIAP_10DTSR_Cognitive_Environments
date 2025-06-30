import streamlit as st
import boto3
from PIL import Image
import openai
import base64
import io
import os
import unicodedata
import json
import re
from pdf2image import convert_from_bytes
from pathlib import Path

# --- Configuração da Página e Estado da Sessão ---
st.set_page_config(page_title="Validador de Identidade", page_icon="🔐", layout="wide")

# Inicializa o estado da sessão para armazenar os dados entre as etapas
if 'dados_cnh' not in st.session_state:
    st.session_state.dados_cnh = None
if 'dados_comprovante' not in st.session_state:
    st.session_state.dados_comprovante = None
if 'dados_faciais' not in st.session_state:
    st.session_state.dados_faciais = None
if 'processo_iniciado' not in st.session_state:
    st.session_state.processo_iniciado = False


# --- Interface com Abas ---
tab_config, tab_analise, tab_resultado = st.tabs(["1. Configuração e Upload", "2. Análise dos Documentos", "3. Resultado Final"])

with tab_config:
    st.header("Configuração e Upload de Documentos")
    st.write("Insira suas credenciais de API e faça o upload dos arquivos necessários.")

    # --- Barra Lateral: Parâmetros e Credenciais ---
    with st.sidebar:
        st.header("Parâmetros de Confiança")
        cnh_confianca_minima = st.slider("Confiança Mínima (CNH %)", 0.0, 100.0, 70.0, key="conf_cnh")
        comprovante_similaridade_minima = st.slider("Similaridade Mínima (Nome %)", 0.0, 100.0, 70.0, key="conf_nome")
        selfie_similaridade_minima = st.slider("Similaridade Mínima (Selfie %)", 0.0, 100.0, 95.0, key="conf_selfie")

        st.header("Credenciais de API")
        st.info("As chaves podem ser inseridas aqui ou configuradas via `st.secrets` para implantação.")
        ACCESS_ID = st.secrets.get("aws_access_id", "") or st.text_input("AWS Access Key ID", type="password")
        ACCESS_KEY = st.secrets.get("aws_access_key", "") or st.text_input("AWS Secret Access Key", type="password")
        openai_api_key = st.secrets.get("openai_api_key", "") or st.text_input("OpenAI API Key", type="password")
        region = "us-east-1"
        openai_model = "gpt-4o"

    # --- Upload de Documentos ---
    col1, col2, col3 = st.columns(3)
    with col1:
        cnh_file = st.file_uploader("CNH (Imagem ou PDF)", type=["pdf", "png", "jpg", "jpeg"])
    with col2:
        comprovante_file = st.file_uploader("Comprovante de Residência", type=["pdf", "png", "jpg", "jpeg"])
    with col3:
        selfie_file = st.file_uploader("Selfie", type=["png", "jpg", "jpeg"])

# --- Funções de Processamento ---
# (As funções permanecem as mesmas da versão anterior, mas serão chamadas de forma mais organizada)
def processar_arquivo_cnh(uploaded_file):
    if not uploaded_file: return None
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext == ".pdf":
        pil_img = convert_from_bytes(uploaded_file.getvalue(), first_page=1, last_page=1, dpi=300, fmt="png")[0]
    else:
        pil_img = Image.open(uploaded_file)
    buf = io.BytesIO()
    if pil_img.mode == 'RGBA': pil_img = pil_img.convert('RGB')
    pil_img.save(buf, format="PNG")
    try:
        session = boto3.Session(aws_access_key_id=ACCESS_ID, aws_secret_access_key=ACCESS_KEY, region_name=region)
        textract = session.client("textract")
        response = textract.analyze_document(Document={"Bytes": buf.getvalue()}, FeatureTypes=["FORMS"])
        palavras = [b["Text"] for b in response["Blocks"] if b["BlockType"] == "WORD" and b["Confidence"] > cnh_confianca_minima]
        return " ".join(palavras), pil_img
    except Exception as e:
        st.error(f"Erro no AWS Textract: {e}")
        return None, None

def cnh_extrair_nome_cpf(cnh_texto):
    if not cnh_texto: return {"nome": "Não encontrado", "cpf": "Não encontrado"}
    cnh_texto = " ".join(cnh_texto.split())
    padrao_nome = r"\bNOME\s+([A-ZÀ-Ü\s]+?)\s+(?:CPF|DOC|DATA|FILIAÇÃO|\d{3}\.\d{3}\.\d{3}-\d{2})"
    padrao_cpf = r"\bCPF\b[^0-9]{0,30}(\d{3}\.\d{3}\.\d{3}-\d{2})"
    nome_match = re.search(padrao_nome, cnh_texto, flags=re.IGNORECASE)
    nome = nome_match.group(1).upper().strip() if nome_match else "Nome não encontrado"
    cpf_match = re.search(padrao_cpf, cnh_texto, flags=re.IGNORECASE)
    cpf = cpf_match.group(1) if cpf_match else "CPF não encontrado"
    return {"nome": nome, "cpf": cpf}

def extrair_dados_comprovante(uploaded_file, api_key):
    if not uploaded_file: return None, None, None
    openai.api_key = api_key
    extensao = os.path.splitext(uploaded_file.name)[1].lower()
    if extensao == ".pdf":
        imagem = convert_from_bytes(uploaded_file.getvalue(), first_page=1, last_page=1, dpi=300, fmt="png")[0]
    else:
        imagem = Image.open(uploaded_file)
    if imagem.mode == 'RGBA': imagem = imagem.convert('RGB')
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    imagem_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    try:
        resposta = openai.chat.completions.create(
            model=openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Analise a imagem deste comprovante de residência. Extraia o nome completo do titular e o endereço completo. Retorne os dados em um formato JSON com as chaves 'comprovante_nome' e 'comprovante_endereco'. Se não encontrar, retorne uma string vazia."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imagem_base64}"}}
                ]}
            ], max_tokens=1000)
        dados = json.loads(resposta.choices[0].message.content)
        return dados.get("comprovante_nome", ""), dados.get("comprovante_endereco", ""), imagem
    except Exception as e:
        st.error(f"Erro na API da OpenAI: {e}")
        return None, None, None

def comparar_nomes(nome1, nome2):
    if not nome1 or not nome2: return False
    def limpar(nome):
        nome = unicodedata.normalize("NFKD", nome.upper()).encode("ASCII", "ignore").decode("ASCII")
        return re.sub(r"[^\w\s]", "", nome).strip()
    n1, n2 = limpar(nome1), limpar(nome2)
    if n1 == n2: return True
    palavras1, palavras2 = set(n1.split()), set(n2.split())
    if not palavras1 or not palavras2: return False
    proporcao = len(palavras1 & palavras2) / min(len(palavras1), len(palavras2))
    return proporcao >= (comprovante_similaridade_minima / 100.0)

def comparar_faces(cnh_file, selfie_file):
    if not cnh_file or not selfie_file: return None, 0.0, False, False
    def load_bytes(file):
        ext = Path(file.name).suffix.lower()
        if ext == ".pdf":
            page = convert_from_bytes(file.getvalue(), dpi=300, first_page=1, last_page=1)[0]
        else:
            page = Image.open(file)
        if page.mode == 'RGBA': page = page.convert('RGB')
        buf = io.BytesIO()
        page.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    bytes_cnh, bytes_selfie = load_bytes(cnh_file), load_bytes(selfie_file)
    try:
        client = boto3.client("rekognition", aws_access_key_id=ACCESS_ID, aws_secret_access_key=ACCESS_KEY, region_name=region)
        response = client.compare_faces(SourceImage={"Bytes": bytes_cnh}, TargetImage={"Bytes": bytes_selfie})
        face_detectada_cnh = "SourceImageFace" in response
        similaridade = response["FaceMatches"][0]["Similarity"] if response.get("FaceMatches") else 0.0
        match_valido = similaridade >= selfie_similaridade_minima
        return response, similaridade, face_detectada_cnh, match_valido
    except Exception as e:
        st.error(f"Erro no AWS Rekognition: {e}")
        return None, 0.0, False, False

# --- Lógica do Botão ---
with tab_config:
    if st.button("Iniciar Verificação Completa", type="primary", use_container_width=True):
        if not all([cnh_file, comprovante_file, selfie_file, ACCESS_ID, ACCESS_KEY, openai_api_key]):
            st.error("ERRO: Por favor, carregue todos os três documentos e insira todas as credenciais de API na barra lateral antes de iniciar.")
        else:
            with st.spinner("Analisando documentos e realizando verificação facial..."):
                # Etapa 1: CNH
                cnh_texto, cnh_img = processar_arquivo_cnh(cnh_file)
                st.session_state.dados_cnh = {"imagem": cnh_img, **cnh_extrair_nome_cpf(cnh_texto)}
                
                # Etapa 2: Comprovante
                nome_comp, end_comp, comp_img = extrair_dados_comprovante(comprovante_file, openai_api_key)
                st.session_state.dados_comprovante = {"nome": nome_comp, "endereco": end_comp, "imagem": comp_img}
                
                # Etapa 3: Comparação Facial
                resp, sim, face_cnh, match = comparar_faces(cnh_file, selfie_file)
                st.session_state.dados_faciais = {"similaridade": sim, "face_detectada_cnh": face_cnh, "match_valido": match}
                
                st.session_state.processo_iniciado = True
            st.success("Processo concluído! Verifique os resultados nas abas 'Análise' e 'Resultado Final'.")

with tab_analise:
    st.header("Análise Detalhada dos Documentos")
    if not st.session_state.processo_iniciado:
        st.info("Clique em 'Iniciar Verificação' na primeira aba para ver a análise.")
    else:
        col_cnh, col_comp, col_selfie = st.columns(3)
        with col_cnh:
            st.subheader("CNH")
            if st.session_state.dados_cnh and st.session_state.dados_cnh.get("imagem"):
                st.image(st.session_state.dados_cnh["imagem"], caption="CNH Processada", width=300)
                st.write(f"**Nome:** `{st.session_state.dados_cnh.get('nome', 'N/A')}`")
                st.write(f"**CPF:** `{st.session_state.dados_cnh.get('cpf', 'N/A')}`")

        with col_comp:
            st.subheader("Comprovante")
            if st.session_state.dados_comprovante and st.session_state.dados_comprovante.get("imagem"):
                st.image(st.session_state.dados_comprovante["imagem"], caption="Comprovante Processado", width=300)
                st.write(f"**Nome:** `{st.session_state.dados_comprovante.get('nome', 'N/A')}`")
                st.write(f"**Endereço:** `{st.session_state.dados_comprovante.get('endereco', 'N/A')}`")

        with col_selfie:
            st.subheader("Selfie")
            if selfie_file:
                st.image(selfie_file, caption="Selfie", width=300)
                sim_facial = st.session_state.dados_faciais.get('similaridade', 0.0)
                st.write(f"**Similaridade com CNH:** `{sim_facial:.2f}%`")
                
with tab_resultado:
    st.header("Resultado Final da Validação")
    if not st.session_state.processo_iniciado:
        st.info("Clique em 'Iniciar Verificação' na primeira aba para ver o resultado.")
    else:
        # Recupera dados do estado da sessão
        cnh_nome = st.session_state.dados_cnh.get('nome', '')
        cnh_cpf = st.session_state.dados_cnh.get('cpf', '')
        comp_nome = st.session_state.dados_comprovante.get('nome', '')
        comp_end = st.session_state.dados_comprovante.get('endereco', '')
        similaridade = st.session_state.dados_faciais.get('similaridade', 0.0)
        face_cnh = st.session_state.dados_faciais.get('face_detectada_cnh', False)
        match_valido = st.session_state.dados_faciais.get('match_valido', False)

        # Lógica de validação
        def sim_nao(flag): return "✅" if flag else "❌"
        
        cnh_ok = cnh_nome != "Nome não encontrado" and cnh_cpf != "CPF não encontrado"
        comp_ok = bool(comp_nome)
        nomes_ok = comparar_nomes(cnh_nome, comp_nome)
        similaridade_ok = similaridade >= selfie_similaridade_minima

        aprovado = all([cnh_ok, comp_ok, nomes_ok, face_cnh, match_valido, similaridade_ok])

        # Exibição do status geral
        if aprovado:
            st.success("### 🟢 CADASTRO APROVADO")
        else:
            st.error("### 🔴 CADASTRO NÃO APROVADO")

        # Exibição do resumo
        st.subheader("Resumo das Verificações")
        st.markdown(f"""
        - **{sim_nao(cnh_ok)} Extração da CNH:** Dados de nome e CPF foram lidos com sucesso.
        - **{sim_nao(comp_ok)} Extração do Comprovante:** O nome do titular foi identificado.
        - **{sim_nao(nomes_ok)} Correspondência de Nomes:** O nome na CNH e no comprovante são compatíveis.
        - **{sim_nao(face_cnh)} Detecção Facial na CNH:** O rosto foi localizado no documento.
        - **{sim_nao(match_valido)} Correspondência Facial:** O rosto na selfie corresponde ao do documento.
        - **{sim_nao(similaridade_ok)} Nível de Similaridade:** A confiança de **{similaridade:.2f}%** atingiu o mínimo de **{selfie_similaridade_minima:.2f}%**.
        """)

        # Exibição dos dados consolidados
        st.subheader("Dados Consolidados")
        st.json({
            "Nome Verificado": cnh_nome if cnh_ok else "Falha na extração",
            "CPF Verificado": cnh_cpf if cnh_ok else "Falha na extração",
            "Endereço Verificado": comp_end if comp_ok and nomes_ok else "Não validado",
            "Similaridade Facial": f"{similaridade:.2f}%",
            "Status Final": "Aprovado" if aprovado else "Não Aprovado"
        })