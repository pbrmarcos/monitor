"""Perfil único de inferência e pré-carga local; não altera pesos do modelo."""
import threading
from datetime import datetime, timezone

import httpx
from sqlmodel import Session

from .models import Setting

CONTEXT = 16384
KEEP_ALIVE = '30m'


class ModelRuntime:
    def __init__(self, engine, default_model, url):
        self.engine, self.default_model, self.url = engine, default_model, url
        self.guard = threading.Lock()
        self.running = False
        self.last = {'state': 'idle', 'detail': 'O modelo será preparado quando necessário.'}

    def config(self):
        with Session(self.engine) as db:
            model = db.get(Setting, 'model')
            enabled = db.get(Setting, 'keep_model_warm')
            return (model.value if model else self.default_model), (not enabled or enabled.value == 'true')

    def status(self):
        model, enabled = self.config()
        with self.guard:
            last = dict(self.last)
        if last.get('model') and last['model'] != model:
            last = {'state': 'idle', 'detail': 'Prepare o modelo selecionado.'}
        return {**last, 'model': model, 'enabled': enabled, 'context': CONTEXT, 'keep_alive': KEEP_ALIVE}

    def launch(self):
        # A carga pode demorar; não retenha o scheduler nem o encerramento do aplicativo.
        threading.Thread(target=self.prepare, name='monitor-model-preload', daemon=True).start()

    def prepare(self, *, force=False):
        model, enabled = self.config()
        if not enabled and not force:
            return self.status()
        with self.guard:
            if self.running:
                busy = True
            else:
                busy = False
                self.running = True
                self.last = {'state': 'preparing', 'model': model, 'detail': 'Preparando o modelo em segundo plano…'}
        if busy:
            return self.status()
        result = {'state': 'error', 'model': model, 'detail': 'Não foi possível preparar o modelo. Confira o Ollama.'}
        try:
            with httpx.Client(timeout=httpx.Timeout(240, connect=3), trust_env=False) as client:
                tags = client.get(f'{self.url}/api/tags')
                tags.raise_for_status()
                installed = {item['name'] for item in tags.json().get('models', [])}
                if model not in installed and (model + ':latest') not in installed:
                    result.update(state='missing', detail='O modelo selecionado ainda não foi baixado.')
                else:
                    active = client.get(f'{self.url}/api/ps')
                    active.raise_for_status()
                    loaded = active.json().get('models', [])
                    conflicts = any(item.get('name') not in (model, model + ':latest') or item.get('context_length', CONTEXT) != CONTEXT for item in loaded)
                    if conflicts and not force:
                        result.update(state='deferred', detail='Há um modelo ou contexto diferente em uso. A pré-carga automática foi adiada; use Preparar modelo para trocar agora.')
                    else:
                        response = client.post(f'{self.url}/api/chat', json={'model': model, 'messages': [], 'stream': False,
                                               'keep_alive': KEEP_ALIVE, 'options': {'num_ctx': CONTEXT}})
                        response.raise_for_status()
                        payload = response.json()
                        if payload.get('done') is True and not payload.get('error'):
                            result.update(state='ready', detail='Modelo preparado para texto e imagens no mesmo contexto.',
                                          prepared_at=datetime.now(timezone.utc).isoformat(),
                                          load_seconds=round(float(payload.get('load_duration') or 0) / 1e9, 2))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            pass
        finally:
            with self.guard:
                self.last, self.running = result, False
        return self.status()
