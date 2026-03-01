'use client';

import { ReactNode } from 'react';
import type { RightPaneTab, ParseSubTab } from './types';

interface RightPaneProps {
  activeTab: RightPaneTab;
  setActiveTab: (tab: RightPaneTab) => void;
  parseSubTab: ParseSubTab;
  setParseSubTab: (tab: ParseSubTab) => void;
  elementCount: number;
  markdownView: ReactNode;
  jsonView: ReactNode;
  chatView: ReactNode;
}

export function RightPane({
  activeTab, setActiveTab,
  parseSubTab, setParseSubTab,
  elementCount,
  markdownView, jsonView, chatView,
}: RightPaneProps) {
  return (
    <div className="flex flex-col h-full bg-zinc-900 overflow-hidden">
      {/* Top tabs */}
      <div className="flex-shrink-0 border-b border-zinc-800">
        <div className="flex items-center px-4 py-2 gap-1">
          {(['parse', 'chat'] as RightPaneTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                activeTab === tab
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {tab === 'parse' ? 'Parse' : 'Chat'}
            </button>
          ))}

          {/* Parse sub-tabs */}
          {activeTab === 'parse' && (
            <>
              <div className="w-px h-4 bg-zinc-700 mx-2" />
              {(['markdown', 'json'] as ParseSubTab[]).map((sub) => (
                <button
                  key={sub}
                  onClick={() => setParseSubTab(sub)}
                  className={`px-2 py-1 text-[10px] font-medium rounded transition-colors ${
                    parseSubTab === sub
                      ? 'bg-zinc-700 text-white'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  {sub === 'markdown' ? 'Markdown' : 'JSON'}
                </button>
              ))}
              <span className="text-xs text-zinc-600 ml-auto">
                {elementCount} elements
              </span>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'parse' ? (
          parseSubTab === 'markdown' ? markdownView : jsonView
        ) : (
          chatView
        )}
      </div>
    </div>
  );
}
