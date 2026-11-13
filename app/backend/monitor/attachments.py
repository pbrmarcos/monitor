"""Leitura local de arquivos anexados ao assistente.

O conteúdo é lido neste computador e só vai para o modelo local. Nada é executado nem enviado a serviços externos.
"""
import base64
import io
import re
import zipfile
from xml.etree import ElementTree

from .mail import _Text

MAX_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 6 * 1024 * 1024
TEXT_LIMIT = 40000
PDF_PAGES = 80
SHEET_ROWS = 2000
XML_LIMIT = 40 * 1024 * 1024
TEXT_EXTENSIONS = ('.txt', '.md', '.csv', '.tsv', '.json', '.log', '.eml', '.xml', '.html', '.htm', '.yaml', '.yml', '.ini')
IMAGE_TYPES = ((b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'))
SUPPORTED = 'Envie texto (.txt, .md, .csv, .json), PDF, Word (.docx), Excel (.xlsx) ou imagem (PNG e JPEG).'


class AttachmentError(Exception):
    """Mensagem pronta para a interface; `status` indica o código HTTP."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def clean_name(name: str) -> str:
    name = re.sub(r'[\x00-\x1f\x7f]', '', name.replace('\\', '/').split('/')[-1]).strip()
    return name[:120] or 'arquivo'


def decode(data: bytes) -> str:
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1', 'replace')


def _xml(archive: zipfile.ZipFile, member: str) -> ElementTree.Element:
    try:
        info = archive.getinfo(member)
    except KeyError:
        raise AttachmentError('O arquivo está incompleto ou não é um documento válido.') from None
    if info.file_size > XML_LIMIT:
        raise AttachmentError('O documento é grande demais para ser lido.', 413)
    return ElementTree.fromstring(archive.read(member))


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def read_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = _xml(archive, 'word/document.xml')
    except (zipfile.BadZipFile, ElementTree.ParseError):
        raise AttachmentError('Não foi possível abrir este arquivo Word.') from None
    paragraphs = []
    for node in root.iter():
        if _local(node.tag) != 'p':
            continue
        parts = []
        for child in node.iter():
            name = _local(child.tag)
            if name == 't' and child.text:
                parts.append(child.text)
            elif name in ('tab', 'br'):
                parts.append('\t' if name == 'tab' else '\n')
        paragraphs.append(''.join(parts))
    return '\n'.join(paragraphs)


def read_xlsx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            strings: list[str] = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                for item in _xml(archive, 'xl/sharedStrings.xml'):
                    strings.append(''.join(node.text or '' for node in item.iter() if _local(node.tag) == 't'))
            sheets = sorted((name for name in archive.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name)),
                            key=lambda name: int(re.search(r'(\d+)\.xml', name).group(1)))
            if not sheets:
                raise AttachmentError('Esta planilha não tem abas legíveis.')
            out = []
            for number, name in enumerate(sheets, 1):
                out.append(f'Planilha {number}')
                rows = 0
                for row in _xml(archive, name).iter():
                    if _local(row.tag) != 'row':
                        continue
                    cells = []
                    for cell in row:
                        if _local(cell.tag) != 'c':
                            continue
                        kind = cell.get('t')
                        value = next((node for node in cell if _local(node.tag) == 'v'), None)
                        if kind == 'inlineStr':
                            text = ''.join(node.text or '' for node in cell.iter() if _local(node.tag) == 't')
                        elif value is None or value.text is None:
                            text = ''
                        elif kind == 's':
                            index = int(value.text)
                            text = strings[index] if 0 <= index < len(strings) else ''
                        else:
                            text = value.text
                        cells.append(text.replace('\t', ' ').replace('\n', ' '))
                    if any(cells):
                        out.append('\t'.join(cells).rstrip('\t'))
                        rows += 1
                    if rows >= SHEET_ROWS:
                        out.append('[restante da planilha omitido]')
                        break
            return '\n'.join(out)
    except (zipfile.BadZipFile, ElementTree.ParseError, ValueError):
        raise AttachmentError('Não foi possível abrir esta planilha.') from None


def read_pdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            raise AttachmentError('Este PDF está protegido por senha. Remova a proteção e envie de novo.')
        pages = reader.pages[:PDF_PAGES]
        text = '\n\n'.join((page.extract_text() or '').strip() for page in pages)
        return text, len(reader.pages)
    except AttachmentError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, OSError, RecursionError):
        raise AttachmentError('Não foi possível ler este PDF.') from None


def read_image(data: bytes) -> str:
    if len(data) > MAX_IMAGE_BYTES:
        raise AttachmentError('A imagem é grande demais. Envie uma captura de até 6 MB.', 413)
    for magic, mime in IMAGE_TYPES:
        if data.startswith(magic):
            return mime
    raise AttachmentError('Formato de imagem não suportado. Use PNG ou JPEG.', 415)


def read(name: str, data: bytes) -> dict:
    """Extrai o conteúdo de um arquivo. Devolve kind, text, image (base64), mime, pages e truncated."""
    if not data:
        raise AttachmentError('O arquivo está vazio.')
    if len(data) > MAX_BYTES:
        raise AttachmentError('O arquivo passa de 10 MB.', 413)
    lowered = name.lower()
    result = {'kind': 'text', 'text': '', 'image': '', 'mime': 'text/plain', 'pages': 0}
    if data[:5] == b'%PDF-' or lowered.endswith('.pdf'):
        result.update(kind='pdf', mime='application/pdf')
        result['text'], result['pages'] = read_pdf(data)
        if not result['text'].strip():
            raise AttachmentError('Este PDF não tem texto selecionável (parece digitalizado). Envie as páginas como imagem.')
    elif lowered.endswith('.docx'):
        result.update(kind='docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', text=read_docx(data))
    elif lowered.endswith('.xlsx'):
        result.update(kind='xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', text=read_xlsx(data))
    elif data[:2] == b'PK' or lowered.endswith(('.doc', '.xls', '.ppt', '.pptx', '.zip', '.exe', '.dll', '.msi')):
        raise AttachmentError(f'Tipo de arquivo não suportado. {SUPPORTED}', 415)
    elif data.startswith(b'\x89PNG') or data.startswith(b'\xff\xd8\xff') or lowered.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')):
        result.update(kind='image', mime=read_image(data), image=base64.b64encode(data).decode())
        return result
    elif b'\x00' in data[:4096]:
        raise AttachmentError(f'Tipo de arquivo não suportado. {SUPPORTED}', 415)
    else:
        text = decode(data)
        if lowered.endswith(('.html', '.htm')):
            parser = _Text()
            parser.feed(text)
            text = ''.join(parser.parts)
        result['text'] = text
    text = re.sub(r'\n{3,}', '\n\n', result['text'].replace('\r\n', '\n').replace('\r', '\n')).strip()
    if not text:
        raise AttachmentError('Não encontrei texto neste arquivo.')
    result['truncated'] = len(text) > TEXT_LIMIT
    result['text'] = text[:TEXT_LIMIT]
    return result
