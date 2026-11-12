"""Leitura GET na sessão local do Chrome do Instagram Prospect, sempre headless."""
import os
import hashlib
import re
import sqlite3
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode


class BrowserError(Exception):
    def __init__(self, message, status='erro'):
        super().__init__(message)
        self.status = status


def prospect_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'InstagramProspect'


def discover():
    root = prospect_root()
    database = root / 'dados.db'
    if not database.is_file():
        return []
    try:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=3) as db:
            rows = db.execute('SELECT id, nome, handle FROM contas ORDER BY id').fetchall()
        return [{'account_id': int(identifier), 'name': name, 'username': str(handle).lstrip('@').lower(),
                 'path': str(root / 'perfis' / f'conta-{int(identifier)}')}
                for identifier, name, handle in rows
                if identifier > 0 and re.fullmatch(r'[a-zA-Z0-9_.]{1,30}', str(handle).lstrip('@'))
                and (root / 'perfis' / f'conta-{int(identifier)}' / 'Default').is_dir()]
    except (sqlite3.Error, OSError, ValueError):
        raise BrowserError('Não foi possível ler as contas do Instagram Prospect. Tente novamente.') from None


def profile_in_use(path):
    """Só informa ocupação; não encerra processos nem remove locks do Chrome."""
    if os.name != 'nt':
        return False
    script = "$p = $env:MONITOR_CHECK_PROFILE; $found = Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($p) }; if ($found) { 'busy' }"
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                env={**os.environ, 'MONITOR_CHECK_PROFILE': str(path)}, capture_output=True,
                                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise BrowserError('Não foi possível verificar se o perfil está livre. A coleta foi adiada.', 'ocupado')
        return b'busy' in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        raise BrowserError('Não foi possível verificar se o perfil está livre. A coleta foi adiada.', 'ocupado') from None


@contextmanager
def profile_lock(path):
    path = Path(path).resolve()
    if not (path / 'Default').is_dir() or not re.fullmatch(r'conta-\d+', path.name):
        raise BrowserError('Perfil do Prospect não encontrado. Confira a pasta de dados do Prospect.')
    # Este lock cobre duas instâncias do Monitor. O lock nativo do Chrome cobre o Prospect.
    with (path / '.monitor-collector.lock').open('a+b') as file:
        file.seek(0)
        file.write(b'0')
        file.flush()
        file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BrowserError('Este perfil já está sendo coletado. Nova tentativa na próxima rodada.', 'ocupado') from None
        try:
            if profile_in_use(path):
                raise BrowserError('Perfil aberto no Instagram Prospect. Coleta adiada; feche o Chrome dessa conta no Prospect.', 'ocupado')
            yield path
        finally:
            if os.name == 'nt':
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)


FETCH = """async path => {
  if (location.origin !== 'https://www.instagram.com') return {status:401, body:{}};
  const csrf = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  const r = await fetch(path, {method:'GET', credentials:'include', signal:AbortSignal.timeout(15000),
    headers:{'x-ig-app-id':'936619743392459', 'x-requested-with':'XMLHttpRequest', 'x-csrftoken':csrf}});
  let body = {}; try { body = await r.json(); } catch {}
  return {status:r.status, body};
}"""


def request(page, path, deadline):
    if time.monotonic() >= deadline:
        raise BrowserError('Tempo máximo da coleta atingido. A próxima rodada tentará novamente.')
    reply = page.evaluate(FETCH, path)
    status, body = reply.get('status'), reply.get('body')
    body = body if isinstance(body, dict) else {}
    message = str(body.get('message', ''))
    if status == 429 or re.search(r'please wait|rate.?limit|feedback_required', message, re.I):
        raise BrowserError('O Instagram limitou as consultas. Coleta pausada; revise a conta no Prospect e retome no Monitor.', 'limitado')
    if status in (401, 403) or re.search(r'login_required|challenge_required|checkpoint_required', message, re.I):
        raise BrowserError('O Instagram pediu login ou verificação. Resolva no Prospect e retome a coleta no Monitor.', 'login')
    if status != 200 or body.get('status') == 'fail':
        raise BrowserError('O Instagram não liberou esta leitura. Os últimos dados foram mantidos.')
    return body


