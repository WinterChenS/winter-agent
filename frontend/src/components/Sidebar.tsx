import React from 'react';
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

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isMobileOpen,
  setMobileOpen
}) => {
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
        <div className="p-4">
          <button
            onClick={() => {
              onNewSession();
              setMobileOpen(false);
            }}
            className="w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 transition-colors"
          >
            <span>+ 新建对话</span>
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto py-2">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`
                group relative flex items-center px-4 py-3 cursor-pointer
                ${activeSessionId === session.id ? 'bg-gray-800' : 'hover:bg-gray-800/50'}
              `}
              onClick={() => {
                onSelectSession(session.id);
                setMobileOpen(false);
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
                  onDeleteSession(session.id);
                }}
                className="opacity-0 group-hover:opacity-100 ml-2 text-gray-500 hover:text-red-400"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
};
