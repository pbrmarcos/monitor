<?php
/** Chame no SERVIDOR após validar o contato e manter o handler de e-mail existente.
 * Requer PHP com cURL. Configure MONITOR_RELAY_URL, MONITOR_SITE_ID e
 * MONITOR_SITE_TOKEN no ambiente do servidor, fora da pasta pública.
 * Função auxiliar, não um endpoint público pronto.
 */
function forwardToMonitor(array $validatedSubmission): bool {
    $base = rtrim(getenv('MONITOR_RELAY_URL') ?: '', '/');
    $siteId = getenv('MONITOR_SITE_ID') ?: '';
    $token = getenv('MONITOR_SITE_TOKEN') ?: '';
    if (!str_starts_with($base, 'https://') || !ctype_digit($siteId) || strlen($token) < 32) {
        return false;
    }
    $payload = json_encode([
        'submission_id' => $validatedSubmission['submission_id'],
        'name' => $validatedSubmission['name'] ?? '',
        'email' => $validatedSubmission['email'],
        'subject' => $validatedSubmission['subject'] ?? 'Contato pelo site',
        'message' => $validatedSubmission['message'],
    ], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
    $curl = curl_init($base . '/forms/' . $siteId);
    curl_setopt_array($curl, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $payload,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Authorization: Bearer ' . $token],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 3,
        CURLOPT_TIMEOUT => 6,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_SSL_VERIFYHOST => 2,
    ]);
    $response = curl_exec($curl);
    $status = curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    // false: mantenha o e-mail; caso exista fila, repita usando o MESMO ID.
    // Nunca registre o token ou conteúdo em logs públicos.
    return $response !== false && $status === 202;
}
