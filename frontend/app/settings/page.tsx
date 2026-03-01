'use client';

/**
 * Settings Index Page
 *
 * Redirects to profile settings by default.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function SettingsIndexPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings/profile');
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="animate-pulse text-gray-500">Loading...</div>
    </div>
  );
}
