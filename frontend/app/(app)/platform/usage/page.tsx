'use client';

import { useState } from 'react';
import { BarChart2, TrendingUp, TrendingDown, Calendar, Download, CreditCard } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

interface UsageMetric {
  label: string;
  value: string;
  change: number;
  unit: string;
}

const usageMetrics: UsageMetric[] = [
  { label: 'API Requests', value: '124,532', change: 12.5, unit: 'requests' },
  { label: 'Tokens Used', value: '2.4M', change: -3.2, unit: 'tokens' },
  { label: 'Audio Minutes', value: '847', change: 8.1, unit: 'minutes' },
  { label: 'Images Generated', value: '156', change: 22.3, unit: 'images' },
];

const dailyUsage = [
  { date: 'Jan 25', requests: 4200, cost: 12.50 },
  { date: 'Jan 26', requests: 3800, cost: 11.20 },
  { date: 'Jan 27', requests: 5100, cost: 15.30 },
  { date: 'Jan 28', requests: 4600, cost: 13.80 },
  { date: 'Jan 29', requests: 4900, cost: 14.70 },
  { date: 'Jan 30', requests: 5500, cost: 16.50 },
  { date: 'Jan 31', requests: 4100, cost: 12.30 },
];

export default function UsagePage() {
  const [period, setPeriod] = useState('month');

  return (
    <div className="flex-1 p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <BarChart2 className="w-6 h-6" />
              Usage
            </h1>
            <p className="text-muted-foreground mt-1">
              Monitor your API usage and costs
            </p>
          </div>
          <div className="flex gap-2">
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger className="w-[150px]">
                <Calendar className="w-4 h-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="day">Today</SelectItem>
                <SelectItem value="week">This Week</SelectItem>
                <SelectItem value="month">This Month</SelectItem>
                <SelectItem value="year">This Year</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {usageMetrics.map((metric) => (
            <Card key={metric.label}>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">{metric.label}</p>
                  <div
                    className={cn(
                      'flex items-center text-xs font-medium',
                      metric.change >= 0 ? 'text-green-600' : 'text-red-600'
                    )}
                  >
                    {metric.change >= 0 ? (
                      <TrendingUp className="w-3 h-3 mr-1" />
                    ) : (
                      <TrendingDown className="w-3 h-3 mr-1" />
                    )}
                    {Math.abs(metric.change)}%
                  </div>
                </div>
                <p className="text-2xl font-bold mt-2">{metric.value}</p>
                <p className="text-xs text-muted-foreground">{metric.unit}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="breakdown">Cost Breakdown</TabsTrigger>
            <TabsTrigger value="limits">Rate Limits</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Daily Usage</CardTitle>
                <CardDescription>Requests and costs over the last 7 days</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] flex items-end gap-2">
                  {dailyUsage.map((day, i) => (
                    <div key={day.date} className="flex-1 flex flex-col items-center gap-2">
                      <div
                        className="w-full bg-primary/80 rounded-t"
                        style={{ height: `${(day.requests / 6000) * 250}px` }}
                      />
                      <span className="text-xs text-muted-foreground">{day.date.split(' ')[1]}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="grid lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Usage by Model</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {[
                    { model: 'GPT-4o', usage: 65, tokens: '1.56M' },
                    { model: 'GPT-4o Mini', usage: 25, tokens: '600K' },
                    { model: 'Claude 3.5 Sonnet', usage: 10, tokens: '240K' },
                  ].map((item) => (
                    <div key={item.model}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{item.model}</span>
                        <span className="text-muted-foreground">{item.tokens}</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${item.usage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Current Billing</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Current period</span>
                      <span>Jan 1 - Jan 31, 2024</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Usage to date</span>
                      <span className="text-2xl font-bold">$96.50</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Monthly budget</span>
                      <span>$150.00</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full" style={{ width: '64%' }} />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      You've used 64% of your monthly budget
                    </p>
                    <Button variant="outline" className="w-full">
                      <CreditCard className="w-4 h-4 mr-2" />
                      Manage Billing
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="breakdown" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Cost Breakdown</CardTitle>
                <CardDescription>Detailed breakdown of costs by service</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    { service: 'Language Models', cost: 72.30, percentage: 75 },
                    { service: 'Speech-to-Text', cost: 12.50, percentage: 13 },
                    { service: 'Text-to-Speech', cost: 8.20, percentage: 8.5 },
                    { service: 'Image Generation', cost: 3.50, percentage: 3.5 },
                  ].map((item) => (
                    <div key={item.service} className="flex items-center justify-between p-3 rounded-lg border">
                      <div>
                        <p className="font-medium">{item.service}</p>
                        <p className="text-sm text-muted-foreground">{item.percentage}% of total</p>
                      </div>
                      <p className="text-lg font-semibold">${item.cost.toFixed(2)}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="limits" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Rate Limits</CardTitle>
                <CardDescription>Current rate limits for your account</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    { endpoint: 'Chat Completions', limit: '10,000 RPM', used: 3200 },
                    { endpoint: 'Embeddings', limit: '5,000 RPM', used: 800 },
                    { endpoint: 'Image Generation', limit: '100 RPM', used: 12 },
                    { endpoint: 'Audio Transcription', limit: '500 RPM', used: 45 },
                  ].map((item) => (
                    <div key={item.endpoint} className="p-4 rounded-lg border">
                      <div className="flex justify-between mb-2">
                        <span className="font-medium">{item.endpoint}</span>
                        <span className="text-muted-foreground">{item.limit}</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${(item.used / parseInt(item.limit.replace(/,/g, ''))) * 100}%` }}
                        />
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
