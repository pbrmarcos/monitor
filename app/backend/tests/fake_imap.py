"""Servidor IMAP mínimo para testes: registra os comandos recebidos e nunca altera mensagens."""
import socketserver
import threading


def message(sender, subject, body, message_id, extra=''):
    return (f'From: {sender}\r\nTo: contato@frente01.example\r\nSubject: {subject}\r\n'
            f'Message-ID: {message_id}\r\nDate: Thu, 12 Nov 2026 09:00:00 -0300\r\n{extra}'
            f'Content-Type: text/plain; charset=utf-8\r\n\r\n{body}\r\n').encode()


class FakeImap:
    def __init__(self, messages, password='segredo', sent=None):
        self.messages = dict(messages)  # uid -> bytes
        self.sent = None if sent is None else dict(sent)  # pasta de enviados opcional
        self.sent_name = 'INBOX.Sent'
        self.password = password
        self.commands = []
        self.omit_uids = set()
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                current = outer.messages
                self.wfile.write(b'* OK IMAP4rev1 pronto\r\n')
                while line := self.rfile.readline():
                    tag, _, command = line.decode().strip().partition(' ')
                    outer.commands.append(command)
                    upper = command.upper()
                    reply = []
                    if upper.startswith('CAPABILITY'):
                        reply = ['* CAPABILITY IMAP4rev1']
                    elif upper.startswith('LOGIN'):
                        if outer.password not in command:
                            self.wfile.write(f'{tag} NO credenciais invalidas\r\n'.encode())
                            continue
                    elif upper.startswith('LIST'):
                        reply = ['* LIST (\\HasNoChildren) "." INBOX']
                        if outer.sent is not None:
                            reply.append(f'* LIST (\\HasNoChildren \\Sent) "." "{outer.sent_name}"')
                    elif upper.startswith('EXAMINE'):
                        name = command.split(' ', 1)[1].strip().strip('"')
                        if name.upper() == 'INBOX':
                            current = outer.messages
                        elif outer.sent is not None and name == outer.sent_name:
                            current = outer.sent
                        else:
                            self.wfile.write(f'{tag} NO pasta inexistente\r\n'.encode())
                            continue
                        reply = [f'* {len(current)} EXISTS', f'* OK [UIDVALIDITY {7 if current is outer.messages else 9}] ok']
                    elif upper.startswith('UID SEARCH'):
                        low = int(command.split('UID')[-1].split(':')[0]) if ':' in command else 0
                        reply = ['* SEARCH ' + ' '.join(str(uid) for uid in sorted(current) if uid >= low)]
                    elif upper.startswith('UID FETCH'):
                        for uid in (int(value) for value in command.split()[2].split(',')):
                            if uid in outer.omit_uids:
                                continue
                            raw = current[uid]
                            head = f'* {uid} FETCH (UID {uid} FLAGS (\\Seen) BODYSTRUCTURE ("TEXT" "PLAIN") BODY[]<0> {{{len(raw)}}}\r\n'
                            self.wfile.write(head.encode() + raw + b')\r\n')
                    elif upper.startswith('LOGOUT'):
                        self.wfile.write(f'* BYE\r\n{tag} OK fim\r\n'.encode())
                        return
                    elif not upper.startswith('NOOP'):
                        self.wfile.write(f'{tag} BAD comando nao permitido\r\n'.encode())
                        continue
                    self.wfile.write(''.join(f'{item}\r\n' for item in reply).encode() + f'{tag} OK feito\r\n'.encode())

        self.server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
