import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Conversation } from '../types/chat';

interface SidebarProps {
  sessions: Conversation[];
  activeSessionId?: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  isMobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}

interface NavItem {
  label: string;
  icon: string;
  route?: string;
  locked?: boolean;
  action?: () => void;
}

function SessionGroup({ title, sessions, activeSessionId, onSelect, onDelete }: {
  title: string;
  sessions: Conversation[];
  activeSessionId?: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (sessions.length === 0) return null;
  return (
    <div className="mb-2">
      <div className="px-4 py-1 text-xs text-gray-500 uppercase tracking-wider">{title}</div>
      {sessions.map(session => (
        <div
          key={session.id}
          className={`
            group relative flex items-center px-4 py-2 cursor-pointer
            ${activeSessionId === session.id ? 'bg-gray-800' : 'hover:bg-gray-800/50'}
          `}
          onClick={() => {
            onSelect(session.id);
          }}
        >
          <div className="flex-1 overflow-hidden">
            <div className="truncate text-sm text-gray-300">
              {session.title}
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(session.id);
            }}
            className="opacity-0 group-hover:opacity-100 ml-2 text-gray-500 hover:text-red-400 shrink-0"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isMobileOpen,
  setMobileOpen
}) => {
  const navigate = useNavigate();

  const navItems: NavItem[] = [
    { label: 'AI Studio', icon: 'sparkles', action: () => { navigate('/'); setMobileOpen(false); } },
    { label: 'New Chat', icon: 'plus', action: () => { onNewSession(); setMobileOpen(false); } },
    { label: 'Agents', icon: 'robot', action: () => { navigate('/agents'); setMobileOpen(false); } },
    { label: 'Tools', icon: 'wrench', locked: true },
    { label: 'Knowledge', icon: 'book', locked: true },
    { label: 'MCP', icon: 'plug', locked: true },
    { label: 'Settings', icon: 'cog', locked: true },
  ];

  // Group sessions by time period
  const { today, yesterday, earlier } = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;

    const groups: { today: Conversation[]; yesterday: Conversation[]; earlier: Conversation[] } = {
      today: [],
      yesterday: [],
      earlier: [],
    };

    for (const s of sessions) {
      const t = s.createdAt;
      if (t >= todayStart) groups.today.push(s);
      else if (t >= yesterdayStart) groups.yesterday.push(s);
      else groups.earlier.push(s);
    }

    return groups;
  }, [sessions]);

  const renderIcon = (icon: string) => {
    const icons: Record<string, JSX.Element> = {
      sparkles: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
      ),
      plus: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      ),
      robot: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
      wrench: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
      book: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      ),
      plug: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      cog: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    };
    return icons[icon] || null;
  };

  return (
    <>
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar container */}
      <div className={`
        fixed md:static inset-y-0 left-0 z-30
        w-64 bg-gray-900 text-white flex flex-col
        transition-transform duration-300 ease-in-out
        ${isMobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        {/* Navigation menu - sticky at top */}
        <div className="sticky top-0 bg-gray-900 z-10">
          <div className="px-4 py-4">
            <h2 className="text-lg font-bold text-white">AI Studio</h2>
          </div>
          <nav className="px-2 pb-2 space-y-0.5">
            {navItems.map((item) => (
              <button
                key={item.label}
                onClick={item.action}
                disabled={item.locked}
                className={`
                  w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm
                  ${item.locked
                    ? 'text-gray-600 cursor-not-allowed'
                    : 'text-gray-300 hover:text-white hover:bg-gray-800 transition-colors'
                  }
                `}
                title={item.locked ? 'Coming soon' : item.label}
              >
                <span className="shrink-0">{renderIcon(item.icon)}</span>
                <span className="text-left">{item.label}</span>
                {item.locked && (
                  <svg className="w-3 h-3 ml-auto text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                )}
              </button>
            ))}
          </nav>
          <div className="border-t border-gray-800 mx-4" />
        </div>

        {/* Recent Chats - scrollable */}
        <div className="flex-1 overflow-y-auto py-2">
          <div className="px-4 py-2 text-xs text-gray-500 uppercase tracking-wider">Recent Chats</div>
          <SessionGroup title="Today" sessions={today} activeSessionId={activeSessionId} onSelect={(id) => { onSelectSession(id); setMobileOpen(false); }} onDelete={onDeleteSession} />
          <SessionGroup title="Yesterday" sessions={yesterday} activeSessionId={activeSessionId} onSelect={(id) => { onSelectSession(id); setMobileOpen(false); }} onDelete={onDeleteSession} />
          <SessionGroup title="Earlier" sessions={earlier} activeSessionId={activeSessionId} onSelect={(id) => { onSelectSession(id); setMobileOpen(false); }} onDelete={onDeleteSession} />
        </div>
      </div>
    </>
  );
};
