'use client';

import { useState } from 'react';
import { Video, Upload, Wand2, Download, Loader2, Play, Clock, FileVideo } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
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

export default function VideosPage() {
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [duration, setDuration] = useState('5');
  const [aspectRatio, setAspectRatio] = useState('16:9');

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setIsGenerating(true);
    // Simulate API call
    setTimeout(() => {
      setIsGenerating(false);
    }, 5000);
  };

  const recentVideos = [
    { id: '1', title: 'Ocean waves at sunset', duration: '5s', status: 'completed', thumbnail: 'https://placehold.co/320x180/2563eb/white?text=Video+1' },
    { id: '2', title: 'Abstract geometric animation', duration: '10s', status: 'processing', thumbnail: 'https://placehold.co/320x180/7c3aed/white?text=Video+2' },
    { id: '3', title: 'Nature time-lapse', duration: '15s', status: 'completed', thumbnail: 'https://placehold.co/320x180/10b981/white?text=Video+3' },
  ];

  return (
    <div className="flex-1 p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Video className="w-6 h-6" />
            Videos
          </h1>
          <p className="text-muted-foreground mt-1">
            Generate AI-powered videos
          </p>
        </div>

        <Tabs defaultValue="generate" className="space-y-6">
          <TabsList>
            <TabsTrigger value="generate">Generate</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>

          <TabsContent value="generate" className="space-y-6">
            <div className="grid lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Wand2 className="w-5 h-5" />
                    Text to Video
                  </CardTitle>
                  <CardDescription>Generate videos from text descriptions</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label>Prompt</Label>
                    <Textarea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="A drone flying over a beautiful mountain landscape at golden hour..."
                      rows={4}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Duration</Label>
                      <Select value={duration} onValueChange={setDuration}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="5">5 seconds</SelectItem>
                          <SelectItem value="10">10 seconds</SelectItem>
                          <SelectItem value="15">15 seconds</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Aspect Ratio</Label>
                      <Select value={aspectRatio} onValueChange={setAspectRatio}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="16:9">16:9 (Landscape)</SelectItem>
                          <SelectItem value="9:16">9:16 (Portrait)</SelectItem>
                          <SelectItem value="1:1">1:1 (Square)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Button
                    onClick={handleGenerate}
                    disabled={!prompt.trim() || isGenerating}
                    className="w-full"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Generating (~2-3 min)...
                      </>
                    ) : (
                      <>
                        <Video className="w-4 h-4 mr-2" />
                        Generate Video
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Upload className="w-5 h-5" />
                    Image to Video
                  </CardTitle>
                  <CardDescription>Animate a static image</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary transition-colors cursor-pointer">
                    <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Drag and drop an image here, or click to browse
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      PNG, JPG up to 10MB
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>Motion Description (optional)</Label>
                    <Input placeholder="Describe how the image should animate..." />
                  </div>

                  <Button variant="outline" className="w-full" disabled>
                    <Video className="w-4 h-4 mr-2" />
                    Upload and Animate
                  </Button>
                </CardContent>
              </Card>
            </div>

            {isGenerating && (
              <Card>
                <CardContent className="py-8">
                  <div className="text-center">
                    <Loader2 className="w-12 h-12 mx-auto mb-4 animate-spin text-primary" />
                    <h3 className="text-lg font-medium">Generating your video...</h3>
                    <p className="text-muted-foreground mt-1">
                      This usually takes 2-3 minutes. You can leave this page and check back later.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="history" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Recent Videos</CardTitle>
                <CardDescription>Your generated videos from the last 30 days</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {recentVideos.map((video) => (
                    <div key={video.id} className="rounded-lg border overflow-hidden">
                      <div className="aspect-video bg-muted relative group">
                        <img
                          src={video.thumbnail}
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                        {video.status === 'completed' && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button variant="secondary" size="icon">
                              <Play className="w-5 h-5" />
                            </Button>
                          </div>
                        )}
                        {video.status === 'processing' && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                            <Loader2 className="w-8 h-8 animate-spin text-white" />
                          </div>
                        )}
                        <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                          {video.duration}
                        </div>
                      </div>
                      <div className="p-3">
                        <h4 className="font-medium text-sm truncate">{video.title}</h4>
                        <div className="flex items-center justify-between mt-2">
                          <span className="text-xs text-muted-foreground capitalize">
                            {video.status}
                          </span>
                          {video.status === 'completed' && (
                            <Button variant="ghost" size="sm">
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
