<?php
/**
 * CA Agent Proxy
 * Accepts {message, session_id} from the browser, injects server-side
 * CA credentials from environment variables, and forwards to the ca-agent.
 * Credentials are never exposed to the client.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

$body = json_decode(file_get_contents('php://input'), true);
if (!$body || !isset($body['message'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing message']);
    exit;
}

$caAgentUrl  = getenv('CA_AGENT_URL') ?: 'http://ca-agent.ca-system.svc.cluster.local:8001';
$caUrl       = getenv('CA_URL')       ?: '';
$caUsername  = getenv('CA_USERNAME')  ?: '';
$caPassword  = getenv('CA_PASSWORD')  ?: '';

$payload = json_encode([
    'message'     => $body['message'],
    'session_id'  => $body['session_id'] ?? null,
    'ca_url'      => $caUrl,
    'ca_username' => $caUsername,
    'ca_password' => $caPassword,
]);

$ctx = stream_context_create([
    'http' => [
        'method'          => 'POST',
        'header'          => "Content-Type: application/json\r\nContent-Length: " . strlen($payload),
        'content'         => $payload,
        'timeout'         => 60,
        'ignore_errors'   => true,
    ],
]);

$result = @file_get_contents($caAgentUrl . '/chat', false, $ctx);

if ($result === false) {
    http_response_code(502);
    echo json_encode(['error' => 'Could not reach AI agent. Please try again.']);
    exit;
}

// Pass through the response (JSON) from ca-agent
// Check the actual status code, not a substring (which can match Content-Length)
$status_line = $http_response_header[0] ?? '';
if (preg_match('/^HTTP\/\d\.\d\s+(\d{3})\s/', $status_line, $m)) {
    $status_code = (int) $m[1];
    if ($status_code >= 500) {
        http_response_code(502);
    }
}

echo $result;
