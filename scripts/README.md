# Scripts

`reminder_sidecar_smoke.py` valida agendamento e fusos dentro do executável empacotado, com banco e pasta temporários isolados. O build Windows executa essa verificação antes de compilar o Tauri.

`keyring_smoke.py` verifica o Gerenciador de Credenciais do Windows com uma entrada sintética única e a remove ao final; não usa senhas reais.

`build_windows.ps1` gera instaladores e executa testes; `desktop_smoke.py` verifica o sidecar; `ui_smoke.mjs` testa a prévia com Edge headless e exige `npm run dev` ativo. `integration_smoke.mjs` testa frontend com API e SQLite reais isolados (IPC simulado). `generate_icons.py` gera ícones originais. `inspect_prototype.py` renderiza o PDF em `tmp/`. `eval_emails.py` mede a triagem de e-mails contra um CSV rotulado (`docs/eval-exemplo.csv` mostra o formato).
