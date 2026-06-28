import { useState, useEffect, useCallback } from 'react';
import { agentApi } from '../../../features/ai-chat/services/agent';
import type { AgentCreateRequest } from '../../../features/ai-chat/types/agent';
import { ToolSelector } from './ToolSelector';
import { TagInput } from './TagInput';
import { PromptEditor } from './PromptEditor';

const AVAILABLE_TOOLS = ['search', 'browser', 'execute_python', 'time'];
const COLLABORATION_STRATEGIES = ['sequential', 'parallel', 'supervisor'];

interface AgentDrawerProps {
  open: boolean;
  agentId?: string;
  onClose: () => void;
  onSave: () => void;
}

const defaultFormData: AgentCreateRequest = {
  name: '',
  display_name: '',
  description: '',
  enabled: true,
  icon: '',
  agent_type: '',
  system_prompt: '',
  tools: [],
  model_config: {
    model_name: '',
    temperature: 0.7,
    top_p: 1,
    max_tokens: 2048,
    streaming: true,
    json_mode: false,
  },
  trigger_keywords: [],
  collaboration_strategy: 'sequential',
  priority: 0,
  tags: [],
};

export function AgentDrawer({ open, agentId, onClose, onSave }: AgentDrawerProps) {
  const [form, setForm] = useState<AgentCreateRequest>(defaultFormData);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const isEdit = !!agentId;

  useEffect(() => {
    if (open) {
      if (agentId) {
        agentApi.getAgent(agentId).then(agent => {
          const { id: _id, created_at, updated_at, ...rest } = agent;
          setForm(rest as AgentCreateRequest);
        }).catch(console.error);
      } else {
        setForm(defaultFormData);
      }
    }
  }, [open, agentId]);

  const handleChange = useCallback(<K extends keyof AgentCreateRequest>(
    key: K,
    value: AgentCreateRequest[K]
  ) => {
    setForm(prev => ({ ...prev, [key]: value }));
  }, []);

  const handleModelConfigChange = useCallback(<K extends keyof NonNullable<AgentCreateRequest['model_config']>>(
    key: K,
    value: string | number | boolean
  ) => {
    setForm(prev => ({
      ...prev,
      model_config: { ...prev.model_config, [key]: value } as AgentCreateRequest['model_config'],
    }));
  }, []);

  const handleSave = async () => {
    setSaveError(null);
    if (!form.name.trim() || !form.display_name.trim() || !form.system_prompt.trim()) {
      setSaveError('请填写必填字段（名称、显示名称、System Prompt）');
      return;
    }
    setSaving(true);
    try {
      if (isEdit && agentId) {
        await agentApi.updateAgent(agentId, form);
      } else {
        await agentApi.createAgent(form);
      }
      onSave();
      onClose();
    } catch (e) {
      console.error('Save failed', e);
      setSaveError(e instanceof Error ? e.message : '保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* Overlay backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />
      )}

      {/* Drawer panel */}
      <div
        className={`
          fixed right-0 top-0 h-full z-50
          w-[520px] max-w-full bg-white shadow-xl
          transform transition-transform duration-300
          ${open ? 'translate-x-0' : 'translate-x-full'}
          flex flex-col
        `}
      >
        {open && (
          <>
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
              <h2 className="text-lg font-bold text-gray-800">
                {isEdit ? '编辑 Agent' : '新建 Agent'}
              </h2>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600" type="button">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Form body */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              {saveError && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {saveError}
                </div>
              )}

              {/* Basic Info */}
              <section>
                <h3 className="text-sm font-semibold text-gray-800 mb-3">基本信息</h3>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">名称 (name)</label>
                      <input
                        value={form.name}
                        onChange={e => handleChange('name', e.target.value)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                        placeholder="researcher"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">显示名称</label>
                      <input
                        value={form.display_name}
                        onChange={e => handleChange('display_name', e.target.value)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                        placeholder="研究员"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">描述</label>
                    <input
                      value={form.description || ''}
                      onChange={e => handleChange('description', e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="Agent 职责描述"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">图标 (emoji)</label>
                      <div className="flex flex-wrap gap-1 border border-gray-300 rounded-lg p-2">
                        {['🤖','📊','🌐','📄','🧠','🔍','💻','🎯','⚡','🔧','📈','🎨','🚀','💡','🛡️','🏆'].map(emoji => (
                          <button
                            key={emoji}
                            type="button"
                            onClick={() => handleChange('icon', emoji)}
                            className={`w-8 h-8 flex items-center justify-center rounded text-lg hover:bg-gray-100 ${form.icon === emoji ? 'bg-blue-100 ring-1 ring-blue-500' : ''}`}
                          >{emoji}</button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Agent 类型</label>
                      <select
                        value={form.agent_type || ''}
                        onChange={e => handleChange('agent_type', e.target.value)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">选择类型</option>
                        <option value="assistant">助手 (Assistant)</option>
                        <option value="coder">编码 (Coder)</option>
                        <option value="analyst">分析 (Analyst)</option>
                        <option value="researcher">研究 (Researcher)</option>
                        <option value="writer">写作 (Writer)</option>
                        <option value="custom">自定义 (Custom)</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">标签 (逗号分隔)</label>
                      <input
                        value={(form.tags || []).join(', ')}
                        onChange={e => handleChange('tags', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                        placeholder="search, research"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">优先级</label>
                      <input
                        type="number"
                        value={form.priority ?? 0}
                        onChange={e => handleChange('priority', parseInt(e.target.value) || 0)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="enabled"
                      checked={form.enabled ?? true}
                      onChange={e => handleChange('enabled', e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <label htmlFor="enabled" className="text-sm text-gray-700">启用</label>
                  </div>
                </div>
              </section>

              {/* System Prompt */}
              <section>
                <h3 className="text-sm font-semibold text-gray-800 mb-3">System Prompt</h3>
                <PromptEditor
                  value={form.system_prompt || ''}
                  onChange={(value) => handleChange('system_prompt', value)}
                  minHeight="150px"
                />
              </section>

              {/* Model Config */}
              <section>
                <h3 className="text-sm font-semibold text-gray-800 mb-3">模型配置</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">模型名称</label>
                    <input
                      value={form.model_config?.model_name || ''}
                      onChange={e => handleModelConfigChange('model_name', e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="gpt-4"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Temperature</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={form.model_config?.temperature ?? 0.7}
                        onChange={e => handleModelConfigChange('temperature', parseFloat(e.target.value) || 0)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Top P</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        value={form.model_config?.top_p ?? 1}
                        onChange={e => handleModelConfigChange('top_p', parseFloat(e.target.value) || 0)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Max Tokens</label>
                      <input
                        type="number"
                        value={form.model_config?.max_tokens ?? 2048}
                        onChange={e => handleModelConfigChange('max_tokens', parseInt(e.target.value) || 0)}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                    <div className="flex items-end gap-4 pb-2">
                      <label className="flex items-center gap-1.5 text-sm">
                        <input
                          type="checkbox"
                          checked={form.model_config?.streaming ?? true}
                          onChange={e => handleModelConfigChange('streaming', e.target.checked)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        Streaming
                      </label>
                      <label className="flex items-center gap-1.5 text-sm">
                        <input
                          type="checkbox"
                          checked={form.model_config?.json_mode ?? false}
                          onChange={e => handleModelConfigChange('json_mode', e.target.checked)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        JSON Mode
                      </label>
                    </div>
                  </div>
                </div>
              </section>

              {/* Tools */}
              <section>
                <h3 className="text-sm font-semibold text-gray-800 mb-3">工具</h3>
                <ToolSelector
                  selected={form.tools || []}
                  available={AVAILABLE_TOOLS}
                  onChange={tools => handleChange('tools', tools)}
                />
              </section>

              {/* Trigger Keywords */}
              <section>
                <h3 className="text-sm font-semibold text-gray-800 mb-3">触发关键词</h3>
                <TagInput
                  tags={form.trigger_keywords || []}
                  onChange={tags => handleChange('trigger_keywords', tags)}
                  placeholder="输入触发关键词后回车"
                />
              </section>

              {/* Advanced */}
              <section>
                <h3 className="text-sm font-semibold text-gray-800 mb-3">高级配置</h3>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">协作策略</label>
                  <select
                    value={form.collaboration_strategy || 'sequential'}
                    onChange={e => handleChange('collaboration_strategy', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {COLLABORATION_STRATEGIES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </section>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 shrink-0">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
                type="button"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 text-sm"
                type="button"
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
