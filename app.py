import os
import io
from flask import Flask, request, render_template, send_file, flash, redirect, url_for
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit
app.secret_key = 'replace-with-a-secure-key'

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
REPORT_FOLDER = os.path.join(os.getcwd(), 'reports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Palavras‑chave para análise de contratos de serviços médicos/hospitalares
KEYWORDS = {
    "obrigatorios": [
        "objeto", "serviços médicos", "hospitalares", "clínicas", "pacientes",
        "prefeitura", "pessoa física", "responsabilidade", "confidencialidade",
        "LGPD", "penalidade", "prazo", "vigência", "rescisão", "foro", "jurisdição"
    ],
    "ambiguos": [
        "adequado", "razoável", "conforme necessidade", "a critério", "se necessário",
        "em conformidade com a legislação aplicável"
    ]
}

def extract_text_and_logo(pdf_path):
    """Extrai todo o texto do PDF e devolve a primeira imagem (logo) caso exista.
    Retorna (texto:str, logo_bytes:bytes ou None).
    """
    doc = fitz.open(pdf_path)
    full_text = []
    logo_bytes = None
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        full_text.append(page.get_text())
        if page_num == 0 and not logo_bytes:
            # tenta extrair a primeira imagem da primeira página
            imglist = page.get_images(full=True)
            if imglist:
                xref = imglist[0][0]
                base_image = doc.extract_image(xref)
                logo_bytes = base_image["image"]
    return "\n".join(full_text), logo_bytes

def analyze_contract(text: str) -> list:
    """Analisa o texto do contrato e devolve uma lista de *issue* dictionaries.
    Cada dicionário contém: 'type' ("missing" ou "ambiguous"), 'term' e 'suggestion'."""
    issues = []
    lower = text.lower()
    # Verifica termos obrigatórios
    for term in KEYWORDS["obrigatorios"]:
        if term.lower() not in lower:
            issues.append({
                "type": "missing",
                "term": term,
                "suggestion": f"Incluir cláusula sobre **{term}**."
            })
    # Detecta ambiguidade
    for amb in KEYWORDS["ambiguos"]:
        if amb.lower() in lower:
            issues.append({
                "type": "ambiguous",
                "term": amb,
                "suggestion": f"Especificar melhor o que significa **{amb}** para evitar interpretações divergentes."
            })
    return issues

def generate_report(issues, logo_bytes=None):
    """Gera um PDF em memória com o relatório de análise.
    Mantém a logo (se houver) no cabeçalho da primeira página.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    if logo_bytes:
        # Redimensiona logo para caber na página
        img = ImageReader(io.BytesIO(logo_bytes))
        c.drawImage(img, 40, y - 80, width=120, preserveAspectRatio=True, mask='auto')
        y -= 100
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Relatório de Análise de Contrato de Serviços Médicos e Hospitalares")
    y -= 30
    c.setFont("Helvetica", 12)
    if not issues:
        c.drawString(40, y, "Nenhum ponto fraco detectado. O contrato parece conter todas as cláusulas essenciais.")
        y -= 20
    else:
        for i, issue in enumerate(issues, 1):
            if y < 80:
                c.showPage()
                y = height - 50
            c.drawString(40, y, f"{i}. [{issue['type'].title()}] {issue['term']}")
            y -= 15
            text = issue['suggestion']
            # quebra de linha simples
            for line in text.split('\n'):
                if y < 50:
                    c.showPage()
                    y = height - 50
                c.drawString(60, y, f"- {line}")
                y -= 12
            y -= 8
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'contract' not in request.files:
            flash('Nenhum arquivo enviado.')
            return redirect(request.url)
        file = request.files['contract']
        if file.filename == '':
            flash('Nenhum arquivo selecionado.')
            return redirect(request.url)
        if not file.filename.lower().endswith('.pdf'):
            flash('Apenas arquivos PDF são suportados.')
            return redirect(request.url)
        save_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(save_path)
        # Processamento
        text, logo = extract_text_and_logo(save_path)
        issues = analyze_contract(text)
        report_buf = generate_report(issues, logo)
        report_name = f"relatorio_{os.path.splitext(file.filename)[0]}.pdf"
        report_path = os.path.join(REPORT_FOLDER, report_name)
        with open(report_path, 'wb') as f:
            f.write(report_buf.read())
        return send_file(report_path, as_attachment=True, download_name=report_name)
    return render_template('index.html')

import os

if __name__ == '__main__':
    # Use the port provided by the hosting environment (Railway sets $PORT).
    # Default to 5000 for local development.
    port = int(os.getenv('PORT', 5000))
    # Disable debug mode in production; can be overridden with an env var if needed.
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
