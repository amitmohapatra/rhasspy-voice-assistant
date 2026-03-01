import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Bot, MessageSquare, Database, Zap, User2, Video } from 'lucide-react';

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-background to-secondary">
      {/* Navigation */}
      <nav className="border-b bg-background/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">Rhasspy</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/auth/login">
              <Button variant="ghost">Login</Button>
            </Link>
            <Link href="/auth/register">
              <Button>Get Started</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-24">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-6">
            Enterprise AI Voice Assistant
          </h1>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
            Build intelligent AI assistants with 3D avatars, knowledge bases, and powerful tool integrations.
            Powered by multiple LLM providers.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/auth/register">
              <Button size="lg" className="h-12 px-8 w-full sm:w-auto">
                Start Building
              </Button>
            </Link>
            <Link href="/chat">
              <Button size="lg" variant="outline" className="h-12 px-8 w-full sm:w-auto">
                <MessageSquare className="w-5 h-5 mr-2" />
                Text Chat Demo
              </Button>
            </Link>
            <Link href="/chat?mode=avatar">
              <Button size="lg" variant="outline" className="h-12 px-8 w-full sm:w-auto">
                <User2 className="w-5 h-5 mr-2" />
                Avatar Chat Demo
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-4 py-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">Two Ways to Chat</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Choose between text-based chat or immersive avatar conversations with voice
          </p>
        </div>
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto mb-16">
          <div className="p-8 bg-card border rounded-xl hover:shadow-lg transition-shadow">
            <MessageSquare className="h-12 w-12 text-primary mb-4" />
            <h3 className="text-2xl font-semibold mb-3">Text Chat</h3>
            <p className="text-muted-foreground mb-4">
              Traditional chat interface with streaming responses, markdown support,
              and conversation history. Perfect for productivity and quick interactions.
            </p>
            <ul className="text-sm text-muted-foreground space-y-2">
              <li>Streaming responses</li>
              <li>Markdown rendering</li>
              <li>Conversation history</li>
              <li>Multiple conversations</li>
            </ul>
          </div>
          <div className="p-8 bg-card border rounded-xl hover:shadow-lg transition-shadow">
            <User2 className="h-12 w-12 text-primary mb-4" />
            <h3 className="text-2xl font-semibold mb-3">Avatar Chat</h3>
            <p className="text-muted-foreground mb-4">
              Immersive 3D avatar experience with text-to-speech. The avatar animates
              while speaking, creating a more engaging interaction.
            </p>
            <ul className="text-sm text-muted-foreground space-y-2">
              <li>3D animated avatar</li>
              <li>Text-to-speech responses</li>
              <li>Emotion expressions</li>
              <li>Fullscreen mode</li>
            </ul>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            icon={<Bot className="h-10 w-10" />}
            title="AI Assistants"
            description="Create custom AI assistants with unique personalities, knowledge, and capabilities."
          />
          <FeatureCard
            icon={<Database className="h-10 w-10" />}
            title="Knowledge Bases"
            description="Upload documents and build searchable knowledge bases with RAG technology."
          />
          <FeatureCard
            icon={<Zap className="h-10 w-10" />}
            title="Tool Integrations"
            description="Connect to external services and APIs with powerful tool integrations."
          />
        </div>
      </section>

      {/* LLM Providers Section */}
      <section className="container mx-auto px-4 py-24 border-t">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">Multi-Provider Support</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Choose the best model for your use case. Switch between providers seamlessly.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-8">
          {['OpenAI', 'Anthropic', 'Google Gemini', 'AWS Bedrock', 'Custom Models'].map((provider) => (
            <div
              key={provider}
              className="px-6 py-3 bg-card border rounded-lg text-sm font-medium"
            >
              {provider}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-background">
        <div className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bot className="h-6 w-6 text-primary" />
              <span className="font-semibold">Rhasspy Voice Assistant</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Enterprise AI Platform
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="p-6 bg-card border rounded-xl hover:shadow-lg transition-shadow">
      <div className="text-primary mb-4">{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-muted-foreground">{description}</p>
    </div>
  );
}