def count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def timestamp(value):
    try:
        parsed = datetime.fromtimestamp(float(value), timezone.utc)
        return parsed if 2010 <= parsed.year <= 2100 else None
    except (ValueError, OverflowError, TypeError, OSError):
        return None


def comment_identifier(code, author, published, content):
    stable = f"{code}|{author.casefold()}|{int(published.timestamp())}|{' '.join(content.split())}"
    return str(int.from_bytes(hashlib.sha256(stable.encode()).digest()[:16]))


def read_account(page, username):
    """Até 12 posts, 100 comentários/post em duas páginas. Nunca abre Direct ou stories."""
    deadline = time.monotonic() + 150
    page.goto(f'https://www.instagram.com/{username}/', wait_until='domcontentloaded', timeout=30000)
    if re.search(r'/accounts/(login|suspended|disabled)|/challenge/|/checkpoint/', page.url):
        raise BrowserError('Faça login ou resolva a verificação desta conta no Prospect e retome no Monitor.', 'login')
    try:
        payload = request(page, '/api/v1/users/web_profile_info/?' + urlencode({'username': username}), deadline)
    except BrowserError as error:
        if error.status != 'erro':
            raise
        return read_dom(page, username, deadline)
    user = (payload.get('data') or {}).get('user')
    if not isinstance(user, dict):
        return read_dom(page, username, deadline)
    if str(user.get('username', '')).lower() != username.lower():
        raise BrowserError('Não foi possível confirmar o perfil consultado. Nenhum dado foi substituído.')
    identifier = str(user.get('id') or user.get('pk') or '')
    own_id = page.evaluate("() => document.cookie.match(/(?:^|; )ds_user_id=([^;]+)/)?.[1] || ''")
    if not identifier or str(own_id) != identifier:
        raise BrowserError('A sessão do Chrome não corresponde a esta conta. Confira o login no Prospect.', 'login')
    followers = count((user.get('edge_followed_by') or {}).get('count'))
    posts = count((user.get('edge_owner_to_timeline_media') or {}).get('count'))
    result = {'account_id': identifier, 'name': str(user.get('full_name') or '')[:120],
              'followers': followers, 'posts': posts, 'media': [], 'comments': [], 'detail': ''}
    if followers is None or posts is None:
        raise BrowserError('Os totais de seguidores/posts não foram disponibilizados. Última coleta mantida.')
    try:
        feed = request(page, f'/api/v1/feed/user/{identifier}/?count=12', deadline)
    except BrowserError as error:
        if error.status != 'erro':
            raise
        return read_dom(page, username, deadline)
    if not isinstance(feed.get('items'), list):
        return read_dom(page, username, deadline)
    for item in feed['items'][:12]:
        if not isinstance(item, dict):
            continue
        media_id = str(item.get('pk') or str(item.get('id') or '').split('_')[0])
        code, published = item.get('code'), timestamp(item.get('taken_at'))
        if not re.fullmatch(r'\d+', media_id) or not isinstance(code, str) or not re.fullmatch(r'[\w-]+', code) or not published:
            continue
        likes, comments_count = count(item.get('like_count')), count(item.get('comment_count'))
        result['media'].append({'id': 'post:' + code, 'published_at': published, 'likes': likes, 'comments': comments_count})
        if comments_count == 0:
            continue
        cursor, seen = None, set()
        for _ in range(2):
            query = {'can_support_threading': 'true', 'permalink_enabled': 'false', 'count': 50}
            if cursor:
                query['min_id'] = cursor
            try:
                data = request(page, f'/api/v1/media/{media_id}/comments/?' + urlencode(query), deadline)
            except BrowserError as error:
                if error.status in ('login', 'limitado'):
                    raise
                result['detail'] = 'Parte dos comentários não pôde ser lida; a próxima rodada tentará novamente.'
                break
            if not isinstance(data.get('comments'), list):
                result['detail'] = 'Comentários indisponíveis em parte dos posts.'
                break
            for comment in data['comments'][:50]:
                if not isinstance(comment, dict):
                    continue
                author = str((comment.get('user') or {}).get('username') or '')
                comment_id = str(comment.get('pk') or '')
                instant = timestamp(comment.get('created_at_utc') or comment.get('created_at'))
                text = str(comment.get('text') or '').strip()
                if re.fullmatch(r'\d+', comment_id) and re.fullmatch(r'[\w.]{1,30}', author) and instant and text:
                    result['comments'].append({'id': comment_identifier(code, author, instant, text[:6000]), 'author': author, 'text': text[:6000],
                                               'published_at': instant, 'post_url': f'https://www.instagram.com/p/{code}/'})
            cursor = data.get('next_min_id')
            if not data.get('has_more_comments') or not cursor or str(cursor) in seen:
                break
            cursor = str(cursor)
            seen.add(cursor)
        else:
            if data.get('has_more_comments'):
                result['detail'] = 'Há mais comentários do que o limite desta coleta (100 por post).'
    return result


