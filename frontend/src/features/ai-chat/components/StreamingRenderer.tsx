import { type ReactNode } from 'react';

interface StreamingRendererProps {
  isStreaming: boolean;
  children: ReactNode;
}

export function StreamingRenderer({ isStreaming, children }: StreamingRendererProps) {
  return (
    <>
      {children}
      {isStreaming && <span className="animate-pulse">▌</span>}
    </>
  );
}
