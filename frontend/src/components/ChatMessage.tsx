import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
}

const PreBlock = ({ children, ...props }: any) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = (e: React.MouseEvent<HTMLButtonElement>) => {
    const codeNode = e.currentTarget.parentElement?.querySelector('code');
    if (codeNode) {
      navigator.clipboard.writeText(codeNode.textContent || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="relative group my-4">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10 border border-gray-300"
      >
        {copied ? '已复制' : '复制'}
      </button>
      <pre className="!my-0" {...props}>
        {children}
      </pre>
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ role, content }) => {
  const isUser = role === 'user';

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
    >
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-500 text-white'
            : 'bg-gray-100 text-gray-800'
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{content}</div>
        ) : (
          <div className="prose prose-sm max-w-none prose-pre:bg-white prose-pre:text-gray-800">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                pre: PreBlock,
                code({ node, className, children, ...props }) {
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};
