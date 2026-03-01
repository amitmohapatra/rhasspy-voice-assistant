'use client';

import { useState, useEffect, useMemo } from 'react';
import { Bot, Plus, Settings, Trash2, Copy, Play, Save, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { api } from '@/lib/api';

interface APIModel {
  id: string;
  model_id: string;
  name: string;
  display_name: string;
  provider?: { name: string; display_name: string };
  provider_name?: string;
  category: string;
  status: string;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  model: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  tools: string[];
  isPublic: boolean;
}

export default function AgentBuilderPage() {
  const [agents, setAgents] = useState<Agent[]>([
    {
      id: '1',
      name: 'Customer Support Agent',
      description: 'Helps customers with inquiries and issues',
      model: 'gpt-4o',
      systemPrompt: 'You are a helpful customer support agent...',
      temperature: 0.7,
      maxTokens: 2048,
      tools: ['search', 'knowledge-base'],
      isPublic: false,
    },
  ]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(agents[0]);
  const [isEditing, setIsEditing] = useState(false);
  const [availableModels, setAvailableModels] = useState<APIModel[]>([]);

  useEffect(() => {
    async function loadModels() {
      try {
        const modelsRes = await api.listModels({ status: 'active', limit: 500 });
        const chatModels = (modelsRes.models || [] as APIModel[]).filter(
          m => !['embedding', 'audio_stt', 'audio_tts', 'reranking'].includes(m.category)
        );
        setAvailableModels(chatModels);
      } catch (err) {
        console.error('Failed to load models:', err);
      }
    }
    loadModels();
  }, []);

  const groupedModels = useMemo(() => {
    const groups: Record<string, APIModel[]> = {};
    for (const model of availableModels) {
      const provider = model.provider?.display_name || model.provider_name || 'Other';
      if (!groups[provider]) groups[provider] = [];
      groups[provider].push(model);
    }
    return groups;
  }, [availableModels]);

  const createNewAgent = () => {
    const newAgent: Agent = {
      id: Date.now().toString(),
      name: 'New Agent',
      description: '',
      model: 'gpt-4o',
      systemPrompt: '',
      temperature: 0.7,
      maxTokens: 2048,
      tools: [],
      isPublic: false,
    };
    setAgents([...agents, newAgent]);
    setSelectedAgent(newAgent);
    setIsEditing(true);
  };

  return (
    <div className="flex h-screen">
      {/* Agent List Sidebar */}
      <div className="w-72 border-r bg-muted/30 flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <Bot className="w-5 h-5" />
            Agent Builder
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Create and manage AI agents
          </p>
        </div>
        <div className="p-3 border-b">
          <Button onClick={createNewAgent} className="w-full" size="sm">
            <Plus className="w-4 h-4 mr-2" />
            New Agent
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent)}
              className={`w-full text-left p-3 rounded-lg transition-colors ${
                selectedAgent?.id === agent.id
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted'
              }`}
            >
              <div className="font-medium text-sm">{agent.name}</div>
              <div className={`text-xs mt-1 ${
                selectedAgent?.id === agent.id
                  ? 'text-primary-foreground/70'
                  : 'text-muted-foreground'
              }`}>
                {agent.model}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Agent Editor */}
      <div className="flex-1 overflow-y-auto p-6">
        {selectedAgent ? (
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-semibold">{selectedAgent.name}</h2>
                <p className="text-muted-foreground">Configure your AI agent</p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Play className="w-4 h-4 mr-2" />
                  Test
                </Button>
                <Button size="sm">
                  <Save className="w-4 h-4 mr-2" />
                  Save
                </Button>
              </div>
            </div>

            <Tabs defaultValue="configuration" className="space-y-6">
              <TabsList>
                <TabsTrigger value="configuration">Configuration</TabsTrigger>
                <TabsTrigger value="tools">Tools</TabsTrigger>
                <TabsTrigger value="knowledge">Knowledge</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
              </TabsList>

              <TabsContent value="configuration" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Basic Information</CardTitle>
                    <CardDescription>Set up your agent's identity</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">Name</Label>
                      <Input id="name" value={selectedAgent.name} placeholder="Agent name" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="description">Description</Label>
                      <Textarea
                        id="description"
                        value={selectedAgent.description}
                        placeholder="Describe what this agent does"
                        rows={2}
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Model Configuration</CardTitle>
                    <CardDescription>Choose the AI model and parameters</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>Model</Label>
                      <Select value={selectedAgent?.model || 'gpt-4o'}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(groupedModels).map(([provider, models]) => (
                            <div key={provider}>
                              <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">{provider}</div>
                              {models.map((model) => (
                                <SelectItem key={model.model_id} value={model.model_id}>
                                  {model.display_name}
                                </SelectItem>
                              ))}
                            </div>
                          ))}
                          {availableModels.length === 0 && (
                            <div className="px-2 py-1.5 text-xs text-muted-foreground">Loading models...</div>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Temperature: {selectedAgent.temperature}</Label>
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.1"
                          value={selectedAgent.temperature}
                          className="w-full"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Max Tokens</Label>
                        <Input type="number" value={selectedAgent.maxTokens} />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>System Prompt</CardTitle>
                    <CardDescription>Define your agent's behavior and personality</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-end">
                        <Button variant="outline" size="sm">
                          <Wand2 className="w-4 h-4 mr-2" />
                          Generate with AI
                        </Button>
                      </div>
                      <Textarea
                        value={selectedAgent.systemPrompt}
                        placeholder="You are a helpful assistant..."
                        rows={8}
                        className="font-mono text-sm"
                      />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="tools" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Available Tools</CardTitle>
                    <CardDescription>Enable tools for your agent to use</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {['Web Search', 'Code Interpreter', 'File Upload', 'Knowledge Base', 'API Calls'].map((tool) => (
                      <div key={tool} className="flex items-center justify-between p-3 rounded-lg border">
                        <div>
                          <div className="font-medium">{tool}</div>
                          <div className="text-sm text-muted-foreground">Enable {tool.toLowerCase()} capability</div>
                        </div>
                        <Switch />
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="knowledge" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Knowledge Sources</CardTitle>
                    <CardDescription>Connect knowledge bases to your agent</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center py-8 text-muted-foreground">
                      <p>No knowledge sources connected</p>
                      <Button variant="outline" className="mt-4">
                        <Plus className="w-4 h-4 mr-2" />
                        Add Knowledge Source
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="settings" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Agent Settings</CardTitle>
                    <CardDescription>Configure additional options</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">Public Agent</div>
                        <div className="text-sm text-muted-foreground">
                          Allow others to use this agent
                        </div>
                      </div>
                      <Switch checked={selectedAgent.isPublic} />
                    </div>
                    <div className="pt-4 border-t">
                      <Button variant="destructive" size="sm">
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete Agent
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Bot className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Select an agent or create a new one</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
