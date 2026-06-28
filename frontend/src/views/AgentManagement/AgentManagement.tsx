import { useState, useMemo } from 'react';
import { useAgent } from '../../features/ai-chat/hooks/useAgent';
import { AgentCard } from './components/AgentCard';
import { AgentDrawer } from './components/AgentDrawer';
import type { AgentInfo } from '../../features/ai-chat/types/agent';

const PAGE_SIZE = 12;

export function AgentManagement() {
  const { agents, loading, error, fetchAgents, deleteAgent, toggleAgent, cloneAgent } = useAgent();
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'priority' | 'created_at'>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingAgentId, setEditingAgentId] = useState<string | undefined>();

  const filtered = useMemo(() => {
    let result = agents;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(a =>
        a.name.toLowerCase().includes(q) ||
        a.display_name.toLowerCase().includes(q) ||
        (a.description || '').toLowerCase().includes(q) ||
        (a.tags || []).some(t => t.toLowerCase().includes(q))
      );
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortBy === 'name') cmp = a.display_name.localeCompare(b.display_name);
      else if (sortBy === 'priority') cmp = (a.priority ?? 0) - (b.priority ?? 0);
      else if (sortBy === 'created_at') cmp = (a.created_at || '').localeCompare(b.created_at || '');
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [agents, search, sortBy, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleCreate = () => {
    setEditingAgentId(undefined);
    setDrawerOpen(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        加载中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-500">
        加载失败: {error}
        <button onClick={() => fetchAgents()} className="ml-2 underline">重试</button>
      </div>
    );
  }

  return (
    <>
      <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Agent 管理</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm"
          >
            + 新建 Agent
          </button>
        </div>
      </div>

      {/* Search & Sort bar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="搜索 Agent..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <select
          value={`${sortBy}-${sortDir}`}
          onChange={e => {
            const [by, dir] = e.target.value.split('-') as [typeof sortBy, typeof sortDir];
            setSortBy(by);
            setSortDir(dir);
          }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="name-asc">名称 A-Z</option>
          <option value="name-desc">名称 Z-A</option>
          <option value="priority-desc">优先级 高-低</option>
          <option value="priority-asc">优先级 低-高</option>
          <option value="created_at-desc">最新创建</option>
          <option value="created_at-asc">最早创建</option>
        </select>
      </div>

      {/* Agent cards grid */}
      {paged.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-gray-400">
          <p className="text-lg mb-2">暂无 Agent</p>
          <p className="text-sm">点击"新建 Agent"创建第一个</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {paged.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onEdit={(id) => {
                setEditingAgentId(id);
                setDrawerOpen(true);
              }}
              onDelete={async (id) => {
                if (confirm('确认删除？')) await deleteAgent(id);
              }}
              onToggle={toggleAgent}
              onClone={cloneAgent}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <span className="text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      )}
        </div>

        <AgentDrawer
          open={drawerOpen}
          agentId={editingAgentId}
          onClose={() => setDrawerOpen(false)}
          onSave={fetchAgents}
        />
      </>
    );
  }
