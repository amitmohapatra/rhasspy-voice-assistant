/**
 * Capability System Types
 *
 * Types for the database-driven capability management system.
 */

// ==================== Capability Types (mirrors backend enum) ====================

export type CapabilityType =
  | 'file_search'
  | 'code_interpreter'
  | 'web_search'
  | 'image_generation'
  | 'vision'
  | 'audio_input'
  | 'audio_output'
  | 'video_input'
  | 'video_output'
  | 'function_calling'
  | 'parallel_functions'
  | 'structured_output'
  | 'extended_thinking'
  | 'chain_of_thought'
  | 'long_context'
  | 'streaming'
  | 'artifacts'
  | 'computer_use'
  | 'mcp';

export type ToolCategory = 'builtin' | 'function' | 'integration' | 'mcp' | 'custom';

export type CapabilityScope = 'vendor_native' | 'platform_provided' | 'user_custom';

// ==================== Capability Definition ====================

export interface CapabilityDefinition {
  id: string;
  capability_type: CapabilityType;
  display_name: string;
  description: string | null;
  icon: string | null;
  category: string;
  config_schema: Record<string, unknown>;
  default_config: Record<string, unknown>;
  vendor_mappings: Record<string, unknown>;
  requires_capabilities: string[];
  incompatible_with: string[];
  is_premium: boolean;
  is_beta: boolean;
  is_deprecated: boolean;
  sort_order: number;
}

// ==================== Model Capability ====================

