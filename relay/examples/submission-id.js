// Acrescente este script à página do formulário existente. Não contém tokens.
// O envio original continua funcionando; o servidor repassa submission_id ao relay.
document.querySelectorAll('form[data-monitor]').forEach((form) => {
  let input = form.querySelector('input[name="submission_id"]');
  if (!input) {
    input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'submission_id';
    form.append(input);
  }
  // Preserve durante tentativas do mesmo envio; gere outro após sucesso confirmado.
  input.value ||= crypto.randomUUID();
});
