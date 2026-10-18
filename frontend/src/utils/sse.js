// Parse complete SSE events across arbitrary UTF-8 and CRLF chunk boundaries.
export async function* readSse(response) {
  if (!response.body) throw new Error('The server returned no stream.');
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = '', type = 'message', data = [];
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let end;
      while ((end = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, end).replace(/\r$/, '');
        buffer = buffer.slice(end + 1);
        if (!line) {
          if (data.length) yield { type, data: data.join('\n') };
          type = 'message'; data = [];
        } else if (!line.startsWith(':')) {
          const colon = line.indexOf(':');
          const field = colon < 0 ? line : line.slice(0, colon);
          const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
          if (field === 'event') type = value;
          if (field === 'data') data.push(value);
        }
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
