'use client';

import { useState } from 'react';

interface ProviderInfo {
  name: string;
  display_name: string;
  description: string;
  requires_api_key: boolean;
}

interface ProviderModel {
  id: string;
  name: string;
  description?: string;
  dimensions?: number;
}

interface ProviderCardProps {
  provider: ProviderInfo;
  providerType: string;
  isSelected?: boolean;
  onSelect?: (provider: ProviderInfo) => void;
  onConfigure?: (provider: ProviderInfo) => void;
}

export function ProviderCard({
  provider,
  providerType,
  isSelected,
  onSelect,
  onConfigure,
}: ProviderCardProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={`
        relative p-4 rounded-lg border-2 transition-all cursor-pointer
        ${isSelected
          ? 'border-blue-500 bg-blue-500/10'
          : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'
        }
      `}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onSelect?.(provider)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-semibold text-white">{provider.display_name}</h3>
          <p className="text-sm text-gray-400 mt-1">{provider.description}</p>
        </div>

        {isSelected && (
          <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
            <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-3">
        {provider.requires_api_key && (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-900/50 text-yellow-300">
            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
            </svg>
            API Key
          </span>
        )}
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-300">
          {providerType}
        </span>
      </div>

      {(isHovered || isSelected) && onConfigure && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onConfigure(provider);
          }}
          className="absolute bottom-3 right-3 p-2 rounded-md bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      )}
    </div>
  );
}

export function ProviderCardSkeleton() {
  return (
    <div className="p-4 rounded-lg border-2 border-gray-700 bg-gray-800/50 animate-pulse">
      <div className="h-5 bg-gray-700 rounded w-1/3 mb-2"></div>
      <div className="h-4 bg-gray-700 rounded w-2/3"></div>
      <div className="flex gap-2 mt-3">
        <div className="h-5 bg-gray-700 rounded w-16"></div>
        <div className="h-5 bg-gray-700 rounded w-12"></div>
      </div>
    </div>
  );
}