def exact_number(value):
    value = str(value).strip()
    if not re.fullmatch(r'[\d.,\s]+', value):
        return None
    groups = re.split(r'[.,\s]+', value)
    if len(groups) > 1 and (len(groups[0]) > 3 or any(len(part) != 3 for part in groups[1:])):
        return None
    digits = re.sub(r'\D', '', value)
    return int(digits) if digits else None


PROFILE_DOM = """() => {
  const header = document.querySelector('main header') || document.querySelector('header');
  return {text:header?.innerText || '', title:document.querySelector('meta[property="og:title"]')?.content || '',
    links:[...(header?.querySelectorAll('a[href]') || [])].map(a=>({href:a.getAttribute('href'), title:a.querySelector('[title]')?.title || ''})),
    posts:[...document.querySelectorAll('main a[href]')].map(a=>a.getAttribute('href')).filter(h=>/^\\/(?:[A-Za-z0-9_.]+\\/)?(p|reel)\\/[A-Za-z0-9_-]+\\//.test(h)),
    own:document.cookie.match(/(?:^|; )ds_user_id=([^;]+)/)?.[1] || ''};
}"""

POST_DOM = """() => {
  const root = document.querySelector('main');
  const times = [...(root?.querySelectorAll('time[datetime]') || [])];
  const comments = [];
  for (const time of times) {
    let node = time.parentElement;
    for (let i=0; i<8 && node && node !== root; i++,node=node.parentElement) {
      if (node.querySelectorAll('time[datetime]').length !== 1) break;
      const link = [...node.querySelectorAll('a[href]')].find(a=>/^\\/[A-Za-z0-9_.]{1,30}\\/$/.test(a.getAttribute('href') || ''));
      if (!link) continue;
      const spans = [...node.querySelectorAll('span[dir="auto"]')].filter(s=>!s.closest('a') && !s.querySelector('time') && !s.querySelector('button'));
      const text = spans.map(s=>s.innerText?.trim() || '').filter(Boolean).sort((a,b)=>b.length-a.length)[0];
      if (text) comments.push({author:link.getAttribute('href').split('/')[1], text, date:time.dateTime});
      break;
    }
  }
  return {dates:times.map(t=>t.dateTime), comments,
    description:document.querySelector('meta[property="og:description"]')?.content || '',
    login:!!document.querySelector('input[name="password"]')};
}"""


