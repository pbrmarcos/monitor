"""Avalia a triagem de e-mails contra um CSV rotulado pelo usuário.

Colunas do CSV (separador ;): de; para; assunto; corpo; importante (sim/nao); prazo_iso (opcional)

    .venv/Scripts/python.exe scripts/eval_emails.py docs/eval-exemplo.csv --so-regras
    .venv/Scripts/python.exe scripts/eval_emails.py meus-emails.csv --modelo qwen3.5:4b-q4_K_M

Use apenas arquivos locais; o conteúdo vai somente para o Ollama deste computador.
"""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app' / 'backend'))

from monitor import ai  # noqa: E402
from monitor.rules import Context, decide  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('csv', type=Path)
    parser.add_argument('--modelo', default=ai.DEFAULT_MODEL)
    parser.add_argument('--so-regras', action='store_true', help='não chama o Ollama; mede só as regras determinísticas')
    parser.add_argument('--hoje', type=date.fromisoformat, default=date.today(), help='data de referência para prazos relativos')
    parser.add_argument('--prioritarios', default='', help='remetentes prioritários separados por vírgula')
    args = parser.parse_args()

    with args.csv.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    if not rows:
        print('CSV vazio.')
        return 1
    context = Context(today=args.hoje, priority_senders=[v for v in args.prioritarios.split(',') if v.strip()])
    important = hits = missed = false_alerts = dated = dated_hits = failures = 0
    lost = []
    for row in rows:
        sender, subject, body = row.get('de', ''), row.get('assunto', ''), row.get('corpo', '')
        answer = None
        if not args.so_regras:
            try:
                answer = ai.analyze(sender, row.get('para', ''), subject, body, args.modelo, args.hoje).model_dump()
            except ai.OllamaUnavailable as error:
                print(f'Ollama indisponível ({error}). Rode com --so-regras ou inicie o Ollama.')
                return 2
            except ai.InvalidAnalysis:
                failures += 1
        bulk = 'unsubscribe' in body.lower() or 'descadastr' in body.lower()
        result = decide(sender, subject, body, bulk, answer, context)
        # "Revisar" conta como alerta: a mensagem não se perde, mas pede atenção.
        flagged = result['importancia'] in ('acao', 'importante', 'revisar')
        expected = row.get('importante', '').strip().lower() in ('sim', 's', '1', 'true')
        if expected:
            important += 1
            hits += flagged
            if not flagged:
                missed += 1
                lost.append(subject)
        elif flagged:
            false_alerts += 1
        if row.get('prazo_iso', '').strip():
            dated += 1
            dated_hits += str(result['prazo_iso'] or '') == row['prazo_iso'].strip()

    recall = hits / important if important else 1.0
    print(f'Mensagens avaliadas:      {len(rows)}' + ('  (somente regras)' if args.so_regras else f'  (modelo {args.modelo})'))
    print(f'Recall dos importantes:   {recall:.1%}  ({hits} de {important})  meta: 95%')
    print(f'Importantes perdidos:     {missed}')
    print(f'Alertas desnecessários:   {false_alerts} de {len(rows) - important} não importantes')
    print(f'Acerto de prazos:         {dated_hits} de {dated}')
    if failures:
        print(f'Respostas inválidas da IA: {failures} (tratadas só pelas regras)')
    for subject in lost:
        print(f'  perdido: {subject}')
    return 0 if recall >= 0.95 else 3


if __name__ == '__main__':
    raise SystemExit(main())
