// Minimal Server-Sent Events reader for `fetch` streaming responses.
// We hand-roll this (instead of EventSource) because EventSource can't send
// an Authorization header or a POST body. Frames are `event:`/`data:` lines
// separated by a blank line, exactly as the backend emits them.

export interface SSEEvent {
  event: string;
  // Parsed JSON payload (backend always sends JSON in `data:`).
  data: unknown;
}

function parseFrame(frame: string): SSEEvent | null {
  let event = "";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (!event) {
    return null;
  }
  const raw = dataLines.join("\n");
  try {
    return { event, data: raw ? JSON.parse(raw) : null };
  } catch {
    return { event, data: raw };
  }
}

/** Yield decoded SSE events from a streaming `fetch` Response until it ends. */
export async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseFrame(frame);
      if (parsed) {
        yield parsed;
      }
    }
  }
}