def read_dom(page, username, deadline):
    """Fallback pela página da própria conta; não clica, publica nem abre mensagens."""
    from playwright.sync_api import Error
    try:
        page.locator('main header, header').last.wait_for(state='visible', timeout=10000)
    except Error:
        if page.locator('input[name="password"], input[name="verificationCode"]').count() or re.search(r'/challenge/|/accounts/login', page.url):
            raise BrowserError('Faça login ou resolva a verificação no Prospect e atualize a conta no Monitor.', 'login') from None
        visible = page.locator('body').inner_text(timeout=2000)[:2000]
        if re.search(r'please wait|try again later|tente novamente mais tarde|aguarde alguns minutos', visible, re.I):
            raise BrowserError('O Instagram limitou a leitura. Revise a conta no Prospect e retome no Monitor.', 'limitado') from None
        raise BrowserError('O cabeçalho do perfil não carregou. Última coleta mantida.') from None
    raw = page.evaluate(PROFILE_DOM)
    if not raw['own'] or not re.search(r'editar perfil|edit profile', raw['text'], re.I):
        raise BrowserError('Não foi possível confirmar o login da própria conta na página. Confira no Prospect.', 'login')
    if username.casefold() not in raw['text'].casefold().split():
        raise BrowserError('O cabeçalho não confirmou a conta consultada. Última coleta mantida.')
    def metric(labels, href=None):
        if href:
            for link in raw['links']:
                if href in str(link['href']) and exact_number(link['title']) is not None:
                    return exact_number(link['title'])
        match = re.search(r'([\d.,]+(?:\s*(?:mil|mi|k|m))?)\s+(?:' + labels + r')\b', raw['text'], re.I)
        return exact_number(match[1]) if match else None
    followers, posts = metric('seguidores|followers', '/followers'), metric('posts|publicações')
    if followers is None or posts is None:
        raise BrowserError('A página não mostrou os totais exatos de seguidores/posts. Última coleta mantida.')
    if posts:
        try:
            page.locator('main a[href*="/p/"], main a[href*="/reel/"]').first.wait_for(state='attached', timeout=7000)
            raw = page.evaluate(PROFILE_DOM)
        except Exception as error:
            from playwright.sync_api import Error
            if not isinstance(error, Error):
                raise
    result = {'account_id': raw['own'], 'name': raw['title'].split(' (@')[0][:120] or username,
              'followers': followers, 'posts': posts, 'media': [], 'comments': [],
              'detail': 'Leitura pela página: até 12 posts e os comentários carregados, sem expandir respostas.'}
    paths = []
    for href in raw['posts']:
        match = re.fullmatch(r'/(?:([\w.]+)/)?(p|reel)/([\w-]+)/?(?:\?.*)?', href)
        if match and (not match[1] or match[1].casefold() == username.casefold()):
            paths.append(f'/{match[2]}/{match[3]}/')
    paths = list(dict.fromkeys(paths))[:12]
    if posts and not paths:
        result['detail'] += ' A lista de posts não foi disponibilizada nesta rodada.'
    for path in paths:
        if time.monotonic() >= deadline:
            result['detail'] += ' Tempo da rodada atingido; alguns posts não foram lidos.'
            break
        try:
            page.goto('https://www.instagram.com' + path, wait_until='domcontentloaded', timeout=20000)
            page.locator('main time[datetime]').first.wait_for(state='attached', timeout=5000)
            post = page.evaluate(POST_DOM)
            if post['login'] or re.search(r'/challenge/|/accounts/login', page.url):
                raise BrowserError('A sessão pediu novo login. Resolva no Prospect e retome no Monitor.', 'login')
            dates = []
            for value in post['dates']:
                try:
                    dates.append(datetime.fromisoformat(value.replace('Z', '+00:00')))
                except (ValueError, TypeError):
                    pass
            if not dates:
                continue
            code = path.split('/')[2]
            def counter(labels):
                match = re.search(r'([\d.,]+)\s+(?:' + labels + r')\b', post['description'], re.I)
                return exact_number(match[1]) if match else None
            result['media'].append({'id': 'post:' + code, 'published_at': min(dates),
                                    'likes': counter('likes?|curtidas?'), 'comments': counter('comments?|comentários?')})
            for comment in post['comments'][:100]:
                try:
                    published = datetime.fromisoformat(comment['date'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    continue
                content = ' '.join(comment['text'].split())[:6000]
                # A interface não expõe sempre o ID; uma origem determinística evita duplicações.
                identifier = comment_identifier(code, comment['author'], published, content)
                result['comments'].append({'id': identifier, 'author': comment['author'], 'text': content,
                                           'published_at': published, 'post_url': f'https://www.instagram.com/p/{code}/'})
        except BrowserError:
            raise
        except Exception as error:
            from playwright.sync_api import Error
            if not isinstance(error, Error):
                raise
            result['detail'] += ' Um ou mais posts não puderam ser lidos.'
    return result


def collect(path, username):
    try:
        from playwright.sync_api import Error
    except ImportError:
        raise BrowserError('O coletor do Chrome não está instalado nesta versão do Monitor.') from None
    try:
        return _collect(path, username)
    except (Error, OSError, RuntimeError) as error:
        raise BrowserError('Não foi possível iniciar o coletor oculto. Confira o Chrome instalado e o acesso ao perfil do Prospect.') from None


def _collect(path, username):
    from playwright.sync_api import sync_playwright, Error
    with profile_lock(path) as directory, sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(str(directory), channel='chrome', headless=True,
                locale='pt-BR', viewport={'width': 1280, 'height': 900}, timeout=25000,
                args=['--no-first-run', '--no-default-browser-check', '--hide-crash-restore-bubble'])
        except Error:
            raise BrowserError('Chrome indisponível ou perfil em uso. Feche o Chrome dessa conta no Prospect e tente novamente.', 'ocupado') from None
        try:
            page = context.new_page()
            for previous in context.pages:
                if previous != page:
                    previous.close()
            page.set_default_timeout(15000)
            return read_account(page, username)
        except (Error, ValueError, TypeError, AttributeError):
            raise BrowserError('A leitura do Instagram foi interrompida. Os últimos dados foram mantidos.') from None
        finally:
            try:
                context.close()
            except Error:
                pass


def smoke():
    """Teste do driver empacotado e Chrome real, inteiramente sem tráfego externo."""
    import tempfile
    from unittest.mock import patch
    reader = read_account
    instant = int(time.time())

    mode = 'api'
    def fixture(page, username):
        page.context.add_cookies([{'name': 'ds_user_id', 'value': '123', 'domain': '.instagram.com', 'path': '/', 'secure': True}])
        def route(request):
            url = request.request.url
            if '/api/v1/users/web_profile_info/' in url:
                if mode == 'dom':
                    request.fulfill(status=404, body='Unavailable')
                else:
                    request.fulfill(json={'data': {'user': {'id': '123', 'username': 'fixture', 'edge_followed_by': {'count': 45}, 'edge_owner_to_timeline_media': {'count': 1}}}})
            elif '/api/v1/feed/user/' in url:
                request.fulfill(json={'items': [{'pk': '50', 'code': 'ABC', 'taken_at': instant, 'like_count': 3, 'comment_count': 1}]})
            elif '/api/v1/media/50/comments/' in url:
                request.fulfill(json={'comments': [{'pk': '901', 'user': {'username': 'cliente'}, 'text': 'Qual o valor?', 'created_at': instant}]})
            elif url == 'https://www.instagram.com/fixture/':
                request.fulfill(content_type='text/html', body='<html><body><main><header>fixture<br>45 followers<br>1 posts<br>Edit profile</header><a href="/fixture/p/ABC/">Post</a></main></body></html>')
            elif url == 'https://www.instagram.com/p/ABC/':
                date = datetime.fromtimestamp(instant, timezone.utc).isoformat()
                request.fulfill(content_type='text/html', body=f'<html><head><meta property="og:description" content="3 likes, 1 comments"></head><body><main><div><a href="/cliente/">cliente</a><span dir="auto">Qual o valor?</span><span><time datetime="{date}">agora</time></span></div></main></body></html>')
            else:
                request.abort()
        page.context.route('**/*', route)
        return reader(page, username)

    with tempfile.TemporaryDirectory(prefix='monitor-browser-smoke-') as folder:
        path = Path(folder) / 'conta-1'
        (path / 'Default').mkdir(parents=True)
        results = []
        for mode in ('api', 'dom'):
            with patch(__name__ + '.read_account', fixture):
                result = collect(path, 'fixture')
            assert result['followers'] == 45 and result['posts'] == 1
            assert len(result['comments']) == 1 and len(result['media']) == 1
            results.append(result)
        assert results[0]['comments'][0]['id'] == results[1]['comments'][0]['id']
        print('Chrome headless + packaged driver + API/DOM fixtures + stable comment identity: OK')
