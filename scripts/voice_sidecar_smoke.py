"""Verifica, no backend empacotado, o motor de voz local e a leitura de PDF/Word dos anexos.

Nada é baixado: o modelo de voz é uma pasta falsa. Se as bibliotecas nativas do Whisper estiverem empacotadas,
o motor carrega e só o modelo falso é recusado (HTTP 422). Se faltarem, a resposta é 503.
"""
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError

root = Path(__file__).resolve().parents[1]
temporary = root / 'tmp'
temporary.mkdir(exist_ok=True)
binary = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'app/desktop/src-tauri/binaries/monitor-backend.exe'


def pdf(text: str) -> bytes:
    stream = f'BT /F1 12 Tf 72 720 Td ({text}) Tj ET'.encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out, offsets = b'%PDF-1.4\n', []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    table = ''.join(f'{offset:010d} 00000 n \n' for offset in offsets)
    return out + (f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n{table}trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
                  f'startxref\n{len(out)}\n%%EOF').encode()


def docx(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


with tempfile.TemporaryDirectory(prefix='voice-sidecar-', dir=temporary) as directory:
    assert Path(directory).resolve().is_relative_to(temporary.resolve())
    child = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             env={**os.environ, 'LOCALAPPDATA': directory, 'MONITOR_DEMO': '0', 'MONITOR_PARENT_PIPE': '1'})
    try:
        handshake = json.loads(child.stdout.readline())
        base = f"http://127.0.0.1:{handshake['port']}"
        headers = {'Authorization': f"Bearer {handshake['token']}"}

        def call(path, body=None, method=None, raw=None, content_type='application/json'):
            data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
            request = urllib.request.Request(base + path, data=data, method=method,
                                             headers={**headers, 'Content-Type': content_type})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    text = response.read()
                    return response.status, (json.loads(text) if text else None)
            except HTTPError as error:
                return error.code, json.loads(error.read() or b'null')

        for _ in range(80):
            try:
                call('/health')
                break
            except URLError:
                time.sleep(.1)
        else:
            raise RuntimeError('Packaged API did not start')

        status, voice = call('/voice')
        assert status == 200 and voice['engine'] is True and not voice['ready'], voice
        status, body = call('/assistant/transcribe', raw=b'audio', content_type='audio/webm')
        assert status == 409, (status, body)  # sem modelo: pede o download, sem tentar carregar nada

        call('/voice', {'size': 'tiny'}, method='PUT')
        fake = Path(directory) / 'Monitor' / 'voice' / 'tiny'
        fake.mkdir(parents=True)
        for name in ('config.json', 'model.bin', 'tokenizer.json', '.verified'):
            (fake / name).write_bytes(b'x')
        status, body = call('/assistant/transcribe', raw=b'audio nao valido', content_type='audio/webm')
        assert status == 422, f'O motor de voz não carregou no executável (HTTP {status}): {body}'
        assert 'entender este áudio' in body['detail'], body

        for name, data, expected in (('contrato.pdf', pdf('Contrato de aluguel 2026'), 'pdf'), ('proposta.docx', docx('Proposta comercial'), 'docx')):
            status, body = call('/assistant/attachments', {'name': name, 'data': base64.b64encode(data).decode()})
            assert status == 201 and body['kind'] == expected and body['chars'] > 5, (name, status, body)
        print('Packaged backend: local voice engine loads (native libraries bundled), PDF and Word attachments are read')
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
