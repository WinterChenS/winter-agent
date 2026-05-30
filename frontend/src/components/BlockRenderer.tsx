import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { ChartRenderer } from './ChartRenderer';
import type { ChartSpecData } from '../types/chat';

type BlockType = 'markdown' | 'chart' | 'table' | 'code';

interface ContentBlock {
  id?: string;
  type: BlockType;
  content?: string;
  chartId?: string;
  chartSpec?: ChartSpecData;
  language?: string;
}

interface BlockRendererProps {
  blocks: ContentBlock[];
  /** Chart datas from the assistant message (for backward compat) */
  chartDatas?: ChartSpecData[];
}

const PreBlock = ({ children }: any) => (
  <div className="relative group my-3">
    <pre className="!mt-0 !mb-0 bg-gray-50 rounded-lg border border-gray-200 p-3 overflow-x-auto text-sm">
      {children}
    </pre>
  </div>
);

const MarkdownBlock: React.FC<{ content: string }> = ({ content }) => (
  <div className="prose prose-sm max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-table:text-sm">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        pre: PreBlock,
        blockquote({ children }) {
          return (
            <blockquote className="border-l-4 border-blue-400 bg-blue-50 pl-4 pr-2 py-1.5 my-2 rounded-r-lg text-gray-700 not-italic">
              {children}
            </blockquote>
          );
        },
        code({ className, children, ...props }) {
          const isInline = !className;
          if (isInline) {
            return <code className="bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>;
          }
          return <code className={className} {...props}>{children}</code>;
        },
        table({ children }) {
          return <div className="overflow-x-auto my-2"><table className="min-w-full border-collapse border border-gray-300 text-sm">{children}</table></div>;
        },
        thead({ children }) { return <thead className="bg-gray-100">{children}</thead>; },
        th({ children }) { return <th className="border border-gray-300 px-3 py-1.5 text-left font-semibold">{children}</th>; },
        td({ children }) { return <td className="border border-gray-300 px-3 py-1.5">{children}</td>; },
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);

const ChartBlock: React.FC<{ chartSpec: ChartSpecData }> = ({ chartSpec }) => (
  <div className="my-3">
    <ChartRenderer chartData={chartSpec} />
  </div>
);

const TableBlock: React.FC<{ content: string }> = ({ content }) => (
  <div className="overflow-x-auto my-2">
    <table className="min-w-full border-collapse border border-gray-300 text-sm"
      dangerouslySetInnerHTML={{ __html: content }} />
  </div>
);

const CodeBlock: React.FC<{ content: string; language?: string }> = ({ content, language }) => (
  <div className="relative group my-3">
    <pre className="!mt-0 !mb-0 bg-gray-50 rounded-lg border border-gray-200 p-3 overflow-x-auto text-sm">
      <code className={language ? `language-${language}` : ''}>{content}</code>
    </pre>
  </div>
);

/** Unified block renderer — dispatches to MarkdownBlock, ChartBlock, TableBlock, or CodeBlock */
export const BlockRenderer: React.FC<BlockRendererProps> = ({ blocks, chartDatas }) => {
  // Merge chartDatas into blocks if no blocks provided (backward compat)
  if ((!blocks || blocks.length === 0) && chartDatas && chartDatas.length > 0) {
    blocks = chartDatas.map(cd => ({ type: 'chart' as BlockType, chartSpec: cd }));
  }

  if (!blocks || blocks.length === 0) return null;

  return (
    <div className="space-y-2">
      {blocks.map((block, idx) => {
        const key = block.id || `block-${idx}`;
        switch (block.type) {
          case 'markdown':
            return <MarkdownBlock key={key} content={block.content || ''} />;
          case 'chart':
            return block.chartSpec ? <ChartBlock key={key} chartSpec={block.chartSpec} /> : null;
          case 'table':
            return <TableBlock key={key} content={block.content || ''} />;
          case 'code':
            return <CodeBlock key={key} content={block.content || ''} language={block.language} />;
          default:
            return block.content ? <MarkdownBlock key={key} content={block.content} /> : null;
        }
      })}
    </div>
  );
};
