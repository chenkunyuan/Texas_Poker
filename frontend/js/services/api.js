export async function startGame(config, baseUrl = window.location.origin) {
    const response = await fetch(`${baseUrl}/api/game/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `Server returned ${response.status}`);
    return body;
}

export function replayUrl(id, baseUrl = window.location.origin) {
    return `${baseUrl}/api/replay/${encodeURIComponent(id)}`;
}
