import { useState, useEffect } from 'react';

interface AgentDefinition {
  id: string;
  name: string;
  display_name: string;
  description: string;
  system_prompt: string;
  tools: string[];
  model_config: Record<string, any>;
  trigger_keywords: string[];
  collaboration_strategy: string;
  priority: number;
  enabled: boolean;
}

const AVAILABLE_TOOLS = ['search', 'time', 'browser', 'execute_python'];
const STRATEGIES = ['sequential', 'parallel', 'supervisor'];

export function AdminAgents() {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [editing, setEditing] = useState<AgentDefinition | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);

  const defaultAgent: AgentDefinition = {
    id: '',
    name: '',
    display_name: '',
    description: '',
    system_prompt: '',
    tools: [],
    model_config: { temperature: 0.7 },
    trigger_keywords: [],
    collaboration_strategy: 'sequential',
    priority: 0,
    enabled: true,
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/v1/agents/');
      const data = await res.json();
      setAgents(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to fetch agents', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleSave = async () => {
    if (!editing) return;
    const isNew = !editing.id;
    const url = isNew ? '/api/v1/agents/' : `/api/v1/agents/${editing.id}`;
    const method = isNew ? 'POST' : 'PUT';

    try {
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editing),
      });
      setShowForm(false);
      setEditing(null);
      fetchAgents();
    } catch (e) {
      console.error('Failed to save agent', e);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确认删除？')) return;
    try {
      await fetch(`/api/v1/agents/${id}`, { method: 'DELETE' });
      fetchAgents();
    } catch (e) {
      console.error('Failed to delete', e);
    }
  };

  const handleToggle = async (agent: AgentDefinition) => {
    try {
      await fetch(`/api/v1/agents/${agent.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...agent, enabled: !agent.enabled }),
      });
      fetchAgents();
    } catch (e) {
      console.error('Failed to toggle', e);
    }
  };

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Agent 专家池</h1>
        <button
          onClick={() => { setEditing({ ...defaultAgent }); setShowForm(true); }}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          + 新建 Agent
        </button>
      </div>

      {/* Agent List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 text-left">名称</th>
              <th className="px-4 py-3 text-left">策略</th>
              <th className="px-4 py-3 text-left">工具</th>
              <th className="px-4 py-3 text-left">关键词</th>
              <th className="px-4 py-3 text-center">状态</th>
              <th className="px-4 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr key={agent.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{agent.display_name}</div>
                  <div className="text-xs text-gray-400">{agent.name}</div>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 text-xs rounded bg-blue-50 text-blue-700">
                    {agent.collaboration_strategy}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 flex-wrap">
                    {agent.tools.map((t) => (
                      <span key={t} className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-600">{t}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {agent.trigger_keywords.slice(0, 3).join(', ')}
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => handleToggle(agent)}
                    className={`px-2 py-0.5 text-xs rounded ${agent.enabled ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}
                  >
                    {agent.enabled ? '启用' : '禁用'}
                  </button>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => { setEditing({ ...agent }); setShowForm(true); }}
                    className="text-blue-500 hover:text-blue-700 mr-3">编辑</button>
                  <button onClick={() => handleDelete(agent.id)}
                    className="text-red-500 hover:text-red-700">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal Form */}
      {showForm && editing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold mb-4">{editing.id ? '编辑 Agent' : '新建 Agent'}</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">名称 (name)</label>
                <input value={editing.name} onChange={e => setEditing({...editing, name: e.target.value})}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="researcher" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">显示名称</label>
                <input value={editing.display_name} onChange={e => setEditing({...editing, display_name: e.target.value})}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="研究员" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium mb-1">描述</label>
                <input value={editing.description} onChange={e => setEditing({...editing, description: e.target.value})}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="Agent 职责描述" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium mb-1">System Prompt</label>
                <textarea value={editing.system_prompt} onChange={e => setEditing({...editing, system_prompt: e.target.value})}
                  className="w-full border rounded px-3 py-2 text-sm h-32" placeholder="You are a helpful..." />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">协作策略</label>
                <select value={editing.collaboration_strategy} onChange={e => setEditing({...editing, collaboration_strategy: e.target.value})}
                  className="w-full border rounded px-3 py-2 text-sm">
                  {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">优先级</label>
                <input type="number" value={editing.priority} onChange={e => setEditing({...editing, priority: parseInt(e.target.value) || 0})}
                  className="w-full border rounded px-3 py-2 text-sm" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium mb-1">工具</label>
                <div className="flex gap-2 flex-wrap">
                  {AVAILABLE_TOOLS.map(t => (
                    <label key={t} className="flex items-center gap-1 text-sm">
                      <input type="checkbox" checked={editing.tools.includes(t)}
                        onChange={e => {
                          const tools = e.target.checked
                            ? [...editing.tools, t]
                            : editing.tools.filter(x => x !== t);
                          setEditing({...editing, tools});
                        }} />
                      {t}
                    </label>
                  ))}
                </div>
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium mb-1">触发关键词 (逗号分隔)</label>
                <input value={editing.trigger_keywords.join(', ')}
                  onChange={e => setEditing({...editing, trigger_keywords: e.target.value.split(',').map(s => s.trim()).filter(Boolean)})}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="搜索, 研究, 数据" />
              </div>
            </div>

            <div className="flex gap-3 justify-end mt-6">
              <button onClick={() => { setShowForm(false); setEditing(null); }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800">取消</button>
              <button onClick={handleSave}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
