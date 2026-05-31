export interface ParsedSseChunk {
  events: string[];
  rest: string;
}

/**
 * Parse raw text buffer into complete SSE event payloads using frame boundary (blank line).
 */
export function parseSseChunk(buffer: string): ParsedSseChunk {
  const frames = buffer.split(/\r?\n\r?\n/);
  const rest = frames.pop() ?? '';
  const events: string[] = [];

  for (const frame of frames) {
    const dataLines = frame
      .split(/\r?\n/)
      .filter(line => line.startsWith('data:'))
      .map(line => (line.startsWith('data: ') ? line.slice(6) : line.slice(5)));

    if (dataLines.length > 0) {
      events.push(dataLines.join('\n'));
    }
  }

  return { events, rest };
}

