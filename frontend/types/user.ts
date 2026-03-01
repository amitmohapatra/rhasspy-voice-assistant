/**
 * User Types
 */

export interface User {
  id: string;
  email: string;
  name?: string;
  full_name?: string;
  avatar_url?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  last_login_at?: string;
  preferences?: UserPreferences;
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  language: string;
  timezone: string;
  default_model?: string;
  default_provider?: string;
}

// ==================== Settings Sections ====================

export interface SettingsSection {
  id: string;
  title: string;
  description: string;
  icon: string;
  path: string;
}

export const SETTINGS_SECTIONS: SettingsSection[] = [
  { id: 'profile', title: 'Profile', description: 'Personal information, avatar, theme, and preferences', icon: 'User', path: '/settings/profile' },
  { id: 'api-keys', title: 'API Keys', description: 'Manage your personal API keys', icon: 'Key', path: '/settings/api-keys' },
  { id: 'providers', title: 'AI Providers', description: 'Manage AI providers and their configurations', icon: 'Cpu', path: '/settings/providers' },
];