export interface ModelCapability {
  id: string;
  model_id: string;
  capability_type: CapabilityType;
  is_enabled: boolean;
  config: Record<string, unknown>;
  vendor_implementation: Record<string, unknown>;
  limitations: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelCapabilitySummary {
  model_id: string;
  enabled_capabilities: CapabilityInfo[];
  disabled_capabilities: CapabilityInfo[];
  total_enabled: number;
  total_disabled: number;
}

export interface CapabilityInfo {
  type: CapabilityType;
  display_name: string;
  description: string | null;
  icon: string | null;
  config: Record<string, unknown>;
}

// ==================== Tool Capability Requirement ====================

export interface ToolCapabilityRequirement {
  id: string;
  tool_id: string;
  capability_type: CapabilityType;
  is_required: boolean;
  reason: string | null;
}

// ==================== Vendor Capability Mapping ====================

export interface VendorCapabilityMapping {
  id: string;
  provider_id: string;
  capability_type: CapabilityType;
  vendor_name: string;
  invocation_method: 'tool' | 'parameter' | 'header' | 'endpoint';
  api_config: Record<string, unknown>;
  default_params: Record<string, unknown>;
  supported_model_patterns: string[];
  excluded_model_patterns: string[];
  is_available: boolean;
  notes: string | null;
}

// ==================== API Request/Response Types ====================

export interface SetModelCapabilityRequest {
  capability_type: CapabilityType;
  is_enabled: boolean;
  config?: Record<string, unknown>;
  vendor_implementation?: Record<string, unknown>;
}

export interface BulkSetCapabilitiesRequest {
  capabilities: SetModelCapabilityRequest[];
}

export interface ToolCompatibilityRequest {
  tool_ids: string[];
  model_id: string;
}

export interface ToolCompatibilityResponse {
  compatible_tools: string[];
  incompatible_tools: {
    tool_id: string;
    missing_capabilities: string[];
    reason: string;
  }[];
}

export interface UpdateVendorMappingRequest {
  vendor_name?: string;
  invocation_method?: 'tool' | 'parameter' | 'header' | 'endpoint';
  api_config?: Record<string, unknown>;
  default_params?: Record<string, unknown>;
  supported_model_patterns?: string[];
  excluded_model_patterns?: string[];
  is_available?: boolean;
  notes?: string;
}

// ==================== UI Display Helpers ====================

export interface CapabilityCardData {
  type: CapabilityType;
  displayName: string;
  description: string;
  icon: string;
  category: string;
  isEnabled: boolean;
  isPremium: boolean;
  isBeta: boolean;
  config?: Record<string, unknown>;
}

export interface ModelCapabilityMatrix {
  models: {
    id: string;
    name: string;
    provider: string;
  }[];
  capabilities: CapabilityType[];
  matrix: Record<string, Record<CapabilityType, boolean>>;
}

// ==================== Capability Icon Mapping ====================

export const CAPABILITY_ICONS: Record<CapabilityType, string> = {
  file_search: 'FileSearch',
  code_interpreter: 'Code',
  web_search: 'Globe',
  image_generation: 'Image',
  vision: 'Eye',
  audio_input: 'Mic',
  audio_output: 'Volume2',
  video_input: 'Video',
  video_output: 'Film',
  function_calling: 'Function',
  parallel_functions: 'GitBranch',
  structured_output: 'Braces',
  extended_thinking: 'Brain',
  chain_of_thought: 'ListOrdered',
  long_context: 'FileText',
  streaming: 'Activity',
  artifacts: 'Box',
  computer_use: 'Monitor',
  mcp: 'Plug',
};

export const CAPABILITY_CATEGORIES: Record<string, CapabilityType[]> = {
  'Retrieval': ['file_search', 'web_search'],
  'Execution': ['code_interpreter', 'computer_use'],
  'Multimodal': ['vision', 'audio_input', 'video_input'],
  'Generation': ['image_generation', 'audio_output', 'video_output'],
  'Tools': ['function_calling', 'parallel_functions', 'mcp'],
  'Output': ['structured_output', 'streaming', 'artifacts'],
  'Reasoning': ['extended_thinking', 'chain_of_thought'],
  'Context': ['long_context'],
};

// ==================== Helper Functions ====================

export function getCapabilityDisplayName(type: CapabilityType): string {
  const names: Record<CapabilityType, string> = {
    file_search: 'File Search',
    code_interpreter: 'Code Interpreter',
    web_search: 'Web Search',
    image_generation: 'Image Generation',
    vision: 'Vision',
    audio_input: 'Audio Input',
    audio_output: 'Audio Output',
    video_input: 'Video Input',
    video_output: 'Video Output',
    function_calling: 'Function Calling',
    parallel_functions: 'Parallel Functions',
    structured_output: 'Structured Output',
    extended_thinking: 'Extended Thinking',
    chain_of_thought: 'Chain of Thought',
    long_context: 'Long Context',
    streaming: 'Streaming',
    artifacts: 'Artifacts',
    computer_use: 'Computer Use',
    mcp: 'MCP Protocol',
  };
  return names[type] || type;
}

export function getCapabilityDescription(type: CapabilityType): string {
  const descriptions: Record<CapabilityType, string> = {
    file_search: 'Search through uploaded files and documents',
    code_interpreter: 'Execute Python code in a sandboxed environment',
    web_search: 'Search the internet for real-time information',
    image_generation: 'Generate images from text descriptions',
    vision: 'Analyze and understand images and screenshots',
    audio_input: 'Process and transcribe audio input',
    audio_output: 'Generate speech and audio from text',
    video_input: 'Process and analyze video content',
    video_output: 'Generate video content',
    function_calling: 'Call custom functions and tools',
    parallel_functions: 'Execute multiple functions simultaneously',
    structured_output: 'Generate JSON or structured data',
    extended_thinking: 'Advanced reasoning with longer processing',
    chain_of_thought: 'Show step-by-step reasoning process',
    long_context: 'Handle very long conversations (100k+ tokens)',
    streaming: 'Stream responses token by token',
    artifacts: 'Create rich content artifacts',
    computer_use: 'Control computer through actions',
    mcp: 'Connect to external tools via MCP protocol',
  };
  return descriptions[type] || '';
}

export function isCapabilityAvailable(
  capability: CapabilityType,
  modelCapabilities: ModelCapability[],
): boolean {
  const cap = modelCapabilities.find(c => c.capability_type === capability);
  return cap?.is_enabled ?? false;
}

export function getIncompatibleCapabilities(
  selectedCapabilities: CapabilityType[],
  definitions: CapabilityDefinition[],
): CapabilityType[] {
  const incompatible = new Set<CapabilityType>();

  for (const selected of selectedCapabilities) {
    const definition = definitions.find(d => d.capability_type === selected);
    if (definition?.incompatible_with) {
      for (const incompat of definition.incompatible_with) {
        incompatible.add(incompat as CapabilityType);
      }
    }
  }

  return Array.from(incompatible);
}
