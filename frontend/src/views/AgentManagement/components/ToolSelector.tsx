interface ToolSelectorProps {
  selected: string[];
  available: string[];
  onChange: (tools: string[]) => void;
}

export function ToolSelector({ selected, available, onChange }: ToolSelectorProps) {
  const handleToggle = (tool: string) => {
    if (selected.includes(tool)) {
      onChange(selected.filter(t => t !== tool));
    } else {
      onChange([...selected, tool]);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {available.map(tool => (
          <label key={tool} className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={selected.includes(tool)}
              onChange={() => handleToggle(tool)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-gray-700">{tool}</span>
          </label>
        ))}
      </div>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selected.map(tool => (
            <span key={tool} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-purple-100 text-purple-600 rounded-full">
              {tool}
              <button
                onClick={() => handleToggle(tool)}
                className="hover:text-purple-900 leading-none"
                type="button"
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
