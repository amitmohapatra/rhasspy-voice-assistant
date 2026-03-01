/**
 * Shared TypeScript types for API entities.
 *
 * These types are generated from or aligned with the backend Pydantic schemas
 * to ensure type safety across the full stack.
 */

// ==================== Common Types ====================

export type UUID = string;
export type ISODateString = string;

export interface BaseEntity {
  id: UUID;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface PaginationParams {
  skip?: number;
  limit?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// ==================== Auth Types ====================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User extends BaseEntity {
  email: string;
  full_name?: string;
  is_active: boolean;
}

// ==================== Assistant Types ====================

export interface Assistant extends BaseEntity {
  name: string;
  description?: string;
  system_prompt: string;
  model: string;
  provider: string;
  temperature: number;
  max_tokens?: number;
  tools: string[];
  knowledge_base_ids: UUID[];
  avatar_config: Record<string, unknown>;
  voice_config: Record<string, unknown>;
  settings: Record<string, unknown>;
  is_active: boolean;
  is_public: boolean;
}

export interface AssistantCreate {
  name: string;
  description?: string;
  system_prompt: string;
  model?: string;
  provider?: string;
  temperature?: number;
  max_tokens?: number;
  tools?: string[];
  knowledge_base_ids?: UUID[];
  avatar_config?: Record<string, unknown>;
  voice_config?: Record<string, unknown>;
  settings?: Record<string, unknown>;
}

export type AssistantUpdate = Partial<AssistantCreate>;

export interface AssistantListResponse {
  items: Assistant[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBase[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ==================== Pipeline Info Types ====================

export interface PipelineInfoResponse {
  pipeline: Record<string, string>;
  message: string;
}

// ==================== Knowledge Base Types ====================

export type KnowledgeBaseStatus = 'pending' | 'processing' | 'ready' | 'error';

export type KBType = 'platform_managed' | 'provider_managed';

export interface KnowledgeBase extends BaseEntity {
  name: string;
  description?: string;
  kb_type: KBType;
  settings: Record<string, unknown>;
  status: KnowledgeBaseStatus;
  documents: Document[];
  document_count: number;
  total_chunks: number;
  pipeline_info: Record<string, string>;
  provider_id?: UUID;
  provider_kb_ref?: string;
  provider_config?: Record<string, unknown>;
}

export interface KnowledgeBaseCreate {
  name: string;
  description?: string;
  kb_type?: KBType;
  provider_id?: string;
  provider_config?: Record<string, unknown>;
}

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'error';

export interface Document extends BaseEntity {
  knowledge_base_id: UUID;
  filename: string;
  file_type?: string;
  file_size?: number;
  status: DocumentStatus;
  chunk_count: number;
  error_message?: string;
  structured_json_path?: string;
  page_count?: number;
  language?: string;
}

// ==================== Chat / Response Types ====================

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

export interface Conversation extends BaseEntity {
  assistant_id: UUID;
  user_id?: UUID;
  title?: string;
  latest_response_id?: UUID;
  response_count: number;
}

export type ResponseItemType = 'message' | 'function_call' | 'function_call_output' | 'rag_context';
export type ItemDirection = 'input' | 'output';
export type ResponseStatus = 'in_progress' | 'completed' | 'failed' | 'cancelled';

export interface ResponseItemSchema extends BaseEntity {
  item_type: ResponseItemType;
  direction: ItemDirection;
  sequence_order: number;
  role?: string;
  content?: string;
  call_id?: string;
  function_name?: string;
  function_arguments?: string;
  function_output?: string;
  rag_sources?: Record<string, unknown>[];
}

export interface ResponseSchema extends BaseEntity {
  conversation_id: UUID;
  assistant_id: UUID;
  previous_response_id?: UUID;
  model: string;
  provider: string;
  status: ResponseStatus;
  status_reason?: string;
  output: ResponseItemSchema[];
  usage: { input_tokens: number; output_tokens: number; total_tokens: number };
  metadata: Record<string, unknown>;
}

export interface CreateResponseRequest {
  assistant_id: UUID;
  input: Array<{
    type: 'message' | 'function_call_output';
    role?: string;
    content?: string;
    call_id?: string;
    output?: string;
  }>;
  previous_response_id?: UUID;
  conversation_id?: UUID;
  stream?: boolean;
  model?: string;
  provider?: string;
  instructions?: string;
  temperature?: number;
  max_tokens?: number;
  tool_ids?: string[];
  knowledge_base_ids?: UUID[];
  max_tool_rounds?: number;
  metadata?: Record<string, unknown>;
}

/** Flattened message for chat UI display. */
export interface ChatDisplayMessage {
  id: string;
  role: MessageRole;
  content: string;
  isStreaming?: boolean;
  created_at: string;
  toolCalls?: Array<{
    id: string;
    name: string;
    arguments: string;
    output?: string;
  }>;
}

// ==================== AI Model Types ====================

export type ProviderStatus = 'active' | 'degraded' | 'disabled' | 'maintenance' | 'deprecated';
export type ModelStatus = 'active' | 'beta' | 'deprecated' | 'disabled' | 'retired';
export type ModelCategory =
  // Chat & Reasoning
  | 'chat'
  | 'reasoning'
  | 'flagship'
  | 'standard'
  | 'efficient'
  | 'edge'
  // Specialized
  | 'coding'
  | 'code'
  | 'vision'
  | 'multimodal'
  | 'search'
  // Embeddings & Retrieval
  | 'embedding'
  | 'reranking'
  // Audio
  | 'audio_stt'
  | 'audio_tts'
  // Generation
  | 'image_gen'
  | 'video_gen'
  // Moderation & Safety
  | 'moderation'
  | 'translation';
export type ModelTier = 'free' | 'standard' | 'premium' | 'enterprise';
export type ProviderType = 'llm' | 'embedding' | 'audio' | 'image' | 'video';

export interface AIProvider extends BaseEntity {
  name: string;
  display_name: string;
  description?: string;
  website?: string;
  docs_url?: string;
  provider_type: ProviderType;
  status: ProviderStatus;
  status_message?: string;
  base_url?: string;
  api_version?: string;
  required_secrets?: string[];
  supports_streaming: boolean;
  supports_function_calling: boolean;
  supports_vision: boolean;
  supports_audio: boolean;
  default_rpm?: number;
  default_tpm?: number;
  logo_url?: string;
  color?: string;
  sort_order: number;
  model_count?: number;
}

export interface AIModel extends BaseEntity {
  provider_id: UUID;
  model_id: string;
  name: string;
  display_name: string;
  aliases?: string[];
  category: ModelCategory;
  tier: ModelTier;
  status: ModelStatus;
  short_description?: string;
  description?: string;
  best_for?: string[];
  limitations?: string[];
  context_window: number;
  max_output_tokens?: number;
  supports_tools: boolean;
  supports_vision: boolean;
  supports_audio: boolean;
  supports_streaming: boolean;
  supports_json_mode?: boolean;
  supports_fim?: boolean;
  supports_search?: boolean;
  supports_citations?: boolean;
  supports_documents?: boolean;
  supports_video?: boolean;
  supports_diarization?: boolean;
  supports_batch?: boolean;
  supports_ssml?: boolean;
  supports_voice_cloning?: boolean;
  supports_emotion?: boolean;
  supports_custom_voice?: boolean;
  is_reasoning_model: boolean;
  is_moe?: boolean;
  is_distilled?: boolean;
  parameter_count?: string;
  architecture?: string;
  // Pricing
  input_price_per_1m?: number;
  output_price_per_1m?: number;
  reasoning_token_price_per_1m?: number;
  input_price_per_minute?: number;
  output_price_per_1k_chars?: number;
  output_price_per_1m_chars?: number;
  // Embedding specific
  embedding_dimensions?: number;
  // Audio specific
  supported_formats?: string[];
  max_file_size_mb?: number;
  voices?: string[];
  output_formats?: string[];
  languages?: number;
  voices_count?: number;
  supported_languages?: number;
  // Display
  badge?: string;
  is_featured: boolean;
  is_default: boolean;
  sort_order?: number;
  provider_name?: string;
  provider_display_name?: string;
}

// ==================== Tool Types ====================

export type ToolType = 'function' | 'custom' | 'mcp' | 'builtin' | 'integration';

export interface Tool extends BaseEntity {
  type: string;
  name: string;
  display_name?: string;
  description?: string;
  category: string;
  icon?: string;
  schema_definition: Record<string, unknown>;
  implementation: Record<string, unknown>;
  required_secrets: string[];
  mcp_config?: Record<string, unknown>;
  is_active: boolean;
  is_system: boolean;
}

export interface ToolCreate {
  name: string;
  display_name?: string;
  description?: string;
  category?: string;
  icon?: string;
  schema_definition: Record<string, unknown>;
  implementation: Record<string, unknown>;
  required_secrets?: string[];
  mcp_config?: Record<string, unknown>;
}

// DB-driven vendor built-in tools
export interface BuiltinToolDB {
  id: string;
  provider_id: string;
  name: string;
  display_name: string;
  description: string | null;
  icon: string | null;
  category: string;
  capability_type: string;
  config_schema: Record<string, unknown>;
  default_config: Record<string, unknown>;
  api_config: Record<string, unknown>;
  is_builtin: boolean;
  is_active: boolean;
  is_preview: boolean;
  is_beta: boolean;
  is_deprecated: boolean;
  is_always_on: boolean;
  supported_model_patterns: string[];
  excluded_model_patterns: string[];
  docs_url: string | null;
  sort_order: number;
  vendor?: string;
  provider_name?: string;
  is_available?: boolean;
}

export interface AvailableToolsForModel {
  model_id: string;
  model_name: string;
  vendor: string;
  builtin_tools: BuiltinToolDB[];
  custom_tools: (Tool & { is_available: boolean; missing_capabilities?: string[]; unavailable_reason?: string })[];
  model_capabilities: { type: string; is_enabled: boolean; config?: Record<string, unknown> }[];
  total_available_tools: number;
}

export interface SecretMeta {
  id: string;
  project_id: string;
  key: string;
  description: string | null;
  category: string;
  used_by: string | null;
  is_required: boolean;
  is_set: boolean;
  created_at: string;
  updated_at: string;
}

export interface SecretCreate {
  key: string;
  value: string;
  description?: string;
  category?: string;
  used_by?: string;
}

export interface AdhocToolTestResult {
  success: boolean;
  result?: any;
  error?: string;
  status_code?: number;
  duration_ms?: number;
}

// ==================== Integration Types ====================

export type IntegrationAuthType = 'api_key' | 'oauth2' | 'webhook' | 'bearer_token';
export type IntegrationCategory =
  | 'communication'
  | 'productivity'
  | 'development'
  | 'email'
  | 'crm'
  | 'storage'
  | 'analytics'
  | 'custom';

export interface IntegrationCatalog extends BaseEntity {
  name: string;
  display_name: string;
  description?: string;
  icon?: string;
  category: IntegrationCategory;
  auth_type: IntegrationAuthType;
  auth_schema: Record<string, unknown>;
  test_endpoint?: string;
  tool_schemas: Record<string, unknown>[];
  setup_instructions?: string;
  docs_url?: string;
  sort_order: number;
  is_active: boolean;
  is_featured: boolean;
}

export interface UserIntegration extends BaseEntity {
  integration_id: UUID;
  is_verified: boolean;
  is_enabled: boolean;
  config: Record<string, unknown>;
  last_tested_at?: string;
  test_error?: string;
  catalog?: IntegrationCatalog;
}

export interface UserIntegrationCreate {
  integration_id: string;
  credentials: Record<string, unknown>;
  config?: Record<string, unknown>;
}

export interface UserIntegrationUpdate {
  credentials?: Record<string, unknown>;
  config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export interface IntegrationTestRequest {
  integration_id: string;
  credentials: Record<string, unknown>;
}

export interface IntegrationTestResponse {
  success: boolean;
  message: string;
  status_code?: number;
  duration_ms?: number;
}

// ==================== Project Types ====================

export interface Project extends BaseEntity {
  name: string;
  description?: string;
  assistant_ids: UUID[];
  settings: Record<string, unknown>;
  is_active: boolean;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  assistant_ids?: UUID[];
  settings?: Record<string, unknown>;
}

// ==================== Avatar Types ====================

export interface Avatar extends BaseEntity {
  name: string;
  description?: string;
  model_url: string;
  thumbnail_url?: string;
  animation_config: Record<string, unknown>;
  voice_config: Record<string, unknown>;
  is_system: boolean;
  is_public: boolean;
}

// ==================== Analytics Types ====================

export interface UsageStats {
  period_start: ISODateString;
  period_end: ISODateString;
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  by_model: Record<string, {
    requests: number;
    tokens: number;
    cost: number;
  }>;
  by_assistant: Record<string, {
    requests: number;
    tokens: number;
  }>;
}

// ==================== Voice Preset Types ====================

export interface VoicePreset extends BaseEntity {
  type: 'tts' | 'stt';
  name: string;
  config: Record<string, unknown>;
  is_default: boolean;
}

export interface VoicePresetCreate {
  type: 'tts' | 'stt';
  name: string;
  config: Record<string, unknown>;
  is_default?: boolean;
}

export interface VoicePresetUpdate {
  name?: string;
  config?: Record<string, unknown>;
  is_default?: boolean;
}

export interface VoicePresetListResponse {
  items: VoicePreset[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface VoiceProviderInfo {
  source: string;
  name: string;
  available: boolean;
  voices?: string[];
  reason?: string;
}

export interface AvailableVoiceProviders {
  tts: VoiceProviderInfo[];
  stt: VoiceProviderInfo[];
}

// ==================== Utility Types ====================

export type ApiEndpoint =
  | '/api/v1/auth/login'
  | '/api/v1/auth/register'
  | '/api/v1/auth/me'
  | '/api/v1/assistants'
  | '/api/v1/knowledge-bases'
  | '/api/v1/responses'
  | '/api/v1/ai/providers'
  | '/api/v1/ai/models'
  | '/api/v1/tools'
  | '/api/v1/integrations'
  | '/api/v1/projects'
  | '/api/v1/avatars';

// Type-safe API response mapping
export interface ApiResponseMap {
  '/api/v1/auth/login': AuthResponse;
  '/api/v1/auth/me': User;
  '/api/v1/assistants': Assistant[];
  '/api/v1/knowledge-bases': KnowledgeBase[];
  '/api/v1/ai/providers': AIProvider[];
  '/api/v1/ai/models': { models: AIModel[]; total: number };
  '/api/v1/tools': Tool[];
  '/api/v1/projects': Project[];
  '/api/v1/avatars': Avatar[];
}
