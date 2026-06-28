/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { copyText } from '../../../utils/copy';

describe('copyText', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('uses navigator.clipboard.writeText when available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    const result = await copyText('hello');
    expect(result).toBe(true);
    expect(writeText).toHaveBeenCalledWith('hello');
  });

  it('falls back to execCommand when clipboard API fails', async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    });

    const appendChild = vi.spyOn(document.body, 'appendChild');
    const removeChild = vi.spyOn(document.body, 'removeChild');

    // execCommand in jsdom may return false, so we only verify the fallback path was entered
    await copyText('fallback text');
    expect(appendChild).toHaveBeenCalledOnce();
    const textarea = appendChild.mock.calls[0][0] as HTMLTextAreaElement;
    expect(textarea.value).toBe('fallback text');
    expect(removeChild).toHaveBeenCalledWith(textarea);
  });
});
