"""Ditado por voz com transcrição local (Whisper). O áudio nunca sai deste computador.

O modelo é baixado uma vez, pelo botão em Configurações, do repositório público Systran/faster-whisper-*
no Hugging Face. O arquivo principal tem o SHA-256 conferido contra o publicado pelo repositório.
"""
import hashlib
import importlib.util
import io
import shutil
import threading
import time
from pathlib import Path

import httpx

SIZES = {
    'tiny': {'label': 'Rápido', 'mb': 75},
    'base': {'label': 'Equilibrado', 'mb': 145},
    'small': {'label': 'Preciso', 'mb': 484},
}
DEFAULT_SIZE = 'small'
REPO = 'Systran/faster-whisper-{size}'
REQUIRED = ('config.json', 'model.bin', 'tokenizer.json')
OPTIONAL = ('vocabulary.txt', 'vocabulary.json', 'preprocessor_config.json')
API = 'https://huggingface.co/api/models/{repo}?blobs=true'
FILE = 'https://huggingface.co/{repo}/resolve/main/{name}'
MAX_AUDIO = 12 * 1024 * 1024
IDLE_SECONDS = 600


class VoiceError(Exception):
    """Mensagem pronta para a interface."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class WhisperEngine:
    """Envolve o faster-whisper. Fica em memória enquanto for usado."""

    def __init__(self, path: str):
        try:
            from faster_whisper import WhisperModel
        except Exception:  # pacote ausente ou biblioteca nativa que não carregou
            raise VoiceError('O motor de voz não pôde ser carregado neste computador.', 503) from None
        self.model = WhisperModel(path, device='cpu', compute_type='int8')

    def transcribe(self, audio: bytes, prompt: str = '') -> str:
        segments, _ = self.model.transcribe(io.BytesIO(audio), language='pt', beam_size=1, vad_filter=False,
                                            condition_on_previous_text=False, initial_prompt=prompt or None)
        return ' '.join(segment.text.strip() for segment in segments).strip()


class Voice:
    def __init__(self, folder: Path, engine_factory=None, transport=None, installed=None):
        self.folder = folder / 'voice'
        self.engine_factory = engine_factory or WhisperEngine
        self.transport = transport
        self._installed = installed
        self.engine = None
        self.engine_size = ''
        self.last_used = 0.0
        self.lock = threading.Lock()
        self.job: dict = {}

    def available(self) -> bool:
        if self._installed is not None:
            return self._installed
        return importlib.util.find_spec('faster_whisper') is not None

    def path(self, size: str) -> Path:
        return self.folder / size

    def ready(self, size: str) -> bool:
        directory = self.path(size)
        return (directory / 'model.bin').is_file() and (directory / '.verified').is_file() and all((directory / name).is_file() for name in REQUIRED)

    def status(self, size: str) -> dict:
        job = dict(self.job) if self.job.get('size') == size else {}
        return {'size': size, 'sizes': [{'id': key, **value} for key, value in SIZES.items()], 'engine': self.available(),
                'ready': self.ready(size), 'downloading': bool(job.get('running')), 'progress': job.get('progress', 0.0),
                'error': job.get('error', '') if not self.ready(size) else ''}

    # ---- Download -------------------------------------------------------

    def start_download(self, size: str) -> None:
        if size not in SIZES:
            raise VoiceError('Modelo de voz desconhecido.')
        with self.lock:
            if self.job.get('running'):
                raise VoiceError('Já existe um download em andamento.', 409)
            self.job = {'size': size, 'running': True, 'progress': 0.0, 'error': ''}
        threading.Thread(target=self._download, args=(size,), daemon=True).start()

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=httpx.Timeout(60, connect=10), follow_redirects=True, transport=self.transport)

    def _download(self, size: str) -> None:
        repo = REPO.format(size=size)
        directory = self.path(size)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / '.verified').unlink(missing_ok=True)
            with self._client() as client:
                listing = client.get(API.format(repo=repo))
                listing.raise_for_status()
                files = {item['rfilename']: item for item in listing.json().get('siblings', [])}
                wanted = [name for name in REQUIRED + OPTIONAL if name in files]
                if any(name not in files for name in REQUIRED):
                    raise VoiceError('O repositório do modelo mudou de formato. Atualize o Monitor.')
                total = sum(int(files[name].get('size') or 0) for name in wanted) or 1
                done = 0
                for name in wanted:
                    target, part = directory / name, directory / f'{name}.part'
                    expected = int(files[name].get('size') or 0)
                    if not (target.is_file() and target.stat().st_size == expected):
                        self._fetch(client, FILE.format(repo=repo, name=name), part, expected, lambda n: self._progress(done + n, total))
                        part.replace(target)
                    done += expected
                    self._progress(done, total)
                digest = (files['model.bin'].get('lfs') or {}).get('sha256')
                if not digest:
                    raise VoiceError('Não foi possível conferir a integridade do modelo.')
                if self._sha256(directory / 'model.bin') != digest:
                    (directory / 'model.bin').unlink(missing_ok=True)
                    raise VoiceError('O arquivo baixado não confere com o publicado. Tente baixar de novo.')
                (directory / '.verified').write_text(digest, encoding='utf-8')
            self.job['progress'] = 1.0
        except VoiceError as error:
            self.job['error'] = str(error)
        except (httpx.HTTPError, OSError, ValueError, KeyError):
            self.job['error'] = 'Não foi possível baixar o modelo. Verifique a conexão e tente de novo; o download continua de onde parou.'
        finally:
            self.job['running'] = False

    def _progress(self, done: int, total: int) -> None:
        self.job['progress'] = min(0.99, done / total)

    @staticmethod
    def _fetch(client: httpx.Client, url: str, part: Path, expected: int, report) -> None:
        have = part.stat().st_size if part.is_file() else 0
        if expected and have > expected:
            part.unlink()
            have = 0
        headers = {'Range': f'bytes={have}-'} if have else {}
        with client.stream('GET', url, headers=headers) as response:
            if response.status_code == 416:
                return
            response.raise_for_status()
            if have and response.status_code != 206:
                have = 0  # o servidor ignorou o Range: recomeça
            with part.open('ab' if have else 'wb') as handle:
                for chunk in response.iter_bytes(1 << 20):
                    handle.write(chunk)
                    have += len(chunk)
                    report(have)
        if expected and part.stat().st_size != expected:
            raise VoiceError('O download veio incompleto. Tente de novo.')

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1 << 20), b''):
                digest.update(block)
        return digest.hexdigest()

    def remove(self, size: str) -> None:
        with self.lock:
            if self.job.get('running'):
                raise VoiceError('Aguarde o download terminar.', 409)
            if self.engine_size == size:
                self.engine = None
            shutil.rmtree(self.path(size), ignore_errors=True)

    # ---- Transcrição ----------------------------------------------------

    def transcribe(self, audio: bytes, size: str, prompt: str = '') -> str:
        if not audio:
            raise VoiceError('Não recebi áudio. Tente gravar de novo.')
        if len(audio) > MAX_AUDIO:
            raise VoiceError('A gravação é longa demais. Grave trechos de até 3 minutos.', 413)
        if not self.available():
            raise VoiceError('O motor de voz não está incluído nesta instalação.', 503)
        if not self.ready(size):
            raise VoiceError('Baixe o modelo de voz em Configurações antes de usar o microfone.', 409)
        with self.lock:
            try:
                if self.engine is None or self.engine_size != size:
                    self.engine, self.engine_size = None, size
                    self.engine = self.engine_factory(str(self.path(size)))
                self.last_used = time.monotonic()
                return self.engine.transcribe(audio, prompt)
            except VoiceError:
                raise
            except Exception:
                # Áudio ilegível ou falha do motor: a mensagem não expõe detalhes internos.
                raise VoiceError('Não consegui entender este áudio. Tente gravar de novo, mais perto do microfone.', 422) from None

    def unload_idle(self) -> None:
        """Libera a memória do modelo depois de 10 minutos sem uso."""
        if self.lock.acquire(blocking=False):
            try:
                if self.engine is not None and time.monotonic() - self.last_used > IDLE_SECONDS:
                    self.engine = None
            finally:
                self.lock.release()


def router(voice: Voice, session, demo: bool = False):
    from fastapi import APIRouter, Depends, HTTPException, Request
    from pydantic import BaseModel
    from sqlmodel import Session
    from starlette.concurrency import run_in_threadpool

    from . import prefs
    from .models import Setting

    api = APIRouter()

    class SizeInput(BaseModel):
        size: str

    def chosen(db: Session) -> str:
        row = db.get(Setting, 'voice_size')
        return row.value if row and row.value in SIZES else DEFAULT_SIZE

    @api.get('/voice')
    def status(db: Session = Depends(session)):
        return voice.status(chosen(db))

    @api.put('/voice')
    def choose(payload: SizeInput, db: Session = Depends(session)):
        if payload.size not in SIZES:
            raise HTTPException(400, 'Modelo de voz desconhecido.')
        db.merge(Setting(key='voice_size', value=payload.size))
        db.commit()
        return voice.status(payload.size)

    @api.post('/voice/download', status_code=202)
    def download(db: Session = Depends(session)):
        if not voice.available():
            raise HTTPException(503, 'O motor de voz não está incluído nesta instalação.')
        try:
            voice.start_download(chosen(db))
        except VoiceError as error:
            raise HTTPException(error.status, str(error)) from None
        return voice.status(chosen(db))

    @api.delete('/voice', status_code=204)
    def remove(db: Session = Depends(session)):
        try:
            voice.remove(chosen(db))
        except VoiceError as error:
            raise HTTPException(error.status, str(error)) from None

    @api.post('/assistant/transcribe')
    async def transcribe(request: Request, db: Session = Depends(session)):
        if int(request.headers.get('content-length') or 0) > MAX_AUDIO:
            raise HTTPException(413, 'A gravação é longa demais. Grave trechos de até 3 minutos.')
        audio = await request.body()
        # Nomes das frentes ajudam o reconhecimento de palavras que não são comuns em português.
        prompt = ', '.join([*prefs.front_names(db).values(), 'Monitor'])
        try:
            return {'text': await run_in_threadpool(voice.transcribe, audio, chosen(db), prompt)}
        except VoiceError as error:
            raise HTTPException(error.status, str(error)) from None

    return api
