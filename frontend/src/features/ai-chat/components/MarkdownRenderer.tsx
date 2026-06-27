import { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

// Module-level highlighter cache — shared across all CodeBlock instances
let highlighterPromise: Promise<unknown> | null = null;

async function getHighlighter(): Promise<unknown> {
  if (!highlighterPromise) {
    highlighterPromise = (async () => {
      try {
        const shiki = await import('shiki');
        return await (shiki as any).createHighlighter({
          themes: ['github-dark'],
          langs: [
            'typescript', 'javascript', 'python', 'java', 'bash',
            'json', 'xml', 'sql', 'yaml', 'text', 'markdown',
            'html', 'css', 'go', 'rust', 'ruby', 'php', 'shell',
          ],
        });
      } catch {
        return null;
      }
    })();
  }
  return highlighterPromise;
}

interface CodeBlockProps {
  className?: string;
  children?: React.ReactNode;
}

function CodeBlock({ className, children }: CodeBlockProps) {
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const code = String(children).replace(/\n$/, '');
  const language = className?.replace(/^language-/, '') || 'text';

  useEffect(() => {
    let cancelled = false;
    getHighlighter().then(async (highlighter) => {
      if (cancelled || !highlighter) return;
      try {
        const html = await (highlighter as any).codeToHtml(code, {
          lang: language,
          theme: 'github-dark',
        });
        if (!cancelled) setHighlighted(html);
      } catch {
        // fallback to plain pre/code
      }
    });
    return () => {
      cancelled = true;
    };
  }, [code, language]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).catch(() => {});
  }, [code]);

  return (
    <div className="relative group my-2">
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 z-10 px-2 py-1 text-xs text-gray-400 bg-gray-700 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:text-white"
      >
        复制
      </button>
      {highlighted ? (
        <div
          className="overflow-x-auto rounded-lg [&_pre]:p-4 [&_pre]:!bg-gray-900"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      ) : (
        <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm">
          <code className={className}>{children}</code>
        </pre>
      )}
    </div>
  );
}

function InlineCode({ children }: { children?: React.ReactNode }) {
  return (
    <code className="bg-gray-200 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800">
      {children}
    </code>
  );
}

const components: Components = {
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    if (className?.startsWith('language-')) {
      return <CodeBlock className={className}>{children}</CodeBlock>;
    }
    return <InlineCode>{children}</InlineCode>;
  },
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border-collapse border border-gray-300">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-gray-300 px-3 py-2 bg-gray-100 font-semibold text-left text-gray-900">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-gray-300 px-3 py-2 text-gray-800">
      {children}
    </td>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-700 my-2">
      {children}
    </blockquote>
  ),
};

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  if (!content) return null;

  return (
    <div className="text-gray-900 prose prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
