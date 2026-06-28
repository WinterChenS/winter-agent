import { useState, useCallback } from 'react';
import { copyText } from '../../../utils/copy';

interface MessageActionsProps {
  content: string;
  label?: string;
}

export function MessageActions({ content, label }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const ok = await copyText(content);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [content]);

  return (
    <button
      onClick={handleCopy}
      aria-label={label || '复制消息'}
      className="
        absolute bottom-1 right-1
        p-1 rounded
        text-xs leading-none
        text-gray-400 hover:text-gray-600 hover:bg-gray-100
        transition-all duration-150
        opacity-100 sm:opacity-0 sm:group-hover:opacity-100
        focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-blue-400
      "
    >
      {copied ? (
        <span className="text-green-500 font-medium">Copied</span>
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
          />
        </svg>
      )}
    </button>
  );
}
